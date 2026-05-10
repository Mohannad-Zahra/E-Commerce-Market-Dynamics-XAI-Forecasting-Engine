"""
database.py
===========
Simple SQLite persistence layer.

Tables
------
electronics_history   – raw candidate data ingested from recommendations.json
daily_recommendations – final processed recommendations with LLM explanations
subscribers           – users who opted in to daily laptop deal alerts
"""

import json
import logging
import sqlite3
from typing import Any, Dict, List

logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

DB_FILE = "laptops_data.db"

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# 1. init_db
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they do not already exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS electronics_history (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id            TEXT    NOT NULL,
        model               TEXT    NOT NULL,
        current_price       REAL,
        price_14d_avg       REAL,
        forecasted_price    REAL,
        r_score             REAL,
        classification      TEXT,
        confidence          TEXT,
        shap_drivers        TEXT,
        ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS daily_recommendations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id        TEXT    NOT NULL,
        model           TEXT    NOT NULL,
        r_score         REAL,
        classification  TEXT,
        confidence      TEXT,
        llm_explanation TEXT,
        recommended_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS subscribers (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        email       TEXT    NOT NULL UNIQUE,
        name        TEXT,
        category    TEXT    NOT NULL DEFAULT 'laptop',
        active      INTEGER NOT NULL DEFAULT 1,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_hist_model  ON electronics_history(model_id);
    CREATE INDEX IF NOT EXISTS idx_hist_date   ON electronics_history(ingested_at);
    CREATE INDEX IF NOT EXISTS idx_rec_model   ON daily_recommendations(model_id);
    CREATE INDEX IF NOT EXISTS idx_rec_score   ON daily_recommendations(r_score);
    CREATE INDEX IF NOT EXISTS idx_sub_cat     ON subscribers(category, active);
    """
    conn = None
    try:
        conn = _get_conn()
        conn.executescript(schema)
        conn.commit()
        print(f"[DB] Initialised database: {DB_FILE}")
    except sqlite3.Error as e:
        logging.error(f"init_db failed: {e}")
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 2. insert_laptop
# ---------------------------------------------------------------------------

def insert_laptop(candidate: Dict[str, Any]) -> bool:
    """
    Insert one candidate dict into electronics_history.
    Silently skips fields not present in the candidate.
    """
    query = """
        INSERT INTO electronics_history
            (model_id, model, current_price, price_14d_avg,
             forecasted_price, r_score, classification, confidence, shap_drivers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    shap_json = json.dumps(candidate.get("shap_drivers") or {})
    params = (
        candidate.get("model_id", "unknown"),
        candidate.get("model", "unknown"),
        candidate.get("current_price"),
        candidate.get("price_14d_avg"),
        candidate.get("forecasted_price"),
        candidate.get("r_score"),
        candidate.get("classification"),
        candidate.get("confidence"),
        shap_json,
    )
    conn = None
    try:
        conn = _get_conn()
        conn.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"insert_laptop failed for {candidate.get('model_id')}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# 3. save_recommendation
# ---------------------------------------------------------------------------

def save_recommendation(candidate: Dict[str, Any], llm_explanation: str) -> bool:
    """
    Persist a final recommendation + its LLM explanation into daily_recommendations.
    """
    query = """
        INSERT INTO daily_recommendations
            (model_id, model, r_score, classification, confidence, llm_explanation)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    params = (
        candidate.get("model_id", "unknown"),
        candidate.get("model", "unknown"),
        candidate.get("r_score"),
        candidate.get("classification"),
        candidate.get("confidence"),
        llm_explanation,
    )
    conn = None
    try:
        conn = _get_conn()
        conn.execute(query, params)
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"save_recommendation failed for {candidate.get('model_id')}: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Read helpers (optional, used for debugging / reporting)
# ---------------------------------------------------------------------------

def get_history(limit: int = 50) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM electronics_history ORDER BY ingested_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"get_history failed: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_recommendations(limit: int = 10) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM daily_recommendations ORDER BY r_score DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"get_recommendations failed: {e}")
        return []
    finally:
        if conn:
            conn.close()


# ---------------------------------------------------------------------------
# Subscriber helpers
# ---------------------------------------------------------------------------

def add_subscriber(email: str, name: str = "", category: str = "laptop") -> bool:
    """Register a new email subscriber for a given product category alert."""
    conn = None
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO subscribers (email, name, category) VALUES (?, ?, ?)",
            (email.lower().strip(), name, category),
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        logging.error(f"add_subscriber failed: {e}")
        return False
    finally:
        if conn:
            conn.close()


def get_laptop_subscribers() -> List[Dict[str, Any]]:
    """Return all active subscribers opted in for laptop alerts."""
    conn = None
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT email, name FROM subscribers WHERE category = 'laptop' AND active = 1"
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logging.error(f"get_laptop_subscribers failed: {e}")
        return []
    finally:
        if conn:
            conn.close()
