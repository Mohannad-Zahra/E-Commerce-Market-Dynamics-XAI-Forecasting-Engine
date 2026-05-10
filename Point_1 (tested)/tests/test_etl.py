"""
test_etl.py — ETL Feature Engine Unit Tests
=============================================
"""

import pytest
import pandas as pd
from datetime import datetime

from Point_1.etl.feature_engine import (
    compute_potential_laptop,
    compute_potential_phone,
    detect_brand,
    detect_gaming,
    extract_chipset_score,
    extract_gpu_from_title,
    extract_ram_gb,
    extract_storage_gb,
    infer_category,
    run_feature_engineering,
    get_category_distribution,
)


class TestCategoryInference:
    def test_laptop_from_url(self):
        assert infer_category("https://2b.com.eg/laptop-lenovo", "Lenovo") == "Laptop"

    def test_phone_from_title(self):
        assert infer_category("https://2b.com.eg/prod-456", "Samsung Galaxy S24 Ultra") == "Phone"

    def test_tablet_from_title(self):
        assert infer_category("https://2b.com.eg/prod-789", "Apple iPad Pro M2") == "Tablet"

    def test_default_phone(self):
        assert infer_category("https://2b.com.eg/xyz", "Unknown Product") == "Phone"


class TestGPUExtraction:
    def test_rtx_4060(self):
        assert extract_gpu_from_title("Laptop RTX 4060 16GB") == "RTX 4060"

    def test_no_gpu(self):
        assert extract_gpu_from_title("Samsung Galaxy S24") is None


class TestRAMExtraction:
    def test_16gb(self):
        assert extract_ram_gb("Laptop 16GB RAM DDR5") == 16.0

    def test_none(self):
        assert extract_ram_gb("Product without specs") is None


class TestStorageExtraction:
    def test_512gb_ssd(self):
        assert extract_storage_gb("Laptop 512GB SSD") == 512.0

    def test_1tb(self):
        assert extract_storage_gb("Laptop 1TB NVMe SSD") == 1024.0


class TestChipsetScore:
    def test_snapdragon_8_gen3(self):
        assert extract_chipset_score("Galaxy S24 Snapdragon 8 Gen 3") == 0.95

    def test_no_chipset(self):
        assert extract_chipset_score("Random product") is None


class TestComputePotential:
    def test_laptop_rtx_4070(self):
        assert abs(compute_potential_laptop(7) - 0.6667) < 0.01

    def test_laptop_no_gpu(self):
        assert abs(compute_potential_laptop(None) - 0.1111) < 0.01

    def test_phone_chipset(self):
        assert compute_potential_phone(0.95, None, None) == 0.95


class TestBrandDetection:
    def test_lenovo(self):
        assert detect_brand("Lenovo IdeaPad 3") == "Lenovo"

    def test_unknown(self):
        assert detect_brand("XYZ-123") == "Unknown"


class TestGamingDetection:
    def test_gaming(self):
        assert detect_gaming("ASUS ROG Strix Gaming Laptop") is True

    def test_non_gaming(self):
        assert detect_gaming("Lenovo IdeaPad 3") is False


class TestRunFeatureEngineering:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame([
            {
                "product_url": "https://2b.com.eg/laptop-lenovo-loq-rtx4060",
                "raw_title": "Lenovo LOQ Gaming Laptop 16GB RAM 512GB SSD RTX 4060",
                "raw_current_price": 42999.0,
                "raw_original_price": 49999.0,
                "retailer_id": "2b_egypt",
                "scrape_timestamp": datetime(2026, 5, 10),
            },
            {
                "product_url": "https://sigma.com/samsung-galaxy-s24",
                "raw_title": "Samsung Galaxy S24 Ultra Snapdragon 8 Gen 3 12GB",
                "raw_current_price": 72000.0,
                "raw_original_price": None,
                "retailer_id": "sigma_computer",
                "scrape_timestamp": datetime(2026, 5, 10),
            },
        ])

    def test_produces_required_columns(self, sample_df):
        result = run_feature_engineering(sample_df)
        for col in ["category", "brand", "is_gaming", "gpu", "compute_potential",
                     "delta_p_1d", "vol_30d"]:
            assert col in result.columns, f"Missing: {col}"

    def test_laptop_classified(self, sample_df):
        result = run_feature_engineering(sample_df)
        row = result[result["product_url"].str.contains("laptop")].iloc[0]
        assert row["category"] == "Laptop"
        assert row["gpu"] == "RTX 4060"
        assert row["is_gaming"] == True
        assert row["brand"] == "Lenovo"

    def test_phone_classified(self, sample_df):
        result = run_feature_engineering(sample_df)
        row = result[result["product_url"].str.contains("samsung")].iloc[0]
        assert row["category"] == "Phone"

    def test_compute_potential_valid_range(self, sample_df):
        result = run_feature_engineering(sample_df)
        assert (result["compute_potential"] >= 0).all()
        assert (result["compute_potential"] <= 1).all()

    def test_empty_df(self):
        assert run_feature_engineering(pd.DataFrame()).empty

    def test_category_distribution(self, sample_df):
        result = run_feature_engineering(sample_df)
        dist = get_category_distribution(result)
        assert "Laptop" in dist
        assert "Phone" in dist
