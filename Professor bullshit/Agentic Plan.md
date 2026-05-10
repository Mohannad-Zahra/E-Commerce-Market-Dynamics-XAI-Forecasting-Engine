# Phase 4: Autonomous Agentic Verification & Recommendation Layer

**Sub-System:** Category-Conditioned Arbitrage Pipeline (Target: Laptops)
**Execution Trigger:** 00:00 UTC Daily Batch Cycle Halt for now and do Special Execution for testing
**Architecture Paradigm:** ReAct Agentic Loop + Asynchronous MLOps

---

## 1. System State & Inputs (The Orchestration Layer)

The legacy decoupled CSV pipeline is deprecated. The system relies on a centralized persistence layer (PostgreSQL) and an in-memory FastAPI application state to achieve sub-3-second inference without disk I/O bottlenecks.

### 1.1 In-Memory Global State (`app.state`)
Loaded upon FastAPI startup. Generated exclusively by the Offline Outer Loop.
* `svm_model`: Pre-trained RBF classifier weights.
* `fcm_centroids`: Spatial coordinates defining the 'Deflating Arbitrage' cluster.
* `mean_shap_vector`: The ideal economic driver profile (Implicit RAG document store).
* `faiss_index`: Embedded K-NN history of previously verified recommendations (Explicit RAG).

### 1.2 Live Batch Database Inputs
The upstream ETL pipeline populates the `raw_market_data` table before 00:00 UTC.

| Variable | System Name | Data Type | Origin | Description |
| :--- | :--- | :--- | :--- | :--- |
| $P_{t}$ | `current_price` | `Float` | Track B Scraper | Live price extracted during batch cycle. |
| $\hat{P}_{t+14}$ | `price_t_plus_14` | `Float` | SARIMAX/LightGBM | 14-day predicted price trajectory. |
| $S_{shap}$ | `shap_vector` | `Array[Float]` | `shap.TreeExplainer` | Matrix of SHAP drivers (e.g., `shap_delta_p_14d`, `shap_vol_30d`). |
| $V$ | `vol_30d` | `Float` | Feature Engineering | 30-day historical volatility index. |

---

## 2. The 00:00 UTC Inference Pipeline

This sequence executes synchronously per category to guarantee system integrity and quota fulfillment.

### Step 1: Vectorized Gating (The Top-20 Funnel)
**[Goal]** Prevent exponential compute scaling by isolating only mathematically viable assets.
* **Action:** Query `raw_market_data` for the target category.
* **Computation:** Apply the vectorized heuristic $R_{score}$ (Arbitrage Potential) across all N rows.
* **Output:** `CandidateArray[20]` containing the top 20 ranked objects.

### Step 2: Signal Pre-Computation (The "Observe" State)
**[Goal]** Generate the 5-dimensional mathematical proof required for the ReAct router.
* **Action:** Iterate over `CandidateArray[20]` via asynchronous processing (`asyncio.gather`).
* **Computation Matrix:**
    1.  **Severity ($S$):** Normalized $R_{score}$ heuristic.
    2.  **Confidence ($\text{Gap}_{SVM}$):** `svm.decision_function(X)` >> Extracts absolute distance to hyperplane.
    3.  **FCM Membership ($\mu_{predicted}$):** `skfuzzy.cmeans_predict(X)` >> Extracts maximum probability against `fcm_centroids`.
    4.  **Trend Multiplier ($\text{ARIMA}_{mult}$):** Continuous penalty/reward function derived from $P_{t}$ and $\hat{P}_{t+14}$.
    5.  **Implicit RAG ($\text{SHAP}_{cos}$):** Cosine similarity between candidate's `shap_vector` and `mean_shap_vector`.
* **Output:** Appends the `SignalMatrix{5}` to each Candidate object.

### Step 3: The ReAct Decision Router (The "Reason & Act" State)
**[Goal]** Autonomous routing based on real-time signal evaluation. Loops sequentially until `accepted_count == 5` or buffer is exhausted.

**[!] Routing Logic (Evaluated strictly in this order):**
1.  **Path 7 (Hard Reject):**
    >> *Condition:* $S < \text{Base Threshold}$.
    >> *Action:* Drop candidate. Move to next index.
2.  **Path 4 (Human Review):**
    >> *Condition:* $\text{Gap}_{SVM} < \text{Min Margin}$ OR $\mu_{predicted} < \text{Min Prob}$.
    >> *Reason:* Market state unrecognizable; high risk of hallucinated arbitrage.
    >> *Action:* `INSERT INTO pending_review` (Dead-Letter Queue). Bypass email trigger.
3.  **Path 3/5/6 (The RAG Matrix):**
    >> *Condition:* $S \approx \text{Borderline}$.
    >> *Action:* Query `faiss_index` (Explicit RAG).
    * **Branch 6 (Zero-Success):** FAISS Euclidean distance exceeds tolerance. Fallback to evaluating $\text{SHAP}_{cos}$ baseline.
    * **Branch 5 (Tie):** FAISS returns conflicting votes. Evaluate $\text{ARIMA}_{mult}$. If trajectory exceeds historical `vol_30d` negatively >> **Approve**. If positive >> **Human Review**.
    * **Branch 3 (Standard):** FAISS majority vote confirms "Buy" >> **Approve**.
4.  **Path 2 (SHAP Re-check):**
    >> *Condition:* $S \geq \text{Threshold}$ BUT $\text{SHAP}_{cos} < \text{Reliability Threshold}$.
    >> *Reason:* Arbitrage exists, but drivers deviate from historically safe patterns.
    >> *Action:* Apply geometric penalty to $S$. Re-evaluate state.
5.  **Path 1 (Direct Dispatch):**
    >> *Condition:* High $S$ AND High $\text{SHAP}_{cos}$.
    >> *Action:* **Approve**.

### Step 4: LLM Contextualization & Persistence
**[Goal]** Generate transparent user justification driven by the specific routing path.
* **Trigger:** Executes only for Candidates tagged **Approve** in Step 3.
* **Action:** FastAPI constructs a JSON payload containing the candidate data and the *triggering path*. Sends POST request to the LLM endpoint.
    * *Constraint:* The LLM prompt is dynamically shaped by the path. (e.g., Path 5 approvals must explicitly mention conflicting historical data overridden by strong short-term forecasts).
* **Persistence:** `INSERT INTO daily_recommendations` (Candidate Data + LLM Output String).

### Step 5: Autonomous B2C Action
**[Goal]** Deliver the insight to the consumer.
* **Trigger:** Executes when the ReAct loop terminates.
* **Action:** Query `subscribers` table. Format data from `daily_recommendations` into an HTML template.
* **Dispatch:** SendGrid API POST request.

---

## 3. The Outer Loop (Drift Detection & Retraining)

**[Goal]** Prevent model decay in the highly volatile Egyptian economy. Operates entirely decoupled from the 00:00 UTC live cycle.

**[!] Trigger Mechanism (Weekly Cron):**
* **Signal 1:** Calculates a 7-day rolling average of $\text{Gap}_{SVM}$ across all batches. Triggers if median distance degrades by $X\%$.
* **Signal 2:** Measures Euclidean spatial drift between the live feature distributions and the baseline `fcm_centroids`.
* **Execution:** `IF (Signal 1 == TRUE) AND (Signal 2 == TRUE) THEN:`
    1.  Re-run Fuzzy C-Means clustering to establish new centroids.
    2.  Retrain SVM RBF classifier on new labels.
    3.  Recompute `mean_shap_vector`.
    4.  Rebuild FAISS K-NN index.
    5.  Reload `app.state` to propagate new weights to the live inference engine without system downtime.