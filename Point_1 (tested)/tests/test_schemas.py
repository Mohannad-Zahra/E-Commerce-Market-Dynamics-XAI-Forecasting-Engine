"""
test_schemas.py — Pydantic Schema Validation Tests
====================================================
Tests that all Pydantic models correctly validate, reject bad data,
and handle edge cases like price-string cleaning.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from Point_1.db.schemas import (
    BatchCreateIn,
    RawProductIn,
    ProcessedProductOut,
)


# ═══════════════════════════════════════════════════════════════════════════════
# BatchCreateIn
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchCreateIn:

    def test_defaults(self):
        batch = BatchCreateIn()
        assert batch.category == "all"
        assert batch.target_count == 100

    def test_custom_values(self):
        batch = BatchCreateIn(category="laptop", target_count=50)
        assert batch.category == "laptop"
        assert batch.target_count == 50

    def test_rejects_negative_count(self):
        with pytest.raises(ValidationError):
            BatchCreateIn(target_count=0)

    def test_rejects_excessive_count(self):
        with pytest.raises(ValidationError):
            BatchCreateIn(target_count=999999)


# ═══════════════════════════════════════════════════════════════════════════════
# RawProductIn
# ═══════════════════════════════════════════════════════════════════════════════

class TestRawProductIn:

    def test_valid_minimal(self):
        product = RawProductIn(
            retailer_id="2b_egypt",
            raw_title="Lenovo LOQ 15IAX9I Gaming Laptop RTX 4060",
            raw_current_price=42999.0,
            product_url="https://www.2b.com.eg/en/lenovo-loq-15iax9i.html",
        )
        assert product.raw_current_price == 42999.0
        assert product.scrape_timestamp is None  # auto-assigned by server
        assert product.raw_original_price is None

    def test_valid_full(self):
        product = RawProductIn(
            scrape_timestamp=datetime(2026, 5, 10, 12, 0, 0),
            retailer_id="sigma_computer",
            raw_title="Apple iPhone 15 Pro Max 256GB",
            raw_current_price=75000.0,
            raw_original_price=82000.0,
            product_url="https://sigma-computer.com/iphone15promax",
        )
        assert product.raw_original_price == 82000.0

    def test_price_string_cleaning(self):
        """Verify that 'EGP 42,999' gets cleaned to 42999.0"""
        product = RawProductIn(
            retailer_id="2b_egypt",
            raw_title="Test Product",
            raw_current_price="EGP 42,999",
            product_url="https://example.com/test",
        )
        assert product.raw_current_price == 42999.0

    def test_price_string_cleaning_with_currency(self):
        product = RawProductIn(
            retailer_id="btech",
            raw_title="Test Product",
            raw_current_price="£1,500",
            product_url="https://btech.com/test",
        )
        assert product.raw_current_price == 1500.0

    def test_rejects_zero_price(self):
        with pytest.raises(ValidationError):
            RawProductIn(
                retailer_id="2b_egypt",
                raw_title="Test",
                raw_current_price=0,
                product_url="https://example.com/test",
            )

    def test_rejects_negative_price(self):
        with pytest.raises(ValidationError):
            RawProductIn(
                retailer_id="2b_egypt",
                raw_title="Test",
                raw_current_price=-100,
                product_url="https://example.com/test",
            )

    def test_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            RawProductIn(
                retailer_id="2b_egypt",
                raw_title="",
                raw_current_price=1000,
                product_url="https://example.com/test",
            )

    def test_rejects_empty_retailer(self):
        with pytest.raises(ValidationError):
            RawProductIn(
                retailer_id="",
                raw_title="Test",
                raw_current_price=1000,
                product_url="https://example.com/test",
            )
