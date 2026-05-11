import shap
import joblib
import pandas as pd
import logging
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

class JoblibExplainer:
    """
    Requirement 2.2: SHAP Explanation Engine using Joblib models.
    Uses SHAP TreeExplainer for high-performance LightGBM explanations.
    """
    def __init__(self, model_path: str, feature_names: List[str]):
        self.model_path = model_path
        self.feature_names = feature_names
        self.model = None
        self.explainer = None
        
        if os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
                # TreeExplainer is optimized for LightGBM/XGBoost
                self.explainer = shap.TreeExplainer(self.model)
                logger.info(f"✅ Loaded Joblib model for SHAP from {model_path}")
            except Exception as e:
                logger.error(f"❌ Failed to load Joblib model: {e}")
        else:
            logger.error(f"⚠️ Model path not found: {model_path}")

    def compute_shap(self, target_df: pd.DataFrame):
        """
        Computes SHAP values using TreeExplainer.
        Returns a numpy array of shape (n_targets, n_features).
        """
        if self.explainer is None:
            logger.error("Explainer is not initialized.")
            return None
            
        try:
            # TreeExplainer works directly on the feature matrix
            target_values = target_df[self.feature_names]
            shap_values = self.explainer.shap_values(target_values)
            
            # For some versions of SHAP/LGBM, shap_values might be a list (for multi-class)
            # but for Regressor it's usually just an array.
            return shap_values
        except Exception as e:
            logger.error(f"SHAP computation failed: {e}")
            return None
