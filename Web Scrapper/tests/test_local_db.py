"""
tests/test_local_db.py
─────────────────────────────────────────────────────────────────────
Unit tests for the SQLite per-cycle database manager.
─────────────────────────────────────────────────────────────────────
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.local_db import CycleDatabase, BRONZE_COLUMNS


def make_record(**overrides) -> dict:
    """Create a valid Bronze record with optional overrides."""
    base = {
        "scrape_timestamp": "2026-04-05T00:00:02Z",
        "retailer_id": "2b_egypt",
        "raw_title": "Samsung Galaxy S24 Ultra 256GB",
        "raw_current_price": "45,999 EGP",
        "raw_original_price": "52,999 EGP",
        "availability_text": "In Stock",
        "product_url": "https://2b.com.eg/samsung-galaxy-s24-ultra",
        "category": "electronics",
    }
    base.update(overrides)
    return base


class TestCycleDatabaseCreation(unittest.TestCase):
    """Test database file creation and schema."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_db_file(self):
        """A new .db file should be created on disk."""
        ts = datetime(2026, 4, 5, 0, 0, 0, tzinfo=timezone.utc)
        with CycleDatabase(self.tmpdir, ts) as db:
            self.assertTrue(db.db_path.exists())
            self.assertTrue(str(db.db_path).endswith(".db"))

    def test_filename_format(self):
        """Filename should contain timestamp and cycle_id."""
        ts = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        with CycleDatabase(self.tmpdir, ts) as db:
            name = db.db_path.name
            self.assertTrue(name.startswith("2026-04-05T12-00-00Z_"))
            self.assertTrue(name.endswith(".db"))

    def test_unique_cycle_ids(self):
        """Each database should get a unique cycle_id."""
        ts = datetime(2026, 4, 5, 0, 0, 0, tzinfo=timezone.utc)
        with CycleDatabase(self.tmpdir, ts) as db1:
            id1 = db1.cycle_id
        with CycleDatabase(self.tmpdir, ts) as db2:
            id2 = db2.cycle_id
        self.assertNotEqual(id1, id2)

    def test_creates_directory(self):
        """Should create the cycle directory if it doesn't exist."""
        nested = os.path.join(self.tmpdir, "deep", "nested", "dir")
        with CycleDatabase(nested) as db:
            self.assertTrue(db.db_path.exists())


class TestRecordInsert(unittest.TestCase):
    """Test record insertion and validation."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_insert_valid_records(self):
        """Valid records should insert successfully."""
        with CycleDatabase(self.tmpdir) as db:
            records = [make_record() for _ in range(5)]
            inserted, skipped = db.insert_records(records)
            self.assertEqual(inserted, 5)
            self.assertEqual(skipped, 0)
            self.assertEqual(db.record_count, 5)

    def test_skip_invalid_records(self):
        """Records with missing required fields should be skipped."""
        with CycleDatabase(self.tmpdir) as db:
            records = [
                make_record(),                                     # valid
                make_record(raw_title=""),                         # invalid: empty
                make_record(product_url=None),                     # invalid: None
                make_record(),                                     # valid
                {"foo": "bar"},                                    # invalid: missing all
            ]
            inserted, skipped = db.insert_records(records)
            self.assertEqual(inserted, 2)
            self.assertEqual(skipped, 3)

    def test_nullable_fields(self):
        """Nullable fields (raw_original_price, availability_text) can be None."""
        with CycleDatabase(self.tmpdir) as db:
            record = make_record(raw_original_price=None, availability_text=None)
            inserted, skipped = db.insert_records([record])
            self.assertEqual(inserted, 1)
            self.assertEqual(skipped, 0)

    def test_extra_fields_stored_as_json(self):
        """Extra fields beyond Bronze schema should be in extra_data."""
        with CycleDatabase(self.tmpdir) as db:
            record = make_record(brand="Samsung", discount_pct="15%")
            db.insert_records([record])
            results = db.get_all_records()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["brand"], "Samsung")
            self.assertEqual(results[0]["discount_pct"], "15%")

    def test_category_subcategory_roundtrip(self):
        """category and sub_category should survive insert → retrieve."""
        with CycleDatabase(self.tmpdir) as db:
            record = make_record(category="computers", sub_category="laptops")
            db.insert_records([record])
            results = db.get_all_records()
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["category"], "computers")
            self.assertEqual(results[0]["sub_category"], "laptops")

    def test_missing_category_rejected(self):
        """Records without mandatory 'category' should be skipped."""
        with CycleDatabase(self.tmpdir) as db:
            bad = make_record()
            bad.pop("category")  # remove required field
            inserted, skipped = db.insert_records([bad])
            self.assertEqual(inserted, 0)
            self.assertEqual(skipped, 1)

    def test_subcategory_nullable(self):
        """sub_category=None should insert and retrieve as None."""
        with CycleDatabase(self.tmpdir) as db:
            record = make_record(sub_category=None)
            db.insert_records([record])
            results = db.get_all_records()
            self.assertEqual(len(results), 1)
            self.assertIsNone(results[0]["sub_category"])


class TestRecordRetrieval(unittest.TestCase):
    """Test reading records back from the database."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_all_records(self):
        """get_all_records should return all inserted records."""
        with CycleDatabase(self.tmpdir) as db:
            records = [
                make_record(retailer_id="2b_egypt"),
                make_record(retailer_id="dream2000"),
                make_record(retailer_id="sigma_computer"),
            ]
            db.insert_records(records)
            results = db.get_all_records()
            self.assertEqual(len(results), 3)

    def test_get_by_retailer(self):
        """Filter records by retailer_id."""
        with CycleDatabase(self.tmpdir) as db:
            records = [
                make_record(retailer_id="2b_egypt"),
                make_record(retailer_id="2b_egypt"),
                make_record(retailer_id="dream2000"),
            ]
            db.insert_records(records)

            twob = db.get_records_by_retailer("2b_egypt")
            self.assertEqual(len(twob), 2)

            dream = db.get_records_by_retailer("dream2000")
            self.assertEqual(len(dream), 1)

    def test_get_record_count(self):
        """SQL-based count should match insertion count."""
        with CycleDatabase(self.tmpdir) as db:
            db.insert_records([make_record() for _ in range(10)])
            self.assertEqual(db.get_record_count(), 10)

    def test_roundtrip_preserves_data(self):
        """Data should survive insert → retrieve roundtrip."""
        with CycleDatabase(self.tmpdir) as db:
            original = make_record(
                raw_title="Test Roundtrip Product ™",
                raw_current_price="12,345 EGP",
            )
            db.insert_records([original])
            results = db.get_all_records()
            self.assertEqual(results[0]["raw_title"], "Test Roundtrip Product ™")
            self.assertEqual(results[0]["raw_current_price"], "12,345 EGP")


class TestDatabasePersistence(unittest.TestCase):
    """Test that the .db file persists after close (local backup)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_file_persists_after_close(self):
        """DB file should exist on disk after context manager exits."""
        with CycleDatabase(self.tmpdir) as db:
            db.insert_records([make_record()])
            db_path = db.db_path

        # File should still exist
        self.assertTrue(db_path.exists())
        # File should have non-zero size
        self.assertGreater(db_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
