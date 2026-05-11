from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text, func
import os
import sys
import onnxruntime as rt
import numpy as np
import pandas as pd
from src_integrated.database.db import get_db
from src_integrated.orchestrator import PipelineOrchestrator
from src_integrated.schemas.pydantic_models import IngestionRequest, ETLRequest, RawProduct
from pydantic import BaseModel

from fastapi.responses import HTMLResponse
from pathlib import Path

class IngestQueueRequest(BaseModel):
    batch_id: str
    limit: int = 100

app = FastAPI(title="Wise Purchaser Unified Backend")

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def serve_dashboard():
    dashboard_path = Path(__file__).parent / "templates" / "dashboard.html"
    if dashboard_path.exists():
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Dashboard HTML not found."

# ── Model Discovery & Loading (Requirement 2.1) ───────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATHS = {
    "price": os.path.join(BASE_DIR, "Volatility score ML pipeline", "model_14d.onnx"),
    "stability": os.path.join(BASE_DIR, "Volatility score ML pipeline", "stability_model_v2.onnx")
}

# Add ML Pipeline paths for ReAct initialization
sys.path.append(os.path.join(BASE_DIR, "ML_Pipeline", "Recommendation + Verification Layer", "verification_layer"))
sys.path.append(os.path.join(BASE_DIR, "ML_Pipeline", "Recommendation + Verification Layer", "Recommendation system"))

@app.on_event("startup")
def load_models():
    # 1. Load ONNX Inference Models
    app.state.models = {}
    for name, path in MODEL_PATHS.items():
        if os.path.exists(path):
            try:
                app.state.models[name] = rt.InferenceSession(path)
                print(f"[OK] Loaded {name} model from {path}")
            except Exception as e:
                print(f"[ERROR] Failed to load {name} model: {e}")
        else:
            print(f"[WARN] {name} model not found at {path}")
            
    # 2. Initialize ReAct Offline State (Requirement 3.1)
    try:
        from offline_state_builder import load_offline_state
        print("[INFO] Building Agentic ReAct Offline State...")
        app.state.react_state = load_offline_state()
        print("[OK] ReAct State Built Successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to build ReAct State: {e}")
        app.state.react_state = None

@app.post("/ingest")
def ingest_data(request: IngestionRequest, db: Session = Depends(get_db)):
    orchestrator = PipelineOrchestrator(db)
    try:
        count = orchestrator.ingest_raw_data(
            batch_id=request.batch_id,
            category=request.category,
            target_count=request.target_count,
            data=request.data
        )
        return {"status": "success", "rows_ingested": count, "batch_id": request.batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/etl")
def run_etl_batch(request: ETLRequest, req: Request, db: Session = Depends(get_db)):
    orchestrator = PipelineOrchestrator(db)
    success = orchestrator.process_batch_etl(request.batch_id)
    if not success:
        raise HTTPException(status_code=400, detail="ETL processing failed.")
    
    models = req.app.state.models
    forecast_success = orchestrator.run_forecasting_unified(request.batch_id, models)
    
    react_state = req.app.state.react_state
    verify_success = orchestrator.run_verification_react(request.batch_id, react_state)
    
    return {
        "status": "success", 
        "batch_id": request.batch_id, 
        "etl": "completed",
        "forecasting": "completed" if forecast_success else "failed",
        "verification": "completed" if verify_success else "failed"
    }

@app.post("/forecast")
def run_forecasting_batch(request: ETLRequest, req: Request, db: Session = Depends(get_db)):
    orchestrator = PipelineOrchestrator(db)
    models = req.app.state.models
    success = orchestrator.run_forecasting_unified(request.batch_id, models)
    if not success:
        raise HTTPException(status_code=400, detail="Forecasting failed.")
    return {"status": "success", "batch_id": request.batch_id}

@app.post("/verify")
def run_verification_batch(request: ETLRequest, req: Request, db: Session = Depends(get_db)):
    orchestrator = PipelineOrchestrator(db)
    react_state = req.app.state.react_state
    success = orchestrator.run_verification_react(request.batch_id, react_state)
    if not success:
        raise HTTPException(status_code=400, detail="Verification failed.")
    return {"status": "success", "batch_id": request.batch_id}

@app.post("/ingest/testing-queue")
def ingest_from_queue(request: IngestQueueRequest, db: Session = Depends(get_db)):
    orchestrator = PipelineOrchestrator(db)
    try:
        count = orchestrator.ingest_from_testing_queue(
            batch_id=request.batch_id,
            limit=request.limit
        )
        return {"status": "success", "rows_ingested": count, "batch_id": request.batch_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/batch-preview")
def preview_batch_layers(request: IngestQueueRequest, req: Request, db: Session = Depends(get_db)):
    import sqlite3
    import json
    import os
    
    queue_db_path = os.path.join(os.path.dirname(__file__), "database", "testing_queue.db")
    if not os.path.exists(queue_db_path):
        return {"error": "Queue DB not found"}
        
    conn = sqlite3.connect(queue_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT payload FROM raw_queue LIMIT ?", (request.limit,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {"error": "Queue is empty"}
        
    raw_dicts = [json.loads(r[0]) for r in rows]
    
    orchestrator = PipelineOrchestrator(db)
    results = orchestrator.process_external_batch(raw_dicts, models=req.app.state.models)
    return results

@app.get("/drift/{batch_id}")
def check_system_drift(batch_id: str, req: Request, db: Session = Depends(get_db)):
    from drift_monitor import DriftMonitor
    from src_integrated.database.models import RawScrapedData, PriceHistory, MLForecastShap
    
    if not hasattr(req.app.state, "drift_monitor") or req.app.state.drift_monitor is None:
        if req.app.state.react_state:
            req.app.state.drift_monitor = DriftMonitor(req.app.state.react_state)
        else:
            raise HTTPException(status_code=503, detail="ReAct state not initialized for drift monitoring.")
            
    if batch_id == "latest":
        from src_integrated.database.models import IngestionBatch
        latest_batch = db.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).first()
        if latest_batch:
            batch_id = latest_batch.batch_id
        else:
            return {"overall_drift": False, "status": "No batches found"}

    results = db.query(PriceHistory, MLForecastShap).join(MLForecastShap).filter(
        PriceHistory.product_id.in_(
            db.query(RawScrapedData.product_url).filter_by(batch_id=batch_id)
        )
    ).all()
    
    if not results:
        return {"overall_drift": False, "status": f"No data found for batch {batch_id}"}
        
    data = []
    for ph, shap in results:
        data.append({
            "current_price": ph.raw_current_price,
            "forecasted_price": shap.price_t_plus_14,
            "volatility_score": 100 - (shap.predicted_stability_score or 50),
            "price_14d_avg": ph.raw_current_price * 0.98,
            "months_since_release": ph.D_months or 12.0
        })
    df_live = pd.DataFrame(data)
    
    status = req.app.state.drift_monitor.check_drift(df_live)
    return status

@app.get("/dlq/items")
def get_dlq_items(db: Session = Depends(get_db)):
    from src_integrated.database.models import DailyRecommendation, PriceHistory, Product
    results = db.query(DailyRecommendation, PriceHistory, Product).join(
        PriceHistory, DailyRecommendation.price_history_id == PriceHistory.id
    ).join(
        Product, PriceHistory.product_id == Product.id
    ).filter(DailyRecommendation.status == "Human Review").all()
    
    items = []
    for rec, ph, p in results:
        items.append({
            "id": rec.id,
            "product_title": p.raw_title,
            "category": p.category,
            "routing_path": rec.routing_path,
            "intelligent_score": rec.intelligent_score,
            "current_price": ph.raw_current_price,
            "justification": rec.justification
        })
    return items

class DLQActionRequest(BaseModel):
    recommendation_id: int
    action: str

@app.post("/dlq/action")
def take_dlq_action(request: DLQActionRequest, req: Request, db: Session = Depends(get_db)):
    """
    Audit Fix #3 — Agentic Property 4 (Adapts to Outcomes):
    When a human approves a DLQ item, we inject its SHAP vector into the live
    FAISS index so the agent immediately uses it as a valid 'buy' neighbor
    for future RAG majority-vote queries.
    """
    from src_integrated.database.models import DailyRecommendation, PriceHistory, MLForecastShap
    import numpy as np

    rec = db.query(DailyRecommendation).filter_by(id=request.recommendation_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    if request.action == "approve":
        rec.status = "Approved"
        db.commit()

        # --- FAISS Memory Injection ---
        react_state = getattr(req.app.state, "react_state", None)
        if react_state:
            try:
                # Retrieve the SHAP row linked to this recommendation's price_history
                shap_row = db.query(MLForecastShap).filter_by(
                    price_history_id=rec.price_history_id
                ).first()

                if shap_row:
                    from react_router import SHAP_COLS
                    shap_vec = np.array([
                        getattr(shap_row, col.replace("shap_", "shap_"), 0.0) or 0.0
                        for col in SHAP_COLS
                    ], dtype=np.float32).reshape(1, -1)

                    # Add to live FAISS index so future RAG queries include this approved item
                    react_state["faiss_index"].add(np.ascontiguousarray(shap_vec))

                    # Append the ground-truth label so majority vote is updated
                    react_state["historical_labels"] = np.append(
                        react_state["historical_labels"], "Deflating Arbitrage"
                    )
                    print(f"  [DLQ] ✓ SHAP vector injected into FAISS index for rec {request.recommendation_id}")
            except Exception as e:
                # Non-fatal — approval is persisted even if FAISS injection fails
                print(f"  [DLQ] WARN: FAISS injection failed: {e}")

    elif request.action == "reject":
        rec.status = "Rejected"
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'approve' or 'reject'.")

    return {"status": "success", "message": f"Recommendation {request.recommendation_id} → {rec.status}"}

@app.get("/stats/react")
def get_react_stats(db: Session = Depends(get_db)):
    from src_integrated.database.models import DailyRecommendation
    
    path_counts = db.query(
        DailyRecommendation.routing_path, 
        func.count(DailyRecommendation.id)
    ).group_by(DailyRecommendation.routing_path).all()
    
    stats = {path: count for path, count in path_counts}
    standard_paths = [
        "Path 1 (Direct Dispatch)", "Path 2 (SHAP Re-check Approve)", "Path 2 (SHAP Re-check Reject)",
        "Path 3 (RAG Standard Approve)", "Path 3 (RAG Standard Reject)",
        "Path 4 (Human Review)", "Path 5 (RAG Tie Approve)", "Path 5 (RAG Tie Reject)",
        "Path 6 (RAG Zero-Success Approve)", "Path 6 (RAG Zero-Success Reject)",
        "Path 7 (Hard Reject)"
    ]
    for p in standard_paths:
        if p not in stats:
            stats[p] = 0
            
    return stats

@app.get("/stats/intelligence")
def get_intelligence_stats(db: Session = Depends(get_db)):
    from src_integrated.database.models import DailyRecommendation
    
    avg_score = db.query(func.avg(DailyRecommendation.intelligent_score)).scalar() or 0.0
    max_score = db.query(func.max(DailyRecommendation.intelligent_score)).scalar() or 0.0
    
    return {
        "avg_intelligent_score": round(avg_score, 3),
        "max_confidence": round(max_score, 3),
        "total_recommendations": db.query(DailyRecommendation).count()
    }

@app.get("/stats/price-distribution")
def get_price_distribution(db: Session = Depends(get_db)):
    """
    Dashboard: Get price vs forecast distribution for Zone 3.
    """
    from src_integrated.database.models import PriceHistory, MLForecastShap
    results = db.query(PriceHistory.raw_current_price, MLForecastShap.price_t_plus_14).join(
        MLForecastShap, PriceHistory.id == MLForecastShap.price_history_id
    ).order_by(PriceHistory.scrape_timestamp.desc()).limit(50).all()
    
    return [{"current": r[0], "forecast": r[1]} for r in results]

@app.get("/stats/drift-history")
def get_drift_history_stats(db: Session = Depends(get_db)):
    """
    Priority 1 Fix: Removed broken agentic_db import.
    Returns a rolling 7-day history of approval/rejection counts from the SQLite DB.
    """
    from src_integrated.database.models import DailyRecommendation
    from sqlalchemy import cast, Date as SADate
    import datetime

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    rows = db.query(
        DailyRecommendation.status,
        func.count(DailyRecommendation.id)
    ).filter(
        DailyRecommendation.created_at >= cutoff
    ).group_by(DailyRecommendation.status).all()

    return {status: count for status, count in rows}

@app.get("/stats/ingestion")
def get_ingestion_stats(db: Session = Depends(get_db)):
    from src_integrated.database.models import IngestionBatch, RawScrapedData
    import sqlite3
    
    batch_count = db.query(IngestionBatch).count()
    
    # Queue Depth
    queue_db_path = os.path.join(os.path.dirname(__file__), "database", "testing_queue.db")
    queue_depth = 0
    if os.path.exists(queue_db_path):
        try:
            conn = sqlite3.connect(queue_db_path)
            queue_depth = conn.execute("SELECT COUNT(*) FROM raw_queue").fetchone()[0]
            conn.close()
        except:
            pass
            
    # Priority 4 Fix: Compute real ETL success rate from IngestionBatch.status
    total_batches = db.query(IngestionBatch).count()
    completed_batches = db.query(IngestionBatch).filter(IngestionBatch.status == "completed").count()
    etl_success_rate = f"{(completed_batches / total_batches * 100):.1f}%" if total_batches > 0 else "N/A"

    return {
        "batch_count": batch_count,
        "queue_depth": queue_depth,
        "etl_success_rate": etl_success_rate,
        "completed_batches": completed_batches,
        "total_batches": total_batches
    }

@app.post("/system/retrain")
def trigger_retrain(req: Request, db: Session = Depends(get_db)):
    """
    Audit Fix #2 — Autonomous Retraining (Agentic Property 6):
    Rebuilds the entire offline state (FCM, SVM, FAISS, SHAP means) from the
    background dataset and hot-swaps it into app.state.react_state, so all
    subsequent live inference calls immediately use the new models.
    """
    try:
        from offline_state_builder import load_offline_state
        print("  [RETRAIN] Rebuilding offline ReAct state (SVM, FCM, FAISS, SHAP)...")
        new_state = load_offline_state()

        # Hot-swap the live app state so all subsequent requests use new models
        req.app.state.react_state = new_state

        # Also reset the drift monitor with the freshly trained baseline
        from drift_monitor import DriftMonitor
        req.app.state.drift_monitor = DriftMonitor(new_state)

        print("  [RETRAIN] ✓ Offline state rebuilt and hot-swapped.")
        return {
            "status": "success",
            "message": "Offline state fully rebuilt: SVM, FCM, FAISS, and SHAP mean vectors updated.",
            "fpc": float(new_state.get("fpc", 0.0))
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrain failed: {str(e)}")

@app.get("/status/{batch_id}")
def get_batch_status(batch_id: str, db: Session = Depends(get_db)):
    from src_integrated.database.models import IngestionBatch
    batch = db.query(IngestionBatch).filter_by(batch_id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return {
        "batch_id": batch.batch_id, 
        "status": batch.status, 
        "category": batch.category,
        "target_count": batch.target_count,
        "created_at": batch.created_at
    }

@app.get("/health")
def health_check(req: Request, db: Session = Depends(get_db)):
    """
    Audit Fix #1 — Live Drift Health Check (Zone 4 Dashboard):
    Returns 'degraded' status when the real DriftMonitor fires on the latest
    batch. The dashboard Zone 4 panel will turn red automatically.
    """
    drift_status = {"overall_drift": False, "signal_1": {}, "signal_2": {}}

    try:
        react_state = getattr(req.app.state, "react_state", None)
        if react_state:
            # Lazily initialize the drift monitor if not already running
            if not hasattr(req.app.state, "drift_monitor") or req.app.state.drift_monitor is None:
                from drift_monitor import DriftMonitor
                req.app.state.drift_monitor = DriftMonitor(react_state)

            # Run drift check against the most recent batch in the DB
            from src_integrated.database.models import IngestionBatch, PriceHistory, MLForecastShap, RawScrapedData
            latest_batch = db.query(IngestionBatch).order_by(IngestionBatch.created_at.desc()).first()
            if latest_batch:
                results = db.query(PriceHistory, MLForecastShap).join(
                    MLForecastShap, PriceHistory.id == MLForecastShap.price_history_id
                ).filter(
                    PriceHistory.product_id.in_(
                        db.query(RawScrapedData.product_url).filter_by(batch_id=latest_batch.batch_id)
                    )
                ).limit(200).all()

                if results:
                    data = [{
                        "current_price": ph.raw_current_price,
                        "forecasted_price": shap.price_t_plus_14,
                        "volatility_score": 100 - (shap.predicted_stability_score or 50),
                        "price_14d_avg": ph.raw_current_price * 0.98,
                        "months_since_release": ph.D_months or 12.0
                    } for ph, shap in results]
                    df_live = pd.DataFrame(data)
                    drift_status = req.app.state.drift_monitor.check_drift(df_live)
    except Exception as e:
        print(f"  [HEALTH] Drift check error (non-fatal): {e}")

    overall_drift = drift_status.get("overall_drift", False)
    return {
        "status": "degraded" if overall_drift else "healthy",
        "service": "Wise Purchaser API",
        "db": "wise_purchaser.sqlite",
        "drift_detected": overall_drift,
        "signal_1": drift_status.get("signal_1", {}),
        "signal_2": drift_status.get("signal_2", {})
    }

# ── New Dashboard-Required Endpoints ─────────────────────────────────────────

@app.get("/stats/cluster")
def get_cluster_stats(req: Request):
    """
    Zone 1 — Cluster Health: Returns FPC (Fuzzy Partition Coefficient) and
    centroid count from the live offline ReAct state.
    """
    react_state = getattr(req.app.state, "react_state", None)
    if not react_state:
        return {"fpc": None, "n_centroids": None, "status": "ReAct state not initialized"}

    fpc = react_state.get("fpc", 0.0)
    centroids = react_state.get("fcm_centroids", [])
    n_centroids = len(centroids) if centroids is not None else 0

    health = "Good" if fpc > 0.7 else "Degraded" if fpc > 0.5 else "Poor"
    return {
        "fpc": round(float(fpc), 4),
        "n_centroids": n_centroids,
        "health_label": health,
        "interpretation": "FPC measures cluster separation. >0.7 = well-separated, <0.5 = overlapping clusters."
    }


@app.get("/stats/shap-reliability")
def get_shap_reliability(req: Request, db: Session = Depends(get_db)):
    """
    Zone 4 — SHAP Reliability: Computes cosine similarity between each recent
    product's SHAP vector and the offline mean SHAP vector.
    Returns a distribution (min, mean, max, histogram buckets).
    """
    import numpy as np
    from src_integrated.database.models import MLForecastShap

    react_state = getattr(req.app.state, "react_state", None)
    if not react_state:
        return {"error": "ReAct state not initialized"}

    mean_vec = react_state.get("mean_shap_vector")
    if mean_vec is None:
        return {"error": "mean_shap_vector not found in react_state"}

    SHAP_DB_COLS = [
        "shap_compute_potential", "shap_delta_p_7d", "shap_delta_p_14d",
        "shap_delta_p_1d", "shap_vol_30d", "shap_official_egp_usd",
        "shap_cpi_inflation", "shap_is_major_sale_period",
        "shap_competitor_scarcity_count", "shap_volume_weight",
        "shap_D_months", "shap_k", "shap_import_lambda",
        "shap_missing_release_date", "shap_base_expected_price"
    ]

    rows = db.query(MLForecastShap).order_by(MLForecastShap.id.desc()).limit(200).all()
    if not rows:
        return {"cosine_values": [], "mean": 0, "min": 0, "max": 0}

    def cosine(v1, v2):
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        return float(np.dot(v1, v2) / (n1 * n2)) if n1 > 0 and n2 > 0 else 0.0

    cosine_scores = []
    for row in rows:
        vec = np.array([getattr(row, c, 0.0) or 0.0 for c in SHAP_DB_COLS], dtype=np.float32)
        cosine_scores.append(cosine(vec, mean_vec))

    cosine_arr = np.array(cosine_scores)
    hist, edges = np.histogram(cosine_arr, bins=10, range=(0, 1))
    return {
        "mean": round(float(np.mean(cosine_arr)), 4),
        "min": round(float(np.min(cosine_arr)), 4),
        "max": round(float(np.max(cosine_arr)), 4),
        "histogram": [
            {"range": f"{edges[i]:.1f}-{edges[i+1]:.1f}", "count": int(hist[i])}
            for i in range(len(hist))
        ],
        "reliability_threshold": 0.6,
        "samples": len(cosine_scores)
    }


@app.get("/stats/outcomes")
def get_outcome_stats(db: Session = Depends(get_db)):
    """
    Zone 5 — Outcome Tracking: Returns approved, rejected, pending, and emailed
    counts from daily_recommendations for overview display.
    """
    from src_integrated.database.models import DailyRecommendation

    total = db.query(DailyRecommendation).count()
    approved = db.query(DailyRecommendation).filter(DailyRecommendation.status == "Approved").count()
    rejected = db.query(DailyRecommendation).filter(DailyRecommendation.status == "Rejected").count()
    human_review = db.query(DailyRecommendation).filter(DailyRecommendation.status == "Human Review").count()
    emailed = db.query(DailyRecommendation).filter(DailyRecommendation.emailed == True).count()

    return {
        "total": total,
        "approved": approved,
        "rejected": rejected,
        "human_review": human_review,
        "emailed": emailed,
        "approval_rate": f"{(approved / total * 100):.1f}%" if total > 0 else "N/A"
    }


_PIPELINE_HALTED = False

@app.post("/system/halt")
def halt_pipeline(req: Request):
    """
    Priority 5 Fix — Kill Switch: Sets a global halt flag on app.state.
    The orchestrator checks this flag before accepting new batch jobs.
    """
    global _PIPELINE_HALTED
    _PIPELINE_HALTED = True
    req.app.state.halted = True
    return {"status": "halted", "message": "Pipeline emergency stop activated. No new batches will be processed."}


@app.post("/system/resume")
def resume_pipeline(req: Request):
    """Lifts the kill switch halt."""
    global _PIPELINE_HALTED
    _PIPELINE_HALTED = False
    req.app.state.halted = False
    return {"status": "active", "message": "Pipeline resumed."}


# ── Cache Logic (from original backend) ───────────────────────────────────────
_CACHED_PRODUCTS = None
_CACHED_CATEGORIES = None
_CACHED_STATS = None

def get_cached_data(db: Session):
    global _CACHED_PRODUCTS, _CACHED_CATEGORIES, _CACHED_STATS
    if _CACHED_PRODUCTS is None:
        from src_integrated.database.models import Product
        products = db.query(Product).limit(100).all()
        _CACHED_PRODUCTS = [p.id for p in products]
        _CACHED_CATEGORIES = list(set([p.category for p in products]))
        _CACHED_STATS = {"total_products": len(_CACHED_PRODUCTS)}
    return _CACHED_PRODUCTS, _CACHED_CATEGORIES, _CACHED_STATS

@app.get("/api/stats")
def get_api_stats(db: Session = Depends(get_db)):
    _, _, stats = get_cached_data(db)
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
