import pandas as pd
import joblib

# === 1. Row counts ===
df_s = pd.read_csv("Dataset_Stability_Enriched.csv")
df_f = pd.read_csv("Dataset_Forecasting_7_14.csv")
print("=== ROW COUNTS ===")
print(f"Stability: {len(df_s):,}")
print(f"Forecast:  {len(df_f):,}")

# === 2. Key uniqueness ===
print("\n=== KEY UNIQUENESS (Stability) ===")
print(f"product_id unique: {df_s['product_id'].nunique():,}")
combo_s = df_s.groupby(["product_id", "scrape_timestamp"]).ngroups
print(f"(product_id, scrape_timestamp) unique: {combo_s:,}")
print(f"Total rows: {len(df_s):,}")
print(f"Composite key is PK: {combo_s == len(df_s)}")

print("\n=== KEY UNIQUENESS (Forecast) ===")
print(f"product_id unique: {df_f['product_id'].nunique():,}")
combo_f = df_f.groupby(["product_id", "scrape_timestamp"]).ngroups
print(f"(product_id, scrape_timestamp) unique: {combo_f:,}")
print(f"Total rows: {len(df_f):,}")
print(f"Composite key is PK: {combo_f == len(df_f)}")

# === 3. Timestamp format alignment ===
print("\n=== TIMESTAMP SAMPLES ===")
print("Stability:", df_s["scrape_timestamp"].iloc[:3].tolist())
print("Forecast: ", df_f["scrape_timestamp"].iloc[:3].tolist())

# === 4. Merge diagnostics ===
common = pd.merge(
    df_s[["product_id", "scrape_timestamp"]],
    df_f[["product_id", "scrape_timestamp"]],
    on=["product_id", "scrape_timestamp"],
    how="inner",
)
print(f"\n=== MERGE DIAGNOSTICS ===")
print(f"Inner join matches: {len(common):,}")
print(f"Coverage of stability rows: {len(common)/len(df_s)*100:.2f}%")

# === 5. sale_event_label inspection ===
print("\n=== SALE_EVENT_LABEL (Stability) ===")
print(df_s["sale_event_label"].dtype)
print(df_s["sale_event_label"].unique()[:20])

print("\n=== SALE_EVENT_LABEL (Forecast) ===")
print(df_f["sale_event_label"].dtype)
print(df_f["sale_event_label"].unique()[:20])

# === 6. compute_potential distribution ===
print("\n=== COMPUTE_POTENTIAL DISTRIBUTION ===")
print(df_s["compute_potential"].describe())
print(f"Median: {df_s['compute_potential'].median():.4f}")

# === 7. Forecast model features ===
m14 = joblib.load("model_14d.joblib")
print("\n=== FORECAST MODEL (model_14d) ===")
print("Feature names:", m14.feature_name_)
print("Num features:", m14.n_features_in_)

# === 8. Stability model pipeline details ===
sm = joblib.load("stability_model.joblib")
ct = sm.named_steps["preprocessor"]
print("\n=== STABILITY MODEL PIPELINE ===")
for name, trans, cols in ct.transformers_:
    tname = type(trans).__name__ if hasattr(type(trans), "__name__") else str(trans)
    print(f"  {name}: {tname} -> {cols}")

te = ct.named_transformers_["target_enc"]
print("\nTargetEncoder attributes:")
for attr in ["categories_", "encodings_", "classes_", "target_type_"]:
    if hasattr(te, attr):
        val = getattr(te, attr)
        print(f"  {attr}: {val}")
