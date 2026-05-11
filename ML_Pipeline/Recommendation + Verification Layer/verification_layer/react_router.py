import logging
import sys
import os
import numpy as np
import skfuzzy as fuzz
import joblib

# Ensure Recommendation system path is on sys.path for shap_engine
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Recommendation system")))

from shap_engine import compute_shap_drivers
from state_detector import FEATURE_COLS

# Configure logging to see the routing trace
logger = logging.getLogger("ReActRouter")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# Configurable Thresholds
QUOTA_LIMIT = 7
BASE_THRESHOLD = 0.2
MIN_MARGIN = 0.5
MIN_PROB = 0.4
BORDERLINE_S = 0.5
RELIABILITY_THRESHOLD = 0.6
HIGH_S_THRESHOLD = 0.7
FAISS_TOLERANCE = 1.0
LAMBDA_ARIMA = 2.0  # Sensitivity for ARIMA multiplier

# SHAP_COLS now mirrors FEATURE_COLS — live SHAP is computed over the 5 SVM
# input features, not the static CSV shap_* columns.
SHAP_COLS = FEATURE_COLS  # kept for dashboard backward-compat

def calculate_intelligent_score(signals):
    """
    Requirement 1: The Intelligent Score.
    A composite of exactly 5 independent signals: 
    S (severity), Gap(SVM) (confidence), mu(predicted) (FCM), SARIMAX (trend), and SHAP (cosine).
    Using a weighted geometric mean to ensure all signals contribute and none are zero.
    """
    # Normalize Gap_SVM to [0,1] for the composite score (assuming max gap observed is around 5.0)
    norm_gap = min(signals["Gap_SVM"] / 5.0, 1.0)
    
    # Weights can be tuned, but here we give equal importance for compliance
    weights = [0.2, 0.2, 0.2, 0.2, 0.2]
    values = [
        max(signals["S"], 0.001), 
        max(norm_gap, 0.001), 
        max(signals["mu_predicted"], 0.001), 
        max(signals["trend_multiplier"], 0.001), 
        max(signals["SHAP_cos"], 0.001)
    ]
    
    score = np.prod([v**w for v, w in zip(values, weights)])
    return float(score)

def cosine_similarity(v1, v2):
    dot = np.dot(v1, v2)
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def run_react_loop(candidates, app_state):
    """
    Executes the Agentic Verification (ReAct) layer on the top candidates.
    candidates: list of candidate dictionaries.
    app_state: offline state containing svm_model, fcm_centroids, mean_shap_vector, faiss_index.
    """
    import pandas as pd

    dispatched_candidates = []
    dead_letter_queue = []
    
    svm_model = app_state["svm_model"]
    fcm_centroids = app_state["fcm_centroids"]
    mean_shap_vector = app_state["mean_shap_vector"]
    faiss_index = app_state["faiss_index"]
    background_df = app_state["background_df"]

    # -----------------------------------------------------------------------
    # PRE-COMPUTE LIVE SHAP VECTORS (Requirement 4)
    # Build a single DataFrame for all candidates and run one KernelExplainer
    # pass — much cheaper than one call per candidate.
    # -----------------------------------------------------------------------
    logger.info(f"Computing live SHAP vectors for {len(candidates)} candidates via KernelExplainer...")
    try:
        cand_df = pd.DataFrame([
            {
                "current_price":      float(c.get("current_price", 0)),
                "forecasted_price":   float(c.get("forecasted_price", 0)),
                "volatility_score":   float(c.get("volatility_score", 50)),
                "price_14d_avg":      float(c.get("price_14d_avg", 0)),
                "months_since_release": float(c.get("months_since_release", c.get("D_months", 0))),
            }
            for c in candidates
        ], columns=FEATURE_COLS)

        live_shap_dicts = compute_shap_drivers(
            model=svm_model,
            candidates=cand_df,
            background_data=background_df,
        )
        logger.info("  Live SHAP computation complete.")
    except Exception as shap_err:
        logger.warning(f"  Live SHAP failed ({shap_err}); falling back to zero vectors.")
        live_shap_dicts = [{feat: 0.0 for feat in FEATURE_COLS} for _ in candidates]
    
    # 1. SIGNAL COMPUTATION (Observe State) - PRE-COMPUTE FOR ALL
    logger.info(f"Pre-computing signals for {len(candidates)} candidates...")
    for idx, c in enumerate(candidates):
        model_id = c.get("model_id", "Unknown")
        
        # S: Normalized R_score using the trained offline scaler
        raw_r_score = float(c.get("r_score", 0.0))
        r_score_scaler = app_state["r_score_scaler"]
        S = float(r_score_scaler.transform([[raw_r_score]])[0][0])
        
        v_score = float(c.get("volatility_score", 100 - c.get("predicted_stability_score", 50)))
        m_age = float(c.get("months_since_release", c.get("D_months", 0)))
        
        df_x = pd.DataFrame([{
            "current_price": float(c.get("current_price", 0)),
            "forecasted_price": float(c.get("forecasted_price", 0)),
            "volatility_score": v_score,
            "price_14d_avg": float(c.get("price_14d_avg", 0)),
            "months_since_release": m_age
        }], columns=FEATURE_COLS)
        
        try:
            # Gap_SVM: distance to hyperplane (handle multiclass array)
            dfunc = svm_model.decision_function(df_x)[0]
            gap_svm = float(np.max(np.abs(dfunc))) if isinstance(dfunc, np.ndarray) else abs(dfunc)
        except Exception as e:
            gap_svm = 0.0
        
        # FCM Membership
        fcm_scaler = app_state["fcm_scaler"]
        X_fcm_scaled = fcm_scaler.transform(df_x).T
        try:
            u, u0, d, jm, p, fpc = fuzz.cluster.cmeans_predict(
                X_fcm_scaled, fcm_centroids, 2, error=0.005, maxiter=1000
            )
            mu_predicted = np.max(u[:, 0])
            predicted_cluster_idx = int(np.argmax(u[:, 0])) # Requirement 4 Fix
        except Exception as e:
            mu_predicted = 0.0
            predicted_cluster_idx = 0
        
        # SARIMAX_mult: Real SARIMAX forecast-based trend multiplier
        # Uses pre-trained Sub-Category-Level SARIMAX models when available
        p_t = float(c.get("current_price", 1))
        sarimax_models = app_state.get("sarimax_models")
        
        category = c.get("category", "Electronics")
        title = c.get("product_title", c.get("raw_title", "Unknown"))
        brand = str(title).split()[0].capitalize() if title else "Unknown"
        sub_category = f"{category}_{brand}"
        
        sarimax_success = False
        if sarimax_models and sub_category in sarimax_models:
            try:
                fitted_model = sarimax_models[sub_category]
                forecast = fitted_model.forecast(steps=14)
                p_t_14_sarimax = float(forecast.iloc[-1])  # 14-day ahead prediction
                trend_multiplier = 1.0 - (LAMBDA_ARIMA * (p_t_14_sarimax - p_t) / p_t) if p_t != 0 else 1.0
                logger.debug(f"  {model_id[:40]} ({sub_category}): SARIMAX forecast P_t+14={p_t_14_sarimax:.2f} (live P_t={p_t:.2f})")
                sarimax_success = True
            except Exception as e:
                logger.warning(f"  {model_id[:40]} ({sub_category}): SARIMAX forecast failed ({e}), using price-ratio fallback")
        
        if not sarimax_success:
            # No SARIMAX model for this category or inference failed — use price-ratio heuristic
            p_t_14 = float(c.get("forecasted_price", p_t))
            trend_multiplier = 1.0 - (LAMBDA_ARIMA * (p_t_14 - p_t) / p_t) if p_t != 0 else 1.0
            
        # SHAP_cos — built from live KernelExplainer output (not CSV columns)
        shap_dict = live_shap_dicts[idx]          # dict: FEATURE_COL → shap_value
        cand_shap_vector = np.array([float(shap_dict.get(feat, 0.0)) for feat in FEATURE_COLS])
        
        # Requirement 4 Fix: Compare to cluster-specific mean instead of global mean
        cluster_shap_means = app_state.get("cluster_shap_means")
        if cluster_shap_means:
            target_mean = cluster_shap_means[predicted_cluster_idx]
        else:
            target_mean = mean_shap_vector # Fallback
            
        shap_cos = cosine_similarity(cand_shap_vector, target_mean)
        
        # Store computed drivers back onto the candidate for observability
        c["shap_drivers"] = shap_dict

        # Save signals and compute COMPOSITE INTELLIGENT SCORE
        signals = {
            "S": S,
            "Gap_SVM": gap_svm,
            "mu_predicted": mu_predicted,
            "trend_multiplier": trend_multiplier,
            "SHAP_cos": shap_cos
        }
        c["signals"] = signals
        c["intelligent_score"] = calculate_intelligent_score(signals)
        c["shap_vector"] = cand_shap_vector  # Store for FAISS search (Req 3)
    
    # 2. DECISION ROUTER (Reason & Act State)
    logger.info("Starting decision routing...")
    for c in candidates:
        if len(dispatched_candidates) >= QUOTA_LIMIT:
            logger.info(f"Quota fulfilled ({QUOTA_LIMIT} approved). Halting loop.")
            break
            
        model_id = c.get("model_id", "Unknown")
        S = c["signals"]["S"]
        gap_svm = c["signals"]["Gap_SVM"]
        mu_predicted = c["signals"]["mu_predicted"]
        trend_multiplier = c["signals"]["trend_multiplier"]
        shap_cos = c["signals"]["SHAP_cos"]
        cand_shap_vector = c["shap_vector"]
        
        # Path 7: Hard Reject
        if S < BASE_THRESHOLD:
            c["routing_path"] = "Path 7 (Hard Reject)"
            continue
            
        # Path 4: Human Review
        if gap_svm < MIN_MARGIN or mu_predicted < MIN_PROB:
            c["routing_path"] = "Path 4 (Human Review)"
            dead_letter_queue.append(c)
            continue
            
        # Path 3/5/6: The RAG Matrix
        if abs(S - BORDERLINE_S) < 0.2:
            try:
                distances, indices = faiss_index.search(np.array([cand_shap_vector], dtype=np.float32), k=5)
                avg_dist = np.mean(distances[0])
                historical_labels = app_state["historical_labels"]
                neighbor_labels = [historical_labels[idx] for idx in indices[0]]
                buy_votes = sum([1 for label in neighbor_labels if label == "Deflating Arbitrage"])
            except Exception as e:
                avg_dist = FAISS_TOLERANCE + 1
                buy_votes = 0

            if avg_dist > FAISS_TOLERANCE:
                if shap_cos >= RELIABILITY_THRESHOLD:
                    c["routing_path"] = "Path 6 (RAG Zero-Success Approve)"
                    dispatched_candidates.append(c)
                else:
                    c["routing_path"] = "Path 6 (RAG Zero-Success Reject)"
                continue
            elif buy_votes == 2: # Fix: Only 2 votes (split/minority) go to Path 5. 3 is a majority.
                vol_30d = float(c.get("vol_30d", 50)) 
                if trend_multiplier > 1.0 and ((trend_multiplier - 1.0) * 100 > vol_30d):
                    c["routing_path"] = "Path 5 (RAG Tie Approve)"
                    dispatched_candidates.append(c)
                else:
                    c["routing_path"] = "Path 5 (RAG Tie Reject)"
                    dead_letter_queue.append(c)
                continue
            else:
                if buy_votes > 2:
                    c["routing_path"] = "Path 3 (RAG Standard Approve)"
                    dispatched_candidates.append(c)
                else:
                    c["routing_path"] = "Path 3 (RAG Standard Reject)"
                continue
                
        # Path 2: SHAP Re-check
        if S >= HIGH_S_THRESHOLD and shap_cos < RELIABILITY_THRESHOLD:
            S_penalized = S * 0.5
            if S_penalized < BASE_THRESHOLD:
                c["routing_path"] = "Path 2 (SHAP Re-check Reject)"
            else:
                c["routing_path"] = "Path 2 (SHAP Re-check Approve)"
                dispatched_candidates.append(c)
            continue
            
        # Path 1: Direct Dispatch
        if S >= HIGH_S_THRESHOLD and shap_cos >= RELIABILITY_THRESHOLD:
            c["routing_path"] = "Path 1 (Direct Dispatch)"
            dispatched_candidates.append(c)
            continue
            
        c["routing_path"] = "Catch-all (Human Review)"
        dead_letter_queue.append(c)
        
    logger.info(f"Loop finished. Dispatched: {len(dispatched_candidates)}, DLQ: {len(dead_letter_queue)}")
    return dispatched_candidates, dead_letter_queue
