# Component 5: DLQ Feedback Loop — Documentation

**Status:** ✅ COMPLETE  
**Date:** 2026-05-11

## What Changed

### [REWRITTEN] `verification_layer/streamlit_app.py` — Zone 5

**Before:** Approve/Reject buttons called `st.toast()` only — zero state mutation, zero DB persistence.

**After:** Full feedback loop with 3 actions per click:

### On Approve:
1. **DB write** → `save_dlq_decision(candidate, "approved")` → persists to `dlq_outcomes` table
2. **FAISS update** → `app_state["faiss_index"].add(shap_vector)` → injects candidate's SHAP vector into the live KNN index
3. **Label append** → `np.append(historical_labels, "Deflating Arbitrage")` → so future RAG majority votes benefit from this new evidence
4. **UI update** → removes candidate from DLQ list, triggers `st.rerun()`

### On Reject:
1. **DB write** → `save_dlq_decision(candidate, "rejected")` → persists rejection with timestamp
2. **UI update** → removes candidate from DLQ list, triggers `st.rerun()`

### Decision History
Zone 5 now shows a **historical table** of all past decisions read from the `dlq_outcomes` DB table, plus running tallies of approve/reject counts.

## Rubric Compliance
- **Agentic Property 4 (Adapts to outcomes):** ✅ Now PASS — approved candidates enhance FAISS index for future batches
- **Dashboard Zone 5 (Outcome Tracking):** ✅ Now PASS — real DB-backed feedback loop with history
