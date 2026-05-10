"""
scraper.py — Scraper Ingestion API Router
==========================================
FastAPI endpoints that replace file-based scraper output.

Endpoints:
  POST /api/batch/start           → Create a new batch
  POST /api/batch/{id}/ingest     → Ingest raw products into a batch
  GET  /api/batch/{id}/status     → Get batch status
  GET  /api/batch/list            → List recent batches

Implements:
  - Pydantic validation on all inputs
  - Max+1 temporal continuity rule
  - Atomic batch lifecycle tracking
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from Point_1.db.engine import get_db
from Point_1.db.models import Batch, RawScrapedData
from Point_1.db.schemas import (
    BatchCreateIn,
    BatchOut,
    IngestResponse,
    RawProductIn,
    RawProductOut,
)

router = APIRouter(prefix="/api/batch", tags=["Scraper Ingestion"])


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/batch/start — Create a new batch
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/start",
    response_model=BatchOut,
    status_code=201,
    summary="Create a new scraping batch",
    description=(
        "Creates a new batch record with a unique batch_id. "
        "Use this batch_id to ingest raw products via /api/batch/{batch_id}/ingest."
    ),
)
def create_batch(body: BatchCreateIn, db: Session = Depends(get_db)):
    batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    batch = Batch(
        batch_id=batch_id,
        category=body.category,
        target_count=body.target_count,
        status="CREATED",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    return batch


# ═══════════════════════════════════════════════════════════════════════════════
# POST /api/batch/{batch_id}/ingest — Ingest raw products
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/{batch_id}/ingest",
    response_model=IngestResponse,
    summary="Ingest raw scraped products into a batch",
    description=(
        "Accepts a list of raw product records, validates them against the "
        "RawProduct schema, and bulk-inserts them into the raw_scraped_data table. "
        "Implements the Max+1 temporal continuity rule for scrape_timestamp."
    ),
)
def ingest_raw_products(
    batch_id: str,
    products: List[RawProductIn],
    db: Session = Depends(get_db),
):
    # 1. Validate batch exists
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    if batch.status not in ("CREATED", "SCRAPING"):
        raise HTTPException(
            status_code=409,
            detail=f"Batch '{batch_id}' is in status '{batch.status}' and cannot accept new data.",
        )

    # 2. Apply Max+1 temporal continuity rule
    max_ts = db.query(func.max(RawScrapedData.scrape_timestamp)).scalar()
    if max_ts is None:
        default_ts = datetime.now(timezone.utc)
    else:
        from datetime import timedelta
        default_ts = max_ts + timedelta(days=1)

    # 3. Bulk insert with validation
    inserted = 0
    skipped = 0
    errors: List[str] = []

    for i, product in enumerate(products):
        try:
            # Apply default timestamp if not provided
            ts = product.scrape_timestamp or default_ts

            record = RawScrapedData(
                batch_id=batch_id,
                scrape_timestamp=ts,
                retailer_id=product.retailer_id,
                raw_title=product.raw_title,
                raw_current_price=product.raw_current_price,
                raw_original_price=product.raw_original_price,
                product_url=product.product_url,
            )
            db.add(record)
            inserted += 1

        except Exception as e:
            skipped += 1
            errors.append(f"Row {i}: {str(e)}")

    # 4. Update batch metadata
    batch.status = "SCRAPING"
    batch.scrape_count = (batch.scrape_count or 0) + inserted

    db.commit()

    # Query total count after commit
    total_in_batch = (
        db.query(func.count(RawScrapedData.id))
        .filter(RawScrapedData.batch_id == batch_id)
        .scalar()
    )

    return IngestResponse(
        batch_id=batch_id,
        inserted_count=inserted,
        skipped_count=skipped,
        total_in_batch=total_in_batch,
        errors=errors,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/batch/{batch_id}/status — Batch status
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/{batch_id}/status",
    response_model=BatchOut,
    summary="Get batch status",
)
def get_batch_status(batch_id: str, db: Session = Depends(get_db)):
    batch = db.query(Batch).filter(Batch.batch_id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found.")
    return batch


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/batch/list — List recent batches
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/list",
    response_model=List[BatchOut],
    summary="List recent batches",
)
def list_batches(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    batches = (
        db.query(Batch)
        .order_by(Batch.created_at.desc())
        .limit(limit)
        .all()
    )
    return batches
