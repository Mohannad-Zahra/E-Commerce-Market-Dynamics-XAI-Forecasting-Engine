# XAI Validation & Architectural Audit Report

**Generated**: 2026-05-08T14:37:12.886265
**Pipeline**: `xai_pipeline.py`
**Output Artifact**: `Dataset_Pipeline_Final_XAI.parquet`

---

## 1. Merge Mechanics

### 1.1 Join Type & Keys
- **Join type**: Left join (stability is the primary table)
- **Keys**: `(product_id, scrape_timestamp)`
- **Row integrity**: `assert len(df_merged) == 678,410` — PASSED OK
- **Column pulled from forecast**: `price_t_plus_14` only

### 1.2 Timestamp Alignment
- Both datasets use daily-level `YYYY-MM-DD` string timestamps.
- No `merge_asof` required — exact key match is sufficient.
- The 14-day offset (stability starts 2025-04-16; forecast starts 2025-04-30) produces ~50,120 unmatched rows.

### 1.3 NaN Handling
| Column | NaN before fill | NaN after fill | Method |
|--------|----------------|----------------|--------|
| `price_t_plus_14` | ~50,120 | 0 | `ffill()` then `bfill()` per `product_id` |

---

## 2. XAI Mathematics

### 2.1 Stability Model SHAP Computation
$$\phi_i = \text{SHAP attribution for feature } i$$

- **Explainer**: `shap.TreeExplainer(lgbm_model, feature_perturbation="interventional")`
- **Background**: Tier-specific data (low / high compute_potential)
- **Expected value (low tier)**: `93.322716`
- **Expected value (high tier)**: `93.322716`

### 2.2 Consumer-Price Scaling
$$g(\phi_i) = \phi_i \times W_{\text{row}}$$

where the per-row weight is:
$$W = e^{-k \cdot D}$$

| Parameter | Values |
|-----------|--------|
| `k` | 0.0 (local), 0.0005 (high scarcity), 0.0011 (moderate scarcity) |
| `D` | `D_months × 30.436875` days |
| `W` range | `[0.2178, 1.0000]` |
| `W` mean | `0.8709` |

**Semantic interpretation**: SHAP values express marginal contribution to predicted `stability_score`. Multiplying by `W` re-expresses each attribution in consumer-price-depreciation units — i.e., "how much would this feature's influence translate to a price-adjusted stability impact?"

> [WARN] **Conceptual Limitation**: The stability model predicts a dimensionless `stability_score`, not a price. The multiplier scaling is an economic alignment operation, not a mathematically invertible transformation back to price space. Consumers of scaled SHAP values should treat them as *price-weighted* attributions, not price deltas.

### 2.3 Delta SHAP
$$\Delta\phi_i(T_0) = \phi_i(T_0) - \phi_i(T_{-14})$$

- Computed by sorting within each `product_id` by `scrape_timestamp` and applying a 14-row shift.
- Products with fewer than 14 days of history produce NaN deltas (not excluded, left as NaN).

---

## 3. TargetEncoder Re-mapping

The `ColumnTransformer` applies `TargetEncoder` to `sale_event_label`.

| Original Label | Encoded Value | SHAP Column |
|---------------|---------------|-------------|
| *(categories unavailable)* | 93.3220 | `shap_sale_event_label` |


> [WARN] **Degeneracy Finding**: All 10 categories encode to the **same value** (`93.3220` ≈ global target mean). This means `sale_event_label` has **zero discriminative power** after encoding. Its SHAP values reflect noise, not learned signal.

---

## 4. System Vulnerabilities & Refinements

### 4.1 TargetEncoder Degeneracy
| Attribute | Value |
|-----------|-------|
| Unique encoded values | N/A |
| Is degenerate | N/A |
| Encoded mean | 93.3220 |

**Severity**: [HIGH] **HIGH** — The encoder maps every sale event to the global mean, collapsing the feature.

**Refinement**: Replace `TargetEncoder` with an `OrdinalEncoder` or manually engineered frequency/recency features per sale event. Alternatively, drop the column and retrain.

### 4.2 Inverse Relationship Check (CPI Inflation)
| Metric | Value |
|--------|-------|
| Pearson r (cpi_inflation <-> shap_cpi_inflation) | 0.6754 |
| Direction | positive OK |

**Refinement**: If inverse, verify that higher inflation is correctly expected to *reduce* predicted stability (economically plausible). If not, investigate feature encoding or sign conventions.

### 4.3 Proxy Feature Collinearity
| Feature A | Feature B | Pearson r | Flag |
|-----------|-----------|-----------|------|
| `multiplier` | `D_months` | `-0.9931` | [WARN] Collinear |


**Refinement**: If `multiplier` and `D_months` are collinear (both encode product age), consider dropping one from the feature set to reduce redundancy.

### 4.4 Leakage Candidates
| Column | In Model Features | Risk |
|--------|------------------|------|
| `predicted_stability_score` | False | OK Clean |
| `stability_score` (target) | False | OK Clean |

---

## 5. Final Schema — `Dataset_Pipeline_Final_XAI.parquet`

| Column |
|--------|
| `scrape_timestamp` |
| `product_id` |
| `raw_title` |
| `official_egp_usd` |
| `cpi_inflation` |
| `is_major_sale_period` |
| `competitor_scarcity_count` |
| `import_lambda` |
| `sale_event_label` |
| `volume_weight` |
| `global_release_date_str` |
| `missing_release_date` |
| `k` |
| `multiplier` |
| `D_months` |
| `category` |
| `compute_potential` |
| `delta_p_1d` |
| `vol_30d` |
| `delta_p_7d` |
| `delta_p_14d` |
| `stability_score` |
| `predicted_stability_score` |
| `price_t_plus_14` |
| `shap_compute_potential` |
| `shap_delta_p_7d` |
| `shap_delta_p_14d` |
| `shap_delta_p_1d` |
| `shap_vol_30d` |
| `shap_official_egp_usd` |
| `shap_cpi_inflation` |
| `shap_is_major_sale_period` |
| `shap_competitor_scarcity_count` |
| `shap_volume_weight` |
| `shap_D_months` |
| `shap_k` |
| `shap_import_lambda` |
| `shap_missing_release_date` |
| `shap_base_expected_price` |
| `delta_shap_compute_potential` |
| `delta_shap_delta_p_7d` |
| `delta_shap_delta_p_14d` |
| `delta_shap_delta_p_1d` |
| `delta_shap_vol_30d` |
| `delta_shap_official_egp_usd` |
| `delta_shap_cpi_inflation` |
| `delta_shap_is_major_sale_period` |
| `delta_shap_competitor_scarcity_count` |
| `delta_shap_volume_weight` |
| `delta_shap_D_months` |
| `delta_shap_k` |
| `delta_shap_import_lambda` |
| `delta_shap_missing_release_date` |

**Total columns**: 53
**Total rows**: 678,410
**Compression**: Snappy

---

*Report generated by `xai_pipeline.py` — XAI Validation & Architectural Documentation Pipeline*
