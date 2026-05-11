"""
engine/transport.py
─────────────────────────────────────────────────────────────────────
Cloud data transport layer with retry logic and store-and-forward.

Responsibilities:
  1. Upload cycle data (list of Bronze records) to GCP Cloud Storage.
  2. On failure: retry exactly 3 times at 1-minute intervals.
  3. If all retries fail: fire a webhook alert and buffer locally.
  4. On startup: check the buffer directory for un-uploaded data
     and attempt to flush it before starting a new cycle.

This module abstracts the cloud backend so the scraper only calls:
    transport.upload_cycle_data(records, cycle_id)

Note: In development/testing mode (when GCP credentials are unavailable),
the transport falls back to local-only mode and logs a warning.
─────────────────────────────────────────────────────────────────────
"""

import json
import logging
import os
import time as time_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("engine.transport")


class CloudTransport:
    """
    Manages data upload to GCP with retry logic and local buffering.

    Upload flow:
        1. Try GCP upload
        2. On failure → retry up to max_retries at retry_interval
        3. If exhausted → save to buffer dir + webhook alert
        4. On next cycle → attempt to flush buffer first

    Usage:
        transport = CloudTransport(config, notifier)
        success = transport.upload_cycle_data(records, cycle_id, "2b_egypt")
    """

    def __init__(self, config: dict, notifier=None):
        """
        Args:
            config:   Full config dict from config.json.
            notifier: Optional EmailNotifier instance for failure alerts.
        """
        retry_cfg = config.get("cloud_retry", {})
        self._max_retries = retry_cfg.get("max_retries", 3)
        self._retry_interval = retry_cfg.get("retry_interval_seconds", 60)

        gdrive_cfg = config.get("google_drive", {})
        self._folder_id = gdrive_cfg.get("folder_id", "")
        self._credentials_path = gdrive_cfg.get("credentials_path", "")

        db_cfg = config.get("database", {})
        self._buffer_dir = Path(db_cfg.get("buffer_dir", "./data/buffer"))
        self._buffer_dir.mkdir(parents=True, exist_ok=True)

        self._notifier = notifier
        self._drive_service = None
        self._drive_available = False

        # Try to initialize Drive client
        self._init_drive_client()

    def _init_drive_client(self):
        """
        Attempt to initialize the Google Drive API client using OAuth 2.0 Desktop Flow.
        Falls back to local-only mode if credentials are unavailable.
        """
        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            token_path = os.path.join(os.path.dirname(self._credentials_path), "token.json")
            creds = None

            if os.path.exists(token_path):
                creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/drive.file'])

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if self._credentials_path and os.path.exists(self._credentials_path):
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self._credentials_path, ['https://www.googleapis.com/auth/drive.file'])
                        logger.info("Opening browser for Google Drive OAuth login...")
                        creds = flow.run_local_server(port=0)
                    else:
                        logger.warning(
                            "OAuth credentials file not found at %s. "
                            "Running in LOCAL-ONLY mode — data will be buffered to disk.",
                            self._credentials_path
                        )
                        return

                with open(token_path, 'w') as token:
                    token.write(creds.to_json())

            self._drive_service = build('drive', 'v3', credentials=creds)
            self._drive_available = True
            logger.info("Google Drive client initialized (OAuth) for folder: %s", self._folder_id)

        except ImportError:
            logger.warning(
                "google-api-python-client not installed. "
                "Running in LOCAL-ONLY mode — data will be buffered to disk."
            )
        except Exception as exc:
            logger.warning(
                "Google Drive client initialization failed: %s. "
                "Running in LOCAL-ONLY mode.",
                exc,
            )

    # ── Public API ────────────────────────────────────────────────

    def upload_cycle_data(
        self,
        records: list[dict],
        cycle_id: str,
        timestamp_utc: str | None = None,
    ) -> bool:
        """
        Upload a set of Bronze records to GCP Cloud Storage.

        Implements the mandatory retry logic:
          - 3 retries at 1-minute intervals
          - On exhaustion: buffer locally + webhook alert

        Args:
            records:       List of Bronze record dicts.
            cycle_id:      Unique cycle identifier (for file naming).
            timestamp_utc: ISO 8601 timestamp for the cycle.

        Returns:
            True if upload succeeded (including after retries), False if buffered.
        """
        if not records:
            logger.warning("No records to upload for cycle %s.", cycle_id)
            return True

        if timestamp_utc is None:
            timestamp_utc = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H-%M-%SZ"
            )

        # Group records by retailer for organized storage
        by_retailer: dict[str, list[dict]] = {}
        for r in records:
            rid = r.get("retailer_id", "unknown")
            by_retailer.setdefault(rid, []).append(r)

        all_success = True
        for retailer_id, retailer_records in by_retailer.items():
            blob_name = f"{retailer_id}/{timestamp_utc}_{cycle_id}.json"
            success = self._upload_with_retry(
                retailer_records, blob_name, retailer_id, cycle_id
            )
            if not success:
                all_success = False

        return all_success

    def flush_buffer(self) -> tuple[int, int]:
        """
        Attempt to upload any buffered (previously failed) data.
        Should be called at the start of each cycle.

        Returns:
            Tuple of (flushed_count, remaining_count).
        """
        buffer_files = list(self._buffer_dir.glob("*.json"))
        if not buffer_files:
            return 0, 0

        logger.info(
            "Found %d buffered files. Attempting to flush...",
            len(buffer_files),
        )

        flushed = 0
        for bf in buffer_files:
            try:
                with open(bf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                records = data.get("records", [])
                blob_name = data.get("blob_name", bf.stem + ".json")
                retailer_id = data.get("retailer_id", "unknown")

                success = self._do_upload(records, blob_name)
                if success:
                    bf.unlink()  # Delete buffer file on success
                    flushed += 1
                    logger.info("Flushed buffered file: %s", bf.name)
                else:
                    logger.warning("Buffer flush failed for: %s", bf.name)

            except Exception as exc:
                logger.error(
                    "Error processing buffer file %s: %s", bf.name, exc
                )

        remaining = len(buffer_files) - flushed
        logger.info(
            "Buffer flush complete: %d flushed, %d remaining.",
            flushed,
            remaining,
        )
        return flushed, remaining

    def get_buffer_count(self) -> int:
        """Count the number of buffered (un-uploaded) files."""
        return len(list(self._buffer_dir.glob("*.json")))

    # ── Internal Methods ──────────────────────────────────────────

    def _upload_with_retry(
        self,
        records: list[dict],
        blob_name: str,
        retailer_id: str,
        cycle_id: str,
    ) -> bool:
        """
        Upload with the mandatory retry logic:
          - Try once (initial attempt)
          - On failure: retry exactly 3 times at 1-minute intervals
          - On exhaustion: buffer locally + webhook alert
        """
        # Initial attempt
        if self._do_upload(records, blob_name):
            logger.info(
                "Upload success: %s (%d records)", blob_name, len(records)
            )
            return True

        # Retry loop: exactly 3 retries at 1-minute intervals
        last_error = "Initial upload failed"
        for attempt in range(1, self._max_retries + 1):
            logger.warning(
                "Upload retry %d/%d for %s in %ds...",
                attempt,
                self._max_retries,
                blob_name,
                self._retry_interval,
            )

            # Notify on first failure
            if attempt == 1 and self._notifier:
                self._notifier.notify_upload_failure(
                    retailer_id, attempt, self._max_retries, last_error,
                    cycle_id=cycle_id, blob_name=blob_name
                )

            time_module.sleep(self._retry_interval)

            if self._do_upload(records, blob_name):
                logger.info(
                    "Upload succeeded on retry %d: %s", attempt, blob_name
                )
                return True

            last_error = f"Retry {attempt} failed"
            if self._notifier:
                self._notifier.notify_upload_failure(
                    retailer_id, attempt, self._max_retries, last_error,
                    cycle_id=cycle_id, blob_name=blob_name
                )

        # All retries exhausted → buffer locally
        logger.error(
            "ALL %d retries exhausted for %s. Buffering locally.",
            self._max_retries,
            blob_name,
        )

        self._save_to_buffer(records, blob_name, retailer_id, cycle_id)

        if self._notifier:
            self._notifier.notify_upload_exhausted(
                retailer_id,
                last_error,
                cycle_id=cycle_id,
                blob_name=blob_name,
                record_count=len(records),
            )

        return False

    def _do_upload(self, records: list[dict], blob_name: str) -> bool:
        """
        Execute the actual upload to Google Drive.
        Returns True on success, False on failure.
        """
        if not self._drive_available:
            logger.debug(
                "Google Drive not available — upload skipped for %s", blob_name
            )
            return False

        try:
            from googleapiclient.http import MediaIoBaseUpload
            import io

            # In GDrive, replacing / with _ gives a flat filename, e.g. "retailer_id_date_cycle.json"
            filename = blob_name.replace("/", "_")

            file_metadata = {
                'name': filename
            }
            if self._folder_id and self._folder_id != "YOUR_FOLDER_ID":
                file_metadata['parents'] = [self._folder_id]

            # JSON Lines format: one JSON object per line
            data = "\n".join(json.dumps(r) for r in records)
            
            # We encode the string to bytes for MediaIoBaseUpload
            media = MediaIoBaseUpload(io.BytesIO(data.encode('utf-8')), mimetype='application/json', resumable=True)

            self._drive_service.files().create(
                body=file_metadata, media_body=media, fields='id').execute()

            logger.info(
                "Google Drive upload complete: %s (%d records)",
                filename,
                len(records),
            )
            return True

        except Exception as exc:
            logger.error("Google Drive upload failed for %s: %s", blob_name, exc)
            return False

    def _save_to_buffer(
        self,
        records: list[dict],
        blob_name: str,
        retailer_id: str,
        cycle_id: str,
    ):
        """
        Save failed upload data to the local buffer for future retry.
        """
        buffer_filename = (
            f"{retailer_id}_{cycle_id}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        )
        buffer_path = self._buffer_dir / buffer_filename

        buffer_data = {
            "retailer_id": retailer_id,
            "cycle_id": cycle_id,
            "blob_name": blob_name,
            "buffered_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(records),
            "records": records,
        }

        try:
            with open(buffer_path, "w", encoding="utf-8") as f:
                json.dump(buffer_data, f, ensure_ascii=False, indent=2)
            logger.info(
                "Data buffered locally: %s (%d records)",
                buffer_path,
                len(records),
            )
        except Exception as exc:
            logger.critical(
                "CRITICAL: Failed to buffer data locally! "
                "Data may be lost. Error: %s",
                exc,
            )
