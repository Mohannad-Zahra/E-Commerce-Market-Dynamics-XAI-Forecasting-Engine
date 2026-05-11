"""
api.py
======
FastAPI service for the Agentic ReAct Verification Framework.
Endpoints correspond to loop layers with full context logging.

USAGE:
    uvicorn api:app --reload --port 8000

ENDPOINTS:
    POST /predict   — Run ReAct loop on candidate batch
    GET  /health    — Drift detection status
    POST /retrain   — Manual retrain trigger
    GET  /state     — Current model metadata
    POST /feedback  — DLQ approve/reject decision
    POST /ingest    — Ingest batch rows into DB
"""

import os
import sys
import time
import json
import logging
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure module paths
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Recommendation system"))

import react_router
from offline_state_builder import load_offline_state
from drift_monitor import DriftMonitor
from agentic_db import (
    init_agentic_db, insert_ingested_rows, get_rows_since_last_retrain,
    get_total_ingested_count, save_dlq_decision, get_dlq_history,
    get_dlq_stats, get_retrain_history, get_drift_history,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-15s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AgenticAPI")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------
class CandidateInput(BaseModel):
    model_id: str
    current_price: float
    forecasted_price: float
    price_14d_avg: float = 0.0
    volatility_score: float = 50.0
    months_since_release: float = 0.0
    r_score: float = 0.0
    vol_30d: float = 20.0
    product_title: str = ""
    category: str = ""


class PredictRequest(BaseModel):
    candidates: List[CandidateInput]


class FeedbackRequest(BaseModel):
    product_id: str
    decision: str  # "approved" or "rejected"
    routing_path: str = ""
    intelligent_score: float = 0.0
    signals: Dict[str, float] = {}
    shap_vector: List[float] = []
    product_title: str = ""


class IngestRow(BaseModel):
    product_id: str
    raw_title: str = ""
    category: str = ""
    current_price: Optional[float] = None
    forecasted_price: Optional[float] = None
    price_14d_avg: Optional[float] = None
    volatility_score: Optional[float] = None
    months_since_release: Optional[float] = None


class IngestRequest(BaseModel):
    rows: List[IngestRow]


# ---------------------------------------------------------------------------
# Application Lifecycle
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load offline state on startup, cleanup on shutdown."""
    logger.info("=" * 60)
    logger.info("🚀 Starting Agentic ReAct API Server...")
    logger.info("=" * 60)
    
    init_agentic_db()
    
    t0 = time.time()
    app.state.app_state = load_offline_state()
    app.state.drift_monitor = DriftMonitor(app.state.app_state)
    elapsed = time.time() - t0
    
    logger.info(f"✅ Offline state loaded in {elapsed:.1f}s")
    logger.info(f"   SVM: {type(app.state.app_state['svm_model']).__name__}")
    logger.info(f"   FCM Centroids: {app.state.app_state['fcm_centroids'].shape}")
    logger.info(f"   FAISS Vectors: {app.state.app_state['faiss_index'].ntotal}")
    logger.info(f"   FPC: {app.state.app_state['fpc']:.4f}")
    sarimax = app.state.app_state.get("sarimax_models")
    logger.info(f"   SARIMAX Models: {len(sarimax) if sarimax else 'None (fallback mode)'}")
    logger.info("=" * 60)
    
    yield
    
    logger.info("🛑 Shutting down Agentic ReAct API Server.")


app = FastAPI(
    title="Agentic ReAct Verification API",
    description="FastAPI service for the ReAct Agentic Verification Framework. "
                "Endpoints correspond to loop layers with full context logging.",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request/Response Logging Middleware
# ---------------------------------------------------------------------------
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class ContextLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        logger.info(f"→ {request.method} {request.url.path}")
        
        response = await call_next(request)
        
        elapsed = time.time() - t0
        logger.info(f"← {request.method} {request.url.path} | {response.status_code} | {elapsed:.3f}s")
        return response

app.add_middleware(ContextLoggingMiddleware)


# ---------------------------------------------------------------------------
# POST /predict — Run ReAct loop on candidate batch
# ---------------------------------------------------------------------------
@app.post("/predict")
async def predict(request: PredictRequest):
    """
    Accepts a batch of candidates, runs the full ReAct decision loop,
    and returns scored/routed results with signal breakdowns.
    """
    app_state = app.state.app_state
    
    # Convert Pydantic models to dicts for the router
    candidates = [c.model_dump() for c in request.candidates]
    
    t0 = time.time()
    dispatched, dlq = react_router.run_react_loop(candidates, app_state)
    elapsed = time.time() - t0
    
    # Persist to DB
    insert_ingested_rows(candidates)
    
    # Check row threshold for auto-retrain
    drift_monitor = app.state.drift_monitor
    should_retrain, rows_since = drift_monitor.check_row_threshold()
    retrain_triggered = False
    if should_retrain:
        logger.warning(f"Row threshold reached ({rows_since}). Auto-retraining...")
        new_state = drift_monitor.trigger_retrain(
            source_df=app_state["background_df"],
            trigger_reason="row_threshold",
        )
        retrain_triggered = new_state is not None
    
    # Build response
    def _serialize_candidate(c):
        result = {k: v for k, v in c.items() if k not in ("shap_vector",)}
        if "shap_vector" in c:
            result["shap_vector"] = c["shap_vector"].tolist() if hasattr(c["shap_vector"], "tolist") else c["shap_vector"]
        return result
    
    response = {
        "dispatched": [_serialize_candidate(d) for d in dispatched],
        "dead_letter_queue": [_serialize_candidate(d) for d in dlq],
        "summary": {
            "total_candidates": len(candidates),
            "dispatched_count": len(dispatched),
            "dlq_count": len(dlq),
            "processing_time_seconds": round(elapsed, 3),
            "retrain_triggered": retrain_triggered,
        },
        "context": {
            "timestamp": datetime.utcnow().isoformat(),
            "quota_limit": react_router.QUOTA_LIMIT,
            "faiss_vectors": app_state["faiss_index"].ntotal,
            "fpc": float(app_state["fpc"]),
        },
    }
    
    logger.info(f"Predict complete: {len(dispatched)} dispatched, {len(dlq)} DLQ in {elapsed:.3f}s")
    return response


# ---------------------------------------------------------------------------
# GET /health — Drift detection status
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    """Returns current drift detection status (Signal 1 + Signal 2)."""
    app_state = app.state.app_state
    drift_monitor = app.state.drift_monitor
    
    # Run drift check on a sample of background data
    sample = app_state["background_df"].sample(min(100, len(app_state["background_df"])))
    status = drift_monitor.check_drift(sample)
    
    return {
        "status": "degraded" if status["overall_drift"] else "healthy",
        "signal_1": status["signal_1"],
        "signal_2": status["signal_2"],
        "overall_drift": status["overall_drift"],
        "retrain_executed": status.get("retrain_executed", False),
        "rows_since_last_retrain": get_rows_since_last_retrain(),
        "total_ingested": get_total_ingested_count(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /retrain — Manual retrain trigger
# ---------------------------------------------------------------------------
@app.post("/retrain")
async def retrain():
    """Manually triggers a full retrain cycle (FCM + SVM + FAISS + SHAP)."""
    app_state = app.state.app_state
    drift_monitor = app.state.drift_monitor
    
    fpc_before = float(app_state["fpc"])
    faiss_before = app_state["faiss_index"].ntotal
    
    t0 = time.time()
    new_state = drift_monitor.trigger_retrain(
        source_df=app_state["background_df"],
        trigger_reason="api_manual",
    )
    elapsed = time.time() - t0
    
    if new_state is None:
        raise HTTPException(status_code=500, detail="Retrain failed. Check server logs.")
    
    return {
        "status": "success",
        "fpc_before": fpc_before,
        "fpc_after": float(new_state["fpc"]),
        "faiss_before": faiss_before,
        "faiss_after": new_state["faiss_index"].ntotal,
        "duration_seconds": round(elapsed, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /state — Current model metadata
# ---------------------------------------------------------------------------
@app.get("/state")
async def state():
    """Returns current model metadata (FPC, centroid count, FAISS size, etc.)."""
    app_state = app.state.app_state
    
    sarimax = app_state.get("sarimax_models")
    retrain_hist = get_retrain_history(limit=1)
    last_retrain = retrain_hist[0]["retrained_at"] if retrain_hist else "Never"
    
    return {
        "fpc": float(app_state["fpc"]),
        "n_clusters": int(app_state["fcm_centroids"].shape[0]),
        "centroid_dimensions": int(app_state["fcm_centroids"].shape[1]),
        "faiss_vectors": app_state["faiss_index"].ntotal,
        "faiss_dimension": app_state["faiss_index"].d,
        "historical_labels_count": len(app_state["historical_labels"]),
        "sarimax_models_loaded": len(sarimax) if sarimax else 0,
        "mean_shap_vector_norm": float(np.linalg.norm(app_state["mean_shap_vector"])),
        "total_ingested_rows": get_total_ingested_count(),
        "rows_since_last_retrain": get_rows_since_last_retrain(),
        "last_retrain": last_retrain,
        "dlq_stats": get_dlq_stats(),
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /feedback — DLQ approve/reject decision
# ---------------------------------------------------------------------------
@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    """
    Accepts a DLQ approve/reject decision.
    If approved, injects the candidate's SHAP vector into the live FAISS index.
    """
    if request.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")
    
    app_state = app.state.app_state
    
    candidate = {
        "model_id": request.product_id,
        "product_title": request.product_title,
        "routing_path": request.routing_path,
        "intelligent_score": request.intelligent_score,
        "signals": request.signals,
        "shap_vector": request.shap_vector,
    }
    
    # Save to database
    save_dlq_decision(candidate, decision=request.decision)
    
    faiss_updated = False
    if request.decision == "approved" and request.shap_vector:
        # Inject into live FAISS index
        shap_vec = np.array(request.shap_vector, dtype=np.float32).reshape(1, -1)
        app_state["faiss_index"].add(shap_vec)
        app_state["historical_labels"] = np.append(
            app_state["historical_labels"], "Deflating Arbitrage"
        )
        faiss_updated = True
        logger.info(f"FAISS updated: +1 vector (total: {app_state['faiss_index'].ntotal})")
    
    return {
        "status": "recorded",
        "product_id": request.product_id,
        "decision": request.decision,
        "faiss_updated": faiss_updated,
        "faiss_total_vectors": app_state["faiss_index"].ntotal,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# POST /ingest — Ingest batch rows into DB
# ---------------------------------------------------------------------------
@app.post("/ingest")
async def ingest(request: IngestRequest):
    """
    Ingest a batch of rows into the database.
    Checks row threshold and auto-retrains if needed.
    """
    rows = [r.model_dump() for r in request.rows]
    
    # Map to expected format
    formatted_rows = []
    for r in rows:
        formatted_rows.append({
            "model_id": r["product_id"],
            "product_title": r.get("raw_title", ""),
            "category": r.get("category", ""),
            "current_price": r.get("current_price"),
            "forecasted_price": r.get("forecasted_price"),
            "price_14d_avg": r.get("price_14d_avg"),
            "volatility_score": r.get("volatility_score"),
            "months_since_release": r.get("months_since_release"),
        })
    
    count = insert_ingested_rows(formatted_rows)
    
    # Check row threshold
    drift_monitor = app.state.drift_monitor
    should_retrain, rows_since = drift_monitor.check_row_threshold()
    retrain_triggered = False
    
    if should_retrain:
        logger.warning(f"Row threshold reached after ingest ({rows_since}). Auto-retraining...")
        new_state = drift_monitor.trigger_retrain(
            source_df=app.state.app_state["background_df"],
            trigger_reason="row_threshold",
        )
        retrain_triggered = new_state is not None
    
    return {
        "status": "ingested",
        "rows_inserted": count,
        "total_ingested": get_total_ingested_count(),
        "rows_since_last_retrain": rows_since,
        "retrain_triggered": retrain_triggered,
        "timestamp": datetime.utcnow().isoformat(),
    }
