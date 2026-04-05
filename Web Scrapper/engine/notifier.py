"""
engine/notifier.py
─────────────────────────────────────────────────────────────────────
Email notification client for the scraper infrastructure.

Sends structured HTML email payloads to the team via SMTP.
"""

import json
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("engine.notifier")

class EmailNotifier:
    def __init__(self, config: dict):
        smtp_config = config.get("smtp", {})
        self._host = smtp_config.get("host", "smtp.gmail.com")
        self._port = smtp_config.get("port", 587)
        self._sender_email = smtp_config.get("sender_email", "")
        self._sender_password = smtp_config.get("sender_app_password", "")
        self._team_emails = smtp_config.get("team_emails", [])
        self._developer_id = config.get("developer_id", "unknown")
        self._machine_name = os.environ.get("COMPUTERNAME", "unknown")

        if not self._sender_password or self._sender_password == "YOUR_APP_PASSWORD_HERE":
            logger.warning("SMTP App Password is not configured. Alerts will be logged only.")

    def send(self, event: str, message: str, source: str = "scraper", extra: dict[str, Any] | None = None) -> bool:
        payload = {
            "source": source,
            "developer_id": self._developer_id,
            "machine_name": self._machine_name,
            "event": event,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            payload["details"] = extra

        if not self._sender_password or self._sender_password == "YOUR_APP_PASSWORD_HERE":
            logger.warning("[DRY RUN] Email alert (no password): %s | %s", message, json.dumps(payload, indent=2))
            return False

        if not self._team_emails:
            logger.warning("No team_emails configured. Skipping email alert.")
            return False

        try:
            msg = MIMEMultipart()
            msg["From"] = self._sender_email
            msg["To"] = ", ".join(self._team_emails)
            msg["Subject"] = f"[Alert] Scraper Event: {event} ({self._machine_name})"

            body = f"""
            <h2>E-Commerce Scraper Alert</h2>
            <p><strong>Event:</strong> {event}</p>
            <p><strong>Message:</strong> {message}</p>
            <p><strong>Source:</strong> {source}</p>
            <p><strong>Developer ID:</strong> {self._developer_id}</p>
            <p><strong>Machine:</strong> {self._machine_name}</p>
            <p><strong>Timestamp (UTC):</strong> {payload["timestamp_utc"]}</p>
            <pre>{json.dumps(extra or {}, indent=2)}</pre>
            """
            
            msg.attach(MIMEText(body, "html"))

            server = smtplib.SMTP(self._host, self._port, timeout=15)
            server.starttls()
            server.login(self._sender_email, self._sender_password)
            server.send_message(msg)
            server.quit()
            
            logger.info("Email alert sent successfully: event=%s", event)
            return True

        except Exception as exc:
            logger.error("SMTP error sending email for event=%s: %s", event, exc)
            return False

    def notify_scrape_failure(self, retailer_id: str, error_msg: str, **extra):
        self.send("scrape_failed", f"Scraping failed for '{retailer_id}': {error_msg}", extra={"retailer_id": retailer_id, **extra})

    def notify_upload_failure(self, retailer_id: str, attempt: int, max_attempts: int, error_msg: str):
        self.send("upload_retry_failed", f"Cloud upload for '{retailer_id}' failed (attempt {attempt}/{max_attempts}): {error_msg}", extra={"retailer_id": retailer_id, "attempt": attempt, "max_attempts": max_attempts})

    def notify_upload_exhausted(self, retailer_id: str, error_msg: str):
        self.send("upload_retry_exhausted", f"ALL upload retries exhausted for '{retailer_id}'. Data buffered locally. Last error: {error_msg}", extra={"retailer_id": retailer_id})

    def notify_cycle_complete(self, total_records: int, retailers_scraped: int, duration_seconds: float):
        self.send("cycle_complete", f"Scrape cycle complete: {total_records} records from {retailers_scraped} retailers in {duration_seconds:.1f}s.", extra={"total_records": total_records, "retailers_scraped": retailers_scraped, "duration_seconds": duration_seconds})

    def notify_missed_interval(self, missed_time: str, actual_time: str):
        self.send("missed_interval", f"Missed scheduled interval {missed_time}. Executing catch-up scrape at {actual_time}.", extra={"scheduled_utc": missed_time, "actual_utc": actual_time})
