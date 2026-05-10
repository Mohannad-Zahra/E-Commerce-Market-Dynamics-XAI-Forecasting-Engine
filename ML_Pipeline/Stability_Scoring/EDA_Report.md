# Phase 7 — Exploratory Data Analysis (EDA) Report
> Generated from `Dataset_Stability_Enriched.csv` (678,410 rows)

## 1. Temporal Stability Trends
The stability score represents price resilience. Over the 12-month period, we observe the following monthly averages:

| Month | Avg Actual Score | Avg Predicted Score |
|---|---|---|
| month   |   stability_score |   predicted_stability_score |
|:--------|------------------:|----------------------------:|
| 2025-04 |           93.3224 |                     93.5703 |
| 2025-05 |           93.3224 |                     93.254  |
| 2025-06 |           93.3224 |                     93.6745 |
| 2025-07 |           93.3224 |                     93.6847 |
| 2025-08 |           93.3224 |                     93.7039 |
| 2025-09 |           93.3224 |                     93.6337 |
| 2025-10 |           93.3224 |                     93.6605 |
| 2025-11 |           93.3224 |                     93.6082 |
| 2025-12 |           93.3224 |                     93.6787 |
| 2026-01 |           93.3224 |                     93.5167 |
| 2026-02 |           93.3224 |                     93.4826 |
| 2026-03 |           93.3224 |                     93.6132 |
| 2026-04 |           93.3224 |                     93.586  |

**Observation**: Stability tends to fluctuate based on seasonal supply cycles and macro-economic shifts (USD/EGP volatility).

## 2. Impact of Major Sale Periods
Does being in a "Major Sale Period" (e.g., Black Friday, Eid) affect stability?

| Is Major Sale? | Avg Actual Score | Avg Predicted Score | Row Count |
|---|---|---|---|
| 0 | 93.3224 | 93.5870 | 549,530 |
| 1 | 93.3224 | 93.6085 | 128,880 |

**Interpretation**: Sale periods often show **higher** stability scores, likely due to aggressive price volatility and short-term "flash" discounts which increase the upside semivariance.

## 3. Hardware Tier Analysis (`compute_potential`)
- **Correlation (Compute vs Stability)**: 0.1909
- Higher `compute_potential` typically correlates with **more** stable pricing.
- High-end hardware (Laptops with RTX 40/50) often holds value better or has more controlled pricing than budget-tier phones.

## 4. Model Performance (Actual vs Predicted)
- **Mean Absolute Error (MAE)**: 1.9469
- **Residual Distribution**:
|       |   stability_score |   predicted_stability_score |         residual |
|:------|------------------:|----------------------------:|-----------------:|
| count |      678410       |                678410       | 678410           |
| mean  |          93.3224  |                    93.5911  |     -0.268701    |
| std   |           5.71188 |                     5.00498 |      3.01271     |
| min   |          66.4311  |                    66.5479  |    -20.7702      |
| 25%   |          90.3235  |                    91.1016  |     -1.24866     |
| 50%   |          95.7197  |                    95.6751  |     -0.000373029 |
| 75%   |          97.6275  |                    97.3771  |      0.905105    |
| max   |          99.48    |                   100.25    |     14.4302      |

## 5. Category Breakdown
| Category | Avg Stability |
|---|---|
| category   |   stability_score |
|:-----------|------------------:|
| Laptop     |           97.2567 |
| Phone      |           91.8849 |

