import os
import json

def create_directory_structure():
    base_dir = r"c:\Users\mohan\OneDrive\Desktop\Wise Purchaser\System_Architecture_WrapUp"
    components_dir = os.path.join(base_dir, "Components")
    data_schemas_dir = os.path.join(base_dir, "Data_Schemas")
    
    os.makedirs(components_dir, exist_ok=True)
    os.makedirs(data_schemas_dir, exist_ok=True)
    
    # 1. System Interaction Graph
    interaction_graph_content = """# System Interaction Graph

## End-to-End Data Flow

1. **Web Scrapper**: Responsible for collecting raw market pricing data from external sources. The data includes product URLs, raw titles, and scraped timestamps.
2. **ETL Pipeline (`ETl`)**: Ingests raw JSON data from scrapers, extracts features (CPU, RAM, GPU, Brand) from raw titles, cleans the data, and writes to `processed_products.csv`.
3. **Volatility & Pricing Models (`Volatility score ML pipeline`, `Vola Score`)**: Ingests processed data. Generates stability scores and calculates multi-scale price deltas (1d, 7d, 14d) and volatility indicators.
4. **XAI Forecasting (`forecast+shap`, `E-Commerce Market Dynamics & XAI Forecasting Engine`)**: Computes SHAP values for the features to provide an Explainable AI output on pricing multipliers and prediction logic.
5. **Recommendation System**: Takes final computed scores (R_score, stability scores, XAI explanations) and ranks the products for final consumer action.
6. **Backend & Frontend (`backend`, `FrontEnd`)**: Serves the unified dataset to the user via APIs and visualizes the best deals.

## Component Interactions

- **Asynchronous Execution**: The web scrapers run asynchronously and drop raw data into designated folders.
- **Batch Processing**: The ETL and ML modeling components operate sequentially on scheduled batch files (`Dataset_Pipeline_Processed.csv`, etc.).
- **Data Sinks**: All inter-component communication happens via static file handoffs (`.csv` and `.parquet`), enforcing strict decoupling without shared memory overhead.

> **Note on Test Data**: The folder `oldData_need the scrape_time to update for it to work` contains legacy/test data used for model verification and should remain intact.
"""
    with open(os.path.join(base_dir, "system_interaction_graph.md"), 'w', encoding='utf-8') as f:
        f.write(interaction_graph_content)
        
    # 2. Data Schemas
    final_schema_features = "scrape_timestamp,product_id,raw_title,official_egp_usd,cpi_inflation,is_major_sale_period,competitor_scarcity_count,import_lambda,sale_event_label,volume_weight,global_release_date_str,missing_release_date,k,multiplier,D_months,category,compute_potential,delta_p_1d,vol_30d,delta_p_7d,delta_p_14d,stability_score,predicted_stability_score,price_t_plus_14,shap_compute_potential,shap_delta_p_7d,shap_delta_p_14d,shap_delta_p_1d,shap_vol_30d,shap_official_egp_usd,shap_cpi_inflation,shap_is_major_sale_period,shap_competitor_scarcity_count,shap_volume_weight,shap_D_months,shap_k,shap_import_lambda,shap_missing_release_date,shap_base_expected_price,delta_shap_compute_potential,delta_shap_delta_p_7d,delta_shap_delta_p_14d,delta_shap_delta_p_1d,delta_shap_vol_30d,delta_shap_official_egp_usd,delta_shap_cpi_inflation,delta_shap_is_major_sale_period,delta_shap_competitor_scarcity_count,delta_shap_volume_weight,delta_shap_D_months,delta_shap_k,delta_shap_import_lambda,delta_shap_missing_release_date"
    
    schema_content = f"""# Final Required Dataset Schema

The system pipeline incrementally builds towards the following comprehensive schema containing temporal, economic, and explainable AI (SHAP) features.

**Source**: Aggregated from output of the XAI Forecasting and Volatility ML components.

### Columns (Exact Spec):
{', '.join(f'`{col}`' for col in final_schema_features.split(','))}

---

# Intermediate Schema (ETL Processed Products)

**Source**: `ETl/Data Pipiline/main.py` -> `processed_products.csv`

### Columns:
`scrape_timestamp`, `retailer_id`, `raw_title`, `raw_current_price`, `raw_original_price`, `product_url`, `category`, `sub_category`, `brand`, `cpu`, `ram_gb`, `storage_gb`, `gpu`, `is_gaming`
"""
    with open(os.path.join(data_schemas_dir, "Final_Schema.md"), 'w', encoding='utf-8') as f:
        f.write(schema_content)
        
    # 3. Components
    components = [
        "Web_Scrapper",
        "ETL",
        "Volatility_Score",
        "XAI_Forecasting",
        "Recommendation_System",
        "Backend"
    ]
    
    for comp in components:
        comp_dir = os.path.join(components_dir, comp)
        os.makedirs(comp_dir, exist_ok=True)
        
        # README.md
        readme = f"""# Component: {comp}

## Primary Function
This component encapsulates the domain logic for `{comp}`. 
It follows Clean Architecture principles by isolating its internal algorithms from external dependencies.

## Internal Logic & Algorithms
- Processes inputs independently.
- Avoids mutating source data files directly.
- Handles {comp.lower().replace('_', ' ')} logic and outputs to standard formats.
"""
        with open(os.path.join(comp_dir, "README.md"), 'w', encoding='utf-8') as f:
            f.write(readme)
            
        # io_contracts.md
        io_contract = f"""# I/O Contracts: {comp}

## Expected Inputs
- Defined input schemas depending on the pipeline step (raw JSON or `.csv` extracts).

## Expected Outputs
- Emits structured payloads/files conforming strictly to downstream requirements. No arbitrary schema changes are permitted without upstream synchronization.
"""
        with open(os.path.join(comp_dir, "io_contracts.md"), 'w', encoding='utf-8') as f:
            f.write(io_contract)
            
        # dependencies.md
        deps = f"""# Dependencies: {comp}

## Internal System Calls
- Communicates via decoupled file handoffs (`.csv`/`.parquet` sinks).

## External Libraries
- `pandas`
- `numpy`
- Python standard libraries (`os`, `json`, `re`, `glob`)
- For ML components: `scikit-learn`, `lightgbm`, `shap`
"""
        with open(os.path.join(comp_dir, "dependencies.md"), 'w', encoding='utf-8') as f:
            f.write(deps)

if __name__ == '__main__':
    create_directory_structure()
    print("Documentation generated successfully.")
