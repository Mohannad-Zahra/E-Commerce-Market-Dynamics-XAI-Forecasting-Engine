"""
main_pipeline.py
================
Orchestrates the full daily recommendation pipeline:

    1. Load  recommendations.json
    2. Validate candidates (gracefully skip broken entries)
    3. For each candidate:
         a. Insert raw record  → electronics_history
         b. Generate LLM explanation
         c. Save final record  → daily_recommendations
    4. Print a summary

Entry point
-----------
    python main_pipeline.py          # run once immediately
    python main_pipeline.py --loop   # run daily at 00:00 UTC

Or import and call programmatically:
    from main_pipeline import run_daily_pipeline
    run_daily_pipeline()
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from database import (
    add_subscriber,
    get_laptop_subscribers,
    get_recommendations,
    init_db,
    insert_laptop,
    save_recommendation,
)
from email_service import dispatch_laptop_alerts
from llm_service import generate_explanation

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_DIR                 = os.path.dirname(os.path.abspath(__file__))
RECOMMENDATIONS_JSON = os.path.join(_DIR, "recommendations.json")

# Demo subscriber – replace / remove as needed.
# In production populate the subscribers table via your sign-up flow.
_DEMO_SUBSCRIBER = {"email": "", "name": ""}


# ---------------------------------------------------------------------------
# 1. Data loading & validation
# ---------------------------------------------------------------------------

def load_candidates(path: str = RECOMMENDATIONS_JSON) -> List[Dict[str, Any]]:
    """
    Load candidates from recommendations.json.
    Returns an empty list if the file is missing or malformed.
    """
    if not os.path.exists(path):
        print(f"[WARN] {path} not found. Run the ML pipeline first.")
        return []

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[ERROR] Could not read {path}: {e}")
        return []

    candidates = data.get("candidates", [])
    if not isinstance(candidates, list):
        print("[ERROR] 'candidates' key is not a list.")
        return []

    print(f"[INFO] Loaded {len(candidates)} candidate(s) from {path}")
    return candidates


def validate_candidate(c: Any) -> bool:
    """Return True only if the candidate has the bare minimum required fields."""
    if not isinstance(c, dict):
        return False
    return bool(c.get("model_id")) and c.get("current_price") is not None


# ---------------------------------------------------------------------------
# 2. Core daily pipeline
# ---------------------------------------------------------------------------

def run_daily_pipeline(json_path: str = RECOMMENDATIONS_JSON) -> None:
    """
    Full pipeline:  load → persist history → LLM → persist recommendation.
    Safe to call manually or from the scheduler.
    """
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*55}")
    print(f" Daily Recommendation Pipeline  |  {run_ts}")
    print(f"{'='*55}")

    # Step 1 – ensure tables exist
    init_db()

    # Step 2 – load candidates
    candidates = load_candidates(json_path)
    if not candidates:
        print("[DONE] No candidates to process.")
        return

    ok_count  = 0
    err_count = 0

    for i, candidate in enumerate(candidates, start=1):
        cid = candidate.get("model_id", f"<item {i}>")
        print(f"\n[{i}/{len(candidates)}] Processing: {cid[:60]}")

        # Validate
        if not validate_candidate(candidate):
            print(f"  ⚠ Skipping – missing required fields.")
            err_count += 1
            continue

        # Step 3a – persist raw record
        hist_ok = insert_laptop(candidate)
        if hist_ok:
            print("  ✓ Saved to electronics_history")
        else:
            print("  ✗ Failed to save history (will still attempt LLM)")

        # Step 3b – generate LLM explanation
        print("  ⏳ Generating explanation …")
        explanation = generate_explanation(candidate)
        print(f"  💬 {explanation[:120]}{'…' if len(explanation) > 120 else ''}")

        # Step 3c – persist recommendation
        rec_ok = save_recommendation(candidate, explanation)
        if rec_ok:
            print("  ✓ Saved to daily_recommendations")
            ok_count += 1
        else:
            print("  ✗ Failed to save recommendation")
            err_count += 1

    # ------------------------------------------------------------------
    # Step 5 – Autonomous Email Notification (SendGrid)
    # ------------------------------------------------------------------
    print("\n[5/5] Dispatching email alerts …")

    # Seed a demo subscriber if the table is empty (first run only)
    subs = get_laptop_subscribers()
    if not subs and _DEMO_SUBSCRIBER["email"]:
        add_subscriber(**_DEMO_SUBSCRIBER, category="laptop")
        subs = get_laptop_subscribers()

    todays_recs = get_recommendations(limit=len(candidates))
    email_result = dispatch_laptop_alerts(subscribers=subs, recommendations=todays_recs)

    print(f"  📧 Emails sent: {email_result['sent']}  |  Failed: {email_result['failed']}")

    print(f"\n{'='*55}")
    print(f" Summary: {ok_count} recommendation(s) stored, "
          f"{err_count} skipped, "
          f"{email_result['sent']} email(s) sent")
    print(f"{'='*55}\n")


# ---------------------------------------------------------------------------
# 3. Simple daily scheduler (--loop flag)
# ---------------------------------------------------------------------------

def _seconds_until_midnight_utc() -> float:
    """Returns seconds remaining until next 00:00:00 UTC."""
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # If we're already past midnight, schedule for tomorrow midnight
    if tomorrow <= now:
        tomorrow = tomorrow.replace(day=tomorrow.day + 1)
    return (tomorrow - now).total_seconds()


def run_scheduler() -> None:
    """
    Runs run_daily_pipeline() once immediately, then every day at 00:00 UTC.
    Stop with Ctrl-C.
    """
    print("[SCHEDULER] Starting daily scheduler (Ctrl-C to stop).")
    while True:
        run_daily_pipeline()
        wait = _seconds_until_midnight_utc()
        wake = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        print(f"[SCHEDULER] Next run at 00:00 UTC – sleeping {wait/3600:.1f} h …")
        time.sleep(wait)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--loop" in sys.argv:
        run_scheduler()
    else:
        run_daily_pipeline()
