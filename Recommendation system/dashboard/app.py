import time
import requests
import streamlit as st
import pandas as pd

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

API_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="RecSys Dashboard", layout="wide")

if HAS_AUTOREFRESH:
    # Poll every 3 seconds
    st_autorefresh(interval=3000, limit=None, key="dashboard_autorefresh")

def fetch_data(endpoint: str):
    try:
        resp = requests.get(f"{API_BASE_URL}/{endpoint}", timeout=2)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

st.title("🎛️ Central Management Dashboard")

# 1. Pipeline Status & 6. System Health
st.header("System Health & Status")
metrics = fetch_data("metrics")

if metrics:
    status = metrics.get("status", "Unknown")
    color = "green" if status == "Running" else "gray"
    st.markdown(f"**Pipeline Status:** <span style='color:{color}; font-weight:bold;'>{status}</span>", unsafe_allow_html=True)
    st.markdown("**API Health:** 🟢 Online")
else:
    st.markdown("**Pipeline Status:** 🔴 Offline")
    st.markdown("**API Health:** 🔴 Offline")
    st.error("Could not connect to FastAPI backend. Ensure uvicorn api.main:app --reload is running.")
    st.stop()

st.divider()

# 5. System Controls
st.header("⚙️ System Controls")
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("▶️ Start Batch"):
        resp = requests.post(f"{API_BASE_URL}/trigger")
        if resp.status_code == 200:
            st.success("Batch started.")
        else:
            st.error(f"Error: {resp.text}")
with col2:
    if st.button("⏹️ Kill Switch"):
        resp = requests.post(f"{API_BASE_URL}/kill")
        if resp.status_code == 200:
            st.warning("Kill signal sent.")
with col3:
    if st.button("🔄 Manual Retrain"):
        resp = requests.post(f"{API_BASE_URL}/retrain")
        if resp.status_code == 200:
            st.info("Retrain triggered.")
with col4:
    if st.button("🔃 Refresh Now"):
        st.rerun()

st.divider()

# 3. Metrics Overview
st.header("📊 Metrics Overview")
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
m_col1.metric("Candidates Scraped", metrics.get("total_candidates_scraped", 0))
m_col2.metric("Recommendations Made", metrics.get("total_recommendations_made", 0))
m_col3.metric("Emails Attempted", metrics.get("total_emails_attempted", 0))
m_col4.metric("Email Success Rate", f"{metrics.get('email_success_rate', 0)}%")

st.divider()

# 4. Recommendation Preview
st.header("🏆 Recent Recommendations")
recs_data = fetch_data("recommendations")
if recs_data and recs_data.get("recommendations"):
    df = pd.DataFrame(recs_data["recommendations"])
    st.dataframe(df, use_container_width=True)
else:
    st.info("No recommendations found.")

st.divider()

# 2. Live Logs Console
st.header("📝 Live Logs Console")
logs_data = fetch_data("logs")
if logs_data and logs_data.get("logs"):
    logs_str = "".join(logs_data["logs"])
    st.text_area("Pipeline Logs", value=logs_str, height=300, disabled=True)
else:
    st.text_area("Pipeline Logs", value="No logs to display.", height=300, disabled=True)
