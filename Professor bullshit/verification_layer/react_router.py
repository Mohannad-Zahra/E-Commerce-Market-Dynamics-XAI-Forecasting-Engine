import logging
import numpy as np
import skfuzzy as fuzz

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

SHAP_COLS = [
    'shap_compute_potential', 'shap_delta_p_7d', 'shap_delta_p_14d', 
    'shap_delta_p_1d', 'shap_vol_30d', 'shap_official_egp_usd', 
    'shap_cpi_inflation', 'shap_is_major_sale_period', 
    'shap_competitor_scarcity_count', 'shap_volume_weight', 
    'shap_D_months', 'shap_k', 'shap_import_lambda', 
    'shap_missing_release_date', 'shap_base_expected_price'
]

def calculate_intelligent_score(signals):
    """
    Requirement 1: The Intelligent Score.
    A composite of exactly 5 independent signals: 
    S (severity), Gap(SVM) (confidence), mu(predicted) (FCM), ARIMA (trend), and SHAP (cosine).
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
        max(signals["ARIMA_mult"], 0.001), 
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
    dispatched_candidates = []
    dead_letter_queue = []
    
    svm_model = app_state["svm_model"]
    fcm_centroids = app_state["fcm_centroids"]
    mean_shap_vector = app_state["mean_shap_vector"]
    faiss_index = app_state["faiss_index"]
    
    # 1. SIGNAL COMPUTATION (Observe State) - PRE-COMPUTE FOR ALL
    logger.info(f"Pre-computing signals for {len(candidates)} candidates...")
    for c in candidates:
        model_id = c.get("model_id", "Unknown")
        
        # S: Normalized R_score using the trained offline scaler
        raw_r_score = float(c.get("r_score", 0.0))
        r_score_scaler = app_state["r_score_scaler"]
        S = float(r_score_scaler.transform([[raw_r_score]])[0][0])
        
        v_score = float(c.get("volatility_score", 100 - c.get("predicted_stability_score", 50)))
        m_age = float(c.get("months_since_release", c.get("D_months", 0)))
        
        import pandas as pd
        from state_detector import FEATURE_COLS
        
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
        except Exception as e:
            mu_predicted = 0.0
        
        # ARIMA_mult
        p_t = float(c.get("current_price", 1))
        p_t_14 = float(c.get("forecasted_price", p_t))
        arima_mult = 1.0 - (LAMBDA_ARIMA * (p_t_14 - p_t) / p_t) if p_t != 0 else 1.0
            
        # SHAP_cos
        shap_dict = c.get("shap_drivers", {})
        cand_shap_vector = np.array([float(shap_dict.get(col, 0.0)) for col in SHAP_COLS])
        shap_cos = cosine_similarity(cand_shap_vector, mean_shap_vector)
        
        # Save signals and compute COMPOSITE INTELLIGENT SCORE
        signals = {
            "S": S,
            "Gap_SVM": gap_svm,
            "mu_predicted": mu_predicted,
            "ARIMA_mult": arima_mult,
            "SHAP_cos": shap_cos
        }
        c["signals"] = signals
        c["intelligent_score"] = calculate_intelligent_score(signals)
        c["shap_vector"] = cand_shap_vector # Store for later FAISS search
    
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
        arima_mult = c["signals"]["ARIMA_mult"]
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
            elif buy_votes == 2 or buy_votes == 3:
                vol_30d = float(c.get("vol_30d", 50)) 
                if arima_mult > 1.0 and ((arima_mult - 1.0) * 100 > vol_30d):
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
