# 05. Master Testing Queue & Monitoring Dashboard

This document details the architecture and implementation of the QA testing pipeline, designed to stress-test the ETL and ML layers using legacy data while bypassing the recommendation system.

## 1. The Master Testing Queue

### Purpose
To consolidate varied, messy legacy data from multiple retailers into a single, high-performance testing database for destructive processing.

### Database Architecture (`testing_queue.db`)
- **Type**: SQLite (Separated from the main production database).
- **Location**: `src_integrated/database/testing_queue.db`.
- **Schema**:
  - `raw_queue` Table:
    - `id` (INTEGER, PRIMARY KEY): Unique identifier for the row.
    - `payload` (TEXT/JSON): The raw, unmutated JSON string of the product data.

### Builder Logic (`testing_queue_builder.py`)
The builder scans the directory `oldData_need the scrape_time to update for it to work/` and performs the following:
1. **Format Detection**: Detects if a `.json` file is a standard JSON array, a single object, or a JSON-lines file.
2. **CSV Conversion**: Converts `.csv` files into JSON objects per row.
3. **Deduplication**: Currently performs a fresh overwrite of the `raw_queue` table on every run to ensure clean state.

---

## 2. Interactive Dashboard (Streamlit)

### Tech Stack
- **Framework**: Streamlit.
- **Path**: `src_integrated/dashboard.py`.
- **Environment Requirement**: Must be run with `PYTHONPATH="."` to ensure the `src_integrated` and `ETL` modules are discoverable.

### Core Features

#### A. Destructive Batch Processing
When "Trigger Batch Cycle" is clicked, the system consumes exactly 100 rows.
- **SQL Implementation**: Uses a transaction to ensure no rows are lost if the pipeline fails after extraction.
  ```sql
  BEGIN TRANSACTION;
  CREATE TEMPORARY TABLE batch_ids AS SELECT id FROM raw_queue LIMIT 100;
  SELECT * FROM raw_queue WHERE id IN (SELECT id FROM batch_ids);
  DELETE FROM raw_queue WHERE id IN (SELECT id FROM batch_ids);
  DROP TABLE batch_ids;
  COMMIT;
  ```

#### B. Dynamic Temporal Continuation
To prevent ML forecasting layers from breaking due to stale temporal features, the dashboard enforces "Simulated Continuity":
1. **Lookup**: Scans `forecast+shap/ECom_Forecast_XAI_data.csv`.
2. **Detection**: Extracts the `max(scrape_timestamp)`.
3. **Mutation**: Assigns `max_date + 1 day` to every row in the current batch.

#### C. Component I/O Inspector
Visualizes the data schema and sample row as it transforms through the pipeline layers:
1. **Raw Ingestion**: Validates raw JSON against `WebScrapperOutput` pydantic model. Handles currency parsing (e.g., "EGP 10,000" -> 10000.0).
2. **ETL Layer**: Uses the *actual* `FeatureExtractor` imported from `ETL/Data Pipiline`. Dynamically classifies items into `Electronics` (Laptops), `Phone`, `Tablet`, `Accessories`, `PC Components`, `Networking`, or `Gaming`. It uses word-boundary regex to prevent false positives (e.g. "flow" vs "flowing silver"), maps exact `global_release_date_str` from the v4 JSON dictionary, and extracts structured hardware features (CPU, RAM, Storage, GPU) only when applicable.
3. **Volatility Layer**: Shows engineered temporal features (delta_p_1d, vol_30d, stability_score).
4. **ML Forecasting**: Generates an exact 1:1 schema representation matching `ECom_Forecast_XAI_data.csv`, including all 15+ SHAP attribution weights, `sale_event_label`, and release dates. It uses hardcoded latest economic indicators (EGP/USD: 54.69, CPI: 24.65).

#### D. Visual Analytics
- **Category Breakdown**: A bar chart and table showing the distribution of the 100 rows in the current batch.
- **Filterable Results Table**: An interactive table allowing granular inspection of the ETL output, filterable by any category combination.

---

## 3. Debugging & Maintenance

### Common Issues for Next Agent
- **ModuleNotFoundError**: If running `streamlit run src_integrated/dashboard.py`, you MUST set `PYTHONPATH="."` first.
- **Validation Errors**: If the legacy JSON format changes significantly, the `WebScrapperOutput` validation in the dashboard might fail. These failures are captured and displayed in the **Detailed Error Logs** section of the UI.
- **Empty Queue**: The dashboard will display a warning if the `testing_queue.db` is empty. Run `testing_queue_builder.py` to refill it.

### Schema Persistence
UI state (the results of the last batch) is stored in `st.session_state.last_results`. This allows the inspector to remain visible even when the page reruns to update the queue counter.
