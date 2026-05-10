"""
data/loader.py
--------------
Responsible for loading, cleaning, and validating the raw prices.csv dataset.

Steps:
  1. Load CSV
  2. Parse and normalize timestamps
  3. Deduplicate (keep latest scrape per product_id × timestamp)
  4. Normalize missing categoricals ("unknown" → NaN → proper category)
  5. Fix missing numerics with group-wise median
  6. Smooth transient price spikes with rolling-median IQR filter
     (sustained high prices are preserved — only single-day artefacts removed)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_COLUMNS_TO_DROP = ["scrape_timestamp", "raw_current_price", "raw_original_price",
                        "raw_title", "product_url"]
CATEGORICAL_COLS = ["retailer_id", "category", "sub_category", "brand", "cpu", "gpu"]
NUMERIC_COLS = ["ram_gb", "storage_gb"]
TARGET_COL = "price_egp"
ID_COL = "product_id"
TIME_COL = "timestamp"

# Rolling-median spike smoother parameters
# A price is flagged as a spike if it deviates from the local rolling median
# by more than SPIKE_IQR_MULTIPLIER x rolling IQR.  A spike is treated as
# TRANSIENT (noise) only when the price reverts to a non-outlier value within
# SPIKE_REVERSION_DAYS.  Sustained elevated prices are left untouched.
SMOOTHING_WINDOW = 7           # days for rolling median / IQR
SPIKE_IQR_MULTIPLIER = 3.0     # deviation threshold in IQR units
SPIKE_REVERSION_DAYS = 3       # look-ahead window for reversion check (extended from 1)
MIN_GROUP_SIZE_FOR_SMOOTHING = 5  # products with fewer rows are left as-is


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_and_clean(csv_path: str | Path) -> pd.DataFrame:
    """Full loading and cleaning pipeline.  Returns a clean, sorted DataFrame."""
    path = Path(csv_path)
    logger.info("Loading dataset from %s", path)

    df = _load_raw(path)
    df = _parse_timestamps(df)
    df = _deduplicate(df)
    df = _drop_leak_columns(df)
    df = _normalize_categoricals(df)
    df = _impute_numerics(df)
    df = _smooth_price_outliers(df)
    df = df.sort_values([ID_COL, TIME_COL]).reset_index(drop=True)

    logger.info(
        "Clean dataset: %d rows, %d unique products, date range %s → %s",
        len(df),
        df[ID_COL].nunique(),
        df[TIME_COL].min().date(),
        df[TIME_COL].max().date(),
    )
    return df


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _load_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        low_memory=False,
        dtype={
            "retailer_id": "str",
            "category": "str",
            "sub_category": "str",
            "brand": "str",
            "cpu": "str",
            "gpu": "str",
            "is_gaming": "Int8",   # nullable integer
        },
    )
    logger.info("Raw shape: %s", df.shape)
    return df


def _parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Parse both timestamp columns; keep only the daily-level timestamp."""
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    df["scrape_timestamp"] = pd.to_datetime(df["scrape_timestamp"], errors="coerce")

    # Drop rows where the key daily timestamp could not be parsed
    bad_ts = df[TIME_COL].isna().sum()
    if bad_ts > 0:
        logger.warning("Dropping %d rows with unparseable timestamp", bad_ts)
        df = df[df[TIME_COL].notna()]

    return df


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the latest scrape per (product_id, timestamp) pair."""
    before = len(df)
    df = (
        df
        .sort_values("scrape_timestamp", na_position="first")
        .drop_duplicates(subset=[ID_COL, TIME_COL], keep="last")
    )
    after = len(df)
    logger.info("Deduplication removed %d rows (%d → %d)", before - after, before, after)
    return df


def _drop_leak_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove columns that are direct representations of the target or identifiers
    with no predictive signal (raw string prices, urls, etc.)."""
    cols_to_drop = [c for c in RAW_COLUMNS_TO_DROP if c in df.columns]
    df = df.drop(columns=cols_to_drop)
    logger.info("Dropped leaky/irrelevant columns: %s", cols_to_drop)
    return df


def _normalize_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """Convert literal 'unknown' / 'nan' / '' to proper NaN,
    then cast to pandas Categorical for memory efficiency and LightGBM support."""
    UNKNOWN_STRINGS = {"unknown", "nan", "none", "n/a", "", "na"}

    for col in CATEGORICAL_COLS:
        if col not in df.columns:
            continue
        df[col] = df[col].astype(str).str.strip().str.lower()
        df[col] = df[col].replace(UNKNOWN_STRINGS, np.nan)
        # Fill NaN with a dedicated "missing" label so LightGBM can learn from it
        df[col] = df[col].fillna("__missing__")
        df[col] = df[col].astype("category")

    return df


def _impute_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """Impute missing numeric specs (ram_gb, storage_gb) using
    group-wise median: first by sub_category, then global median as fallback."""
    for col in NUMERIC_COLS:
        if col not in df.columns:
            continue

        df[col] = pd.to_numeric(df[col], errors="coerce")
        missing_before = df[col].isna().sum()

        if missing_before == 0:
            continue

        # Group-wise median by sub_category
        group_medians = df.groupby("sub_category", observed=True)[col].transform("median")
        df[col] = df[col].fillna(group_medians)

        # Remaining NaN → global median
        global_median = df[col].median()
        df[col] = df[col].fillna(global_median)

        logger.info(
            "Imputed %d missing values in '%s' (group-wise + global median)",
            missing_before, col,
        )
    return df


def _smooth_price_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Remove transient price spikes (noise) using a rolling-median IQR filter.

    Algorithm per product:
      1. Compute rolling median and rolling IQR over SMOOTHING_WINDOW days.
      2. Flag a row as a spike if:
           |price - rolling_median| > SPIKE_IQR_MULTIPLIER x rolling_IQR
      3. A spike is TRANSIENT (noise) if the price reverts to a non-outlier
         value within SPIKE_REVERSION_DAYS days.
         - Reversion means: at least one of the next N days is NOT also an
           outlier, indicating the anomalous price did not persist.
      4. Replace only transient-spike rows with the rolling median.

    Why 3-day reversion window:
      Scraping jobs often run on a daily cadence but with 1-2 day lag.
      A scraped placeholder price can persist for 2-3 days before the real
      price is captured again.  Extending from 1-day to 3-day catches these
      multi-day artefacts while still preserving genuine sustained repricing.

    Sustained elevated prices (e.g., ultra-high-end products priced at
    1,000,000 EGP for weeks) satisfy none of the reversion conditions
    and are left untouched.
    """
    def _smooth_group(g: pd.DataFrame) -> pd.Series:
        prices = g[TARGET_COL].copy()
        if len(prices) < MIN_GROUP_SIZE_FOR_SMOOTHING:
            return prices

        roll_med = prices.rolling(SMOOTHING_WINDOW, min_periods=1, center=False).median()
        roll_q75 = prices.rolling(SMOOTHING_WINDOW, min_periods=1, center=False).quantile(0.75)
        roll_q25 = prices.rolling(SMOOTHING_WINDOW, min_periods=1, center=False).quantile(0.25)
        # Guard against near-zero IQR on flat price series
        roll_iqr = (roll_q75 - roll_q25).clip(lower=prices.std() * 0.05)

        deviation = (prices - roll_med).abs()
        is_outlier = deviation > SPIKE_IQR_MULTIPLIER * roll_iqr

        # Reversion check: is ANY of the next SPIKE_REVERSION_DAYS days normal?
        # Build a boolean mask: True = that future day is NOT an outlier.
        # If at least one of days +1, +2, ..., +N is normal, the spike is transient.
        reverts_within_window = pd.Series(False, index=prices.index)
        for ahead in range(1, SPIKE_REVERSION_DAYS + 1):
            future_is_normal = ~is_outlier.shift(-ahead).fillna(value=True)
            reverts_within_window = reverts_within_window | future_is_normal

        is_transient_spike = is_outlier & reverts_within_window

        prices[is_transient_spike] = roll_med[is_transient_spike]
        return prices

    before_std = df[TARGET_COL].std()
    n_corrected = 0

    # Apply group-wise — must work row-by-row so we can count corrections
    corrected = df.groupby(ID_COL, observed=True, group_keys=False).apply(
        lambda g: g.assign(**{TARGET_COL: _smooth_group(g)}),
        include_groups=False,
    )
    n_corrected = (corrected[TARGET_COL] != df[TARGET_COL]).sum()
    df[TARGET_COL] = corrected[TARGET_COL].values

    after_std = df[TARGET_COL].std()
    logger.info(
        "Spike smoother: corrected %d transient outliers | price std %.1f -> %.1f EGP",
        n_corrected, before_std, after_std,
    )
    return df
