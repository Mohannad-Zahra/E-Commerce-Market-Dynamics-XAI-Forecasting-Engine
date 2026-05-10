"""
models.py
---------
SQLAlchemy ORM mapping for tables that ALREADY EXIST in electronics_history.db.
We do NOT create or migrate anything — the DB is read-only for our purposes.
"""
from __future__ import annotations
from sqlalchemy import Column, Integer, Float, Text, String
from database import Base


class TrainingFeature(Base):
    """Maps to the `master_training_features` table — 678k rows of real scraped data."""
    __tablename__ = "master_training_features"

    # SQLite has no PK defined on this table; we use rowid as a surrogate
    rowid = Column("rowid", Integer, primary_key=True)

    scrape_timestamp        = Column(Text)
    product_id              = Column(Text, index=True)   # URL used as unique product key
    raw_title               = Column(Text)
    official_egp_usd        = Column(Float)
    cpi_inflation           = Column(Float)
    is_major_sale_period    = Column(Integer)
    competitor_scarcity_count = Column(Integer)
    
    # Target and results
    price_t_plus_14         = Column(Float)
    stability_score         = Column(Float)
    predicted_stability_score = Column(Float)
    
    # Category and compute
    category                = Column(Text)
    compute_potential       = Column(Float)
    
    # Price deltas
    delta_p_1d              = Column(Float)
    delta_p_7d              = Column(Float)
    delta_p_14d             = Column(Float)
    vol_30d                 = Column(Float)


class Product(Base):
    """Maps to the `products` table — unique product metadata and thumbnails."""
    __tablename__ = "products"

    product_url        = Column(Text, primary_key=True)
    raw_title          = Column(Text)
    category           = Column(Text)
    brand              = Column(Text)
    raw_current_price  = Column(Integer)
    raw_original_price = Column(Integer)
    thumbnail          = Column(Text)
    images             = Column(Text)

