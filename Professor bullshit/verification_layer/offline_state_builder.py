import pandas as pd
import numpy as np
import faiss
import skfuzzy as fuzz
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
import os
import sys

# Ensure Recommendation system path is accessible for state_detector logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Recommendation system")))

from state_detector import FEATURE_COLS, SVM_PARAMS, label_logic

# Use the correct SHAP columns
SHAP_COLS = [
    'shap_compute_potential', 'shap_delta_p_7d', 'shap_delta_p_14d', 
    'shap_delta_p_1d', 'shap_vol_30d', 'shap_official_egp_usd', 
    'shap_cpi_inflation', 'shap_is_major_sale_period', 
    'shap_competitor_scarcity_count', 'shap_volume_weight', 
    'shap_D_months', 'shap_k', 'shap_import_lambda', 
    'shap_missing_release_date', 'shap_base_expected_price'
]

def load_offline_state(st=None):
    """
    Trains the actual offline ReAct models on the background dataset.
    Returns the real app_state to be used by the live router.
    """
    csv_path = os.path.join(os.path.dirname(__file__), "..", "ECom_Forecast_XAI_data.csv")
    msg = f"Loading 1000 background rows from {csv_path} for offline training..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    # Read only 1000 rows because the file is 650MB and would crash memory/time
    df = pd.read_csv(csv_path, nrows=1000)

    # 1. Preprocessing for Models (Deterministic instead of random)
    # If price_t is missing, we derive it from price_t_plus_14 and delta_p_14d
    # delta_p_14d = (P_t+14 - P_t) / P_t  => P_t = P_t+14 / (1 + delta_p_14d)
    if "current_price" not in df.columns:
        df["current_price"] = df["price_t_plus_14"] / (1 + df["delta_p_14d"].fillna(0))
    
    if "price_14d_avg" not in df.columns:
        # Simple heuristic: midway between price_t and price_t+7
        p_t_7 = df["price_t_plus_14"] / (1 + (df["delta_p_14d"] - df["delta_p_7d"]).fillna(0))
        df["price_14d_avg"] = (df["current_price"] + p_t_7) / 2
        
    df["forecasted_price"] = df["price_t_plus_14"]
    df["volatility_score"] = 100 - df["predicted_stability_score"]
    df["months_since_release"] = df["D_months"]
    
    # We need an r_score for labelling the SVM
    from ranking_engine import calculate_r_score
    df["r_score"] = calculate_r_score(df)
    
    # 2. Train Real SVM Classifier
    msg = "Training Real SVM Pipeline on Background Data..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    X_train = df[FEATURE_COLS].fillna(0)
    y_train = df.apply(label_logic, axis=1)

    svm_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("svm", SVC(**SVM_PARAMS)),
    ])
    svm_pipeline.fit(X_train, y_train)

    # 3. Train Real FCM (Fuzzy C-Means)
    msg = "Computing FCM Centroids via skfuzzy..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    scaler_fcm = StandardScaler()
    X_scaled = scaler_fcm.fit_transform(X_train).T # skfuzzy expects [n_features, n_data]
    
    # n_clusters = 3
    cntr, u, u0, d, jm, p, fpc = fuzz.cluster.cmeans(
        X_scaled, c=3, m=2.0, error=0.005, maxiter=1000, init=None
    )
    # cntr has shape [n_clusters, n_features]

    # 4. Compute Mean SHAP Vector
    msg = "Extracting Mean SHAP Vector for Implicit RAG..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    valid_shap = df[SHAP_COLS].fillna(0).values
    mean_shap_vector = np.mean(valid_shap, axis=0)

    # 5. Build Real FAISS Index
    msg = "Embedding Contexts into FAISS K-NN Index..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    dimension = len(SHAP_COLS)
    faiss_index = faiss.IndexFlatL2(dimension)
    # Convert vectors to float32 for FAISS
    vectors_f32 = np.ascontiguousarray(valid_shap.astype(np.float32))
    faiss_index.add(vectors_f32)
    
    # Store labels for RAG Majority Vote (Requirement 3 Fix)
    # We map the indices to the actual labels from the background dataset
    historical_labels = y_train.values

    # 6. Fit R_score MinMax Scaler (To mathematically isolate Layer 1)
    msg = "Fitting R_score MinMax Scaler..."
    if st: st.write("✅ " + msg)
    else: print(msg)
    
    r_score_scaler = MinMaxScaler()
    r_score_scaler.fit(df[["r_score"]])

    state = {
        "svm_model": svm_pipeline,
        "fcm_centroids": cntr,
        "fcm_scaler": scaler_fcm,
        "mean_shap_vector": mean_shap_vector,
        "faiss_index": faiss_index,
        "historical_labels": historical_labels, # Critical for Path 3/5/6
        "r_score_scaler": r_score_scaler,
        "background_df": df, # Useful for drift detection
        "fpc": fpc # Requirement 7 (Cluster Health)
    }
    
    msg = "Offline State successfully trained and loaded."
    if st: st.write("✨ " + msg)
    else: print(msg)
    
    return state

if __name__ == "__main__":
    app_state = load_offline_state()
