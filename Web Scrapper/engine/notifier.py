"""
engine/notifier.py
─────────────────────────────────────────────────────────────────────
Email notification client for the scraper infrastructure.

Sends structured HTML email payloads to the team via SMTP.
"""

import json
import logging
import os
import html
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

    @staticmethod
    def _details_html(details: dict[str, Any]) -> str:
        if not details:
            return "<p><em>No additional details provided.</em></p>"
        rows = []
        for key, value in details.items():
            safe_key = html.escape(str(key))
            safe_value = html.escape(json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value))
            rows.append(f"<tr><td><strong>{safe_key}</strong></td><td>{safe_value}</td></tr>")
        table_rows = "".join(rows)
        return (
            "<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
            "<thead><tr><th>Field</th><th>Value</th></tr></thead>"
            f"<tbody>{table_rows}</tbody></table>"
        )

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
            details_block = self._details_html(extra or {})

            body = f"""
            <h2>E-Commerce Scraper Alert</h2>
            <p><strong>Event:</strong> {event}</p>
            <p><strong>Message:</strong> {message}</p>
            <p><strong>Source:</strong> {source}</p>
            <p><strong>Developer ID:</strong> {self._developer_id}</p>
            <p><strong>Machine:</strong> {self._machine_name}</p>
            <p><strong>Timestamp (UTC):</strong> {payload["timestamp_utc"]}</p>
            <h3>Details</h3>
            {details_block}
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

    def notify_scrape_failure(
        self,
        retailer_id: str,
        error_msg: str,
        retailer_name: str | None = None,
        payload_module: str | None = None,
        **extra,
    ):
        name = retailer_name or retailer_id
        details = {"retailer_id": retailer_id, "retailer_name": name}
        if payload_module:
            details["payload_module"] = payload_module
        details.update(extra)
        self.send("scrape_failed", f"Scraping failed for '{name}': {error_msg}", extra=details)

    def notify_upload_failure(
        self,
        retailer_id: str,
        attempt: int,
        max_attempts: int,
        error_msg: str,
        retailer_name: str | None = None,
        cycle_id: str | None = None,
        blob_name: str | None = None,
    ):
        name = retailer_name or retailer_id
        details = {
            "retailer_id": retailer_id,
            "retailer_name": name,
            "attempt": attempt,
            "max_attempts": max_attempts,
        }
        if cycle_id:
            details["cycle_id"] = cycle_id
        if blob_name:
            details["blob_name"] = blob_name
        self.send(
            "upload_retry_failed",
            f"Cloud upload for '{name}' failed (attempt {attempt}/{max_attempts}): {error_msg}",
            extra=details,
        )

    def notify_upload_exhausted(
        self,
        retailer_id: str,
        error_msg: str,
        retailer_name: str | None = None,
        cycle_id: str | None = None,
        blob_name: str | None = None,
        record_count: int | None = None,
    ):
        name = retailer_name or retailer_id
        details = {"retailer_id": retailer_id, "retailer_name": name}
        if cycle_id:
            details["cycle_id"] = cycle_id
        if blob_name:
            details["blob_name"] = blob_name
        if record_count is not None:
            details["record_count"] = record_count
        self.send(
            "upload_retry_exhausted",
            f"ALL upload retries exhausted for '{name}'. Data buffered locally. Last error: {error_msg}",
            extra=details,
        )

    def notify_cycle_complete(self, total_records: int, retailers_scraped: int, duration_seconds: float, retailer_names: list[str] | None = None):
        retailer_str = ", ".join(retailer_names) if retailer_names else "N/A"
        msg = f"Scrape cycle complete: {total_records} records from {retailers_scraped} retailers ({retailer_str}) in {duration_seconds:.1f}s."
        self.send("cycle_complete", msg, extra={
            "total_records": total_records,
            "retailers_scraped": retailers_scraped,
            "duration_seconds": duration_seconds,
            "retailers": retailer_names or []
        })

    def notify_missed_interval(self, missed_time: str, actual_time: str):
        self.send("missed_interval", f"Missed scheduled interval {missed_time}. Executing catch-up scrape at {actual_time}.", extra={"scheduled_utc": missed_time, "actual_utc": actual_time})
