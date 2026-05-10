import os
import re
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy import create_engine

# --- Configuration ---
DB_PATH = "sqlite:///src_integrated/database/wise_purchaser.sqlite"
MODELS_DIR = Path("ETL/models")

# GPU tier map (24 unique strings → numeric tier 1-10)
GPU_TIER_MAP: dict[str, int] = {
    "GTX 1650": 2, "GTX 1660": 3, "RTX 2050": 3, "RTX 3050": 4, "RTX3050": 4,
    "RTX 3070": 6, "RTX 4050": 5, "RTX4050": 5, "RTX 4060": 6, "RTX 4070": 7,
    "RTX4080": 8, "RTX 5050": 5, "RTX 5060": 7, "RTX 5070": 8, "RTX5070": 8,
    "RTX 5080": 9, "RTX 5090": 10, "RX 6500": 3, "RX 6650": 4, "RX 6900": 7,
    "RX 7800": 7, "RX 7900": 8, "RX 9060": 6, "RX 9070": 7,
}

# RAM / Storage ordinal → midpoint GB
RAM_MID = {"2-4": 3, "4-8": 6, "8-16": 12, "16-32": 24, "32+": 48}
STO_MID = {"0-64": 32, "64-128": 96, "128-256": 192, "256-512": 384}

LAPTOP_KW = (
    r"laptop|macbook|thinkpad|aspire|vivobook|inspiron|pavilion|spectre|envy|"
    r"zenbook|gram|surface-laptop|swift|spin|chromebook|ideapad|probook|"
    r"elitebook|latitude|xps|omen|predator|nitro|rog-"
)

def discover_onnx_model(model_name_pattern: str):
    """Dynamically search for .onnx files in the models directory."""
    print(f"[INFO] Searching for .onnx models matching '{model_name_pattern}' in {MODELS_DIR}...")
    onnx_files = list(MODELS_DIR.glob(f"*{model_name_pattern}*.onnx"))
    if onnx_files:
        print(f"[SUCCESS] Found model: {onnx_files[0]}")
        return onnx_files[0]
    print(f"[WARN] No .onnx model found for {model_name_pattern}.")
    return None

def extract_chipset_score(title: str) -> float | None:
    if not isinstance(title, str): return None
    t = title.lower()
    if re.search(r"snapdragon\s*8\s*(gen\s*[234]|elite)", t): return 0.95
    if re.search(r"snapdragon\s*8\s*gen", t): return 0.88
    if re.search(r"a1[678]\s*(bionic|pro|chip)?", t): return 0.93
    if re.search(r"a15\s*bionic", t): return 0.80
    if re.search(r"dimensity\s*9[0-9]{3}", t): return 0.82
    if re.search(r"snapdragon\s*(7[0-9]{2}|695|690)", t): return 0.55
    if re.search(r"dimensity\s*[78][0-9]{2}", t): return 0.50
    if re.search(r"a1[234]\s*(bionic)?", t): return 0.60
    if re.search(r"snapdragon\s*(4[0-9]{2}|480)", t): return 0.25
    if re.search(r"helio\s*[gp][0-9]+", t): return 0.20
    if re.search(r"dimensity\s*[0-9]{3}[^0-9]", t): return 0.30
    return None

def run_etl_pipeline(batch_id: str = None):
    engine = create_engine(DB_PATH)
    
    # Discovery
    stability_model = discover_onnx_model("stability")
    
    print("\n[1/3] Fetching data from database...")
    query = "SELECT * FROM RawScrapedData"
    if batch_id:
        query += f" WHERE batch_id = '{batch_id}'"
    
    df = pd.read_sql(query, engine)
    if df.empty:
        print("[DONE] No data to process.")
        return

    print(f"[2/3] Processing {len(df)} rows...")
    # Category Inference
    url_lower = df["product_id"].str.lower()
    df["category"] = "Phone"
    df.loc[url_lower.str.contains(LAPTOP_KW, na=False, regex=True), "category"] = "Laptop"
    
    # Hardware Engineering
    df["gpu_tier_num"] = df["gpu_tier"].map(GPU_TIER_MAP)
    # ... (rest of the logic from Vola Score)
    
    # Price Momentum (Dynamic)
    df = df.sort_values(["product_id", "scrape_timestamp"])
    # ...
    
    print("[3/3] Writing to ProcessedProducts table...")
    # df.to_sql("ProcessedProducts", engine, if_exists="append", index=False)
    print("      ✓ ETL Cycle Complete.")

if __name__ == "__main__":
    run_etl_pipeline()
