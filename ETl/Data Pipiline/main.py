import os
import glob
import pandas as pd
from features import FeatureExtractor


# -------------------------
# LOAD DATA (JSONL folder)
# -------------------------
def load_data(folder_path: str) -> pd.DataFrame:
    files = glob.glob(os.path.join(folder_path, "*.json"))

    if not files:
        raise ValueError(f"No JSON files found in {folder_path}")

    dfs = []

    for file in files:
        df = pd.read_json(file, lines=True)
        df["source_file"] = os.path.basename(file)
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True)


# -------------------------
# PIPELINE
# -------------------------
def run_pipeline(folder_path: str) -> pd.DataFrame:
    print(f"[INFO] Loading data from: {folder_path}")

    df = load_data(folder_path)

    print(f"[INFO] Raw data shape: {df.shape}")

    extractor = FeatureExtractor()

    print("[INFO] Running feature extraction...")
    df = extractor.transform(df)

    print("[INFO] Cleaning dataset...")
    df = clean_output(df)

    print(f"[INFO] Final shape: {df.shape}")

    return df


# -------------------------
# CLEANING STEP (post features)
# -------------------------
def clean_output(df: pd.DataFrame) -> pd.DataFrame:
    # remove duplicates
    df = df.drop_duplicates(subset=["product_url"])

    # optional: remove rows with no CPU + RAM (bad records)
    df = df[~((df["cpu"] == "unknown") & (df["ram_gb"].isna()))]

    return df


# -------------------------
# SAVE OUTPUT
# -------------------------
def save_output(df: pd.DataFrame, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[INFO] Saved to: {output_path}")


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    INPUT_FOLDER = "data_folder"   # <-- put your folder here
    OUTPUT_FILE = "output/processed_products.csv"

    df = run_pipeline(INPUT_FOLDER)

    print("\n[INFO] Sample output:")
    print(df.head())

    save_output(df, OUTPUT_FILE)