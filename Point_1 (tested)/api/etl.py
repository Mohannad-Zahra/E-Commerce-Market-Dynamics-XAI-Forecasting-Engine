"""
etl.py — ETL Processing API Router
=====================================
FastAPI endpoints that trigger and monitor ETL feature engineering.

Endpoints:
  POST /api/etl/run/{batch_id}    → Run ETL for a batch
  GET  /api/etl/status/{batch_id} → Get ETL processing status

Flow:
  1. Receives batch_id
  2. Queries raw_scraped_data for that batch
  3. Applies feature_engine.run_feature_engineering()
  4. Bulk-inserts results into processed_products
  5. Updates batch status
"""

from __future__ import annotations

import time
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Point_1.db.engine import get_db
from Point_1.db.models import Batch, ProcessedProduct, RawScrapedData
from Point_1.db.schemas import ETLRunResponse, ETLStatusOut
from Point_1.etl.feature_engine import get_category_distribution, run_feature_engineering

router = APIRouter(prefix="/api/etl", tags=["ETL Processing"])


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/etl/run/{batch_id} — Trigger ETL processing
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/run/{batch_id}",
    response_model=ETLRunResponse,
    summary="Run ETL feature engineering for a batch",
    description=(
        "Fetches all raw records for the given batch_id, applies the full "
        "feature engineering pipeline (category inference, hardware extraction, "
        "compute potential, price momentum), and writes results to processed_products."
    ),
)
def run_etl(batch_id: str, db: Session = Depends(get_db)):
    t0 = time.time()

    # 1. Validate batch
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")

    if batch.status == "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail=f"Batch '{batch_id}' ETL already completed. Use a new batch.",
        )

    # 2. Update status to ETL_RUNNING
    batch.status = "ETL_RUNNING"
    db.commit()

    try:
        # 3. Fetch raw data for this batch
        raw_records = (
            db.query(RawScrapedData)
            .filter(RawScrapedData.batch_id == batch_id)
            .all()
        )

        if not raw_records:
            batch.status = "FAILED"
            batch.error_message = "No raw records found for this batch."
            db.commit()
            raise HTTPException(
                status_code=404,
                detail=f"No raw records found for batch '{batch_id}'. Ingest data first.",
            )

        # 4. Convert ORM objects to DataFrame
        raw_data = []
        for r in raw_records:
            raw_data.append({
                "product_url": r.product_url,
                "raw_title": r.raw_title,
                "raw_current_price": r.raw_current_price,
                "raw_original_price": r.raw_original_price,
                "retailer_id": r.retailer_id,
                "scrape_timestamp": r.scrape_timestamp,
            })

        df_raw = pd.DataFrame(raw_data)

        # 5. Run feature engineering
        df_processed = run_feature_engineering(df_raw)

        # 6. Bulk insert into processed_products
        inserted_count = 0
        for _, row in df_processed.iterrows():
            record = ProcessedProduct(
                batch_id=batch_id,
                scrape_timestamp=row.get("scrape_timestamp"),
                product_url=row.get("product_url"),
                retailer_id=row.get("retailer_id"),
                raw_title=row.get("raw_title"),
                raw_current_price=row.get("raw_current_price"),
                raw_original_price=row.get("raw_original_price"),
                category=row.get("category"),
                brand=row.get("brand"),
                gpu=row.get("gpu"),
                gpu_tier_num=_safe_int(row.get("gpu_tier_num")),
                is_gaming=bool(row.get("is_gaming", False)),
                ram_gb=_safe_float(row.get("ram_gb")),
                storage_gb=_safe_float(row.get("storage_gb")),
                compute_potential=_safe_float(row.get("compute_potential")),
                global_release_date_str=row.get("global_release_date_str"),
                missing_release_date=bool(row.get("missing_release_date", True)),
                D_months=_safe_float(row.get("D_months")),
                k=_safe_float(row.get("k")),
                delta_p_1d=_safe_float(row.get("delta_p_1d")),
                delta_p_7d=_safe_float(row.get("delta_p_7d")),
                delta_p_14d=_safe_float(row.get("delta_p_14d")),
                vol_30d=_safe_float(row.get("vol_30d")),
                competitor_scarcity_count=_safe_int(row.get("competitor_scarcity_count")),
                volume_weight=_safe_float(row.get("volume_weight")),
                official_egp_usd=_safe_float(row.get("official_egp_usd")),
                cpi_inflation=_safe_float(row.get("cpi_inflation")),
                import_lambda=_safe_float(row.get("import_lambda")),
                multiplier=_safe_float(row.get("multiplier")),
                is_major_sale_period=bool(row.get("is_major_sale_period", False)),
                sale_event_label=row.get("sale_event_label"),
                sub_category=row.get("sub_category"),
                cpu=row.get("cpu"),
            )
            db.add(record)
            inserted_count += 1

        # 7. Update batch status
        batch.status = "COMPLETED"
        batch.etl_count = inserted_count
        batch.error_message = None
        db.commit()

        # 8. Build response
        elapsed = time.time() - t0
        cat_dist = get_category_distribution(df_processed)

        return ETLRunResponse(
            batch_id=batch_id,
            status="COMPLETED",
            processed_count=inserted_count,
            feature_columns=len(df_processed.columns),
            category_distribution=cat_dist,
            processing_time_seconds=round(elapsed, 3),
        )

    except HTTPException:
        raise
    except Exception as e:
        batch.status = "FAILED"
        batch.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"ETL processing failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/etl/status/{batch_id} — Check ETL status
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/status/{batch_id}",
    response_model=ETLStatusOut,
    summary="Get ETL processing status for a batch",
)
def get_etl_status(batch_id: str, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")

    return ETLStatusOut(
        batch_id=batch.batch_id,
        status=batch.status,
        etl_count=batch.etl_count,
        error_message=batch.error_message,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/etl/processed/{batch_id} — Get processed products
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/processed/{batch_id}",
    summary="Get processed products for a batch",
)
def get_processed_products(
    batch_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    records = (
        db.query(ProcessedProduct)
        .filter(ProcessedProduct.batch_id == batch_id)
        .limit(limit)
        .all()
    )

    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No processed products found for batch '{batch_id}'.",
        )

    results = []
    for r in records:
        results.append({
            "id": r.id,
            "batch_id": r.batch_id,
            "product_url": r.product_url,
            "raw_title": r.raw_title,
            "raw_current_price": r.raw_current_price,
            "category": r.category,
            "brand": r.brand,
            "gpu": r.gpu,
            "gpu_tier_num": r.gpu_tier_num,
            "is_gaming": r.is_gaming,
            "compute_potential": r.compute_potential,
            "ram_gb": r.ram_gb,
            "storage_gb": r.storage_gb,
            "delta_p_1d": r.delta_p_1d,
            "vol_30d": r.vol_30d,
            "delta_p_7d": r.delta_p_7d,
            "delta_p_14d": r.delta_p_14d,
            "scrape_timestamp": r.scrape_timestamp.isoformat() if r.scrape_timestamp else None,
        })

    return {"batch_id": batch_id, "count": len(results), "products": results}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_float(val) -> Optional[float]:
    """Convert value to float, returning None for NaN/None."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Convert value to int, returning None for NaN/None."""
    if val is None:
        return None
    try:
        import math
        f = float(val)
        return None if math.isnan(f) else int(f)
    except (ValueError, TypeError):
        return None
