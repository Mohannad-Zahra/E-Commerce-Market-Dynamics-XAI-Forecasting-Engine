# System Overview

## High-Level Architecture
The Wise Purchaser system is a distributed, high-precision e-commerce forecasting and recommendation engine designed for the Egyptian Retail Electronics Sector. It has evolved from a decoupled CSV/Parquet architecture into an **Integrated Database Orchestrator**, where components communicate seamlessly in-memory via strictly-typed Pydantic schemas and persist data directly to a relational database (SQLite/PostgreSQL).

### Data Flow
1. **Web Scrapper (Edge Layer)**: Responsible for the raw data ingestion. The scraper collects market pricing data from external electronics retailers asynchronously. It outputs raw JSON payloads.
2. **ETL Pipeline** (`ETL/Data Pipiline/features.py`): Ingests raw JSON data. Dynamically categorizes all product types (Electronics/Laptops, Phones, Tablets, Accessories, PC Components, Networking, Gaming) using a 16-level priority chain with word-boundary regex matching. Maps `global_release_date_str` from a reference dictionary of ~1,770 products. Extracts hardware features (CPU, RAM, Storage, GPU, is_gaming, Brand) per category rules. **Zero products fall to Unknown** across the full 1,770-product catalog.
3. **Volatility Modeling (Vola Score)**: Ingests the ETL output to calculate temporal price deltas (1d, 7d, 14d) and compute market stability scores.
4. **XAI Forecasting (forecast+shap)**: Utilizes the Volatility output. Predicts `price_t_plus_14` using ONNX-exported SARIMAX/LightGBM models and calculates SHAP values to explain the predictions based on economic indicators (EGP/USD rate, CPI inflation).
5. **Recommendation System**: Takes the enriched forecast and SHAP outputs to score, rank, and formulate natural-language recommendations for end consumers.
6. **QA Testing & Monitoring Dashboard** (`src_integrated/dashboard.py`): A diagnostic layer that consumes legacy data via a destructive queue (`testing_queue.db`) to verify pipeline integrity across the ETL and ML layers while bypassing recommendations.
7. **Delivery (Backend & FrontEnd)**: A FastAPI backend serves the finalized insights and cached recommendations to the React FrontEnd.

## Product Category Taxonomy (ETL Layer)
The ETL pipeline classifies every scraped product into one of the following categories:

| Category | Sub-Category | Examples |
|---|---|---|
| Electronics | Laptops | ASUS ROG, MSI Katana, ACER Nitro, MacBook |
| Phone | Smartphones | Samsung Galaxy, Realme 15T, iPhone, Infinix Hot |
| Tablet | Tablets | iPad, Huawei MatePad, Lenovo M10 |
| Accessories | Audio | Anker Soundcore, AirPods, TWS earbuds |
| Accessories | Wearables | Samsung Galaxy Watch, Fitbit |
| Accessories | Power | Chargers, power banks, USB-C cables |
| Accessories | Peripherals | Mice, keyboards, monitors |
| PC Components | Desktop GPU | ASUS RTX 5080, ASRock RX 9070, GALAX RTX 5070 |
| PC Components | Storage | Samsung T7 SSD, Crucial BX500, WD HDD |
| PC Components | Components | AMD Ryzen processors, DDR5 RAM, NVMe M.2 SSDs |
| PC Components | Cooling | CPU coolers, heatsinks |
| Networking | Networking | Routers, access points |
| Gaming | Consoles | PlayStation, Xbox, Nintendo |

## Design Philosophy
- **Integrated Orchestration**: Components are wrapped by a central orchestrator (`src_integrated/orchestrator.py`), eliminating intermediate file I/O in favor of robust object passing.
- **Medallion Database Architecture**: Data still follows Bronze/Silver/Gold logic, but is stored safely inside unified database tables (`products`, `macro_economics`, `price_history`, `ml_forecast_shap`).
- **Explainability First**: Forecasting explicitly incorporates economic factors (CPI, USD parallel rate) and justifies predictions through SHAP attributions.
- **Word-Boundary Safe Categorization**: All keyword matching uses regex word boundaries to prevent substring collisions (e.g. `flow` ≠ `flowing`, `vivo` ≠ `vivobook`).
