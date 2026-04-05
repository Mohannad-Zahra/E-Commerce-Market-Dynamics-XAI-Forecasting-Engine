"""
watchdog.py
─────────────────────────────────────────────────────────────────────
Lightweight process supervisor for the scraper infrastructure.

This is compiled into `watchdog.exe` via PyInstaller. It:
  1. Activates Windows sleep prevention (system stays awake).
  2. Launches `scraper.exe` as a child process.
  3. Monitors the child — if it dies (OOM, crash, unhandled exception),
     the Watchdog restarts it and fires a webhook notification.
  4. Respects a maximum restart budget to avoid infinite crash loops.
  5. Handles graceful shutdown on Ctrl+C / SIGINT / SIGTERM.

This file has ZERO knowledge of scraping logic, UTC scheduling, or
retailer payloads. It is purely a process lifecycle manager.

Usage (development):
    python watchdog.py

Usage (production):
    watchdog.exe
    (scraper.exe must be in the same directory or configured via config)
─────────────────────────────────────────────────────────────────────
"""

import json
import logging
import logging.handlers
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Resolve paths relative to the executable / script location ────
# When running as a PyInstaller .exe, sys._MEIPASS is the temp extract dir,
# but we want paths relative to where the .exe actually sits on disk.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_PATH = BASE_DIR / "config" / "config.json"


# ═══════════════════════════════════════════════════════════════════
#  CONFIGURATION LOADER
# ═══════════════════════════════════════════════════════════════════

def load_config(config_path: Path = CONFIG_PATH) -> dict:
    """Load and validate the config.json file."""
    if not config_path.exists():
        print(f"[FATAL] Config file not found: {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # ── Validate required keys ────────────────────────────────────
    required_keys = [
        "developer_id", "developer_email", "watchdog",
        "smtp", "logging",
    ]
    for key in required_keys:
        if key not in config:
            print(f"[FATAL] Missing required config key: '{key}'")
            sys.exit(1)

    return config


# ═══════════════════════════════════════════════════════════════════
#  LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════

def setup_logging(config: dict) -> logging.Logger:
    """
    Configure structured logging with both console and rotating file output.
    """
    log_cfg = config["logging"]
    log_dir = BASE_DIR / log_cfg.get("local_log_dir", "./logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("watchdog")
    logger.setLevel(getattr(logging, log_cfg.get("level", "INFO").upper()))

    fmt = logging.Formatter(
        log_cfg.get(
            "log_format",
            "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
        )
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # Rotating file handler
    log_file = log_dir / "watchdog.log"
    max_bytes = log_cfg.get("max_log_size_mb", 50) * 1024 * 1024
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=log_cfg.get("backup_count", 5),
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


# ═══════════════════════════════════════════════════════════════════
#  WEBHOOK NOTIFIER
# ═══════════════════════════════════════════════════════════════════

def send_email_alert(
    config: dict,
    event: str,
    message: str,
    logger: logging.Logger,
    extra: dict | None = None,
):
    """
    Send an email alert using the engine.notifier module.
    This is fire-and-forget to avoid cascading failures.
    """
    from engine.notifier import EmailNotifier
    try:
        notifier = EmailNotifier(config)
        notifier.send(event, message, source="watchdog", extra=extra)
    except Exception as exc:
        logger.error("Failed to send email alert: %s", exc)


# ═══════════════════════════════════════════════════════════════════
#  WATCHDOG CORE
# ═══════════════════════════════════════════════════════════════════

class Watchdog:
    """
    Process supervisor that launches, monitors, and restarts scraper.exe.

    Lifecycle:
        1. Start scraper as a subprocess
        2. Poll process health every `health_check_interval_seconds`
        3. If process exits:
           a. Exit code 0 → graceful shutdown, do not restart
           b. Exit code != 0 → crash, restart + notify webhook
        4. If restart budget exhausted → send fatal alert + exit
    """

    def __init__(self, config: dict, logger: logging.Logger):
        self._config = config
        self._logger = logger

        wd_cfg = config.get("watchdog", {})
        self._health_interval = wd_cfg.get("health_check_interval_seconds", 30)
        self._max_restarts = wd_cfg.get("max_restart_attempts", 5)
        self._restart_cooldown = wd_cfg.get("restart_cooldown_seconds", 10)

        # Resolve scraper executable path
        scraper_name = wd_cfg.get("scraper_executable", "scraper.exe")
        self._scraper_path = BASE_DIR / scraper_name

        # If running in dev mode (not frozen), run scraper.py via Python
        if not getattr(sys, "frozen", False):
            self._scraper_cmd = [sys.executable, str(BASE_DIR / "scraper.py")]
        else:
            self._scraper_cmd = [str(self._scraper_path)]

        self._process: subprocess.Popen | None = None
        self._restart_count = 0
        self._running = True
        self._total_crashes = 0

    # ── Process Management ────────────────────────────────────────

    def _start_scraper(self) -> bool:
        """
        Launch the scraper as a child process.
        Returns True if launch succeeded, False otherwise.
        """
        try:
            self._logger.info(
                "Launching scraper: %s", " ".join(self._scraper_cmd)
            )
            self._process = subprocess.Popen(
                self._scraper_cmd,
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                # Ensure child gets its own process group for clean termination
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )
            self._logger.info(
                "Scraper launched successfully (PID=%d)", self._process.pid
            )
            return True

        except FileNotFoundError:
            self._logger.critical(
                "Scraper executable not found at: %s",
                " ".join(self._scraper_cmd),
            )
            return False

        except Exception as exc:
            self._logger.critical(
                "Failed to launch scraper: %s", exc, exc_info=True
            )
            return False

    def _stop_scraper(self):
        """Gracefully terminate the scraper process."""
        if self._process is None:
            return

        self._logger.info("Sending termination signal to scraper (PID=%d)...",
                          self._process.pid)
        try:
            if sys.platform == "win32":
                # On Windows, send CTRL_BREAK_EVENT to the process group
                self._process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self._process.terminate()

            # Wait up to 30 seconds for graceful shutdown
            try:
                self._process.wait(timeout=30)
                self._logger.info("Scraper exited gracefully.")
            except subprocess.TimeoutExpired:
                self._logger.warning(
                    "Scraper did not exit within 30s — force killing."
                )
                self._process.kill()
                self._process.wait(timeout=5)

        except Exception as exc:
            self._logger.error("Error during scraper shutdown: %s", exc)
            try:
                self._process.kill()
            except Exception:
                pass

    def _is_alive(self) -> bool:
        """Check if the scraper process is still running."""
        if self._process is None:
            return False
        return self._process.poll() is None

    def _get_exit_info(self) -> dict:
        """Get diagnostic info about a crashed scraper."""
        if self._process is None:
            return {}

        exit_code = self._process.returncode
        info = {
            "pid": self._process.pid,
            "exit_code": exit_code,
            "exit_meaning": self._interpret_exit_code(exit_code),
        }

        # Try to capture last few lines of output for diagnostics
        try:
            if self._process.stdout and self._process.stdout.readable():
                remaining = self._process.stdout.read()
                if remaining:
                    last_lines = remaining.decode("utf-8", errors="replace")
                    # Keep only the last 500 chars to avoid huge payloads
                    info["last_output"] = last_lines[-500:]
        except Exception:
            pass

        return info

    @staticmethod
    def _interpret_exit_code(code: int | None) -> str:
        """Provide a human-readable interpretation of common exit codes."""
        if code is None:
            return "Process still running"
        if code == 0:
            return "Clean exit"
        if code == 1:
            return "General error / unhandled exception"
        if code == -9 or code == 137:
            return "SIGKILL — likely OOM killed"
        if code == -15 or code == 143:
            return "SIGTERM — terminated by signal"
        # Windows-specific: negative codes are unsigned 32-bit status codes
        if code < 0:
            return f"Windows exception (0x{code & 0xFFFFFFFF:08X})"
        return f"Unknown exit code: {code}"

    # ── Main Loop ─────────────────────────────────────────────────

    def run(self):
        """
        Main watchdog loop:
          1. Launch scraper
          2. Monitor health
          3. Restart on crash (up to budget)
          4. Alert on failures
        """
        self._logger.info("=" * 65)
        self._logger.info("WATCHDOG STARTED")
        self._logger.info(
            "  Developer:          %s", self._config.get("developer_id")
        )
        self._logger.info(
            "  Scraper:            %s", " ".join(self._scraper_cmd)
        )
        self._logger.info(
            "  Health check:       every %ds", self._health_interval
        )
        self._logger.info(
            "  Max restarts:       %d", self._max_restarts
        )
        self._logger.info("=" * 65)

        # Initial launch
        if not self._start_scraper():
            send_email_alert(
                self._config, "fatal_launch_failure",
                "Watchdog could not find or launch scraper.exe. "
                "Manual intervention required.",
                self._logger,
            )
            return

        # ── Health monitoring loop ────────────────────────────────
        while self._running:
            try:
                time.sleep(self._health_interval)
            except (KeyboardInterrupt, SystemExit):
                self._logger.info("Watchdog received shutdown signal.")
                self._running = False
                break

            if not self._running:
                break

            # ── Check if scraper is still alive ───────────────────
            if self._is_alive():
                continue  # All good, keep monitoring

            # ── Scraper has exited ────────────────────────────────
            exit_info = self._get_exit_info()
            exit_code = exit_info.get("exit_code")

            # Graceful exit (code 0) — do not restart
            if exit_code == 0:
                self._logger.info(
                    "Scraper exited cleanly (code 0). "
                    "Watchdog will NOT restart it."
                )
                send_email_alert(
                    self._config, "scraper_clean_exit",
                    "Scraper exited with code 0 (clean shutdown).",
                    self._logger,
                    extra=exit_info,
                )
                break

            # ── Crash detected ────────────────────────────────────
            self._total_crashes += 1
            self._restart_count += 1
            self._logger.error(
                "SCRAPER CRASHED (crash #%d) — %s",
                self._total_crashes,
                json.dumps(exit_info, indent=2),
            )

            # Notify webhook on every crash
            send_email_alert(
                self._config, "scraper_crash",
                f"Scraper crashed (crash #{self._total_crashes}). "
                f"Exit code: {exit_code} "
                f"({exit_info.get('exit_meaning', 'unknown')}). "
                f"Restart attempt {self._restart_count}/{self._max_restarts}.",
                self._logger,
                extra=exit_info,
            )

            # ── Check restart budget ──────────────────────────────
            if self._restart_count > self._max_restarts:
                self._logger.critical(
                    "RESTART BUDGET EXHAUSTED (%d/%d). "
                    "Watchdog is shutting down. Manual intervention required.",
                    self._restart_count - 1,
                    self._max_restarts,
                )
                send_email_alert(
                    self._config, "fatal_restart_budget_exhausted",
                    f"Scraper has crashed {self._total_crashes} times. "
                    f"Restart budget of {self._max_restarts} exhausted. "
                    "Watchdog is shutting down. MANUAL INTERVENTION REQUIRED.",
                    self._logger,
                    extra={
                        "total_crashes": self._total_crashes,
                        "max_restarts": self._max_restarts,
                    },
                )
                break

            # ── Wait cooldown, then restart ───────────────────────
            self._logger.info(
                "Waiting %ds before restart attempt %d/%d...",
                self._restart_cooldown,
                self._restart_count,
                self._max_restarts,
            )
            time.sleep(self._restart_cooldown)

            if not self._start_scraper():
                self._logger.critical(
                    "Failed to restart scraper. Watchdog exiting."
                )
                send_email_alert(
                    self._config, "fatal_restart_failure",
                    "Watchdog failed to restart scraper after crash. "
                    "Manual intervention required.",
                    self._logger,
                )
                break

            self._logger.info(
                "Scraper restarted successfully (attempt %d/%d).",
                self._restart_count,
                self._max_restarts,
            )

        # ── Cleanup ───────────────────────────────────────────────
        self._stop_scraper()
        self._logger.info("Watchdog shutdown complete.")

    def shutdown(self):
        """Signal the watchdog to stop gracefully."""
        self._logger.info("Shutdown requested.")
        self._running = False


# ═══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════

def main():
    # 1. Load configuration
    config = load_config()

    # 2. Setup logging
    logger = setup_logging(config)

    # 3. Activate Windows sleep prevention
    from engine.sleep_prevention import SleepPrevention

    with SleepPrevention():
        logger.info("Windows sleep prevention active.")

        # 4. Create and register the watchdog
        watchdog = Watchdog(config, logger)

        # 5. Register signal handlers for graceful shutdown
        def _signal_handler(signum, frame):
            logger.info(
                "Received signal %d — initiating graceful shutdown...", signum
            )
            watchdog.shutdown()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        if sys.platform == "win32":
            signal.signal(signal.SIGBREAK, _signal_handler)

        # 6. Run the watchdog loop
        logger.info("Starting Watchdog supervisor...")
        watchdog.run()

    logger.info("Process fully terminated.")


if __name__ == "__main__":
    main()
