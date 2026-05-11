# Component 1: Cleanup — Documentation

**Status:** ✅ COMPLETE  
**Date:** 2026-05-11

## Changes Made

### 1. Deleted `mock_state_loader.py`
- **Reason:** Dead code containing `MockSVM` (random decisions) and `MockFAISSIndex` (random distances). The live system uses `offline_state_builder.py` exclusively. This file's presence was a red flag for academic review.
- **Impact:** None — no other file imports from `mock_state_loader.py`.

### 2. Fixed `test_agentic_layer.py` — Random Price Generation
- **Before (Lines 21-23):**
  ```python
  df["current_price"] = df["price_t_plus_14"] * np.random.uniform(0.9, 1.1, len(df))
  df["price_14d_avg"] = df["current_price"] * np.random.uniform(0.95, 1.05, len(df))
  ```
- **After:**
  ```python
  df["current_price"] = df["price_t_plus_14"] / (1 + df["delta_p_14d"].fillna(0))
  p_t_7 = df["price_t_plus_14"] / (1 + (df["delta_p_14d"] - df["delta_p_7d"]).fillna(0))
  df["price_14d_avg"] = (df["current_price"] + p_t_7) / 2
  ```
- **Reason:** Uses the same deterministic derivation formula as `offline_state_builder.py` and `streamlit_app.py`. No random data anywhere in the pipeline.

### 3. Calibrated RAG Decision Matrix (Path 3 vs Path 5)
- **Before:** `buy_votes == 3` (60% majority) was intercepted by Path 5 (Tie logic), requiring an ARIMA trend check to approve.
- **After:** `buy_votes == 3` now falls through to Path 3 (Standard Majority), allowing immediate approval. Path 5 is reserved for true split votes or fringe minorities (`buy_votes == 2`).
- **Reason:** Aligns with standard majority-vote principles and reduces over-cautiousness in high-confidence RAG retrieval cases.

## Verification
Run `python test_agentic_layer.py` from the `verification_layer/` directory. Output should show deterministic R_scores and correct Path 3/Path 5 routing for RAG candidates.
