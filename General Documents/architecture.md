# System Architecture Document
## E-Commerce Market Dynamics & XAI Forecasting Engine
### Distributed Web Scraping Infrastructure

**Version:** 2.1 (Browser Fix & Security Update)  
**Date:** April 7, 2026  
**Author:** Mohannad Zahra  
**Status:** In Implementation — Infrastructure Completion (58/58 Tests Passing)

---

## 1. System Overview

The infrastructure operates as a **distributed, clock-synchronized data ingestion network** using a **two-process executable architecture** (Watchdog + Scraper):

1. **Edge Nodes (Developer Laptops)** — Each developer runs `watchdog.exe` which supervises `scraper.exe`. The scraper contains the UTC scheduling engine and batch retailer payloads.
2. **Cloud Backend (Google Cloud Platform)** — Centralized data lake, webhook notification endpoint, and optional remote configuration.

### 1.1 High-Level Topology

```
┌──────────────────────────────────────────────────────────────────────┐
│                        EDGE LAYER (Local Machines)                  │
│                                                                      │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │  Developer A  │  │  Developer B  │  │  Developer N  │    ...     │
│   │  ┌──────────┐ │  │  ┌──────────┐ │  │  ┌──────────┐ │          │
│   │  │ watchdog │ │  │  │ watchdog │ │  │  │ watchdog │ │          │
│   │  │   .exe   │ │  │  │   .exe   │ │  │  │   .exe   │ │          │
│   │  │  ┌──────┐│ │  │  │  ┌──────┐│ │  │  │  ┌──────┐│ │          │
│   │  │  │scrape││ │  │  │  │scrape││ │  │  │  │scrape││ │          │
│   │  │  │r.exe ││ │  │  │  │r.exe ││ │  │  │  │r.exe ││ │          │
│   │  │  └──────┘│ │  │  │  └──────┘│ │  │  │  └──────┘│ │          │
│   │  └──────────┘ │  │  └──────────┘ │  │  └──────────┘ │          │
│   │  [SQLite DBs] │  │  [SQLite DBs] │  │  [SQLite DBs] │          │
│   └──────────────┘  └──────────────┘  └──────────────┘              │
│            │                 │                 │                      │
└────────────┼─────────────────┼─────────────────┼─────────────────────┘
             │                 │                 │
             ▼                 ▼                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     CLOUD LAYER (Google Cloud Platform)              │
│                                                                      │
│   ┌─────────────────┐  ┌──────────────┐                             │
│   │  Cloud Storage   │  │   BigQuery    │                             │
│   │  (Bronze Bucket) │  │  (Silver/Gold)│                             │
│   └─────────────────┘  └──────────────┘                             │
└──────────────────────────────────────────────────────────────────────┘
```

Runtime note: both `watchdog.exe` and `scraper.exe` resolve `config/config.json`
from the executable directory first, then fall back to the parent directory.

---

## 2. Component Breakdown

### 2.1 watchdog.exe — Process Supervisor

**File:** `watchdog.py` — **IMPLEMENTED ✅**

**Responsibility:** Launch, monitor, and restart `scraper.exe`. Zero knowledge of scraping logic.

| Feature | Detail |
|---|---|
| Process monitoring | Polls child process every 30 seconds |
| Crash detection | Interprets exit codes (OOM/SIGKILL, general error, clean exit) |
| Restart budget | Max 5 restart attempts with 10s cooldown between each |
| SMTP Email alerts | Dispatches HTML emails via `smtplib` on crash + fatal error |
| Terminal observability | Emits structured `[WATCHDOG_STATUS]` heartbeat lines with PID, uptime, and restart budget |
| Child log visibility | Scraper logs stream directly to terminal and log output |
| Sleep prevention | `SetThreadExecutionState` via `ctypes.windll.kernel32` |
| Signal handling | Graceful shutdown on Ctrl+C / SIGINT / SIGBREAK |
| Dev mode | Runs `python scraper.py` when not frozen as .exe |

```
Watchdog Behavior:
  exit code 0  → Clean exit, do NOT restart
  exit code !0 → Crash detected → restart + email alert
  budget hit   → Fatal email alert → watchdog exits
```

### 2.2 scraper.exe — Batch Execution Engine

**File:** `scraper.py` — **IMPLEMENTED ✅ (2 tests)**

Contains three internal layers:

#### Layer 1: UTC Scheduler (`engine/scheduler.py`) — **IMPLEMENTED ✅ (18 tests)**

**Core Algorithm — Self-Correcting Delta Calculation:**

```python
# Pseudocode — actual implementation in engine/scheduler.py
def calculate_next_target(intervals, now):
    candidates = []
    for interval in intervals:           # e.g., 00:00, 12:00
        target = today at interval (UTC)
        if target <= now:
            target = tomorrow at interval
        candidates.append(target)
    return min(candidates)

# After EVERY cycle, delta is recalculated from scratch.
# NEVER: time.sleep(43200)
```

**Catch-Up Logic:**
- On startup, checks if the most recent past interval was serviced.
- If `last_execution < most_recent_past_interval` → immediate catch-up scrape.
- Drift threshold: if wake time > 60s past target → flagged as catch-up.

**Sleep Strategy:**
- Sleeps in 30-second chunks (not one `sleep(delta)` call).
- Each chunk checks `self._running` for responsive shutdown.
- Uses `datetime.now(timezone.utc)` for wall-clock comparison (detects OS sleep/wake jumps).

#### Layer 2: Scraping Payloads (`payload/`) — **IMPLEMENTED ✅ (4 tests)**

Every retailer scraper must implement:

```python
class ScraperPayload:
    def run(self) -> list[dict]:
        """Return list of Bronze-layer records."""
        # Each record MUST contain:
        # scrape_timestamp, retailer_id, raw_title,
        # raw_current_price, raw_original_price (nullable),
        # availability_text (nullable), product_url
        # Extra fields are preserved in SQLite as JSON blob.
```

**Rate Limiting (HARDCODED — cannot be overridden):**
```python
delay = random.uniform(5.0, 7.0)  # Egyptian Anti-Cybercrime Law 175/2018
time.sleep(delay)
```

#### Layer 3: Data Transport (`engine/transport.py`) — **IMPLEMENTED ✅ (15 tests)**

**Upload Flow with Mandatory Retry:**

```
Scrape completes
    │
    ▼
Validate Bronze schema → invalid records logged & skipped
    │
    ▼
Save to local SQLite (./data/cycles/{timestamp}_{id}.db) → PERMANENT BACKUP
    │
    ▼
Attempt GCP upload (groupped by retailer_id)
    │
    ├── ✅ Success → done
    │
    └── ✖ Failure → retry up to 3 times at 1-minute intervals
         │
         ├── ✅ Retry success → done
         │
         └── ✖ All retries exhausted
              ├── Webhook alert (upload_retry_exhausted)
              └── Buffer to ./data/buffer/{retailer}_{cycle}.json
                  └── Re-attempted on next cycle (flush_buffer)
```

### 2.3 Notification System (`engine/notifier.py`) — **IMPLEMENTED ✅ (8 tests)**

| Event | Source | Trigger |
|---|---|---|
| `scraper_crash` | watchdog | Scraper process exits with code ≠ 0 |
| `fatal_restart_budget_exhausted` | watchdog | 5 crashes, no more restarts |
| `scrape_failed` | scraper | Retailer payload throws exception |
| `upload_retry_failed` | scraper | Cloud upload attempt fails |
| `upload_retry_exhausted` | scraper | All 3 retries exhausted |
| `missed_interval` | scraper | Catch-up execution triggered |
| `cycle_complete` | scraper | Successful cycle completion |

**Implementation:**
Uses Python's native `smtplib` and `email.mime.text`. Alert emails include structured details (retailer info, cycle metadata, retry context). The `cycle_complete` heartbeat now dynamically lists the names of all retailers successfully processed in that specific cycle.

### 2.4 Local Database (`database/local_db.py`) — **IMPLEMENTED ✅ (11 tests)**

Each scrape cycle creates a **new SQLite file** (never reused, never deleted):

```
./data/cycles/
├── 2026-04-05T00-00-00Z_a1b2c3d4.db
├── 2026-04-05T12-00-00Z_e5f6g7h8.db
├── 2026-04-06T00-00-00Z_i9j0k1l2.db
└── ...
```

**Schema:**

| Column | Type | Required |
|---|---|---|
| `id` | INTEGER PK AUTO | auto |
| `scrape_timestamp` | TEXT (ISO 8601) | ✅ |
| `retailer_id` | TEXT | ✅ |
| `raw_title` | TEXT | ✅ |
| `raw_current_price` | TEXT | ✅ |
| `raw_original_price` | TEXT | nullable |
| `availability_text` | TEXT | nullable |
| `product_url` | TEXT | ✅ |
| `category` | TEXT | ✅ |
| `sub_category` | TEXT | nullable |
| `extra_data` | TEXT (JSON) | nullable |
| `inserted_at` | TEXT | auto |

---

## 3. Data Flow — Full Lifecycle

```
PHASE 1: EDGE (Developer Laptop)
══════════════════════════════════

  [Developer launches watchdog.exe]
          │
          ▼
  watchdog.exe activates sleep prevention (kernel32)
          │
          ▼
  watchdog.exe spawns scraper.exe
          │
          ▼
  scraper.exe loads config.json
          │
          ▼
  CHECK CATCH-UP: Was an interval missed?
  ├── YES → Execute immediate catch-up scrape
  └── NO  → Proceed to scheduling
          │
          ▼
  ┌───────────────────────────────────────────────┐
  │              SCHEDULING LOOP                  │
  │                                               │
  │  1. calculate_delta(now, intervals)           │
  │  2. Sleep in 30s chunks until target UTC      │
  │  3. WAKE: flush any buffered data             │
  │  4. FOR EACH enabled retailer:                │
  │     a. Execute payload.run()                  │
  │     b. Rate limit: 5.0-7.0s between requests  │
  │  5. Insert all records into NEW SQLite file   │
  │  6. Upload to GCP Cloud Storage               │
  │     └─ On failure: 3 retries at 1-min each   │
  │     └─ On exhaustion: buffer locally + webhook│
  │  7. Send cycle_complete heartbeat             │
  │  8. LOOP → recalculate delta from scratch     │
  └───────────────────────────────────────────────┘

PHASE 2: CLOUD (GCP)
══════════════════════

  gs://ecommerce-bronze-data/{retailer_id}/{timestamp}_{cycle_id}.json
          │
          ▼
  Cloud Function / Dataflow
  ├── SILVER: normalize text, parse prices, boolean stock
  └── GOLD: FuzzyWuzzy SKU match, EGP rates, sale flags
          │
          ▼
  BigQuery → ML Pipeline (SARIMAX + LightGBM + SHAP)
```

---

## 4. Technology Stack

### Edge Layer

| Component | Technology | Status |
|---|---|---|
| Language | Python 3.11+ | ✅ |
| Packaging | PyInstaller (`--onefile`) | ✅ Implemented |
| HTTP Client | `requests` / `httpx` | ✅ Implemented |
| Browser Automation | Playwright (async) | ✅ Implemented (Absolute Path Patch) |
| HTML Parser | BeautifulSoup4 | ✅ Implemented |
| GCP Client | `google-cloud-storage` | ✅ Implemented |
| Scheduling | `datetime` + `time.sleep()` | ✅ Implemented |
| Logging | Python `logging` (RotatingFileHandler) | ✅ Implemented |
| OS Sleep Prevention | `ctypes.windll.kernel32` | ✅ Implemented |
| Local DB | SQLite3 (stdlib) | ✅ Implemented |
| Notifications | `smtplib` (stdlib) → Gmail Auth | ✅ Implemented |
| Frozen Env Patch | Absolute %LOCALAPPDATA% Path | ✅ Implemented |

### Cloud Layer

| Component | GCP Service |
|---|---|
| Bronze Storage | Cloud Storage (GCS) |
| Silver/Gold | Cloud Functions / Dataflow |
| Analytics | BigQuery |
| Alerts | (Removed in V2.1 — Handled on Edge) |
| Remote Config | Cloud Storage (GCS) |

---

## 5. Directory Structure

```
Web Scrapper/
├── watchdog.py                    ✅ Process supervisor
├── scraper.py                     ✅ Entry point
├── engine/
│   ├── __init__.py
│   ├── scheduler.py               ✅ UTC delta calculator + catch-up
│   ├── transport.py               ✅ GCP upload + 3x retry + buffer
│   ├── notifier.py                ✅ Webhook notification client
│   └── sleep_prevention.py        ✅ Windows kernel32 API
├── payload/
│   ├── __init__.py
│   ├── base.py                    ✅ Abstract base class
│   ├── dummy_retailer.py          ✅ Team boilerplate template
│   ├── twob.py                    ✅ 2B Egypt Playwright payload
│   └── ...                        (retailer-specific payloads)
├── database/
│   ├── __init__.py
│   └── local_db.py                ✅ SQLite per-cycle manager
├── config/
│   ├── config.json                ✅ Full configuration schema
│   └── service_account.json       (GCP credentials — gitignored)
├── data/
│   ├── cycles/                    (per-cycle SQLite backups)
│   └── buffer/                    (store-and-forward failed uploads)
├── logs/                          (rotating log files)
├── tests/
│   ├── test_scheduler.py          ✅ 18 tests
│   ├── test_local_db.py           ✅ 11 tests
│   ├── test_notifier.py           ✅ 8 tests
│   └── test_transport.py          ✅ 15 tests
└── WebScrapper Documents/
    └── Web Scraper Audit.docx
```

---

## 6. Configuration Schema (`config/config.json`)

```json
{
    "version": "1.0.0",
    "developer_id": "mohannad_zahra",
    "developer_email": "mohannad@example.com",
    "scrape_intervals_utc": ["00:00", "12:00"],
    "retailers": [
        {
            "retailer_id": "2b_egypt",
            "enabled": true,
            "payload_module": "payload.twob",
            "target_urls": ["..."]
        },
        {
            "retailer_id": "sigma-computer",
            "enabled": true,
            "payload_module": "payload.sigma",
            "target_urls": ["..."]
        }
    ],
    "rate_limit": { "min_seconds": 5.0, "max_seconds": 7.0 },
    "google_drive": { "folder_id": "...", "credentials_path": "..." },
    "smtp": {
        "host": "smtp.gmail.com",
        "port": 587,
        "sender_email": "...",
        "sender_app_password": "...",
        "team_emails": ["..."]
    },
    "cloud_retry": { "max_retries": 3, "retry_interval_seconds": 60 },
    "watchdog": {
        "health_check_interval_seconds": 30,
        "max_restart_attempts": 5,
        "heartbeat_every_checks": 4
    },
    "database": { "cycle_db_dir": "./data/cycles", "buffer_dir": "./data/buffer" }
}
```

---

## 7. Security & Compliance

| Domain | Measure |
|---|---|
| GCP Credentials | Never committed to Git. Scoped write-only service accounts. |
| GitHub Security | `oauth_credentials.json` sanitized to placeholder before push. `token.json` blocked via `.gitignore`. |
| Rate Limiting | **Hardcoded** 5.0–7.0s. Cannot be overridden via config. |
| Data in Transit | HTTPS (TLS 1.2+) for all GCP uploads. |
| Data at Rest | GCS: Google-managed encryption. Local: SQLite files on developer disk. |
| Legal | Egyptian Anti-Cybercrime Law 175/2018 compliance enforced in code. |

---

## 8. Failure Modes & Recovery

| Failure | Recovery |
|---|---|
| Scraper OOM (3000+ items) | Watchdog restarts scraper + webhook alert |
| Laptop off during interval | Catch-up execution on wake |
| Cloud upload fails | 3x retry at 60s → local buffer → flush next cycle |
| Retailer site changed | Schema validation catches 0-record cycles → webhook |
| Watchdog budget exhausted | Fatal webhook → manual intervention |
| Internet down during scrape | Scrape completes locally (SQLite), upload retried later |

---

*End of Document*
