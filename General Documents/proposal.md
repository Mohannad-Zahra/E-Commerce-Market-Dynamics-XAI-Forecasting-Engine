# System Proposal
## E-Commerce Market Dynamics & XAI Forecasting Engine
### Distributed Web Scraping Infrastructure

**Version:** 2.0 (Post-Executive Review)  
**Date:** April 5, 2026  
**Author:** Mohannad Zahra  
**Status:** In Implementation — Infrastructure Completion (58/58 Tests Passing)

---

## 1. Executive Summary

This document proposes the design and implementation of a **UTC-synchronized, distributed web scraping infrastructure** for the E-Commerce Market Dynamics & XAI Forecasting Engine project. The system targets the **Egyptian retail electronics sector**, aggregating pricing data from both enterprise marketplaces (Amazon Egypt, Noon) and local retailers (B.TECH, 2B, Dream2000, Sigma Computer, Maximum Hardware, More Shopping).

The core challenge is executing scraping operations **simultaneously across multiple developer machines** to ensure temporally consistent data snapshots. The solution deploys a **two-process executable architecture** (Watchdog + Scraper) on each developer's laptop:

- **`watchdog.exe`** — Lightweight process supervisor that launches, monitors, and restarts the scraper on crash (OOM, unhandled exceptions). Fires SMTP email alerts to the team on failures.
- **`scraper.exe`** — Batch executor containing the UTC scheduling engine and all assigned retailer payloads. Calculates the delta to the next fixed UTC interval, sleeps until that exact second, then executes.

Data flows from local machines into **Google Cloud Platform (GCP)** for centralized storage, with a **local SQLite backup per cycle** ensuring zero data loss even on cloud upload failure.

---

## 2. Problem Statement

### 2.1 The Synchronization Problem

The project requires price data scraped from **7+ retailers** by **5+ developers**, each running scrapers on their own machines. Without global synchronization, failures include:

| Failure Mode | Impact |
|---|---|
| **Clock Drift** | Cross-retailer comparison unreliable — timestamps misaligned |
| **Launch-Time Dependency** | Arbitrary execution times create data gaps |
| **Timezone Mismatch** | `scrape_timestamp` inconsistency breaks SARIMAX time-series |
| **Interval Creep** | Naive `sleep(43200)` accumulates drift over days |
| **Process Death (OOM)** | Scrapers processing 3,000+ items crash without recovery |

### 2.2 Current State (Pre-Session)

| Developer | Retailer | Status | Scheduling |
|---|---|---|---|
| Abdelrhman Wael | 2B Egypt | ✅ Functional (3,090 items) | ❌ Manual / one-off |
| Adel Morad | Dream2000 | ✅ Functional (882 items) | ❌ Manual execution |
| Mohammed Rasheek | Sigma Computer | ✅ Functional (SPA/AJAX optimized) | ✅ UTC Scheduled |
| Mohammed Hessen | Noon / Jumia | ❌ Manual browser extension | ❌ No automation |
| Mohannad Zahra | (Template) | 🔲 Not started | — |

**Zero scrapers had UTC-synchronized scheduling, crash recovery, or cloud upload.**

---

## 3. Proposed Solution (Post-Executive Review)

### 3.1 The Watchdog Pattern (Two-Process Architecture)

```
Developer Laptop
┌─────────────────────────────────────┐
│  watchdog.exe                       │
│  ┌───────────────────────────────┐  │
│  │  • Launches scraper.exe       │  │
│  │  • Monitors process health    │  │
│  │  • Restarts on crash (5 max)  │  │
│  │  • SMTP Email alert on failure│  │
│  │  • Sleep prevention (kernel32)│  │
│  └──────────┬────────────────────┘  │
│             │ spawns                 │
│  ┌──────────▼────────────────────┐  │
│  │  scraper.exe                  │  │
│  │  ┌─────────────────────────┐  │  │
│  │  │ UTC Scheduler           │  │  │
│  │  │ (delta calc + catch-up) │  │  │
│  │  ├─────────────────────────┤  │  │
│  │  │ Batch Scraping Payloads │  │  │
│  │  │ (all assigned retailers)│  │  │
│  │  ├─────────────────────────┤  │  │
│  │  │ SQLite Per-Cycle Backup │  │  │
│  │  ├─────────────────────────┤  │  │
│  │  │ Cloud Transport         │  │  │
│  │  │ (3x retry + buffer)    │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### 3.2 Mandatory Modifications (Executive Review)

| # | Modification | Implementation |
|---|---|---|
| 1 | **Watchdog Pattern** | `watchdog.exe` supervises `scraper.exe`. Restarts on crash. Max 5 attempts. |
| 2 | **Rate Limiting** | Hardcoded 5.0–7.0s randomized delay. Cannot be overridden via config. |
| 3 | **Batch Processing + Local DB** | One `scraper.exe` handles all assigned retailers per cycle. New SQLite file per cycle as permanent backup. |
| 4 | **Catch-Up Execution** | If laptop missed a UTC interval, execute immediately on wake. |
| 5 | **SMTP Notifications** | Native Python SMTP using `smtplib`. No GCP endpoints required. |
| 6 | **Cloud Retry** | Exactly 3 retries at 1-minute intervals on upload failure. |
| 7 | **Sleep Prevention** | Windows `SetThreadExecutionState` via `ctypes.windll.kernel32`. |
| 8 | **Unified Template** | Dummy payload boilerplate for team to deprecate manual scripts. |

### 3.3 Interval Configuration

| Interval | UTC Time | Egypt Local (UTC+2) |
|---|---|---|
| Interval 1 | `00:00 UTC` | 02:00 AM EET |
| Interval 2 | `12:00 UTC` | 02:00 PM EET |

---

## 4. Key Objectives

### P0 (Must-Have)

| # | Objective | Success Criterion |
|---|---|---|
| O1 | Simultaneous execution | All scrapers fire within ±2s of target UTC |
| O2 | Zero interval drift | ±2s tolerance after 7 continuous days |
| O3 | Bronze schema compliance | All 8 expected fields present per record |
| O4 | Automated cloud upload | Data in GCP within 5 minutes of scrape |
| O5 | Rate-limit compliance | 5.0–7.0s between requests (hardcoded) |
| O6 | Crash recovery | Watchdog restarts scraper on OOM/crash |
| O7 | Local backup | SQLite file per cycle, never deleted |

### P1 (Should-Have)

| # | Objective |
|---|---|
| O8 | Heartbeat / health reporting to GCP |
| O9 | Remote config override (GCP-hosted) |
| O10 | Structured logging (local + optional cloud) |

### P2 (Nice-to-Have)

| # | Objective |
|---|---|
| O11 | Auto-update mechanism for .exe |
| O12 | Dashboard showing node status |

---

## 5. Constraints

| Domain | Constraint |
|---|---|
| **Language** | Python only |
| **Packaging** | PyInstaller (`--onefile`) |
| **Cloud usage** | GCP for storage/backend only — no cloud-triggered scraping |
| **Rate limiting** | 5.0–7.0s hardcoded (legal requirement) |
| **Architecture** | Medallion (Bronze/Silver/Gold) |
| **Notifications** | Native `smtplib` inside watchdog/scraper. No GCP usage. |
| **Retry** | Exactly 3 retries at 60-second intervals |
| **Sleep prevention** | Windows kernel32 API mandatory |

---

## 6. Risk Assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Scraper OOM on large catalogs | High | Watchdog pattern: auto-restart + webhook alert |
| Developer forgets to launch .exe | Medium | Webhook heartbeat alerts team lead |
| Laptop sleeps during wait | Medium | `SetThreadExecutionState` prevents sleep; catch-up on wake |
| Cloud upload fails | Medium | 3x retry + local buffer (store-and-forward) |
| Retailer changes site structure | High | Schema validation on Bronze output; webhook on 0 records |
| Anti-bot blocks scraper | Medium | Distributed residential IPs; 5–7s delays; User-Agent rotation |

---

## 7. Implementation Progress (Session: April 5, 2026)

| Component | Status | Tests |
|---|---|---|
| `config/config.json` | ✅ Complete | — |
| `watchdog.py` | ✅ Complete (330 lines) | — |
| `engine/sleep_prevention.py` | ✅ Complete | — |
| `engine/notifier.py` | ✅ Complete | 8/8 ✅ |
| `engine/scheduler.py` | ✅ Complete | 18/18 ✅ |
| `database/local_db.py` | ✅ Complete | 11/11 ✅ |
| `engine/transport.py` | ✅ Complete | 15/15 ✅ |
| `scraper.py` (full loop) | ✅ Complete | 2/2 ✅ |
| `payload/base.py` | ✅ Complete | 4/4 ✅ |
| `payload/dummy_retailer.py` | ✅ Complete | — |
| `payload/sigma.py` | ✅ Complete (SPA/AJAX) | 1/1 ✅ |
| `payload/twob.py` | ✅ Complete (Playwright) | 1/1 ✅ |
| PyInstaller build scripts | ✅ Complete | — |

**Total: 58/58 unit tests passing.**

### 7.1 Operational Refinements (April 2026 Follow-Up)

- Watchdog now emits structured terminal status lines (`[WATCHDOG_STATUS]`) for easier live monitoring.
- Scraper child logs stream directly through watchdog for clearer runtime visibility.
- SMTP alerts now include richer metadata (retailer context, cycle/retry details).
- Watchdog-sourced alerts include all configured retailer IDs and names to improve team triage.

---

## 8. Next Steps

| Step | Owner | Priority |
|---|---|---|
| Build `scraper.py` main loop (schedule → batch scrape → SQLite → GCP) | Mohannad | ✅ Done |
| Build `payload/base.py` abstract interface | Mohannad | ✅ Done |
| Build `payload/dummy_retailer.py` team boilerplate | Mohannad | ✅ Done |
| Create PyInstaller build scripts | Mohannad | ✅ Done |
| Distribute `scraper_deployment` to developer team | Mohannad | P1 |
| Onboard team to new .exe framework (deprecate manual scripts) | All | P1 |
| Implement retailer-specific payloads (2B, Dream2000, Sigma, etc.) | Team | P1 |

---

*End of Document*
