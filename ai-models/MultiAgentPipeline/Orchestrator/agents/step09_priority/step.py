"""
Step 6 — Prioritization Agent
=============================
Calls the PrioritizationAgent runtime rules engine and stores:
    state["priority_label"]  -> low|medium|high|critical
    state["priority_score"]  -> int mapped for backend ticket insert
"""

import sys
import logging
from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)

# Prioritization agent package copied in Docker to /app/prioritization_agent
sys.path.insert(0, "/app/prioritization_agent")
try:
    from src.inference import (  # noqa: E402
        prioritize as model_prioritize,
        add_manager_feedback_example,
    )
    _PRIORITY_MODEL_AVAILABLE = True
except Exception as exc:  # pragma: no cover - runtime fallback guard
    model_prioritize = None
    add_manager_feedback_example = None
    _PRIORITY_MODEL_AVAILABLE = False
    logger.warning("priority | runtime unavailable, using mock fallback. err=%s", exc)


PRIORITY_TO_SCORE = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}

def get_priority_diagnostics() -> dict[str, object]:
    return {
        "priority_model_available": _PRIORITY_MODEL_AVAILABLE,
        "priority_mode": "model" if _PRIORITY_MODEL_AVAILABLE else "mock",
        "priority_mode_reason": (
            "prioritization runtime loaded from /app/prioritization_agent"
            if _PRIORITY_MODEL_AVAILABLE
            else "prioritization runtime missing; using medium-priority mock fallback"
        ),
    }

def _bucket_from_numeric(score: float) -> str:
    if score < -0.25:
        return "negative"
    if score > 0.25:
        return "positive"
    return "neutral"


async def score_priority(state: dict) -> dict:
    if state.get("label") not in {"complaint", "inquiry"}:
        logger.info("priority | skipped (unsupported label=%s)", state.get("label"))
        return state

    sentiment_input = str(state.get("sentiment_score", "")).strip().lower()
    if sentiment_input not in {"negative", "neutral", "positive"}:
        sentiment_input = _bucket_from_numeric(
            float(state.get("sentiment_score_numeric", 0.0) or 0.0)
        )

    issue_severity = str(state.get("issue_severity", "medium")).strip().lower()
    issue_urgency = str(state.get("issue_urgency", "medium")).strip().lower()
    business_impact = str(state.get("business_impact", "medium")).strip().lower()
    safety_concern = bool(state.get("safety_concern", False))
    is_recurring = bool(state.get("is_recurring", False))
    ticket_type = str(state.get("label", "complaint")).strip().lower()

    # Branch D recurrence: inherit the prior ticket's priority directly.
    # This bypasses the model so the new ticket matches the old one's severity.
    priority_override = str(state.get("priority_override") or "").strip().lower()
    if priority_override and priority_override in PRIORITY_TO_SCORE:
        state["priority_label"] = priority_override
        state["priority_score"] = PRIORITY_TO_SCORE[priority_override]
        state["priority_mode"] = "recurrence_override"
        logger.info("priority | override from prior ticket priority=%s", priority_override)
        return state

    try:
        if not _PRIORITY_MODEL_AVAILABLE or model_prioritize is None:
            raise RuntimeError("priority runtime unavailable")
        state["priority_mode"] = "model"
        result = model_prioritize(
            sentiment_score=sentiment_input,
            issue_severity_val=issue_severity,
            issue_urgency_val=issue_urgency,
            business_impact_val=business_impact,
            safety_concern=safety_concern,
            is_recurring=False,  # recurrence handled via Branch B — never influence the model
            ticket_type=ticket_type,
        )
        final_priority = str(result["final_priority"]).strip().lower()
        state["priority_label"] = final_priority
        state["priority_score"] = PRIORITY_TO_SCORE.get(final_priority, 3)
        state["priority_details"] = result
        logger.info(
            "priority | base=%s final=%s score=%s modifiers=%s",
            result.get("base_priority"),
            final_priority,
            state.get("priority_score"),
            "; ".join(result.get("modifiers_applied", [])),
        )
    except Exception as exc:
        logger.warning("priority | runtime unavailable/failed (%s) — defaulting medium", exc)
        state["priority_mode"] = "mock"
        state["priority_label"] = "medium"
        state["priority_score"] = 3

    return state


def record_manager_feedback_from_state(
    *,
    state: dict,
    approved_priority: str,
    ticket_id: str | None = None,
    retrain_now: bool = False,
) -> dict:
    """Append manager-approved label and retrain periodically."""
    sentiment_score = str(state.get("sentiment_score", "")).strip().lower()
    if sentiment_score not in {"negative", "neutral", "positive"}:
        sentiment_score = _bucket_from_numeric(
            float(state.get("sentiment_score_numeric") or state.get("text_sentiment") or 0.0)
        )
    if not _PRIORITY_MODEL_AVAILABLE or add_manager_feedback_example is None:
        return {
            "saved": False,
            "retrained": False,
            "mode": "mock",
            "note": "priority runtime unavailable; feedback not persisted to model",
        }
    return add_manager_feedback_example(
        sentiment_score=sentiment_score,
        issue_severity_val=str(state.get("issue_severity", "medium")),
        issue_urgency_val=str(state.get("issue_urgency", "medium")),
        business_impact_val=str(state.get("business_impact", "medium")),
        safety_concern=bool(state.get("safety_concern", False)),
        is_recurring=bool(state.get("is_recurring", False)),
        ticket_type=str(state.get("label", "complaint")),
        approved_priority=approved_priority,
        ticket_id=ticket_id,
        retrain_now=retrain_now,
    )


priority_step = RunnableLambda(score_priority)
