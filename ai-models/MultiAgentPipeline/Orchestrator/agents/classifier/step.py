"""
Step 2 — Classification Agent
==============================
Routes the transcript to the complaint or inquiry path using the
DistilRoBERTa classifier service (port 8003).

If classifier confidence < CONFIDENCE_THRESHOLD, falls back to "complaint"
(the safer default that ensures the tenant always gets a response).
"""

import httpx
import logging
from langchain_core.runnables import RunnableLambda

CLASSIFIER_URL = "http://classifier:8003"
CONFIDENCE_THRESHOLD = 0.75
logger = logging.getLogger(__name__)


async def classify(state: dict) -> dict:
    """
    Calls the classifier service and sets state["label"].

    Service response: {label, confidence, processing_time_ms, mock_mode}
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

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{CLASSIFIER_URL}/classify",
            json={"text": state["text"]},
        )
        response.raise_for_status()
        data = response.json()

    state["label"] = data["label"]               # "complaint" or "inquiry"
    state["class_confidence"] = data["confidence"]

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
