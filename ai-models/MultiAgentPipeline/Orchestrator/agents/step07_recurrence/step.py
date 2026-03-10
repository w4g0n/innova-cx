"""
Step 5 — Recurrence Agent
=========================
Determines is_recurring using explicit state when available, otherwise a
lightweight text heuristic.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

from langchain_core.runnables import RunnableLambda

from db import db_connect

logger = logging.getLogger(__name__)

_RECURRING_PATTERNS = (
    r"\bagain\b",
    r"\brepeat(?:ed|ing)?\b",
    r"\brepeatedly\b",
    r"\bmultiple times\b",
    r"\bstill not fixed\b",
    r"\bnot the first time\b",
    r"\bfor weeks\b",
    r"\bfor months\b",
    r"\bfifth time\b",
    r"\bthird time\b",
    r"\bsecond time\b",
    r"\bcalled before\b",
    r"\breported (this )?before\b",
)
_RECURRING_REGEX = re.compile("|".join(_RECURRING_PATTERNS), re.IGNORECASE)


def _optional_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _find_similar_ticket(text: str, current_ticket_code: str | None) -> tuple[str | None, str | None, float]:
    query_text = str(text or "").strip().lower()
    if not query_text:
        return None, None, 0.0
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_code, subject, details
                    FROM tickets
                    WHERE (%s IS NULL OR ticket_code <> %s)
                    ORDER BY created_at DESC
                    LIMIT 120
                    """,
                    (current_ticket_code, current_ticket_code),
                )
                rows = cur.fetchall() or []
    except Exception:
        return None, None, 0.0

    best_code = None
    best_subject = None
    best_score = 0.0
    for row in rows:
        code = str(row[0] or "").strip()
        subject = str(row[1] or "").strip()
        subject_lc = subject.lower()
        details = str(row[2] or "").strip().lower()
        if not code or (not details and not subject_lc):
            continue
        details_score = SequenceMatcher(None, query_text, details).ratio() if details else 0.0
        subject_score = SequenceMatcher(None, query_text, subject_lc).ratio() if subject_lc else 0.0
        score = max(details_score, subject_score)
        if score > best_score:
            best_score = score
            best_code = code
            best_subject = subject
    # Keep threshold permissive so explainability can surface the linked prior ticket.
    if best_score < 0.25:
        return None, None, best_score
    return best_code, best_subject, best_score


async def check_recurrence(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("recurrence_check | skipped (label=%s)", state.get("label"))
        return state

    explicit = _optional_bool(state.get("is_recurring"))
    if explicit is not None:
        state["is_recurring"] = explicit
        state["is_recurring_source"] = "state"
        if explicit:
            similar_code, similar_subject, similar_score = _find_similar_ticket(
                str(state.get("text") or ""),
                str(state.get("ticket_id") or "").strip() or None,
            )
            state["similar_ticket_code"] = similar_code
            state["similar_ticket_subject"] = similar_subject
            state["similarity_score"] = round(float(similar_score), 3) if similar_score else None
            if similar_code:
                state["recurrence_reason"] = f"Matched similar prior ticket {similar_code}"
            else:
                state["recurrence_reason"] = "Marked recurring by upstream state"
        else:
            state["similar_ticket_code"] = None
            state["similar_ticket_subject"] = None
            state["similarity_score"] = None
            state["recurrence_reason"] = "No recurrence signal"
        logger.info(
            "recurrence_check | is_recurring=%s source=state",
            state["is_recurring"],
        )
        return state

    text = str(state.get("text") or "")
    recurring = bool(_RECURRING_REGEX.search(text))
    state["is_recurring"] = recurring
    state["is_recurring_source"] = "heuristic"
    similar_code = None
    similar_subject = None
    similar_score = 0.0
    if recurring:
        similar_code, similar_subject, similar_score = _find_similar_ticket(
            text,
            str(state.get("ticket_id") or "").strip() or None,
        )
    state["similar_ticket_code"] = similar_code
    state["similar_ticket_subject"] = similar_subject
    state["similarity_score"] = round(float(similar_score), 3) if similar_score else None
    if recurring and similar_code:
        state["recurrence_reason"] = f"Text matched recurrence pattern and similar ticket {similar_code}"
    elif recurring:
        state["recurrence_reason"] = "Text matched recurrence pattern"
    else:
        state["recurrence_reason"] = "No recurrence pattern found"
    logger.info(
        "recurrence_check | is_recurring=%s source=heuristic",
        state["is_recurring"],
    )
    return state


recurrence_step = RunnableLambda(check_recurrence)
