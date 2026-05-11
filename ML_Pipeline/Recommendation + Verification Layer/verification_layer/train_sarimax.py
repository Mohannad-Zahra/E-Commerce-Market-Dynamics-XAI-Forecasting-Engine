"""
train_sarimax.py
================
Trains SARIMAX models aggregated by Sub-Category (e.g. 'Laptop_Apple', 'Phone_Samsung').
This perfectly handles edge cases where brands make both laptops and phones,
and uses virtually zero RAM compared to per-product training.

Exports the trained models to joblib for live inference in the ReAct router.
"""

import os
import sys
import time
import warnings
import numpy as np
import pandas as pd
import joblib
from datetime import datetime
from statsmodels.tsa.statespace.sarimax import SARIMAX

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_DIR, "..", "ECom_Forecast_XAI_data.csv")
MODEL_DIR = os.path.join(_DIR, "models")
OUTPUT_MODELS = os.path.join(MODEL_DIR, "sarimax_category_models.joblib")
OUTPUT_META = os.path.join(MODEL_DIR, "sarimax_metadata.joblib")

SARIMAX_ORDER = (1, 1, 1)
SARIMAX_SEASONAL_ORDER = (1, 1, 1, 7)
MIN_OBSERVATIONS = 30

def _hr(): print("=" * 80)
def _section(title): print(f"\n--- {title} ---")
def _ok(msg): print(f"  ✅ {msg}")
def _info(msg): print(f"  ℹ️  {msg}")

def train_category_sarimax():
    _hr()
    print("  SARIMAX SUB-CATEGORY LEVEL TRAINING PIPELINE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _hr()

    # 1. Load Data
    _section("STEP 1: Loading Dataset")
    t0 = time.time()
    df = pd.read_csv(CSV_PATH)
    _ok(f"Loaded {len(df):,} rows in {time.time() - t0:.1f}s")

    # 2. Preprocessing & Sub-Category Extraction
    _section("STEP 2: Preprocessing and Aggregating by Sub-Category")
    df["current_price"] = df["price_t_plus_14"] / (1 + df["delta_p_14d"].fillna(0))
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"])
    
    # Extract Brand from raw_title (first word) and handle the edge case
    df["brand"] = df["raw_title"].apply(lambda x: str(x).split()[0].capitalize() if pd.notna(x) else "Unknown")
    df["sub_category"] = df["category"] + "_" + df["brand"]
    
    # Aggregate by sub_category and date
    df_agg = df.groupby(["sub_category", "scrape_timestamp"])["current_price"].mean().reset_index()
    df_agg = df_agg.sort_values(["sub_category", "scrape_timestamp"])
    
    sub_categories = df_agg["sub_category"].unique()
    _ok(f"Aggregated data into {len(sub_categories)} sub-categories.")
    print(f"  ℹ️  Sub-categories detected: {sub_categories.tolist()[:10]}...")

    # 3. Training
    _section("STEP 3: Training Models")
    trained_models = {}
    training_metadata = {
        "trained_at": datetime.now().isoformat(),
        "sub_categories": {}
    }

    for subcat in sub_categories:
        t_start = time.time()
        print(f"  Training for {subcat}...", end=" ", flush=True)
        
        subcat_data = df_agg[df_agg["sub_category"] == subcat]
        series = pd.Series(subcat_data["current_price"].values, index=subcat_data["scrape_timestamp"])
        
        # Ensure daily frequency
        series = series.resample("D").mean().ffill()
        
        if len(series) < MIN_OBSERVATIONS:
            print(f"SKIPPED (low data: {len(series)} obs)")
            continue

        try:
            model = SARIMAX(
                series,
                order=SARIMAX_ORDER,
                seasonal_order=SARIMAX_SEASONAL_ORDER,
                enforce_stationarity=False,
                enforce_invertibility=False,
            )
            fitted = model.fit(disp=False, maxiter=50)
            
            trained_models[subcat] = fitted
            
            elapsed = time.time() - t_start
            print(f"OK ({elapsed:.1f}s)")
            
            training_metadata["sub_categories"][subcat] = {
                "status": "success",
                "aic": float(fitted.aic),
                "n_obs": len(series)
            }
        except Exception as e:
            print(f"FAILED: {e}")
            training_metadata["sub_categories"][subcat] = {"status": "failed", "error": str(e)}

    # 4. Save
    _section("STEP 4: Saving Results")
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(trained_models, OUTPUT_MODELS)
    joblib.dump(training_metadata, OUTPUT_META)
    _ok(f"Models and metadata saved to {MODEL_DIR}")
    _hr()

if __name__ == "__main__":
    train_category_sarimax()
