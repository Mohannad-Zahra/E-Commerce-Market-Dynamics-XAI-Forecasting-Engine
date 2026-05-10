"""
phase6_inference.py — Phase 6: Batch Inference & Enrichment
============================================================
Loads the serialized stability_model.joblib and runs batch inference
across the full 678,410-row dataset.

Input:  features_with_target.parquet  (contains stability_score + all features)
        stability_model.joblib         (TargetEncoder + LGBMRegressor pipeline)
Output: Dataset_Stability_Enriched.parquet  (all cols + predicted_stability_score)
        pipeline_architecture.md updated with Phase 6 calibration section
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

BASE     = Path(__file__).parent
IN_FILE  = BASE / "features_with_target.parquet"
MODEL_F  = BASE / "stability_model.joblib"
OUT_FILE = BASE / "Dataset_Stability_Enriched.parquet"
DOCS_F   = BASE / "pipeline_architecture.md"

# Feature schema must exactly match training
CAT_FEATURES = ["sale_event_label"]
NUM_FEATURES = [
    "compute_potential",
    "delta_p_7d", "delta_p_14d", "delta_p_1d", "vol_30d",
    "official_egp_usd", "cpi_inflation",
    "is_major_sale_period", "competitor_scarcity_count",
    "volume_weight", "D_months", "k", "multiplier",
    "import_lambda", "missing_release_date",
]
ALL_FEATURES = NUM_FEATURES + CAT_FEATURES
TARGET = "stability_score"

print("=" * 62)
print("  PHASE 6: Batch Inference & Enrichment")
print("=" * 62)

# ── 1. Load model ─────────────────────────────────────────────────────────────
print("\n[1/5] Loading stability_model.joblib ...")
pipeline = joblib.load(MODEL_F)
print(f"      Pipeline steps: {[s[0] for s in pipeline.steps]}")

# ── 2. Load feature dataset ───────────────────────────────────────────────────
print("[2/5] Loading features_with_target.parquet ...")
df = pd.read_parquet(IN_FILE)
print(f"      {len(df):,} rows x {len(df.columns)} cols")

# Verify schema alignment
missing = [c for c in ALL_FEATURES if c not in df.columns]
assert not missing, f"Missing features: {missing}"
print(f"      Feature schema aligned. ({len(ALL_FEATURES)} features)")

# ── 3. Prepare input matrix ───────────────────────────────────────────────────
print("[3/5] Preparing input matrix ...")
# Cast categorical exactly as during training
df["sale_event_label"] = df["sale_event_label"].astype(str)

X = df[ALL_FEATURES].copy()
print(f"      X shape: {X.shape}")

# ── 4. Batch inference ────────────────────────────────────────────────────────
print("[4/5] Running batch inference ...")
preds = pipeline.predict(X)
df["predicted_stability_score"] = preds.astype(float)
print(f"      Predictions complete.")

# Calibration stats
actual = df[TARGET]
pred   = df["predicted_stability_score"]

cal_stats = pd.DataFrame({
    "metric":  ["count", "mean", "std", "min", "25%", "50%", "75%", "max"],
    "stability_score (actual)": [
        f"{actual.count():,}", f"{actual.mean():.4f}", f"{actual.std():.4f}",
        f"{actual.min():.4f}", f"{actual.quantile(0.25):.4f}",
        f"{actual.median():.4f}", f"{actual.quantile(0.75):.4f}",
        f"{actual.max():.4f}",
    ],
    "predicted_stability_score": [
        f"{pred.count():,}", f"{pred.mean():.4f}", f"{pred.std():.4f}",
        f"{pred.min():.4f}", f"{pred.quantile(0.25):.4f}",
        f"{pred.median():.4f}", f"{pred.quantile(0.75):.4f}",
        f"{pred.max():.4f}",
    ],
})

residuals   = actual - pred
mae_full    = np.abs(residuals).mean()
rmse_full   = np.sqrt((residuals ** 2).mean())
bias        = residuals.mean()          # positive = model under-predicts
corr        = actual.corr(pred)

print(f"\n      === Calibration Summary ===")
print(f"      Full-dataset MAE  : {mae_full:.4f}")
print(f"      Full-dataset RMSE : {rmse_full:.4f}")
print(f"      Bias (actual-pred): {bias:+.4f}")
print(f"      Pearson r         : {corr:.6f}")
print(f"\n{cal_stats.to_string(index=False)}")

# ── 5. Export enriched dataset + update docs ──────────────────────────────────
print(f"\n[5/5] Exporting enriched dataset ...")
df.to_parquet(OUT_FILE, index=False, engine="pyarrow")
print(f"      Saved {len(df):,} rows x {len(df.columns)} cols -> {OUT_FILE.name}")
print(f"      File size: {OUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# Build calibration table rows for markdown
cal_rows = "\n".join(
    f"| {row['metric']} | {row['stability_score (actual)']} "
    f"| {row['predicted_stability_score']} |"
    for _, row in cal_stats.iterrows()
)

phase6_section = f"""

---

## 6. Phase 6 — Batch Inference & Enrichment

### 6.1 Inference Setup
The full 678,410-row dataset was passed through the serialized `stability_model.joblib`
(sklearn Pipeline: TargetEncoder + LGBMRegressor). Feature schema was aligned to the
exact 16-column matrix used during training. Output appended as `predicted_stability_score`.

**Exported artifact**: `Dataset_Stability_Enriched.parquet`

### 6.2 Model Calibration — Predicted vs Actual

| Metric | `stability_score` (Phase 3 synthetic) | `predicted_stability_score` |
|---|---|---|
{cal_rows}

**Additional calibration metrics (full dataset):**

| Metric | Value |
|---|---|
| MAE | {mae_full:.4f} |
| RMSE | {rmse_full:.4f} |
| Bias (actual − predicted) | {bias:+.4f} |
| Pearson r | {corr:.6f} |

### 6.3 Calibration Interpretation
- A **Pearson r close to 1.0** indicates the model has captured the ordinal ranking
  of product stability correctly.
- **Bias** near zero confirms the model is neither systematically over- nor under-predicting.
- The predicted distribution will be **narrower** than the synthetic target (regression
  toward the mean) — this is expected LightGBM behaviour and not a calibration failure.
- The full-dataset MAE is expected to be **lower** than the 5-fold CV MAE (2.3653)
  since the final model was retrained on all data.
"""

# Append to existing pipeline_architecture.md
existing = DOCS_F.read_text(encoding="utf-8")
DOCS_F.write_text(existing + phase6_section, encoding="utf-8")
print(f"      pipeline_architecture.md updated ({DOCS_F.stat().st_size/1024:.1f} KB)")

print(f"\nPhase 6 complete.")
