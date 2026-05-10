import numpy as np
import pandas as pd
from scipy.spatial.distance import euclidean
import logging

logger = logging.getLogger("DriftMonitor")
logger.setLevel(logging.INFO)

class DriftMonitor:
    def __init__(self, baseline_state):
        """
        Initializes with the app_state from offline_state_builder.
        """
        self.baseline_centroids = baseline_state["fcm_centroids"]
        self.svm_model = baseline_state["svm_model"]
        self.fcm_scaler = baseline_state["fcm_scaler"]
        self.baseline_df = baseline_state["background_df"]
        
        # Historical gap buffer for Signal 1
        self.gap_history = []
        
    def calculate_signal_1(self, live_batch_df):
        """
        Signal 1: 7-day rolling average of SVM Gap across all batches.
        Triggers if median distance degrades by > 30%.
        """
        from state_detector import FEATURE_COLS
        X = live_batch_df[FEATURE_COLS].fillna(0)
        
        try:
            # Calculate gaps for the current batch
            current_gaps = np.abs(self.svm_model.decision_function(X))
            median_gap = np.median(current_gaps)
            
            self.gap_history.append(median_gap)
            if len(self.gap_history) > 7:
                self.gap_history.pop(0)
            
            if len(self.gap_history) < 3:
                return False, median_gap, 0.0 # Not enough history
            
            rolling_avg = np.mean(self.gap_history[:-1])
            degradation = (rolling_avg - median_gap) / rolling_avg if rolling_avg > 0 else 0
            
            triggered = degradation > 0.30
            return triggered, median_gap, degradation
        except Exception as e:
            logger.error(f"Signal 1 calculation failed: {e}")
            return False, 0.0, 0.0

    def calculate_signal_2(self, live_batch_df):
        """
        Signal 2: Euclidean spatial drift between live feature distributions and baseline centroids.
        """
        from state_detector import FEATURE_COLS
        X = live_batch_df[FEATURE_COLS].fillna(0)
        X_scaled = self.fcm_scaler.transform(X)
        
        # Calculate live centroids (simplified as mean of scaled features)
        live_centroid = np.mean(X_scaled, axis=0)
        
        # Compare to baseline 'Deflating Arbitrage' centroid (index 0 usually)
        # In a real scenario, we'd find the closest centroid
        distances = [euclidean(live_centroid, c) for c in self.baseline_centroids]
        min_dist = min(distances)
        
        # Trigger if drift exceeds a threshold (e.g., 1.5 standard deviations or absolute value)
        # Here we use a heuristic threshold
        DRIFT_THRESHOLD = 1.2 
        triggered = min_dist > DRIFT_THRESHOLD
        
        return triggered, min_dist

    def check_drift(self, live_batch_df):
        """
        Requirement 5: Dual-trigger drift detection.
        Requires BOTH Signal 1 and Signal 2 firing simultaneously.
        """
        s1_triggered, gap, deg = self.calculate_signal_1(live_batch_df)
        s2_triggered, dist = self.calculate_signal_2(live_batch_df)
        
        status = {
            "signal_1": {"triggered": s1_triggered, "median_gap": gap, "degradation": deg},
            "signal_2": {"triggered": s2_triggered, "centroid_distance": dist},
            "overall_drift": s1_triggered and s2_triggered
        }
        
        if status["overall_drift"]:
            logger.warning("🚨 CRITICAL DRIFT DETECTED. Re-training recommended.")
        else:
            logger.info("✅ System stability within normal parameters.")
            
        return status
