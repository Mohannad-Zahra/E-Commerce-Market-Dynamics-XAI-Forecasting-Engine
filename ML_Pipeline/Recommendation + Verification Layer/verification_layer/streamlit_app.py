import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import plotly.express as px
import plotly.graph_objects as go
import json

# Ensure modules can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Recommendation system"))
import react_router
from offline_state_builder import load_offline_state
from ranking_engine import calculate_r_score
from drift_monitor import DriftMonitor, RETRAIN_ROW_THRESHOLD
from agentic_db import (
    init_agentic_db, insert_ingested_rows, get_rows_since_last_retrain,
    get_total_ingested_count, save_dlq_decision, get_dlq_history,
    get_dlq_stats, get_retrain_history, get_drift_history, save_drift_snapshot,
)

st.set_page_config(page_title="Agentic Verification Monitor", layout="wide", initial_sidebar_state="expanded")

# --- CUSTOM CSS FOR PREMIUM LOOK ---
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    .zone-card {
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        background-color: #0d1117;
        margin-bottom: 20px;
    }
    .status-pass { color: #238636; font-weight: bold; }
    .status-fail { color: #da3633; font-weight: bold; }
    .status-partial { color: #d29922; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🤖 Agentic ReAct Verification Framework")
st.markdown("### Compliance Level: 🟢 High | Version: 2.0 — Full Autonomous Loop")

# Sidebar Configuration
st.sidebar.header("⚙️ Router Configuration")
react_router.QUOTA_LIMIT = st.sidebar.slider("Quota Limit", 1, 50, 7, 1)
react_router.BASE_THRESHOLD = st.sidebar.slider("Base Threshold (Path 7)", 0.0, 1.0, 0.2, 0.05)
react_router.MIN_MARGIN = st.sidebar.slider("Min Margin (SVM Gap)", 0.0, 5.0, 0.5, 0.1)
react_router.MIN_PROB = st.sidebar.slider("Min Prob (FCM)", 0.0, 1.0, 0.4, 0.05)
react_router.RELIABILITY_THRESHOLD = st.sidebar.slider("Reliability Threshold", 0.0, 1.0, 0.6, 0.05)

# Sidebar: System Status
st.sidebar.markdown("---")
st.sidebar.header("📊 System Status")
total_ingested = get_total_ingested_count()
rows_since_retrain = get_rows_since_last_retrain()
dlq_stats = get_dlq_stats()
st.sidebar.metric("Total Ingested Rows", f"{total_ingested:,}")
st.sidebar.metric("Rows Since Last Retrain", f"{rows_since_retrain:,}/{RETRAIN_ROW_THRESHOLD:,}")
st.sidebar.metric("DLQ Decisions (Approve/Reject)", f"{dlq_stats['approved']}/{dlq_stats['rejected']}")


@st.cache_data
def load_data_and_rank(limit=20):
    csv_path = os.path.join(os.path.dirname(__file__), "..", "ECom_Forecast_XAI_data.csv")
    df = pd.read_csv(csv_path, nrows=10000)
    
    # Deterministic price calculation (No Mocking)
    if "current_price" not in df.columns:
        df["current_price"] = df["price_t_plus_14"] / (1 + df["delta_p_14d"].fillna(0))
    if "price_14d_avg" not in df.columns:
        p_t_7 = df["price_t_plus_14"] / (1 + (df["delta_p_14d"] - df["delta_p_7d"]).fillna(0))
        df["price_14d_avg"] = (df["current_price"] + p_t_7) / 2
        
    df["forecasted_price"] = df["price_t_plus_14"]
    df["volatility_score"] = 100 - df["predicted_stability_score"]
    df["months_since_release"] = df["D_months"]
    
    df = df.drop_duplicates(subset=["raw_title"])
    df["r_score"] = calculate_r_score(df)
    top_candidates = df.sort_values("r_score", ascending=False).head(limit)
    
    candidates = []
    for _, row in top_candidates.iterrows():
        c = {
            "model_id": str(row["product_id"]),
            "product_title": str(row.get("raw_title", "Unknown")),
            "category": str(row.get("category", "Electronics")),
            "current_price": float(row["current_price"]),
            "price_14d_avg": float(row["price_14d_avg"]),
            "forecasted_price": float(row["forecasted_price"]),
            "volatility_score": float(row["volatility_score"]),
            "months_since_release": float(row["months_since_release"]),
            "r_score": float(row["r_score"]),
            "vol_30d": float(row.get("vol_30d", 20))
        }
        candidates.append(c)
    return candidates, df.head(100) # Return sample for drift monitor

# Initialize State
if "app_state" not in st.session_state:
    with st.status("Training Offline State...") as status:
        st.session_state["app_state"] = load_offline_state()
        st.session_state["drift_monitor"] = DriftMonitor(st.session_state["app_state"])
        status.update(label="Offline State Loaded!", state="complete")

app_state = st.session_state["app_state"]
drift_monitor = st.session_state["drift_monitor"]

# --- LAYOUT: 6 ZONES ---

# Zone 6: System Alerts (Top Banner)
drift_status = drift_monitor.check_drift(app_state["background_df"].sample(100))
if drift_status.get("retrain_executed"):
    st.success(f"🔄 **ZONE 6: SYSTEM ALERT** — DRIFT DETECTED + AUTO-RETRAIN EXECUTED. System recalibrated.")
elif drift_status["overall_drift"]:
    st.error(f"🚨 **ZONE 6: SYSTEM ALERT** - CRITICAL DRIFT DETECTED (Signal 1: {drift_status['signal_1']['degradation']:.1%}, Signal 2: {drift_status['signal_2']['centroid_distance']:.2f})")
else:
    st.info(f"✅ **ZONE 6: SYSTEM ALERTS** - Drift Monitoring Active. Status: Stable (Gap Median: {drift_status['signal_1']['median_gap']:.2f})")

# Row threshold check
should_retrain, rows_since = drift_monitor.check_row_threshold()
if should_retrain:
    st.warning(f"📊 **ROW THRESHOLD REACHED** — {rows_since:,} rows ingested since last retrain. Auto-retrain recommended.")
    if st.button("🔄 Execute Threshold Retrain Now"):
        with st.spinner("Retraining models..."):
            new_state = drift_monitor.trigger_retrain(
                source_df=app_state["background_df"],
                trigger_reason="row_threshold",
            )
            if new_state:
                st.success("✅ Retrain complete! Models updated in-memory.")
                st.rerun()

tab1, tab2, tab3, tab4 = st.tabs(["📊 Live Monitoring", "📈 Model Health", "📋 Outcome Tracking", "🔧 System Control"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🌐 Zone 2: Live Scoring Feed")
        if st.button("🚀 Execute Daily ReAct Batch"):
            candidates, batch_df = load_data_and_rank(limit=20)
            dispatched, dlq = react_router.run_react_loop(candidates, app_state)
            st.session_state["dispatched"] = dispatched
            st.session_state["dlq"] = dlq
            st.session_state["batch_results"] = candidates
            
            # Persist all routed candidates to DB
            insert_ingested_rows(candidates)
            
        if "batch_results" in st.session_state:
            res_df = pd.DataFrame(st.session_state["batch_results"])
            res_df["score"] = res_df["model_id"].apply(lambda x: next((c["intelligent_score"] for c in st.session_state["batch_results"] if c["model_id"] == x), 0))
            
            fig = px.bar(res_df, x="model_id", y="score", color="score", title="Composite Intelligent Scores", color_continuous_scale="Viridis")
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(res_df[["model_id", "product_title", "r_score", "score"]].rename(columns={"score": "Intelligent_Score"}), use_container_width=True)

    with col2:
        st.subheader("🎯 Zone 3: Action Dispatch")
        if "dispatched" in st.session_state:
            st.metric("Total Dispatched", len(st.session_state["dispatched"]))
            for d in st.session_state["dispatched"]:
                with st.expander(f"📦 {d['product_title'][:40]}..."):
                    st.write(f"**Path:** `{d['routing_path']}`")
                    st.write(f"**Intelligent Score:** `{d['intelligent_score']:.4f}`")
                    st.progress(d['intelligent_score'])

with tab2:
    z_col1, z_col2 = st.columns(2)
    
    with z_col1:
        st.subheader("🏥 Zone 1: Cluster Health (FCM)")
        st.write(f"**Fuzzy Partition Coefficient (FPC):** `{app_state['fpc']:.4f}`")
        centroids = app_state["fcm_centroids"]
        c_df = pd.DataFrame(centroids, columns=react_router.SHAP_COLS[:centroids.shape[1]] if centroids.shape[1] < len(react_router.SHAP_COLS) else [f"F_{i}" for i in range(centroids.shape[1])])
        st.write("Centroid Coordinates (Scaled):")
        st.dataframe(c_df.style.background_gradient(cmap='Blues'), use_container_width=True)
        
        # Retrain history
        retrain_hist = get_retrain_history(limit=5)
        if retrain_hist:
            st.write("**Recent Retrain Events:**")
            for r in retrain_hist:
                st.write(f"  • `{r['retrained_at']}` — {r['trigger_reason']} (FPC: {r['fpc_before']:.4f} → {r['fpc_after']:.4f}, {r['duration_seconds']:.1f}s)")

    with z_col2:
        st.subheader("🛡️ Zone 4: SHAP Reliability")
        if "batch_results" in st.session_state:
            cosines = [c["signals"]["SHAP_cos"] for c in st.session_state["batch_results"]]
            fig_cos = px.histogram(cosines, nbins=10, title="SHAP Cosine Distribution (vs Mean)", labels={'value': 'Cosine Similarity'})
            st.plotly_chart(fig_cos, use_container_width=True)
            st.write(f"**Mean SHAP Reliability:** `{np.mean(cosines):.4f}`")

with tab3:
    st.subheader("📝 Zone 5: Outcome Tracking & Human Review")
    
    # DLQ with REAL feedback loop
    if "dlq" in st.session_state and len(st.session_state["dlq"]) > 0:
        st.write(f"**Dead Letter Queue Count:** `{len(st.session_state['dlq'])}`")
        
        for idx, d in enumerate(st.session_state["dlq"]):
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.write(f"**{d.get('product_title', d['model_id'][:40])}** (Path: {d['routing_path']})")
            
            if c2.button("✅ Approve", key=f"app_{idx}"):
                # 1. Write decision to database
                save_dlq_decision(d, decision="approved")
                
                # 2. Inject SHAP vector into live FAISS index
                if "shap_vector" in d:
                    shap_vec = np.array(d["shap_vector"], dtype=np.float32).reshape(1, -1)
                    app_state["faiss_index"].add(shap_vec)
                    # Append label to historical_labels
                    app_state["historical_labels"] = np.append(
                        app_state["historical_labels"], "Deflating Arbitrage"
                    )
                
                # 3. Remove from DLQ in session state
                st.session_state["dlq"].pop(idx)
                st.toast(f"✅ Approved {d['model_id'][:40]} — FAISS updated ({app_state['faiss_index'].ntotal} vectors)")
                st.rerun()
                
            if c3.button("❌ Reject", key=f"rej_{idx}"):
                # 1. Write rejection to database
                save_dlq_decision(d, decision="rejected")
                
                # 2. Remove from DLQ
                st.session_state["dlq"].pop(idx)
                st.toast(f"❌ Rejected {d['model_id'][:40]} — recorded in DB")
                st.rerun()
    else:
        st.info("No pending DLQ candidates. Run a batch to see outcomes.")
    
    # Historical decisions table
    st.markdown("---")
    st.write("**📋 Decision History (from Database)**")
    dlq_history = get_dlq_history(limit=20)
    if dlq_history:
        hist_df = pd.DataFrame(dlq_history)
        display_cols = [c for c in ["product_id", "raw_title", "routing_path", "decision", "decided_at"] if c in hist_df.columns]
        st.dataframe(hist_df[display_cols], use_container_width=True)
        
        # Stats
        stats = get_dlq_stats()
        sc1, sc2, sc3 = st.columns(3)
        sc1.metric("Total Decisions", stats["total"])
        sc2.metric("Approved", stats["approved"])
        sc3.metric("Rejected", stats["rejected"])
    else:
        st.write("No decisions recorded yet.")

with tab4:
    st.subheader("🔧 System Control Panel")
    
    ctrl_col1, ctrl_col2 = st.columns(2)
    
    with ctrl_col1:
        st.write("**Manual Retrain**")
        st.write("Force a full model retrain cycle regardless of drift signals.")
        if st.button("🔄 Force Manual Retrain"):
            with st.spinner("Executing retrain cycle..."):
                new_state = drift_monitor.trigger_retrain(
                    source_df=app_state["background_df"],
                    trigger_reason="manual",
                )
                if new_state:
                    st.success(f"✅ Retrain complete! New FPC: {new_state['fpc']:.4f}")
                    st.rerun()
                else:
                    st.error("❌ Retrain failed. Check logs.")
    
    with ctrl_col2:
        st.write("**Upload 10K Rows**")
        st.write("Upload a CSV batch to ingest into the system. Triggers retrain if threshold is reached.")
        uploaded_file = st.file_uploader("Upload CSV batch", type=["csv"], key="batch_upload")
        if uploaded_file is not None:
            with st.spinner("Ingesting batch..."):
                batch_df = pd.read_csv(uploaded_file)
                
                # Derive prices if needed
                if "current_price" not in batch_df.columns and "price_t_plus_14" in batch_df.columns:
                    batch_df["current_price"] = batch_df["price_t_plus_14"] / (1 + batch_df["delta_p_14d"].fillna(0))
                if "forecasted_price" not in batch_df.columns and "price_t_plus_14" in batch_df.columns:
                    batch_df["forecasted_price"] = batch_df["price_t_plus_14"]
                
                rows = batch_df.to_dict('records')
                count = insert_ingested_rows(rows)
                st.success(f"✅ Ingested {count:,} rows into database.")
                
                # Check retrain threshold
                should_retrain, rows_since = drift_monitor.check_row_threshold()
                if should_retrain:
                    st.warning(f"🔄 Row threshold reached ({rows_since:,} rows). Triggering auto-retrain...")
                    new_state = drift_monitor.trigger_retrain(
                        source_df=app_state["background_df"],
                        trigger_reason="row_threshold",
                    )
                    if new_state:
                        st.success("✅ Auto-retrain complete!")
                        st.rerun()
    
    # Drift History
    st.markdown("---")
    st.write("**📈 Drift Signal History**")
    drift_hist = get_drift_history(limit=20)
    if drift_hist:
        drift_df = pd.DataFrame(drift_hist)
        fig_drift = go.Figure()
        fig_drift.add_trace(go.Scatter(
            y=drift_df["signal_1_median_gap"],
            mode="lines+markers",
            name="Signal 1: SVM Gap Median",
            line=dict(color="#3b82f6"),
        ))
        fig_drift.add_trace(go.Scatter(
            y=drift_df["signal_2_distance"],
            mode="lines+markers",
            name="Signal 2: Centroid Distance",
            line=dict(color="#ef4444"),
        ))
        fig_drift.update_layout(
            title="Drift Signals Over Time",
            xaxis_title="Snapshot Index",
            yaxis_title="Signal Value",
            template="plotly_dark",
        )
        st.plotly_chart(fig_drift, use_container_width=True)
    else:
        st.write("No drift snapshots recorded yet. Run a batch to start monitoring.")
    
    # Retrain History Table
    st.write("**🔄 Retrain History**")
    retrain_hist = get_retrain_history()
    if retrain_hist:
        rt_df = pd.DataFrame(retrain_hist)
        display_cols = [c for c in ["trigger_reason", "fpc_before", "fpc_after", "faiss_size_before", "faiss_size_after", "duration_seconds", "retrained_at"] if c in rt_df.columns]
        st.dataframe(rt_df[display_cols], use_container_width=True)
    else:
        st.write("No retrain events recorded yet.")
