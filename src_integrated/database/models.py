from sqlalchemy import Column, String, Float, Boolean, Date, Integer, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class IngestionBatch(Base):
    __tablename__ = 'ingestion_batches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, unique=True, index=True)
    status = Column(String) # e.g., 'raw', 'processing', 'completed', 'failed'
    category = Column(String, nullable=True)
    target_count = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    raw_data = relationship("RawScrapedData", back_populates="batch")

class RawScrapedData(Base):
    __tablename__ = 'raw_scraped_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String, ForeignKey('ingestion_batches.batch_id'))
    scrape_timestamp = Column(DateTime)
    retailer_id = Column(String)
    raw_title = Column(String)
    raw_current_price = Column(Float)
    raw_original_price = Column(Float, nullable=True)
    product_url = Column(String)
    
    batch = relationship("IngestionBatch", back_populates="raw_data")

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(String, primary_key=True) # The unique product_id (URL or hash)
    retailer_id = Column(String)
    raw_title = Column(String)
    product_url = Column(String, nullable=True)
    category = Column(String)
    sub_category = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    cpu = Column(String, nullable=True)
    ram_gb = Column(Float, nullable=True)
    storage_gb = Column(Float, nullable=True)
    gpu = Column(String, nullable=True)
    is_gaming = Column(Boolean, nullable=True)
    global_release_date = Column(Date, nullable=True)
    global_release_date_str = Column(String, nullable=True)
    missing_release_date = Column(Boolean)
    compute_potential = Column(Float, nullable=True)
    thumbnail = Column(String, nullable=True)
    images = Column(String, nullable=True)

    price_history = relationship("PriceHistory", back_populates="product")

class MacroEconomic(Base):
    __tablename__ = 'macro_economics'
    
    date_id = Column(Date, primary_key=True) # Mapped from scrape_timestamp
    official_egp_usd = Column(Float)
    cpi_inflation = Column(Float)
    import_lambda = Column(Float)
    multiplier = Column(Float)
    is_major_sale_period = Column(Boolean)
    sale_event_label = Column(String, nullable=True)

    price_history = relationship("PriceHistory", back_populates="macro")

class PriceHistory(Base):
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(String, ForeignKey('products.id'))
    date_id = Column(Date, ForeignKey('macro_economics.date_id'))
    scrape_timestamp = Column(DateTime)
    
    raw_current_price = Column(Float)
    raw_original_price = Column(Float, nullable=True)
    
    competitor_scarcity_count = Column(Integer)
    volume_weight = Column(Float)
    k = Column(Float)
    D_months = Column(Float)
    
    delta_p_1d = Column(Float)
    delta_p_7d = Column(Float)
    delta_p_14d = Column(Float)
    vol_30d = Column(Float)
    
    product = relationship("Product", back_populates="price_history")
    macro = relationship("MacroEconomic", back_populates="price_history")
    ml_forecast_shap = relationship("MLForecastShap", back_populates="price_history", uselist=False)

class MLForecastShap(Base):
    __tablename__ = 'ml_forecast_shap'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    price_history_id = Column(Integer, ForeignKey('price_history.id'))
    
    stability_score = Column(Float)
    predicted_stability_score = Column(Float)
    price_t_plus_14 = Column(Float)
    
    shap_compute_potential = Column(Float)
    shap_delta_p_7d = Column(Float)
    shap_delta_p_14d = Column(Float)
    shap_delta_p_1d = Column(Float)
    shap_vol_30d = Column(Float)
    shap_official_egp_usd = Column(Float)
    shap_cpi_inflation = Column(Float)
    shap_is_major_sale_period = Column(Float)
    shap_competitor_scarcity_count = Column(Float)
    shap_volume_weight = Column(Float)
    shap_D_months = Column(Float)
    shap_k = Column(Float)
    shap_import_lambda = Column(Float)
    shap_missing_release_date = Column(Float)
    shap_base_expected_price = Column(Float)
    
    delta_shap_compute_potential = Column(Float)
    delta_shap_delta_p_7d = Column(Float)
    delta_shap_delta_p_14d = Column(Float)
    delta_shap_delta_p_1d = Column(Float)
    delta_shap_vol_30d = Column(Float)
    delta_shap_official_egp_usd = Column(Float)
    delta_shap_cpi_inflation = Column(Float)
    delta_shap_is_major_sale_period = Column(Float)
    delta_shap_competitor_scarcity_count = Column(Float)
    delta_shap_volume_weight = Column(Float)
    delta_shap_D_months = Column(Float)
    delta_shap_k = Column(Float)
    delta_shap_import_lambda = Column(Float)
    delta_shap_missing_release_date = Column(Float)

    price_history = relationship("PriceHistory", back_populates="ml_forecast_shap")

class DailyRecommendation(Base):
    __tablename__ = 'daily_recommendations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    price_history_id = Column(Integer, ForeignKey('price_history.id'))
    
    intelligent_score = Column(Float)
    routing_path = Column(String) # Path 1 to Path 7
    status = Column(String) # 'Approved', 'Rejected', 'Human Review'
    justification = Column(String, nullable=True)
    emailed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)

    price_history = relationship("PriceHistory")

class Subscriber(Base):
    __tablename__ = 'subscribers'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    category = Column(String, default='laptop')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
