# Web Scraper Audit & Inventory Report
## E-Commerce Market Dynamics & XAI Forecasting Engine
### Updated: April 5, 2026

---

## Architecture Note (Post-Executive Review)

> **All scrapers in this audit are being migrated to the new Watchdog + Scraper framework.**
> The new architecture uses a standardized `payload/base.py` interface. Each developer must
> repackage their scraping logic as a `ScraperPayload` subclass that implements `.run() -> list[dict]`.
> The framework handles scheduling (UTC sync), crash recovery (watchdog), local backup (SQLite),
> cloud upload (GCP + 3x retry), and rate limiting (hardcoded 5.0–7.0s).

---

## Developer 1: Mohannad Zahra

### 1. Developer Information
- **Assigned Developer:** Mohannad Zahra
- **Current Status:** Framework architect — building the shared infrastructure

### 2. Target Scope
- **Target Retailer:** Framework (all retailers via payload interface)
- **Broad Category:** N/A (framework, not a specific scraper)
- **Role:** Building watchdog.py, scraper.py, engine/*, database/*, and payload/base.py

### 3. Framework Components Built (This Session)
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
| `scraper_deployment/` | ✅ Complete | (Portable exe build) |

---

## Developer 2: Abdelrhman Wael

### 1. Developer Information
- **Assigned Developer:** Abdelrhman Wael
- **Current Status:** ✅ Migrated to Framework (Pagination fixed & Bronze schema compliant)

### 2. Target Scope
- **Target Retailer:** 2B Egypt (2b.com.eg)
- **Broad Category:** Electronics & Hardware (Mobiles, Laptops, Gaming, Smart Home, Appliances)
- **Specific Items Targeted:** Full inventory across 17 mapped categories (PC Components, TVs, etc.)
- **Volume:** ~3,090 unique items per full scrape cycle.

### 3. Data Extraction Schema
- [X] Scrape Timestamp
- [X] Product Title (Raw)
- [X] Current Price
- [X] Discounts label (Calculated as `discount_pct`)
- [X] Original Price (if discounted)
- [X] Stock Availability Status
- [X] Product URL
- [X] Category
- [X] Sub-category
- **Extra Fields:** Brand, Numeric Price, Deal Status (`is_deal`), Media URLs, Regex-Extracted Specs (CPU, RAM, GPU, Storage, Resolution, OS), Dynamic Table Specs (`spec_`-prefixed).

### 4. Technical Stack & Health
- **Libraries Used:** Playwright (`async_playwright`), Pandas, Asyncio, Re (Regex), Python Logging.
- **Anti-Bot Strategy:** Randomized User-Agents; randomized polite delays (1.2s–3.5s); blocking heavy media payloads; `safe_goto` retry mechanism.
- **Execution Time:** ~1–2 hours for a full cycle.
- **Cycle Time:** N/A (Currently manual/one-off).
- **Known Issues:** High dependency on site leniency for deep-tab scraping; vulnerable to Magento layout changes.

### 5. Migration Notes
- **✅ Rate limit updated** (strictly tied to 5.0–7.0s base class logic)
- **✅ Implemented** `ScraperPayload.run()` interface
- **✅ Pagination fixed** (rewritten using AJAX click interaction and `.loading-mask` detection)

---

## Developer 3: Mohammed Hessen

### 1. Developer Information
- **Assigned Developer:** Mohammed Hessen
- **Current Status:** Not production-ready — uses manual browser extension

### 2. Target Scope
- **Target Retailer:** Noon Egypt, Jumia
- **Broad Category:** Laptops and accessories
- **Specific Items Targeted:** Lenovo laptops only
- **Volume:** All items on the page

### 3. Data Extraction Schema
- [X] Scrape Timestamp (added manually)
- [X] Product Title (Raw)
- [X] Current Price
- [X] Product URL
- [X] Avg rating
- [X] No. of rates
- [X] E-commerce platform
- [ ] Discounts label
- [ ] Original Price (if discounted)
- [ ] Stock Availability Status

### 4. Technical Stack & Health
- **Libraries Used:** Web browser extension (not Python-based)
- **Anti-Bot Strategy:** Manual — no automation
- **Execution Time:** 1 page avg 1–2 minutes
- **Cycle Time:** Every 12 hours (manual)
- **Known Issues:** Price column scraping fails on certain pages

### 5. Migration Notes
- **❌ Must be completely rewritten** as a Python-based `ScraperPayload`
- Browser extension approach is incompatible with the `.exe` framework
- Noon/Jumia may require enterprise proxy APIs (commercial scrapers)
- Scope question: "Lenovo laptops only" — needs broadening per project spec

---

## Developer 4: Adel Morad

### 1. Developer Information
- **Assigned Developer:** Adel Morad
- **Current Status:** Functional (882 items across 5 categories)

### 2. Target Scope
- **Target Retailer:** Dream2000 (Egypt)
- **Broad Category:** Consumer Electronics & Gaming
- **Specific Items Targeted:** Laptops, Mobile Phones, Audio Accessories, TVs, PlayStation Consoles/Games
- **Volume:** 882 unique items per cycle

### 3. Data Extraction Schema
- [X] Scrape Timestamp
- [X] Product Title (Raw)
- [X] Current Price
- [ ] Discounts label
- [X] Original Price (if discounted)
- [X] Stock Availability Status
- [X] Product URL
- **Extra Fields:** Category Name and details, Image URL

### 4. Technical Stack & Health
- **Libraries Used:** `requests`, `BeautifulSoup4`, `csv`, `time`, `os`
- **Anti-Bot Strategy:** Custom `User-Agent` headers, `Accept-Language` headers, 2-second `time.sleep()` delay
- **Execution Time:** ~20–30 seconds per category
- **Cycle Time:** Manual execution
- **Known Issues:** Previously had 404 errors due to URL parameter syntax (resolved)

### 5. Migration Notes
- **⚠️ Rate limit must be updated to 5.0–7.0s** (currently 2s)
- `requests`/BS4 approach is clean and compatible with the framework
- Should be straightforward to wrap in `ScraperPayload.run()` interface
- Recommend adding Discounts label extraction

---

## Developer 5: Mohammed Rasheek

### 1. Developer Information
- **Assigned Developer:** Mohammed Rasheek
- **Current Status:** Functional (with pagination issues)

### 2. Target Scope
- **Target Retailer:** Sigma Computer
- **Broad Category:** Laptops
- **Specific Items Targeted:** Dell Laptops
- **Volume:** ~50 items

### 3. Data Extraction Schema
- [ ] Scrape Timestamp
- [X] Product Title (Raw)
- [X] Current Price
- [ ] Discounts label
- [X] Original Price (if discounted)
- [X] Stock Availability Status
- [X] Product URL

### 4. Technical Stack & Health
- **Libraries Used:** BeautifulSoup
- **Anti-Bot Strategy:** Randomized `time.sleep()`
- **Execution Time:** Under 10 minutes
- **Cycle Time:** 12 hours (naive sleep)
- **Known Issues:** Pagination failing

### 5. Migration Notes
- **❌ Missing `scrape_timestamp`** — must be added (mandatory Bronze field)
- **⚠️ Pagination must be fixed** before migration
- Rate limit needs update to 5.0–7.0s
- Scope question: "Dell Laptops only" — needs broadening per project spec
- Naive 12-hour sleep will be replaced by UTC delta calculation

---

*End of Audit*
