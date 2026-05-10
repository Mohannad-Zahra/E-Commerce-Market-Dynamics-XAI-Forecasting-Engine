# Component Dictionary

*Note: The system has been migrated to an Integrated Database Orchestrator. The components below now communicate in-memory via strictly typed Pydantic models (`src_integrated/schemas/pydantic_models.py`) instead of CSV handoffs, and persist their final state to a relational database (`src_integrated/database/models.py`).*

## 1. Web Scrapper
**Filepath**: `Web Scrapper/`
**Summary**: Distributed scraping engine using Playwright/BeautifulSoup. Captures raw pricing data from various retailers asynchronously and dumps JSON files to a local database/Google Drive, synchronized via a watchdog process.

**Inputs**:
- Market Retailer HTML/DOM.

**Exact Outputs** (JSON files per retailer cycle):
- `scrape_timestamp` [String/ISO8601]: The exact UTC execution time.
- `retailer_id` [String]: e.g., 'sigma-computer', '2b_egypt'.
- `raw_title` [String]: Unprocessed product title.
- `raw_current_price` [Float]: Extracted price value.
- `raw_original_price` [Float]: Strikethrough price if available.
- `product_url` [String]: Direct link to item.

---

## 2. ETL Pipeline
**Filepath**: `ETl/`
**Summary**: Cleans the messy raw scraper output. Parses hardware strings (CPU, RAM, GPU) using regex, filters invalid data, and generates a structured catalog.

**Exact Inputs**:
- Raw JSON files from `Web Scrapper`.

**Exact Outputs** (`processed_products.csv` shape: `[N, 14]`):
- `scrape_timestamp` [String]
- `retailer_id` [String]
- `raw_title` [String]
- `raw_current_price` [Float]
- `raw_original_price` [Float]
- `product_url` [String]
- `category` [String]
- `sub_category` [String]
- `brand` [String]
- `cpu` [String]
- `ram_gb` [Int/Float]
- `storage_gb` [Int/Float]
- `gpu` [String]
- `is_gaming` [Boolean]

---

## 3. Volatility Modeling
**Filepath**: `Vola Score/`
**Summary**: Computes historical price volatility and stability. Calculates rolling windows over the ETL output to define price deltas across 1, 7, and 14 days, establishing the baseline `stability_score`.

**Exact Inputs**:
- `processed_products.csv`

**Exact Outputs**:
- All ETL columns + engineered temporal features:
- `delta_p_1d` [Float]: 1-day price delta.
- `delta_p_7d` [Float]: 7-day price delta.
- `delta_p_14d` [Float]: 14-day price delta.
- `vol_30d` [Float]: 30-day volatility metric.
- `stability_score` [Float]: Baseline calculated stability index.

---

## 4. XAI Forecasting Engine
**Filepath**: `forecast+shap/`
**Summary**: The core ML component. Uses the Volatility features and macroeconomic indicators (Inflation, EGP/USD) to forecast the `price_t_plus_14` using LightGBM/SARIMAX. Explains the prediction via SHAP values, assigning an exact attribution weight to every input feature.

**Exact Inputs**:
- Temporal/Volatility output + Macroeconomic data.

**Exact Outputs** (`ECom_Forecast_XAI_data.csv` shape: `[N, 53]`):
- Core Identifiers: `scrape_timestamp` [String], `product_id` [String], `raw_title` [String], `category` [String].
- Economic Indicators: `official_egp_usd` [Float], `cpi_inflation` [Float], `import_lambda` [Float], `multiplier` [Float].
- Temporal Features: `is_major_sale_period` [Int], `sale_event_label` [String], `D_months` [Float], `k` [Float], `missing_release_date` [Int], `global_release_date_str` [String].
- Market Features: `competitor_scarcity_count` [Int], `volume_weight` [Float], `compute_potential` [Float].
- Volatility Metrics: `delta_p_1d` [Float], `vol_30d` [Float], `delta_p_7d` [Float], `delta_p_14d` [Float].
- Predictions: `stability_score` [Float], `predicted_stability_score` [Float], `price_t_plus_14` [Float].
- SHAP Attributions [Floats]: `shap_compute_potential`, `shap_delta_p_7d`, `shap_delta_p_14d`, `shap_delta_p_1d`, `shap_vol_30d`, `shap_official_egp_usd`, `shap_cpi_inflation`, `shap_is_major_sale_period`, `shap_competitor_scarcity_count`, `shap_volume_weight`, `shap_D_months`, `shap_k`, `shap_import_lambda`, `shap_missing_release_date`, `shap_base_expected_price`.
- Delta SHAP Values [Floats]: `delta_shap_compute_potential`, `delta_shap_delta_p_7d`, `delta_shap_delta_p_14d`, `delta_shap_delta_p_1d`, `delta_shap_vol_30d`, `delta_shap_official_egp_usd`, `delta_shap_cpi_inflation`, `delta_shap_is_major_sale_period`, `delta_shap_competitor_scarcity_count`, `delta_shap_volume_weight`, `delta_shap_D_months`, `delta_shap_k`, `delta_shap_import_lambda`, `delta_shap_missing_release_date`.

---

## 5. Recommendation System
**Filepath**: `Recommendation system/`
**Summary**: Ingests the `ECom_Forecast_XAI_data.csv`, evaluates deals using the SHAP explanations and stability scores, and applies LLM-driven natural language summaries for consumer-facing output.

**Exact Inputs**:
- `ECom_Forecast_XAI_data.csv`

**Exact Outputs**:
- Ranked JSON output containing top deals, `R_score` (Recommendation Score), and a generated reasoning string explaining *why* the user should buy now based on SHAP factors.
---

## 6. QA Pipeline Monitoring & Testing Queue
**Filepath**: `src_integrated/` (`dashboard.py`, `testing_queue_builder.py`)
**Summary**: A diagnostic layer that allows developers to run destructive "dry-runs" of the pipeline using legacy data. It consolidates messy historical data into a queue and provides a web GUI to trigger batches and inspect feature transformations in real-time.

**Inputs**:
- Legacy JSON/CSV files from `oldData_need the scrape_time...`
- Latest `scrape_timestamp` from `forecast+shap/ECom_Forecast_XAI_data.csv` (for temporal continuation).

**Exact Outputs**:
- UI Visualization of data flow across all 4 layers.
- Validated Pydantic models fed into the main pipeline components.
- **Destruction**: Deletion of processed rows from `testing_queue.db`.
