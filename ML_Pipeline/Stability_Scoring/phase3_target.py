"""
phase3_target.py — Phase 3: Target Variable Generation (stability_score)
=========================================================================
Input:  features_engineered.parquet  (from phase1_2_features.py)
Output: features_with_target.parquet

Target synthesis method:
  1. Bin products into compute_potential deciles
  2. Per-decile OLS: P̂ = β₀ + β₁·EGP_USD + β₂·CPI → residuals R
  3. Per-product upside semivariance:
       μ_R = mean(R);  SV_upside = sqrt( mean( max(0, R-μ_R)² ) )
  4. Exponential scoring:
       λᵢ = 1.0 × (1 − 0.5 × import_λᵢ)
       Sᵢ = 100 × exp(−λᵢ × SV_upside_i)
  5. Broadcast one stability_score per product to all its rows
  6. Drop price_final, ols_residual, cp_decile (OLS helpers)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd
import numpy as np
from pathlib import Path

OUT_DIR  = Path(__file__).parent
IN_FILE  = OUT_DIR / "features_engineered.parquet"
OUT_FILE = OUT_DIR / "features_with_target.parquet"

print("=" * 62)
print("  PHASE 3: Target Variable Generation (stability_score)")
print("=" * 62)

# ── 1. Load ───────────────────────────────────────────────────────────────────
print("\n[1/5] Loading features_engineered.parquet …")
df = pd.read_parquet(IN_FILE)
print(f"      {len(df):,} rows × {len(df.columns)} cols")

for col in ("price_final", "official_egp_usd", "cpi_inflation", "import_lambda"):
    assert col in df.columns, f"Required column '{col}' missing!"

# ── 2. compute_potential deciles ──────────────────────────────────────────────
print("[2/5] Binning compute_potential into deciles …")
df["cp_decile"] = pd.qcut(
    df["compute_potential"], q=10, labels=False, duplicates="drop"
)
decile_counts = df["cp_decile"].value_counts().sort_index()
print(f"      Decile sizes:\n{decile_counts.to_string()}")

# ── 3. Per-decile OLS → residuals ─────────────────────────────────────────────
print("[3/5] Fitting per-decile OLS regressions …")
print("      Model: price_final = β₀ + β₁·EGP_USD + β₂·CPI")
df["ols_residual"] = np.nan

for decile, grp in df.groupby("cp_decile"):
    idx = grp.index
    X = np.column_stack([
        np.ones(len(grp)),
        grp["official_egp_usd"].values,
        grp["cpi_inflation"].values,
    ])
    y = grp["price_final"].values

    try:
        beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        y_hat = X @ beta
        residuals = y - y_hat
    except np.linalg.LinAlgError:
        # Fallback: demean
        residuals = y - y.mean()
        beta = [y.mean(), 0.0, 0.0]

    # Normalise residuals by decile mean price → dimensionless ratio
    # Without this, SV_upside is in raw EGP (thousands), causing exp(-λ*SV)→0
    decile_mean_price = np.abs(y).mean()
    if decile_mean_price > 0:
        residuals = residuals / decile_mean_price

    df.loc[idx, "ols_residual"] = residuals

    if int(decile) % 2 == 0:
        print(f"      Decile {int(decile):2d}: β=[{beta[0]:+.1f}, {beta[1]:+.4f}, "
              f"{beta[2]:+.4f}]  resid_std={residuals.std():.2f}")

residual_nan = df["ols_residual"].isna().sum()
if residual_nan:
    print(f"      ⚠ {residual_nan:,} residual NaNs — filling with 0")
    df["ols_residual"].fillna(0.0, inplace=True)

# ── 4. Per-product semivariance + stability score ──────────────────────────────
print("[4/5] Computing per-product stability scores …")

# Per-product import_lambda (product-level constant — take first value)
product_lambda = df.groupby("product_id")["import_lambda"].first()

records = {}
for pid, grp in df.groupby("product_id"):
    R    = grp["ols_residual"].values
    mu_R = R.mean()
    # Upside semivariance
    sv_upside = np.sqrt(np.mean(np.maximum(0.0, R - mu_R) ** 2))
    # Effective lambda
    lam_import = product_lambda.get(pid, 0.5)
    lam_i = 1.0 * (1.0 - 0.5 * lam_import)
    # Exponential score
    score = 100.0 * np.exp(-lam_i * sv_upside)
    records[pid] = float(np.clip(score, 0.0, 100.0))

score_series = pd.Series(records, name="stability_score")
score_series.index.name = "product_id"

# Broadcast to all rows
df = df.merge(score_series.reset_index(), on="product_id", how="left")

stats = df["stability_score"].describe()
print(f"      stability_score stats:\n{stats.round(4).to_string()}")
assert df["stability_score"].between(0, 100).all(), "Score out of [0, 100]!"
print(f"      ✓ All scores in [0, 100]")

# Distribution sanity
low  = (df.groupby("product_id")["stability_score"].first() < 50).sum()
high = (df.groupby("product_id")["stability_score"].first() >= 50).sum()
print(f"      Products with score < 50: {low:,}  |  ≥ 50: {high:,}")

# ── 5. Drop OLS helpers + price_final ─────────────────────────────────────────
print("[5/5] Dropping OLS helper columns and price_final …")
DROP = ["price_final", "ols_residual", "cp_decile"]
df.drop(columns=[c for c in DROP if c in df.columns], inplace=True)

df.to_parquet(OUT_FILE, index=False, engine="pyarrow")
print(f"      ✓ Saved {len(df):,} rows × {len(df.columns)} cols → {OUT_FILE}")
print(f"\n✓  Phase 3 complete.")
