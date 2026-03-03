"""
Step 6 — Router
================
Final step: enriches routed ticket with final priority/SLA/department.
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


def _department_from_asset(asset_type: str | None) -> str | None:
    """
    Temporary rule: selected asset acts as selected department.
    """
    if not asset_type:
        return None
    department = str(asset_type).strip()
    return department or None


def infer_department(keywords: list[str]) -> str:
    """Infer department from extracted keywords."""
    kw_lower = [k.lower() for k in keywords]
    for dept, dept_keywords in DEPARTMENT_KEYWORDS.items():
        if any(dk.lower() in kw_lower for dk in dept_keywords):
            return dept
    return "general"


async def route_and_store(state: dict) -> dict:
    """
    Inquiry → backend ticket (POST /api/complaints)
    Complaint → backend ticket (POST /api/complaints)
    """
    if state["label"] == "inquiry":
        state["chatbot_response"] = None
        selected_department = _department_from_asset(state.get("asset_type")) or "general"
        inquiry_payload = {
            "ticket_id": state.get("ticket_id"),
            "transcript": state["text"],
            "asset_type": state.get("asset_type") or "General",
            "sentiment": state.get("text_sentiment", 0.0),
            "sentiment_label": state.get("sentiment_category"),
            "audio_sentiment": state.get("audio_sentiment", 0.0),
            "priority": state.get("priority_score", 3),
            "department": selected_department,
            "keywords": state.get("keywords", []),
            "label": "inquiry",
            "status": "Assigned",
            "classification_confidence": state.get("class_confidence", 1.0),
            "is_recurring": bool(state.get("is_recurring", False)),
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{BACKEND_URL}/api/complaints",
                    json=inquiry_payload,
                )
                response.raise_for_status()
                data = response.json()
            state["status"] = data.get("status", state.get("status"))
            state["department"] = data.get("department", selected_department)
            state["asset_type"] = data.get("asset_type", inquiry_payload.get("asset_type"))
            state["priority_label"] = data.get("priority", state.get("priority_label"))
            state["priority_assigned_at"] = data.get("priority_assigned_at")
            state["respond_due_at"] = data.get("respond_due_at")
            state["resolve_due_at"] = data.get("resolve_due_at")
            state["ticket_id"] = data.get("ticket_id")
            logger.info(
                "ticket_status_update | ticket_id=%s status=%s department=%s asset_type=%s priority=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                state.get("ticket_id"),
                data.get("status", "Assigned"),
                data.get("department", selected_department),
                data.get("asset_type", inquiry_payload.get("asset_type")),
                data.get("priority"),
                data.get("priority_assigned_at"),
                data.get("respond_due_at"),
                data.get("resolve_due_at"),
            )
        except Exception as exc:
            logger.warning("router | inquiry ticket creation failed: %s", exc)
            state["ticket_id"] = state.get("ticket_id")

        return state

    # Complaint path — infer department if not set
    if not state.get("department"):
        state["department"] = (
            _department_from_asset(state.get("asset_type"))
            or infer_department(state.get("keywords", []))
        )

    ticket_payload = {
        "ticket_id": state.get("ticket_id"),
        "transcript": state["text"],
        "asset_type": state.get("asset_type") or "General",
        "sentiment": state.get("text_sentiment", 0.0),
        "sentiment_label": state.get("sentiment_category"),
        "audio_sentiment": state.get("audio_sentiment", 0.0),
        "priority": state.get("priority_score", 3),
        "department": state["department"],
        "keywords": state.get("keywords", []),
        "label": "complaint",
        "status": "Assigned",
        "classification_confidence": state.get("class_confidence", 1.0),
        "is_recurring": bool(state.get("is_recurring", False)),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{BACKEND_URL}/api/complaints",
            json=ticket_payload,
        )
        response.raise_for_status()
        data = response.json()

    state["status"] = data.get("status", state.get("status"))
    state["department"] = data.get("department", state.get("department"))
    state["asset_type"] = data.get("asset_type", ticket_payload.get("asset_type"))
    state["priority_label"] = data.get("priority", state.get("priority_label"))
    state["priority_assigned_at"] = data.get("priority_assigned_at")
    state["respond_due_at"] = data.get("respond_due_at")
    state["resolve_due_at"] = data.get("resolve_due_at")
    state["ticket_id"] = data.get("ticket_id")
    logger.info(
        "ticket_status_update | ticket_id=%s status=%s department=%s asset_type=%s priority=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
        state.get("ticket_id"),
        data.get("status", "Assigned"),
        data.get("department", state.get("department")),
        data.get("asset_type", ticket_payload.get("asset_type")),
        data.get("priority"),
        data.get("priority_assigned_at"),
        data.get("respond_due_at"),
        data.get("resolve_due_at"),
    )
    return state


router_step = RunnableLambda(route_and_store)
