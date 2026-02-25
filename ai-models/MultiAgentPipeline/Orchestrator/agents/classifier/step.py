"""
Step 2 — Classification Agent
==============================
Routes the transcript to the complaint or inquiry path using local
in-process heuristic classification only.

If classifier confidence < CONFIDENCE_THRESHOLD, falls back to "complaint"
(the safer default that ensures the tenant always gets a response).
"""

import logging
from langchain_core.runnables import RunnableLambda

CONFIDENCE_THRESHOLD = 0.75
logger = logging.getLogger(__name__)

INQUIRY_HINTS = (
    "how", "what", "where", "when", "can i", "could i", "would it",
    "help", "guide", "question", "information", "status", "track",
    "follow up", "follow-up",
)
COMPLAINT_HINTS = (
    "broken", "not working", "fault", "issue", "problem", "outage",
    "leak", "urgent", "angry", "frustrated", "complaint", "failed",
    "error", "can't", "cannot",
)


def _heuristic_classify(text: str) -> tuple[str, float]:
    t = (text or "").strip().lower()
    if not t:
        return "complaint", 0.0

    inquiry_score = sum(1 for k in INQUIRY_HINTS if k in t)
    complaint_score = sum(1 for k in COMPLAINT_HINTS if k in t)
    is_question = "?" in t
    if is_question:
        inquiry_score += 1

    if complaint_score > inquiry_score:
        return "complaint", 0.65
    if inquiry_score > complaint_score:
        return "inquiry", 0.65
    return "complaint", 0.5


async def classify(state: dict) -> dict:
    """
    Classifies transcript in-process and sets state["label"].
    """
    # If ticket type was already provided at ticket-creation gate, skip classifier.
    provided_type = str(state.get("ticket_type") or state.get("label") or "").strip().lower()
    if provided_type in {"complaint", "inquiry"}:
        state["label"] = provided_type
        state["class_confidence"] = 1.0
        logger.info("classifier | skipped (provided ticket_type=%s)", provided_type)
        return state

    if not state.get("text", "").strip():
        # Empty transcript — treat as complaint so it gets a ticket
        state["label"] = "complaint"
        state["class_confidence"] = 0.0
        logger.info("classifier | empty text fallback -> complaint")
        return state

    label, conf = _heuristic_classify(state.get("text", ""))
    state["label"] = label
    state["class_confidence"] = conf
    logger.info("classifier | using local in-process heuristic")

    # Fallback to complaint if below threshold (safer default)
    if state["class_confidence"] < CONFIDENCE_THRESHOLD:
        state["label"] = "complaint"
    logger.info(
        "classifier | label=%s confidence=%.3f",
        state["label"],
        float(state.get("class_confidence", 0.0) or 0.0),
    )

    return state


classifier_step = RunnableLambda(classify)
