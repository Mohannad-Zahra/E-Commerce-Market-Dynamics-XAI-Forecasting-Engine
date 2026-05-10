# Monitoring Dashboard — User Guide

**File:** `src_integrated/dashboard.py`  
**URL:** `http://localhost:8502`  
**Command:** `$env:PYTHONPATH="."; streamlit run src_integrated/dashboard.py --server.port 8502`

---

## Purpose

The Pipeline Monitor is a **destructive testing dashboard** for validating the end-to-end data pipeline across all four processing layers. It pulls real product records from a live SQLite queue, runs them through the actual production ETL logic, and displays the results visually.

> ⚠️ **Destructive**: Each "Trigger Batch Cycle" permanently removes 100 rows from `testing_queue.db`. They cannot be recovered.

---

## Architecture — 4 Pipeline Layers

```
testing_queue.db
       │
       ▼
┌─────────────────────┐
│  Raw Ingestion      │  Validates & coerces raw scraper output
│  (WebScrapperOutput)│  via Pydantic schema
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  ETL Layer          │  FeatureExtractor (ETL/Data Pipiline/features.py)
│  (ETLOutput)        │  → Category, brand, RAM, storage, GPU, is_gaming,
│                     │    global_release_date_str
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  Volatility Modeling│  Computes delta_p_1d/7d/14d, vol_30d,
│  (VolatilityOutput) │  stability_score (mock values)
└────────┬────────────┘
         ▼
┌─────────────────────┐
│  ML Forecasting     │  Assembles the full XAI forecast record
│  (XAIForecastOutput)│  matching ECom_Forecast_XAI_data.csv schema
└─────────────────────┘
```

---

## UI Components

### Queue Status Card
Shows how many rows remain in `src_integrated/database/testing_queue.db`.

### Control Panel
- **Trigger Batch Cycle (100 Rows)** — Extracts and destroys 100 rows, processes them through all 4 layers, and stores results in session state.
- **Error Logs** — Displays any Pydantic `ValidationError` or runtime exceptions caught during processing.

### 📊 ETL Category Breakdown
After each batch cycle, displays:
- A **bar chart** of category distribution across the 100 processed rows
- A **count table** (Category | Count) side by side

### 🔍 Browse ETL Results
An interactive, filterable table of all 100 ETL-processed rows. Columns:
`raw_title`, `category`, `sub_category`, `brand`, `cpu`, `ram_gb`, `storage_gb`, `gpu`, `is_gaming`, `global_release_date_str`, `raw_current_price`

Use the **multi-select filter** to narrow results by any category combination.

### 🧩 Component I/O Inspector
Expandable panels for each pipeline layer showing:
- **Schema Definition** — Pydantic model JSON schema
- **Sample Data** — First row of the processed batch

---

## Hardcoded Economic Indicators

The ML Forecasting layer uses the following values, sourced from the **latest row** (scrape_timestamp: 2026-04-29) in `forecast+shap/ECom_Forecast_XAI_data.csv`:

| Field | Value |
|---|---|
| `official_egp_usd` | 54.69 |
| `cpi_inflation` | 24.6493 |
| `import_lambda` | 0.55 |
| `multiplier` | 0.8732 |

These should be updated whenever a newer row is appended to the CSV.

---

## Output Location

The dashboard is **monitoring-only**. Processed data is stored in `st.session_state.last_results` (in-memory only). It is **not persisted** to disk after the session ends.

If persistence is needed, a CSV export or database write function can be added to the end of the batch cycle.

---

## Product Category Reference

The ETL layer classifies products into the following taxonomy:

| Category | Sub-Categories |
|---|---|
| Electronics | Laptops |
| Phone | Smartphones |
| Tablet | Tablets |
| Accessories | Audio, Wearables, Power, Peripherals, Storage |
| PC Components | Desktop GPU, Storage, Cooling, Case, Components |
| Networking | Networking |
| Gaming | Consoles |
