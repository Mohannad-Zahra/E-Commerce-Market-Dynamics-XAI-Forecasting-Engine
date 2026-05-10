"""
feature_engine.py — Core ETL Feature Extraction Engine
========================================================
Database-resident feature engineering that transforms raw scraped data
into ML-ready features. Replaces the old CSV-based ETL/Data Pipeline/features.py.

Sources consolidated:
  - ETL/Data Pipeline/features.py          → GPU tiers, chipset extraction, category
  - ML_Pipeline/Stability_Scoring/phase1_2_features.py → compute_potential, price momentum

Pipeline:
  1. Category Inference       (Laptop / Phone / Tablet from URL + title)
  2. Hardware Feature Extraction  (GPU tier, RAM, storage, chipset)
  3. Compute Potential        (unified [0,1] score across all categories)
  4. Scale-Invariant Price Features (delta_p_1d, vol_30d, delta_p_7d, delta_p_14d)
  5. Brand Extraction
  6. Gaming Detection
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
# Constants & Lookup Tables
# ═══════════════════════════════════════════════════════════════════════════════

# GPU tier map: 24 unique GPU strings → numeric tier 1-10
GPU_TIER_MAP: dict[str, int] = {
    # NVIDIA GTX
    "GTX 1650": 2, "GTX 1660": 3,
    # NVIDIA RTX 20-series
    "RTX 2050": 3,
    # NVIDIA RTX 30-series
    "RTX 3050": 4, "RTX3050": 4, "RTX 3070": 6,
    # NVIDIA RTX 40-series
    "RTX 4050": 5, "RTX4050": 5, "RTX 4060": 6, "RTX 4070": 7, "RTX4080": 8,
    # NVIDIA RTX 50-series
    "RTX 5050": 5, "RTX 5060": 7, "RTX 5070": 8, "RTX5070": 8,
    "RTX 5080": 9, "RTX 5090": 10,
    # AMD RX RDNA2
    "RX 6500": 3, "RX 6650": 4, "RX 6900": 7,
    # AMD RX RDNA3
    "RX 7800": 7, "RX 7900": 8,
    # AMD RX RDNA4
    "RX 9060": 6, "RX 9070": 7,
}

# RAM / Storage ordinal → midpoint GB
RAM_MID = {"2-4": 3, "4-8": 6, "8-16": 12, "16-32": 24, "32+": 48}
STO_MID = {"0-64": 32, "64-128": 96, "128-256": 192, "256-512": 384}

# MinMax bounds (from known bins)
RAM_MIN, RAM_MAX = 3.0, 48.0
STO_MIN, STO_MAX = 32.0, 384.0

# Laptop detection keywords for URL matching
LAPTOP_KW = (
    r"laptop|macbook|thinkpad|aspire|vivobook|inspiron|pavilion|spectre|envy|"
    r"zenbook|gram|surface-laptop|swift|spin|chromebook|ideapad|probook|"
    r"elitebook|latitude|xps|omen|predator|nitro|rog-"
)

# Extended title-based category keywords (from backend/main.py)
MOBILE_KW = [
    "iphone", "samsung galaxy", "redmi", "xiaomi", "oppo", "vivo", "realme",
    "infinix", "honor", "hmd", "motorola", "moto ", "nokia", "google pixel",
    "tecno", "huawei", "zte", "itel", "pova", "spark", "camon", "phantom",
    "zero 30", "zero ultra", "y90", "y70",
]

TABLET_KW = [
    "ipad", "tablet", "tab ", "tab s", "tab a", "idea tab",
    "matepad", "t-tab", "pad 6", "pad x",
]

LAPTOP_TITLE_KW = [
    "laptop", "notebook", "aspire", "vivobook", "ideapad", "macbook", "zenbook",
    "pavilion", "legion", "loq", "nitro", "rog ", "strix", "victus", "predator",
    "alienware", "omen", "tuf ", "katana", "sword", "vector", "stealth", "thin ",
    "cyborg", "bravo", "thinkpad", "latitude", "vostro", "xps", "probook",
    "elitebook", "surface", "proart", "raider", "prestige", "modern 14",
    "modern 15", "expertbook",
]

# Gaming keywords (for is_gaming flag)
GAMING_KW = [
    "gaming", "rog", "strix", "predator", "nitro", "legion", "omen", "victus",
    "tuf", "katana", "raider", "loq", "alienware",
]

# Brand detection keywords
BRAND_KW = [
    "apple", "samsung", "lenovo", "asus", "acer", "dell", "hp", "msi",
    "xiaomi", "oppo", "vivo", "realme", "infinix", "huawei", "honor",
    "tecno", "itel", "nokia", "motorola", "google", "sony",
    "kingston", "pny", "antec", "seagate", "western digital", "redragon",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Feature Extraction Functions
# ═══════════════════════════════════════════════════════════════════════════════

def extract_chipset_score(title: str) -> Optional[float]:
    """
    Extract a normalised [0, 1] chipset compute score from raw_title.
    Returns None if no known chipset pattern is found.
    """
    if not isinstance(title, str):
        return None
    t = title.lower()
    # High-end
    if re.search(r"snapdragon\s*8\s*(gen\s*[234]|elite)", t): return 0.95
    if re.search(r"snapdragon\s*8\s*gen", t):                  return 0.88
    if re.search(r"a1[678]\s*(bionic|pro|chip)?", t):          return 0.93
    if re.search(r"a15\s*bionic", t):                           return 0.80
    if re.search(r"dimensity\s*9[0-9]{3}", t):                  return 0.82
    # Mid-range
    if re.search(r"snapdragon\s*(7[0-9]{2}|695|690)", t):      return 0.55
    if re.search(r"dimensity\s*[78][0-9]{2}", t):               return 0.50
    if re.search(r"a1[234]\s*(bionic)?", t):                    return 0.60
    # Low-end
    if re.search(r"snapdragon\s*(4[0-9]{2}|480)", t):          return 0.25
    if re.search(r"helio\s*[gp][0-9]+", t):                    return 0.20
    if re.search(r"dimensity\s*[0-9]{3}[^0-9]", t):            return 0.30
    return None


def extract_gpu_from_title(title: str) -> Optional[str]:
    """
    Extract GPU model string from product title.
    Returns the matching GPU key from GPU_TIER_MAP or None.
    """
    if not isinstance(title, str):
        return None
    for gpu_key in GPU_TIER_MAP:
        if gpu_key.lower() in title.lower():
            return gpu_key
    return None


def extract_ram_gb(title: str) -> Optional[float]:
    """Extract RAM size in GB from product title."""
    if not isinstance(title, str):
        return None
    match = re.search(r"(\d+)\s*GB\s*(?:RAM|DDR|memory)", title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    # Fallback: just "16GB" without RAM qualifier
    match = re.search(r"(\d+)\s*GB", title, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        if val in (2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64, 128):
            return val
    return None


def extract_storage_gb(title: str) -> Optional[float]:
    """Extract storage capacity in GB from product title."""
    if not isinstance(title, str):
        return None
    # Match TB first
    match = re.search(r"(\d+(?:\.\d+)?)\s*TB\s*(?:SSD|HDD|NVMe|storage)?", title, re.IGNORECASE)
    if match:
        return float(match.group(1)) * 1024
    # Match GB SSD/HDD/NVMe
    match = re.search(r"(\d+)\s*GB\s*(?:SSD|HDD|NVMe|storage)", title, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def infer_category(product_url: str, raw_title: str) -> str:
    """
    Infer product category from URL and title.
    Priority: URL keywords → Title keywords → Default 'Phone'.
    """
    url_lower = product_url.lower() if isinstance(product_url, str) else ""
    title_lower = raw_title.lower() if isinstance(raw_title, str) else ""

    # 1. Check URL for laptop keywords
    if re.search(LAPTOP_KW, url_lower):
        return "Laptop"

    # 2. Check title for tablets (before phones, since some tablets have phone-like names)
    if any(kw in title_lower for kw in TABLET_KW):
        return "Tablet"

    # 3. Check title for laptops
    if any(kw in title_lower for kw in LAPTOP_TITLE_KW):
        return "Laptop"

    # 4. Check title for phones
    if any(kw in title_lower for kw in MOBILE_KW):
        return "Phone"

    # 5. Default
    return "Phone"


def detect_brand(raw_title: str) -> Optional[str]:
    """Extract brand name from product title."""
    if not isinstance(raw_title, str):
        return None
    title_lower = raw_title.lower()
    for brand in BRAND_KW:
        if brand in title_lower:
            return brand.title()
    return "Unknown"


def detect_gaming(raw_title: str) -> bool:
    """Detect if a product is gaming-oriented from its title."""
    if not isinstance(raw_title, str):
        return False
    title_lower = raw_title.lower()
    return any(kw in title_lower for kw in GAMING_KW)


def compute_potential_laptop(gpu_tier_num: Optional[int]) -> float:
    """
    Compute potential for laptops: (tier - 1) / 9.
    Edge case: no GPU → tier=2 (integrated graphics).
    """
    if gpu_tier_num is not None and gpu_tier_num >= 1:
        return (gpu_tier_num - 1) / 9.0
    return (2 - 1) / 9.0  # 0.1111 — integrated graphics default


def compute_potential_phone(
    chipset_score: Optional[float],
    ram_gb: Optional[float],
    storage_gb: Optional[float],
) -> float:
    """
    Compute potential for phones.
    Priority: chipset_score (if extracted) > proxy formula (α=0.6*ram + β=0.4*storage).
    """
    if chipset_score is not None:
        return float(np.clip(chipset_score, 0.0, 1.0))

    # Proxy from RAM + storage
    ram_norm = 0.0
    if ram_gb is not None:
        ram_norm = (float(np.clip(ram_gb, RAM_MIN, RAM_MAX)) - RAM_MIN) / (RAM_MAX - RAM_MIN)

    sto_norm = 0.0
    if storage_gb is not None:
        sto_norm = (float(np.clip(storage_gb, STO_MIN, STO_MAX)) - STO_MIN) / (STO_MAX - STO_MIN)

    return float(np.clip(0.6 * ram_norm + 0.4 * sto_norm, 0.0, 1.0))


# ═══════════════════════════════════════════════════════════════════════════════
# Main ETL Pipeline Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the full ETL feature engineering pipeline to a DataFrame of raw products.

    Input DataFrame must contain:
      - product_url, raw_title, raw_current_price, raw_original_price,
        retailer_id, scrape_timestamp

    Returns a new DataFrame with all engineered features added.
    """
    if df.empty:
        return df

    result = df.copy()

    # ── 1. Category Inference ────────────────────────────────────────────────
    result["category"] = result.apply(
        lambda row: infer_category(row.get("product_url", ""), row.get("raw_title", "")),
        axis=1,
    )

    # ── 2. Brand Detection ───────────────────────────────────────────────────
    result["brand"] = result["raw_title"].apply(detect_brand)

    # ── 3. Gaming Detection ──────────────────────────────────────────────────
    result["is_gaming"] = result["raw_title"].apply(detect_gaming)

    # ── 4. GPU Extraction & Tier Mapping ─────────────────────────────────────
    result["gpu"] = result["raw_title"].apply(extract_gpu_from_title)
    result["gpu_tier_num"] = result["gpu"].map(GPU_TIER_MAP)

    # ── 5. RAM & Storage Extraction ──────────────────────────────────────────
    result["ram_gb"] = result["raw_title"].apply(extract_ram_gb)
    result["storage_gb"] = result["raw_title"].apply(extract_storage_gb)

    # ── 6. Chipset Score (phones only) ───────────────────────────────────────
    phone_mask = result["category"] == "Phone"
    result["_chipset_score"] = np.nan
    if phone_mask.any():
        result.loc[phone_mask, "_chipset_score"] = (
            result.loc[phone_mask, "raw_title"].apply(extract_chipset_score)
        )

    # ── 7. Compute Potential ─────────────────────────────────────────────────
    result["compute_potential"] = np.nan

    # Laptops
    laptop_mask = result["category"] == "Laptop"
    if laptop_mask.any():
        result.loc[laptop_mask, "compute_potential"] = (
            result.loc[laptop_mask, "gpu_tier_num"].apply(compute_potential_laptop)
        )

    # Phones & Tablets
    non_laptop_mask = ~laptop_mask
    if non_laptop_mask.any():
        result.loc[non_laptop_mask, "compute_potential"] = result.loc[non_laptop_mask].apply(
            lambda row: compute_potential_phone(
                row.get("_chipset_score"),
                row.get("ram_gb"),
                row.get("storage_gb"),
            ),
            axis=1,
        )

    result["compute_potential"] = result["compute_potential"].clip(0.0, 1.0).fillna(0.1111)

    # ── 8. Scale-Invariant Price Features ────────────────────────────────────
    # These require historical data (multiple timestamps per product).
    # For a single batch, we initialize to 0 and compute properly when
    # historical data exists.

    result = result.sort_values(["product_url", "scrape_timestamp"])

    # Daily percentage change
    if result.groupby("product_url").size().max() > 1:
        result["delta_p_1d"] = (
            result.groupby("product_url", group_keys=False)["raw_current_price"]
            .transform(lambda x: x.pct_change().fillna(0.0))
        )
    else:
        result["delta_p_1d"] = 0.0

    # 30-day rolling volatility
    if result.groupby("product_url").size().max() > 2:
        result["vol_30d"] = (
            result.groupby("product_url", group_keys=False)["delta_p_1d"]
            .transform(lambda x: x.rolling(30, min_periods=2).std().fillna(0.0))
        )
    else:
        result["vol_30d"] = 0.0

    # 7d and 14d relative momentum (need rolling avg for proper computation)
    # For a single batch, these are 0. With accumulating data they become meaningful.
    if "delta_p_7d" not in result.columns:
        result["delta_p_7d"] = 0.0
    if "delta_p_14d" not in result.columns:
        result["delta_p_14d"] = 0.0

    # ── 9. Initialize remaining feature columns ──────────────────────────────
    defaults = {
        "sub_category": None,
        "cpu": None,
        "global_release_date_str": None,
        "missing_release_date": True,
        "D_months": 0.0,
        "k": 0.0,
        "competitor_scarcity_count": 0,
        "volume_weight": 1.0,
        "official_egp_usd": None,
        "cpi_inflation": None,
        "import_lambda": None,
        "multiplier": 1.0,
        "is_major_sale_period": False,
        "sale_event_label": None,
    }
    for col, default_val in defaults.items():
        if col not in result.columns:
            result[col] = default_val

    # ── Cleanup ──────────────────────────────────────────────────────────────
    result.drop(columns=["_chipset_score"], errors="ignore", inplace=True)

    return result


def get_category_distribution(df: pd.DataFrame) -> dict:
    """Return a {category: count} dict from a processed DataFrame."""
    if df.empty or "category" not in df.columns:
        return {}
    return df["category"].value_counts().to_dict()
