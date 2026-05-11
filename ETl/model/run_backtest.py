#!/usr/bin/env python
"""
run_backtest.py
---------------
Standalone CLI script to run rolling-origin backtesting.

Usage:
    python run_backtest.py
    python run_backtest.py --data prices.csv --folds 5 --horizon 14 --step 14

The backtester re-trains LightGBM from scratch for each fold using an
expanding training window, then evaluates on the held-out horizon window.
This simulates the real production scenario where the model is retrained
periodically (e.g., weekly) and evaluated on the next 2 weeks.
"""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SRC  = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from data.loader import load_and_clean
from features.engineer import build_features
from training.backtester import rolling_backtest


def main():
    import argparse
    import io

    utf8_out = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(utf8_out)],
    )
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Rolling backtest for price forecasting")
    parser.add_argument("--data",     default=str(_ROOT / "prices.csv"))
    parser.add_argument("--folds",    type=int,   default=5,  help="Max number of folds")
    parser.add_argument("--horizon",  type=int,   default=14, help="Val window days")
    parser.add_argument("--step",     type=int,   default=14, help="Roll-forward days")
    parser.add_argument("--min-train",type=int,   default=60, help="Min training days")
    args = parser.parse_args()

    logger.info("Loading and cleaning data from: %s", args.data)
    clean_df = load_and_clean(args.data)

    logger.info("Engineering features...")
    feat_df = build_features(clean_df)

    logger.info(
        "Starting rolling backtest: max_folds=%d, horizon=%d days, step=%d days",
        args.folds, args.horizon, args.step,
    )
    result = rolling_backtest(
        feat_df=feat_df,
        min_train_days=args.min_train,
        horizon_days=args.horizon,
        step_days=args.step,
        max_folds=args.folds,
    )

    # Print aggregate stats
    if not result.summary.empty:
        s = result.summary
        print(f"\n{'='*55}")
        print(f"  AGGREGATE BACKTEST STATS  ({len(s)} folds)")
        print(f"{'='*55}")
        for metric in ["mae", "rmse", "smape", "mase", "da", "hit5"]:
            if metric in s.columns and s[metric].notna().any():
                print(f"  {metric.upper():<10}  mean={s[metric].mean():.4f}  "
                      f"std={s[metric].std():.4f}  "
                      f"min={s[metric].min():.4f}  "
                      f"max={s[metric].max():.4f}")
        print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
