# Finalized Unified Database Schema

The pipeline has been migrated to an Integrated Orchestrator leveraging robust SQL Database persistence.

## Target RDBMS: PostgreSQL / SQLite

---

### Table: `products`
**Description**: Stores static metadata and hardware specifications for each item.
- `id` (VARCHAR) - PRIMARY KEY. The unique `product_id` (URL or hash).
- `retailer_id` (VARCHAR) - The source of the scrape.
- `raw_title` (VARCHAR) - Unprocessed item title.
- `product_url` (VARCHAR) - Direct link to item.
- `category` (VARCHAR) - Broad category (e.g., 'Laptop').
- `sub_category` (VARCHAR) - Sub-category (e.g., 'Gaming').
- `brand` (VARCHAR) - Extracted brand name.
- `cpu` (VARCHAR) - CPU model/tier.
- `ram_gb` (FLOAT) - RAM size in GB.
- `storage_gb` (FLOAT) - Storage size in GB.
- `gpu` (VARCHAR) - GPU model/tier.
- `is_gaming` (BOOLEAN) - Flag indicating gaming orientation.
- `global_release_date` (DATE) - The parsed Date object representing release.
- `global_release_date_str` (VARCHAR) - Release date representation.
- `missing_release_date` (BOOLEAN) - Flag for missing dates.
- `compute_potential` (FLOAT) - Extracted hardware power index.

---

### Table: `macro_economics`
**Description**: Stores daily time-series macro and market indicators.
- `date_id` (DATE) - PRIMARY KEY. Mapped from `scrape_timestamp`.
- `official_egp_usd` (FLOAT) - Official/Parallel exchange rate multiplier.
- `cpi_inflation` (FLOAT) - Current inflation rate.
- `import_lambda` (FLOAT) - Import tax/tariff weight proxy.
- `multiplier` (FLOAT) - Pricing margin parameter.
- `is_major_sale_period` (BOOLEAN) - Flag if date falls in a major sale.
- `sale_event_label` (VARCHAR) - Specific sale name.

---

### Table: `price_history`
**Description**: Stores the temporal pricing and dynamic metrics for a product.
- `id` (SERIAL) - PRIMARY KEY.
- `product_id` (VARCHAR) - FOREIGN KEY referencing `products(id)`.
- `date_id` (DATE) - FOREIGN KEY referencing `macro_economics(date_id)`.
- `scrape_timestamp` (TIMESTAMP) - The exact scraping time.
- `raw_current_price` (FLOAT) - Extracted current price.
- `raw_original_price` (FLOAT) - Extracted original/strikethrough price.
- `competitor_scarcity_count` (INTEGER) - Number of competitors holding stock.
- `volume_weight` (FLOAT) - Physical weight proxy for shipping costs.
- `k` (FLOAT) - Demand elasticity proxy.
- `D_months` (FLOAT) - Age in months since release.
- `delta_p_1d` (FLOAT) - Price delta over 1 day.
- `delta_p_7d` (FLOAT) - Price delta over 7 days.
- `delta_p_14d` (FLOAT) - Price delta over 14 days.
- `vol_30d` (FLOAT) - Volatility metric.

---

### Table: `ml_forecast_shap`
**Description**: Stores the output of the XAI Forecasting pipeline.
- `id` (SERIAL) - PRIMARY KEY.
- `price_history_id` (INTEGER) - FOREIGN KEY referencing `price_history(id)`.
- `stability_score` (FLOAT) - The actual computed stability.
- `predicted_stability_score` (FLOAT) - Model predicted stability.
- `price_t_plus_14` (FLOAT) - Model predicted price at T+14.
- `shap_compute_potential` (FLOAT) - SHAP attribution for compute_potential.
- `shap_delta_p_7d` (FLOAT) - SHAP attribution for delta_p_7d.
- `shap_delta_p_14d` (FLOAT) - SHAP attribution for delta_p_14d.
- `shap_delta_p_1d` (FLOAT) - SHAP attribution for delta_p_1d.
- `shap_vol_30d` (FLOAT) - SHAP attribution for vol_30d.
- `shap_official_egp_usd` (FLOAT) - SHAP attribution for USD rate.
- `shap_cpi_inflation` (FLOAT) - SHAP attribution for inflation.
- `shap_is_major_sale_period` (FLOAT) - SHAP attribution for sale period.
- `shap_competitor_scarcity_count` (FLOAT) - SHAP attribution for scarcity.
- `shap_volume_weight` (FLOAT) - SHAP attribution for weight.
- `shap_D_months` (FLOAT) - SHAP attribution for age.
- `shap_k` (FLOAT) - SHAP attribution for demand.
- `shap_import_lambda` (FLOAT) - SHAP attribution for import friction.
- `shap_missing_release_date` (FLOAT) - SHAP attribution for missing date.
- `shap_base_expected_price` (FLOAT) - Model's base/intercept price.
- `delta_shap_compute_potential` (FLOAT) - Interventional Delta SHAP values.
- `delta_shap_delta_p_7d` (FLOAT)
- `delta_shap_delta_p_14d` (FLOAT)
- `delta_shap_delta_p_1d` (FLOAT)
- `delta_shap_vol_30d` (FLOAT)
- `delta_shap_official_egp_usd` (FLOAT)
- `delta_shap_cpi_inflation` (FLOAT)
- `delta_shap_is_major_sale_period` (FLOAT)
- `delta_shap_competitor_scarcity_count` (FLOAT)
- `delta_shap_volume_weight` (FLOAT)
- `delta_shap_D_months` (FLOAT)
- `delta_shap_k` (FLOAT)
- `delta_shap_import_lambda` (FLOAT)
- `delta_shap_missing_release_date` (FLOAT)
---

# 5. Testing & QA Database (testing_queue.db)

**Description**: A separate, auxiliary SQLite database used for destructive batch testing and pipeline simulation.

### Table: `raw_queue`
- `id` (INTEGER) - PRIMARY KEY (AUTOINCREMENT).
- `payload` (TEXT) - The raw JSON string representing the original retailer scrape. This is unmutated until it enters the pipeline.
