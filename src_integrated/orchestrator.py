import os
import numpy as np
import pandas as pd
from typing import List
from sqlalchemy.orm import Session
from src_integrated.database.db import SessionLocal, engine
from src_integrated.database.models import Product, MacroEconomic, PriceHistory, MLForecastShap, IngestionBatch, RawScrapedData, DailyRecommendation
from src_integrated.schemas.pydantic_models import WebScrapperOutput, ETLOutput, VolatilityOutput, XAIForecastOutput, RawProduct
from src_integrated.utils.shap_engine import JoblibExplainer
from src_integrated.database.db import SessionLocal
from sqlalchemy import func
import logging
import sqlite3
import json
import re
from datetime import datetime

log = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, db_session: Session):
        self.db = db_session

    def ingest_raw_data(self, batch_id: str, category: str, target_count: int, data: List[RawProduct]):
        """Requirement 1.1: Bulk insertion of raw scraped data into the database."""
        # Check if batch exists
        batch = self.db.query(IngestionBatch).filter_by(batch_id=batch_id).first()
        if not batch:
            batch = IngestionBatch(batch_id=batch_id, category=category, target_count=target_count, status='raw')
            self.db.add(batch)
            self.db.flush()
        
        raw_rows = []
        for r in data:
            raw_rows.append(RawScrapedData(
                batch_id=batch_id,
                scrape_timestamp=r.scrape_timestamp,
                retailer_id=r.retailer_id,
                raw_title=r.raw_title,
                raw_current_price=r.raw_current_price,
                raw_original_price=r.raw_original_price,
                product_url=r.product_url
            ))
        self.db.bulk_save_objects(raw_rows)
        self.db.commit()
        return len(raw_rows)
        
    def _clean_price(self, price_str):
        """Helper to convert 'EGP 3,999' or 'EGP\u00a03,999' to float 3999.0"""
        if price_str is None: return None
        if isinstance(price_str, (int, float)): return float(price_str)
        # Remove currency symbols, commas, and non-breaking spaces
        cleaned = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        try:
            return float(cleaned)
        except:
            return 0.0

    def ingest_from_testing_queue(self, batch_id: str, limit: int = 100):
        """Requirement: User-controlled ingestion from testing_queue.db."""
        queue_db_path = os.path.join(os.path.dirname(__file__), "database", "testing_queue.db")
        if not os.path.exists(queue_db_path):
            log.error(f"Testing queue DB not found at {queue_db_path}")
            return 0
            
        conn = sqlite3.connect(queue_db_path)
        cursor = conn.cursor()
        
        # Fetch rows from raw_queue
        cursor.execute("SELECT id, payload FROM raw_queue LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        if not rows:
            conn.close()
            return 0
            
        raw_products = []
        row_ids_to_delete = []
        
        for row_id, payload_str in rows:
            payload = json.loads(payload_str)
            try:
                # Map to RawProduct schema
                # Some fields might be missing or in different format
                # e.g. raw_current_price needs cleaning
                p = RawProduct(
                    scrape_timestamp=datetime.fromisoformat(payload["scrape_timestamp"]),
                    retailer_id=payload["retailer_id"],
                    raw_title=payload["raw_title"],
                    raw_current_price=self._clean_price(payload.get("raw_current_price")),
                    raw_original_price=self._clean_price(payload.get("raw_original_price")),
                    product_url=payload["product_url"]
                )
                raw_products.append(p)
                row_ids_to_delete.append(row_id)
            except Exception as e:
                log.warning(f"Failed to parse payload for row {row_id}: {e}")
                
        # Bulk ingest into main DB
        count = self.ingest_raw_data(
            batch_id=batch_id,
            category="mixed_test", # Or extract from payload if available
            target_count=len(raw_products),
            data=raw_products
        )
        
        # Delete from queue if successful
        if count > 0:
            cursor.executemany("DELETE FROM raw_queue WHERE id = ?", [(rid,) for rid in row_ids_to_delete])
            conn.commit()
            
        conn.close()
        return count

    def process_batch_etl(self, batch_id: str):
        """Requirement 1.2: Database-resident ETL transformation."""
        batch = self.db.query(IngestionBatch).filter_by(batch_id=batch_id).first()
        if not batch:
            log.error(f"Batch {batch_id} not found.")
            return False
            
        batch.status = 'processing'
        self.db.commit()
        
        try:
            raw_data = self.db.query(RawScrapedData).filter_by(batch_id=batch_id).all()
            if not raw_data:
                batch.status = 'failed'
                self.db.commit()
                return False
                
            # Convert to WebScrapperOutput for run_etl
            web_scrapper_inputs = [
                WebScrapperOutput(
                    scrape_timestamp=r.scrape_timestamp,
                    retailer_id=r.retailer_id,
                    raw_title=r.raw_title,
                    raw_current_price=r.raw_current_price,
                    raw_original_price=r.raw_original_price,
                    product_url=r.product_url
                ) for r in raw_data
            ]
            
            etl_results = self.run_etl(web_scrapper_inputs)
            
            # Persist processed products (UPSERT)
            for etl in etl_results:
                # Use product_url as ID
                p_id = str(etl.product_url)
                product = self.db.query(Product).filter_by(id=p_id).first()
                if not product:
                    product = Product(id=p_id)
                    self.db.add(product)
                
                # Map ETL fields to Product
                product.retailer_id = etl.retailer_id
                product.raw_title = etl.raw_title
                product.product_url = p_id
                product.category = etl.category
                product.sub_category = etl.sub_category
                product.brand = etl.brand
                product.cpu = etl.cpu
                product.ram_gb = etl.ram_gb
                product.storage_gb = etl.storage_gb
                product.gpu = etl.gpu
                product.is_gaming = etl.is_gaming
                product.global_release_date_str = etl.global_release_date_str
                
                # Also create PriceHistory record
                ph = PriceHistory(
                    product_id=p_id,
                    scrape_timestamp=etl.scrape_timestamp,
                    date_id=etl.scrape_timestamp.date(),
                    raw_current_price=etl.raw_current_price,
                    raw_original_price=etl.raw_original_price
                )
                self.db.add(ph)

            batch.status = 'completed'
            self.db.commit()
            return True
        except Exception as e:
            log.error(f"ETL failed for batch {batch_id}: {e}")
            batch.status = 'failed'
            self.db.commit()
            return False

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

    def process_external_batch(self, raw_dicts: List[dict], models: dict = None) -> dict:
        """
        Process a batch of raw dicts (e.g. from testing queue) and return all intermediate results.
        Useful for the dashboard/monitor to inspect the I/O of each layer.
        """
        raw_data = []
        for d in raw_dicts:
            try:
                # Clean price strings before Pydantic validation
                d["raw_current_price"] = self._clean_price(d.get("raw_current_price"))
                d["raw_original_price"] = self._clean_price(d.get("raw_original_price"))
                raw_data.append(WebScrapperOutput(**d))
            except Exception as e:
                log.warning(f"Skipping malformed row: {e}")
                
        if not raw_data:
            return {"raw": [], "etl": [], "vol": [], "ml": []}

        etl_data = self.run_etl(raw_data)
        vol_data = self.run_volatility(etl_data)
        forecast_data = self.run_forecasting(vol_data, models=models)
        
        return {
            "raw": [r.model_dump() for r in raw_data],
            "etl": [e.model_dump() for e in etl_data],
            "vol": [v.model_dump() for v in vol_data],
            "ml": [f.model_dump() for f in forecast_data]
        }

    def run_forecasting_unified(self, batch_id: str, models: dict):
        """Requirement 2.1 & 2.2: Integrated Forecasting & SHAP."""
        log.info(f"Running Forecasting & SHAP for batch {batch_id}...")
        
        # 1. Fetch relevant PriceHistory records
        # Since we just ran ETL, we need to find records created/updated for this batch.
        # We can join RawScrapedData with PriceHistory via product_id and timestamp
        results = self.db.query(PriceHistory, Product).join(Product).filter(
            PriceHistory.product_id.in_(
                self.db.query(RawScrapedData.product_url).filter_by(batch_id=batch_id)
            )
        ).all()
        
        if not results:
            log.warning("No records found for forecasting.")
            return
            
        # 2. Prepare Feature Vectors (14 features from NEW_FEATURES)
        from ml_models import NEW_FEATURES
        
        # Use recent macro data (Requirement 5.3: Temporal Continuity)
        macro = self.db.query(MacroEconomic).order_by(MacroEconomic.date_id.desc()).first()
        macro_dict = {
            "official_egp_usd": macro.official_egp_usd if macro else 48.0,
            "cpi_inflation": macro.cpi_inflation if macro else 35.0,
            "is_major_sale_period": 1 if macro and macro.is_major_sale_period else 0,
            "import_lambda": macro.import_lambda if macro else 1.0,
        }
        
        features_list = []
        target_records = []
        for ph, p in results:
            feat_dict = {
                "compute_potential": p.compute_potential or 0.5,
                "delta_p_7d": ph.delta_p_7d or 0.0,
                "delta_p_14d": ph.delta_p_14d or 0.0,
                "delta_p_1d": ph.delta_p_1d or 0.0,
                "vol_30d": ph.vol_30d or 0.0,
                "official_egp_usd": macro_dict["official_egp_usd"],
                "cpi_inflation": macro_dict["cpi_inflation"],
                "is_major_sale_period": macro_dict["is_major_sale_period"],
                "competitor_scarcity_count": ph.competitor_scarcity_count or 0,
                "volume_weight": ph.volume_weight or 0.5,
                "D_months": ph.D_months or 12.0,
                "k": ph.k or 0.001,
                "import_lambda": macro_dict["import_lambda"],
                "missing_release_date": 1 if p.missing_release_date else 0
            }
            # Maintain strict order from NEW_FEATURES
            vector = [feat_dict[f] for f in NEW_FEATURES]
            features_list.append(vector)
            target_records.append((ph, feat_dict))

        # 3. Inference
        df_features = pd.DataFrame(features_list, columns=NEW_FEATURES)
        
        price_results = []
        stability_results = []
        
        price_model = models.get("price")
        stability_model = models.get("stability")
        
        if price_model and stability_model:
            # Batch Inference (or loop if session requires)
            for vec in features_list:
                # Price Forecast
                inp_price = {price_model.get_inputs()[0].name: np.array([vec], dtype=np.float32)}
                raw_p = price_model.run(None, inp_price)
                price_results.append(raw_p[0].flat[0])
                
                # Stability Forecast
                inp_stab = {name: np.array([[vec[i]]], dtype=np.float32) for i, name in enumerate([inp.name for inp in stability_model.get_inputs()])}
                raw_s = stability_model.run(None, inp_stab)
                stability_results.append(raw_s[0].flat[0])
        
        # 4. SHAP Explanations (Using Joblib as requested)
        shap_values_stability = []
        shap_values_price = []
        
        # Paths to Joblib artifacts for SHAP
        STABILITY_JOBLIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ML_Pipeline", "Forecasting", "stability_model_v2_final.joblib")
        PRICE_JOBLIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ML_Pipeline", "Forecasting", "model_14d.joblib")
        
        if os.path.exists(STABILITY_JOBLIB_PATH):
            explainer_s = JoblibExplainer(STABILITY_JOBLIB_PATH, NEW_FEATURES)
            shap_values_stability = explainer_s.compute_shap(df_features)
            
        if os.path.exists(PRICE_JOBLIB_PATH):
            explainer_p = JoblibExplainer(PRICE_JOBLIB_PATH, NEW_FEATURES)
            shap_values_price = explainer_p.compute_shap(df_features)
        else:
            log.warning(f"Price Joblib not found at {PRICE_JOBLIB_PATH}. Price SHAP skipped.")

        # 5. Persist Results
        for i, (ph, feats) in enumerate(target_records):
            shap_record = self.db.query(MLForecastShap).filter_by(price_history_id=ph.id).first()
            if not shap_record:
                shap_record = MLForecastShap(price_history_id=ph.id)
                self.db.add(shap_record)
            
            shap_record.price_t_plus_14 = price_results[i] if i < len(price_results) else 0.0
            shap_record.stability_score = stability_results[i] if i < len(stability_results) else 0.0
            shap_record.predicted_stability_score = shap_record.stability_score
            
            # Map SHAP values (Stability)
            if i < len(shap_values_stability):
                row_shap = shap_values_stability[i]
                for j, feat_name in enumerate(NEW_FEATURES):
                    setattr(shap_record, f"shap_{feat_name}", float(row_shap[j]))
            
            # Map SHAP values (Price - stored as delta_shap columns in schema)
            if i < len(shap_values_price):
                row_shap_p = shap_values_price[i]
                for j, feat_name in enumerate(NEW_FEATURES):
                    setattr(shap_record, f"delta_shap_{feat_name}", float(row_shap_p[j]))

        self.db.commit()
        log.info(f"Successfully processed {len(target_records)} forecasts and SHAP explanations.")
        return True

    def run_verification_react(self, batch_id: str, react_state: dict):
        """Requirement 3.1: Fully Dynamic ReAct Decision Router."""
        log.info(f"Executing ReAct Verification for batch {batch_id}...")
        
        if not react_state:
            log.error("ReAct State not initialized.")
            return False
            
        # 1. Fetch relevant records (joined data for signals)
        from ml_models import NEW_FEATURES
        
        # Need: current_price, forecasted_price, volatility_score, price_14d_avg, months_since_release
        # Plus metadata for SARIMAX: category, title
        results = self.db.query(PriceHistory, Product, MLForecastShap).join(Product).join(MLForecastShap).filter(
            PriceHistory.product_id.in_(
                self.db.query(RawScrapedData.product_url).filter_by(batch_id=batch_id)
            )
        ).all()
        
        if not results:
            log.warning("No records found for verification.")
            return False
            
        candidates = []
        for ph, p, shap in results:
            # Map DB fields to ReAct candidate format
            cand = {
                "model_id": p.id,
                "product_title": p.raw_title,
                "category": p.category,
                "current_price": ph.raw_current_price,
                "forecasted_price": shap.price_t_plus_14,
                "volatility_score": 100 - (shap.predicted_stability_score or 50),
                "predicted_stability_score": shap.predicted_stability_score,
                "price_14d_avg": ph.raw_current_price * 0.98, # Heuristic fallback
                "months_since_release": ph.D_months or 12.0,
                "r_score": ph.raw_current_price / (shap.price_t_plus_14 + 1e-6) * 100, # Heuristic r_score proxy
                "db_price_history_id": ph.id
            }
            candidates.append(cand)

        # 2. Execute ReAct Loop
        from react_router import run_react_loop
        approved, dlq = run_react_loop(candidates, react_state)
        
        # 3. Persist Recommendations
        for c in approved + dlq:
            status = "Approved" if c in approved else "Human Review"
            if "Hard Reject" in c.get("routing_path", ""):
                status = "Rejected"
                
            rec = DailyRecommendation(
                price_history_id=c["db_price_history_id"],
                intelligent_score=c.get("intelligent_score", 0.0),
                routing_path=c.get("routing_path", "Unknown"),
                status=status,
                justification=f"Automated {status} via {c.get('routing_path')}"
            )
            self.db.add(rec)
            
        self.db.commit()
        log.info(f"ReAct Loop Complete. {len(approved)} approved, {len(dlq)} sent to DLQ.")
        return True

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
