"""
engine/scheduler.py
─────────────────────────────────────────────────────────────────────
UTC-synchronized scheduling engine with catch-up execution.

Core responsibilities:
  1. Calculate the exact delta (in seconds) to the next fixed UTC
     interval (e.g., 00:00 or 12:00).
  2. Sleep until that exact global second.
  3. Detect missed intervals (laptop was asleep/off) and trigger
     immediate catch-up execution.
  4. Self-correct after every cycle — never use naive sleep(43200).

This module has ZERO knowledge of what is scraped. It only decides
WHEN to fire the scrape callback.
─────────────────────────────────────────────────────────────────────
"""

import logging
import time as time_module
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Callable

logger = logging.getLogger("engine.scheduler")


class UTCScheduler:
    """
    UTC-anchored interval scheduler with catch-up logic.

    The scheduler operates on fixed UTC times (e.g., ["00:00", "12:00"]).
    On each iteration:
      1. It computes the next target UTC datetime.
      2. It sleeps until that moment.
      3. On wake, it checks if the actual time has drifted past the target
         (system was asleep) — if so, it flags a catch-up execution.
      4. It calls the provided `on_cycle` callback.
      5. After the callback returns, it recalculates from scratch (no drift).

    Usage:
        scheduler = UTCScheduler(intervals=["00:00", "12:00"])
        scheduler.run(on_cycle=my_scrape_function)
    """

    # Maximum acceptable drift (in seconds) between target and actual wake.
    # Beyond this, we consider the interval "missed" and log a catch-up.
    CATCHUP_THRESHOLD_SECONDS = 60.0

    def __init__(self, intervals: list[str]):
        """
        Args:
            intervals: List of UTC time strings in "HH:MM" format.
                       Example: ["00:00", "12:00"]
        """
        if not intervals:
            raise ValueError("At least one interval must be specified.")

        self._intervals = self._parse_intervals(intervals)
        self._running = True

        logger.info(
            "UTCScheduler initialized with intervals: %s",
            [t.strftime("%H:%M") for t in self._intervals],
        )

    # ── Interval Parsing ──────────────────────────────────────────

    @staticmethod
    def _parse_intervals(raw: list[str]) -> list[dt_time]:
        """Parse "HH:MM" strings into dt_time objects, sorted ascending."""
        parsed = []
        for s in raw:
            parts = s.strip().split(":")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid interval format '{s}'. Expected 'HH:MM'."
                )
            h, m = int(parts[0]), int(parts[1])
            parsed.append(dt_time(h, m, 0))
        parsed.sort()
        return parsed

    # ── Core Algorithm ────────────────────────────────────────────

    def calculate_next_target(
        self, now: datetime | None = None
    ) -> datetime:
        """
        Calculate the next target UTC datetime from the configured intervals.

        Algorithm:
          1. For each interval, construct today's target at that HH:MM UTC.
          2. If the target is in the past (already passed today), try tomorrow.
          3. Return the nearest future target.

        Args:
            now: Current UTC datetime. If None, uses datetime.now(timezone.utc).

        Returns:
            The next target as a timezone-aware UTC datetime.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        candidates = []
        for t in self._intervals:
            # Today at this interval time
            target = now.replace(
                hour=t.hour, minute=t.minute, second=0, microsecond=0
            )
            if target <= now:
                # Already passed today — move to tomorrow
                target += timedelta(days=1)
            candidates.append(target)

        next_target = min(candidates)
        return next_target

    def calculate_delta_seconds(
        self, now: datetime | None = None
    ) -> tuple[float, datetime]:
        """
        Calculate seconds until the next interval.

        Returns:
            Tuple of (delta_seconds, target_datetime).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        target = self.calculate_next_target(now)
        delta = (target - now).total_seconds()

        return delta, target

    def find_most_recent_past_interval(
        self, now: datetime | None = None
    ) -> datetime:
        """
        Find the most recent interval that has already passed.
        Used for catch-up detection: if this interval wasn't serviced,
        we need to execute it now.

        Returns:
            The most recent past interval as a UTC datetime.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        candidates = []
        for t in self._intervals:
            # Today at this interval time
            target = now.replace(
                hour=t.hour, minute=t.minute, second=0, microsecond=0
            )
            if target > now:
                # This one hasn't happened yet today — try yesterday
                target -= timedelta(days=1)
            candidates.append(target)

        return max(candidates)

    # ── Catch-Up Detection ────────────────────────────────────────

    def check_catchup_needed(
        self, last_execution_utc: datetime | None, now: datetime | None = None
    ) -> tuple[bool, datetime | None]:
        """
        Determine whether a catch-up scrape is needed.

        A catch-up is needed when:
          - The laptop woke up after a scheduled interval
          - The last execution was BEFORE the most recent past interval

        Args:
            last_execution_utc: When the last cycle actually ran (UTC).
                                None on first launch.
            now: Current UTC time (injected for testing).

        Returns:
            Tuple of (is_catchup_needed, missed_interval_datetime).
        """
        if now is None:
            now = datetime.now(timezone.utc)

        most_recent = self.find_most_recent_past_interval(now)

        # If we've never run, we need a catch-up for the most recent interval
        if last_execution_utc is None:
            logger.info(
                "First launch. Most recent past interval: %s. "
                "Triggering immediate catch-up.",
                most_recent.isoformat(),
            )
            return True, most_recent

        # If last execution was before the most recent interval, we missed it
        if last_execution_utc < most_recent:
            logger.warning(
                "MISSED INTERVAL detected. "
                "Last execution: %s, Missed interval: %s. "
                "Triggering catch-up.",
                last_execution_utc.isoformat(),
                most_recent.isoformat(),
            )
            return True, most_recent

        return False, None

    # ── Main Run Loop ─────────────────────────────────────────────

    def run(
        self,
        on_cycle: Callable[[bool, datetime], None],
        last_execution_utc: datetime | None = None,
    ):
        """
        Main scheduling loop. Blocks indefinitely.

        Args:
            on_cycle:  Callback invoked at each interval.
                       Signature: on_cycle(is_catchup: bool, target_utc: datetime)
            last_execution_utc: When the last cycle ran (for catch-up on first launch).
        """
        logger.info("Scheduler run loop started.")

        # ── Step 0: Check for catch-up on startup ─────────────────
        is_catchup, missed_interval = self.check_catchup_needed(
            last_execution_utc
        )
        if is_catchup and missed_interval is not None:
            logger.info(
                "CATCH-UP EXECUTION: running missed interval %s NOW.",
                missed_interval.isoformat(),
            )
            try:
                on_cycle(True, missed_interval)
            except Exception as exc:
                logger.error(
                    "Catch-up cycle failed: %s", exc, exc_info=True
                )
            last_execution_utc = datetime.now(timezone.utc)

        # ── Step 1: Normal scheduling loop ────────────────────────
        while self._running:
            now = datetime.now(timezone.utc)
            delta, target = self.calculate_delta_seconds(now)

            logger.info(
                "Next scrape at %s UTC (sleeping %.1f seconds / %.1f hours)",
                target.strftime("%Y-%m-%d %H:%M:%S"),
                delta,
                delta / 3600,
            )

            # ── Step 2: Sleep until target ────────────────────────
            # We sleep in 1-second chunks so we can check self._running
            # and detect OS sleep/wake (time jumps).
            sleep_start = time_module.monotonic()
            target_timestamp = target.timestamp()

            while self._running:
                now_ts = datetime.now(timezone.utc).timestamp()
                remaining = target_timestamp - now_ts

                if remaining <= 0:
                    break  # Time to wake up

                # Sleep in chunks: min(remaining, 30 seconds)
                # 30s chunks allow reasonably fast shutdown response
                chunk = min(remaining, 30.0)
                try:
                    time_module.sleep(chunk)
                except (KeyboardInterrupt, SystemExit):
                    self._running = False
                    break

            if not self._running:
                break

            # ── Step 3: Post-wake drift check ─────────────────────
            actual_wake = datetime.now(timezone.utc)
            drift = (actual_wake - target).total_seconds()
            is_late = drift > self.CATCHUP_THRESHOLD_SECONDS

            if is_late:
                logger.warning(
                    "DRIFT DETECTED: Woke %.1fs after target %s. "
                    "System was likely asleep. Executing as CATCH-UP.",
                    drift,
                    target.isoformat(),
                )

            # ── Step 4: Execute the cycle callback ────────────────
            logger.info(
                "WAKE: Executing cycle for target %s (drift=%.2fs, catchup=%s)",
                target.strftime("%Y-%m-%d %H:%M:%S"),
                drift,
                is_late,
            )

            try:
                on_cycle(is_late, target)
            except Exception as exc:
                logger.error(
                    "Cycle execution failed: %s", exc, exc_info=True
                )

            last_execution_utc = datetime.now(timezone.utc)

            # ── Step 5: Loop back to recalculate delta ────────────
            # (no sleep(43200) — delta is recomputed from scratch)

        logger.info("Scheduler run loop stopped.")

    def stop(self):
        """Signal the scheduler to exit its run loop."""
        logger.info("Scheduler stop requested.")
        self._running = False
