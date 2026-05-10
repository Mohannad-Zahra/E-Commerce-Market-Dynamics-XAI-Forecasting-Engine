import streamlit as st
import sqlite3
import pandas as pd
import json
import traceback
from datetime import datetime, timedelta
import time
import os

from src_integrated.schemas.pydantic_models import WebScrapperOutput, ETLOutput, VolatilityOutput, XAIForecastOutput
from pydantic import ValidationError
import sys

# Dynamically add ETL/Data Pipiline to path to import features
# Support both renamed ETL and legacy ETl folder
for _etl_dir in ['ETL', 'ETl']:
    etl_path = os.path.join(os.getcwd(), _etl_dir, 'Data Pipiline')
    if os.path.isdir(etl_path):
        if etl_path not in sys.path:
            sys.path.append(etl_path)
        break
from features import FeatureExtractor

st.set_page_config(page_title="Pipeline Monitor & Destructive Testing Queue", layout="wide")

QUEUE_DB_PATH = 'src_integrated/database/testing_queue.db'
CSV_PATH = 'forecast+shap/ECom_Forecast_XAI_data.csv'

def get_queue_count():
    try:
        if not os.path.exists(QUEUE_DB_PATH):
            return 0
        conn = sqlite3.connect(QUEUE_DB_PATH)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM raw_queue')
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        return 0

def get_latest_scrape_time():
    try:
        # Read the last few rows to find the max date
        # Assuming scrape_timestamp is the first column as seen in inspection
        if os.path.exists(CSV_PATH):
            # Read just columns we need, limit rows or just use standard pandas read (might be slow if large)
            # For robustness, we read the last 1000 rows, or use a shell command to get tail if it was bash, 
            # but since we are in python, let's just do a chunked read or read specific columns
            df = pd.read_csv(CSV_PATH, usecols=['scrape_timestamp'])
            df['scrape_timestamp'] = pd.to_datetime(df['scrape_timestamp'])
            latest_date = df['scrape_timestamp'].max()
            return latest_date
    except Exception as e:
        st.sidebar.error(f"Error reading CSV: {e}")
    return datetime.now()

def fetch_and_destroy_batch(batch_size=100):
    if not os.path.exists(QUEUE_DB_PATH):
        raise FileNotFoundError(f"Database {QUEUE_DB_PATH} not found.")
    
    conn = sqlite3.connect(QUEUE_DB_PATH)
    c = conn.cursor()
    
    # Begin transaction for destructive read
    c.execute('BEGIN TRANSACTION;')
    
    # 1. Identify rows
    c.execute(f'CREATE TEMPORARY TABLE batch_ids AS SELECT id FROM raw_queue LIMIT {batch_size};')
    
    # 2. Extract
    c.execute('SELECT id, payload FROM raw_queue WHERE id IN (SELECT id FROM batch_ids);')
    rows = c.fetchall()
    
    # 3. Destroy
    c.execute('DELETE FROM raw_queue WHERE id IN (SELECT id FROM batch_ids);')
    
    # 4. Cleanup
    c.execute('DROP TABLE batch_ids;')
    conn.commit()
    conn.close()
    
    return [json.loads(row[1]) for row in rows]

# --- UI Layout ---
st.title("Integrated Pipeline Monitor")

st.markdown("""
<style>
.metric-card {
    background-color: #1e1e1e;
    padding: 20px;
    border-radius: 10px;
    text-align: center;
    border: 1px solid #333;
}
.metric-value {
    font-size: 3rem;
    font-weight: bold;
    color: #00ffcc;
}
</style>
""", unsafe_allow_html=True)

# Header
queue_count = get_queue_count()
st.markdown(f'<div class="metric-card"><h3>Queue Status</h3><div class="metric-value">{queue_count}</div><p>Rows remaining in testing_queue.db</p></div>', unsafe_allow_html=True)

st.markdown("---")

# Control Panel
col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("Control Panel")
    trigger_btn = st.button("Trigger Batch Cycle (100 Rows)", use_container_width=True, type="primary")
    st.caption("⚠️ Destructive: permanently removes rows from the queue.")

with col2:
    st.subheader("Error Logs")
    error_placeholder = st.empty()
    if 'errors' not in st.session_state:
        st.session_state.errors = []
    
    if st.session_state.errors:
        error_text = "\\n".join(st.session_state.errors)
        error_placeholder.text_area("Stack Traces & Schema Validation Failures:", value=error_text, height=150)
    else:
        error_placeholder.text_area("Stack Traces & Schema Validation Failures:", value="No errors in the current session.", height=150)

st.markdown("---")

# Processing State & IO
st.subheader("Processing State & Component I/O Inspector")

def display_schema(title, pydantic_model, sample_data=None):
    with st.expander(f"Inspect {title}"):
        col_schema, col_data = st.columns(2)
        with col_schema:
            st.markdown("**Schema Definition:**")
            if pydantic_model:
                st.json(pydantic_model.model_json_schema())
            else:
                st.write("Dynamic JSON Schema")
        with col_data:
            st.markdown("**Sample Data (First Row):**")
            if sample_data:
                st.json(sample_data)
            else:
                st.write("No data processed yet.")

# Define expanders
raw_expander = st.empty()
etl_expander = st.empty()
vol_expander = st.empty()
ml_expander = st.empty()

# --- State Management ---
if 'last_results' not in st.session_state:
    st.session_state.last_results = None

if trigger_btn:
    st.session_state.errors = []
    if queue_count == 0:
        st.warning("Queue is empty!")
    else:
        try:
            # 1. Fetch data
            with st.spinner("Extracting & Destroying 100 rows..."):
                raw_data = fetch_and_destroy_batch(100)
                
                latest_date = get_latest_scrape_time()
                next_date = latest_date + timedelta(days=1)
                
                # Apply Temporal Continuation
                for item in raw_data:
                    item['scrape_timestamp'] = next_date.isoformat()
            
            # --- RAW INGESTION ---
            validated_raw = []
            for item in raw_data:
                try:
                    if 'raw_current_price' in item and isinstance(item['raw_current_price'], str):
                        item['raw_current_price'] = float(item['raw_current_price'].replace('EGP', '').replace(',', '').strip())
                    if 'raw_original_price' in item and isinstance(item['raw_original_price'], str):
                        item['raw_original_price'] = float(item['raw_original_price'].replace('EGP', '').replace(',', '').strip())
                    
                    validated_raw.append(WebScrapperOutput(**item).model_dump())
                except ValidationError as e:
                    st.session_state.errors.append(f"Raw Ingestion Validation Error: {str(e)}")
                    validated_raw.append(item)
                except Exception:
                    pass
            
            # --- ETL LAYER ---
            etl_processed = []
            extractor = FeatureExtractor()
            for item in validated_raw:
                # Use the actual ETL logic
                etl_item = extractor.transform_row(item)
                etl_processed.append(etl_item)
                
            # --- VOLATILITY MODELING ---
            vol_processed = []
            for item in etl_processed:
                item_copy = dict(item)
                item_copy['delta_p_1d'] = 0.05
                item_copy['delta_p_7d'] = 0.12
                item_copy['delta_p_14d'] = 0.08
                item_copy['vol_30d'] = 0.15
                item_copy['stability_score'] = 85.5
                vol_processed.append(item_copy)
                
            # --- ML FORECASTING ---
            # Economic indicators hardcoded from latest row in ECom_Forecast_XAI_data.csv
            # (scrape_timestamp: 2026-04-29, official_egp_usd=54.69, cpi_inflation=24.6493)
            LATEST_EGP_USD   = 54.69
            LATEST_CPI       = 24.6493
            LATEST_LAMBDA    = 0.55
            LATEST_MULT      = 0.8732

            ml_processed = []
            for item in vol_processed:
                ml_mock = {
                    "scrape_timestamp": item['scrape_timestamp'],
                    "product_id": str(item.get('product_url', 'id_123')),
                    "raw_title": item.get('raw_title', ''),
                    "category": item.get('category', 'unknown'),
                    "official_egp_usd": LATEST_EGP_USD,
                    "cpi_inflation": LATEST_CPI,
                    "import_lambda": LATEST_LAMBDA,
                    "multiplier": LATEST_MULT,
                    "is_major_sale_period": 0,
                    "sale_event_label": None,
                    "D_months": 24.0, "k": 0.0003, "missing_release_date": 0,
                    "global_release_date_str": item.get('global_release_date_str'),
                    "competitor_scarcity_count": 5, "volume_weight": 0.5, "compute_potential": 0.8,
                    "delta_p_1d": item['delta_p_1d'], "vol_30d": item['vol_30d'],
                    "delta_p_7d": item['delta_p_7d'], "delta_p_14d": item['delta_p_14d'],
                    "stability_score": item['stability_score'],
                    "predicted_stability_score": 86.0,
                    "price_t_plus_14": item.get('raw_current_price', 0) * 1.05,
                    "shap_compute_potential": 1.5, "shap_delta_p_7d": 0.01,
                    "shap_delta_p_14d": 0.02, "shap_delta_p_1d": 0.01,
                    "shap_vol_30d": 0.2, "shap_official_egp_usd": 0.3,
                    "shap_cpi_inflation": 0.5, "shap_is_major_sale_period": 0.0,
                    "shap_competitor_scarcity_count": 0.01, "shap_volume_weight": 0.1,
                    "shap_D_months": -0.05, "shap_k": -0.02,
                    "shap_import_lambda": 0.01, "shap_missing_release_date": 0.0,
                    "shap_base_expected_price": 75.0,
                    "delta_shap_compute_potential": 0.0, "delta_shap_delta_p_7d": 0.0,
                    "delta_shap_delta_p_14d": 0.0, "delta_shap_delta_p_1d": 0.0,
                    "delta_shap_vol_30d": 0.0, "delta_shap_official_egp_usd": 0.0,
                    "delta_shap_cpi_inflation": 0.0, "delta_shap_is_major_sale_period": 0.0,
                    "delta_shap_competitor_scarcity_count": 0.0, "delta_shap_volume_weight": 0.0,
                    "delta_shap_D_months": 0.0, "delta_shap_k": 0.0,
                    "delta_shap_import_lambda": 0.0, "delta_shap_missing_release_date": 0.0
                }
                ml_processed.append(ml_mock)

            st.session_state.last_results = {
                "raw": validated_raw,
                "etl": etl_processed,
                "vol": vol_processed,
                "ml": ml_processed,
                "date": next_date
            }
            
            st.balloons()
            st.rerun()
            
        except Exception as e:
            st.session_state.errors.append(f"Execution Error: {traceback.format_exc()}")
            st.rerun()

# --- Display Results ---
if st.session_state.last_results:
    res = st.session_state.last_results
    st.success(f"Last batch cycle completed for temporal date: {res['date'].strftime('%Y-%m-%d')}")

    # ── Category Distribution ──────────────────────────────────────────
    st.markdown("#### 📊 ETL Category Breakdown")
    if res['etl']:
        etl_df = pd.DataFrame(res['etl'])
        cat_counts = etl_df['category'].value_counts().reset_index()
        cat_counts.columns = ['Category', 'Count']
        # Show as horizontal bar chart + table side by side
        bc1, bc2 = st.columns([2, 1])
        with bc1:
            st.bar_chart(cat_counts.set_index('Category')['Count'])
        with bc2:
            st.dataframe(cat_counts, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Filterable ETL Results Table ───────────────────────────────────
    st.markdown("#### 🔍 Browse ETL Results")
    if res['etl']:
        etl_df = pd.DataFrame(res['etl'])
        available_cats = sorted(etl_df['category'].dropna().unique().tolist())
        selected_cats = st.multiselect(
            "Filter by Category:",
            options=available_cats,
            default=available_cats,
            key='cat_filter'
        )
        filtered_df = etl_df[etl_df['category'].isin(selected_cats)] if selected_cats else etl_df

        # Column selection for display
        display_cols = ['raw_title', 'category', 'sub_category', 'brand', 'cpu', 'ram_gb', 'storage_gb', 'gpu', 'is_gaming', 'global_release_date_str', 'raw_current_price']
        display_cols = [c for c in display_cols if c in filtered_df.columns]
        display_df = filtered_df[display_cols].copy()
        # Ensure consistent dtypes for pyarrow
        if 'is_gaming' in display_df.columns:
            display_df['is_gaming'] = display_df['is_gaming'].fillna(0).astype(int)
        st.dataframe(display_df, use_container_width=True, height=300)

    st.markdown("---")

    # ── Layer-by-Layer Schema Inspector ───────────────────────────────
    st.markdown("#### 🧩 Processing State & Component I/O Inspector")
    st.markdown("#### 1. Raw Ingestion Layer ✅")
    display_schema("Raw Ingestion", WebScrapperOutput, res['raw'][0] if res['raw'] else None)
    
    st.markdown("#### 2. ETL Layer ✅")
    display_schema("ETL Layer", ETLOutput, res['etl'][0] if res['etl'] else None)
    
    st.markdown("#### 3. Volatility Modeling ✅")
    display_schema("Volatility", VolatilityOutput, res['vol'][0] if res['vol'] else None)
    
    st.markdown("#### 4. ML Forecasting Layer ✅")
    display_schema("ML Forecasting", XAIForecastOutput, res['ml'][0] if res['ml'] else None)
else:
    st.info("No data processed in this session yet. Click 'Trigger Batch Cycle' to start.")

