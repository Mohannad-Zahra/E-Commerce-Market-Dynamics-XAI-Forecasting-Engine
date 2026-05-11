# Phase 4: Autonomous Recommendation Engine Architecture
**Sub-System:** Category-Conditioned Arbitrage Pipeline (Target: Laptops)
**Execution Trigger:** 00:00 UTC Daily Batch Cycle

---

### 1. System Inputs: De-Obfuscating the "Blackbox"

Before the recommendation engine executes, the upstream data engineering and forecasting layers must populate the database with the following deterministic schema.

| Variable | System Name | Data Type | Origin Pipeline | Description |
| :--- | :--- | :--- | :--- | :--- |
| $P_{t, i}$ | `current_price` | `Float` | Hybrid Web Scraper (Track B) | The live price extracted during the current batch cycle. |
| $\mu_{14d, i}$ | `price_14d_avg` | `Float` | Pandas Rolling Window | The 14-day trailing moving average of the product's price. |
| $M_{age, i}$ | `months_since_release`| `Integer` | Feature Engineering Layer | Calculated delta between `release_date` and `current_date`. |
| $\hat{P}_{t+14, i}$| `forecasted_price` | `Float` | FastAPI Inference Engine | The LightGBM/SARIMAX prediction for price at $t+14$. |
| $V_i$ | `volatility_score` | `Float` | Upstream Statistical Module | Normalized metric (0-100) indicating price instability. |
| $S_{shap, i}$ | `shap_vector` | `JSON Object` | `shap.TreeExplainer` Endpoint | Dictionary mapping features to their absolute SHAP values. |

---

### 2. The Laptop-Conditioned Arbitrage Formula ($R_{score}$)

The recommendation system ranks all laptops using a vectorized weighted sum of four discrete market variables.

$$R_{score, i, \text{laptop}} = \left[ \alpha_L \left( \frac{\hat{P}_{t+14, i} - P_{t, i}}{P_{t, i}} \right) \right] + \left[ \beta_L (100 - V_i) \right] + \left[ \gamma_L \left( \frac{\mu_{14d, i} - P_{t, i}}{\mu_{14d, i}} \right) \right] - \left[ \delta_L (M_{age, i}) \right]$$

**Term Explanations & Hyperparameters:**
1. **Price Momentum ($\alpha_L$):** $\left( \frac{\hat{P}_{t+14, i} - P_{t, i}}{P_{t, i}} \right)$. Calculates the percentage increase expected in the next 14 days. If the price is expected to rise by 20%, buying today captures maximum utility. $\alpha_L$ is set high for laptops, as capital outlay is massive.
2. **Stability Yield ($\beta_L$):** $(100 - V_i)$. Inverts the volatility score. A volatility of 90 (Red Zone) becomes a 10, penalizing the asset. A volatility of 10 (Green Zone) becomes a 90, rewarding the asset. $\beta_L$ controls risk appetite.
3. **Discount Depth ($\gamma_L$):** $\left( \frac{\mu_{14d, i} - P_{t, i}}{\mu_{14d, i}} \right)$. Measures immediate localized arbitrage. If the laptop averaged 40,000 EGP for 14 days and drops to 32,000 EGP today, this term spikes. $\gamma_L$ captures flash sales.
4. **Obsolescence Penalty ($\delta_L$):** $(M_{age, i})$. Subtracts raw points for every month since the laptop's release. $\delta_L$ is set aggressively for laptops, ensuring the system does not recommend obsolete, heavily discounted inventory.

---

### 3. The 00:00 UTC Execution Pipeline

This is the sequence of events that occurs autonomously during the daily batch cycle to fulfill the data flow and the academic rubric.

**Step 1: Batch Metric Vectorization**
*   **Action:** The backend queries `electronics_history.db` for the laptop category, extracting $P_{t}, \hat{P}_{t+14}, V, \mu_{14d}$, and $M_{age}$.
*   **Processing:** Calculates the $R_{score}$ for all laptops using vectorized NumPy operations. Ranks results descending.
*   **Output:** `Float64Array` of $R_{scores}$.
*   **Why:** Vectorization ensures execution in microseconds. Ranking mathematically is mandatory before passing data to heavier classification models.

**Step 2: Candidate Filtering & Classification (The State Detector)**
*   **Action:** The top 5 laptops with the highest $R_{score}$ are isolated. Their metrics are passed to the trained SVM RBF model.
*   **Input Shape:** `Array[5, n_features]` (Top 5 laptops, scaled numerical features).
*   **Processing:** `svm.predict(X_candidates)`
*   **Output:** `Array[String]` (e.g., `['Deflating Arbitrage', 'Hyper-Inflated']`).
*   **Why:** Fulfills the academic requirement for a supervised classifier state detector. The SVM acts as a final sanity check to confirm the heuristically scored laptops belong to a statistically valid "Buy" cluster.

**Step 3: LLM Pre-Computation (The Back-End Communicator)**
*   **Action:** For candidates classified as 'Deflating Arbitrage', extract their corresponding $S_{shap, i}$ vector.
*   **Input:** JSON Payload.
    ```json
    {
      "category": "laptop",
      "model": "Lenovo Legion 5",
      "current_price": 45000,
      "shap_drivers": {"egp_usd_rate": "+8.2", "price_lag_14d": "-12.5"}
    }
    ```
*   **Processing:** Send POST request to OpenAI/Anthropic API using a category-specific system prompt. Wrapped in a `try/except` block with exponential backoff to handle API timeouts.
*   **Output:** `String` (e.g., "The Lenovo Legion 5 represents a strong buy. EGP stabilization has halted price increases, while a 14-day local discount accounts for a significant price drop, ensuring immediate value.")
*   **Why:** Pre-computes the heavy API logic in the background so the front-end user experiences zero latency when viewing recommendations.

**Step 4: Persistence & UI Availability**
*   **Action:** The Top 5 candidates, along with their LLM-generated string, are inserted into the `daily_recommendations` SQL table.
*   **Input:** SQL `INSERT` statement.
*   **Output:** Successful database commit.
*   **Why:** Decouples the heavy batch processing from the live consumer React application.

**Step 5: The Autonomous API Action**
*   **Action:** A script queries the `subscribers` table for users opted into the "Laptops" alert list. It formats the `daily_recommendations` data into an HTML email.
*   **Input:** Email template + SQL fetch results.
*   **Processing:** SendGrid API POST request (bypassing native SMTP to ensure deliverability).
*   **Output:** HTTP 200 OK (Emails dispatched).
*   **Why:** Satisfies the strict requirement for an autonomous external API action triggered by model conditions.