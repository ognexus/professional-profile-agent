"""
loop.py — Feedback recording and retrieval for the self-improvement loop.

After every assessment or curation, the user can submit:
  - thumbs_up: bool
  - rating: int (1-5) per relevant dimension
  - comment: str (free text)

Top-rated past outputs are injected as few-shot examples in future prompts.
Thumbs-down outputs with comments are injected as "mistakes to avoid" cautions.

This is in-context learning — no fine-tuning, no model updates.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from app.core import storage

logger = logging.getLogger(__name__)

RecordType = Literal["assessment", "curation"]


def record_feedback(
    record_type: RecordType,
    record_id: int,
    thumbs_up: bool,
    ratings: dict[str, int] | None = None,
    comment: str = "",
    db_path: Path | None = None,
) -> None:
    """
    Persist user feedback for an assessment or curation result.

    Args:
        record_type: "assessment" or "curation"
        record_id: SQLite row id of the record
        thumbs_up: Overall positive/negative signal
        ratings: Optional per-dimension ratings (1-5), e.g. {"accuracy": 4, "usefulness": 5}
        comment: Free-text feedback
    """
    feedback = {
        "thumbs_up": thumbs_up,
        "ratings": ratings or {},
        "comment": comment,
    }

    if record_type == "assessment":
        storage.save_assessment_feedback(record_id, feedback, db_path)
    elif record_type == "curation":
        storage.save_cv_feedback(record_id, feedback, db_path)
    else:
        raise ValueError(f"Unknown record_type: {record_type}")

    logger.info(
        "Feedback recorded [type=%s, id=%d, thumbs_up=%s]",
        record_type,
        record_id,
        thumbs_up,
    )


def get_recent_high_quality_examples(
    record_type: RecordType,
    n: int = 3,
    min_rating: int = 4,
    db_path: Path | None = None,
) -> list[dict]:
    """
    Return the n most-recent records rated positively (thumbs up + avg rating >= min_rating).
    Used to inject as few-shot examples into the next prompt.

    Returns list of {"context": str, "result": dict}
    """
    if record_type == "assessment":
        records = storage.list_recent_assessments(n=50, db_path=db_path)
    else:
        records = storage.list_recent_cvs(n=50, db_path=db_path)

    good_examples = []
    for record in records:
        feedback = record.get("feedback_json")
        if not feedback:
            continue
        if not feedback.get("thumbs_up"):
            continue
        ratings = feedback.get("ratings", {})
        if ratings:
            avg_rating = sum(ratings.values()) / len(ratings)
            if avg_rating < min_rating:
                continue

        # Build context string from record
        if record_type == "assessment":
            context = _truncate(record.get("jd_text", ""), 300)
        else:
            context = _truncate(record.get("jd_text", ""), 300)

        good_examples.append({
            "context": context,
            "result": record.get("result_json", {}),
            "comment": feedback.get("comment", ""),
        })

        if len(good_examples) >= n:
            break

    return good_examples


def get_recent_corrections(
    record_type: RecordType,
    n: int = 3,
    db_path: Path | None = None,
) -> list[dict]:
    """
    Return the n most-recent records rated negatively (thumbs down) with comments.
    Used to inject as "mistakes to avoid" in the next prompt.

    Returns list of {"comment": str, "result": dict}
    """
    if record_type == "assessment":
        records = storage.list_recent_assessments(n=50, db_path=db_path)
    else:
        records = storage.list_recent_cvs(n=50, db_path=db_path)

    corrections = []
    for record in records:
        feedback = record.get("feedback_json")
        if not feedback:
            continue
        if feedback.get("thumbs_up"):
            continue  # Only collect negative feedback
        comment = feedback.get("comment", "").strip()
        if not comment:
            continue  # Only useful if the user explained what went wrong

        corrections.append({
            "comment": comment,
            "result": record.get("result_json", {}),
        })

        if len(corrections) >= n:
            break

    return corrections


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."
