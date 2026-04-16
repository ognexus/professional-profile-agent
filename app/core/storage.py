"""
storage.py — SQLite persistence layer (no ORM, stdlib only).

Tables:
  assessments — candidate assessment results + feedback
  cvs         — CV curation results + feedback
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from app.config import settings


def _get_conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create tables if they don't already exist."""
    with _get_conn(db_path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS assessments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at      TEXT NOT NULL,
                jd_hash         TEXT NOT NULL,
                candidate_hash  TEXT NOT NULL,
                jd_text         TEXT NOT NULL,
                candidate_text  TEXT NOT NULL,
                result_json     TEXT NOT NULL,
                feedback_json   TEXT
            );

            CREATE TABLE IF NOT EXISTS cvs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at      TEXT NOT NULL,
                jd_hash         TEXT NOT NULL,
                source_hash     TEXT NOT NULL,
                jd_text         TEXT NOT NULL,
                cv_text         TEXT NOT NULL,
                linkedin_text   TEXT NOT NULL,
                result_json     TEXT NOT NULL,
                feedback_json   TEXT
            );
        """)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------


def save_assessment(
    jd_text: str,
    candidate_text: str,
    result: dict,
    db_path: Path | None = None,
) -> int:
    """Persist an assessment result. Returns the new row id."""
    init_db(db_path)
    with _get_conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO assessments
                (created_at, jd_hash, candidate_hash, jd_text, candidate_text, result_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                _sha256(jd_text),
                _sha256(candidate_text),
                jd_text,
                candidate_text,
                json.dumps(result),
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_assessment(record_id: int, db_path: Path | None = None) -> dict | None:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM assessments WHERE id = ?", (record_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_recent_assessments(n: int = 20, db_path: Path | None = None) -> list[dict]:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM assessments ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_assessment_feedback(
    record_id: int, feedback: dict, db_path: Path | None = None
) -> None:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        conn.execute(
            "UPDATE assessments SET feedback_json = ? WHERE id = ?",
            (json.dumps(feedback), record_id),
        )


# ---------------------------------------------------------------------------
# CVs
# ---------------------------------------------------------------------------


def save_cv(
    jd_text: str,
    cv_text: str,
    linkedin_text: str,
    result: dict,
    db_path: Path | None = None,
) -> int:
    init_db(db_path)
    source_hash = _sha256(cv_text + linkedin_text)
    with _get_conn(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO cvs
                (created_at, jd_hash, source_hash, jd_text, cv_text, linkedin_text, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _now(),
                _sha256(jd_text),
                source_hash,
                jd_text,
                cv_text,
                linkedin_text,
                json.dumps(result),
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def get_cv(record_id: int, db_path: Path | None = None) -> dict | None:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM cvs WHERE id = ?", (record_id,)
        ).fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def list_recent_cvs(n: int = 20, db_path: Path | None = None) -> list[dict]:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM cvs ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def save_cv_feedback(
    record_id: int, feedback: dict, db_path: Path | None = None
) -> None:
    init_db(db_path)
    with _get_conn(db_path) as conn:
        conn.execute(
            "UPDATE cvs SET feedback_json = ? WHERE id = ?",
            (json.dumps(feedback), record_id),
        )


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    for key in ("result_json", "feedback_json"):
        if d.get(key):
            d[key] = json.loads(d[key])
    return d
