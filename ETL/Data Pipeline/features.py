import os
import re
import json
import pandas as pd
import numpy as np
from pathlib import Path

# GPU tier map (24 unique strings -> numeric tier 1-10)
GPU_TIER_MAP: dict[str, int] = {
    "GTX 1650": 2, "GTX 1660": 3, "RTX 2050": 3, "RTX 3050": 4, "RTX3050": 4,
    "RTX 3070": 6, "RTX 4050": 5, "RTX4050": 5, "RTX 4060": 6, "RTX 4070": 7,
    "RTX4080": 8, "RTX 5050": 5, "RTX 5060": 7, "RTX 5070": 8, "RTX5070": 8,
    "RTX 5080": 9, "RTX 5090": 10, "RX 6500": 3, "RX 6650": 4, "RX 6900": 7,
    "RX 7800": 7, "RX 7900": 8, "RX 9060": 6, "RX 9070": 7,
}

class FeatureExtractor:
    """
    Production-grade feature extraction module for all product categories.
    Implements the strict priority chain and hardware extraction logic.
    """
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent
        self.gaming_keywords_path = self.base_dir / "gaming_keywords.json"
        self.release_dates_path = self.base_dir / "release_dates_dictionary_v4.json"
        
        # Load gaming keywords
        self.gaming_keywords = {}
        if self.gaming_keywords_path.exists():
            with open(self.gaming_keywords_path, 'r', encoding='utf-8') as f:
                self.gaming_keywords = json.load(f)
        
        # Compile gaming regex
        all_gaming_terms = []
        for terms in self.gaming_keywords.values():
            all_gaming_terms.extend(terms)
        self.gaming_re = re.compile(r'\b(' + '|'.join(map(re.escape, all_gaming_terms)) + r')\b', re.I)
        
        # Load release dates
        self.release_dates = {}
        if self.release_dates_path.exists():
            with open(self.release_dates_path, 'r', encoding='utf-8') as f:
                self.release_dates = json.load(f)

    def extract_brand(self, title: str) -> str:
        t = title.lower()
        brands = ["apple", "samsung", "lenovo", "asus", "acer", "dell", "hp", "msi", 
                  "xiaomi", "oppo", "vivo", "realme", "infinix", "honor", "nokia", 
                  "huawei", "sony", "lg", "microsoft", "google"]
        for b in brands:
            if re.search(r'\b' + re.escape(b) + r'\b', t):
                return b.title()
        return "Unknown"

    def transform_row(self, row: dict) -> dict:
        """
        Transforms a raw scraped row into an enriched ETLOutput dictionary.
        """
        title = row.get("raw_title", "")
        t = title.lower()
        
        res = {
            "scrape_timestamp": row.get("scrape_timestamp"),
            "retailer_id": row.get("retailer_id"),
            "raw_title": title,
            "raw_current_price": row.get("raw_current_price"),
            "raw_original_price": row.get("raw_original_price"),
            "product_url": row.get("product_url"),
            "category": "Unknown",
            "sub_category": "Unknown",
            "brand": self.extract_brand(title),
            "cpu": None,
            "ram_gb": None,
            "storage_gb": None,
            "gpu": None,
            "is_gaming": 0,
            "global_release_date_str": self.release_dates.get(title)
        }

        # 1. Categorization Chain
        # Accessories Audio
        if re.search(r'\b(buds|earbuds|airpods|headphone|tws|earphone|headset|soundcore|speaker)\b', t):
            res["category"] = "Accessories"
            res["sub_category"] = "Audio"
        # Laptops (Gaming)
        elif self.gaming_re.search(t):
            res["category"] = "Electronics"
            res["sub_category"] = "Laptops"
            res["is_gaming"] = 1
        # Laptops (General)
        elif re.search(r'\b(laptop|macbook|notebook|ideapad|thinkpad|aspire|zenbook|vivobook|envy|pavilion)\b', t):
            res["category"] = "Electronics"
            res["sub_category"] = "Laptops"
        # Phone
        elif re.search(r'\b(phone|iphone|galaxy|redmi|poco|smartphone|realme|spark)\b', t):
            res["category"] = "Phone"
            res["sub_category"] = "Smartphones"
        # Tablet
        elif re.search(r'\b(ipad|tablet|tab|matepad|mediapad)\b', t):
            res["category"] = "Tablet"
            res["sub_category"] = "Tablets"
        
        # 2. Hardware Extraction & Tiering
        res["cpu_tier"] = 0
        res["gpu_tier"] = 0
        res["ram_gb_ordinal"] = 0
        res["storage_ordinal"] = 0

        if res["sub_category"] == "Laptops":
            # RAM
            ram_match = re.search(r'(\d{1,3})\s*GB\s*RAM', title, re.I)
            if ram_match:
                val = int(ram_match.group(1))
                res["ram_gb"] = val
                # Simple ordinal: 1: <4, 2: 4-8, 3: 8-16, 4: 16-32, 5: 32+
                if val < 4: res["ram_gb_ordinal"] = 1
                elif val <= 8: res["ram_gb_ordinal"] = 2
                elif val <= 16: res["ram_gb_ordinal"] = 3
                elif val <= 32: res["ram_gb_ordinal"] = 4
                else: res["ram_gb_ordinal"] = 5
            
            # Storage
            storage_match = re.search(r'(\d{1,4})\s*(GB|TB)\s*(SSD|HDD)', title, re.I)
            if storage_match:
                val = int(storage_match.group(1))
                unit = storage_match.group(2).upper()
                if unit == "TB":
                    val *= 1024
                res["storage_gb"] = val
                # Simple ordinal: 1: <128, 2: 128-256, 3: 256-512, 4: 512-1024, 5: 1024+
                if val < 128: res["storage_ordinal"] = 1
                elif val <= 256: res["storage_ordinal"] = 2
                elif val <= 512: res["storage_ordinal"] = 3
                elif val <= 1024: res["storage_ordinal"] = 4
                else: res["storage_ordinal"] = 5
                
            # CPU (Heuristic Tiering)
            cpu_match = re.search(r'\b(Core\s*i([3579])|Ryzen\s*([3579])|Ultra\s*([3579])|M([123]))\b', title, re.I)
            if cpu_match:
                res["cpu"] = cpu_match.group(1)
                # Tier based on the number
                digit = cpu_match.group(2) or cpu_match.group(3) or cpu_match.group(4) or cpu_match.group(5)
                if digit:
                    res["cpu_tier"] = int(digit)
            
            # GPU Tiering
            for gpu_name, tier in GPU_TIER_MAP.items():
                if gpu_name.lower() in t:
                    res["gpu_tier"] = tier
                    res["gpu"] = gpu_name
                    break

        return res

def run_etl_pipeline(batch_id: str = None):
    # This remains for backward compatibility or direct script runs
    print("Running ETL pipeline...")
    # ... logic to fetch from DB and process ...
    pass
