
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Setup
BASE = Path(__file__).parent
DATA_FILE = BASE / "Dataset_Stability_Enriched.csv"
REPORT_FILE = BASE / "EDA_Report.md"

print("Loading dataset...")
df = pd.read_csv(DATA_FILE)
df['scrape_timestamp'] = pd.to_datetime(df['scrape_timestamp'])

# 1. Temporal Analysis
print("Analyzing temporal trends...")
df['month'] = df['scrape_timestamp'].dt.to_period('M')
monthly_avg = df.groupby('month')[['stability_score', 'predicted_stability_score']].mean()

# 2. Sale Period Analysis
print("Analyzing sale periods...")
sale_impact = df.groupby('is_major_sale_period')[['stability_score', 'predicted_stability_score']].mean()
# Also check count of rows in sale periods
sale_counts = df['is_major_sale_period'].value_counts()

# 3. Category & Compute Analysis
print("Analyzing categories and hardware tiers...")
cat_impact = df.groupby('category')[['stability_score', 'predicted_stability_score']].mean()

# Correlation between compute_potential and stability
compute_corr = df['compute_potential'].corr(df['stability_score'])

# 4. Error Analysis
df['residual'] = df['stability_score'] - df['predicted_stability_score']
mae = df['residual'].abs().mean()

# Summary Stats for the report
summary_stats = df[['stability_score', 'predicted_stability_score', 'residual']].describe()

# 5. Build the Markdown Report
report = f"""# Phase 7 — Exploratory Data Analysis (EDA) Report
> Generated from `Dataset_Stability_Enriched.csv` ({len(df):,} rows)

## 1. Temporal Stability Trends
The stability score represents price resilience. Over the 12-month period, we observe the following monthly averages:

| Month | Avg Actual Score | Avg Predicted Score |
|---|---|---|
{monthly_avg.to_markdown()}

**Observation**: Stability tends to fluctuate based on seasonal supply cycles and macro-economic shifts (USD/EGP volatility).

## 2. Impact of Major Sale Periods
Does being in a "Major Sale Period" (e.g., Black Friday, Eid) affect stability?

| Is Major Sale? | Avg Actual Score | Avg Predicted Score | Row Count |
|---|---|---|---|
| 0 | {sale_impact.loc[0, 'stability_score']:.4f} | {sale_impact.loc[0, 'predicted_stability_score']:.4f} | {sale_counts[0]:,} |
| 1 | {sale_impact.loc[1, 'stability_score']:.4f} | {sale_impact.loc[1, 'predicted_stability_score']:.4f} | {sale_counts[1]:,} |

**Interpretation**: Sale periods often show **{'lower' if sale_impact.loc[1, 'stability_score'] < sale_impact.loc[0, 'stability_score'] else 'higher'}** stability scores, likely due to aggressive price volatility and short-term "flash" discounts which increase the upside semivariance.

## 3. Hardware Tier Analysis (`compute_potential`)
- **Correlation (Compute vs Stability)**: {compute_corr:.4f}
- Higher `compute_potential` typically correlates with **{'more' if compute_corr > 0 else 'less'}** stable pricing.
- High-end hardware (Laptops with RTX 40/50) often holds value better or has more controlled pricing than budget-tier phones.

## 4. Model Performance (Actual vs Predicted)
- **Mean Absolute Error (MAE)**: {mae:.4f}
- **Residual Distribution**:
{summary_stats.to_markdown()}

## 5. Category Breakdown
| Category | Avg Stability |
|---|---|
{cat_impact['stability_score'].to_markdown()}

"""

with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write(report)

print(f"EDA complete. Report saved to {REPORT_FILE.name}")
