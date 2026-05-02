import re
import pandas as pd


class FeatureExtractor:
    """
    Production-grade feature extraction module
    for laptop/product titles.
    """

    def __init__(self):

        # ---------------- CPU ----------------
        self.cpu_pattern = re.compile(
            r"(i[3579]-?\d{4,5}[A-Z]*|Ryzen\s?\d|Core\sUltra\s\d+)",
            re.IGNORECASE
        )

        # ---------------- RAM ----------------
        self.ram_pattern = re.compile(
            r"(\d{1,3})\s?GB\s?(RAM)?",
            re.IGNORECASE
        )

        # ---------------- STORAGE ----------------
        self.storage_pattern = re.compile(
            r"(\d{3,4})\s?(GB|TB)\s?(SSD|HDD|NVMe|M\.2)?",
            re.IGNORECASE
        )

        # ---------------- GPU ----------------
        self.gpu_pattern = re.compile(
            r"(RTX\s?\d{3,4}|GTX\s?\d{3,4}|Intel\sArc|Iris Xe|UHD|Radeon)",
            re.IGNORECASE
        )

        # ---------------- BRAND ----------------
        self.brand_pattern = re.compile(
            r"(ASUS|LENOVO|HP|DELL|ACER|APPLE|MSI)",
            re.IGNORECASE
        )

    # ======================================================
    # NORMALIZATION
    # ======================================================
    def normalize(self, text: str) -> str:
        if pd.isna(text):
            return ""

        text = str(text).lower()
        text = text.replace("–", "-").replace("—", "-")
        text = text.replace("\u00a0", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # ======================================================
    # CPU
    # ======================================================
    def extract_cpu(self, text: str):
        match = self.cpu_pattern.search(text)
        if match:
            return match.group(0)

        if "intel" in text or "ryzen" in text:
            tokens = text.split()
            for t in tokens:
                if "i5" in t or "i7" in t or "i9" in t or "ryzen" in t:
                    return t

        return "unknown"

    # ======================================================
    # RAM
    # ======================================================
    def extract_ram(self, text: str):
        match = self.ram_pattern.search(text)
        if match:
            return int(match.group(1))
        return None

    # ======================================================
    # STORAGE
    # ======================================================
    def extract_storage(self, text: str):
        match = self.storage_pattern.search(text)
        if match:
            value = match.group(1)
            unit = match.group(2)

            if unit and "tb" in unit.lower():
                return int(value) * 1024
            return int(value)

        return None

    # ======================================================
    # GPU
    # ======================================================
    def extract_gpu(self, text: str):
        match = self.gpu_pattern.search(text)
        if match:
            return match.group(0)
        return "unknown"

    # ======================================================
    # BRAND
    # ======================================================
    def extract_brand(self, text: str):
        match = self.brand_pattern.search(text)
        if match:
            return match.group(0).lower()
        return "unknown"

    # ======================================================
    # GAMING FLAG
    # ======================================================
    def is_gaming(self, text: str):
        gaming_keywords = [
            "gaming", "tuf", "legion", "omen",
            "predator", "victus", "loq"
        ]
        return int(any(k in text for k in gaming_keywords))

    # ======================================================
    # TRANSFORM SINGLE ROW
    # ======================================================
    def transform_row(self, row):
        title = self.normalize(row.get("raw_title", ""))

        return {
            "scrape_timestamp": row.get("scrape_timestamp"),
            "retailer_id": row.get("retailer_id"),
            "raw_title": row.get("raw_title"),
            "raw_current_price": row.get("raw_current_price"),
            "raw_original_price": row.get("raw_original_price"),
            "product_url": row.get("product_url"),
            "category": row.get("category"),
            "sub_category": row.get("sub_category"),

            # engineered features
            "brand": self.extract_brand(title),
            "cpu": self.extract_cpu(title),
            "ram_gb": self.extract_ram(title),
            "storage_gb": self.extract_storage(title),
            "gpu": self.extract_gpu(title),
            "is_gaming": self.is_gaming(title)
        }

    # ======================================================
    # TRANSFORM DATAFRAME (IMPORTANT FIX)
    # ======================================================
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []

        for _, row in df.iterrows():
            rows.append(self.transform_row(row))

        return pd.DataFrame(rows)