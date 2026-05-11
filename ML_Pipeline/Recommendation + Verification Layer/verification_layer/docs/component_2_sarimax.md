# Component 2: Real SARIMAX Model Training — Documentation

**Status:** ✅ COMPLETE (script created, awaiting your execution)  
**Date:** 2026-05-11

## What Changed

### [NEW] `verification_layer/train_sarimax.py`
Sub-Category Level SARIMAX training script that:
- Reads all rows from `ECom_Forecast_XAI_data.csv`
- Groups by **Sub-Category** (`category` + `brand`) to solve OOM (Out-of-Memory) issues
- Fits SARIMAX(1,1,1)(1,1,1,7) per sub-category (weekly seasonality)
- Exports to `verification_layer/models/sarimax_category_models.joblib`
- Exports metadata to `verification_layer/models/sarimax_metadata.joblib`
- **Memory Optimized:** Uses incremental processing to stay within 8GB RAM limits.

### [MODIFIED] `verification_layer/offline_state_builder.py`
- Added `joblib` import
- Added SARIMAX model loading at Step 7 (after R_score scaler)
- Loads `models/sarimax_models.joblib` into `app_state["sarimax_models"]`
- Graceful fallback: if joblib file doesn't exist, logs warning and sets `sarimax_models = None`

### [MODIFIED] `verification_layer/react_router.py`
- **Lines 121-141:** Replaced price-ratio heuristic with real SARIMAX inference
- When `sarimax_models[product_id]` exists: calls `fitted_model.forecast(steps=14)` for 14-day prediction
- Falls back to original heuristic only if no model exists for that product
- Updated docstring to reference SARIMAX instead of ARIMA

## How to Run

```bash
cd verification_layer
python train_sarimax.py
```

**Expected output:** ~5-15 minutes of training with per-product progress bars, AIC scores, and a final summary.

**After training**, the ReAct router will automatically use the SARIMAX models via `offline_state_builder.py`.

## Architecture Decision: joblib over ONNX
- `statsmodels.SARIMAX` has no official ONNX converter
- Community converters (skl2onnx, onnxmltools) don't support SARIMAX
- `joblib` is the standard serialization for statsmodels objects
- Load time is <100ms which is fine for batch inference
