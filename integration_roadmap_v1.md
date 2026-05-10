# Master Engineering Roadmap: Unified Dashboard-Controlled Pipeline (v1.0)

## Objective
Transition the "Wise Purchaser" system from a decoupled collection of Python scripts using disk-based I/O (CSVs) to a unified, event-driven FastAPI/PostgreSQL architecture. The system will be controlled via a central Streamlit/FastAPI dashboard with all components operating "in-memory" or via the central database. **Static mockups and hardcoded logic are strictly forbidden.**

---

## 1. Data Ingestion & ETL Layer

### Hybrid Scraper (Web Scrapper)
* **Current State:** Standalone Selenium/Request scripts that save scraped data into local JSON/CSV files (e.g., `payload/` directory).
* **Target State:** FastAPI-triggered service that scrapes market data and writes directly to the `RawScrapedData` PostgreSQL table.
* **Input Modifications:** Remove `config.json` file dependency. Accept `batch_id`, `category`, and `target_count` as parameters from the FastAPI orchestrator.
* **Output Modifications:** Remove all `df.to_csv()` or `json.dump()` calls. Return a list of Pydantic `RawProduct` models for bulk database insertion.
* **Connected to Workflow:** Triggered by the "Start Batch" button on the Dashboard. Feeds the `RawScrapedData` table for the ETL Pipeline.
* **Reason to Change:** To eliminate file-system latency and ensure data consistency across the distributed pipeline.
* **Unit Testing (Isolated):** Execute scraper for 5 items, mock the DB connection, and assert that the returned list of dictionaries matches the `RawProduct` schema exactly.
* **Integration Testing:** Verify that calling the scraper via the FastAPI endpoint successfully creates a new record in `RawScrapedData` with a valid `batch_id`.

### ETL Pipeline (Feature Extractor)
* **Current State:** Reads `raw_data.csv`, applies regex for hardware extraction, and outputs a feature-complete `processed_data.csv`.
* **Target State:** A database-resident transformation function that pulls from `RawScrapedData` and populates the `ProcessedProducts` table.
* **Input Modifications:** Remove `pd.read_csv`. Accept a `batch_id` and query the database for all raw records associated with that batch.
* **Output Modifications:** Remove `df.to_csv()`. Perform a bulk `UPSERT` into the `ProcessedProducts` table, including the 53 required features for the ML layer.
* **Connected to Workflow:** Triggered automatically upon completion of the Scraper task. Feeds the ML Forecasting layer.
* **Reason to Change:** Mandatory for the 00:00 UTC batch cycle to operate without manual file movement.
* **Unit Testing (Isolated):** Pass a mocked raw DB record (Laptop with '8GB RAM') and assert the extracted `ram_capacity` integer is `8`.
* **Integration Testing:** Confirm that the output of the ETL layer matches the input dimensions (53 features) expected by the SARIMAX/LightGBM model.

---

## 2. ML Forecasting Layer

### ML Forecasting Engine (SARIMAX/LightGBM)
* **Current State:** Loads `.joblib` models to generate 14-day forecasts and saves them to a temporary CSV.
* **Target State:** Loaded into FastAPI `app.state` at startup. Performs in-memory inference on the `ProcessedProducts` table. **Must prioritize discovery of `.onnx` versions of the models.**
* **Input Modifications:** Remove CSV loading. Load models into memory once. Fetch features from `ProcessedProducts` using the current `batch_id`.
* **Output Modifications:** Update the existing database records in `ProcessedProducts` with `price_t_plus_14` and `prediction_confidence`.
* **Connected to Workflow:** Triggered by the ETL completion signal. Feeds the SHAP Explanation engine.
* **Reason to Change:** Loading 100MB+ models per request is inefficient. In-memory state allows sub-second inference for the Top-20 funnel.
* **Unit Testing (Isolated):** Mock a 53-feature vector and assert that the model returns a float for `price_t_plus_14` within a reasonable range (0.5x to 2.0x of current price).
* **Integration Testing:** Verify that the forecast values are correctly written back to the database and are accessible by the ReAct Router.

### SHAP Explanation Engine
* **Current State:** Calculates SHAP values for top candidates and saves plots to disk.
* **Target State:** Generates a `shap_vector` (array of floats) and stores it as a JSONB field in the database.
* **Input Modifications:** Remove dependencies on local CSVs. Accept the model and data row directly from the Forecasting Engine.
* **Output Modifications:** Instead of saving `.png` files, return the raw SHAP importance values for the top 5 features.
* **Connected to Workflow:** Executes immediately after Forecasting. Feeds the "Observe" state of the ReAct Router.
* **Reason to Change:** The ReAct router requires the `SHAP_cos` signal (cosine similarity to historical drivers) which must be computed from raw vectors, not images.
* **Unit Testing (Isolated):** Provide a model and a sample row; assert that the output is a dictionary of feature names and their corresponding SHAP floats.
* **Integration Testing:** Ensure the `shap_vector` is successfully stored in the `daily_recommendations` table for LLM consumption.

---

## 3. Agentic Verification Layer (ReAct)

### ReAct Decision Router
* **Current State:** Logic is partially mocked in `mock_state_loader.py` and `react_router.py`.
* **Target State:** Fully dynamic 7-path routing engine utilizing the 5 mathematical signals ($S$, $\text{Gap}_{SVM}$, $\mu$, $\text{ARIMA}_{mult}$, $\text{SHAP}_{cos}$).
* **Input Modifications:** Replace `mock_state_loader` with live queries to `app.state` for FCM centroids and SVM weights.
* **Output Modifications:** Instead of printing to console, it must tag each candidate with a `routing_path` ID and a `status` (Approved/Rejected/Pending).
* **Connected to Workflow:** Final gatekeeper. Triggered by SHAP completion. Feeds the LLM Contextualizer and the B2C Email Layer.
* **Reason to Change:** To achieve the "Autonomous Agentic" requirement of the Phase 4 blueprint.
* **Unit Testing (Isolated):** Set signals to specific values (e.g., $S < \text{Threshold}$) and assert that Path 7 (Hard Reject) is triggered.
* **Integration Testing:** Verify that "Approved" items are correctly inserted into the `daily_recommendations` table with their specific routing logic justification.

### Drift Monitor (Outer Loop)
* **Current State:** Non-existent/Manual observation of model performance.
* **Target State:** Weekly Cron job within FastAPI that calculates system drift and triggers re-clustering.
* **Input Modifications:** Queries the last 7 days of `Gap_SVM` and FCM membership probabilities from the database.
* **Output Modifications:** Updates `app.state` with newly trained model weights without restarting the server.
* **Connected to Workflow:** Periodically monitors the Database. Triggers the "Retrain" workflow.
* **Reason to Change:** Essential for maintaining accuracy in volatile market conditions (Drift Detection).
* **Unit Testing (Isolated):** Feed a set of degrading signals and assert that the `trigger_retraining` flag is set to `True`.
* **Integration Testing:** Ensure that after retraining, the live inference engine uses the new centroids stored in `app.state`.

---

## 4. Output & Dashboard Layer

### B2C Action Layer (Email/Dispatch)
* **Current State:** Reads `recommendations.json` and sends emails via SendGrid.
* **Target State:** Event-driven service that triggers upon the ReAct loop's "Batch Complete" event.
* **Input Modifications:** Remove JSON file reading. Query `daily_recommendations` for records with `status = 'Approved'` and `emailed = False`.
* **Output Modifications:** Update the `emailed` boolean in the DB upon successful SendGrid dispatch.
* **Connected to Workflow:** Final step of the daily pipeline.
* **Reason to Change:** To prevent duplicate emails and ensure a reliable audit trail of what was sent to users.
* **Unit Testing (Isolated):** Mock the SendGrid API and assert that the email body contains the LLM-generated justification.
* **Integration Testing:** Verify that after the ReAct loop finishes, the `subscribers` table is queried and exactly $N$ emails are dispatched.

### Central Management Dashboard (Streamlit)
* **Current State:** Displays static graphs or mock data.
* **Target State:** Real-time observability platform for the FastAPI backend.
* **Input Modifications:** Replace all local file reads with REST API calls to the FastAPI backend (`/metrics`, `/logs`, `/trigger`).
* **Output Modifications:** Add "Kill Switch" and "Manual Retrain" buttons that send POST requests to the orchestrator.
* **Connected to Workflow:** Overlays the entire system. Acts as the UI for the Lead PM.
* **Reason to Change:** To provide the required "6 required zones" of visibility for the academic defense.
* **Unit Testing (Isolated):** Assert that clicking the "Refresh" button updates the `st.metric` components via a mocked API response.
* **Integration Testing:** Confirm that clicking "Start Batch" in the Dashboard initiates the Scraper on the server and begins logging to the Dashboard's console view.
## 5. Strict Compliance & Integrity Rules

### Zero-Mock Policy
*   **Requirement:** Hardcoded signals, placeholder metrics, or mocked state loaders are strictly prohibited in the final implementation.
*   **Enforcement:** Every component must be dynamically connected to either the PostgreSQL/SQLite database or the FastAPI `app.state`.
*   **Rationale:** To ensure 100% architectural compliance for the academic defense and real-world reliability.

### ONNX Model Discovery
*   **Requirement:** The ML and Verification layers must prioritize searching for `.onnx` model files in the designated `/models` directory before falling back to other formats.
*   **Logic:** Implement a systematic lookup for `*.onnx` files to leverage cross-platform performance and standardized serialization.

### Temporal Data Continuity (The "Max + 1" Rule)
*   **Requirement:** All testing and live workflows must use real-world historical data. To maintain temporal integrity, the system must never use static timestamps for new batches.
*   **Implementation:** 
    1.  Query the target database for the `MAX(scrape_time)`.
    2.  Set the `current_scrape_time` for the incoming batch to `MAX(scrape_time) + 1`.
*   **Goal:** Ensure the SARIMAX/LightGBM models perceive a continuous time-series flow without data gaps or overlaps.

---

## 6. Structural Cleanup & Refactoring

### ETL Folder Standardization
*   **Action:** The legacy `ETl` folder has been renamed to `ETL`.
*   **Refactor:** All internal import paths and script references must be updated to use the `ETL` namespace.

### Data Folder Centralization
*   **Action:** The `data` folder previously located in `src_integrated` has been moved to the root project directory.
*   **Usage:** This folder serves as the authoritative source for raw datasets and temporal test batches.

---

## 7. Documentation & Knowledge Protocol

### Phase-Based Documentation Requirement
*   **Rule:** Every developer assigned to a specific phase (e.g., Data Ingestion, ML Forecasting, etc.) is responsible for maintaining the system's "Source of Truth."
*   **Protocol:**
    1.  **Modify/Update:** Existing documentation in the `/docs` folder must be updated to reflect architectural changes (e.g., schema updates, API endpoint changes).
    2.  **Create:** If a new sub-system or module is introduced, a corresponding technical specification must be added to `/docs`.
    3.  **Contextual Integrity:** Documentation must include the "why" behind technical decisions, especially regarding how the component connects to the unified dashboard/database pipeline.
*   **Enforcement:** A phase is not considered "Complete" until the associated documentation in `/docs` is synchronized with the actual codebase.
