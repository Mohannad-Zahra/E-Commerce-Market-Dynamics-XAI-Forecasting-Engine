"""
shap_engine.py
==============
Computes SHAP (SHapley Additive exPlanations) values for the SVM classifier
using a KernelExplainer backed by a sample from the full dataset.

Returns per-candidate feature importance dictionaries sorted by absolute
contribution (descending), matching the notebook output format.
"""

import warnings
from typing import Dict, List

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline

from state_detector import FEATURE_COLS

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_CLASS = "Deflating Arbitrage"
BACKGROUND_SAMPLE_SIZE = 100  # rows sampled for the KernelExplainer background


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_shap_drivers(
    model: Pipeline,
    candidates: pd.DataFrame,
    background_data: pd.DataFrame,
    feature_names: List[str] = FEATURE_COLS,
    target_class: str = TARGET_CLASS,
    background_n: int = BACKGROUND_SAMPLE_SIZE,
) -> List[Dict[str, float]]:
    """
    Runs SHAP KernelExplainer on *candidates* and returns a list of
    ``shap_drivers`` dictionaries – one dict per candidate row.

    Each dict maps feature_name → SHAP value (float, rounded to 4 dp),
    sorted by absolute contribution descending.

    Parameters
    ----------
    model : fitted sklearn Pipeline (StandardScaler + SVC)
    candidates : pd.DataFrame
        Rows to explain; must contain ``feature_names`` columns.
    background_data : pd.DataFrame
        Pool used to build the SHAP background distribution.
    feature_names : list[str]
        Feature column names (must match training order).
    target_class : str
        The class whose SHAP values are extracted.
    background_n : int
        Number of background rows to sample.

    Returns
    -------
    list[dict]  –  one dict per row in *candidates*.
    """
    svm_model = model.named_steps["svm"]
    scaler = model.named_steps["scaler"]

    # Scale inputs
    X_candidates = scaler.transform(candidates[feature_names].fillna(0))

    bg_sample = (
        background_data[feature_names]
        .sample(n=min(background_n, len(background_data)), random_state=42)
        .fillna(0)
    )
    X_background = scaler.transform(bg_sample)

    # KernelExplainer works with any sklearn-compatible predict_proba
    explainer = shap.KernelExplainer(svm_model.predict_proba, X_background)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        shap_values = explainer.shap_values(X_candidates, silent=True)

    # Resolve which class index we care about
    classes = list(svm_model.classes_)
    try:
        class_idx = classes.index(target_class)
    except ValueError:
        class_idx = 0

    # Extract the target class slice
    if isinstance(shap_values, list):
        target_shap = shap_values[class_idx]          # shape: (n_candidates, n_features)
    elif shap_values.ndim == 3:
        target_shap = shap_values[:, :, class_idx]
    else:
        target_shap = shap_values

    # Build sorted dicts
    result: List[Dict[str, float]] = []
    for row_shap in target_shap:
        drivers = {
            feat: round(float(row_shap[i]), 4)
            for i, feat in enumerate(feature_names)
        }
        # Sort by |value| descending
        drivers = dict(sorted(drivers.items(), key=lambda kv: abs(kv[1]), reverse=True))
        result.append(drivers)

    return result
