"""
phase1_2_features.py — Phases 1 & 2: Feature Alignment + Scale-Invariant Engineering
======================================================================================
Input:  Dataset_Pipeline_Processed.csv
Output: features_engineered.parquet

Phase 1 — Cross-Category Feature Alignment
  - Infers Laptop/Phone category from product_id URL
  - Maps 24 GPU string values to numeric tiers 1-10
  - Computes compute_potential ∈ [0.0, 1.0] for all rows
  - Edge case: Laptops with no GPU → tier=2 (compute_potential=0.111)
  - Drops: gpu_tier, cpu_tier, ram_gb_ordinal, storage_ordinal

Phase 2 — Scale-Invariant Price Features
  - Computes price_7d_avg via 7-day rolling per product
  - Computes ΔP_7d, ΔP_14d (relative momentum)
  - Computes delta_p_1d (daily pct change) and vol_30d (30-day rolling std)
  - Drops: base_price_egp, price_14d_avg, price_7d_avg, all absolute prices
  - Retains price_final for Phase 3 OLS (dropped from training features in phase4_5)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import re
import pandas as pd
import numpy as np
from pathlib import Path

RAW_CSV = (
    r"b:/Akuma/Uni/3rd year/second/ecom Data Generated/Dataset_Pipeline_Processed.csv"
)
OUT_DIR  = Path(__file__).parent
OUT_FILE = OUT_DIR / "features_engineered.parquet"

# ── GPU tier map (24 unique strings → numeric tier 1-10) ─────────────────────
GPU_TIER_MAP: dict[str, int] = {
    # --- NVIDIA GTX ---
    "GTX 1650": 2,
    "GTX 1660": 3,
    # --- NVIDIA RTX 20-series ---
    "RTX 2050": 3,
    # --- NVIDIA RTX 30-series ---
    "RTX 3050": 4,
    "RTX3050":  4,   # space-less variant in data
    "RTX 3070": 6,
    # --- NVIDIA RTX 40-series ---
    "RTX 4050": 5,
    "RTX4050":  5,
    "RTX 4060": 6,
    "RTX 4070": 7,
    "RTX4080":  8,
    # --- NVIDIA RTX 50-series ---
    "RTX 5050": 5,
    "RTX 5060": 7,
    "RTX 5070": 8,
    "RTX5070":  8,   # space-less variant
    "RTX 5080": 9,
    "RTX 5090": 10,
    # --- AMD RX RDNA2 ---
    "RX 6500": 3,
    "RX 6650": 4,
    "RX 6900": 7,
    # --- AMD RX RDNA3 ---
    "RX 7800": 7,
    "RX 7900": 8,
    # --- AMD RX RDNA4 ---
    "RX 9060": 6,
    "RX 9070": 7,
}

# RAM / Storage ordinal → midpoint GB
RAM_MID = {"2-4": 3, "4-8": 6, "8-16": 12, "16-32": 24, "32+": 48}
STO_MID = {"0-64": 32, "64-128": 96, "128-256": 192, "256-512": 384}

# MinMax bounds (from known bins)
RAM_MIN, RAM_MAX = 3.0, 48.0
STO_MIN, STO_MAX = 32.0, 384.0

# URL keyword patterns
LAPTOP_KW = (
    r"laptop|macbook|thinkpad|aspire|vivobook|inspiron|pavilion|spectre|envy|"
    r"zenbook|gram|surface-laptop|swift|spin|chromebook|ideapad|probook|"
    r"elitebook|latitude|xps|omen|predator|nitro|rog-"
)


def extract_chipset_score(title: str) -> float | None:
    """Return a normalised [0, 1] chipset compute score from raw_title, or None."""
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


def compute_phone_proxy(ram_norm: float, sto_norm: float) -> float:
    """α=0.6, β=0.4 proxy for phones without chipset data."""
    return 0.6 * ram_norm + 0.4 * sto_norm


# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 62)
print("  PHASE 1-2: Cross-Category Alignment + Scale-Invariant Features")
print("=" * 62)

# ── 1. Load ───────────────────────────────────────────────────────────────────
print("\n[1/9] Loading CSV …")
df = pd.read_csv(RAW_CSV, low_memory=False, parse_dates=["scrape_timestamp"])
print(f"      Loaded {len(df):,} rows × {len(df.columns)} cols")

# ── 2. Infer category ─────────────────────────────────────────────────────────
print("[2/9] Inferring category from product_id URL …")
url_lower = df["product_id"].str.lower()
df["category"] = "Phone"
df.loc[url_lower.str.contains(LAPTOP_KW, na=False, regex=True), "category"] = "Laptop"
print(f"      Laptop: {(df['category']=='Laptop').sum():,}  |  "
      f"Phone/Tablet: {(df['category']=='Phone').sum():,}")

# ── 3. Map gpu_tier → numeric ─────────────────────────────────────────────────
print("[3/9] Mapping gpu_tier strings → numeric tiers (1–10) …")
df["gpu_tier_num"] = df["gpu_tier"].map(GPU_TIER_MAP)
mapped   = df["gpu_tier_num"].notna().sum()
unmapped = df["gpu_tier"].notna().sum() - mapped
print(f"      Mapped: {mapped:,}  |  Unmapped (new strings): {unmapped:,}")
if unmapped > 0:
    print("      ⚠ Unmapped strings (will fall back to edge-case):")
    print("       ", df.loc[df["gpu_tier"].notna() & df["gpu_tier_num"].isna(),
                             "gpu_tier"].unique())

# ── 4. Ordinal midpoints ──────────────────────────────────────────────────────
print("[4/9] Converting ordinals to normalised midpoints …")
df["ram_norm"] = df["ram_gb_ordinal"].map(RAM_MID).fillna(RAM_MIN)
df["sto_norm"] = df["storage_ordinal"].map(STO_MID).fillna(STO_MIN)
df["ram_norm"] = (df["ram_norm"] - RAM_MIN) / (RAM_MAX - RAM_MIN)
df["sto_norm"] = (df["sto_norm"] - STO_MIN) / (STO_MAX - STO_MIN)

# ── 5. Chipset extraction (phones only) ───────────────────────────────────────
print("[5/9] Extracting chipset identifiers from raw_title (phones) …")
phone_mask = df["category"] == "Phone"
df["chipset_score"] = np.nan
df.loc[phone_mask, "chipset_score"] = (
    df.loc[phone_mask, "raw_title"].apply(extract_chipset_score)
)
found = df.loc[phone_mask, "chipset_score"].notna().sum()
print(f"      Chipset score resolved for {found:,} / {phone_mask.sum():,} phone rows")

# ── 6. compute_potential ──────────────────────────────────────────────────────
print("[6/9] Computing compute_potential ∈ [0.0, 1.0] …")
df["compute_potential"] = np.nan
laptop_mask = df["category"] == "Laptop"

# 6a. Laptop with valid GPU tier
lap_gpu = laptop_mask & df["gpu_tier_num"].notna()
df.loc[lap_gpu, "compute_potential"] = (df.loc[lap_gpu, "gpu_tier_num"] - 1) / 9

# 6b. Laptop WITHOUT GPU (integrated graphics edge case → tier=2 fixed)
lap_no_gpu = laptop_mask & df["gpu_tier_num"].isna()
LAPTOP_NO_GPU_TIER = 2
df.loc[lap_no_gpu, "compute_potential"] = (LAPTOP_NO_GPU_TIER - 1) / 9  # = 0.1111
print(f"      Laptops with GPU:    {lap_gpu.sum():,}  → formula (tier-1)/9")
print(f"      Laptops without GPU: {lap_no_gpu.sum():,} → fixed tier=2 (cp=0.111)")

# 6c. Phone with chipset extraction
ph_chip = phone_mask & df["chipset_score"].notna()
df.loc[ph_chip, "compute_potential"] = df.loc[ph_chip, "chipset_score"]

# 6d. Phone proxy (α=0.6, β=0.4)
ph_proxy = phone_mask & df["chipset_score"].isna()
df.loc[ph_proxy, "compute_potential"] = compute_phone_proxy(
    df.loc[ph_proxy, "ram_norm"], df.loc[ph_proxy, "sto_norm"]
)
print(f"      Phones (chipset):     {ph_chip.sum():,}")
print(f"      Phones (proxy):       {ph_proxy.sum():,}")

df["compute_potential"] = df["compute_potential"].clip(0.0, 1.0)

nans = df["compute_potential"].isna().sum()
assert nans == 0, f"compute_potential has {nans} NaNs!"
print(f"      Range: [{df['compute_potential'].min():.4f}, "
      f"{df['compute_potential'].max():.4f}]  mean={df['compute_potential'].mean():.4f}")

# ── 7. Phase 2 — rolling price features ───────────────────────────────────────
print("[7/9] Computing scale-invariant price features …")
df = df.sort_values(["product_id", "scrape_timestamp"])
df = df.set_index("scrape_timestamp")

print("      → 7-day rolling avg per product …")
df["price_7d_avg"] = (
    df.groupby("product_id", group_keys=False)["price_final"]
    .transform(lambda x: x.rolling("7D", min_periods=1).mean())
)

print("      → Daily pct change per product …")
df["delta_p_1d"] = (
    df.groupby("product_id", group_keys=False)["price_final"]
    .transform(lambda x: x.pct_change().fillna(0.0))
)

print("      → 30-day rolling volatility …")
df["vol_30d"] = (
    df.groupby("product_id", group_keys=False)["delta_p_1d"]
    .transform(lambda x: x.rolling("30D", min_periods=2).std().fillna(0.0))
)

df = df.reset_index()  # restore scrape_timestamp as column

# Relative momentum
eps = 1e-8
df["delta_p_7d"]  = (df["price_final"] - df["price_7d_avg"])  / (df["price_7d_avg"]  + eps)
df["delta_p_14d"] = (df["price_final"] - df["price_14d_avg"]) / (df["price_14d_avg"] + eps)

print(f"      delta_p_7d  ∈ [{df['delta_p_7d'].min():.4f}, {df['delta_p_7d'].max():.4f}]")
print(f"      delta_p_14d ∈ [{df['delta_p_14d'].min():.4f}, {df['delta_p_14d'].max():.4f}]")
print(f"      vol_30d     ∈ [{df['vol_30d'].min():.6f}, {df['vol_30d'].max():.6f}]")

# ── 8. Drop forbidden columns ─────────────────────────────────────────────────
print("[8/9] Dropping forbidden raw columns …")
DROP = [
    "gpu_tier", "gpu_tier_num", "cpu_tier",
    "ram_gb_ordinal", "storage_ordinal",
    "ram_norm", "sto_norm", "chipset_score",
    "base_price_egp",
    "price_14d_avg",   # absolute avg — replaced by delta_p_14d
    "price_7d_avg",    # absolute avg — replaced by delta_p_7d
    # NOTE: price_final is kept → required by phase3 OLS; dropped from train in phase4
]
df.drop(columns=[c for c in DROP if c in df.columns], inplace=True)
print(f"      Retained columns ({len(df.columns)}): {list(df.columns)}")

# ── 9. Save ───────────────────────────────────────────────────────────────────
print(f"[9/9] Saving → {OUT_FILE} …")
df.to_parquet(OUT_FILE, index=False, engine="pyarrow")
print(f"      ✓ {len(df):,} rows × {len(df.columns)} cols saved.")
print("\n✓  Phase 1-2 complete.")
