import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import sys
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CONFIGURATION ---
API_BASE = "http://localhost:8000"
ST_PAGE_TITLE = "Wise Purchaser | Unified Control Plane"
st.set_page_config(page_title=ST_PAGE_TITLE, layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR PREMIUM LOOK ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0e1117;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00ffcc, #00b4ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .zone-card {
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #30363d;
        background-color: #161b22;
        margin-bottom: 1rem;
    }
    .status-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-approved { background-color: #238636; color: white; }
    .badge-dlq { background-color: #d29922; color: white; }
    .badge-rejected { background-color: #da3633; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def api_request(method, endpoint, data=None):
    try:
        url = f"{API_BASE}{endpoint}"
        if method == "GET":
            resp = requests.get(url)
        else:
            resp = requests.post(url, json=data)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API Error ({endpoint}): {e}")
        return None

# --- SIDEBAR: SYSTEM STATUS ---
st.sidebar.markdown(f"<h1 class='main-header'>Wise Purchaser</h1>", unsafe_allow_html=True)
st.sidebar.markdown("### `v2.0-Agentic` | 🟢 System Online")
st.sidebar.markdown("---")

# Health Check
health = api_request("GET", "/health")
if health:
    st.sidebar.success(f"Backend: {health.get('status', 'Online')}")
    st.sidebar.info(f"Database: {health.get('db', 'Connected')}")
    st.sidebar.info(f"Models: {health.get('models', 'Loaded')}")

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ System Control")
if st.sidebar.button("🔄 Force ReAct Retrain", use_container_width=True):
    with st.spinner("Executing ReAct Loop..."):
        res = api_request("POST", "/system/retrain")
        if res:
            st.toast("ReAct Verification Cycle Complete!")
            st.rerun()

if st.sidebar.button("🧹 Clear Ingestion Queue", use_container_width=True):
    res = api_request("POST", "/queue/clear")
    if res:
        st.toast("Testing Queue Cleared!")

st.sidebar.markdown("---")
st.sidebar.subheader("🚀 Batch Orchestration")
batch_id_input = st.sidebar.text_input("Active Batch ID", value=f"batch_{datetime.now().strftime('%m%d_%H%M')}")

if st.sidebar.button("Trigger Full Pipeline Cycle", type="primary", use_container_width=True):
    with st.sidebar.status("Executing End-to-End Pipeline...") as s:
        res = api_request("POST", "/etl", {"batch_id": batch_id_input})
        if res:
            s.update(label="Pipeline Cycle Complete!", state="complete")
            st.toast("Pipeline executed successfully!")
            st.session_state["last_batch"] = batch_id_input
            st.rerun()

# --- MAIN UI ---
if "last_batch" not in st.session_state:
    st.session_state["last_batch"] = "latest"

# ZONE 6: System Alerts (Top Banner)
drift_status = api_request("GET", f"/drift/{st.session_state['last_batch']}")
if drift_status:
    if drift_status.get("overall_drift"):
        st.error(f"🚨 **ZONE 6: SYSTEM ALERT** - DRIFT DETECTED (Signal: {drift_status['signal_1']['median_gap']:.2f}). Retrain recommended.")
    else:
        st.info(f"✅ **ZONE 6: SYSTEM ALERT** - Drift Monitoring Active. Status: Stable.")

tab1, tab_trace, tab2, tab3, tab4, tab5 = st.tabs([
    "🛰️ Mission Control",
    "🔍 Dataset Trace",
    "🤖 ReAct Trace",
    "🩺 Drift & Health",
    "📈 Intelligence",
    "📥 Human Review (DLQ)"
])

# ZONE 1: Mission Control (Ingestion/ETL)
with tab1:
    st.markdown("<h2 class='main-header'>🛰️ Zone 1: Ingestion Mission Control</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Manual Queue Release")
        rows_to_release = st.number_input("Rows to Release", min_value=1, max_value=500, value=20)
        if st.button("📥 Release from Test Queue", type="primary"):
            res = api_request("POST", "/ingest/testing-queue", {"batch_id": batch_id_input, "limit": rows_to_release})
            if res:
                st.success(f"Ingested {res['rows_ingested']} rows into {batch_id_input}")
                st.session_state["last_batch"] = batch_id_input
    
    with col2:
        st.subheader("Ingestion Health")
        ingest_stats = api_request("GET", "/stats/ingestion")
        if ingest_stats:
            m1, m2 = st.columns(2)
            m1.metric("Ingested Batches", ingest_stats.get('batch_count', 0))
            m2.metric("Pending Queue Depth", f"{ingest_stats.get('queue_depth', 0):,}")
        else:
            st.warning("Could not fetch ingestion stats.")

# ZONE: Dataset Trace (Multi-Layer View)
with tab_trace:
    st.markdown("<h2 class='main-header'>🔍 Dataset Layer Trace</h2>", unsafe_allow_html=True)
    trace_limit = st.slider("Trace Preview Rows", 1, 20, 5)
    if st.button("Generate Trace Preview"):
        with st.spinner("Processing trace sample..."):
            preview = api_request("POST", "/batch-preview", {"batch_id": "trace", "limit": trace_limit})
            if preview and 'raw' in preview and len(preview['raw']) > 0:
                st.write("### 🟢 Layer 1: Raw Ingestion Input")
                st.dataframe(pd.DataFrame(preview['raw']), use_container_width=True)
                
                st.write("### 🔵 Layer 2: ETL Output (Extracted Features)")
                st.dataframe(pd.DataFrame(preview['etl']), use_container_width=True)
                
                st.write("### 🟡 Layer 3: Volatility Engine Output")
                st.dataframe(pd.DataFrame(preview['vol']), use_container_width=True)
                
                st.write("### 🔴 Layer 4: ML Forecast & SHAP Output")
                st.dataframe(pd.DataFrame(preview['ml']), use_container_width=True)
            else:
                st.error("Trace Preview returned no data. Check if the Testing Queue is empty or if rows are malformed.")

# ZONE 2: ReAct Trace
with tab2:
    st.markdown("<h2 class='main-header'>🤖 Zone 2: Agentic ReAct Trace</h2>", unsafe_allow_html=True)
    
    react_stats = api_request("GET", "/stats/react")
    if react_stats and sum(react_stats.values()) > 0:
        col_re1, col_re2 = st.columns([2, 1])
        
        with col_re1:
            st.subheader("Decision Path Distribution")
            fig_re = px.pie(names=list(react_stats.keys()), values=list(react_stats.values()), 
                           hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_re, use_container_width=True)

        with col_re2:
            st.subheader("Path Breakdown")
            for path, count in react_stats.items():
                if count > 0:
                    st.write(f"**{path}:** {count}")
    else:
        st.warning("No ReAct decisions found in database. Run 'Force ReAct Retrain' to populate.")

# ZONE 3: Drift & Health
with tab3:
    st.markdown("<h2 class='main-header'>🩺 Zone 4: Drift & Health Dashboard</h2>", unsafe_allow_html=True)
    
    d_col1, d_col2 = st.columns(2)
    
    with d_col1:
        st.subheader("Zone 1: Cluster Health (FCM)")
        drift_hist = api_request("GET", "/stats/drift-history")
        if drift_hist:
            df_dh = pd.DataFrame(drift_hist)
            fig_d = go.Figure()
            fig_d.add_trace(go.Scatter(y=df_dh["signal_2_distance"], name="Centroid Drift", line=dict(color="#00ffcc")))
            fig_d.update_layout(title="FCM Centroid Movement (Real-time)", template="plotly_dark")
            st.plotly_chart(fig_d, use_container_width=True)
        else:
            st.info("No drift history available yet.")

    with d_col2:
        st.subheader("Zone 4: SHAP Reliability")
        cos_data = api_request("GET", "/stats/shap-reliability")
        if cos_data and len(cos_data) > 0:
            fig_c = px.histogram(cos_data, nbins=20, title="SHAP Cosine Distribution (Live Data)",
                                 labels={'value': 'Cosine Similarity'},
                                 color_discrete_sequence=['#00b4ff'])
            st.plotly_chart(fig_c, use_container_width=True)
        else:
            st.info("No SHAP reliability data found. Run verification batches to populate.")

# ZONE 4: Intelligence Layer
with tab4:
    st.markdown("<h2 class='main-header'>📈 Zone 3: Intelligence Visualizer</h2>", unsafe_allow_html=True)
    
    intel_stats = api_request("GET", "/stats/intelligence")
    if intel_stats:
        m_i1, m_i2, m_i3 = st.columns(3)
        m_i1.metric("Avg Intelligent Score", intel_stats['avg_intelligent_score'], "+0.02")
        m_i2.metric("Max Confidence", intel_stats['max_confidence'], "🟢")
        m_i3.metric("Total Recommendations", intel_stats['total_recommendations'])
    
    st.subheader("Price Forecast Distribution")
    price_dist = api_request("GET", "/stats/price-distribution")
    if price_dist:
        f_df = pd.DataFrame(price_dist)
        fig_p = px.bar(f_df, y=['current', 'forecast'], barmode='group', 
                       title="Live Price vs. ML Forecast Comparison",
                       color_discrete_map={"current": "#00ffcc", "forecast": "#00b4ff"})
        st.plotly_chart(fig_p, use_container_width=True)
    else:
        st.info("Ingest and verify data to see price distribution.")

# ZONE 5: Human Review (DLQ)
with tab5:
    st.markdown("<h2 class='main-header'>📥 Zone 5: Outcome Tracking (DLQ)</h2>", unsafe_allow_html=True)
    
    dlq_items = api_request("GET", "/dlq/items")
    if dlq_items:
        for item in dlq_items:
            with st.container():
                st.markdown(f"""
                <div class='zone-card'>
                    <h4>{item['product_title']}</h4>
                    <p><b>Decision Path:</b> {item['routing_path']} | <b>Intelligent Score:</b> {item['intelligent_score']:.3f}</p>
                    <p><b>Current Price:</b> EGP {item['current_price']:,} | <b>Category:</b> {item['category']}</p>
                    <p><i>Justification: {item['justification']}</i></p>
                </div>
                """, unsafe_allow_html=True)
                c1, c2, _ = st.columns([1, 1, 4])
                if c1.button("✅ Approve", key=f"app_{item['id']}"):
                    res = api_request("POST", "/dlq/action", {"recommendation_id": item['id'], "action": "approve"})
                    if res:
                        st.toast(f"Approved recommendation {item['id']}")
                        st.rerun()
                if c2.button("❌ Reject", key=f"rej_{item['id']}"):
                    res = api_request("POST", "/dlq/action", {"recommendation_id": item['id'], "action": "reject"})
                    if res:
                        st.toast(f"Rejected recommendation {item['id']}")
                        st.rerun()
    else:
        st.info("No items currently in DLQ. All systems are automated.")
