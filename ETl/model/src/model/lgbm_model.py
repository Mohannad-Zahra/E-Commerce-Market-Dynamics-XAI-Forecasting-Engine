"""
model/lgbm_model.py
-------------------
Thin, production-ready wrapper around LightGBM for panel price forecasting.

Responsibilities:
  - Configure the LightGBM regressor with sensible production defaults
  - Train with early stopping on a validation set
  - Predict log returns and invert them to get EGP prices
  - Expose a clean fit / predict / predict_price interface
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default hyperparameters (can be overridden via config)
# ---------------------------------------------------------------------------

DEFAULT_PARAMS: dict = {
    "objective": "regression_l1",   # MAE-optimised (robust to residual outliers)
    "metric": "mae",
    "boosting_type": "gbdt",
    "num_leaves": 127,
    "max_depth": -1,
    "learning_rate": 0.05,
    "n_estimators": 2000,           # upper bound; early stopping used
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.1,               # L1
    "reg_lambda": 0.1,              # L2
    "verbose": -1,
    "n_jobs": -1,
    "random_state": 42,
}

EARLY_STOPPING_ROUNDS = 50
LOG_EVAL_PERIOD = 100


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ModelConfig:
    params: dict = field(default_factory=lambda: dict(DEFAULT_PARAMS))
    early_stopping_rounds: int = EARLY_STOPPING_ROUNDS
    log_eval_period: int = LOG_EVAL_PERIOD
    categorical_features: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Main model class
# ---------------------------------------------------------------------------

class PriceForecastModel:
    """Global LightGBM model for electronics price forecasting.

    The model predicts `log_return` (log(P_t) - log(P_{t-1})).
    To recover the EGP price, it needs the previous price as an anchor.
    """

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config or ModelConfig()
        self._booster: Optional[lgb.Booster] = None
        self._feature_names: list[str] = []
        self._best_iteration: int = 0

    # -----------------------------------------------------------------------
    # Training
    # -----------------------------------------------------------------------

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        sample_weights: Optional[np.ndarray] = None,
    ) -> "PriceForecastModel":
        """Train the LightGBM booster with early stopping.

        Args:
            X_train / y_train:  Training features and log-return targets.
            X_val   / y_val  :  Validation features and log-return targets.
            sample_weights    :  Optional per-row training weights (numpy array).
                                 Pass inverse-frequency weights to rebalance
                                 price tiers.  Val set is never weighted.

        Returns:
            self (for chaining)
        """
        self._feature_names = list(X_train.columns)

        cat_features = [
            f for f in self.config.categorical_features
            if f in self._feature_names
        ]

        train_ds = lgb.Dataset(
            X_train,
            label=y_train,
            weight=sample_weights,            # None = uniform weights (LightGBM default)
            categorical_feature=cat_features if cat_features else "auto",
            free_raw_data=False,
        )
        val_ds = lgb.Dataset(
            X_val,
            label=y_val,
            reference=train_ds,
            categorical_feature=cat_features if cat_features else "auto",
            free_raw_data=False,
        )

        callbacks = [
            lgb.early_stopping(
                stopping_rounds=self.config.early_stopping_rounds,
                verbose=True,
            ),
            lgb.log_evaluation(period=self.config.log_eval_period),
        ]

        params = dict(self.config.params)
        n_estimators = params.pop("n_estimators", 2000)

        logger.info(
            "Training LightGBM: %d train rows, %d val rows, max %d rounds",
            len(X_train), len(X_val), n_estimators,
        )

        self._booster = lgb.train(
            params=params,
            train_set=train_ds,
            num_boost_round=n_estimators,
            valid_sets=[val_ds],
            callbacks=callbacks,
        )

        self._best_iteration = self._booster.best_iteration
        logger.info("Training complete. Best iteration: %d", self._best_iteration)
        return self

    # -----------------------------------------------------------------------
    # Prediction
    # -----------------------------------------------------------------------

    def predict_log_return(self, X: pd.DataFrame) -> np.ndarray:
        """Return predicted log returns."""
        if self._booster is None:
            raise RuntimeError("Model has not been trained yet. Call .fit() first.")
        return self._booster.predict(X, num_iteration=self._best_iteration)

    def predict_price(
        self,
        X: pd.DataFrame,
        prev_prices: pd.Series,
    ) -> np.ndarray:
        """Invert log return prediction to obtain EGP price.

        P_hat_t = P_{t-1} * exp(log_return_hat_t)

        Args:
            X: Feature matrix for the prediction step.
            prev_prices: Series of actual prices at t-1 (same index as X).

        Returns:
            Numpy array of predicted EGP prices.
        """
        log_return_hat = self.predict_log_return(X)
        prev = prev_prices.values.astype(float)
        return prev * np.exp(log_return_hat)

    # -----------------------------------------------------------------------
    # Inspection
    # -----------------------------------------------------------------------

    def feature_importance(self, importance_type: str = "gain") -> pd.DataFrame:
        """Return a sorted DataFrame of feature importances."""
        if self._booster is None:
            raise RuntimeError("Model has not been trained yet.")
        importances = self._booster.feature_importance(importance_type=importance_type)
        df = pd.DataFrame({
            "feature": self._feature_names,
            "importance": importances,
        }).sort_values("importance", ascending=False).reset_index(drop=True)
        return df

    def save(self, path: str) -> None:
        """Persist the trained booster to disk."""
        if self._booster is None:
            raise RuntimeError("Nothing to save – model not trained.")
        self._booster.save_model(path)
        logger.info("Model saved to %s", path)

    @classmethod
    def load(cls, path: str, config: Optional[ModelConfig] = None) -> "PriceForecastModel":
        """Load a persisted LightGBM booster from disk."""
        instance = cls(config=config)
        instance._booster = lgb.Booster(model_file=path)
        instance._best_iteration = instance._booster.best_iteration
        instance._feature_names = instance._booster.feature_name()
        logger.info("Model loaded from %s", path)
        return instance
