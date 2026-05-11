"""
tests/test_scheduler.py
─────────────────────────────────────────────────────────────────────
Unit tests for the UTC scheduler — delta calculation, catch-up
detection, and interval parsing.
─────────────────────────────────────────────────────────────────────
"""

import sys
import os
import unittest
from datetime import datetime, timedelta, timezone, time as dt_time

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.scheduler import UTCScheduler


class TestIntervalParsing(unittest.TestCase):
    """Test that HH:MM strings are parsed correctly."""

    def test_basic_parsing(self):
        s = UTCScheduler(["00:00", "12:00"])
        self.assertEqual(len(s._intervals), 2)
        self.assertEqual(s._intervals[0], dt_time(0, 0))
        self.assertEqual(s._intervals[1], dt_time(12, 0))

    def test_sorts_ascending(self):
        s = UTCScheduler(["18:30", "06:15", "00:00"])
        times = [t.strftime("%H:%M") for t in s._intervals]
        self.assertEqual(times, ["00:00", "06:15", "18:30"])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            UTCScheduler([])

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            UTCScheduler(["not-a-time"])


class TestDeltaCalculation(unittest.TestCase):
    """Test the core UTC delta calculator."""

    def setUp(self):
        self.scheduler = UTCScheduler(["00:00", "12:00"])

    def test_before_first_interval(self):
        """At 06:00 UTC, next target should be 12:00 UTC today."""
        now = datetime(2026, 4, 5, 6, 0, 0, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        expected = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(target, expected)

    def test_between_intervals(self):
        """At 14:00 UTC, next target should be 00:00 UTC tomorrow."""
        now = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        expected = datetime(2026, 4, 6, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(target, expected)

    def test_exactly_on_interval(self):
        """At exactly 12:00:00 UTC, next should be 00:00 tomorrow."""
        now = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        expected = datetime(2026, 4, 6, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(target, expected)

    def test_just_before_interval(self):
        """At 11:59:59 UTC, next target should be 12:00 UTC today."""
        now = datetime(2026, 4, 5, 11, 59, 59, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        expected = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(target, expected)

    def test_just_after_midnight(self):
        """At 00:00:01 UTC, next target should be 12:00 UTC today."""
        now = datetime(2026, 4, 5, 0, 0, 1, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        expected = datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(target, expected)

    def test_delta_seconds_positive(self):
        """Delta should always be positive."""
        now = datetime(2026, 4, 5, 6, 0, 0, tzinfo=timezone.utc)
        delta, target = self.scheduler.calculate_delta_seconds(now)
        self.assertGreater(delta, 0)
        # Should be 6 hours = 21600 seconds
        self.assertAlmostEqual(delta, 21600.0, places=0)

    def test_23h59m_before_midnight(self):
        """At 23:59 UTC, next should be 00:00 tomorrow (1 minute away)."""
        now = datetime(2026, 4, 5, 23, 59, 0, tzinfo=timezone.utc)
        delta, target = self.scheduler.calculate_delta_seconds(now)
        self.assertAlmostEqual(delta, 60.0, places=0)


class TestCatchUpDetection(unittest.TestCase):
    """Test the catch-up logic for missed intervals."""

    def setUp(self):
        self.scheduler = UTCScheduler(["00:00", "12:00"])

    def test_first_launch_triggers_catchup(self):
        """First launch (no previous execution) should trigger catch-up."""
        now = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
        is_catchup, missed = self.scheduler.check_catchup_needed(None, now)
        self.assertTrue(is_catchup)
        # Most recent past interval at 14:00 should be 12:00 today
        self.assertEqual(
            missed,
            datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_no_catchup_when_recently_served(self):
        """No catch-up needed if last execution was after the recent interval."""
        now = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
        last = datetime(2026, 4, 5, 12, 2, 0, tzinfo=timezone.utc)  # ran at 12:02
        is_catchup, missed = self.scheduler.check_catchup_needed(last, now)
        self.assertFalse(is_catchup)

    def test_catchup_when_interval_missed(self):
        """Catch-up needed: last ran at 00:05, now it's 14:00 (missed 12:00)."""
        now = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
        last = datetime(2026, 4, 5, 0, 5, 0, tzinfo=timezone.utc)
        is_catchup, missed = self.scheduler.check_catchup_needed(last, now)
        self.assertTrue(is_catchup)
        self.assertEqual(
            missed,
            datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc),
        )

    def test_catchup_after_overnight_sleep(self):
        """Laptop was off overnight. Last ran at 12:02 yesterday, now 08:00 today."""
        now = datetime(2026, 4, 6, 8, 0, 0, tzinfo=timezone.utc)
        last = datetime(2026, 4, 5, 12, 2, 0, tzinfo=timezone.utc)
        is_catchup, missed = self.scheduler.check_catchup_needed(last, now)
        self.assertTrue(is_catchup)
        # Should have missed 00:00 today
        self.assertEqual(
            missed,
            datetime(2026, 4, 6, 0, 0, 0, tzinfo=timezone.utc),
        )

    def test_most_recent_past_interval(self):
        """Verify we find the correct most recent past interval."""
        # At 08:00, most recent past is 00:00 today
        now = datetime(2026, 4, 5, 8, 0, 0, tzinfo=timezone.utc)
        recent = self.scheduler.find_most_recent_past_interval(now)
        self.assertEqual(
            recent,
            datetime(2026, 4, 5, 0, 0, 0, tzinfo=timezone.utc),
        )

        # At 14:00, most recent past is 12:00 today
        now = datetime(2026, 4, 5, 14, 0, 0, tzinfo=timezone.utc)
        recent = self.scheduler.find_most_recent_past_interval(now)
        self.assertEqual(
            recent,
            datetime(2026, 4, 5, 12, 0, 0, tzinfo=timezone.utc),
        )


class TestMultipleIntervals(unittest.TestCase):
    """Test with more than 2 intervals (e.g., 6-hour)."""

    def setUp(self):
        self.scheduler = UTCScheduler(["00:00", "06:00", "12:00", "18:00"])

    def test_four_intervals(self):
        """At 03:30 UTC, next should be 06:00."""
        now = datetime(2026, 4, 5, 3, 30, 0, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        self.assertEqual(
            target,
            datetime(2026, 4, 5, 6, 0, 0, tzinfo=timezone.utc),
        )

    def test_after_last_interval(self):
        """At 20:00 UTC, next should be 00:00 tomorrow."""
        now = datetime(2026, 4, 5, 20, 0, 0, tzinfo=timezone.utc)
        target = self.scheduler.calculate_next_target(now)
        self.assertEqual(
            target,
            datetime(2026, 4, 6, 0, 0, 0, tzinfo=timezone.utc),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
