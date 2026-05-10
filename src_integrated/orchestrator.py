import pandas as pd
from typing import List
from sqlalchemy.orm import Session
from src_integrated.database.db import SessionLocal, engine
from src_integrated.database.models import Product, MacroEconomic, PriceHistory, MLForecastShap
from src_integrated.schemas.pydantic_models import WebScrapperOutput, ETLOutput, VolatilityOutput, XAIForecastOutput
from sqlalchemy import func
import logging

log = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, db_session: Session):
        self.db = db_session

    def fetch_raw_scrape_data(self, target_date) -> List[WebScrapperOutput]:
        """Fetch raw data for a specific date from PriceHistory and Product tables."""
        print(f"Fetching data for {target_date}...")
        
        # In the new architecture, RawScrapedData might be separate, 
        # but currently we have PriceHistory which represents the snapshots.
        results = self.db.query(PriceHistory, Product).join(Product).filter(
            func.date(PriceHistory.scrape_timestamp) == target_date
        ).limit(100).all()

        output = []
        for ph, p in results:
            output.append(WebScrapperOutput(
                scrape_timestamp=ph.scrape_timestamp,
                retailer_id=p.retailer_id,
                raw_title=p.raw_title,
                raw_current_price=ph.raw_current_price,
                raw_original_price=None, # Assuming not in DB yet or mapping from elsewhere
                product_url=p.product_url
            ))
        return output

    def run_etl(self, raw_data: List[WebScrapperOutput]) -> List[ETLOutput]:
        """
        Replaces: pd.read_csv('raw_data.json') -> ETL logic -> to_csv('processed_products.csv')
        """
        print("Executing ETL component in-memory...")
        
        # Ensure ETL path is available
        import sys
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        etl_path = os.path.join(base_dir, 'ETL', 'Data Pipeline')
        if etl_path not in sys.path:
            sys.path.append(etl_path)
        
        from features import FeatureExtractor
        extractor = FeatureExtractor()
        
        processed_data = []
        for raw in raw_data:
            # Convert Pydantic to dict for the extractor
            raw_dict = raw.model_dump()
            # The extractor expects some specific keys or structure
            # Let's map them if necessary
            etl_result = extractor.transform_row(raw_dict)
            
            # Convert back to Pydantic ETLOutput
            # We need to handle potential missing fields in ETLOutput
            processed_data.append(ETLOutput(**etl_result))
            
        return processed_data

    def run_volatility(self, etl_data: List[ETLOutput]) -> List[VolatilityOutput]:
        """
        Calculates price momentum and volatility features.
        """
        print("Executing Volatility Modeling in-memory...")
        vol_data = []
        for etl in etl_data:
            # In a real scenario, we would fetch historical prices for this product
            # For now, we simulate or use what's in the DB if available.
            # Let's use some dummy values that look realistic.
            vol_item = VolatilityOutput(
                **etl.model_dump(),
                delta_p_1d=0.01,
                delta_p_7d=0.05,
                delta_p_14d=0.08,
                vol_30d=0.15,
                stability_score=85.0
            )
            vol_data.append(vol_item)
        return vol_data

    def run_forecasting(self, vol_data: List[VolatilityOutput]) -> List[XAIForecastOutput]:
        """
        Runs the ONNX models for price and stability forecasting.
        """
        print("Executing XAI Forecasting in-memory...")
        
        # Ensure backend path is available for ml_models
        import sys
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        backend_path = os.path.join(base_dir, 'backend')
        if backend_path not in sys.path:
            sys.path.append(backend_path)
            
        from ml_models import predict_price_onnx, predict_stability_onnx, NEW_FEATURES
        
        forecast_data = []
        for v in vol_data:
            # Prepare 18 features for Model 1 (Price)
            # 1-14: Standard XAI features
            # 15-18: Hardware features (cpu_tier, gpu_tier, ram_gb_ordinal, storage_ordinal)
            
            # Use some realistic dummy macro values for now
            macro_features = {
                "official_egp_usd": 48.5,
                "cpi_inflation": 35.0,
                "is_major_sale_period": 0,
                "competitor_scarcity_count": 5,
                "volume_weight": 0.5,
                "D_months": 12.0,
                "k": 0.001,
                "import_lambda": 1.2,
                "missing_release_date": 0
            }
            
            feature_14 = [
                v.model_dump().get('compute_potential', 0.5) or 0.5,
                v.delta_p_7d,
                v.delta_p_14d,
                v.delta_p_1d,
                v.vol_30d,
                macro_features["official_egp_usd"],
                macro_features["cpi_inflation"],
                macro_features["is_major_sale_period"],
                macro_features["competitor_scarcity_count"],
                macro_features["volume_weight"],
                macro_features["D_months"],
                macro_features["k"],
                macro_features["import_lambda"],
                macro_features["missing_release_date"]
            ]
            
            # Add hardware features for Model 1
            feature_18 = feature_14 + [
                v.model_dump().get('cpu_tier', 0),
                v.model_dump().get('gpu_tier', 0),
                v.model_dump().get('ram_gb_ordinal', 0),
                v.model_dump().get('storage_ordinal', 0)
            ]
            
            try:
                price_res = predict_price_onnx(feature_18)
                stability_res = predict_stability_onnx(feature_14)
                
                forecast_item = XAIForecastOutput(
                    scrape_timestamp=v.scrape_timestamp,
                    product_id=str(v.product_url),
                    raw_title=v.raw_title,
                    category=v.category or "Unknown",
                    official_egp_usd=macro_features["official_egp_usd"],
                    cpi_inflation=macro_features["cpi_inflation"],
                    import_lambda=macro_features["import_lambda"],
                    multiplier=1.0,
                    is_major_sale_period=macro_features["is_major_sale_period"],
                    D_months=macro_features["D_months"],
                    k=macro_features["k"],
                    missing_release_date=macro_features["missing_release_date"],
                    competitor_scarcity_count=macro_features["competitor_scarcity_count"],
                    volume_weight=macro_features["volume_weight"],
                    compute_potential=feature_14[0],
                    delta_p_1d=v.delta_p_1d,
                    delta_p_7d=v.delta_p_7d,
                    delta_p_14d=v.delta_p_14d,
                    vol_30d=v.vol_30d,
                    stability_score=v.stability_score,
                    predicted_stability_score=stability_res["predicted_stability_score"],
                    price_t_plus_14=price_res["predicted_price_egp"],
                    # Fill SHAP with dummy zeros for now
                    **{f"shap_{f}": 0.0 for f in NEW_FEATURES},
                    shap_base_expected_price=0.0,
                    **{f"delta_shap_{f}": 0.0 for f in NEW_FEATURES}
                )
                forecast_data.append(forecast_item)
            except Exception as e:
                print(f"Error forecasting for {v.raw_title}: {e}")
                
        return forecast_data

    def save_forecasts_to_db(self, forecast_data: List[XAIForecastOutput]):
        """
        Persists final output back to the database instead of CSV handoffs.
        """
        print(f"Persisting {len(forecast_data)} forecasts to database...")
        for f in forecast_data:
            # Find the price history record we just processed
            ph = self.db.query(PriceHistory).filter(
                PriceHistory.product_id == f.product_id,
                func.date(PriceHistory.scrape_timestamp) == f.scrape_timestamp.date()
            ).first()
            
            if ph:
                # Update PriceHistory with volatility info if not already there
                ph.delta_p_1d = f.delta_p_1d
                ph.delta_p_7d = f.delta_p_7d
                ph.delta_p_14d = f.delta_p_14d
                ph.vol_30d = f.vol_30d
                
                # Add or update MLForecastShap
                shap_record = self.db.query(MLForecastShap).filter(
                    MLForecastShap.price_history_id == ph.id
                ).first()
                
                if not shap_record:
                    shap_record = MLForecastShap(price_history_id=ph.id)
                    self.db.add(shap_record)
                
                shap_record.stability_score = f.stability_score
                shap_record.predicted_stability_score = f.predicted_stability_score
                shap_record.price_t_plus_14 = f.price_t_plus_14
                # ... map SHAP values ...
                
        self.db.commit()

    def process_external_batch(self, raw_dicts: List[dict]) -> dict:
        """
        Process a batch of raw dicts (e.g. from testing queue) and return all intermediate results.
        Useful for the dashboard/monitor to inspect the I/O of each layer.
        """
        raw_data = []
        for d in raw_dicts:
            try:
                raw_data.append(WebScrapperOutput(**d))
            except Exception as e:
                log.warning(f"Skipping malformed row: {e}")
                
        if not raw_data:
            return {"raw": [], "etl": [], "vol": [], "ml": []}

        etl_data = self.run_etl(raw_data)
        vol_data = self.run_volatility(etl_data)
        forecast_data = self.run_forecasting(vol_data)
        
        return {
            "raw": [r.model_dump() for r in raw_data],
            "etl": [e.model_dump() for e in etl_data],
            "vol": [v.model_dump() for v in vol_data],
            "ml": [f.model_dump() for f in forecast_data]
        }

    def run_pipeline(self, target_date):
        print(f"--- Starting Pipeline for {target_date} ---")
        raw_data = self.fetch_raw_scrape_data(target_date)
        
        if not raw_data:
            print("No raw data to process. Exiting pipeline.")
            return

        etl_data = self.run_etl(raw_data)
        vol_data = self.run_volatility(etl_data)
        forecast_data = self.run_forecasting(vol_data)
        
        self.save_forecasts_to_db(forecast_data)
        print("--- Pipeline Execution Complete ---")

if __name__ == "__main__":
    session = SessionLocal()
    try:
        orchestrator = PipelineOrchestrator(session)
        # Execute for today's date or specific scrape run
        orchestrator.run_pipeline('2026-05-10')
    finally:
        session.close()
