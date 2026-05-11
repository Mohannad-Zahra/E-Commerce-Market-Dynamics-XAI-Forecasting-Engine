"""
recommendation_pipeline.py
===========================
Orchestrates the full autonomous recommendation pipeline:

    1. Ranking         – ranking_engine.get_ranked_laptops()
    2. Classification  – state_detector.train_state_detector() + predict_states()
    3. SHAP            – shap_engine.compute_shap_drivers()
    4. JSON export     – strict contract (see OUTPUT CONTRACT below)

OUTPUT CONTRACT
---------------
{
    "candidates": [
        {
            "model_id":        str,   # product_id (URL or identifier)
            "model":           str,   # same as model_id (human label)
            "current_price":   float,
            "price_14d_avg":   float,
            "forecasted_price": float,
            "r_score":         float,
            "classification":  str,   # e.g. "Deflating Arbitrage"
            "confidence":      str,   # e.g. "80.96%"
            "shap_drivers":    dict   # feature → SHAP value
        },
        ...
    ]
}

ENTRY POINT
-----------
    from recommendation_pipeline import run_recommendation_pipeline
    output = run_recommendation_pipeline()   # returns the dict
"""

import json
import os
import warnings
from typing import Dict, List, Optional

import pandas as pd

from ranking_engine import get_ranked_laptops
from shap_engine import compute_shap_drivers
from state_detector import FEATURE_COLS, predict_states, train_state_detector

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(_DIR, "recommendations.json")

TOP_N = 20                        # candidates forwarded to classification + SHAP
PREFERRED_CLASS = "Deflating Arbitrage"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_candidate_record(
    row: pd.Series,
    shap_drivers: Dict[str, float],
) -> dict:
    """Converts a DataFrame row + SHAP dict into the strict output record."""
    return {
        "model_id": str(row["product_id"]),
        "model": str(row["product_id"]),          # same field; rename if you have a human label column
        "current_price": float(row["current_price"]),
        "price_14d_avg": float(row["price_14d_avg"]),
        "forecasted_price": float(row["forecasted_price"]),
        "r_score": round(float(row["r_score"]), 4),
        "classification": str(row["state_classification"]),
        "confidence": str(row.get("confidence", "N/A")),
        "shap_drivers": shap_drivers,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_recommendation_pipeline(
    output_path: str = OUTPUT_JSON,
    top_n: int = TOP_N,
    preferred_class: str = PREFERRED_CLASS,
) -> Dict:
    """
    Runs the full pipeline end-to-end and returns a clean Python dict that
    also gets persisted to *output_path* as formatted JSON.

    Parameters
    ----------
    output_path : str
        Where to save ``recommendations.json``.
    top_n : int
        How many top-ranked candidates to classify and explain.
    preferred_class : str
        If any candidate belongs to this class, only those are included in
        the final output; otherwise all *top_n* candidates are included.

    Returns
    -------
    dict – the full recommendation payload (no pandas objects).
    """
    print("[1/4] Loading data & computing R_score rankings …")
    full_latest, ranked = get_ranked_laptops()

    print(f"[2/4] Training state detector on {len(full_latest):,} products …")
    model = train_state_detector(full_latest)

    print(f"[3/4] Classifying top-{top_n} candidates & computing SHAP …")
    top_n_df = ranked.head(top_n).copy()
    top_n_classified = predict_states(model, top_n_df)

    # Select valid buys (preferred class); fall back to all top-n if none found
    valid_buys = top_n_classified[
        top_n_classified["state_classification"] == preferred_class
    ].copy()

    if valid_buys.empty:
        print(
            f"  ⚠  No '{preferred_class}' candidates in top-{top_n}. "
            "Returning all top candidates."
        )
        valid_buys = top_n_classified.copy()

    shap_list = compute_shap_drivers(
        model=model,
        candidates=valid_buys,
        background_data=full_latest,
        feature_names=FEATURE_COLS,
        target_class=preferred_class,
    )

    print("[4/4] Building JSON payload …")
    candidates: List[dict] = []
    for (_, row), shap_drivers in zip(valid_buys.iterrows(), shap_list):
        candidates.append(_build_candidate_record(row, shap_drivers))

    payload = {"candidates": candidates}

    # Persist to disk
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=4, ensure_ascii=False)

    print(f"✓ Done. {len(candidates)} candidate(s) saved to '{output_path}'.")
    return payload


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_recommendation_pipeline()
    print("\nFinal JSON Payload:")
    print(json.dumps(result, indent=4, ensure_ascii=False))
