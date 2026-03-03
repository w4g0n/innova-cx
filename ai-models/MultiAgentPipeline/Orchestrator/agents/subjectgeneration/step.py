"""
Step 1 — Subject Generation Agent
=================================
Generates a short subject using the chatbot model when the current subject is empty.
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain_core.runnables import RunnableLambda

BACKEND_URL = "http://backend:8000"
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://chatbot:8000")
CHATBOT_URL_LOCAL = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001")

logger = logging.getLogger(__name__)


def _is_empty_subject(value: object) -> bool:
    return not str(value or "").strip()


async def _generate_subject(details: str) -> str:
    payload = {"details": details}
    last_error: Exception | None = None
    for base in (CHATBOT_URL, CHATBOT_URL_LOCAL):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{base}/api/suggest-subject", json=payload)
                response.raise_for_status()
                data = response.json()
                subject = str(data.get("subject") or "").strip()
                if subject:
                    return subject
        except Exception as exc:  # pragma: no cover
            last_error = exc
            continue
    raise RuntimeError(f"Subject generation service unavailable: {last_error}")


async def generate_subject(state: dict) -> dict:
    current_subject = state.get("subject")
    details = str(state.get("text") or "").strip()
    if not details or not _is_empty_subject(current_subject):
        return state

    generated_subject = await _generate_subject(details)
    state["subject"] = generated_subject

    payload = {
        "ticket_id": state.get("ticket_id"),
        "subject": generated_subject,
        "transcript": details,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"{BACKEND_URL}/api/complaints", json=payload)
        response.raise_for_status()
        data = response.json()

    state["ticket_id"] = data.get("ticket_id", state.get("ticket_id"))
    logger.info(
        "subject_generation | ticket_id=%s subject=%s",
        state.get("ticket_id"),
        generated_subject,
    )
    return state


subject_generation_step = RunnableLambda(generate_subject)
