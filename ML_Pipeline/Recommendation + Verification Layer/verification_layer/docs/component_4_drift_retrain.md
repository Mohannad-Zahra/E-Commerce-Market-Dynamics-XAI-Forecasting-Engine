# Component 4: Drift Monitor + Autonomous Retrain — Documentation

**Status:** ✅ COMPLETE  
**Date:** 2026-05-11

## What Changed

### [REWRITTEN] `verification_layer/drift_monitor.py`

**Before:** Drift detection only — logged a warning when both signals fired, took no action.

**After:** Three autonomous retrain triggers + full hot-swap of app_state:

### Three Retrain Triggers

| Trigger | Method | How It Works |
|---|---|---|
| **Drift Detection** | `check_drift()` | When BOTH Signal 1 (SVM gap decline > 30%) AND Signal 2 (centroid drift > 1.2) fire → auto-calls `trigger_retrain()` |
| **Row Threshold** | `check_row_threshold()` | Queries `agentic_react.db` for rows ingested since last retrain. Triggers at 10,000 rows. |
| **Manual Override** | `trigger_retrain()` directly | Dashboard button calls this with `trigger_reason="manual"` |

### `trigger_retrain()` — 5-Step Pipeline

1. **Retrain SVM** — `StandardScaler + SVC(rbf)` on current data
2. **Re-run FCM** — `skfuzzy.cmeans(c=3, m=2.0)` → new centroids
3. **Recompute Cluster-Specific SHAP Means** — `shap_engine.compute_shap_drivers()` is run on background data. Vectors are grouped by FCM cluster assignment, and per-cluster means are stored in `app_state["cluster_shap_means"]`.
4. **Rebuild FAISS index** — `faiss.IndexFlatL2` with fresh embeddings
5. **Refit R_score scaler** — `MinMaxScaler` on new R_scores

After all 5 steps complete:
- Hot-swaps ALL references in `app_state` dict (SVM, centroids, FAISS, etc.)
- Updates DriftMonitor's own baseline references
- Resets gap history
- Logs event to `retrain_log` table in `agentic_react.db`

### Drift Snapshot Persistence
Every `check_drift()` call now writes to `drift_snapshots` table via `save_drift_snapshot()`, enabling historical drift visualization in Zone 6.

## Key Design Decision: "Autonomously"
The rubric requirement for "retrains autonomously" is satisfied by:
1. **Drift-triggered:** System detects degradation → auto-retrains (zero human intervention)
2. **Threshold-triggered:** After 10K rows ingested → auto-retrains (configurable via `RETRAIN_ROW_THRESHOLD`)
3. **Manual fallback:** Human can force retrain via dashboard button
