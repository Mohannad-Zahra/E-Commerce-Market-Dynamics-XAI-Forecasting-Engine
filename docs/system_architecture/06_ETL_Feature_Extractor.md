# ETL Pipeline — Feature Extraction Engine

**Module:** `ETL/Data Pipiline/features.py`  
**Class:** `FeatureExtractor`  
**Last Updated:** 2026-05-10

---

## Overview

The `FeatureExtractor` is the core transformation engine of the ETL pipeline. It receives raw scraped product records (as dicts or DataFrames) and produces a structured, enriched output row suitable for downstream ML forecasting.

It handles **all product categories** sold across the monitored e-commerce retailers — not just laptops.

---

## Initialization

On startup, the extractor loads two reference files from the project root:

| File | Purpose |
|---|---|
| `gaming_keywords.json` | Brand-to-series mapping for gaming laptop detection |
| `release_dates_dictionary_v4.json` | Lookup table of ~1,770 product titles → global release dates |

If either file is missing, a safe fallback is used.

---

## Product Categorization

Categorization uses a **strict priority chain** — the first matching rule wins. All matches use **word-boundary regex** to prevent false positives (e.g. `flow` matching `flowing`, `vivo` matching `vivobook`).

| Priority | Category | Sub-Category | Trigger Keywords/Logic |
|---|---|---|---|
| 1 | Accessories | Audio | buds, earbuds, airpods, headphone, tws, earphone, headset, soundcore; or speaker+bluetooth |
| 2 | Electronics | Laptops | Gaming series keyword match (word-boundary) via `gaming_keywords.json` |
| 3 | Electronics | Laptops | laptop, macbook, notebook, ideapad, thinkpad, aspire, zenbook, vivobook, envy, pavilion |
| 4 | Phone | Smartphones | phone, iphone, galaxy, redmi, poco, smartphone, realme, spark; + word-boundary brand match; + brand+5G/LTE pattern |
| 5 | Tablet | Tablets | ipad, tablet, tab, matepad, mediapad, lenovo m7/m9/m10/m11 |
| 6 | Accessories | Wearables | watch, smartwatch, fitbit; or band+fitness keywords |
| 7 | Accessories | Power | charger, power bank; cable+usb; adapter+power |
| 8 | Accessories | Peripherals | mouse, keyboard, monitor, webcam, microphone |
| 9 | Gaming | Consoles | playstation, xbox, nintendo, console |
| 10 | PC Components | Desktop GPU | geforce, xfx, asrock, galax; or rtx/gtx/rx+gddr without laptop keywords |
| 11 | Networking | Networking | router, modem, access point, ethernet |
| 12 | PC Components | Storage | flash drive, usb drive, portable ssd, sata+ssd/hdd; nvme+ssd; m.2+gb; 3d tlc/nand; read-write+gb |
| 13 | PC Components | Cooling | cooler, heatsink, thermal paste, cpu fan |
| 14 | PC Components | Case | mid-tower, e-atx, itx case, pc case |
| 15 | PC Components | Components | ryzen, intel core, ddr4/ddr5, motherboard, corsair, adata, addlink, crucial |
| 16 | Unknown | Unknown | No rule matched |

### Gaming Keywords Dictionary (`gaming_keywords.json`)

The gaming series keywords are loaded from a JSON file and compiled into a **word-boundary regex** at startup. This prevents substring collisions (e.g. `flow` ≠ `flowing`, `blade` ≠ `bladebook`).

| Brand | Series |
|---|---|
| Acer | nitro, predator, helios, triton |
| ASUS | rog, strix, zephyrus, tuf, scar, flow |
| Dell | alienware, g15, g16 |
| HP | omen, victus, pavilion gaming |
| Lenovo | legion, loq, ideapad gaming |
| MSI | katana, cyborg, stealth, raider, titan, pulse, crosshair, sword, bravo, vector, alpha, delta |
| Gigabyte | aorus, aero |
| Razer | blade |
| General | gaming |

---

## Hardware Extraction

| Field | Electronics (Laptops) | Phone | Tablet | Other |
|---|---|---|---|---|
| `cpu` | ✅ Regex + fallback | ❌ null | ❌ null | ❌ null |
| `ram_gb` | ✅ | ✅ | ✅ | ❌ null |
| `storage_gb` | ✅ | ✅ | ✅ | ❌ null |
| `gpu` | ✅ | ❌ null | ❌ null | ❌ null |
| `is_gaming` | ✅ 0 or 1 | `0` | `0` | `0` |

---

## Output Schema

Each row returned by `transform_row()`:

```python
{
    "scrape_timestamp":       str | None,
    "retailer_id":            str | None,
    "raw_title":              str,
    "raw_current_price":      float | None,
    "raw_original_price":     float | None,
    "product_url":            str | None,
    "category":               str,           # e.g. Electronics, Phone, Tablet
    "sub_category":           str,           # e.g. Laptops, Smartphones
    "brand":                  str,           # lowercased brand name or 'unknown'
    "cpu":                    str | None,
    "ram_gb":                 int | None,
    "storage_gb":             int | None,
    "gpu":                    str | None,
    "is_gaming":              int,           # 0 or 1
    "global_release_date_str": str | None,  # e.g. "2024-09"
}
```

---

## Known Limitations

- Release date lookup uses **exact title matching** against `release_dates_dictionary_v4.json`. Scraped titles with typos or retailer-added suffixes will miss the lookup.
- RAM extraction uses a greedy regex (`\d{1,3} GB`). Titles that list multiple RAM sizes (e.g. upgrade options) will match the first occurrence only.
- Storage extraction picks the first 3–4 digit GB/TB value in the title. USB drive capacities (e.g. 64GB) may sometimes be picked up as storage for accessories if not caught by earlier rules.
