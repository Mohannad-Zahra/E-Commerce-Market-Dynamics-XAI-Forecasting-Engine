"""
models.py — Consolidated ORM Models
=====================================
Single authoritative schema for the entire Wise Purchaser pipeline.

Tables:
  batches              – Batch lifecycle tracking
  raw_scraped_data     – Raw scraper output (immutable after insertion)
  processed_products   – ETL feature-engineered output
  products             – Unique product metadata + thumbnails
  macro_economics      – Economic indicators per scrape date
  price_history        – Time-series price observations
  ml_forecast_shap     – ML predictions + SHAP attribution vectors
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from Point_1.db.engine import Base


# ═══════════════════════════════════════════════════════════════════════════════
# Batch Tracking
# ═══════════════════════════════════════════════════════════════════════════════

class Batch(Base):
    """
    Tracks each scraping + ETL cycle through its lifecycle.
    Status flow: CREATED → SCRAPING → ETL_RUNNING → COMPLETED / FAILED
    """
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=False, default="all")
    target_count = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="CREATED")
    scrape_count = Column(Integer, nullable=False, default=0)
    etl_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    raw_records = relationship("RawScrapedData", back_populates="batch", cascade="all, delete-orphan")
    processed_records = relationship("ProcessedProduct", back_populates="batch", cascade="all, delete-orphan")


# ═══════════════════════════════════════════════════════════════════════════════
# Raw Scraped Data (Scraper Output)
# ═══════════════════════════════════════════════════════════════════════════════

class RawScrapedData(Base):
    """
    Immutable record of raw scraper output.
    One row per product per scrape cycle. No transformations applied.
    """
    __tablename__ = "raw_scraped_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), ForeignKey("batches.batch_id"), nullable=False, index=True)
    scrape_timestamp = Column(DateTime, nullable=False)
    retailer_id = Column(String(100), nullable=False)
    raw_title = Column(Text, nullable=False)
    raw_current_price = Column(Float, nullable=False)
    raw_original_price = Column(Float, nullable=True)
    product_url = Column(Text, nullable=False)

    # Relationships
    batch = relationship("Batch", back_populates="raw_records")

    __table_args__ = (
        Index("ix_raw_product_ts", "product_url", "scrape_timestamp"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Processed Products (ETL Output)
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessedProduct(Base):
    """
    Feature-engineered product record produced by the ETL pipeline.
    Contains all computed features needed by the ML forecasting layer.
    """
    __tablename__ = "processed_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), ForeignKey("batches.batch_id"), nullable=False, index=True)

    # ── Temporal ─────────────────────────────────────────────────────────────
    scrape_timestamp = Column(DateTime, nullable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    product_url = Column(Text, nullable=False)
    retailer_id = Column(String(100), nullable=False)
    raw_title = Column(Text, nullable=False)

    # ── Prices ───────────────────────────────────────────────────────────────
    raw_current_price = Column(Float, nullable=False)
    raw_original_price = Column(Float, nullable=True)

    # ── Category & Hardware ──────────────────────────────────────────────────
    category = Column(String(20), nullable=True)         # "Laptop" | "Phone"
    sub_category = Column(String(50), nullable=True)
    brand = Column(String(50), nullable=True)
    cpu = Column(String(100), nullable=True)
    ram_gb = Column(Float, nullable=True)
    storage_gb = Column(Float, nullable=True)
    gpu = Column(String(100), nullable=True)
    gpu_tier_num = Column(Integer, nullable=True)         # 1-10
    is_gaming = Column(Boolean, nullable=True)

    # ── Compute Potential ────────────────────────────────────────────────────
    compute_potential = Column(Float, nullable=True)      # [0.0, 1.0]

    # ── Temporal Product Features ────────────────────────────────────────────
    global_release_date_str = Column(String(50), nullable=True)
    missing_release_date = Column(Boolean, nullable=True, default=True)
    D_months = Column(Float, nullable=True)               # Product age in months
    k = Column(Float, nullable=True)                      # Depreciation coefficient

    # ── Scale-Invariant Price Features ───────────────────────────────────────
    delta_p_1d = Column(Float, nullable=True)             # Daily pct change
    delta_p_7d = Column(Float, nullable=True)             # 7-day relative momentum
    delta_p_14d = Column(Float, nullable=True)            # 14-day relative momentum
    vol_30d = Column(Float, nullable=True)                # 30-day rolling volatility

    # ── Market Context ───────────────────────────────────────────────────────
    competitor_scarcity_count = Column(Integer, nullable=True)
    volume_weight = Column(Float, nullable=True)

    # ── Economic Indicators ──────────────────────────────────────────────────
    official_egp_usd = Column(Float, nullable=True)
    cpi_inflation = Column(Float, nullable=True)
    import_lambda = Column(Float, nullable=True)
    multiplier = Column(Float, nullable=True)
    is_major_sale_period = Column(Boolean, nullable=True)
    sale_event_label = Column(String(100), nullable=True)

    # Relationships
    batch = relationship("Batch", back_populates="processed_records")

    __table_args__ = (
        Index("ix_proc_product_ts", "product_url", "scrape_timestamp"),
        Index("ix_proc_category", "category"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Unique Product Metadata (for Frontend)
# ═══════════════════════════════════════════════════════════════════════════════

class Product(Base):
    """
    Unique product record with metadata and thumbnails.
    Updated by the ETL layer; consumed by the Frontend API.
    """
    __tablename__ = "products_unified"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_url = Column(Text, unique=True, nullable=False, index=True)
    raw_title = Column(Text, nullable=True)
    category = Column(String(20), nullable=True)
    brand = Column(String(50), nullable=True)
    raw_current_price = Column(Float, nullable=True)
    raw_original_price = Column(Float, nullable=True)
    thumbnail = Column(Text, nullable=True)
    images = Column(Text, nullable=True)
    last_seen = Column(DateTime, nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Macro-Economic Indicators
# ═══════════════════════════════════════════════════════════════════════════════

class MacroEconomic(Base):
    """Per-date economic indicators affecting price dynamics."""
    __tablename__ = "macro_economics_unified"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(String(10), unique=True, nullable=False, index=True)  # YYYY-MM-DD
    official_egp_usd = Column(Float, nullable=True)
    cpi_inflation = Column(Float, nullable=True)
    import_lambda = Column(Float, nullable=True)
    multiplier = Column(Float, nullable=True)
    is_major_sale_period = Column(Boolean, nullable=True)
    sale_event_label = Column(String(100), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# ML Forecast + SHAP (Phase 2 placeholder — tables created now)
# ═══════════════════════════════════════════════════════════════════════════════

class MLForecastShap(Base):
    """
    ML prediction results + SHAP attribution vectors.
    Populated by the ML Forecasting Layer (Phase 2).
    """
    __tablename__ = "ml_forecast_shap_unified"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_url = Column(Text, nullable=False, index=True)
    batch_id = Column(String(64), nullable=True, index=True)
    scrape_timestamp = Column(DateTime, nullable=True)

    # ── Predictions ──────────────────────────────────────────────────────────
    stability_score = Column(Float, nullable=True)
    predicted_stability_score = Column(Float, nullable=True)
    price_t_plus_14 = Column(Float, nullable=True)

    # ── SHAP Values ──────────────────────────────────────────────────────────
    shap_compute_potential = Column(Float, nullable=True)
    shap_delta_p_7d = Column(Float, nullable=True)
    shap_delta_p_14d = Column(Float, nullable=True)
    shap_delta_p_1d = Column(Float, nullable=True)
    shap_vol_30d = Column(Float, nullable=True)
    shap_official_egp_usd = Column(Float, nullable=True)
    shap_cpi_inflation = Column(Float, nullable=True)
    shap_is_major_sale_period = Column(Float, nullable=True)
    shap_competitor_scarcity_count = Column(Float, nullable=True)
    shap_volume_weight = Column(Float, nullable=True)
    shap_D_months = Column(Float, nullable=True)
    shap_k = Column(Float, nullable=True)
    shap_import_lambda = Column(Float, nullable=True)
    shap_missing_release_date = Column(Float, nullable=True)
    shap_base_expected_price = Column(Float, nullable=True)

    # ── Delta SHAP (T0 - T-14) ───────────────────────────────────────────────
    delta_shap_compute_potential = Column(Float, nullable=True)
    delta_shap_delta_p_7d = Column(Float, nullable=True)
    delta_shap_delta_p_14d = Column(Float, nullable=True)
    delta_shap_delta_p_1d = Column(Float, nullable=True)
    delta_shap_vol_30d = Column(Float, nullable=True)
    delta_shap_official_egp_usd = Column(Float, nullable=True)
    delta_shap_cpi_inflation = Column(Float, nullable=True)
    delta_shap_is_major_sale_period = Column(Float, nullable=True)
    delta_shap_competitor_scarcity_count = Column(Float, nullable=True)
    delta_shap_volume_weight = Column(Float, nullable=True)
    delta_shap_D_months = Column(Float, nullable=True)
    delta_shap_k = Column(Float, nullable=True)
    delta_shap_import_lambda = Column(Float, nullable=True)
    delta_shap_missing_release_date = Column(Float, nullable=True)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
