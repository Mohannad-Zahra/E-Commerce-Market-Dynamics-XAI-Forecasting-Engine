import sqlite3
import pandas as pd
import os

# Paths
DB_PATH = r"e:\MY PROJECT\Machine Learning\E-Commerce-Market-Dynamics-XAI-Forecasting-Engine\data\electronics_history.db"
OUTPUT_DIR = r"e:\MY PROJECT\Machine Learning\E-Commerce-Market-Dynamics-XAI-Forecasting-Engine\data"
RECOMMENDATION_DATA_DIR = r"e:\MY PROJECT\Machine Learning\E-Commerce-Market-Dynamics-XAI-Forecasting-Engine\Recommendation system\data"

def generate_processed_csv():
    print(f"[INFO] Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Load master_training_features
    print("[INFO] Loading master_training_features...")
    query_features = "SELECT scrape_timestamp, product_id, price_t_plus_14, D_months FROM master_training_features"
    df_features = pd.read_sql_query(query_features, conn)
    
    # 2. Load products to get base prices (original prices)
    print("[INFO] Loading product metadata...")
    query_products = "SELECT product_url as product_id, raw_original_price as base_price_egp FROM products"
    df_products = pd.read_sql_query(query_products, conn)
    
    # 3. Merge
    print("[INFO] Merging data...")
    df = pd.merge(df_features, df_products, on="product_id", how="left")
    
    # 4. Calculate price_14d_avg
    # Note: Since the real price_14d_avg is missing, we calculate it from the price history in the DB
    print("[INFO] Calculating 14-day rolling average...")
    df['scrape_timestamp'] = pd.to_datetime(df['scrape_timestamp'])
    df = df.sort_values(['product_id', 'scrape_timestamp'])
    
    # Calculate rolling average per product
    df['price_14d_avg'] = df.groupby('product_id')['price_t_plus_14'].transform(
        lambda x: x.rolling(window=14, min_periods=1).mean()
    )
    
    # 5. Clean up and select columns
    # Re-map columns as expected by ranking_engine.py
    # processed_cols = ["scrape_timestamp", "product_id", "base_price_egp", "price_14d_avg", "D_months"]
    
    # If base_price_egp is missing, use price_t_plus_14 as a fallback
    df['base_price_egp'] = df['base_price_egp'].fillna(df['price_t_plus_14'])
    
    final_df = df[["scrape_timestamp", "product_id", "base_price_egp", "price_14d_avg", "D_months"]]
    
    # Save to outputs
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RECOMMENDATION_DATA_DIR, exist_ok=True)
    
    path1 = os.path.join(OUTPUT_DIR, "Dataset_Pipeline_Processed.csv")
    path2 = os.path.join(RECOMMENDATION_DATA_DIR, "Dataset_Pipeline_Processed.csv")
    
    final_df.to_csv(path1, index=False)
    final_df.to_csv(path2, index=False)
    
    # Also ensure ECom_Forecast_XAI_data.csv is in the Recommendation system/data folder
    # as the scripts expect it there
    source_xai = os.path.join(OUTPUT_DIR, "ECom_Forecast_XAI_data.csv")
    dest_xai = os.path.join(RECOMMENDATION_DATA_DIR, "ECom_Forecast_XAI_data.csv")
    
    if os.path.exists(source_xai):
        print(f"[INFO] Copying XAI data to recommendation module...")
        import shutil
        shutil.copy2(source_xai, dest_xai)
    
    print(f"[SUCCESS] Dataset_Pipeline_Processed.csv generated at:\n  - {path1}\n  - {path2}")
    conn.close()

if __name__ == "__main__":
    generate_processed_csv()
