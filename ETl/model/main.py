#!/usr/bin/env python
"""
main.py
-------
Top-level entry point for the electronics price forecasting pipeline.

Usage:
    python main.py
    python main.py --data prices.csv --val-fraction 0.15 --model-out artefacts/lgbm_model.txt

This script sets up logging, validates paths, and delegates to the
training pipeline defined in src/training/train.py.
"""

import argparse
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is on the Python path
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from training.train import run_pipeline  # noqa: E402


# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

def _setup_logging(level: str = "INFO") -> None:
    import io
    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    handler = logging.StreamHandler(utf8_stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Global LightGBM price forecasting pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data",
        type=str,
        default=str(_ROOT / "prices.csv"),
        help="Path to the raw prices.csv dataset",
    )
    parser.add_argument(
        "--model-out",
        type=str,
        default=str(_ROOT / "artefacts" / "lgbm_model.txt"),
        help="File path to save the trained LightGBM model",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.15,
        help="Fraction of unique dates reserved for validation",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()
    _setup_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("  Electronics Price Forecasting - LightGBM Pipeline")
    logger.info("=" * 60)
    logger.info("Data      : %s", args.data)
    logger.info("Model out : %s", args.model_out)
    logger.info("Val frac  : %.0f%%", args.val_fraction * 100)

    # Validate input
    data_path = Path(args.data)
    if not data_path.exists():
        logger.error("Dataset not found at: %s", data_path)
        sys.exit(1)

    # Run pipeline
    results = run_pipeline(
        data_path=data_path,
        model_save_path=args.model_out,
        val_fraction=args.val_fraction,
    )

    # Final summary
    lgbm = results["lgbm_report"]
    naive = results["baseline_report"]

    print("\n" + "=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    print(f"  {'Metric':<8}  {'LightGBM':>12}  {'Naïve':>12}  {'Improvement':>12}")
    print(f"  {'-'*8}  {'-'*12}  {'-'*12}  {'-'*12}")

    mae_imp = (naive.mae - lgbm.mae) / naive.mae * 100
    rmse_imp = (naive.rmse - lgbm.rmse) / naive.rmse * 100

    print(f"  {'MAE':<8}  {lgbm.mae:>12,.0f}  {naive.mae:>12,.0f}  {mae_imp:>+11.1f}%")
    print(f"  {'RMSE':<8}  {lgbm.rmse:>12,.0f}  {naive.rmse:>12,.0f}  {rmse_imp:>+11.1f}%")
    print("=" * 60)
    print(f"\n[OK] Model saved to: {args.model_out}\n")


if __name__ == "__main__":
    main()
