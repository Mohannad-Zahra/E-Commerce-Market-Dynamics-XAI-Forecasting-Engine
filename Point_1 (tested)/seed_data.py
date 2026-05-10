"""
seed_data.py — Historical Data Seeder
======================================
Imports historical data from data/ECom_Forecast_XAI_data.csv
into the unified Wise Purchaser database.

Usage:
    python Point_1/seed_data.py
"""

import os
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from Point_1.db.engine import SessionLocal, engine, Base
from Point_1.db.models import ProcessedProduct, MLForecastShap, Batch

CSV_PATH = "data/ECom_Forecast_XAI_data.csv"
BATCH_SIZE = 5000

def seed():
    print(f"🚀 Starting data migration from {CSV_PATH}...")
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: {CSV_PATH} not found.")
        return

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    legacy_batch_id = "batch_historical_import"
    
    if not db.query(Batch).filter(Batch.batch_id == legacy_batch_id).first():
        db.add(Batch(batch_id=legacy_batch_id, category="mixed", status="COMPLETED"))
        db.commit()
    
    total_rows = 0
    try:
        reader = pd.read_csv(CSV_PATH, chunksize=BATCH_SIZE)
        for i, chunk in enumerate(reader):
            print(f"📦 Processing chunk {i+1}...")
            processed_records = []
            shap_records = []
            for _, row in chunk.iterrows():
                ts = pd.to_datetime(row.get("scrape_timestamp")) if pd.notnull(row.get("scrape_timestamp")) else datetime.now()
                processed_records.append(ProcessedProduct(
                    batch_id=legacy_batch_id, scrape_timestamp=ts,
                    product_url=str(row.get("product_id", "unknown")),
                    retailer_id="historical", raw_title=str(row.get("raw_title", "Unknown")),
                    raw_current_price=float(row.get("raw_current_price", 0)) if "raw_current_price" in row else 0,
                    category=str(row.get("category", "Phone")),
                    compute_potential=float(row.get("compute_potential", 0)),
                    delta_p_1d=float(row.get("delta_p_1d", 0)),
                    delta_p_7d=float(row.get("delta_p_7d", 0)),
                    delta_p_14d=float(row.get("delta_p_14d", 0)),
                    vol_30d=float(row.get("vol_30d", 0)),
                    official_egp_usd=float(row.get("official_egp_usd", 0)),
                    cpi_inflation=float(row.get("cpi_inflation", 0)),
                    import_lambda=float(row.get("import_lambda", 0)),
                    is_major_sale_period=bool(row.get("is_major_sale_period", False)),
                ))
                shap_records.append(MLForecastShap(
                    product_url=str(row.get("product_id", "unknown")),
                    batch_id=legacy_batch_id, scrape_timestamp=ts,
                    stability_score=float(row.get("stability_score", 0)),
                    predicted_stability_score=float(row.get("predicted_stability_score", 0)),
                    price_t_plus_14=float(row.get("price_t_plus_14", 0)),
                    shap_compute_potential=float(row.get("shap_compute_potential", 0)),
                    shap_delta_p_7d=float(row.get("shap_delta_p_7d", 0)),
                    shap_delta_p_14d=float(row.get("shap_delta_p_14d", 0)),
                    shap_delta_p_1d=float(row.get("shap_delta_p_1d", 0)),
                    shap_vol_30d=float(row.get("shap_vol_30d", 0)),
                ))
            db.bulk_save_objects(processed_records)
            db.bulk_save_objects(shap_records)
            db.commit()
            total_rows += len(chunk)
            print(f"✅ Total rows: {total_rows}")
        print(f"🎉 SUCCESS! Imported {total_rows} records.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
