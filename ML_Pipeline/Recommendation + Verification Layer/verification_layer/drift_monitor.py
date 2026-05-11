import numpy as np
import pandas as pd
import faiss
import skfuzzy as fuzz
import time
from scipy.spatial.distance import euclidean
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
import logging

logger = logging.getLogger("DriftMonitor")
logger.setLevel(logging.INFO)

# Retrain threshold: trigger after this many new rows are ingested
RETRAIN_ROW_THRESHOLD = 10_000


class DriftMonitor:
    def __init__(self, baseline_state):
        """
        Initializes with the app_state from offline_state_builder.
        """
        self.baseline_centroids = baseline_state["fcm_centroids"]
        self.svm_model = baseline_state["svm_model"]
        self.fcm_scaler = baseline_state["fcm_scaler"]
        self.baseline_df = baseline_state["background_df"]
        self.app_state = baseline_state  # Full reference for retrain
        
        # Historical gap buffer for Signal 1
        self.gap_history = []
        
    def calculate_signal_1(self, live_batch_df):
        """
        Signal 1: 7-day rolling average of SVM Gap across all batches.
        Triggers if median distance degrades by > 30%.
        """
        from state_detector import FEATURE_COLS
        X = live_batch_df[FEATURE_COLS].fillna(0)
        
        if X.empty:
            return False, 0.0, 0.0
            
        try:
            # Calculate gaps for the current batch
            current_gaps = np.abs(self.svm_model.decision_function(X))
            if len(current_gaps) == 0:
                return False, 0.0, 0.0
            median_gap = np.median(current_gaps)
            
            self.gap_history.append(median_gap)
            if len(self.gap_history) > 7:
                self.gap_history.pop(0)
            
            if len(self.gap_history) < 3:
                return False, median_gap, 0.0 # Not enough history
            
            rolling_avg = np.mean(self.gap_history[:-1])
            degradation = (rolling_avg - median_gap) / rolling_avg if rolling_avg > 0 else 0
            
            triggered = bool(degradation > 0.30)
            return triggered, float(median_gap), float(degradation)
        except Exception as e:
            logger.error(f"Signal 1 calculation failed: {e}")
            return False, 0.0, 0.0

    def calculate_signal_2(self, live_batch_df):
        """
        Signal 2: Euclidean spatial drift between live feature distributions and baseline centroids.
        Requirement 5 Fix: Computes actual live centroids via FCM and compares against baseline.
        """
        from state_detector import FEATURE_COLS
        X = live_batch_df[FEATURE_COLS].fillna(0)
        X_scaled = self.fcm_scaler.transform(X).T # [n_features, n_data]
        
        if X.empty:
            return False, 0.0

        try:
            # Step 1: Run FCM on the live batch to find the ACTUAL new centroids
            # Using the same parameters as the offline builder (c=3, m=2.0)
            cntr_live, u, u0, d, jm, p, fpc = fuzz.cluster.cmeans(
                X_scaled, c=3, m=2.0, error=0.005, maxiter=1000, init=None
            )
            
            # Step 2: Matrix Alignment (Cluster matching)
            # We must map new clusters to baseline clusters correctly before calculating distance.
            # We sort centroids by their first principal component or simply by Euclidean distance 
            # to the global origin to ensure consistent ordering.
            def sort_centroids(centroids):
                return centroids[np.argsort(np.linalg.norm(centroids, axis=1))]
            
            sorted_baseline = sort_centroids(self.baseline_centroids)
            sorted_live = sort_centroids(cntr_live)
            
            # Step 3: Compute Pairwise Distance
            # We take the mean Euclidean distance between the aligned pairs
            distances = [euclidean(sorted_baseline[i], sorted_live[i]) for i in range(len(sorted_baseline))]
            mean_dist = np.mean(distances)
            
            # Trigger if drift exceeds threshold
            DRIFT_THRESHOLD = 1.2 
            triggered = bool(mean_dist > DRIFT_THRESHOLD)
            
            return triggered, float(mean_dist)
        except Exception as e:
            logger.error(f"Signal 2 calculation failed: {e}")
            # Fallback to simple mean if FCM fails on small batch
            live_centroid = np.mean(X_scaled.T, axis=0)
            distances = [euclidean(live_centroid, c) for c in self.baseline_centroids]
            min_dist = float(min(distances))
            return bool(min_dist > 1.2), min_dist

    def check_drift(self, live_batch_df):
        """
        Requirement 5: Dual-trigger drift detection.
        Requires BOTH Signal 1 and Signal 2 firing simultaneously.
        If drift is detected, autonomously triggers retrain.
        """
        from agentic_db import save_drift_snapshot
        
        s1_triggered, gap, deg = self.calculate_signal_1(live_batch_df)
        s2_triggered, dist = self.calculate_signal_2(live_batch_df)
        
        status = {
            "signal_1": {"triggered": s1_triggered, "median_gap": gap, "degradation": deg},
            "signal_2": {"triggered": s2_triggered, "centroid_distance": dist},
            "overall_drift": s1_triggered and s2_triggered,
            "retrain_executed": False,
        }
        
        # Persist drift snapshot to DB
        save_drift_snapshot(status, batch_size=len(live_batch_df))
        
        if status["overall_drift"]:
            logger.warning("🚨 CRITICAL DRIFT DETECTED. Triggering autonomous retrain...")
            new_state = self.trigger_retrain(
                source_df=self.baseline_df,
                trigger_reason="drift_detection",
                signal_1_value=deg,
                signal_2_value=dist,
            )
            if new_state:
                status["retrain_executed"] = True
        else:
            logger.info("✅ System stability within normal parameters.")
            
        return status

    def check_row_threshold(self):
        """
        Trigger 2: Check if enough new rows have been ingested since the last retrain.
        Returns (should_retrain: bool, rows_since_last: int)
        """
        from agentic_db import get_rows_since_last_retrain
        
        rows_since = get_rows_since_last_retrain()
        should_retrain = rows_since >= RETRAIN_ROW_THRESHOLD
        
        if should_retrain:
            logger.warning(f"📊 Row threshold reached: {rows_since:,} rows since last retrain (threshold: {RETRAIN_ROW_THRESHOLD:,})")
        else:
            logger.info(f"📊 Rows since last retrain: {rows_since:,}/{RETRAIN_ROW_THRESHOLD:,}")
        
        return should_retrain, rows_since

    def trigger_retrain(self, source_df, trigger_reason="manual", signal_1_value=0.0, signal_2_value=0.0):
        """
        Autonomous retrain: re-runs the full offline training cycle and hot-swaps app_state.
        
        Steps:
          1. Re-run FCM clustering → new centroids
          2. Retrain SVM classifier → new decision boundary
          3. Recompute mean_shap_vector → new implicit RAG baseline
          4. Rebuild FAISS index → new explicit RAG store
          5. Hot-swap app_state references
          6. Log retrain event to database
        
        Returns the new app_state dict, or None on failure.
        """
        from state_detector import FEATURE_COLS, SVM_PARAMS, label_logic
        from ranking_engine import calculate_r_score
        from agentic_db import log_retrain_event, get_rows_since_last_retrain
        from offline_state_builder import SHAP_COLS
        
        logger.info("=" * 60)
        logger.info(f"🔄 AUTONOMOUS RETRAIN TRIGGERED — Reason: {trigger_reason}")
        logger.info("=" * 60)
        
        t_start = time.time()
        fpc_before = self.app_state.get("fpc", 0.0)
        faiss_size_before = self.app_state["faiss_index"].ntotal
        rows_since = get_rows_since_last_retrain()
        
        try:
            df = source_df.copy()
            
            # Ensure required columns exist
            if "current_price" not in df.columns:
                df["current_price"] = df["price_t_plus_14"] / (1 + df["delta_p_14d"].fillna(0))
            if "price_14d_avg" not in df.columns:
                p_t_7 = df["price_t_plus_14"] / (1 + (df["delta_p_14d"] - df["delta_p_7d"]).fillna(0))
                df["price_14d_avg"] = (df["current_price"] + p_t_7) / 2
            if "forecasted_price" not in df.columns:
                df["forecasted_price"] = df["price_t_plus_14"]
            if "volatility_score" not in df.columns:
                df["volatility_score"] = 100 - df["predicted_stability_score"]
            if "months_since_release" not in df.columns:
                df["months_since_release"] = df["D_months"]
            if "r_score" not in df.columns:
                df["r_score"] = calculate_r_score(df)
            
            X_train = df[FEATURE_COLS].fillna(0)
            y_train = df.apply(label_logic, axis=1)
            
            # Step 1: Retrain SVM
            logger.info("  [1/5] Retraining SVM Pipeline...")
            svm_pipeline = Pipeline([
                ("scaler", StandardScaler()),
                ("svm", SVC(**SVM_PARAMS)),
            ])
            svm_pipeline.fit(X_train, y_train)
            logger.info("  [1/5] ✅ SVM retrained.")
            
            # Step 2: Re-run FCM
            logger.info("  [2/5] Re-computing FCM centroids...")
            scaler_fcm = StandardScaler()
            X_scaled = scaler_fcm.fit_transform(X_train).T
            cntr, u, u0, d, jm, p, fpc = fuzz.cluster.cmeans(
                X_scaled, c=3, m=2.0, error=0.005, maxiter=1000, init=None
            )
            logger.info(f"  [2/5] ✅ FCM retrained. New FPC: {fpc:.4f} (was {fpc_before:.4f})")
            
            # Step 3: Recompute cluster-specific SHAP means (Requirement 4 Fix)
            logger.info("  [3/5] Recomputing cluster-specific SHAP means via KernelExplainer...")
            from shap_engine import compute_shap_drivers
            shap_dicts = compute_shap_drivers(
                model=svm_pipeline,
                candidates=df,
                background_data=df,
                feature_names=FEATURE_COLS
            )
            valid_shap = np.array([
                [d.get(col, 0.0) for col in SHAP_COLS]
                for d in shap_dicts
            ])
            mean_shap_vector = np.mean(valid_shap, axis=0)
            
            cluster_assignments = np.argmax(u, axis=0)
            cluster_shap_means = []
            for i in range(cntr.shape[0]):
                cluster_indices = np.where(cluster_assignments == i)[0]
                if len(cluster_indices) > 0:
                    c_mean = np.mean(valid_shap[cluster_indices], axis=0)
                else:
                    c_mean = np.zeros(len(SHAP_COLS))
                cluster_shap_means.append(c_mean)
            
            logger.info(f"  [3/5] ✅ Cluster SHAP means updated ({len(cluster_shap_means)} clusters).")
            
            # Step 4: Rebuild FAISS index
            logger.info("  [4/5] Rebuilding FAISS K-NN index...")
            dimension = len(SHAP_COLS)
            faiss_index = faiss.IndexFlatL2(dimension)
            vectors_f32 = np.ascontiguousarray(valid_shap.astype(np.float32))
            faiss_index.add(vectors_f32)
            historical_labels = y_train.values
            faiss_size_after = faiss_index.ntotal
            logger.info(f"  [4/5] ✅ FAISS rebuilt. Vectors: {faiss_size_before} → {faiss_size_after}")
            
            # Step 5: Refit R_score scaler
            logger.info("  [5/5] Refitting R_score scaler...")
            r_score_scaler = MinMaxScaler()
            r_score_scaler.fit(df[["r_score"]])
            logger.info("  [5/5] ✅ R_score scaler refitted.")
            
            # Hot-swap: update all references in app_state
            self.app_state["svm_model"] = svm_pipeline
            self.app_state["fcm_centroids"] = cntr
            self.app_state["fcm_scaler"] = scaler_fcm
            self.app_state["mean_shap_vector"] = mean_shap_vector
            self.app_state["cluster_shap_means"] = cluster_shap_means
            self.app_state["faiss_index"] = faiss_index
            self.app_state["historical_labels"] = historical_labels
            self.app_state["r_score_scaler"] = r_score_scaler
            self.app_state["fpc"] = fpc
            
            # Update DriftMonitor's own references
            self.baseline_centroids = cntr
            self.svm_model = svm_pipeline
            self.fcm_scaler = scaler_fcm
            self.gap_history = []  # Reset gap history after retrain
            
            duration = time.time() - t_start
            
            # Log to database
            log_retrain_event(
                trigger_reason=trigger_reason,
                rows_since_last=rows_since,
                fpc_before=fpc_before,
                fpc_after=fpc,
                n_clusters=3,
                faiss_size_before=faiss_size_before,
                faiss_size_after=faiss_size_after,
                signal_1_value=signal_1_value,
                signal_2_value=signal_2_value,
                duration_seconds=duration,
            )
            
            logger.info("=" * 60)
            logger.info(f"✅ RETRAIN COMPLETE in {duration:.1f}s")
            logger.info(f"   FPC: {fpc_before:.4f} → {fpc:.4f}")
            logger.info(f"   FAISS: {faiss_size_before} → {faiss_size_after} vectors")
            logger.info(f"   Trigger: {trigger_reason}")
            logger.info("=" * 60)
            
            return self.app_state
            
        except Exception as e:
            logger.error(f"❌ RETRAIN FAILED: {e}")
            import traceback
            traceback.print_exc()
            return None
