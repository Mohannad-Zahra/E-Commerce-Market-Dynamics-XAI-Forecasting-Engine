"""
migrate_100k.py
===============
Migrates 100,000 RANDOMIZED rows from ECom_Forecast_XAI_data.csv into agentic_react.db.
This seeds the database so the dashboard, drift detection, and retrain threshold all
operate on real persisted data.

USAGE:
    python migrate_100k.py

OUTPUT:
    agentic_react.db → ingested_batches table populated with 100K rows
"""

import os
import sys
import time
import numpy as np
import pandas as pd
import sqlite3
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_DIR, "..", "ECom_Forecast_XAI_data.csv")
DB_PATH = os.path.join(_DIR, "agentic_react.db")

# Import the DB initializer
sys.path.insert(0, _DIR)
from agentic_db import init_agentic_db

TARGET_ROWS = 100_000
BATCH_INSERT_SIZE = 2500  # Insert in chunks to avoid memory issues


def _hr():
    print("=" * 80)

def _section(title):
    print(f"\n{'─' * 80}")
    print(f"  {title}")
    print(f"{'─' * 80}")


def migrate():
    _hr()
    print("  100K ROW MIGRATION: ECom_Forecast_XAI_data.csv -> agentic_react.db")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _hr()

    # ------------------------------------------------------------------
    # Step 1: Load CSV
    # ------------------------------------------------------------------
    _section("STEP 1/4: Loading CSV Dataset")
    print(f"  📂 Source: {CSV_PATH}")
    
    t0 = time.time()
    df = pd.read_csv(CSV_PATH)
    load_time = time.time() - t0
    
    print(f"  ✅ Loaded {len(df):,} rows in {load_time:.1f}s")
    print(f"  ℹ️  Columns: {len(df.columns)}")
    print(f"  ℹ️  Unique products: {df['product_id'].nunique()}")
    print(f"  ℹ️  Memory: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB")

    # ------------------------------------------------------------------
    # Step 2: Randomize and sample
    # ------------------------------------------------------------------
    _section("STEP 2/4: Randomizing & Sampling")
    
    total_available = len(df)
    if total_available >= TARGET_ROWS:
        sampled = df.sample(n=TARGET_ROWS, random_state=42).reset_index(drop=True)
        print(f"  ✅ Randomly sampled {TARGET_ROWS:,} rows from {total_available:,}")
    else:
        # If we have fewer rows than target, repeat with sampling
        repeats = (TARGET_ROWS // total_available) + 1
        sampled = pd.concat([df] * repeats, ignore_index=True).sample(
            n=TARGET_ROWS, random_state=42
        ).reset_index(drop=True)
        print(f"  ✅ Dataset has {total_available:,} rows — repeated and sampled to {TARGET_ROWS:,}")

    # Derive price columns
    sampled["current_price"] = sampled["price_t_plus_14"] / (1 + sampled["delta_p_14d"].fillna(0))
    p_t_7 = sampled["price_t_plus_14"] / (1 + (sampled["delta_p_14d"] - sampled["delta_p_7d"]).fillna(0))
    sampled["price_14d_avg"] = (sampled["current_price"] + p_t_7) / 2
    sampled["forecasted_price"] = sampled["price_t_plus_14"]
    sampled["volatility_score"] = 100 - sampled["predicted_stability_score"]
    sampled["months_since_release"] = sampled["D_months"]
    
    print(f"  ℹ️  Price range: {sampled['current_price'].min():.2f} → {sampled['current_price'].max():.2f}")
    print(f"  ℹ️  Products represented: {sampled['product_id'].nunique()}")
    print(f"  ℹ️  Categories: {sampled['category'].unique().tolist()}")

    # ------------------------------------------------------------------
    # Step 3: Initialize DB & Insert
    # ------------------------------------------------------------------
    _section("STEP 3/4: Inserting into agentic_react.db")
    
    init_agentic_db()
    print(f"  📁 Target: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    t_insert = time.time()
    total_inserted = 0
    n_batches = (len(sampled) + BATCH_INSERT_SIZE - 1) // BATCH_INSERT_SIZE
    
    for batch_idx in range(n_batches):
        start_idx = batch_idx * BATCH_INSERT_SIZE
        end_idx = min(start_idx + BATCH_INSERT_SIZE, len(sampled))
        batch = sampled.iloc[start_idx:end_idx]
        
        rows_to_insert = []
        batch_id = f"migration_{datetime.utcnow().strftime('%Y%m%d')}_{batch_idx:04d}"
        
        for _, row in batch.iterrows():
            rows_to_insert.append((
                str(row["product_id"]),
                str(row.get("raw_title", "")),
                str(row.get("category", "")),
                float(row["current_price"]) if pd.notna(row["current_price"]) else None,
                float(row["forecasted_price"]) if pd.notna(row["forecasted_price"]) else None,
                float(row["price_14d_avg"]) if pd.notna(row["price_14d_avg"]) else None,
                float(row["volatility_score"]) if pd.notna(row["volatility_score"]) else None,
                float(row["months_since_release"]) if pd.notna(row["months_since_release"]) else None,
                None,  # r_score (not computed during migration)
                "migration",  # routing_path
                None,  # intelligent_score
                "{}",  # signals_json
                "{}",  # shap_drivers_json
                batch_id,
            ))
        
        conn.executemany("""
            INSERT INTO ingested_batches
                (product_id, raw_title, category, current_price, forecasted_price,
                 price_14d_avg, volatility_score, months_since_release, r_score,
                 routing_path, intelligent_score, signals_json, shap_drivers_json, batch_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows_to_insert)
        conn.commit()
        
        total_inserted += len(rows_to_insert)
        pct = (total_inserted / TARGET_ROWS) * 100
        bar_len = 30
        filled = int(bar_len * total_inserted / TARGET_ROWS)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"  [{bar}] {pct:5.1f}% ({total_inserted:,}/{TARGET_ROWS:,}) | Batch {batch_idx+1}/{n_batches}")
    
    insert_time = time.time() - t_insert
    conn.close()

    # ------------------------------------------------------------------
    # Step 4: Verification
    # ------------------------------------------------------------------
    _section("STEP 4/4: Verification")
    
    conn = sqlite3.connect(DB_PATH)
    actual_count = conn.execute("SELECT COUNT(*) FROM ingested_batches").fetchone()[0]
    unique_products = conn.execute("SELECT COUNT(DISTINCT product_id) FROM ingested_batches").fetchone()[0]
    db_size = os.path.getsize(DB_PATH) / 1e6
    conn.close()

    _hr()
    print(f"  MIGRATION COMPLETE")
    print(f"  {'─' * 40}")
    print(f"  ✅ Rows inserted:    {actual_count:,}")
    print(f"  ℹ️  Unique products:  {unique_products}")
    print(f"  ℹ️  Database size:    {db_size:.1f} MB")
    print(f"  ℹ️  Insert time:      {insert_time:.1f}s")
    print(f"  📁 Output file:      {DB_PATH}")
    _hr()


if __name__ == "__main__":
    print()
    migrate()
    print("\n  Done. Database is ready for dashboard integration.\n")
