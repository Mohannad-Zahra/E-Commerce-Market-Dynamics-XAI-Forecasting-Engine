# Autonomous Electronics Recommendation System — Documentation

---

# DOCUMENT 1: Technical Documentation

---

## 1. System Overview

The Autonomous Electronics Recommendation System is a two-layer daily batch pipeline that identifies optimal laptop purchase opportunities from live market data. It executes automatically at 00:00 UTC each day, applying ML-driven scoring, supervised classification, explainability analysis, and LLM-generated summaries, culminating in persisted database records and email alerts dispatched to opted-in subscribers.

The system targets the Egyptian electronics market and operates on EGP-denominated pricing data scraped from e-commerce platforms.

---

## 2. Two-Layer Architecture

```
┌──────────────────────────────────────────────────────────┐
│  LAYER 1 — ML Pipeline                                   │
│  ranking_engine.py → state_detector.py → shap_engine.py  │
│  Orchestrated by: recommendation_pipeline.py             │
│  Output: recommendations.json                            │
└─────────────────────────┬────────────────────────────────┘
                          │  recommendations.json
┌─────────────────────────▼────────────────────────────────┐
│  LAYER 2 — System Pipeline                               │
│  database.py + llm_service.py + email_service.py         │
│  Orchestrated by: main_pipeline.py                       │
│  Output: laptops_data.db  +  Email Alerts                │
└──────────────────────────────────────────────────────────┘
```

The two layers are intentionally decoupled. Layer 1 produces a stable JSON contract. Layer 2 consumes it independently, enabling either layer to be swapped or upgraded without breaking the other.

---

## 3. File / Module Breakdown

### Layer 1 — ML Pipeline

| File | Responsibility |
|---|---|
| `ranking_engine.py` | Loads and merges both source CSVs; computes the vectorised R_score for all products; returns a ranked DataFrame |
| `state_detector.py` | Defines feature columns; generates heuristic training labels; trains a `StandardScaler + SVC(rbf)` pipeline; predicts state and confidence per candidate |
| `shap_engine.py` | Wraps SHAP `KernelExplainer` around the fitted SVM; extracts per-feature SHAP values for the target class; returns sorted driver dictionaries |
| `recommendation_pipeline.py` | Orchestrates Layers 1–3; filters for preferred classification; writes `recommendations.json` |

### Layer 2 — System Pipeline

| File | Responsibility |
|---|---|
| `database.py` | SQLite schema management; `init_db`, `insert_laptop`, `save_recommendation`, `add_subscriber`, `get_laptop_subscribers` |
| `llm_service.py` | Builds a structured prompt; calls Groq API (llama-3.3-70b-versatile); returns a 3–5 sentence plain-English explanation with retry and fallback |
| `email_service.py` | Builds an HTML email template per subscriber; dispatches via SendGrid v3 API |
| `main_pipeline.py` | Top-level orchestrator; runs all five pipeline steps; contains the daily UTC scheduler |

### Data Directory

| File | Description |
|---|---|
| `data/Dataset_Pipeline_Processed.csv` | Price history and product metadata from the scraping layer |
| `data/ECom_Forecast_XAI_data.csv` | Stability scores and 14-day price forecasts from the ML inference engine |
| `recommendations.json` | Layer 1 output / Layer 2 input (stable JSON contract) |
| `laptops_data.db` | SQLite database — all persistent state |

---

## 4. Data Flow Pipeline

```
CSVs (scraper + forecaster)
        │
        ▼
 ranking_engine.load_data()
   → Merge on [product_id, scrape_timestamp]
   → Derive: current_price, forecasted_price, volatility_score, months_since_release
        │
        ▼
 calculate_r_score()          [NumPy vectorised]
   → R_score per product
   → Sort descending → Top 5 candidates
        │
        ▼
 state_detector.train_state_detector()
   → Heuristic labels on full dataset
   → Fit StandardScaler + SVC(rbf, probability=True)
        │
        ▼
 predict_states(top_5)
   → state_classification, confidence
        │
        ▼
 shap_engine.compute_shap_drivers()
   → KernelExplainer on SVM
   → {feature: shap_value} sorted by |value| desc
        │
        ▼
 recommendations.json   [strict JSON contract]
        │
        ▼
 main_pipeline.run_daily_pipeline()
   ├─ database.insert_laptop()         → electronics_history
   ├─ llm_service.generate_explanation() → plain-English string
   ├─ database.save_recommendation()   → daily_recommendations
   └─ email_service.dispatch_laptop_alerts() → SendGrid POST
```

---

## 5. Database Schema

### `electronics_history`
Stores raw ingested candidate records on every pipeline run.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `model_id` | TEXT | Product URL / unique identifier |
| `model` | TEXT | Human-readable model label |
| `current_price` | REAL | Live price at scrape time (EGP) |
| `price_14d_avg` | REAL | 14-day rolling average price (EGP) |
| `forecasted_price` | REAL | LightGBM/SARIMAX 14-day forecast (EGP) |
| `r_score` | REAL | Computed R_score value |
| `classification` | TEXT | SVM state label |
| `confidence` | TEXT | SVM prediction probability (%) |
| `shap_drivers` | TEXT | JSON-encoded SHAP feature map |
| `ingested_at` | TIMESTAMP | Row insertion time (UTC) |

### `daily_recommendations`
Stores processed recommendations with LLM explanations.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `model_id` | TEXT | Product identifier |
| `model` | TEXT | Model label |
| `r_score` | REAL | R_score value |
| `classification` | TEXT | Market state classification |
| `confidence` | TEXT | Classifier confidence |
| `llm_explanation` | TEXT | Groq-generated explanation string |
| `recommended_at` | TIMESTAMP | Record insertion time (UTC) |

### `subscribers`
Manages email alert opt-ins.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `email` | TEXT UNIQUE | Subscriber email address |
| `name` | TEXT | Optional display name |
| `category` | TEXT | Alert category (default: `laptop`) |
| `active` | INTEGER | 1 = opted in, 0 = unsubscribed |
| `created_at` | TIMESTAMP | Registration time |

---

## 6. ML Components

### 6.1 R_score Formula

$$R_{score} = \alpha_L \cdot \frac{\hat{P}_{t+14} - P_t}{P_t} + \beta_L \cdot (100 - V) + \gamma_L \cdot \frac{\mu_{14d} - P_t}{\mu_{14d}} - \delta_L \cdot M_{age}$$

| Term | Parameter | Default | Purpose |
|---|---|---|---|
| Price Momentum | α_L | 20.0 | Rewards products with rising 14-day forecasts |
| Stability Yield | β_L | 1.0 | Rewards low volatility; penalises unstable prices |
| Discount Depth | γ_L | 1.0 | Rewards current price below 14-day average |
| Obsolescence Penalty | δ_L | 0.5 | Deducts for product age (months since release) |

All four terms are computed in a single NumPy vectorised pass over the full product array.

### 6.2 SVM State Detector

- **Model:** `sklearn.svm.SVC` with RBF kernel (`C=1.0`, `gamma='scale'`, `probability=True`)
- **Pipeline:** `StandardScaler → SVC`
- **Features:** `current_price`, `forecasted_price`, `volatility_score`, `price_14d_avg`, `months_since_release`
- **Labels (heuristic):**
  - `Deflating Arbitrage` — r_score > 65 AND volatility < 20
  - `Hyper-Inflated` — current_price > price_14d_avg × 1.2
  - `Neutral` — all other cases
- **Output per candidate:** predicted class string + probability as percentage string

### 6.3 SHAP Explainability

- **Explainer:** `shap.KernelExplainer` — model-agnostic, compatible with SVM
- **Background:** random sample of 100 rows from the full latest-snapshot dataset (scaled)
- **Target class:** `Deflating Arbitrage`
- **Output:** per-feature SHAP values sorted by absolute magnitude, returned as a Python dict

---

## 7. LLM Explanation Module (`llm_service.py`)

- **Provider:** Groq API (`https://api.groq.com/openai/v1/chat/completions`)
- **Model:** `llama-3.3-70b-versatile`
- **Temperature:** 0.2 (near-deterministic output)
- **Max tokens:** 200

The module constructs a structured prompt with pricing data, classification, and the top-3 SHAP drivers (translated to plain feature names). The system prompt prohibits ML jargon and constrains output to 3–5 sentences.

**Reliability:**
- 2 retries with exponential backoff (1 s, 2 s)
- Timeout: 12 seconds per request
- Fallback string returned on all failure paths — the pipeline never blocks on LLM failure

---

## 8. Email Notification System (`email_service.py`)

- **Provider:** SendGrid v3 REST API (`POST /v3/mail/send`)
- **Authentication:** Bearer token via `SENDGRID_API_KEY` environment variable
- **Content type:** `text/html`
- **Template:** Per-subscriber personalised HTML with one card per recommendation, styled inline for email client compatibility
- **Subscriber resolution:** queried from `subscribers` table filtered by `category = 'laptop' AND active = 1`
- **Returns:** `{sent: int, failed: int}` — pipeline continues regardless of email outcome

---

## 9. Execution Flow (Step-by-Step)

```
python recommendation_pipeline.py     ← Run Layer 1 (ML)
python main_pipeline.py               ← Run Layer 2 (System)
python main_pipeline.py --loop        ← Run Layer 2 on 00:00 UTC daily schedule
```

**Layer 1 steps:**
1. Load and merge both CSVs on `[product_id, scrape_timestamp]`
2. Derive feature columns; keep latest snapshot per product
3. Compute R_score (NumPy vectorised); rank descending
4. Train SVM on full dataset; classify top-5 candidates
5. Run SHAP KernelExplainer on classified candidates
6. Filter for `Deflating Arbitrage`; write `recommendations.json`

**Layer 2 steps:**
1. `init_db()` — ensure all three tables exist
2. Load `recommendations.json`; validate each candidate record
3. `insert_laptop()` — persist raw record to `electronics_history`
4. `generate_explanation()` — call Groq API; receive plain-English string
5. `save_recommendation()` — persist to `daily_recommendations`
6. `get_laptop_subscribers()` — fetch opted-in users from `subscribers`
7. `dispatch_laptop_alerts()` — POST HTML email per subscriber via SendGrid

---

## 10. Output JSON Contract

```json
{
  "candidates": [
    {
      "model_id": "https://shop.example.com/product-url",
      "model":    "https://shop.example.com/product-url",
      "current_price":    22082.15,
      "price_14d_avg":    24537.27,
      "forecasted_price": 22082.15,
      "r_score":          96.2519,
      "classification":   "Deflating Arbitrage",
      "confidence":       "49.86%",
      "shap_drivers": {
        "months_since_release": -0.3205,
        "volatility_score":     -0.0353,
        "price_14d_avg":         0.0109,
        "current_price":        -0.0032,
        "forecasted_price":     -0.0032
      }
    }
  ]
}
```

All values are native Python types (str, float). No pandas objects. Schema is stable and version-safe.

---

## 11. Key Features

| Feature | Detail |
|---|---|
| Fully autonomous | Single command runs all 5 pipeline steps without human input |
| Decoupled layers | JSON contract separates ML pipeline from system pipeline |
| Graceful failure | LLM fallback, email skip-on-empty-subscribers, DB rollback on error |
| Vectorised scoring | R_score computed in a single NumPy pass over all products |
| Daily scheduler | Built-in UTC midnight trigger — no external cron dependency |
| Explainability | Per-candidate SHAP drivers quantify each feature's contribution |
| No framework lock-in | Pure Python — `sqlite3`, `requests`, `scikit-learn`, `shap` only |

---
---

# DOCUMENT 2: Human-Readable Explanation

---

## What Does This System Do?

This system automatically finds the best laptop deals every day and sends them directly to your inbox — with a written explanation of why each deal is worth buying right now.

It works entirely on its own. No human needs to check prices, analyse data, or write any summaries. It all happens automatically at midnight, every night.

---

## Why Is It Useful?

Laptop prices in fast-moving markets change constantly. A great deal today might be gone tomorrow. Missing the right moment means paying significantly more for the same product.

This system watches thousands of products simultaneously, calculates which ones represent genuine value right now, and explains the reasoning in plain language — so buyers can make confident, informed decisions without needing to understand the underlying numbers.

---

## How It Works — Step by Step

**Step 1 — Collect the Data**
The system pulls in current prices for every laptop it tracks, along with each product's average price over the past 14 days and a prediction of where the price is headed in the next two weeks.

**Step 2 — Score Every Laptop**
Each laptop receives a score based on four things:
- Is the price expected to rise? (Buy now before it does.)
- Has the price been stable recently? (Stable prices mean lower risk.)
- Is today's price below the recent average? (Immediate discount opportunity.)
- How old is the product? (Newer products score better to avoid outdated stock.)

**Step 3 — Identify the Best Opportunities**
The top five laptops by score are then run through a second check — a pattern-recognition system — which confirms whether they genuinely represent a "Deflating Arbitrage" opportunity: a product whose price has temporarily dipped below its normal market value, making it a smart buy right now.

**Step 4 — Write the Explanation**
For each confirmed deal, the system sends the relevant data to an AI assistant (powered by a large language model). The AI writes a short, plain-English summary — three to five sentences — explaining why this specific laptop is worth buying today, in language anyone can understand.

**Step 5 — Save and Send**
All the deals and their explanations are saved to a database for record-keeping. Then the system sends a formatted email to everyone who has signed up for laptop deal alerts. Each email shows the product, the price, and the AI-written explanation.

---

## What the Email Looks Like

Each alert includes:
- The product name and a link to buy it
- The current price versus the recent average price
- A confidence indicator (how certain the system is about this deal)
- A plain-English explanation written by AI — no numbers, no jargon

---

## One-Line Summary

> **Every night at midnight, this system automatically scans thousands of laptop listings, identifies the best deals, writes a plain-English explanation for each one, and emails them directly to subscribers — with zero human involvement.**
