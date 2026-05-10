import pandas as pd
import numpy as np
import logging
from react_router import run_react_loop, SHAP_COLS
from offline_state_builder import load_offline_state
import sys
import os

# Add legacy recommendation system to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Recommendation system"))
from ranking_engine import calculate_r_score

def run_test():
    csv_path = os.path.join(os.path.dirname(__file__), "..", "ECom_Forecast_XAI_data.csv")
    print(f"Loading 1000 rows from {csv_path}...")
    df = pd.read_csv(csv_path, nrows=1000)
    
    # Ensure columns exist for Layer 1 R_score calculation
    # Simulating current_price and price_14d_avg if not present in the XAI CSV
    if "current_price" not in df.columns:
        df["current_price"] = df["price_t_plus_14"] * np.random.uniform(0.9, 1.1, len(df))
    if "price_14d_avg" not in df.columns:
        df["price_14d_avg"] = df["current_price"] * np.random.uniform(0.95, 1.05, len(df))
        
    df["forecasted_price"] = df["price_t_plus_14"]
    df["volatility_score"] = 100 - df["predicted_stability_score"]
    df["months_since_release"] = df["D_months"]
    
    # Layer 1: Vectorized Gating Function
    print("Calculating R_scores for candidates...")
    df["r_score"] = calculate_r_score(df)
    
    # Slice Top 20 Candidates
    top_20 = df.sort_values("r_score", ascending=False).head(20)
    print(f"Isolated Top {len(top_20)} candidates for ReAct router.")
    
    # Formatting for Layer 2
    candidates = []
    for _, row in top_20.iterrows():
        shap_drivers = {col: row.get(col, 0.0) for col in SHAP_COLS}
        c = {
            "model_id": str(row["product_id"]),
            "current_price": float(row["current_price"]),
            "price_14d_avg": float(row["price_14d_avg"]),
            "forecasted_price": float(row["forecasted_price"]),
            "volatility_score": float(row["volatility_score"]),
            "months_since_release": float(row["months_since_release"]),
            "r_score": float(row["r_score"]),
            "shap_drivers": shap_drivers
        }
        candidates.append(c)
        
    # Load Real Offline State
    app_state = load_offline_state()
    
    # Execute Layer 2
    print("\nStarting ReAct Router Loop...")
    dispatched, dlq = run_react_loop(candidates, app_state)
    
    print("\n--- TEST COMPLETE ---")
    print(f"Total Dispatched Candidates: {len(dispatched)}")
    for d in dispatched:
        print(f" [Approve] ID: {d['model_id']} | Path: {d.get('routing_path')} | S: {d['r_score']:.2f}")
        
    print(f"\nTotal Dead Letter Queue: {len(dlq)}")
    for d in dlq:
        print(f" [Reject/Review] ID: {d['model_id']} | Path: {d.get('routing_path')} | S: {d['r_score']:.2f}")

if __name__ == "__main__":
    run_test()
