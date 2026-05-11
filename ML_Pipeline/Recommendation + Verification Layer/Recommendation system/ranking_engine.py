"""
ranking_engine.py
=================
Loads raw data from both CSVs, merges them, computes the R_score ranking
formula using NumPy vectorisation, and returns a ranked DataFrame of the
latest data-point per product.

R_score formula
---------------
R_score = alpha_L * ((P_forecast - P_current) / P_current)   # price momentum
         + beta_L  * (100 - volatility)                       # stability yield
         + gamma_L * ((mu_14d - P_current) / mu_14d)          # discount depth
         - delta_L * months_since_release                     # obsolescence penalty
"""

import os
import warnings
from typing import Optional, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths – resolve relative to this file so the script can be run from anywhere
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_DIR, "data")

PROCESSED_CSV = os.path.join(DATA_DIR, "Dataset_Pipeline_Processed.csv")
XAI_CSV = os.path.join(DATA_DIR, "ECom_Forecast_XAI_data.csv")

# Default R_score hyper-parameters (match the notebook)
DEFAULT_ALPHA = 20.0
DEFAULT_BETA = 1.0
DEFAULT_GAMMA = 1.0
DEFAULT_DELTA = 0.5


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_r_score(
    df: pd.DataFrame,
    alpha_L: float = DEFAULT_ALPHA,
    beta_L: float = DEFAULT_BETA,
    gamma_L: float = DEFAULT_GAMMA,
    delta_L: float = DEFAULT_DELTA,
) -> np.ndarray:
    """
    Vectorised R_score computation.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: current_price, forecasted_price,
        volatility_score, price_14d_avg, months_since_release.
    alpha_L, beta_L, gamma_L, delta_L : float
        Weighting coefficients.

    Returns
    -------
    np.ndarray  –  R_score per row.
    """
    p_t = df["current_price"].values
    p_t_14 = df["forecasted_price"].values
    v = df["volatility_score"].values
    mu_14d = df["price_14d_avg"].values
    m_age = df["months_since_release"].values

    # 1. Price Momentum
    momentum = (p_t_14 - p_t) / p_t
    term1 = alpha_L * momentum

    # 2. Stability Yield  (stability = 100 – volatility)
    term2 = beta_L * (100 - v)

    # 3. Discount Depth
    discount = (mu_14d - p_t) / mu_14d
    term3 = gamma_L * discount

    # 4. Obsolescence Penalty
    term4 = delta_L * m_age

    return term1 + term2 + term3 - term4


# ---------------------------------------------------------------------------
# Data loading & merging
# ---------------------------------------------------------------------------

def load_data(
    processed_csv: str = PROCESSED_CSV,
    xai_csv: str = XAI_CSV,
) -> pd.DataFrame:
    """
    Loads, merges, and pre-processes both source CSVs.

    Returns a DataFrame with unified column names ready for scoring.
    """
    processed_cols = ["scrape_timestamp", "product_id", "base_price_egp", "price_14d_avg", "D_months"]
    xai_cols = ["scrape_timestamp", "product_id", "predicted_stability_score", "price_t_plus_14"]

    df_prices = pd.read_csv(processed_csv, usecols=processed_cols)
    df_xai = pd.read_csv(xai_csv, usecols=xai_cols)

    df = pd.merge(df_prices, df_xai, on=["product_id", "scrape_timestamp"])
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"])
    df = df.sort_values(["product_id", "scrape_timestamp"])

    # Rename / derive columns to match R_score expectations
    df["current_price"] = df["base_price_egp"]
    df["forecasted_price"] = df["price_t_plus_14"]
    df["volatility_score"] = 100 - df["predicted_stability_score"]
    df["months_since_release"] = df["D_months"]

    return df


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def get_ranked_laptops(
    processed_csv: str = PROCESSED_CSV,
    xai_csv: str = XAI_CSV,
    alpha_L: float = DEFAULT_ALPHA,
    beta_L: float = DEFAULT_BETA,
    gamma_L: float = DEFAULT_GAMMA,
    delta_L: float = DEFAULT_DELTA,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full ranking flow:
      1. Load & merge data.
      2. Keep only the latest snapshot per product.
      3. Compute R_score.
      4. Return (latest_data_all, ranked_top_candidates).

    Returns
    -------
    full_latest : pd.DataFrame
        Latest snapshot for every product (used as background for SHAP).
    ranked : pd.DataFrame
        `full_latest` sorted descending by r_score.
    """
    df = load_data(processed_csv, xai_csv)

    # One row per product – take the most recent scrape
    latest_data = df.groupby("product_id").tail(1).copy()

    latest_data["r_score"] = calculate_r_score(
        latest_data, alpha_L=alpha_L, beta_L=beta_L, gamma_L=gamma_L, delta_L=delta_L
    )

    ranked = latest_data.sort_values("r_score", ascending=False)

    return latest_data, ranked
