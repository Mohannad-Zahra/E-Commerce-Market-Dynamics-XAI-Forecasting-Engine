"""
training/train.py
-----------------
Orchestrates the full training pipeline:

  1. Load & clean data         (data.loader)
  2. Engineer features          (features.engineer)
  3. Time-based split           (training.splitter)
  4. Prepare X / y matrices
  5. Train LightGBM             (model.lgbm_model)
  6. Evaluate vs naïve baseline (training.evaluator)
  7. Save artefacts

This module is also importable as a library from other scripts.
"""

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup (allows running as `python -m training.train` from src/)
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).resolve().parent.parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from data.loader import load_and_clean
from features.engineer import (
    LOG_RETURN_COL,
    build_features,
    get_categorical_feature_names,
    get_feature_columns,
)
from model.lgbm_model import ModelConfig, PriceForecastModel
from training.evaluator import (
    compare_reports,
    evaluate_model,
    evaluate_naive_baseline,
    evaluate_segments,
)
from training.splitter import time_based_split

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "prices.csv"
DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[2] / "artefacts" / "lgbm_model.txt"
DEFAULT_VAL_FRACTION = 0.15


# ---------------------------------------------------------------------------
# Pipeline entry point
# ---------------------------------------------------------------------------

def run_pipeline(
    data_path: str | Path = DEFAULT_DATA_PATH,
    model_save_path: str | Path = DEFAULT_MODEL_PATH,
    val_fraction: float = DEFAULT_VAL_FRACTION,
) -> dict:
    """Execute the complete ML pipeline end-to-end.

    Args:
        data_path: Path to prices.csv
        model_save_path: Where to persist the trained model
        val_fraction: Fraction of unique dates to use as validation

    Returns:
        Dictionary with trained model and metric reports.
    """
    # ------------------------------------------------------------------
    # 1. Load and clean
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 1: Loading and cleaning data")
    logger.info("=" * 60)
    clean_df = load_and_clean(data_path)

    # ------------------------------------------------------------------
    # 2. Feature engineering
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 2: Engineering features")
    logger.info("=" * 60)
    feat_df = build_features(clean_df)

    # ------------------------------------------------------------------
    # 3. Time-based split
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 3: Time-based split (val_fraction=%.0f%%)", val_fraction * 100)
    logger.info("=" * 60)
    split = time_based_split(feat_df, val_fraction=val_fraction)

    # ------------------------------------------------------------------
    # 4. Prepare feature / target matrices
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 4: Preparing X / y matrices")
    logger.info("=" * 60)
    feature_cols = get_feature_columns(feat_df)
    cat_features = get_categorical_feature_names(feat_df)

    logger.info("Feature columns (%d): %s", len(feature_cols), feature_cols)
    logger.info("Categorical features: %s", cat_features)

    X_train = split.train[feature_cols]
    y_train = split.train[LOG_RETURN_COL]

    X_val = split.val[feature_cols]
    y_val = split.val[LOG_RETURN_COL]

    logger.info("Train set: X=%s, y=%s", X_train.shape, y_train.shape)
    logger.info("Val   set: X=%s, y=%s", X_val.shape, y_val.shape)

    # ------------------------------------------------------------------
    # 4b. Compute sample weights (inverse price-tier frequency + volatility)
    # ------------------------------------------------------------------
    logger.info("Computing sample weights (tier rebalancing + volatility boost)...")
    sample_weights = _compute_sample_weights(split.train)

    # ------------------------------------------------------------------
    # 5. Train LightGBM
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 5: Training LightGBM")
    logger.info("=" * 60)
    config = ModelConfig(categorical_features=cat_features)
    model = PriceForecastModel(config=config)
    model.fit(X_train, y_train, X_val, y_val, sample_weights=sample_weights)

    # ------------------------------------------------------------------
    # 6. Evaluate on validation set
    # ------------------------------------------------------------------
    logger.info("=" * 60)
    logger.info("STEP 6: Evaluating on validation set")
    logger.info("=" * 60)

    # LightGBM model: predict price from log return
    lgbm_price_pred = model.predict_price(
        X=X_val,
        prev_prices=split.val["price_lag_1"],
    )
    lgbm_report = evaluate_model(
        y_true_price=split.val["price_egp"],
        y_pred_price=lgbm_price_pred,
        y_true_prev=split.val["price_lag_1"],
        model_name="LightGBM (Global)",
    )

    # Naïve baseline
    baseline_report = evaluate_naive_baseline(
        val_df=split.val,
        price_col="price_egp",
        lag1_col="price_lag_1",
    )

    # Side-by-side comparison
    comparison = compare_reports(lgbm_report, baseline_report)
    logger.info("\n%s\n%s", "=" * 60, comparison)

    # Feature importances (top 20)
    fi = model.feature_importance("gain").head(20)
    logger.info("\nTop 20 Feature Importances (by gain):\n%s", fi.to_string(index=False))

    # Segmented evaluation: per price tier and per price-movement regime
    seg_table = evaluate_segments(
        val_df=split.val,
        y_pred_price=lgbm_price_pred,
    )
    logger.info("\n%s", seg_table)

    # ------------------------------------------------------------------
    # 7. Persist model
    # ------------------------------------------------------------------
    save_path = Path(model_save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(save_path))
    logger.info("Pipeline complete. Model saved to %s", save_path)

    return {
        "model": model,
        "lgbm_report": lgbm_report,
        "baseline_report": baseline_report,
        "feature_importance": fi,
        "split": split,
    }


# ---------------------------------------------------------------------------
# Sample weight computation
# ---------------------------------------------------------------------------

def _compute_sample_weights(train_df: pd.DataFrame) -> np.ndarray:
    """Compute per-row sample weights for training.

    Two components are multiplied together:
      1. Inverse price-tier frequency — Ultra products are 2.5x rarer than
         Budget products, so they get 2.5x higher weight.  This prevents
         LightGBM from over-fitting cheap products.
      2. Volatility boost — rows where price_vol_30d is high (top quartile)
         get an additional 1.5x multiplier.  This forces the model to pay
         more attention to repricing events.

    Weights are L1-normalised to sum to len(train_df) so the effective
    learning rate is unchanged.
    """
    PRICE_TIERS = [
        (0,       20_000,  "budget"),
        (20_000,  50_000,  "mid"),
        (50_000,  100_000, "high"),
        (100_000, np.inf,  "ultra"),
    ]

    def _assign_tier(price: float) -> str:
        for lo, hi, label in PRICE_TIERS:
            if lo <= price < hi:
                return label
        return "ultra"

    tiers = train_df["price_egp"].apply(_assign_tier)
    tier_counts = tiers.value_counts()
    max_count   = tier_counts.max()

    # Component 1: inverse-frequency weight per tier
    tier_weight_map = (max_count / tier_counts).to_dict()
    w = tiers.map(tier_weight_map).values.astype(float)

    # Component 2: volatility boost (1.5x for top-quartile volatile rows)
    if "price_vol_30d" in train_df.columns:
        vol = train_df["price_vol_30d"].fillna(0).values.astype(float)
        q75 = np.nanpercentile(vol, 75)
        vol_boost = np.where(vol > q75, 1.5, 1.0)
        w = w * vol_boost

    # Normalise: sum of weights = n_rows (keeps effective n_samples constant)
    w = w / w.mean()

    logger.info(
        "Sample weights: tier counts %s | vol-boost rows: %d (%.1f%%)",
        dict(tier_counts),
        int((w > w.mean() * 1.2).sum()),
        (w > w.mean() * 1.2).mean() * 100,
    )
    return w


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Train global LightGBM price forecasting model")
    parser.add_argument(
        "--data", type=str,
        default=str(DEFAULT_DATA_PATH),
        help="Path to prices.csv",
    )
    parser.add_argument(
        "--model-out", type=str,
        default=str(DEFAULT_MODEL_PATH),
        help="Path to save the trained model",
    )
    parser.add_argument(
        "--val-fraction", type=float,
        default=DEFAULT_VAL_FRACTION,
        help="Fraction of dates to use as validation (default: 0.15)",
    )
    args = parser.parse_args()

    results = run_pipeline(
        data_path=args.data,
        model_save_path=args.model_out,
        val_fraction=args.val_fraction,
    )
    print("\n[OK] Training pipeline complete.")
    print(f"   MAE  (LightGBM) : {results['lgbm_report'].mae:>12,.2f} EGP")
    print(f"   MAE  (Naive)    : {results['baseline_report'].mae:>12,.2f} EGP")
