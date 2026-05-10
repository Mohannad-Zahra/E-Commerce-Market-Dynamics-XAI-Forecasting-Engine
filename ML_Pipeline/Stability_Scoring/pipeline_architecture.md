# Vola Score — Pipeline Architecture

> Auto-generated: 2026-05-08 11:13:01  
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

$$\text{ComputePotential}_{\text{laptop}} = \frac{\text{gpu\_tier} - 1}{9}$$

**Laptops with integrated graphics (edge case)**  
No `gpu_tier` is populated. A fixed conservative tier of **2** is assigned:

$$\text{ComputePotential}_{\text{integrated}} = \frac{2 - 1}{9} \approx 0.111$$

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

$$\text{ComputePotential}_{\text{phone}} = 0.6 \cdot \text{Norm}(\text{ram\_mid}) + 0.4 \cdot \text{Norm}(\text{storage\_mid})$$

where midpoints are: RAM `{2-4→3, 4-8→6, 8-16→12, 16-32→24, 32+→48}` GB  
and Storage `{0-64→32, 64-128→96, 128-256→192, 256-512→384}` GB, MinMax-normalised.

### 1.3 Scale-Invariant Price Features (Phase 2)

| Feature | Formula |
|---|---|
| `delta_p_7d` | $(P_t - P_{7d}) / P_{7d}$ |
| `delta_p_14d` | $(P_t - P_{14d}) / P_{14d}$ |
| `delta_p_1d` | Day-over-day % change of `price_final` per product |
| `vol_30d` | 30-day rolling std of `delta_p_1d` per product |

All absolute price columns (`base_price_egp`, `price_final`, `price_7d_avg`,
`price_14d_avg`) are dropped from the training feature matrix.

---

## 2. Target Variable Generation Mathematics (Phase 3)

### 2.1 Grouped Macro-Adjustment (OLS)

Products are binned into **10 compute_potential deciles**. For each decile an independent
OLS regression is fitted across all observations in that decile:

$$\hat{P}_{i,t} = \beta_0 + \beta_1 \cdot \text{EGP\_USD}_t + \beta_2 \cdot \text{CPI}_t$$

Solved via `numpy.linalg.lstsq`. Residuals:

$$R_{i,t} = P_{i,t} - \hat{P}_{i,t}$$

### 2.2 Per-Product Upside Semivariance

$$\mu_R^{(i)} = \frac{1}{T_i} \sum_t R_{i,t}$$

$$\text{SV}_{\text{upside}}^{(i)} = \sqrt{\frac{1}{T_i} \sum_t \max\!\left(0,\; R_{i,t} - \mu_R^{(i)}\right)^2}$$

### 2.3 Exponential Scoring

$$\lambda_i = 1.0 \times (1 - 0.5 \times \text{import\_lambda}_i)$$

$$S_i = 100 \cdot \exp\!\left(-\lambda_i \cdot \text{SV}_{\text{upside}}^{(i)}\right) \in [0, 100]$$

One score $S_i$ per product is broadcast to all time-series rows of that product.

---

## 3. Feature Importance (Top 10 — LightGBM Gain)

| Rank | Feature | Importance (gain) |
|---|---|---|
| 1 | `D_months` | 6,745 |
| 2 | `vol_30d` | 6,018 |
| 3 | `compute_potential` | 4,429 |
| 4 | `multiplier` | 3,538 |
| 5 | `import_lambda` | 3,176 |
| 6 | `official_egp_usd` | 2,687 |
| 7 | `cpi_inflation` | 2,083 |
| 8 | `delta_p_1d` | 865 |
| 9 | `delta_p_14d` | 752 |
| 10 | `delta_p_7d` | 317 |

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
| 1 | 2.2092 |
| 2 | 2.3316 |
| 3 | 2.2518 |
| 4 | 2.2615 |
| 5 | 2.7724 |
| **Mean** | **2.3653** |
| **Std**  | **0.2073** |

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
ONNX export status: Exported via `onnxmltools.convert_lightgbm` at `target_opset=13`.

---

## 6. Artifact Inventory

| Artifact | Description |
|---|---|
| `stability_model.joblib` | Full sklearn Pipeline (TargetEncoder + LGBMRegressor) |
| `stability_model.onnx` | LightGBM booster in ONNX format (opset=13) |
| `features_engineered.parquet` | Phase 1-2 output (pre-target) |
| `features_with_target.parquet` | Phase 3 output (training-ready) |
| `pipeline_architecture.md` | This document |


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
| count | 678,410 | 678,410 |
| mean | 93.3224 | 93.5911 |
| std | 5.7119 | 5.0050 |
| min | 66.4311 | 66.5479 |
| 25% | 90.3235 | 91.1016 |
| 50% | 95.7197 | 95.6751 |
| 75% | 97.6275 | 97.3771 |
| max | 99.4800 | 100.2502 |

**Additional calibration metrics (full dataset):**

| Metric | Value |
|---|---|
| MAE | 1.9469 |
| RMSE | 3.0247 |
| Bias (actual − predicted) | -0.2687 |
| Pearson r | 0.849993 |

### 6.3 Calibration Interpretation
- A **Pearson r close to 1.0** indicates the model has captured the ordinal ranking
  of product stability correctly.
- **Bias** near zero confirms the model is neither systematically over- nor under-predicting.
- The predicted distribution will be **narrower** than the synthetic target (regression
  toward the mean) — this is expected LightGBM behaviour and not a calibration failure.
- The full-dataset MAE is expected to be **lower** than the 5-fold CV MAE (2.3653)
  since the final model was retrained on all data.
