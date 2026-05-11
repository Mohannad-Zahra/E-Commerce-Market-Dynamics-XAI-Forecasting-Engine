# Component 6: FastAPI Service — Documentation

**Status:** ✅ COMPLETE  
**Date:** 2026-05-11

## What Changed

### [NEW] `verification_layer/api.py`

Full FastAPI service with 6 endpoints corresponding to loop layers.

### Endpoints

| Endpoint | Method | Purpose | Loop Layer |
|---|---|---|---|
| `/predict` | POST | Run ReAct loop on candidate batch | Inner Loop (7 paths) |
| `/health` | GET | Drift detection status (Signal 1 + 2) | Outer Loop |
| `/retrain` | POST | Manual retrain trigger | Outer Loop |
| `/state` | GET | Model metadata (FPC, FAISS size, etc.) | System State |
| `/feedback` | POST | DLQ approve/reject decision | Feedback Loop |
| `/ingest` | POST | Ingest batch rows, check retrain threshold | Data Ingestion |

### Startup Lifecycle
On `uvicorn` startup:
1. Initializes `agentic_react.db`
2. Calls `load_offline_state()` → loads SVM, FCM, FAISS, SHAP, SARIMAX into `app.state`
3. Creates `DriftMonitor` instance
4. Logs all model metadata to console

### Context Logging
Custom `ContextLoggingMiddleware` logs every request/response with:
- HTTP method + path
- Response status code
- Processing time in seconds

### Auto-Retrain Integration
Both `/predict` and `/ingest` endpoints check the row threshold after processing. If 10K rows have been ingested since last retrain, auto-retrain executes.

## How to Run

```bash
cd verification_layer
pip install fastapi uvicorn  # if not installed
uvicorn api:app --reload --port 8000
```

Then open `http://localhost:8000/docs` for the interactive Swagger UI.

### Example API Calls

```bash
# Check system health
curl http://localhost:8000/health

# Check model state
curl http://localhost:8000/state

# Trigger manual retrain
curl -X POST http://localhost:8000/retrain

# Submit DLQ feedback
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"product_id": "test-123", "decision": "approved", "shap_vector": [0.1, 0.2, ...]}'
```
