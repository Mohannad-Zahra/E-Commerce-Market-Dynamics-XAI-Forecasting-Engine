"""
main.py — Point_1 FastAPI Application
=======================================
Unified entry point for the Data Ingestion & ETL Layer.

Usage:
    cd <project_root>
    uvicorn Point_1.main:app --host 0.0.0.0 --port 8001 --reload

Swagger UI:  http://localhost:8001/docs
ReDoc:       http://localhost:8001/redoc

This runs on port 8001 to avoid conflicting with the existing
backend/main.py on port 8000.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from Point_1.db.engine import Base, engine, get_db, DATABASE_URL
from Point_1.db.models import (
    Batch,
    MacroEconomic,
    MLForecastShap,
    ProcessedProduct,
    Product,
    RawScrapedData,
)
from Point_1.db.schemas import HealthOut
from Point_1.api.scraper import router as scraper_router
from Point_1.api.etl import router as etl_router

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Point_1")

# ── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Wise Purchaser — Data Ingestion & ETL Layer (Point 1)",
    description=(
        "Phase 1 of the unified pipeline architecture. "
        "Provides endpoints for batch scraper ingestion and ETL feature engineering. "
        "All data flows through a single database — no CSV/JSON file I/O."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ────────────────────────────────────────────────────────────
app.include_router(scraper_router)
app.include_router(etl_router)


# ── Startup: Create tables ──────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    log.info("=" * 60)
    log.info("  Wise Purchaser — Point 1: Data Ingestion & ETL Layer")
    log.info("=" * 60)
    log.info(f"  Database: {DATABASE_URL}")

    # Create all tables defined in Point_1.db.models
    Base.metadata.create_all(bind=engine)
    log.info("  ✓ Database tables created/verified")
    log.info("=" * 60)


# ── Health endpoint ──────────────────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthOut,
    summary="Health check",
    tags=["System"],
)
def health(db: Session = Depends(get_db)):
    """Returns system health including database connectivity and record counts."""
    try:
        total_batches = db.query(func.count(Batch.id)).scalar() or 0
        total_raw = db.query(func.count(RawScrapedData.id)).scalar() or 0
        total_processed = db.query(func.count(ProcessedProduct.id)).scalar() or 0
    except Exception:
        total_batches = 0
        total_raw = 0
        total_processed = 0

    return HealthOut(
        status="ok",
        database=DATABASE_URL.split("///")[-1] if "///" in DATABASE_URL else DATABASE_URL,
        tables_created=True,
        total_batches=total_batches,
        total_raw_records=total_raw,
        total_processed_records=total_processed,
    )


# ── Root redirect ────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "Wise Purchaser — Point 1: Data Ingestion & ETL",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
