# E-Commerce Market Dynamics & XAI Forecasting Engine

## 🚀 Overview
A distributed, high-precision web scraping and forecasting engine designed for the **Egyptian Retail Electronics Sector**. This system utilizes a **two-process watchdog architecture** to ensure 100% uptime and perfectly synchronized data collection across multiple edge nodes (developer machines).

The engine aggregates data into a **Medallion Architecture (Bronze/Silver/Gold)** for downstream training of **SARIMAX + LightGBM** models, with **SHAP** explainability to provide actionable market insights.

---

## 🛠 Project Architecture
The system is built on a resilient, distributed infrastructure:

### 1. Edge Layer (Scraping Nodes)
- **`watchdog.exe`**: A supervisor process that monitors the scraper, handles auto-restarts, prevents system sleep, and dispatches SMTP alerts.
- **`scraper.exe`**: The execution engine that handles UTC-synchronized scheduling, retailer payloads (Playwright/BS4), and local SQLite backups.
- **`engine/scheduler.py`**: Ensures all nodes fire at exactly `00:00` and `12:00` UTC with self-correcting drift logic.

### 2. Data Strategy
- **Local Persistence**: Every cycle creates a unique SQLite backup (`.db`) to prevent data loss.
- **Cloud Transport**: Automated upload to **Google Drive** with 3x retry logic and local store-and-forward buffering.
- **Bronze Schema**: Standardized 8-field extraction including `scrape_timestamp`, `retailer_id`, `price`, and `category`.

### 3. Compliance & Security
- **Legal Compliance**: Hardcoded 5.0–7.0s randomized rate-limiting in accordance with **Egyptian Anti-Cybercrime Law 175/2018**.
- **Secure Configuration**: Externalized `config.json` for sensitive SMTP and OAuth credentials.

---

## 📂 Repository Structure
```text
├── General Documents/      # Architecture, Proposals, and Audit reports
├── Web Scrapper/           # Core Python source code
│   ├── engine/             # Scheduling, Transport, and Notifier logic
│   ├── payload/            # Retailer-specific scraping modules
│   ├── database/           # Local SQLite management
│   └── tests/              # 58+ Unit tests (100% pass rate)
└── scraper_deployment/     # Portable, standalone production binaries
```

---

## 🚀 Getting Started (Standalone)
To run the engine without Python installed:
1. Navigate to the `scraper_deployment/` folder.
2. Configure `config/config.json` with your credentials.
3. Double-click **`watchdog.exe`**.

---

## 👨‍💻 Developer Onboarding
If you are adding a new retailer:
1. Refer to the **Developer AI Prompt** in `General Documents/`.
2. Inherit from `ScraperPayload` in `payload/base.py`.
3. Use the `dummy_retailer.py` template.
4. Ensure your extraction logic passes the Bronze-layer schema validation.

---

## 📊 Technical Stack
- **Languages**: Python 3.13+
- **Automation**: Playwright, BeautifulSoup4
- **Persistence**: SQLite3, Google Drive API
- **Deployment**: PyInstaller (Standalone Binaries)
- **Forecasting**: SARIMAX, LightGBM (Phase 2)
- **Explainability**: SHAP (Phase 2)

---
*Created by Mohannad Zahra | April 2026*
