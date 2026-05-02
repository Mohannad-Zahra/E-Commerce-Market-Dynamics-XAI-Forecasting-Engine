"""
training/evaluator.py
---------------------
Evaluation utilities: computes and reports all metrics for model and naïve baseline.

Metrics implemented:
  Core regression:
    - MAE   (Mean Absolute Error, EGP)           — scale-dependent, interpretable
    - RMSE  (Root Mean Squared Error, EGP)        — penalises large errors more

  Scale-independent:
    - SMAPE (Symmetric MAPE, %)                   — handles asymmetry in MAPE;
                                                    safe when actuals near 0
    - MASE  (Mean Absolute Scaled Error)           — scaled by in-sample naïve MAE;
                                                    MASE < 1 = beats naïve; gold
                                                    standard for TS benchmarking

  Directional:
    - DA    (Directional Accuracy, %)             — % of price movements predicted
                                                    in the correct direction;
                                                    critical for buy/sell decisions

  Business-calibrated:
    - Hit5  (Hit Rate at 5% tolerance, %)         — % of predictions within ±5% of
                                                    actual price
    - Hit10 (Hit Rate at 10% tolerance, %)        — wider tolerance variant

  Risk:
    - P95 Error (95th percentile |error|, EGP)    — worst-case scenario sizing
    - P99 Error (99th percentile |error|, EGP)    — tail risk

  Bias:
    - Bias  (Mean Signed Error, EGP)              — positive = systematically
                                                    over-predicting prices
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MetricsReport:
    name: str

    # Core regression
    mae: float
    rmse: float

    # Scale-independent
    smape: Optional[float] = None
    mase: Optional[float] = None

    # Directional
    da: Optional[float] = None       # Directional accuracy (0-1)

    # Business-calibrated
    hit5: Optional[float] = None     # Hit rate within 5% (0-1)
    hit10: Optional[float] = None    # Hit rate within 10% (0-1)

    # Risk
    p95_error: Optional[float] = None
    p99_error: Optional[float] = None

    # Bias
    bias: Optional[float] = None     # Mean signed error

    def __str__(self) -> str:
        lines = [
            f"\n[{self.name}]",
            f"  --- Core Regression ---",
            f"  MAE          : {self.mae:>12,.2f} EGP",
            f"  RMSE         : {self.rmse:>12,.2f} EGP",
        ]
        if self.smape is not None:
            lines.append(f"  --- Scale-Independent ---")
            lines.append(f"  SMAPE        : {self.smape:>11.3f}%")
        if self.mase is not None:
            lines.append(
                f"  MASE         : {self.mase:>12.4f}"
                f"  {'(beats naive)' if self.mase < 1 else '(worse than naive)'}"
            )
        if self.da is not None:
            lines.append(f"  --- Directional ---")
            lines.append(f"  Dir. Accuracy: {self.da:>11.1%}")
        if self.hit5 is not None:
            lines.append(f"  --- Business Tolerance ---")
            lines.append(f"  Hit Rate  5% : {self.hit5:>11.1%}")
        if self.hit10 is not None:
            lines.append(f"  Hit Rate 10% : {self.hit10:>11.1%}")
        if self.p95_error is not None:
            lines.append(f"  --- Risk (Tail Errors) ---")
            lines.append(f"  P95 |Error|  : {self.p95_error:>12,.2f} EGP")
        if self.p99_error is not None:
            lines.append(f"  P99 |Error|  : {self.p99_error:>12,.2f} EGP")
        if self.bias is not None:
            lines.append(f"  --- Bias ---")
            direction = "over-predicts" if self.bias > 0 else "under-predicts"
            lines.append(
                f"  Mean Bias    : {self.bias:>+12,.2f} EGP  ({direction})"
            )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "model":      self.name,
            "mae":        self.mae,
            "rmse":       self.rmse,
            "smape":      self.smape,
            "mase":       self.mase,
            "da":         self.da,
            "hit5":       self.hit5,
            "hit10":      self.hit10,
            "p95_error":  self.p95_error,
            "p99_error":  self.p99_error,
            "bias":       self.bias,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_model(
    y_true_price: pd.Series | np.ndarray,
    y_pred_price: np.ndarray,
    y_true_prev: Optional[pd.Series | np.ndarray] = None,
    model_name: str = "LightGBM",
) -> MetricsReport:
    """Compute all metrics against actual EGP prices.

    Args:
        y_true_price:  Actual prices at time t (EGP).
        y_pred_price:  Model-predicted prices at time t (EGP).
        y_true_prev:   Actual prices at time t-1 (EGP).  Required for
                       MASE and Directional Accuracy.  Corresponds to
                       `price_lag_1` in the feature matrix.
        model_name:    Label for the report.

    Returns:
        MetricsReport with all computed metrics.
    """
    y_true = np.asarray(y_true_price, dtype=float)
    y_pred = np.asarray(y_pred_price, dtype=float)
    y_prev = np.asarray(y_true_prev, dtype=float) if y_true_prev is not None else None

    abs_errors = np.abs(y_true - y_pred)

    report = MetricsReport(
        name=model_name,
        mae=float(abs_errors.mean()),
        rmse=float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        smape=_smape(y_true, y_pred),
        mase=_mase(y_true, y_pred, y_prev) if y_prev is not None else None,
        da=_directional_accuracy(y_true, y_pred, y_prev) if y_prev is not None else None,
        hit5=_hit_rate(y_true, y_pred, tolerance=0.05),
        hit10=_hit_rate(y_true, y_pred, tolerance=0.10),
        p95_error=float(np.percentile(abs_errors, 95)),
        p99_error=float(np.percentile(abs_errors, 99)),
        bias=float(np.mean(y_pred - y_true)),
    )

    logger.info("%s", report)
    return report


def evaluate_naive_baseline(
    val_df: pd.DataFrame,
    price_col: str = "price_egp",
    lag1_col: str = "price_lag_1",
    model_name: str = "Naive Baseline (y_t = y_{t-1})",
) -> MetricsReport:
    """Evaluate the naive baseline: predict price_t = price_{t-1}."""
    y_true = val_df[price_col].values.astype(float)
    y_naive = val_df[lag1_col].values.astype(float)
    return evaluate_model(
        y_true_price=y_true,
        y_pred_price=y_naive,
        y_true_prev=y_naive,      # for naive, prev IS the prediction
        model_name=model_name,
    )


def compare_reports(lgbm_report: MetricsReport, baseline_report: MetricsReport) -> str:
    """Format a side-by-side improvement table covering all metrics."""

    def _lift(model_val, base_val, higher_is_better=False):
        """Compute % improvement of model over baseline."""
        if base_val is None or model_val is None or base_val == 0:
            return "N/A"
        raw = (model_val - base_val) / abs(base_val) * 100
        # For metrics where higher = better (DA, hit rates), flip sign convention
        if higher_is_better:
            return f"{raw:>+.1f}%"
        return f"{-raw:>+.1f}%"

    rows = [
        ("Metric",       "LightGBM",                  "Naive",                     "vs Naive"),
        ("-" * 14,       "-" * 14,                    "-" * 14,                    "-" * 10),
        ("MAE (EGP)",    f"{lgbm_report.mae:,.0f}",   f"{baseline_report.mae:,.0f}",
         _lift(lgbm_report.mae, baseline_report.mae)),
        ("RMSE (EGP)",   f"{lgbm_report.rmse:,.0f}",  f"{baseline_report.rmse:,.0f}",
         _lift(lgbm_report.rmse, baseline_report.rmse)),
        ("SMAPE (%)",    f"{lgbm_report.smape:.3f}" if lgbm_report.smape else "N/A",
         f"{baseline_report.smape:.3f}" if baseline_report.smape else "N/A",
         _lift(lgbm_report.smape, baseline_report.smape)),
        ("MASE",         f"{lgbm_report.mase:.4f}" if lgbm_report.mase else "N/A",
         f"{baseline_report.mase:.4f}" if baseline_report.mase else "N/A",
         _lift(lgbm_report.mase, baseline_report.mase)),
        ("Dir. Acc.",    f"{lgbm_report.da:.1%}" if lgbm_report.da else "N/A",
         f"{baseline_report.da:.1%}" if baseline_report.da else "N/A",
         _lift(lgbm_report.da, baseline_report.da, higher_is_better=True)),
        ("Hit@5%",       f"{lgbm_report.hit5:.1%}" if lgbm_report.hit5 else "N/A",
         f"{baseline_report.hit5:.1%}" if baseline_report.hit5 else "N/A",
         _lift(lgbm_report.hit5, baseline_report.hit5, higher_is_better=True)),
        ("Hit@10%",      f"{lgbm_report.hit10:.1%}" if lgbm_report.hit10 else "N/A",
         f"{baseline_report.hit10:.1%}" if baseline_report.hit10 else "N/A",
         _lift(lgbm_report.hit10, baseline_report.hit10, higher_is_better=True)),
        ("P95 Err (EGP)", f"{lgbm_report.p95_error:,.0f}" if lgbm_report.p95_error else "N/A",
         f"{baseline_report.p95_error:,.0f}" if baseline_report.p95_error else "N/A",
         _lift(lgbm_report.p95_error, baseline_report.p95_error)),
        ("Bias (EGP)",   f"{lgbm_report.bias:+,.0f}" if lgbm_report.bias else "N/A",
         f"{baseline_report.bias:+,.0f}" if baseline_report.bias else "N/A",
         "N/A"),
    ]

    header = f"\n{'=' * 60}\n  FULL METRICS COMPARISON\n{'=' * 60}"
    col_w = [16, 14, 14, 10]
    table_rows = [
        "  " + "".join(f"{cell:<{w}}" for cell, w in zip(row, col_w))
        for row in rows
    ]
    return header + "\n" + "\n".join(table_rows) + "\n" + "=" * 60


# ---------------------------------------------------------------------------
# Metric implementations
# ---------------------------------------------------------------------------

def _smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Symmetric Mean Absolute Percentage Error.

    SMAPE = mean(2 * |y_t - y_hat_t| / (|y_t| + |y_hat_t|)) * 100

    Unlike MAPE, SMAPE is symmetric — it penalises under- and over-prediction
    equally.  Safe when actuals approach zero (denominator uses sum of both).
    """
    denom = np.abs(y_true) + np.abs(y_pred)
    mask = denom > 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(2.0 * np.abs(y_true[mask] - y_pred[mask]) / denom[mask]) * 100)


def _mase(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prev: np.ndarray,
) -> Optional[float]:
    """Mean Absolute Scaled Error.

    MASE = MAE(model) / MAE(naive)

    Where naive MAE = mean(|y_t - y_{t-1}|) computed on the validation set.
    MASE < 1 → model beats naive.  MASE > 1 → naive is better.

    This is the gold-standard metric for time series benchmarking because it:
    - Is scale-independent (safe to average across products with different price levels)
    - Has a meaningful absolute reference (1.0 = naïve performance)
    """
    naive_errors = np.abs(y_true - y_prev)
    naive_mae = naive_errors.mean()
    if naive_mae == 0:
        return None
    model_mae = np.abs(y_true - y_pred).mean()
    return float(model_mae / naive_mae)


def _directional_accuracy(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_prev: np.ndarray,
    min_move_pct: float = 0.005,
) -> float:
    """Directional Accuracy (DA).

    DA = % of timesteps where model correctly predicts direction of price change.

    Only evaluated on rows where the actual price MOVED by at least `min_move_pct`
    (0.5% by default).  This filters out flat-price rows where directional
    prediction is trivially correct (predict no change) and thus inflated.

    For buy/sell/hold decision systems, this is often more business-relevant
    than MAE.
    """
    actual_direction = np.sign(y_true - y_prev)
    pred_direction   = np.sign(y_pred  - y_prev)

    # Only count rows with meaningful actual movement
    actual_pct_change = np.abs((y_true - y_prev) / np.clip(np.abs(y_prev), 1e-6, None))
    mask = actual_pct_change >= min_move_pct

    if mask.sum() == 0:
        return 0.0
    return float((actual_direction[mask] == pred_direction[mask]).mean())


def _hit_rate(y_true: np.ndarray, y_pred: np.ndarray, tolerance: float) -> float:
    """Hit Rate at tolerance: fraction of predictions within ±tolerance of actual.

    Example: tolerance=0.05 → what % of predictions are within ±5% of actual price?

    This is a critical business metric: a retailer only cares whether the
    predicted price is "close enough" to make a correct competitive decision,
    not the exact EGP error.
    """
    pct_error = np.abs(y_pred - y_true) / np.clip(np.abs(y_true), 1e-6, None)
    return float((pct_error <= tolerance).mean())


# ---------------------------------------------------------------------------
# Segmented evaluation (per price tier + per price-movement regime)
# ---------------------------------------------------------------------------

_PRICE_TIERS = [
    (0,        20_000,  "Budget   (<20k)"),
    (20_000,   50_000,  "Mid    (20-50k)"),
    (50_000,   100_000, "High  (50-100k)"),
    (100_000,  np.inf,  "Ultra   (>100k)"),
]


def evaluate_segments(
    val_df: pd.DataFrame,
    y_pred_price: np.ndarray,
    price_col: str = "price_egp",
    lag1_col: str = "price_lag_1",
) -> str:
    """Compute MAE, RMSE, MASE, Hit@5% broken down by price tier and price regime.

    Args:
        val_df:        Validation DataFrame (must contain price_col and lag1_col).
        y_pred_price:  Predicted EGP prices (same row order as val_df).
        price_col:     Column name for actual prices.
        lag1_col:      Column name for lagged prices (t-1).

    Returns:
        A formatted multi-line string table suitable for logging.
    """
    y_true = val_df[price_col].values.astype(float)
    y_prev = val_df[lag1_col].values.astype(float)
    y_pred = np.asarray(y_pred_price, dtype=float)

    lines = []
    SEP   = "=" * 72
    SEP2  = "-" * 72
    HDR   = f"  {'Segment':<22} {'n':>7} {'MAE':>10} {'RMSE':>10} {'MASE':>7} {'Hit@5%':>8}"

    # ── BY PRICE TIER ──────────────────────────────────────────────────────
    lines += ["\n" + SEP, "  SEGMENTED EVALUATION — BY PRICE TIER", SEP2, HDR, SEP2]

    for lo, hi, label in _PRICE_TIERS:
        mask = (y_true >= lo) & (y_true < hi)
        if mask.sum() == 0:
            continue
        yt, yp, ypr = y_true[mask], y_pred[mask], y_prev[mask]
        ae   = np.abs(yt - yp)
        mae  = ae.mean()
        rmse = np.sqrt(((yt - yp) ** 2).mean())
        naive_mae = np.abs(yt - ypr).mean()
        mase = mae / naive_mae if naive_mae > 0 else float("nan")
        hit5 = (ae / np.clip(np.abs(yt), 1e-6, None) <= 0.05).mean()
        lines.append(
            f"  {label:<22} {mask.sum():>7,} {mae:>10,.0f} {rmse:>10,.0f} "
            f"{mase:>7.3f} {hit5:>7.1%}"
        )

    lines += [SEP2]

    # Aggregate (all tiers)
    ae_all   = np.abs(y_true - y_pred)
    mae_all  = ae_all.mean()
    rmse_all = np.sqrt(((y_true - y_pred) ** 2).mean())
    naive_mae_all = np.abs(y_true - y_prev).mean()
    mase_all = mae_all / naive_mae_all if naive_mae_all > 0 else float("nan")
    hit5_all = (ae_all / np.clip(np.abs(y_true), 1e-6, None) <= 0.05).mean()
    lines.append(
        f"  {'OVERALL':<22} {len(y_true):>7,} {mae_all:>10,.0f} {rmse_all:>10,.0f} "
        f"{mase_all:>7.3f} {hit5_all:>7.1%}"
    )

    # ── BY PRICE REGIME ────────────────────────────────────────────────────
    lines += ["\n" + SEP, "  SEGMENTED EVALUATION — BY PRICE MOVEMENT REGIME", SEP2, HDR, SEP2]

    pct_change = np.abs((y_true - y_prev) / np.clip(np.abs(y_prev), 1e-6, None))
    regimes = [
        ("Static  (<=1% move)", pct_change <= 0.01),
        ("Moving  ( 1-10% )  ", (pct_change > 0.01) & (pct_change <= 0.10)),
        ("Large   (>10% move)", pct_change > 0.10),
    ]

    for label, mask in regimes:
        if mask.sum() == 0:
            continue
        yt, yp, ypr = y_true[mask], y_pred[mask], y_prev[mask]
        ae   = np.abs(yt - yp)
        mae  = ae.mean()
        rmse = np.sqrt(((yt - yp) ** 2).mean())
        naive_mae = np.abs(yt - ypr).mean()
        mase = mae / naive_mae if naive_mae > 0 else float("nan")
        hit5 = (ae / np.clip(np.abs(yt), 1e-6, None) <= 0.05).mean()
        lines.append(
            f"  {label:<22} {mask.sum():>7,} {mae:>10,.0f} {rmse:>10,.0f} "
            f"{mase:>7.3f} {hit5:>7.1%}"
        )

    lines += [SEP2]
    lines.append(
        f"  {'OVERALL':<22} {len(y_true):>7,} {mae_all:>10,.0f} {rmse_all:>10,.0f} "
        f"{mase_all:>7.3f} {hit5_all:>7.1%}"
    )
    lines.append(SEP)

    return "\n".join(lines)

