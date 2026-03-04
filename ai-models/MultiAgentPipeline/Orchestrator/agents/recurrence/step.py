"""
Step 5 — Recurrence Agent
=========================
Determines is_recurring using explicit state when available, otherwise a
lightweight text heuristic.
"""

from __future__ import annotations

import logging
import re

from langchain_core.runnables import RunnableLambda

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


async def check_recurrence(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("recurrence_check | skipped (label=%s)", state.get("label"))
        return state

    explicit = _optional_bool(state.get("is_recurring"))
    if explicit is not None:
        state["is_recurring"] = explicit
        state["is_recurring_source"] = "state"
        logger.info(
            "recurrence_check | is_recurring=%s source=state",
            state["is_recurring"],
        )
        return state

    text = str(state.get("text") or "")
    state["is_recurring"] = bool(_RECURRING_REGEX.search(text))
    state["is_recurring_source"] = "heuristic"
    logger.info(
        "recurrence_check | is_recurring=%s source=heuristic",
        state["is_recurring"],
    )
    return state


recurrence_step = RunnableLambda(check_recurrence)
