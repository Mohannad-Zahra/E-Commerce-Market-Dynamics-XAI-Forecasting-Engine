# XAI Validation & Architectural Documentation Pipeline

End-to-end Explainable AI pipeline: merge datasets, extract SHAP attributions scaled to consumer pricing, and produce objective self-assessment.

---

## Reconnaissance Findings

| Artifact | Prompt Name | Actual Name | Notes |
|---|---|---|---|
| Stability Data | `dataset_stability.parquet` | `Dataset_Stability_Enriched.csv` | **678,410 rows**, 23 cols. CSV not parquet. |
| Forecast Data | `dataset_forecast.parquet` | `Dataset_Forecasting_7_14.csv` | **628,290 rows**, 32 cols. CSV not parquet. |
| Forecast Model | `forecast_14d.joblib` | `model_14d.joblib` | Raw `LGBMRegressor` — **no pipeline wrapper**. 18 features. |
| Stability Model | `stability_model.joblib` | `stability_model.joblib` | `sklearn.Pipeline` with `ColumnTransformer` (TargetEncoder) + `LGBMRegressor`. 16 features. |
| Business Logic | `Pipeline_Calculation_Report.md` | Same | Exponential depreciation model, not VAT/margin multipliers. |

### Key Diagnostics

- **Composite key** `(product_id, scrape_timestamp)` is a **perfect PK** in both datasets.
- **Timestamps** are daily-level strings (`YYYY-MM-DD`). Stability starts `2025-04-16`, Forecast starts `2025-04-30` (14-day offset — the forecast model needs 14 days of lag history).
- **Inner-join coverage**: 628,290 / 678,410 = **92.61%**. The ~50K unmatched rows are the first 14 days of stability data.
- **`sale_event_label`** in stability is raw strings (object dtype). 10 categories including NaN.

> [!IMPORTANT]
> **Model-Feature Matrix Mismatch**: The forecast model (`model_14d.joblib`) requires 18 features including `cpu_tier`, `gpu_tier`, `ram_gb_ordinal`, `storage_ordinal`, `price_lag_*`, `rolling_*` — **8 of which do not exist** in `dataset_stability`. Running forecast-model SHAP on the stability matrix is impossible without pulling those 8 columns from the forecast dataset.
>
> **Engineering Decision**: The stability model pipeline (`stability_model.joblib`) is the correct SHAP target because:
> 1. It **has** the pipeline wrapper with TargetEncoder (matching Actions 3.1 & 3.4).
> 2. Its 16 features **align perfectly** with `dataset_stability` (matching Action 3.2).
> 3. `compute_potential` exists for tier splitting (matching Action 3.2).
> 4. The forecast target `price_t_plus_14` is injected via Phase 1 merge for downstream context.

> [!WARNING]
> **TargetEncoder Degeneracy**: The TargetEncoder maps ALL 10 `sale_event_label` categories to the identical value `93.322`. This means it provides **zero discriminative power** — every sale event encodes to the global target mean. This is a significant finding for Phase 4 self-assessment.

---

## Open Questions

> [!IMPORTANT]
> 1. **Tier Split Boundary**: `compute_potential` distribution is heavily right-skewed (median=0.111, 75th=0.12, max=1.0). Should the split use the **median (0.111)** or a natural cluster boundary (~0.2) separating phones/tablets from laptops? The plan currently uses median.
> 2. **Scaling Semantics**: The stability model predicts `stability_score` (not a price). Scaling SHAP values by the depreciation `multiplier` converts attributions from "stability-score impact" to "consumer-price-aligned stability impact." Is this the intended interpretation, or should we document this as a conceptual limitation?
> 3. **Delta SHAP (Action 3.6)**: Requires aligning each product's SHAP values at `T_0` vs `T_{-14}`. For products with fewer than 14 days of history, these deltas will be undefined. Should we NaN-fill or exclude them?

---

## Proposed Changes

### Phase 1: Dynamic Data Integration

#### [NEW] [xai_pipeline.py](file:///c:/Users/mohan/OneDrive/Desktop/forecast+shap/xai_pipeline.py)

The single execution script containing all 6 phases.

**Action 1.1–1.2**: Load both CSVs. Profile key uniqueness (already confirmed: composite PK is valid).

**Action 1.3**: Standard **left-join** on `['product_id', 'scrape_timestamp']` (not `merge_asof` — timestamps are perfectly aligned at daily granularity). Extract only `price_t_plus_14` from the forecast dataset.

```python
target_col = df_forecast[['product_id', 'scrape_timestamp', 'price_t_plus_14']]
df_merged = df_stability.merge(target_col, on=['product_id', 'scrape_timestamp'], how='left')
assert len(df_merged) == len(df_stability)  # 678,410
```

**Action 1.4**: Forward-fill NaN in `price_t_plus_14` grouped by `product_id` (covers ~50K early rows).

---

### Phase 2: Business Logic Extraction

**Action 2.1**: Parse the depreciation formula from `Pipeline_Calculation_Report.md`:

$$\text{price\_final} = \text{base\_price\_egp} \times e^{-k \cdot D}$$

The deterministic "weight" is the per-row `multiplier` column: $W = e^{-k \cdot D}$, where $k \in \{0.0, 0.0005, 0.0011\}$ based on `import_lambda`.

**Action 2.2**: Post-hoc scaling function (per-row, not a global constant):

$$g(\phi_i) = \phi_i \times \text{multiplier}_{\text{row}}$$

```python
def scale_shap_to_consumer(shap_values, multiplier_array):
    return shap_values * multiplier_array[:, np.newaxis]
```

---

### Phase 3: Stratified XAI & Translation

**Action 3.1**: Extract the raw LightGBM booster from the stability pipeline:

```python
pipeline = joblib.load('stability_model.joblib')
ct = pipeline.named_steps['preprocessor']
lgbm_model = pipeline.named_steps['model']
booster = lgbm_model.booster_
```

**Action 3.2**: Split by `compute_potential` median (0.1111):
- **Low-tier** (phones/tablets): `compute_potential <= 0.1111`
- **High-tier** (laptops): `compute_potential > 0.1111`

**Action 3.3**: For each tier:
1. Transform features through the `ColumnTransformer` to get the encoded matrix.
2. Compute SHAP via `shap.TreeExplainer(lgbm_model, feature_perturbation="tree_path_dependent")`.
3. Use the tier's own data as background (interventional).

**Action 3.4 (TargetEncoder Inversion)**: Build a feature-name mapping from the ColumnTransformer output:
- Column 0 → `sale_event_label` (from TargetEncoder)
- Columns 1–15 → passthrough feature names in order

The SHAP DataFrame columns are renamed from indices to original feature names.

**Action 3.5**: Apply `g(φ)` per-row using the `multiplier` column.

**Action 3.6 (Delta Isolation)**: For each `product_id`, compute:
$$\Delta\phi_i = \phi_i(T_0) - \phi_i(T_{-14})$$

Sort by `scrape_timestamp`, shift SHAP values by 14 positions within each product group, and subtract.

---

### Phase 4: Self-Assessment

Programmatic checks:

| Check | Method |
|---|---|
| **Inverse relationships** | Correlate `shap_cpi_inflation` with `cpi_inflation`. Flag if negative (inflation reducing predicted stability). |
| **TargetEncoder leakage** | Document that uniform encoding (93.322 for all) means `sale_event_label` SHAP variance is noise, not signal. |
| **Proxy feature dilution** | Compute pairwise Pearson correlation between `multiplier`, `k`, `D_months`, `import_lambda`. Flag collinear pairs (r > 0.8). |
| **Leakage candidates** | Flag `predicted_stability_score` if it leaks into SHAP features (it shouldn't — it's not in the feature set). |

Output a concrete refinement plan.

---

### Phase 5: Documentation

#### [NEW] [XAI_Architecture_and_Audit.md](file:///c:/Users/mohan/OneDrive/Desktop/forecast+shap/XAI_Architecture_and_Audit.md)

Sections:
1. **Merge Mechanics** — join type, keys, row integrity assertion, NaN handling.
2. **XAI Math** — exact scaling formula, per-row multiplier distribution.
3. **TargetEncoder Re-mapping** — sample table showing original labels → encoded values → SHAP column names.
4. **System Vulnerabilities & Refinements** — Phase 4 findings with severity ratings.
5. **Final Schema** — column listing of the enriched parquet (Phase 6).

---

### Phase 6: Batch XAI Enrichment

**Action 6.1**: Compute SHAP for ALL 678,410 rows. For each row, use the tier-appropriate background dataset (low vs. high `compute_potential`).

**Action 6.2**: Apply `g(φ)` globally.

**Action 6.3**: Prefix all SHAP columns with `shap_`. Add `shap_base_expected_price` (the SHAP expected value / base value).

**Action 6.4**: Horizontal concat: `df_stability` (23 cols) + `price_t_plus_14` (1 col) + SHAP columns (16 features + 1 base = 17 cols) = **41 columns**.

**Action 6.5**: Export as `Dataset_Pipeline_Final_XAI.parquet` with snappy compression. Document schema width and file size.

---

## Verification Plan

### Automated Checks (in-script assertions)
- `assert len(df_merged) == 678_410` — row preservation after merge
- `assert df_merged['price_t_plus_14'].notna().all()` — no NaN after forward-fill
- `assert shap_df.shape[0] == 678_410` — SHAP row count matches
- `sum(shap_values, axis=1) + expected_value ≈ model_prediction` — SHAP additivity check
- Parquet round-trip: reload and assert identical shape

### Manual Verification
- Inspect top-5 SHAP features for economic plausibility
- Verify `XAI_Architecture_and_Audit.md` is complete and internally consistent
