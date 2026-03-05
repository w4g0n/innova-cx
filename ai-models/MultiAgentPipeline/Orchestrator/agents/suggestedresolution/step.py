"""
Step 9 — Suggested Resolution Agent
===================================
Triggers backend Suggested Resolution generation for assigned tickets.
This runs only as part of orchestrator pipeline execution.
"""

from __future__ import annotations

import logging
import os

import httpx
from langchain_core.runnables import RunnableLambda

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000")
logger = logging.getLogger(__name__)


async def generate_suggested_resolution(state: dict) -> dict:
    ticket_id = str(state.get("ticket_id") or "").strip()
    if not ticket_id:
        return state

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/internal/tickets/{ticket_id}/generate-suggested-resolution"
            )
            if response.status_code in {404, 409}:
                logger.info(
                    "suggested_resolution_step | skipped ticket_id=%s status=%s",
                    ticket_id,
                    response.status_code,
                )
                return state
            response.raise_for_status()
            payload = response.json() if response.content else {}
            state["suggested_resolution"] = payload.get("suggestedResolution")
            state["suggested_resolution_model"] = payload.get("model", "flan-t5-base")
            return state
    except Exception as exc:
        logger.warning("suggested_resolution_step | failed ticket_id=%s err=%s", ticket_id, exc)
        return state


suggested_resolution_step = RunnableLambda(generate_suggested_resolution)
