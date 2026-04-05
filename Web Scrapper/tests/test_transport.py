"""
tests/test_transport.py
─────────────────────────────────────────────────────────────────────
Unit tests for the cloud transport layer — retry logic, buffering,
and buffer flushing.
─────────────────────────────────────────────────────────────────────
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.transport import CloudTransport


def make_config(buffer_dir: str) -> dict:
    """Create a test config dict with a temp buffer directory."""
    return {
        "cloud_retry": {
            "max_retries": 3,
            "retry_interval_seconds": 0,  # 0 for fast tests
        },
        "gcp": {
            "project_id": "test-project",
            "bronze_bucket": "test-bucket",
            "credentials_path": "",
        },
        "database": {
            "cycle_db_dir": os.path.join(buffer_dir, "cycles"),
            "buffer_dir": buffer_dir,
        },
    }


class TestRetryLogic(unittest.TestCase):
    """Test the mandatory 3x retry at 1-minute interval logic."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = make_config(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_success_on_first_attempt(self):
        """If upload succeeds immediately, no retries needed."""
        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(return_value=True)

        records = [{"retailer_id": "2b", "data": "test"}]
        success = transport._upload_with_retry(records, "blob.json", "2b", "c1")

        self.assertTrue(success)
        self.assertEqual(transport._do_upload.call_count, 1)

    def test_success_on_second_retry(self):
        """Upload fails once, succeeds on first retry."""
        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(side_effect=[False, True])

        records = [{"retailer_id": "2b", "data": "test"}]
        success = transport._upload_with_retry(records, "blob.json", "2b", "c1")

        self.assertTrue(success)
        self.assertEqual(transport._do_upload.call_count, 2)

    def test_all_retries_exhausted(self):
        """After initial + 3 retries (4 total), data should be buffered."""
        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(return_value=False)

        records = [{"retailer_id": "2b", "data": "test"}]
        success = transport._upload_with_retry(records, "blob.json", "2b", "c1")

        self.assertFalse(success)
        # initial attempt + 3 retries = 4 calls
        self.assertEqual(transport._do_upload.call_count, 4)

    def test_buffer_file_created_on_exhaustion(self):
        """When retries exhaust, a buffer file should be written."""
        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(return_value=False)

        records = [{"retailer_id": "2b_egypt", "data": "important"}]
        transport._upload_with_retry(records, "blob.json", "2b_egypt", "cycle1")

        buffer_files = list(
            f for f in os.listdir(self.tmpdir) if f.endswith(".json")
        )
        self.assertEqual(len(buffer_files), 1)

        # Verify buffer content
        with open(os.path.join(self.tmpdir, buffer_files[0])) as f:
            data = json.load(f)
        self.assertEqual(data["retailer_id"], "2b_egypt")
        self.assertEqual(data["record_count"], 1)
        self.assertEqual(len(data["records"]), 1)


class TestNotifierIntegration(unittest.TestCase):
    """Test that webhook alerts fire on upload failures."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = make_config(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_webhook_fired_on_first_failure(self):
        """Webhook should fire on the very first upload failure."""
        mock_notifier = MagicMock()
        transport = CloudTransport(self.config, notifier=mock_notifier)
        transport._do_upload = MagicMock(return_value=False)

        records = [{"retailer_id": "2b", "data": "test"}]
        transport._upload_with_retry(records, "blob.json", "2b", "c1")

        # notify_upload_failure should be called for each retry
        self.assertTrue(mock_notifier.notify_upload_failure.called)

        # notify_upload_exhausted should be called once at the end
        mock_notifier.notify_upload_exhausted.assert_called_once()

    def test_no_webhook_on_success(self):
        """No webhook alerts if upload succeeds."""
        mock_notifier = MagicMock()
        transport = CloudTransport(self.config, notifier=mock_notifier)
        transport._do_upload = MagicMock(return_value=True)

        records = [{"retailer_id": "2b", "data": "test"}]
        transport._upload_with_retry(records, "blob.json", "2b", "c1")

        mock_notifier.notify_upload_failure.assert_not_called()
        mock_notifier.notify_upload_exhausted.assert_not_called()


class TestBufferFlush(unittest.TestCase):
    """Test the store-and-forward buffer flushing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = make_config(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_flush_empty_buffer(self):
        """Flushing an empty buffer should return (0, 0)."""
        transport = CloudTransport(self.config)
        flushed, remaining = transport.flush_buffer()
        self.assertEqual(flushed, 0)
        self.assertEqual(remaining, 0)

    def test_flush_successful(self):
        """Buffered files should be deleted on successful upload."""
        # Create a fake buffer file
        buf_file = os.path.join(self.tmpdir, "test_buffer.json")
        buf_data = {
            "retailer_id": "2b",
            "blob_name": "2b/test.json",
            "records": [{"retailer_id": "2b", "data": "buffered"}],
        }
        with open(buf_file, "w") as f:
            json.dump(buf_data, f)

        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(return_value=True)

        flushed, remaining = transport.flush_buffer()
        self.assertEqual(flushed, 1)
        self.assertEqual(remaining, 0)
        self.assertFalse(os.path.exists(buf_file))  # Deleted on success

    def test_flush_failed_keeps_file(self):
        """Buffer files should persist if flush upload fails."""
        buf_file = os.path.join(self.tmpdir, "test_buffer.json")
        buf_data = {
            "retailer_id": "2b",
            "blob_name": "2b/test.json",
            "records": [{"retailer_id": "2b", "data": "buffered"}],
        }
        with open(buf_file, "w") as f:
            json.dump(buf_data, f)

        transport = CloudTransport(self.config)
        transport._do_upload = MagicMock(return_value=False)

        flushed, remaining = transport.flush_buffer()
        self.assertEqual(flushed, 0)
        self.assertEqual(remaining, 1)
        self.assertTrue(os.path.exists(buf_file))  # Kept on failure

    def test_buffer_count(self):
        """get_buffer_count should return correct number."""
        for i in range(3):
            with open(os.path.join(self.tmpdir, f"buf_{i}.json"), "w") as f:
                json.dump({"records": []}, f)

        transport = CloudTransport(self.config)
        self.assertEqual(transport.get_buffer_count(), 3)


class TestUploadCycleData(unittest.TestCase):
    """Test the high-level upload_cycle_data method."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config = make_config(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_groups_by_retailer(self):
        """Records should be grouped by retailer_id for upload."""
        transport = CloudTransport(self.config)
        transport._upload_with_retry = MagicMock(return_value=True)

        records = [
            {"retailer_id": "2b_egypt", "raw_title": "A"},
            {"retailer_id": "2b_egypt", "raw_title": "B"},
            {"retailer_id": "dream2000", "raw_title": "C"},
        ]
        transport.upload_cycle_data(records, "c1")

        # Should be called twice (once per retailer)
        self.assertEqual(transport._upload_with_retry.call_count, 2)

    def test_empty_records(self):
        """Empty record list should return True (nothing to upload)."""
        transport = CloudTransport(self.config)
        result = transport.upload_cycle_data([], "c1")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
