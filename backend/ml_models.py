"""
ml_models.py
------------
Lazy-loading wrappers for the three production ML models:

  Model 1 – Price Forecast (LightGBM Booster via joblib)
      File   : ETL/model/artefacts/model.joblib
      Input  : 26 named float features
      Output : log_return  →  predicted_price_egp = current_price * exp(log_return)

  Model 2 – Price Forecast (LightGBM ONNX export)
      File   : ETL/model/artefacts/model.onnx
      Input  : float32[1, 26]  (same feature order as joblib)
      Output : float32[1, 1]   log_return

  Model 3 – Volatility Scorer (HistGradientBoosting ONNX)
      File   : Volatility score ML pipeline/volatility_model.onnx
      Input  : float32[1, 15]  (see VOLATILITY_FEATURES below)
      Output : float32[1, 1]   volatility_score

Models are loaded on first use (lazy) to keep the server start-up fast.
"""

from __future__ import annotations
import os
import math
import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Paths (relative to this file) ────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent

JOBLIB_PATH      = _BASE / "ETL" / "model" / "artefacts" / "model.joblib"
LGBM_ONNX_PATH   = _BASE / "ETL" / "model" / "artefacts" / "model.onnx"
VOLAT_ONNX_PATH  = _BASE / "Volatility score ML pipeline" / "volatility_model.onnx"

# ── Feature metadata (from new XAI pipeline) ────────────────────────────
NEW_FEATURES = [
    "compute_potential", "delta_p_7d", "delta_p_14d", "delta_p_1d", "vol_30d",
    "official_egp_usd", "cpi_inflation", "is_major_sale_period", "competitor_scarcity_count",
    "volume_weight", "D_months", "k", "import_lambda", "missing_release_date"
]  # 14 features


# ── Thread-safe lazy singleton ────────────────────────────────────────────────
class _LazyLoader:
    def __init__(self):
        self._lock = threading.Lock()
        self._joblib: Optional[object]   = None
        self._lgbm_onnx: Optional[object] = None
        self._volat_onnx: Optional[object] = None
        self._joblib_loaded   = False
        self._lgbm_onnx_loaded = False
        self._volat_onnx_loaded = False

    # ── Price Forecast (Model 1) ──────────────────────────────────────────────────────
    @property
    def price_onnx_session(self):
        if not self._joblib_loaded:
            with self._lock:
                if not self._joblib_loaded:
                    self._joblib_loaded = True
                    try:
                        import onnxruntime as rt
                        self._joblib = rt.InferenceSession(str(_BASE / "Volatility score ML pipeline" / "model_14d.onnx"))
                        logger.info("✅ Loaded Model 1 (Price ONNX): model_14d.onnx")
                    except Exception as e:
                        logger.error("❌ Could not load Price ONNX: %s", e)
                        self._joblib = None
        return self._joblib

    # ── Stability Score (Model 2) ───────────────────────────────────────────────────
    @property
    def stability_onnx_session(self):
        if not self._lgbm_onnx_loaded:
            with self._lock:
                if not self._lgbm_onnx_loaded:
                    self._lgbm_onnx_loaded = True
                    try:
                        import onnxruntime as rt
                        self._lgbm_onnx = rt.InferenceSession(str(_BASE / "Volatility score ML pipeline" / "stability_model_v2.onnx"))
                        logger.info("✅ Loaded Model 2 (Stability ONNX): stability_model_v2.onnx")
                    except Exception as e:
                        logger.error("❌ Could not load Stability ONNX: %s", e)
                        self._lgbm_onnx = None
        return self._lgbm_onnx


_loader = _LazyLoader()


# ── Public inference API ──────────────────────────────────────────────────────

def predict_price_onnx(features: list[float]) -> dict:
    """
    Model 1: 14d Price Forecast.
    """
    session = _loader.price_onnx_session
    if session is None:
        raise RuntimeError("Model 1 (Price) is not available.")

    # Try mapping to kwargs, but usually it's just a flat array if we converted properly
    try:
        inp_name = session.get_inputs()[0].name
        # model_14d might expect a single tensor or dict of kwargs. Let's assume FloatTensorType like stability model.
        # But wait! If it expects dict, we need to handle that. Let's just use array.
        arr = np.array([features], dtype=np.float32)
        raw = session.run(None, {inp_name: arr})
        
        # It predicts price directly now
        predicted_price = float(raw[0].flat[0])
    except Exception as e:
        # If it expects named kwargs like stability model:
        inputs = {inp.name: np.array([[f]], dtype=np.float32) for inp, f in zip(session.get_inputs(), features)}
        raw = session.run(None, inputs)
        # extract value based on what it returns, usually a list of dicts or array
        res = raw[0]
        if hasattr(res, 'flat'):
            predicted_price = float(res.flat[0])
        else:
            predicted_price = float(res[0])

    return {
        "model":                "14d Price Forecast (ONNX)",
        "predicted_price_egp":  round(predicted_price, 2),
    }

def predict_stability_onnx(features: list[float]) -> dict:
    """
    Model 2: Stability Scorer.
    """
    session = _loader.stability_onnx_session
    if session is None:
        raise RuntimeError("Model 2 (Stability) is not available.")

    try:
        inputs = {inp.name: np.array([[f]], dtype=np.float32) for inp, f in zip(session.get_inputs(), features)}
        raw = session.run(None, inputs)
        score = float(raw[0].flat[0] if hasattr(raw[0], 'flat') else raw[0][0])
    except Exception:
        inp_name = session.get_inputs()[0].name
        arr = np.array([features], dtype=np.float32)
        raw = session.run(None, {inp_name: arr})
        score = float(raw[0].flat[0])

    return {
        "model": "Stability Scorer V2 (ONNX)",
        "predicted_stability_score": round(score, 6),
    }
