"""
Step 6 — Router
================
Final step: routes inquiries to the chatbot and creates tickets for complaints.
"""

import httpx
import logging
from langchain_core.runnables import RunnableLambda

BACKEND_URL = "http://backend:8000"
logger = logging.getLogger(__name__)

DEPARTMENT_KEYWORDS: dict[str, list[str]] = {
    "maintenance": ["AC", "air conditioning", "heating", "leak", "pipe", "elevator", "lift"],
    "electrical":  ["power", "electricity", "lights", "outlet", "circuit"],
    "security":    ["security", "alarm", "fire alarm", "safety", "access"],
    "it":          ["internet", "WiFi", "connectivity", "network"],
    "cleaning":    ["cleaning", "trash", "garbage"],
}


def infer_department(keywords: list[str]) -> str:
    """Infer department from extracted keywords."""
    kw_lower = [k.lower() for k in keywords]
    for dept, dept_keywords in DEPARTMENT_KEYWORDS.items():
        if any(dk.lower() in kw_lower for dk in dept_keywords):
            return dept
    return "general"


async def route_and_store(state: dict) -> dict:
    """
    Inquiry → chatbot  (POST /api/chat)
    Complaint → backend ticket  (POST /api/complaints)
    """
    if state["label"] == "inquiry":
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/api/chatbot/chat",
                    json={"message": state["text"], "mode": "inquiry"},
                )
                response.raise_for_status()
                data = response.json()
            # Backend chatbot proxy returns {"reply": "..."}
            state["chatbot_response"] = data.get("reply", "")
        except Exception as exc:
            logger.warning("router | chatbot proxy unavailable: %s", exc)
            state["chatbot_response"] = "Chatbot service is unavailable right now."
        state["ticket_id"] = None
        logger.info("router | inquiry routed to chatbot proxy")
        return state

    # Complaint path — infer department if not set
    if not state.get("department"):
        state["department"] = infer_department(state.get("keywords", []))

    ticket_payload = {
        "transcript": state["text"],
        "sentiment": state.get("text_sentiment", 0.0),
        "audio_sentiment": state.get("audio_sentiment", 0.0),
        "priority": state.get("priority_score", 3),
        "department": state["department"],
        "keywords": state.get("keywords", []),
        "label": "complaint",
        "classification_confidence": state.get("class_confidence", 1.0),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BACKEND_URL}/api/complaints",
            json=ticket_payload,
        )
        response.raise_for_status()
        data = response.json()

    state["ticket_id"] = data.get("ticket_id")
    logger.info(
        "router | complaint ticket created ticket_id=%s department=%s",
        state.get("ticket_id"),
        state.get("department"),
    )
    return state


router_step = RunnableLambda(route_and_store)
