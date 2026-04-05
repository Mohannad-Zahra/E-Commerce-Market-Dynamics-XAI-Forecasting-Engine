"""
scraper.py
─────────────────────────────────────────────────────────────────────
Main entry point for the batch execution engine.
Combines UTCScheduler, CloudTransport, EmailNotifier, and payloads.
─────────────────────────────────────────────────────────────────────
"""

import json
import logging
import signal
import sys
import importlib
import time as time_module
from pathlib import Path

from engine.scheduler import UTCScheduler
from engine.transport import CloudTransport
from engine.notifier import EmailNotifier
from engine.sleep_prevention import SleepPrevention
from database.local_db import CycleDatabase

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_PATH = BASE_DIR / "config" / "config.json"

_running = True
_scheduler = None

def _signal_handler(signum, frame):
    global _running
    _running = False
    if _scheduler:
        _scheduler.stop()

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[FATAL] Config file not found at {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _setup_logging(config: dict) -> logging.Logger:
    log_cfg = config.get("logging", {})
    logging.basicConfig(
        level=getattr(logging, log_cfg.get("level", "INFO").upper()),
        format=log_cfg.get("log_format", "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"),
        stream=sys.stdout,
    )
    return logging.getLogger("scraper")

def main():
    global _scheduler

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, _signal_handler)

    config = load_config()
    logger = _setup_logging(config)

    logger.info("=" * 65)
    logger.info("SCRAPER STARTED")
    logger.info("=" * 65)

    _scheduler = UTCScheduler(config.get("scrape_intervals_utc", ["00:00", "12:00"]))
    notifier = EmailNotifier(config)
    transport = CloudTransport(config, notifier)
    retailers = config.get("retailers", [])

    def on_cycle(is_catchup, target_utc):
        transport.flush_buffer()
        db_cfg = config.get("database", {})
        db_dir = BASE_DIR / db_cfg.get("cycle_db_dir", "./data/cycles")

        total_inserted = 0
        retailers_scraped = 0
        start_time = time_module.monotonic()

        with CycleDatabase(cycle_dir=db_dir, cycle_timestamp=target_utc) as db:
            for retailer in retailers:
                if not retailer.get("enabled", False):
                    continue
                
                retailer_id = retailer.get("retailer_id")
                payload_module_name = retailer.get("payload_module")
                logger.info("Starting scrape payload for: %s", retailer_id)

                try:
                    payload_module = importlib.import_module(payload_module_name)
                    scraper_obj = payload_module.Scraper()
                    records = scraper_obj.run()
                    inserted, skipped = db.insert_records(records)
                    total_inserted += inserted
                    retailers_scraped += 1
                except Exception as exc:
                    logger.error("Error executing payload for %s: %s", retailer_id, exc, exc_info=True)
                    notifier.notify_scrape_failure(retailer_id, str(exc))

            all_records = db.get_all_records()
            if all_records:
                ts_str = target_utc.strftime("%Y-%m-%dT%H-%M-%SZ")
                transport.upload_cycle_data(all_records, db.cycle_id, ts_str)

        duration = time_module.monotonic() - start_time
        notifier.notify_cycle_complete(total_inserted, retailers_scraped, duration)

    with SleepPrevention():
        # Passing no `last_execution_utc` means it will trigger a catch-up on first launch.
        _scheduler.run(on_cycle=on_cycle)
        
    logger.info("Scraper shutdown complete.")

if __name__ == "__main__":
    main()
