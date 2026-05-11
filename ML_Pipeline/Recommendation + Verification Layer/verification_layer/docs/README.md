# Agentic ReAct Verification Framework — Documentation Hub

This directory contains detailed technical documentation for each component of the Agentic ReAct Verification Layer.

## Documentation Index

| Component | Title | Description |
| :--- | :--- | :--- |
| [Component 1](component_1_cleanup.md) | **System Cleanup** | Removal of mock code and deterministic price derivation. |
| [Component 2](component_2_sarimax.md) | **SARIMAX Training** | Sub-Category level forecasting with memory optimization. |
| [Component 3](component_3_database.md) | **Database Layer** | SQLite persistence and 100K row migration. |
| [Component 4](component_4_drift_retrain.md) | **Drift & Retrain** | Autonomous degradation detection and state hot-swapping. |
| [Component 5](component_5_dlq_feedback.md) | **DLQ Feedback** | Human-in-the-loop decisions and FAISS index injection. |
| [Component 6](component_6_fastapi.md) | **FastAPI Service** | Production-ready API with layer-corresponding endpoints. |
| [Component 7](component_7_compliance_audit.md) | **Compliance Audit** | **Final Audit Results (100% PASS)** and logic remediations. |

---

## Architecture Overview

The Agentic ReAct Framework is designed as a high-fidelity verification layer that sits atop the initial recommendation gating. It implements a dual-loop architecture:

1.  **Inner Loop (ReAct Router):** A 7-path decision engine that uses 5 independent ML signals to observe, reason, and act on product candidates.
2.  **Outer Loop (Drift Monitor):** An autonomous surveillance system that detects model degradation and triggers a full retraining cycle of the FCM, SVM, and RAG components.

### Core Technologies
- **Logic:** Python 3.x
- **ML/Stats:** `scikit-learn`, `skfuzzy`, `statsmodels` (SARIMAX), `shap` (KernelExplainer)
- **Search:** `faiss-cpu` (K-NN Vector Search)
- **Persistence:** `sqlite3`
- **Dashboard:** `streamlit`
- **API:** `fastapi` + `uvicorn`

---

## Final Defense Readiness
As of **2026-05-11**, the system is in a **100% Compliant** state relative to the academic rubric. All logic is dynamic, data-driven, and lacks any hardcoded or mocked components.
