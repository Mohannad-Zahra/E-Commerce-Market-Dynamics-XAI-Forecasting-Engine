"""
schemas.py  –  Pydantic request / response models
"""

from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, Field


# ── Database / Product ────────────────────────────────────────────────────────

class ProductOut(BaseModel):
    id: int
    title: str
    description: str
    price: float
    originalPrice: Optional[float] = None
    discountPercentage: float
    rating: float
    stock: int
    brand: str
    category: str
    thumbnail: str
    images: List[str]
    retailer_id: str
    product_url: str
    scrape_timestamp: str

    class Config:
        from_attributes = True


class ProductsResponse(BaseModel):
    products: List[ProductOut]
    total: int
    skip: int
    limit: int


# ── Model 1 & 2  –  XAI Forecasting (14 features) ──────────────────────────

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


# ── Stability Scoring ───────────────────────────────────────────────────

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
