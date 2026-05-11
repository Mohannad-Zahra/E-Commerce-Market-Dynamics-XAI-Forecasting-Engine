"""
features/engineer.py
--------------------
Transforms the clean DataFrame into a machine-learning-ready feature matrix.

All features are computed in a strict **forward-looking-safe** manner:
  - Lag and rolling features always use .shift(1) or higher, so t-features
    only see prices up to and including day t-1.
  - The target (log return) is derived from price_egp internally.

Feature groups:
  A. Dynamic (time-varying per product)
     - lag features:        price_lag_1, price_lag_3, price_lag_7
     - rolling features:    rolling_mean_7, rolling_std_7, rolling_max_14
     - volatility features: price_vol_30d, reprice_count_30d
     - jump features:       days_since_last_jump          [NEW]
     - spread features:     retailer_price_std, retailer_price_range,
                            retailer_price_spread_pct, n_retailers   [NEW]
  B. Static (per product)
     - ram_gb, storage_gb, is_gaming, brand, cpu, gpu, category, sub_category
  C. Calendar
     - day_of_week, month, is_weekend
  D. Lifecycle
     - days_since_first_seen

Target:
  - log_return = log(price_t) - log(price_{t-1})   [computed BEFORE dropping NaN rows]

Leakage policy:
  All dynamic features use .shift(1) or a date-lagged merge, so at time t
  the feature matrix contains ONLY information available up to t-1.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ID_COL = "product_id"
TIME_COL = "timestamp"
TARGET_COL = "price_egp"
LOG_RETURN_COL = "log_return"

LAG_WINDOWS = [1, 3, 7]
ROLLING_WINDOWS = {
    "rolling_mean_7": (7, "mean"),
    "rolling_std_7":  (7, "std"),
    "rolling_max_14": (14, "max"),
}

CATEGORICAL_FEATURES = ["retailer_id", "category", "sub_category", "brand", "cpu", "gpu"]
NUMERIC_STATIC_FEATURES = ["ram_gb", "storage_gb", "is_gaming"]
CALENDAR_FEATURES = ["day_of_week", "month", "is_weekend"]
LIFECYCLE_FEATURES = ["days_since_first_seen"]

# Volatility feature parameters
VOL_WINDOW = 30            # rolling std of log-returns (days)
REPRICE_THRESHOLD = 0.02   # >2% move counts as a repricing event
REPRICE_WINDOW = 30        # rolling count window (days)

# Jump lifecycle feature
JUMP_THRESHOLD = 0.02      # >2% move triggers the days_since_last_jump clock reset

# Cross-retailer spread feature
# The spread is computed on day t-1 and merged into day t (leakage-safe).
SPREAD_LAG_DAYS = 1        # number of days to lag the spread before merging


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Main entry point.  Returns a DataFrame ready for train/test split.

    Columns added:
      - all lag / rolling features
      - calendar features
      - lifecycle feature
      - log_return  (the TARGET)
    Rows with NaN in any feature column are dropped (necessary after lagging).
    """
    df = df.copy()
    df = df.sort_values([ID_COL, TIME_COL]).reset_index(drop=True)

    # Compute target BEFORE dropping rows so the price series is continuous
    df = _compute_log_return(df)

    # Dynamic features
    df = _add_lag_features(df)
    df = _add_rolling_features(df)
    df = _add_volatility_features(df)      # price_vol_30d, reprice_count_30d
    df = _add_days_since_last_jump(df)     # NEW: days_since_last_jump
    df = _add_cross_retailer_spread(df)    # NEW: retailer spread features

    # Static-like features
    df = _add_calendar_features(df)
    df = _add_lifecycle_features(df)

    # Drop rows that are missing any feature due to warm-up periods
    df = _drop_warmup_rows(df)

    logger.info(
        "Feature matrix: %d rows, %d columns (after dropping warm-up rows)",
        len(df), df.shape[1],
    )
    return df


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return ordered list of feature column names (excludes IDs and target)."""
    exclude = {ID_COL, TIME_COL, TARGET_COL, LOG_RETURN_COL}
    return [c for c in df.columns if c not in exclude]


def get_categorical_feature_names(df: pd.DataFrame) -> list[str]:
    """Return feature columns that are categorical type (for LightGBM)."""
    all_features = get_feature_columns(df)
    return [c for c in all_features if c in CATEGORICAL_FEATURES]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _compute_log_return(df: pd.DataFrame) -> pd.DataFrame:
    """Compute log return: log(P_t) - log(P_{t-1}) grouped by product_id.

    Using log returns instead of raw prices makes the target stationary and
    scale-invariant across price tiers.
    """
    df["log_price"] = np.log(df[TARGET_COL].clip(lower=1e-6))
    df[LOG_RETURN_COL] = df.groupby(ID_COL, observed=True)["log_price"].diff(1)
    df = df.drop(columns=["log_price"])
    return df


def _add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add lagged price_egp features, grouped per product_id."""
    for lag in LAG_WINDOWS:
        col_name = f"price_lag_{lag}"
        df[col_name] = (
            df.groupby(ID_COL, observed=True)[TARGET_COL]
            .shift(lag)
        )
        logger.debug("Added lag feature: %s", col_name)
    return df


def _add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add rolling statistics computed on the shifted price series.

    shift(1) before rolling ensures we never include the current price:
      rolling_mean_7[t] = mean(price[t-7 .. t-1])
    """
    shifted = df.groupby(ID_COL, observed=True)[TARGET_COL].shift(1)

    for col_name, (window, agg) in ROLLING_WINDOWS.items():
        df[col_name] = (
            shifted
            .groupby(df[ID_COL], observed=True)
            .transform(lambda s: s.rolling(window=window, min_periods=1).agg(agg))
        )
        logger.debug("Added rolling feature: %s (window=%d, agg=%s)", col_name, window, agg)
    return df


def _add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode calendar-based features from the timestamp."""
    df["day_of_week"] = df[TIME_COL].dt.dayofweek.astype("int8")   # 0=Mon, 6=Sun
    df["month"] = df[TIME_COL].dt.month.astype("int8")
    df["is_weekend"] = (df["day_of_week"] >= 5).astype("int8")
    return df


def _add_lifecycle_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute how many days since the product was first seen in the dataset."""
    first_seen = df.groupby(ID_COL, observed=True)[TIME_COL].transform("min")
    df["days_since_first_seen"] = (df[TIME_COL] - first_seen).dt.days.astype("int32")
    return df


def _drop_warmup_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows where core lag/rolling features are NaN (warm-up period).

    Only a subset of columns require non-null values.  Specifically:
      - price_lag_N    : must be non-null (need prior prices for prediction)
      - rolling_*      : must be non-null (requires price history window)
      - log_return     : must be non-null (the target; first row of each product is NaN)

    Columns that are allowed to be NaN (and are filled downstream):
      - retailer_price_std / _range / _spread_pct / n_retailers
        Single-retailer products have NaN spread by definition; this is
        valid information (spread=0 = monopoly).  Already filled in
        _add_cross_retailer_spread().
      - price_vol_30d  : NaN during the first 5 rows (min_periods=5)
        These remain but do not cause the row to be dropped.
    """
    # Columns that MUST be non-NaN for a valid training row
    required_cols = (
        [f"price_lag_{lag}" for lag in LAG_WINDOWS]
        + list(ROLLING_WINDOWS.keys())
        + [LOG_RETURN_COL]
    )
    # Keep only those that actually exist in the DataFrame
    required_cols = [c for c in required_cols if c in df.columns]

    before = len(df)
    df = df.dropna(subset=required_cols)
    after = len(df)
    logger.info(
        "Dropped %d warm-up / NaN rows (%d -> %d)",
        before - after, before, after,
    )
    return df
def _add_volatility_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add price volatility regime features per product_id.

    Both features are computed on the SHIFTED log-return series so that
    at time t, only information from t-1 and earlier is used (no leakage).

    price_vol_30d:
        Rolling standard deviation of log-returns over 30 days.

    reprice_count_30d:
        Number of days in the last 30 where |price_change| > 2%.
    """
    log_ret_shifted = (
        df.groupby(ID_COL, observed=True)[TARGET_COL]
        .transform(lambda s: np.log(s.clip(1e-6)).diff(1).shift(1))
    )

    df["price_vol_30d"] = (
        log_ret_shifted
        .groupby(df[ID_COL], observed=True)
        .transform(lambda s: s.rolling(VOL_WINDOW, min_periods=5).std())
    ).astype("float32")

    large_move = (log_ret_shifted.abs() > REPRICE_THRESHOLD).astype(float)
    df["reprice_count_30d"] = (
        large_move
        .groupby(df[ID_COL], observed=True)
        .transform(lambda s: s.rolling(REPRICE_WINDOW, min_periods=1).sum())
    ).astype("float32")

    logger.debug(
        "Added volatility features: price_vol_30d (window=%d), "
        "reprice_count_30d (window=%d, threshold=%.0f%%)",
        VOL_WINDOW, REPRICE_WINDOW, REPRICE_THRESHOLD * 100,
    )
    return df


def _add_days_since_last_jump(df: pd.DataFrame) -> pd.DataFrame:
    """Compute days elapsed since the last significant price change per product.

    Leakage safety:
        pct_change is shifted by 1 before the jump flag is set, so at time t
        the feature reflects the last jump that occurred on or before t-1.

    Algorithm:
        1. Compute |pct_change| shifted by 1 (past data only).
        2. Mark rows where |pct_change| > JUMP_THRESHOLD as jump events.
        3. Assign each row a running counter of consecutive non-jump days
           since the most recent jump.  Counter resets to 0 on jump days.

    Interpretation:
        - days_since_last_jump = 0  → price moved significantly yesterday
        - days_since_last_jump = 30 → price has been stable for 30 days
        ("coiled spring" effect: long stability increases repricing probability)
    """
    # Shifted pct change: at row t this reflects change from t-2 to t-1
    pct_ch_shifted = (
        df.groupby(ID_COL, observed=True)[TARGET_COL]
        .transform(lambda s: s.pct_change().abs().shift(1))
    )
    is_jump = (pct_ch_shifted > JUMP_THRESHOLD).fillna(False)

    # Cumulative jump counter per group: each jump increments the segment index.
    # Within each segment, cumcount() gives days elapsed since the last jump.
    jump_segment = (
        is_jump.astype(int)
        .groupby(df[ID_COL], observed=True)
        .cumsum()
    )
    df["days_since_last_jump"] = (
        df.groupby([ID_COL, jump_segment], observed=True)
        .cumcount()
        .astype("int32")
    )

    logger.debug(
        "Added days_since_last_jump (threshold=%.0f%%)",
        JUMP_THRESHOLD * 100,
    )
    return df


def _add_cross_retailer_spread(df: pd.DataFrame) -> pd.DataFrame:
    """Compute price dispersion across retailers for the same product on the same day.

    Leakage safety:
        Spread metrics are computed for day t-1 (SPREAD_LAG_DAYS=1) and then
        merged into day t.  This guarantees that at training time, the model
        only sees competitive pricing information that was available the day
        before the target price is observed.

    Features produced:
        retailer_price_std   : std of prices across retailers (EGP)
        retailer_price_range : max - min price across retailers (EGP)
        retailer_price_spread_pct : std / mean price (normalised, scale-free)
        n_retailers          : number of retailers carrying this product

    These features encode competitive market pressure:
        - Low std  → retailers are price-aligned; one cut can cascade
        - High std → idiosyncratic pricing; independent repricing
        - High n_retailers → more competitive product

    Note: products sold by only one retailer get spread=0 and range=0,
    which is informative (monopoly pricing behaviour).
    """
    if "retailer_id" not in df.columns:
        logger.warning("retailer_id not found; skipping cross_retailer_spread features.")
        return df

    # Compute spread on each (product_id, timestamp) day
    spread_raw = (
        df.groupby([ID_COL, TIME_COL], observed=True)[TARGET_COL]
        .agg(
            retailer_price_std="std",
            retailer_price_min="min",
            retailer_price_max="max",
            retailer_price_mean="mean",
            n_retailers="count",
        )
        .reset_index()
    )
    spread_raw["retailer_price_range"] = (
        spread_raw["retailer_price_max"] - spread_raw["retailer_price_min"]
    )
    spread_raw["retailer_price_spread_pct"] = (
        spread_raw["retailer_price_std"]
        / spread_raw["retailer_price_mean"].clip(lower=1)
    )

    # Lag the spread by SPREAD_LAG_DAYS: shift the join key forward in time
    # so that day-t's spread row corresponds to day-(t+1)'s features.
    spread_raw[TIME_COL] = spread_raw[TIME_COL] + pd.Timedelta(days=SPREAD_LAG_DAYS)

    spread_cols = [
        ID_COL, TIME_COL,
        "retailer_price_std",
        "retailer_price_range",
        "retailer_price_spread_pct",
        "n_retailers",
    ]
    df = df.merge(spread_raw[spread_cols], on=[ID_COL, TIME_COL], how="left")

    # Fill NaN with 0: products with only one retailer have no spread.
    # This is informative (monopoly pricing) and must NOT become a NaN drop.
    for col in ["retailer_price_std", "retailer_price_range", "retailer_price_spread_pct"]:
        df[col] = df[col].fillna(0).astype("float32")
    # n_retailers=1 for single-retailer products; use 1.0 as the safe default
    df["n_retailers"] = df["n_retailers"].fillna(1.0).astype("float32")

    logger.debug(
        "Added cross-retailer spread features (lag=%d day(s)): %s",
        SPREAD_LAG_DAYS,
        ["retailer_price_std", "retailer_price_range",
         "retailer_price_spread_pct", "n_retailers"],
    )
    return df
