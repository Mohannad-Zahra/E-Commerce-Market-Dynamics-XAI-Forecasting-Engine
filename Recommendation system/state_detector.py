"""
state_detector.py
=================
Trains an SVM (RBF kernel) classifier on the full dataset to detect the
market state of each candidate product:

    • Deflating Arbitrage  – high r_score, low volatility  → good buy signal
    • Hyper-Inflated       – current price significantly above 14-day average
    • Neutral              – everything else

The labelling function mirrors the rule-based heuristic used in the notebook.
"""

import warnings

import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Feature columns used for training / prediction
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    "current_price",
    "forecasted_price",
    "volatility_score",
    "price_14d_avg",
    "months_since_release",
]

# SVM hyper-parameters (match the notebook)
SVM_PARAMS = dict(
    kernel="rbf",
    probability=True,
    C=1.0,
    gamma="scale",
    random_state=42,
)


# ---------------------------------------------------------------------------
# Heuristic labelling (same logic as the notebook)
# ---------------------------------------------------------------------------

def label_logic(row: pd.Series) -> str:
    """Rule-based label generator used to create synthetic training targets."""
    if row["r_score"] > 65 and row["volatility_score"] < 20:
        return "Deflating Arbitrage"
    if row["current_price"] > row["price_14d_avg"] * 1.2:
        return "Hyper-Inflated"
    return "Neutral"


# ---------------------------------------------------------------------------
# Model training
# ---------------------------------------------------------------------------

def train_state_detector(latest_data: pd.DataFrame) -> Pipeline:
    """
    Builds and fits a StandardScaler + SVC pipeline on the provided DataFrame.

    Parameters
    ----------
    latest_data : pd.DataFrame
        Must contain FEATURE_COLS plus 'r_score'.

    Returns
    -------
    sklearn.pipeline.Pipeline  –  fitted pipeline.
    """
    X_train = latest_data[FEATURE_COLS].fillna(0)
    y_train = latest_data.apply(label_logic, axis=1)

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("svm", SVC(**SVM_PARAMS)),
    ])
    model.fit(X_train, y_train)
    return model


# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------

def predict_states(
    model: Pipeline,
    candidates: pd.DataFrame,
) -> pd.DataFrame:
    """
    Appends ``state_classification`` and ``confidence`` columns to *candidates*.

    Parameters
    ----------
    model : fitted sklearn Pipeline
    candidates : pd.DataFrame
        Rows to classify; must contain FEATURE_COLS.

    Returns
    -------
    pd.DataFrame  –  *candidates* with two new columns added.
    """
    result = candidates.copy()
    X = result[FEATURE_COLS].fillna(0)

    result["state_classification"] = model.predict(X)

    probas = model.predict_proba(X)
    result["confidence"] = [f"{round(max(p) * 100, 2)}%" for p in probas]

    return result
