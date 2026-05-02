"""
training/backtester.py
----------------------
Implements rolling-origin backtesting for panel price data.

Strategy: Expanding Window (Recommended for this dataset)
  - The training set GROWS with each fold (never shrinks).
  - We shift the origin forward by `step_days` each fold.
  - Each fold evaluates on the next `horizon_days` of data.

Why expanding over sliding:
  - Electronics pricing has long-term dependencies (currency trends,
    seasonal patterns spanning months).  Sliding windows discard this signal.
  - LightGBM is fast enough that retraining on ever-larger data is feasible.

Diagram (H=horizon, S=step, 4 folds):

  |<---  TRAIN  --->|<-H->|
  |<---- TRAIN ---->|<-H->|
  |<----- TRAIN --->|<-H->|
  |<------ TRAIN -->|<-H->|
                     ^---- roll by S each time
"""

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import pandas as pd

_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from features.engineer import LOG_RETURN_COL, get_categorical_feature_names, get_feature_columns
from model.lgbm_model import ModelConfig, PriceForecastModel
from training.evaluator import MetricsReport, evaluate_model

logger = logging.getLogger(__name__)

ID_COL = "product_id"
TIME_COL = "timestamp"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FoldResult:
    fold_index: int
    train_end: pd.Timestamp
    val_start: pd.Timestamp
    val_end: pd.Timestamp
    n_train_rows: int
    n_val_rows: int
    n_train_products: int
    n_val_products: int
    report: MetricsReport


@dataclass
class BacktestResult:
    fold_results: list[FoldResult] = field(default_factory=list)
    summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    def print_summary(self) -> None:
        if self.summary.empty:
            print("No folds completed.")
            return
        print("\n" + "=" * 75)
        print("  ROLLING BACKTEST SUMMARY")
        print("=" * 75)
        print(f"  Folds evaluated : {len(self.fold_results)}")
        print(f"  {'Fold':<6} {'Train End':<12} {'Val Window':<23} "
              f"{'MAE':>10} {'RMSE':>10} {'DA':>7} {'Hit5':>7}")
        print(f"  {'-'*6} {'-'*12} {'-'*23} {'-'*10} {'-'*10} {'-'*7} {'-'*7}")
        for row in self.summary.itertuples():
            da   = f"{row.da:.1%}"   if hasattr(row, 'da')   and row.da   is not None else "N/A"
            hit5 = f"{row.hit5:.1%}" if hasattr(row, 'hit5') and row.hit5 is not None else "N/A"
            print(f"  {row.fold:<6} {str(row.train_end.date()):<12} "
                  f"{str(row.val_start.date())} -> {str(row.val_end.date())}  "
                  f"{row.mae:>10,.0f} {row.rmse:>10,.0f} {da:>7} {hit5:>7}")

        print(f"  {'':6} {'':12} {'MEAN':>24} "
              f"{self.summary['mae'].mean():>10,.0f} "
              f"{self.summary['rmse'].mean():>10,.0f}")
        print("=" * 75)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rolling_backtest(
    feat_df: pd.DataFrame,
    min_train_days: int = 60,
    horizon_days: int = 14,
    step_days: int = 14,
    max_folds: int | None = None,
) -> BacktestResult:
    """Execute rolling-origin backtesting on a feature-engineered DataFrame.

    Args:
        feat_df:        Feature-engineered DataFrame (output of build_features).
        min_train_days: Minimum number of days required in the training set
                        before we start the first fold.
        horizon_days:   How many days ahead each fold evaluates on.
        step_days:      How many days to roll the origin forward per fold.
        max_folds:      If set, stop after this many folds (useful for quick runs).

    Returns:
        BacktestResult containing per-fold FoldResult objects and a summary DataFrame.
    """
    result = BacktestResult()
    feature_cols = get_feature_columns(feat_df)
    cat_features = get_categorical_feature_names(feat_df)

    folds = list(_generate_fold_windows(
        df=feat_df,
        min_train_days=min_train_days,
        horizon_days=horizon_days,
        step_days=step_days,
    ))

    if max_folds is not None:
        folds = folds[:max_folds]

    logger.info(
        "Rolling backtest: %d folds | horizon=%d days | step=%d days",
        len(folds), horizon_days, step_days,
    )

    for fold_idx, (train_end, val_start, val_end) in enumerate(folds):
        logger.info(
            "Fold %d/%d  |  train: ..→%s  |  val: %s→%s",
            fold_idx + 1, len(folds),
            train_end.date(), val_start.date(), val_end.date(),
        )

        train_df = feat_df[feat_df[TIME_COL] < val_start].copy()
        val_df   = feat_df[
            (feat_df[TIME_COL] >= val_start) & (feat_df[TIME_COL] <= val_end)
        ].copy()

        if len(val_df) == 0:
            logger.warning("Fold %d: empty val set — skipping.", fold_idx + 1)
            continue

        X_train = train_df[feature_cols]
        y_train = train_df[LOG_RETURN_COL]
        X_val   = val_df[feature_cols]
        y_val   = val_df[LOG_RETURN_COL]

        # Train a fresh model per fold
        config = ModelConfig(categorical_features=cat_features)
        model  = PriceForecastModel(config=config)
        model.fit(X_train, y_train, X_val, y_val)

        # Recover EGP price predictions
        price_pred = model.predict_price(X_val, val_df["price_lag_1"])

        report = evaluate_model(
            y_true_price=val_df["price_egp"],
            y_pred_price=price_pred,
            y_true_prev=val_df["price_lag_1"],          # needed for DA, MASE
            model_name=f"Fold-{fold_idx + 1}",
        )

        fold_result = FoldResult(
            fold_index=fold_idx + 1,
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            n_train_rows=len(train_df),
            n_val_rows=len(val_df),
            n_train_products=train_df[ID_COL].nunique(),
            n_val_products=val_df[ID_COL].nunique(),
            report=report,
        )
        result.fold_results.append(fold_result)

    result.summary = _build_summary_df(result.fold_results)
    result.print_summary()
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _generate_fold_windows(
    df: pd.DataFrame,
    min_train_days: int,
    horizon_days: int,
    step_days: int,
) -> Iterator[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    """Yield (train_end, val_start, val_end) tuples for each fold."""
    all_dates = sorted(df[TIME_COL].unique())
    total_days = (all_dates[-1] - all_dates[0]).days

    if total_days < min_train_days + horizon_days:
        raise ValueError(
            f"Dataset spans only {total_days} days. Need at least "
            f"{min_train_days + horizon_days} days for one fold."
        )

    origin_date = all_dates[0] + pd.Timedelta(days=min_train_days)

    while True:
        val_start = origin_date
        val_end   = origin_date + pd.Timedelta(days=horizon_days - 1)
        train_end = origin_date - pd.Timedelta(days=1)

        if val_end > all_dates[-1]:
            break  # No more data for this fold

        yield (
            pd.Timestamp(train_end),
            pd.Timestamp(val_start),
            pd.Timestamp(val_end),
        )
        origin_date += pd.Timedelta(days=step_days)


def _build_summary_df(fold_results: list[FoldResult]) -> pd.DataFrame:
    rows = []
    for fr in fold_results:
        row = {
            "fold":        fr.fold_index,
            "train_end":   fr.train_end,
            "val_start":   fr.val_start,
            "val_end":     fr.val_end,
            "n_train":     fr.n_train_rows,
            "n_val":       fr.n_val_rows,
            "mae":         fr.report.mae,
            "rmse":        fr.report.rmse,
            "smape":       fr.report.smape,
            "mase":        fr.report.mase,
            "da":          fr.report.da,
            "hit5":        fr.report.hit5,
            "bias":        fr.report.bias,
            "p95_error":   fr.report.p95_error,
        }
        rows.append(row)
    return pd.DataFrame(rows)
