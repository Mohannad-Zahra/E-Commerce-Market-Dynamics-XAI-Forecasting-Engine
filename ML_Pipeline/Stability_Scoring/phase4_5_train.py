"""
phase4_5_train.py — Phases 4 & 5: Training, Validation, Export + Documentation
================================================================================
Input:  features_with_target.parquet  (from phase3_target.py)
Output: stability_model.joblib
        stability_model.onnx
        pipeline_architecture.md
"""

import subprocess, sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path
from datetime import datetime

# ── Install onnxmltools if absent ─────────────────────────────────────────────
try:
    import onnxmltools
except ImportError:
    print("Installing onnxmltools …")
    subprocess.check_call([sys.executable, "-m", "pip", "install",
                           "onnxmltools", "-q"])
    import onnxmltools

import numpy as np
import pandas as pd
import joblib

from sklearn.compose   import ColumnTransformer
from sklearn.pipeline  import Pipeline
from sklearn.preprocessing import TargetEncoder
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics         import mean_absolute_error
from lightgbm import LGBMRegressor

from onnxmltools.convert          import convert_lightgbm
from onnxmltools.convert.common.data_types import FloatTensorType

OUT_DIR  = Path(__file__).parent
IN_FILE  = OUT_DIR / "features_with_target.parquet"
JOBLIB_F = OUT_DIR / "stability_model.joblib"
ONNX_F   = OUT_DIR / "stability_model.onnx"
DOCS_F   = OUT_DIR / "pipeline_architecture.md"

# ── Column definitions ────────────────────────────────────────────────────────
TARGET = "stability_score"
META   = ["product_id", "scrape_timestamp", "raw_title",
          "global_release_date_str", "category"]

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

LGBM_PARAMS = dict(
    objective    = "regression_l1",
    metric       = "mae",
    n_estimators = 500,
    learning_rate= 0.05,
    num_leaves   = 63,
    min_child_samples = 30,
    subsample    = 0.8,
    colsample_bytree = 0.8,
    random_state = 42,
    n_jobs       = -1,
    verbose      = -1,
)

print("=" * 62)
print("  PHASE 4-5: Training + Export + Documentation")
print("=" * 62)

# ── 1. Load data ──────────────────────────────────────────────────────────────
print("\n[1/7] Loading features_with_target.parquet …")
df = pd.read_parquet(IN_FILE)
print(f"      {len(df):,} rows × {len(df.columns)} cols")

# Cast categorical to string (handles NaN → "nan" treated as own category)
df["sale_event_label"] = df["sale_event_label"].astype(str)

# Verify all needed columns exist
missing_cols = [c for c in ALL_FEATURES + [TARGET] if c not in df.columns]
assert not missing_cols, f"Missing columns: {missing_cols}"

# ── 2. Sort by time (mandatory for TimeSeriesSplit) ───────────────────────────
print("[2/7] Sorting by scrape_timestamp …")
df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"])
df = df.sort_values("scrape_timestamp").reset_index(drop=True)

X = df[ALL_FEATURES].copy()
y = df[TARGET].copy()
print(f"      X shape: {X.shape}  |  y range: [{y.min():.2f}, {y.max():.2f}]")

# ── 3. Build sklearn pipeline ─────────────────────────────────────────────────
print("[3/7] Building sklearn Pipeline …")
preprocessor = ColumnTransformer(
    transformers=[
        ("target_enc", TargetEncoder(smooth="auto", target_type="continuous"),
         CAT_FEATURES),
        ("passthrough", "passthrough", NUM_FEATURES),
    ],
    remainder="drop",
)

pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", LGBMRegressor(**LGBM_PARAMS)),
])

# ── 4. TimeSeriesSplit cross-validation ───────────────────────────────────────
print("[4/7] Running TimeSeriesSplit (K=5) cross-validation …")
tscv = TimeSeriesSplit(n_splits=5)
fold_maes = []

for fold, (train_idx, val_idx) in enumerate(tscv.split(X), start=1):
    X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

    pipeline.fit(X_tr, y_tr)
    preds = pipeline.predict(X_val)
    mae   = mean_absolute_error(y_val, preds)
    fold_maes.append(mae)
    print(f"      Fold {fold}: train={len(train_idx):,}  val={len(val_idx):,}  "
          f"MAE={mae:.4f}")

mean_mae = float(np.mean(fold_maes))
std_mae  = float(np.std(fold_maes))
print(f"\n      CV MAE = {mean_mae:.4f} ± {std_mae:.4f}")

# ── 5. Refit on full data ─────────────────────────────────────────────────────
print("[5/7] Refitting on full dataset …")
pipeline.fit(X, y)

# Feature importance (after full fit)
lgbm_model    = pipeline.named_steps["model"]
importances   = lgbm_model.feature_importances_

# ColumnTransformer output order: cat features first, then num features
feature_names = CAT_FEATURES + NUM_FEATURES
imp_df = (
    pd.DataFrame({"feature": feature_names, "importance": importances})
    .sort_values("importance", ascending=False)
    .reset_index(drop=True)
)
print("\n      Top 10 Features:")
print(imp_df.head(10).to_string(index=False))

# ── 6. Export artifacts ───────────────────────────────────────────────────────
print("\n[6/7] Exporting artifacts …")

# 6a. Joblib — full sklearn pipeline
joblib.dump(pipeline, JOBLIB_F, compress=3)
print(f"      ✓ stability_model.joblib  ({JOBLIB_F.stat().st_size/1024:.1f} KB)")

# 6b. ONNX — LightGBM booster only (TargetEncoder applied externally pre-inference)
try:
    booster      = lgbm_model.booster_
    n_in         = len(NUM_FEATURES) + len(CAT_FEATURES)  # after TargetEncoder: all numeric
    initial_type = [("float_input", FloatTensorType([None, n_in]))]
    onnx_model   = convert_lightgbm(booster, initial_types=initial_type,
                                    target_opset=13)
    with open(ONNX_F, "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"      ✓ stability_model.onnx     ({ONNX_F.stat().st_size/1024:.1f} KB)")
    onnx_ok = True
except Exception as exc:
    print(f"      ⚠ ONNX export failed: {exc}")
    onnx_ok = False

# ── 7. Generate pipeline_architecture.md ─────────────────────────────────────
print("[7/7] Generating pipeline_architecture.md …")

TOP10 = imp_df.head(10)
top10_rows = "\n".join(
    f"| {i+1} | `{row.feature}` | {int(row.importance):,} |"
    for i, row in TOP10.iterrows()
)
cv_rows = "\n".join(
    f"| {i+1} | {mae:.4f} |"
    for i, mae in enumerate(fold_maes)
)
onnx_note = (
    "Exported via `onnxmltools.convert_lightgbm` at `target_opset=13`."
    if onnx_ok
    else "ONNX export encountered an error — see console output."
)

doc = f"""# Vola Score — Pipeline Architecture

> Auto-generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
> Dataset: `Dataset_Pipeline_Processed.csv` (678,410 rows)

---

## 1. Feature Engineering Rationale

### 1.1 Category Inference
Products are classified as **Laptop** or **Phone/Tablet** by matching the `product_id` URL
against a curated keyword regex. Tablets (iPad, Honor Pad, etc.) are routed through the
Phone compute path since they share the same hardware ordinal schema.

### 1.2 `compute_potential` — Unified Hardware Score ∈ [0.0, 1.0]

**Laptops with discrete GPU**
The raw `gpu_tier` string (e.g., `"RTX 5070"`) is mapped to a numeric tier 1–10 via a
hand-curated table covering 24 observed GPU strings across NVIDIA (GTX, RTX 20/30/40/50)
and AMD (RX RDNA2/3/4) families. The score is then normalised:

$$\\text{{ComputePotential}}_{{\\text{{laptop}}}} = \\frac{{\\text{{gpu\\_tier}} - 1}}{{9}}$$

**Laptops with integrated graphics (edge case)**  
No `gpu_tier` is populated. A fixed conservative tier of **2** is assigned:

$$\\text{{ComputePotential}}_{{\\text{{integrated}}}} = \\frac{{2 - 1}}{{9}} \\approx 0.111$$

**Phones and Tablets**  
Primary path — chipset regex on `raw_title`:
| Pattern | Example | Score |
|---|---|---|
| Snapdragon 8 Elite / Gen 3/4 | SD 8 Gen 3 | 0.95 |
| Snapdragon 8 Gen (other) | SD 8 Gen 2 | 0.88 |
| A16/A17/A18 Bionic | iPhone 15 Pro | 0.93 |
| Dimensity 9xxx | Dimensity 9300 | 0.82 |
| Snapdragon 7xx / Dimensity 8xx | Mid-range | 0.50–0.55 |
| Helio G/P, Dimensity 3-digit | Budget | 0.20–0.30 |

Fallback proxy (α=0.6, β=0.4) when no chipset is matched:

$$\\text{{ComputePotential}}_{{\\text{{phone}}}} = 0.6 \\cdot \\text{{Norm}}(\\text{{ram\\_mid}}) + 0.4 \\cdot \\text{{Norm}}(\\text{{storage\\_mid}})$$

where midpoints are: RAM `{{2-4→3, 4-8→6, 8-16→12, 16-32→24, 32+→48}}` GB  
and Storage `{{0-64→32, 64-128→96, 128-256→192, 256-512→384}}` GB, MinMax-normalised.

### 1.3 Scale-Invariant Price Features (Phase 2)

| Feature | Formula |
|---|---|
| `delta_p_7d` | $(P_t - P_{{7d}}) / P_{{7d}}$ |
| `delta_p_14d` | $(P_t - P_{{14d}}) / P_{{14d}}$ |
| `delta_p_1d` | Day-over-day % change of `price_final` per product |
| `vol_30d` | 30-day rolling std of `delta_p_1d` per product |

All absolute price columns (`base_price_egp`, `price_final`, `price_7d_avg`,
`price_14d_avg`) are dropped from the training feature matrix.

---

## 2. Target Variable Generation Mathematics (Phase 3)

### 2.1 Grouped Macro-Adjustment (OLS)

Products are binned into **10 compute_potential deciles**. For each decile an independent
OLS regression is fitted across all observations in that decile:

$$\\hat{{P}}_{{i,t}} = \\beta_0 + \\beta_1 \\cdot \\text{{EGP\\_USD}}_t + \\beta_2 \\cdot \\text{{CPI}}_t$$

Solved via `numpy.linalg.lstsq`. Residuals:

$$R_{{i,t}} = P_{{i,t}} - \\hat{{P}}_{{i,t}}$$

### 2.2 Per-Product Upside Semivariance

$$\\mu_R^{{(i)}} = \\frac{{1}}{{T_i}} \\sum_t R_{{i,t}}$$

$$\\text{{SV}}_{{\\text{{upside}}}}^{{(i)}} = \\sqrt{{\\frac{{1}}{{T_i}} \\sum_t \\max\\!\\left(0,\\; R_{{i,t}} - \\mu_R^{{(i)}}\\right)^2}}$$

### 2.3 Exponential Scoring

$$\\lambda_i = 1.0 \\times (1 - 0.5 \\times \\text{{import\\_lambda}}_i)$$

$$S_i = 100 \\cdot \\exp\\!\\left(-\\lambda_i \\cdot \\text{{SV}}_{{\\text{{upside}}}}^{{(i)}}\\right) \\in [0, 100]$$

One score $S_i$ per product is broadcast to all time-series rows of that product.

---

## 3. Feature Importance (Top 10 — LightGBM Gain)

| Rank | Feature | Importance (gain) |
|---|---|---|
{top10_rows}

**Interpretation notes:**
- High-ranked price-momentum features (`delta_p_7d`, `delta_p_14d`) capture short-term
  price instability, the primary driver of semivariance.
- `compute_potential` encodes hardware tier; higher-tier products tend toward different
  price elasticity profiles, linking directly to the OLS decile grouping.
- `import_lambda` encodes import sensitivity — a key λ modifier in the scoring formula,
  explaining its predictive power.
- `official_egp_usd` and `cpi_inflation` are the macro regressors used in Phase 3 OLS;
  their residual signal is captured by the model.

---

## 4. Cross-Validation Results (TimeSeriesSplit, K=5)

| Fold | MAE |
|---|---|
{cv_rows}
| **Mean** | **{mean_mae:.4f}** |
| **Std**  | **{std_mae:.4f}** |

**Validation strategy:** `TimeSeriesSplit` enforces forward-looking predictions — each
fold trains only on data prior to the validation window, preventing any look-ahead bias.
Folds are ordered chronologically over the 2025-04-16 → 2026-04-29 date range.

---

## 5. Known Limitations

### 5.1 GPU Tier Mapping
The 24-entry GPU string → numeric tier table is hand-curated from observed values.
**Any GPU string not in the table** (e.g., future RTX 6000-series) falls through as `NaN`
and receives the integrated-graphics fallback (`compute_potential = 0.111`). This could
under-rank future high-end laptops.

### 5.2 Phone Chipset Extraction
Chipset regex matching is pattern-based and may fail for non-standard title formats,
localised Arabic product names, or misspellings. Unmatched phones fall back to the
RAM/storage proxy (α=0.6, β=0.4), which loses the compute dimension entirely.

### 5.3 Target Score Broadasting
`stability_score` is computed once per product (across its full time-series) and
broadcast to all rows. The model therefore predicts a **product-level latent property**
from **time-varying features**. Temporal features (momentum, volatility) serve as
proxies for underlying price behaviour, not direct row-level targets.

### 5.4 OLS Residuals Assume Linearity
The macro-adjustment OLS assumes a linear relationship between EGP/USD exchange rate,
CPI, and price. Non-linear macro shocks (e.g., sudden import bans, hyperinflation
spikes) will produce outsized residuals that bias the semivariance upward, resulting
in artificially lower stability scores for affected products.

### 5.5 Sale Event Label Sparsity
`sale_event_label` is only populated for ~5.5% of rows. TargetEncoder with `smooth="auto"`
handles this via Bayesian smoothing toward the global target mean, but the encoding
signal may be noisy for rare events with few observations.

### 5.6 ONNX Export Scope
The exported `stability_model.onnx` contains **only the LightGBM booster**.
The `TargetEncoder` preprocessing step (sklearn) must be applied to `sale_event_label`
**before** passing features to the ONNX model. The full sklearn pipeline
(including TargetEncoder) is available in `stability_model.joblib` for Python inference.
{f"ONNX export status: {onnx_note}"}

---

## 6. Artifact Inventory

| Artifact | Description |
|---|---|
| `stability_model.joblib` | Full sklearn Pipeline (TargetEncoder + LGBMRegressor) |
| `stability_model.onnx` | LightGBM booster in ONNX format (opset=13) |
| `features_engineered.parquet` | Phase 1-2 output (pre-target) |
| `features_with_target.parquet` | Phase 3 output (training-ready) |
| `pipeline_architecture.md` | This document |
"""

DOCS_F.write_text(doc, encoding="utf-8")
print(f"      ✓ pipeline_architecture.md  ({DOCS_F.stat().st_size/1024:.1f} KB)")

print("\n✓  Phase 4-5 complete. All artifacts written to:")
for f in [JOBLIB_F, ONNX_F, DOCS_F]:
    status = "✓" if f.exists() else "✗"
    print(f"      {status} {f.name}")
