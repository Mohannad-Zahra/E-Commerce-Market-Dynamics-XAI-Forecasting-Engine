"""
engine/sleep_prevention.py
─────────────────────────────────────────────────────────────────────
Windows OS-level sleep/hibernate prevention using kernel32 API.

Uses SetThreadExecutionState to signal Windows that the system
must remain awake while the scraper infrastructure is running.

This module is a context manager:
    with SleepPrevention():
        # ... system will not sleep/hibernate ...

On non-Windows platforms, it degrades gracefully (no-op with a warning).
─────────────────────────────────────────────────────────────────────
"""

import logging
import platform
import sys

logger = logging.getLogger("engine.sleep_prevention")

# ── Windows API constants ────────────────────────────────────────────
# https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadexecutionstate
ES_CONTINUOUS       = 0x80000000  # Preserves the flag until explicitly cleared
ES_SYSTEM_REQUIRED  = 0x00000001  # Prevents system from entering sleep
ES_DISPLAY_REQUIRED = 0x00000002  # Prevents display from turning off (optional)
ES_AWAYMODE_REQUIRED = 0x00000040 # Enables away mode (prevents full hibernate)


class SleepPrevention:
    """
    Context manager that prevents Windows from sleeping or hibernating.

    On enter:  Sets ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
    On exit:   Clears back to ES_CONTINUOUS (allows sleep again)

    Usage:
        with SleepPrevention():
            # System stays awake for the lifetime of this block
            run_scraper_loop()
    """

    def __init__(self, prevent_display_off: bool = False):
        """
        Args:
            prevent_display_off: If True, also prevents the monitor from
                                 turning off. Not usually needed for headless
                                 scraping, but useful during debugging.
        """
        self._prevent_display = prevent_display_off
        self._is_windows = platform.system() == "Windows"
        self._kernel32 = None
        self._original_state = None

    def __enter__(self):
        if not self._is_windows:
            logger.warning(
                "SleepPrevention is a no-op on %s. "
                "Only Windows is supported via SetThreadExecutionState.",
                platform.system(),
            )
            return self

        try:
            import ctypes
            self._kernel32 = ctypes.windll.kernel32

            # Build the desired execution state flags
            flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED
            if self._prevent_display:
                flags |= ES_DISPLAY_REQUIRED

            # Set the thread execution state
            self._original_state = self._kernel32.SetThreadExecutionState(flags)

            if self._original_state == 0:
                logger.error(
                    "SetThreadExecutionState returned 0 — failed to prevent sleep. "
                    "The system may still hibernate."
                )
            else:
                logger.info(
                    "Sleep prevention ACTIVATED (flags=0x%08X). "
                    "System will not sleep or hibernate.",
                    flags,
                )

        except Exception as exc:
            logger.error(
                "Failed to activate sleep prevention: %s. "
                "The system may still hibernate.",
                exc,
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._is_windows or self._kernel32 is None:
            return False

        try:
            # Clear all flags — restore to default (allow sleep)
            result = self._kernel32.SetThreadExecutionState(ES_CONTINUOUS)

            if result == 0:
                logger.error(
                    "SetThreadExecutionState(ES_CONTINUOUS) returned 0 — "
                    "failed to restore default sleep behavior."
                )
            else:
                logger.info("Sleep prevention DEACTIVATED. System may now sleep.")

        except Exception as exc:
            logger.error("Failed to deactivate sleep prevention: %s", exc)

        return False  # Do not suppress exceptions
