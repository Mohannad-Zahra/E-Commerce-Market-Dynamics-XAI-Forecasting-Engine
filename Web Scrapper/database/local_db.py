"""
database/local_db.py
─────────────────────────────────────────────────────────────────────
SQLite per-cycle database manager.

Each scrape cycle creates a brand new SQLite file as a local backup.
After the cycle completes, the data is appended to the cloud database.
The local file is NEVER deleted — it serves as a permanent backup.

Schema mirrors the Bronze layer:
  - scrape_timestamp (TEXT, ISO 8601 UTC)
  - retailer_id (TEXT)
  - raw_title (TEXT)
  - raw_current_price (TEXT)
  - raw_original_price (TEXT, nullable)
  - availability_text (TEXT, nullable)
  - product_url (TEXT)
  - extra_data (TEXT, JSON blob for any additional fields)

File naming: {cycle_db_dir}/{YYYY-MM-DDTHH-MM-SSZ}_{cycle_id}.db
─────────────────────────────────────────────────────────────────────
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("database.local_db")

# ── Bronze schema column definitions ─────────────────────────────

BRONZE_COLUMNS = [
    "scrape_timestamp",
    "retailer_id",
    "raw_title",
    "raw_current_price",
    "raw_original_price",
    "availability_text",
    "product_url",
    "category",
    "sub_category",
]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS bronze_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_timestamp TEXT NOT NULL,
    retailer_id     TEXT NOT NULL,
    raw_title       TEXT NOT NULL,
    raw_current_price TEXT NOT NULL,
    raw_original_price TEXT,
    availability_text TEXT,
    product_url     TEXT NOT NULL,
    category        TEXT NOT NULL,
    sub_category    TEXT,
    extra_data      TEXT,
    inserted_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_retailer_timestamp
    ON bronze_records (retailer_id, scrape_timestamp);
"""


class CycleDatabase:
    """
    Manages a single SQLite database file for one scrape cycle.

    Lifecycle:
        1. CycleDatabase is created → new .db file on disk
        2. Records are inserted via insert_records()
        3. All records are read via get_all_records() for cloud upload
        4. The .db file is KEPT on disk as a permanent backup

    Usage:
        with CycleDatabase(cycle_dir="./data/cycles") as db:
            db.insert_records(records)
            all_data = db.get_all_records()
    """

    def __init__(self, cycle_dir: str | Path, cycle_timestamp: datetime | None = None):
        """
        Args:
            cycle_dir: Directory where cycle .db files are stored.
            cycle_timestamp: UTC timestamp for this cycle.
                             Defaults to now().
        """
        self._cycle_dir = Path(cycle_dir)
        self._cycle_dir.mkdir(parents=True, exist_ok=True)

        if cycle_timestamp is None:
            cycle_timestamp = datetime.now(timezone.utc)

        self._cycle_id = uuid.uuid4().hex[:8]
        self._timestamp = cycle_timestamp

        # Build filename: 2026-04-05T00-00-00Z_a1b2c3d4.db
        ts_str = cycle_timestamp.strftime("%Y-%m-%dT%H-%M-%SZ")
        self._db_filename = f"{ts_str}_{self._cycle_id}.db"
        self._db_path = self._cycle_dir / self._db_filename

        self._conn: sqlite3.Connection | None = None
        self._record_count = 0

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite file."""
        return self._db_path

    @property
    def cycle_id(self) -> str:
        """Unique identifier for this cycle."""
        return self._cycle_id

    @property
    def record_count(self) -> int:
        """Number of records inserted so far."""
        return self._record_count

    # ── Context Manager ───────────────────────────────────────────

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def open(self):
        """Open the SQLite connection and create the schema."""
        logger.info("Creating cycle database: %s", self._db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(CREATE_TABLE_SQL)
        self._conn.execute(CREATE_INDEX_SQL)
        self._conn.commit()
        logger.info("Cycle database ready: %s", self._db_filename)

    def close(self):
        """Close the SQLite connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info(
                "Cycle database closed: %s (%d records)",
                self._db_filename,
                self._record_count,
            )

    # ── Record Operations ─────────────────────────────────────────

    def validate_record(self, record: dict) -> tuple[bool, str]:
        """
        Validate a single record against the Bronze schema.

        Returns:
            Tuple of (is_valid, error_message).
        """
        required_fields = [
            "scrape_timestamp", "retailer_id", "raw_title",
            "raw_current_price", "product_url", "category",
        ]
        for field in required_fields:
            if field not in record or not record[field]:
                return False, f"Missing or empty required field: '{field}'"
        return True, ""

    def insert_records(self, records: list[dict]) -> tuple[int, int]:
        """
        Insert multiple Bronze records into the cycle database.

        Records that fail validation are skipped and logged.

        Args:
            records: List of dicts, each containing Bronze schema fields.

        Returns:
            Tuple of (inserted_count, skipped_count).
        """
        if self._conn is None:
            raise RuntimeError("Database is not open. Use 'with' or call open().")

        inserted = 0
        skipped = 0

        for i, record in enumerate(records):
            is_valid, error = self.validate_record(record)
            if not is_valid:
                logger.warning(
                    "Skipping invalid record #%d: %s", i, error
                )
                skipped += 1
                continue

            # Extract known columns; everything else goes to extra_data
            extra = {
                k: v for k, v in record.items()
                if k not in BRONZE_COLUMNS
            }
            extra_json = json.dumps(extra) if extra else None

            try:
                self._conn.execute(
                    """
                    INSERT INTO bronze_records
                        (scrape_timestamp, retailer_id, raw_title,
                         raw_current_price, raw_original_price,
                         availability_text, product_url,
                         category, sub_category, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.get("scrape_timestamp"),
                        record.get("retailer_id"),
                        record.get("raw_title"),
                        record.get("raw_current_price"),
                        record.get("raw_original_price"),
                        record.get("availability_text"),
                        record.get("product_url"),
                        record.get("category"),
                        record.get("sub_category"),
                        extra_json,
                    ),
                )
                inserted += 1
            except sqlite3.Error as exc:
                logger.error(
                    "SQLite insert error for record #%d: %s", i, exc
                )
                skipped += 1

        self._conn.commit()
        self._record_count += inserted

        logger.info(
            "Inserted %d records, skipped %d (total in DB: %d)",
            inserted,
            skipped,
            self._record_count,
        )
        return inserted, skipped

    def get_all_records(self) -> list[dict]:
        """
        Read all records from the cycle database.
        Used for cloud upload after the cycle completes.

        Returns:
            List of dicts (one per record), including extra_data merged in.
        """
        if self._conn is None:
            raise RuntimeError("Database is not open. Use 'with' or call open().")

        cursor = self._conn.execute(
            """
            SELECT scrape_timestamp, retailer_id, raw_title,
                   raw_current_price, raw_original_price,
                   availability_text, product_url,
                   category, sub_category, extra_data
            FROM bronze_records
            ORDER BY id
            """
        )

        records = []
        for row in cursor:
            record = {
                "scrape_timestamp": row[0],
                "retailer_id": row[1],
                "raw_title": row[2],
                "raw_current_price": row[3],
                "raw_original_price": row[4],
                "availability_text": row[5],
                "product_url": row[6],
                "category": row[7],
                "sub_category": row[8],
            }
            # Merge extra_data back into the record
            if row[9]:
                try:
                    extra = json.loads(row[9])
                    record.update(extra)
                except json.JSONDecodeError:
                    pass
            records.append(record)

        return records

    def get_record_count(self) -> int:
        """Get the count of records in the database (from SQL)."""
        if self._conn is None:
            raise RuntimeError("Database is not open.")
        cursor = self._conn.execute("SELECT COUNT(*) FROM bronze_records")
        return cursor.fetchone()[0]

    def get_records_by_retailer(self, retailer_id: str) -> list[dict]:
        """Get all records for a specific retailer."""
        if self._conn is None:
            raise RuntimeError("Database is not open.")

        cursor = self._conn.execute(
            """
            SELECT scrape_timestamp, retailer_id, raw_title,
                   raw_current_price, raw_original_price,
                   availability_text, product_url,
                   category, sub_category, extra_data
            FROM bronze_records
            WHERE retailer_id = ?
            ORDER BY id
            """,
            (retailer_id,),
        )

        records = []
        for row in cursor:
            record = {
                "scrape_timestamp": row[0],
                "retailer_id": row[1],
                "raw_title": row[2],
                "raw_current_price": row[3],
                "raw_original_price": row[4],
                "availability_text": row[5],
                "product_url": row[6],
                "category": row[7],
                "sub_category": row[8],
            }
            if row[9]:
                try:
                    extra = json.loads(row[9])
                    record.update(extra)
                except json.JSONDecodeError:
                    pass
            records.append(record)

        return records
