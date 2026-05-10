import os
import sys
import numpy as np
import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Recommendation system"))
from react_router import run_react_loop, SHAP_COLS

class MockScaler:
    def __init__(self, val=0.5):
        self.val = val
    def transform(self, X):
        # Return self.val or just pass X if we want to manually control S
        return np.array([[X[0][0]]])

class MockFCM_Scaler:
    def transform(self, X):
        return X

class MockSVM:
    def __init__(self, gap_val=1.0):
        self.gap_val = gap_val
    def decision_function(self, X):
        # We can dynamically read a field from X if we want to customize per candidate
        # But wait, df_x is what is passed:
        # Let's just use the current_price as a hack to pass gap_svm
        return [X.iloc[0]['current_price']]

# Monkey patch skfuzzy because we can't easily mock cmeans_predict otherwise
import skfuzzy as fuzz
def mock_cmeans_predict(test_data, cntr_guess, c, error, maxiter):
    # test_data has shape [n_features, n_data]
    # We used current_price to pass gap_svm. Let's use forecasted_price to pass mu_predicted
    mu = test_data.iloc[1, 0] # forecasted_price
    u = np.zeros((c, 1))
    u[0, 0] = mu
    return u, None, None, None, None, None

fuzz.cluster.cmeans_predict = mock_cmeans_predict

class MockFAISS:
    def search(self, X, k):
        # Use shap_delta_p_7d for avg_dist and shap_delta_p_14d for buy_votes (1 means 3 votes, 0 means 2 votes, -1 means 0 votes)
        dist = X[0][1] # shap_delta_p_7d
        votes_flag = X[0][2] # shap_delta_p_14d
        
        distances = [[dist] * k]
        if votes_flag == 1:
            indices = [[0, 2, 4, 1, 3]] # 3 even indices (buy votes)
        elif votes_flag == 0:
            indices = [[0, 2, 1, 3, 5]] # 2 even indices (tie)
        else:
            indices = [[1, 3, 5, 7, 9]] # 0 even indices
            
        return np.array(distances), np.array(indices)

def run_test():
    app_state = {
        "svm_model": MockSVM(),
        "fcm_centroids": np.array([[0]*5]*2),
        "fcm_scaler": MockFCM_Scaler(),
        "mean_shap_vector": np.array([1.0] + [0.0]*14), # perfect match if first feature is 1.0
        "faiss_index": MockFAISS(),
        "r_score_scaler": MockScaler()
    }
    
    # We will construct candidates where we inject the desired signal values:
    # r_score -> S
    # current_price -> gap_svm
    # forecasted_price -> mu_predicted
    # shap_compute_potential -> controls shap_cos (1.0 = cos 1.0, 0.0 = cos 0.0)
    # shap_delta_p_7d -> faiss dist
    # shap_delta_p_14d -> faiss votes
    
    candidates = [
        # 1. Path 7 (Hard Reject): S < 0.2
        {"model_id": "Cand_Path_7", "r_score": 0.1, "current_price": 1.0, "forecasted_price": 0.8, "shap_drivers": {}},
        
        # 2. Path 4 (Human Review): S=0.5, gap_svm < 0.5
        {"model_id": "Cand_Path_4", "r_score": 0.5, "current_price": 0.2, "forecasted_price": 0.8, "shap_drivers": {}},
        
        # 3. Path 6 (RAG Zero-Success Approve): S=0.5, gap>=0.5, mu>=0.4, dist > 1.0, shap_cos >= 0.6
        {"model_id": "Cand_Path_6", "r_score": 0.5, "current_price": 1.0, "forecasted_price": 0.8, 
         "shap_drivers": {"shap_compute_potential": 1.0, "shap_delta_p_7d": 2.0}},
         
        # 4. Path 5 (RAG Tie Approve): S=0.5, dist <= 1.0, buy_votes == 2, arima_mult > 1 (P_t=1, P_t_14=0.5 -> arima=1-(2*(0.5-1)/1)=2.0 > 1.0), (arima-1)*100 > vol_30d
        {"model_id": "Cand_Path_5", "r_score": 0.5, "current_price": 1.0, "forecasted_price": 0.5, "vol_30d": 50,
         "shap_drivers": {"shap_compute_potential": 1.0, "shap_delta_p_7d": 0.5, "shap_delta_p_14d": 0.0}},
         
        # 5. Path 3 (RAG Standard Approve): S=0.5, dist <= 1.0, buy_votes = 3
        {"model_id": "Cand_Path_3", "r_score": 0.5, "current_price": 1.0, "forecasted_price": 0.8,
         "shap_drivers": {"shap_compute_potential": 1.0, "shap_delta_p_7d": 0.5, "shap_delta_p_14d": 1.0}},
         
        # 6. Path 2 (SHAP Re-check Approve): S=0.8, shap_cos < 0.6
        {"model_id": "Cand_Path_2", "r_score": 0.8, "current_price": 1.0, "forecasted_price": 0.8,
         "shap_drivers": {"shap_compute_potential": 0.0}},
         
        # 7. Path 1 (Direct Dispatch): S=0.8, shap_cos >= 0.6
        {"model_id": "Cand_Path_1", "r_score": 0.8, "current_price": 1.0, "forecasted_price": 0.8,
         "shap_drivers": {"shap_compute_potential": 1.0}}
    ]
    
    print("Testing ReAct Loop with 7 Synthetic Candidates...")
    # Increase quota limit temporarily to process all 7
    import react_router
    react_router.QUOTA_LIMIT = 10 
    
    dispatched, dlq = run_react_loop(candidates, app_state)
    
    print("\\nResults:")
    for d in dispatched:
        print(f"[DISPATCHED] {d['model_id']} -> {d.get('routing_path')}")
    for d in dlq:
        print(f"[DLQ]        {d['model_id']} -> {d.get('routing_path')}")

if __name__ == '__main__':
    run_test()
