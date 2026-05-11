from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import datetime

class WebScrapperOutput(BaseModel):
    scrape_timestamp: datetime
    retailer_id: str
    raw_title: str
    raw_current_price: float
    raw_original_price: Optional[float] = None
    product_url: HttpUrl

class RawProduct(BaseModel):
    scrape_timestamp: datetime
    retailer_id: str
    raw_title: str
    raw_current_price: float
    raw_original_price: Optional[float] = None
    product_url: str

class IngestionRequest(BaseModel):
    batch_id: str
    category: str
    target_count: int
    data: list[RawProduct]

class ETLRequest(BaseModel):
    batch_id: str

class ETLOutput(WebScrapperOutput):
    category: Optional[str] = None
    sub_category: Optional[str] = None
    brand: Optional[str] = None
    cpu: Optional[str] = None
    ram_gb: Optional[float] = None
    storage_gb: Optional[float] = None
    gpu: Optional[str] = None
    is_gaming: Optional[bool] = None
    global_release_date_str: Optional[str] = None

class VolatilityOutput(ETLOutput):
    delta_p_1d: float
    delta_p_7d: float
    delta_p_14d: float
    vol_30d: float
    stability_score: float

class XAIForecastOutput(BaseModel):
    scrape_timestamp: datetime
    product_id: str
    raw_title: str
    category: str
    
    official_egp_usd: float
    cpi_inflation: float
    import_lambda: float
    multiplier: float
    
    is_major_sale_period: int
    sale_event_label: Optional[str] = None
    D_months: float
    k: float
    missing_release_date: int
    global_release_date_str: Optional[str] = None
    
    competitor_scarcity_count: int
    volume_weight: float
    compute_potential: float
    
    delta_p_1d: float
    vol_30d: float
    delta_p_7d: float
    delta_p_14d: float
    
    stability_score: float
    predicted_stability_score: float
    price_t_plus_14: float
    
    shap_compute_potential: float
    shap_delta_p_7d: float
    shap_delta_p_14d: float
    shap_delta_p_1d: float
    shap_vol_30d: float
    shap_official_egp_usd: float
    shap_cpi_inflation: float
    shap_is_major_sale_period: float
    shap_competitor_scarcity_count: float
    shap_volume_weight: float
    shap_D_months: float
    shap_k: float
    shap_import_lambda: float
    shap_missing_release_date: float
    shap_base_expected_price: float
    
    delta_shap_compute_potential: float
    delta_shap_delta_p_7d: float
    delta_shap_delta_p_14d: float
    delta_shap_delta_p_1d: float
    delta_shap_vol_30d: float
    delta_shap_official_egp_usd: float
    delta_shap_cpi_inflation: float
    delta_shap_is_major_sale_period: float
    delta_shap_competitor_scarcity_count: float
    delta_shap_volume_weight: float
    delta_shap_D_months: float
    delta_shap_k: float
    delta_shap_import_lambda: float
    delta_shap_missing_release_date: float
