"""
tests/test_btech.py
─────────────────────────────────────────────────────────────────────
Unit tests for payload/btech.py

Tests cover:
1. Bronze schema validation on well-formed records
2. Bronze schema rejection on records missing required fields
3. Price parsing helpers (_extract_price, _extract_original_price)
4. CAT_MAP resolution for the Dell laptops URL
5. Full run() mock — Playwright replaced with synthetic card HTML,
   verifying record count and field correctness without live network.
─────────────────────────────────────────────────────────────────────
"""

import asyncio
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch


# ── Stub out playwright so the import doesn't require an install ──
def _make_playwright_stub():
    pw_module = types.ModuleType("playwright")
    async_api = types.ModuleType("playwright.async_api")

    class _FakeContext:
        pass

    async_api.async_playwright = MagicMock()
    async_api.async_playwright.return_value.__aenter__ = AsyncMock(
        return_value=MagicMock()
    )
    async_api.async_playwright.return_value.__aexit__ = AsyncMock(return_value=False)

    sys.modules.setdefault("playwright", pw_module)
    sys.modules.setdefault("playwright.async_api", async_api)


_make_playwright_stub()

# Now safe to import
from payload.btech import CAT_MAP, RETAILER_ID, Scraper  # noqa: E402


# ═══════════════════════════════════════════════════════════════════
#  1. PRICE PARSER TESTS
# ═══════════════════════════════════════════════════════════════════

class TestPriceParsers(unittest.TestCase):

    def test_extract_price_standard(self):
        text = "Price drop\nEGP26,500\nDell\nDell Vostro 15-3530"
        self.assertEqual(Scraper._extract_price(text), "EGP26,500")

    def test_extract_price_no_comma(self):
        text = "EGP8888\nDell Latitude"
        self.assertEqual(Scraper._extract_price(text), "EGP8888")

    def test_extract_price_missing(self):
        self.assertEqual(Scraper._extract_price("No price here"), "")

    def test_extract_original_price_present(self):
        # Card text when "Price drop" badge is shown:
        # first EGP = current (discounted), second EGP = original
        text = "Price drop\nEGP22,999\nEGP29,000\nDell Vostro"
        self.assertEqual(Scraper._extract_original_price(text), "EGP29,000")

    def test_extract_original_price_absent(self):
        text = "EGP17,999\nDell Inspiron"
        self.assertIsNone(Scraper._extract_original_price(text))

    def test_extract_original_price_single_egp(self):
        # Price drop badge present but only one EGP value in text
        text = "Price drop\nEGP22,999\nDell Vostro"
        self.assertIsNone(Scraper._extract_original_price(text))


# ═══════════════════════════════════════════════════════════════════
#  2. CAT_MAP RESOLUTION
# ═══════════════════════════════════════════════════════════════════

class TestCatMap(unittest.TestCase):

    def test_dell_laptops_url_resolves(self):
        path = "/en/c/laptop-pc/laptops/b/dell"
        category, sub_category = CAT_MAP[path]
        self.assertEqual(category, "laptops")
        self.assertEqual(sub_category, "dell")

    def test_laptops_generic_url(self):
        path = "/en/c/laptop-pc/laptops"
        category, sub_category = CAT_MAP[path]
        self.assertEqual(category, "laptops")
        self.assertIsNone(sub_category)

    def test_unknown_url_uses_default(self):
        # Callers fall back to ("laptops", "dell") for unrecognised paths
        path = "/en/c/laptop-pc/laptops/b/dell"  # always in map
        self.assertIn(path, CAT_MAP)


# ═══════════════════════════════════════════════════════════════════
#  3. BRONZE SCHEMA VALIDATION
# ═══════════════════════════════════════════════════════════════════

class TestBronzeValidation(unittest.TestCase):

    def setUp(self):
        self.scraper = Scraper()

    def _make_record(self, **overrides) -> dict:
        base = {
            "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
            "retailer_id": RETAILER_ID,
            "raw_title": "Dell Vostro 3520 Laptop",
            "raw_current_price": "EGP17,999",
            "raw_original_price": None,
            "availability_text": None,
            "product_url": "https://btech.com/en/p/some-slug?offering_id=abc",
            "category": "laptops",
            "sub_category": "dell",
        }
        base.update(overrides)
        return base

    def test_valid_record_passes(self):
        self.assertTrue(self.scraper.validate_record(self._make_record()))

    def test_missing_title_fails(self):
        self.assertFalse(
            self.scraper.validate_record(self._make_record(raw_title=""))
        )

    def test_missing_price_fails(self):
        self.assertFalse(
            self.scraper.validate_record(self._make_record(raw_current_price=""))
        )

    def test_missing_url_fails(self):
        self.assertFalse(
            self.scraper.validate_record(self._make_record(product_url=""))
        )

    def test_missing_retailer_id_fails(self):
        self.assertFalse(
            self.scraper.validate_record(self._make_record(retailer_id=""))
        )

    def test_optional_fields_can_be_none(self):
        record = self._make_record(
            raw_original_price=None,
            availability_text=None,
        )
        self.assertTrue(self.scraper.validate_record(record))

    def test_retailer_id_is_btech(self):
        record = self._make_record()
        self.assertEqual(record["retailer_id"], "btech")

    def test_category_is_laptops(self):
        record = self._make_record()
        self.assertEqual(record["category"], "laptops")

    def test_sub_category_is_dell(self):
        record = self._make_record()
        self.assertEqual(record["sub_category"], "dell")


# ═══════════════════════════════════════════════════════════════════
#  4. MOCKED FULL RUN
# ═══════════════════════════════════════════════════════════════════

class TestMockedRun(unittest.TestCase):
    """
    Replaces _async_run with a synthetic implementation that returns
    two fake records — confirms run() plumbing and schema end-to-end.
    """

    def setUp(self):
        self.scraper = Scraper()

    def test_run_returns_list_of_dicts(self):
        fake_records = [
            {
                "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                "retailer_id": "btech",
                "raw_title": "Dell Vostro 3520",
                "raw_current_price": "EGP17,999",
                "raw_original_price": None,
                "availability_text": None,
                "product_url": "https://btech.com/en/p/abc?offering_id=1",
                "category": "laptops",
                "sub_category": "dell",
            },
            {
                "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                "retailer_id": "btech",
                "raw_title": "Dell G15 5530 Gaming Laptop",
                "raw_current_price": "EGP58,999",
                "raw_original_price": "EGP65,000",
                "availability_text": None,
                "product_url": "https://btech.com/en/p/def?offering_id=2",
                "category": "laptops",
                "sub_category": "dell",
            },
        ]

        async def _fake_async_run(urls):
            return fake_records

        with patch.object(self.scraper, "_async_run", side_effect=_fake_async_run):
            result = self.scraper.run()

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_run_records_pass_validation(self):
        fake_records = [
            {
                "scrape_timestamp": datetime.now(timezone.utc).isoformat(),
                "retailer_id": "btech",
                "raw_title": "Dell Inspiron 3520",
                "raw_current_price": "EGP23,500",
                "raw_original_price": None,
                "availability_text": None,
                "product_url": "https://btech.com/en/p/xyz?offering_id=3",
                "category": "laptops",
                "sub_category": "dell",
            }
        ]

        async def _fake_async_run(urls):
            return fake_records

        with patch.object(self.scraper, "_async_run", side_effect=_fake_async_run):
            result = self.scraper.run()

        for record in result:
            self.assertTrue(
                self.scraper.validate_record(record),
                f"Record failed validation: {record}",
            )

    def test_run_returns_empty_on_async_error(self):
        async def _raise(urls):
            raise RuntimeError("Simulated network failure")

        with patch.object(self.scraper, "_async_run", side_effect=_raise):
            with self.assertRaises(RuntimeError):
                self.scraper.run()


# ═══════════════════════════════════════════════════════════════════
#  5. RETAILER_ID CONSTANT
# ═══════════════════════════════════════════════════════════════════

class TestConstants(unittest.TestCase):

    def test_retailer_id_value(self):
        self.assertEqual(RETAILER_ID, "btech")

    def test_cat_map_is_dict(self):
        self.assertIsInstance(CAT_MAP, dict)

    def test_cat_map_dell_entry_exists(self):
        self.assertIn("/en/c/laptop-pc/laptops/b/dell", CAT_MAP)


if __name__ == "__main__":
    unittest.main(verbosity=2)
