"""
schemas.py — Unified Pydantic Schemas
=======================================
Request/response models for all API endpoints.

Naming convention:
  - *In    = request body (client → server)
  - *Out   = response body (server → client)
  - *Base  = shared fields
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Lifecycle
# ═══════════════════════════════════════════════════════════════════════════════

class BatchCreateIn(BaseModel):
    """Request body for POST /api/batch/start"""
    category: str = Field(
        default="all",
        description="Product category to scrape: 'laptop', 'phone', 'tablet', or 'all'.",
        examples=["laptop"],
    )
    target_count: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Number of products to scrape in this batch.",
        examples=[100],
    )


class BatchOut(BaseModel):
    """Response for batch status queries."""
    batch_id: str
    category: str
    target_count: int
    status: str
    scrape_count: int
    etl_count: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Raw Scraped Data (Scraper → Database)
# ═══════════════════════════════════════════════════════════════════════════════

class RawProductIn(BaseModel):
    """
    Single raw product record from the scraper.
    Minimal validation — just enough to ensure data integrity.
    """
    scrape_timestamp: Optional[datetime] = Field(
        default=None,
        description="Scrape time. Auto-assigned by the server if omitted (Max+1 rule).",
    )
    retailer_id: str = Field(
        ...,
        min_length=1,
        description="Retailer identifier: '2b_egypt', 'sigma_computer', 'dream2000', 'btech'.",
        examples=["2b_egypt"],
    )
    raw_title: str = Field(
        ...,
        min_length=1,
        description="Raw product title as scraped from the retailer page.",
        examples=["Lenovo LOQ 15IAX9I Gaming Laptop - Intel Core i7-12650HX - 16GB RAM - 512GB SSD - RTX 4060 8GB - 15.6 FHD 144Hz - Gray"],
    )
    raw_current_price: float = Field(
        ...,
        gt=0,
        description="Current selling price in EGP.",
        examples=[42999.0],
    )
    raw_original_price: Optional[float] = Field(
        default=None,
        description="Original/list price in EGP before discount (if available).",
        examples=[49999.0],
    )
    product_url: str = Field(
        ...,
        min_length=1,
        description="Full product URL (used as the unique product identifier).",
        examples=["https://www.2b.com.eg/en/lenovo-loq-15iax9i-gaming-laptop.html"],
    )

    @field_validator("raw_current_price", "raw_original_price", mode="before")
    @classmethod
    def clean_price(cls, v):
        """Strip currency symbols and commas from price strings."""
        if isinstance(v, str):
            cleaned = v.replace("EGP", "").replace(",", "").replace("£", "").strip()
            return float(cleaned) if cleaned else None
        return v


class RawProductOut(BaseModel):
    """Response after successful raw product insertion."""
    id: int
    batch_id: str
    raw_title: str
    raw_current_price: float
    product_url: str
    scrape_timestamp: datetime

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    """Response for batch ingestion endpoint."""
    batch_id: str
    inserted_count: int
    skipped_count: int
    total_in_batch: int
    errors: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Processed Products (ETL Output)
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessedProductOut(BaseModel):
    """ETL-processed product with all engineered features."""
    id: int
    batch_id: str
    scrape_timestamp: datetime
    product_url: str
    retailer_id: str
    raw_title: str
    raw_current_price: float
    raw_original_price: Optional[float] = None

    # Category & Hardware
    category: Optional[str] = None
    brand: Optional[str] = None
    gpu_tier_num: Optional[int] = None
    is_gaming: Optional[bool] = None
    compute_potential: Optional[float] = None

    # Price Features
    delta_p_1d: Optional[float] = None
    delta_p_7d: Optional[float] = None
    delta_p_14d: Optional[float] = None
    vol_30d: Optional[float] = None

    # Market Context
    competitor_scarcity_count: Optional[int] = None
    volume_weight: Optional[float] = None

    model_config = {"from_attributes": True}


class ETLRunResponse(BaseModel):
    """Response after ETL processing completes."""
    batch_id: str
    status: str
    processed_count: int
    feature_columns: int
    category_distribution: dict
    processing_time_seconds: float


class ETLStatusOut(BaseModel):
    """Status of ETL processing for a batch."""
    batch_id: str
    status: str
    etl_count: int
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# ML Forecast Schemas (Phase 2 — defined now for interface stability)
# ═══════════════════════════════════════════════════════════════════════════════

XAI_FEATURES_DOC = """
14 features in this exact order:
  0  compute_potential
  1  delta_p_7d
  2  delta_p_14d
  3  delta_p_1d
  4  vol_30d
  5  official_egp_usd
  6  cpi_inflation
  7  is_major_sale_period
  8  competitor_scarcity_count
  9  volume_weight
  10 D_months
  11 k
  12 import_lambda
  13 missing_release_date
"""


class PriceForecastRequest(BaseModel):
    features: List[float] = Field(
        ...,
        min_length=14,
        max_length=14,
        description=XAI_FEATURES_DOC,
        examples=[[0.11, 0, 0, 0, 0, 48.5, 35.0, 0, 2, 1.1, 24, 0.0003, 0.8, 0]],
    )


class PriceForecastResponse(BaseModel):
    model: str
    predicted_price_egp: float


class StabilityRequest(BaseModel):
    features: List[float] = Field(
        ...,
        min_length=14,
        max_length=14,
        description=XAI_FEATURES_DOC,
        examples=[[0.11, 0, 0, 0, 0, 48.5, 35.0, 0, 2, 1.1, 24, 0.0003, 0.8, 0]],
    )


class StabilityResponse(BaseModel):
    model: str
    predicted_stability_score: float


# ═══════════════════════════════════════════════════════════════════════════════
# Health / Stats
# ═══════════════════════════════════════════════════════════════════════════════

class HealthOut(BaseModel):
    status: str
    database: str
    tables_created: bool
    total_batches: int
    total_raw_records: int
    total_processed_records: int
