"""
Step 6 — Fuzzy Prioritization Agent
===================================
Calls the PrioritizationAgent fuzzy logic engine and stores:
    state["priority_label"]  -> low|medium|high|critical
    state["priority_score"]  -> int mapped for backend ticket insert
"""

import sys
import logging
from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)

# Prioritization agent package copied in Docker to /app/prioritization_agent
sys.path.insert(0, "/app/prioritization_agent")
from src.inference import prioritize as fuzzy_prioritize  # noqa: E402


PRIORITY_TO_SCORE = {
    "low": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}

SENTIMENT_BUCKET_TO_VALUE = {
    "negative": -0.5,
    "neutral": 0.0,
    "positive": 0.5,
}


async def score_priority(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("priority | skipped (label=%s)", state.get("label"))
        return state

    sentiment_input = str(state.get("sentiment_score", "neutral")).strip().lower()
    sentiment_score = SENTIMENT_BUCKET_TO_VALUE.get(
        sentiment_input,
        float(state.get("sentiment_score_numeric", 0.0) or 0.0),
    )

    issue_severity = str(state.get("issue_severity", "medium")).strip().lower()
    issue_urgency = str(state.get("issue_urgency", "medium")).strip().lower()
    business_impact = str(state.get("business_impact", "medium")).strip().lower()
    safety_concern = bool(state.get("safety_concern", False))
    is_recurring = bool(state.get("is_recurring", False))
    ticket_type = str(state.get("label", "complaint")).strip().lower()

    try:
        result = fuzzy_prioritize(
            sentiment_score=sentiment_score,
            issue_severity_val=issue_severity,
            issue_urgency_val=issue_urgency,
            business_impact_val=business_impact,
            safety_concern=safety_concern,
            is_recurring=is_recurring,
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
        logger.warning("Fuzzy prioritization failed (%s) — defaulting medium", exc)
        state["priority_label"] = "medium"
        state["priority_score"] = 3

    return state


priority_step = RunnableLambda(score_priority)
