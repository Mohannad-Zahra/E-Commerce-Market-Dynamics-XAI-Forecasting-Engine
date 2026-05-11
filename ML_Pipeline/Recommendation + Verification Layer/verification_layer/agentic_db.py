"""
agentic_db.py
=============
SQLite persistence layer for the Agentic ReAct Framework.
Manages the agentic_react.db database with tables for:
  - ingested_batches: rows processed by the system (tracks toward 10K retrain threshold)
  - dlq_outcomes: approve/reject decisions from Zone 5 human review
  - retrain_log: history of retrain events with metrics
  - drift_snapshots: drift signal history for Zone 6 visualization
"""

import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AgenticDB")

_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(_DIR, "agentic_react.db")


# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------
def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ---------------------------------------------------------------------------
# Schema initialization
# ---------------------------------------------------------------------------
def init_agentic_db() -> None:
    """Create all required tables if they don't exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS ingested_batches (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id          TEXT    NOT NULL,
        raw_title           TEXT,
        category            TEXT,
        current_price       REAL,
        forecasted_price    REAL,
        price_14d_avg       REAL,
        volatility_score    REAL,
        months_since_release REAL,
        r_score             REAL,
        routing_path        TEXT,
        intelligent_score   REAL,
        signals_json        TEXT,
        shap_drivers_json   TEXT,
        batch_id            TEXT,
        ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS dlq_outcomes (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id          TEXT    NOT NULL,
        raw_title           TEXT,
        routing_path        TEXT,
        intelligent_score   REAL,
        signals_json        TEXT,
        shap_vector_json    TEXT,
        decision            TEXT    NOT NULL CHECK(decision IN ('approved', 'rejected')),
        decided_by          TEXT    DEFAULT 'human',
        decided_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS retrain_log (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        trigger_reason      TEXT    NOT NULL,
        rows_since_last     INTEGER,
        fpc_before          REAL,
        fpc_after           REAL,
        n_clusters          INTEGER,
        faiss_size_before   INTEGER,
        faiss_size_after    INTEGER,
        signal_1_value      REAL,
        signal_2_value      REAL,
        duration_seconds    REAL,
        retrained_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS drift_snapshots (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_1_triggered  INTEGER,
        signal_1_median_gap REAL,
        signal_1_degradation REAL,
        signal_2_triggered  INTEGER,
        signal_2_distance   REAL,
        overall_drift       INTEGER,
        batch_size          INTEGER,
        snapshot_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_ingested_product ON ingested_batches(product_id);
    CREATE INDEX IF NOT EXISTS idx_ingested_batch ON ingested_batches(batch_id);
    CREATE INDEX IF NOT EXISTS idx_ingested_date ON ingested_batches(ingested_at);
    CREATE INDEX IF NOT EXISTS idx_dlq_product ON dlq_outcomes(product_id);
    CREATE INDEX IF NOT EXISTS idx_dlq_decision ON dlq_outcomes(decision);
    CREATE INDEX IF NOT EXISTS idx_retrain_date ON retrain_log(retrained_at);
    CREATE INDEX IF NOT EXISTS idx_drift_date ON drift_snapshots(snapshot_at);
    """
    conn = None
    try:
        conn = _get_conn()
        conn.executescript(schema)
        conn.commit()
        logger.info(f"Agentic DB initialized: {DB_FILE}")
    except sqlite3.Error as e:
        logger.error(f"init_agentic_db failed: {e}")
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Ingested Batches
# ---------------------------------------------------------------------------
def insert_ingested_rows(rows: List[Dict[str, Any]], batch_id: str = None) -> int:
    """Insert processed candidate rows. Returns count of rows inserted."""
    if not batch_id:
        batch_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    query = """
        INSERT INTO ingested_batches
            (product_id, raw_title, category, current_price, forecasted_price,
             price_14d_avg, volatility_score, months_since_release, r_score,
             routing_path, intelligent_score, signals_json, shap_drivers_json, batch_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = None
    count = 0
    try:
        conn = _get_conn()
        for row in rows:
            params = (
                row.get("model_id", row.get("product_id", "unknown")),
                row.get("product_title", row.get("raw_title", "")),
                row.get("category", ""),
                row.get("current_price"),
                row.get("forecasted_price"),
                row.get("price_14d_avg"),
                row.get("volatility_score"),
                row.get("months_since_release"),
                row.get("r_score"),
                row.get("routing_path", ""),
                row.get("intelligent_score"),
                json.dumps(row.get("signals", {})),
                json.dumps(row.get("shap_drivers", {})),
                batch_id,
            )
            conn.execute(query, params)
            count += 1
        conn.commit()
        return count
    except sqlite3.Error as e:
        logger.error(f"insert_ingested_rows failed: {e}")
        if conn:
            conn.rollback()
        return count
    finally:
        if conn:
            conn.close()


def get_rows_since_last_retrain() -> int:
    """Count ingested rows since the last retrain event."""
    conn = None
    try:
        conn = _get_conn()
        # Find the last retrain timestamp
        last_retrain = conn.execute(
            "SELECT MAX(retrained_at) FROM retrain_log"
        ).fetchone()[0]
        
        if last_retrain:
            count = conn.execute(
                "SELECT COUNT(*) FROM ingested_batches WHERE ingested_at > ?",
                (last_retrain,)
            ).fetchone()[0]
        else:
            count = conn.execute(
                "SELECT COUNT(*) FROM ingested_batches"
            ).fetchone()[0]
        return count
    except sqlite3.Error as e:
        logger.error(f"get_rows_since_last_retrain failed: {e}")
        return 0
    finally:
        if conn:
            conn.close()


def get_total_ingested_count() -> int:
    """Return total number of ingested rows."""
    conn = None
    try:
        conn = _get_conn()
        return conn.execute("SELECT COUNT(*) FROM ingested_batches").fetchone()[0]
    except sqlite3.Error as e:
        return 0
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# DLQ Outcomes
# ---------------------------------------------------------------------------
def save_dlq_decision(candidate: Dict[str, Any], decision: str) -> bool:
    """Record an approve/reject decision for a DLQ candidate."""
    query = """
        INSERT INTO dlq_outcomes
            (product_id, raw_title, routing_path, intelligent_score,
             signals_json, shap_vector_json, decision)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    shap_vector = candidate.get("shap_vector")
    if shap_vector is not None:
        import numpy as np
        shap_vector = shap_vector.tolist() if isinstance(shap_vector, np.ndarray) else shap_vector
    
    params = (
        candidate.get("model_id", "unknown"),
        candidate.get("product_title", ""),
        candidate.get("routing_path", ""),
        candidate.get("intelligent_score"),
        json.dumps(candidate.get("signals", {})),
        json.dumps(shap_vector) if shap_vector else "[]",
        decision,
    )
    conn = None
    try:
        conn = _get_conn()
        conn.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"save_dlq_decision failed: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_dlq_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent DLQ decisions."""
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM dlq_outcomes ORDER BY decided_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error(f"get_dlq_history failed: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_dlq_stats() -> Dict[str, int]:
    """Return approve/reject counts."""
    conn = None
    try:
        conn = _get_conn()
        approved = conn.execute(
            "SELECT COUNT(*) FROM dlq_outcomes WHERE decision='approved'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM dlq_outcomes WHERE decision='rejected'"
        ).fetchone()[0]
        return {"approved": approved, "rejected": rejected, "total": approved + rejected}
    except sqlite3.Error as e:
        return {"approved": 0, "rejected": 0, "total": 0}
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Retrain Log
# ---------------------------------------------------------------------------
def log_retrain_event(
    trigger_reason: str,
    rows_since_last: int = 0,
    fpc_before: float = 0.0,
    fpc_after: float = 0.0,
    n_clusters: int = 3,
    faiss_size_before: int = 0,
    faiss_size_after: int = 0,
    signal_1_value: float = 0.0,
    signal_2_value: float = 0.0,
    duration_seconds: float = 0.0,
) -> bool:
    """Record a retrain event with before/after metrics."""
    query = """
        INSERT INTO retrain_log
            (trigger_reason, rows_since_last, fpc_before, fpc_after, n_clusters,
             faiss_size_before, faiss_size_after, signal_1_value, signal_2_value,
             duration_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    conn = None
    try:
        conn = _get_conn()
        conn.execute(query, (
            trigger_reason, rows_since_last, fpc_before, fpc_after, n_clusters,
            faiss_size_before, faiss_size_after, signal_1_value, signal_2_value,
            duration_seconds,
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"log_retrain_event failed: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_retrain_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Return recent retrain events."""
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM retrain_log ORDER BY retrained_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        return []
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Drift Snapshots
# ---------------------------------------------------------------------------
def save_drift_snapshot(status: Dict[str, Any], batch_size: int = 0) -> bool:
    """Record a drift detection snapshot."""
    query = """
        INSERT INTO drift_snapshots
            (signal_1_triggered, signal_1_median_gap, signal_1_degradation,
             signal_2_triggered, signal_2_distance, overall_drift, batch_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    s1 = status.get("signal_1", {})
    s2 = status.get("signal_2", {})
    conn = None
    try:
        conn = _get_conn()
        conn.execute(query, (
            int(s1.get("triggered", False)),
            s1.get("median_gap", 0.0),
            s1.get("degradation", 0.0),
            int(s2.get("triggered", False)),
            s2.get("centroid_distance", 0.0),
            int(status.get("overall_drift", False)),
            batch_size,
        ))
        conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error(f"save_drift_snapshot failed: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_drift_history(limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent drift snapshots."""
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM drift_snapshots ORDER BY snapshot_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        return []
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
# Auto-initialize on import
init_agentic_db()
