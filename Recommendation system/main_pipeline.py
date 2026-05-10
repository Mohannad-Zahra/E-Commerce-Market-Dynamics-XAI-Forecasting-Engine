"""
main_pipeline.py
================
Orchestrates the full daily recommendation pipeline.
Refactored to use SQLAlchemy and event-driven dispatch via FastAPI.
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from database.models import SessionLocal, ElectronicsHistory, DailyRecommendation, init_db
from llm_service import generate_explanation

_DIR                 = os.path.dirname(os.path.abspath(__file__))
RECOMMENDATIONS_JSON = os.path.join(_DIR, "recommendations.json")
KILL_FLAG_FILE       = os.path.join(_DIR, "kill_flag.txt")

def _check_kill_flag():
    if os.path.exists(KILL_FLAG_FILE):
        print("\n[KILL] Kill signal detected! Aborting pipeline.")
        sys.exit(0)

def load_candidates(path: str = RECOMMENDATIONS_JSON) -> List[Dict[str, Any]]:
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
    if not isinstance(c, dict):
        return False
    return bool(c.get("model_id")) and c.get("current_price") is not None

def run_daily_pipeline(json_path: str = RECOMMENDATIONS_JSON) -> None:
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*55}")
    print(f" Daily Recommendation Pipeline  |  {run_ts}")
    print(f"{'='*55}")

    init_db()

    candidates = load_candidates(json_path)
    if not candidates:
        print("[DONE] No candidates to process.")
        return

    ok_count  = 0
    err_count = 0

    db = SessionLocal()
    try:
        for i, candidate in enumerate(candidates, start=1):
            _check_kill_flag()
            
            cid = candidate.get("model_id", f"<item {i}>")
            print(f"\n[{i}/{len(candidates)}] Processing: {cid[:60]}")

            if not validate_candidate(candidate):
                print(f"  ⚠ Skipping – missing required fields.")
                err_count += 1
                continue

            hist = ElectronicsHistory(
                model_id=candidate.get("model_id"),
                model=candidate.get("model"),
                current_price=candidate.get("current_price"),
                price_14d_avg=candidate.get("price_14d_avg"),
                forecasted_price=candidate.get("forecasted_price"),
                r_score=candidate.get("r_score"),
                classification=candidate.get("classification"),
                confidence=candidate.get("confidence"),
                shap_drivers=json.dumps(candidate.get("shap_drivers") or {})
            )
            db.add(hist)
            db.commit()
            print("  ✓ Saved to electronics_history")

            print("  ⏳ Generating explanation …")
            explanation = generate_explanation(candidate)
            print(f"  💬 {explanation[:120]}{'…' if len(explanation) > 120 else ''}")

            rec = DailyRecommendation(
                model_id=candidate.get("model_id"),
                model=candidate.get("model"),
                r_score=candidate.get("r_score"),
                classification=candidate.get("classification"),
                confidence=candidate.get("confidence"),
                llm_explanation=explanation
            )
            db.add(rec)
            db.commit()
            print("  ✓ Saved to daily_recommendations")
            ok_count += 1

    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        db.rollback()
    finally:
        db.close()

    print("\n[5/5] Triggering Email Dispatch Webhook …")
    try:
        resp = requests.post("http://127.0.0.1:8000/events/batch-complete", timeout=5)
        if resp.status_code == 200:
            print("  ✓ Dispatch webhook triggered successfully.")
        else:
            print(f"  ✗ Dispatch webhook failed: {resp.status_code} - {resp.text}")
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Failed to connect to FastAPI backend: {e}")

    print(f"\n{'='*55}")
    print(f" Summary: {ok_count} recommendation(s) stored, {err_count} skipped.")
    print(f"{'='*55}\n")

def _seconds_until_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if tomorrow <= now:
        tomorrow = tomorrow.replace(day=tomorrow.day + 1)
    return (tomorrow - now).total_seconds()

def run_scheduler() -> None:
    print("[SCHEDULER] Starting daily scheduler (Ctrl-C to stop).")
    while True:
        run_daily_pipeline()
        wait = _seconds_until_midnight_utc()
        wake = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
        print(f"[SCHEDULER] Next run at 00:00 UTC – sleeping {wait/3600:.1f} h …")
        time.sleep(wait)

if __name__ == "__main__":
    if "--loop" in sys.argv:
        run_scheduler()
    else:
        run_daily_pipeline()
