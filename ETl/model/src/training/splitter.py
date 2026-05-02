"""
training/splitter.py
--------------------
Implements a strict time-based train/validation split for panel data.

Key invariant: ALL training rows come from timestamps strictly earlier than
               ALL validation rows, per-product AND globally.

Why this matters:
  - A random split would contaminate the training set with future observations,
    creating temporal data leakage even if lag features appear correct.
  - We split at a fixed global cutoff date (configurable).
"""

import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)

ID_COL = "product_id"
TIME_COL = "timestamp"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SplitResult:
    train: pd.DataFrame
    val: pd.DataFrame
    cutoff_date: pd.Timestamp
    train_date_range: tuple[pd.Timestamp, pd.Timestamp]
    val_date_range: tuple[pd.Timestamp, pd.Timestamp]

    def summary(self) -> str:
        return (
            f"Split cutoff: {self.cutoff_date.date()}\n"
            f"  Train: {len(self.train):,} rows  "
            f"[{self.train_date_range[0].date()} → {self.train_date_range[1].date()}]\n"
            f"  Val:   {len(self.val):,} rows  "
            f"[{self.val_date_range[0].date()} → {self.val_date_range[1].date()}]"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def time_based_split(
    df: pd.DataFrame,
    val_fraction: float = 0.15,
) -> SplitResult:
    """Split the dataset chronologically using a global cutoff date.

    The cutoff is chosen so that the LAST `val_fraction` of unique dates
    form the validation set, and all earlier dates form the training set.

    Args:
        df: Feature-engineered DataFrame (must contain TIME_COL).
        val_fraction: Proportion of unique dates to reserve for validation.

    Returns:
        SplitResult with train/val DataFrames and metadata.
    """
    if not 0.0 < val_fraction < 1.0:
        raise ValueError(f"val_fraction must be in (0, 1), got {val_fraction}")

    sorted_dates = sorted(df[TIME_COL].unique())
    n_dates = len(sorted_dates)
    n_val_dates = max(1, int(np.ceil(n_dates * val_fraction)))
    cutoff_idx = n_dates - n_val_dates
    cutoff_date = pd.Timestamp(sorted_dates[cutoff_idx])

    train = df[df[TIME_COL] < cutoff_date].copy()
    val = df[df[TIME_COL] >= cutoff_date].copy()

    result = SplitResult(
        train=train,
        val=val,
        cutoff_date=cutoff_date,
        train_date_range=(train[TIME_COL].min(), train[TIME_COL].max()),
        val_date_range=(val[TIME_COL].min(), val[TIME_COL].max()),
    )

    # Leak guard: ensure zero temporal overlap
    assert train[TIME_COL].max() < val[TIME_COL].min(), (
        "LEAK DETECTED: training set contains dates >= validation start!"
    )

    logger.info("\n%s", result.summary())
    return result


# ---------------------------------------------------------------------------
# Numpy import needed by time_based_split
# ---------------------------------------------------------------------------
import numpy as np  # noqa: E402  (placed here to keep module header clean)
