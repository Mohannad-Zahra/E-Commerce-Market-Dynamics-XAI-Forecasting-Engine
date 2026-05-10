import numpy as np

class MockSVM:
    def decision_function(self, X):
        # Mock decision function returning random distance to hyperplane
        return np.random.uniform(0.1, 5.0, size=(X.shape[0],))

class MockFAISSIndex:
    def __init__(self, dimension):
        self.dimension = dimension
        
    def search(self, query_vectors, k):
        # Mock FAISS search returning distances and indices
        num_queries = query_vectors.shape[0]
        distances = np.random.uniform(0.0, 2.0, size=(num_queries, k))
        indices = np.random.randint(0, 1000, size=(num_queries, k))
        return distances, indices

def load_mock_state():
    """
    Loads a mocked representation of the in-memory Global State (app.state)
    """
    n_features = 5 # E.g., scaled [P_t, P_t+14, V, mu_14d, M_age]
    n_shap_features = 15 # Based on the 15 shap_ columns in the dataset
    n_clusters = 3 # Let's assume 3 clusters for FCM
    
    # 1. Mock SVM RBF Model
    svm_model = MockSVM()
    
    # 2. Mock FCM Centroids
    # Shape: [n_clusters, n_features]
    fcm_centroids = np.random.uniform(0, 1, size=(n_clusters, n_features))
    
    # 3. Mock Mean SHAP Vector (Implicit RAG)
    # Shape: [n_shap_features]
    mean_shap_vector = np.random.uniform(-0.5, 0.5, size=(n_shap_features,))
    
    # 4. Mock FAISS Index (Explicit RAG)
    # FAISS usually indexes the SHAP vectors or the full feature set. Let's assume SHAP vectors.
    faiss_index = MockFAISSIndex(dimension=n_shap_features)
    
    state = {
        "svm_model": svm_model,
        "fcm_centroids": fcm_centroids,
        "mean_shap_vector": mean_shap_vector,
        "faiss_index": faiss_index
    }
    
    return state

if __name__ == "__main__":
    state = load_mock_state()
    print("Mocked State Loaded Successfully.")
    print(f"SVM Model: {state['svm_model']}")
    print(f"FCM Centroids Shape: {state['fcm_centroids'].shape}")
    print(f"Mean SHAP Vector Shape: {state['mean_shap_vector'].shape}")
    print(f"FAISS Index Dimension: {state['faiss_index'].dimension}")
