"""
Step 1 — Subject Generation Agent
=================================
Generates a short subject when the current subject is empty.
This agent is self-contained and does not depend on chatbot.
"""

from __future__ import annotations

import logging
import os
import re
import asyncio

import httpx
from langchain_core.runnables import RunnableLambda

BACKEND_URL = "http://backend:8000"
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://chatbot:8000").rstrip("/")
CHATBOT_URL_LOCAL = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001").rstrip("/")
SUBJECT_ENDPOINT_TIMEOUT_SECONDS = float(os.getenv("SUBJECT_ENDPOINT_TIMEOUT_SECONDS", "75"))
SUBJECT_ENDPOINT_RETRIES = max(1, int(os.getenv("SUBJECT_ENDPOINT_RETRIES", "2")))

logger = logging.getLogger(__name__)


def _is_empty_subject(value: object) -> bool:
    return not str(value or "").strip()


def _sanitize_subject(value: str) -> str:
    subject = str(value or "").strip()
    if not subject:
        return ""
    subject = subject.splitlines()[0].strip()
    subject = re.sub(r"\s+", " ", subject)
    subject = re.sub(
        r"^(?:here(?:'s| is)\s+)?(?:the\s+)?(?:best\s+)?(?:support\s+ticket\s+)?(?:subject|title)(?:\s+line)?\s*(?:is)?\s*[:\-]\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    subject = re.sub(
        r"^(?:subject|title|ticket|tickets?|issue|details?)\s*[:\-]\s*",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    subject = re.sub(r"^(?:output|answer|generated)\s*[:\-]\s*", "", subject, flags=re.IGNORECASE)
    subject = subject.strip(" .,:;!?-\"'")
    # Keep subject concise and predictable for UI display.
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9&/'-]*", subject)
    if tokens:
        subject = " ".join(tokens[:8])
    if not subject:
        return ""
    return subject[0].upper() + subject[1:]


def _heuristic_subject(details: str) -> str:
    text = str(details or "").strip()
    if not text:
        return "Support issue..."
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= 25:
        return compact
    truncated = compact[:25].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0].rstrip()
    if not truncated:
        truncated = compact[:25].rstrip()
    return f"{truncated}..."


def _is_low_quality_subject(subject: str) -> bool:
    s = str(subject or "").strip().lower()
    if not s:
        return True
    generic_prefixes = (
        "ticket to ",
        "ticket for ",
        "support ticket",
        "issue reported",
        "details ",
    )
    if any(s.startswith(prefix) for prefix in generic_prefixes):
        return True
    return len(s.split()) < 3


def get_subject_generation_diagnostics() -> dict[str, object]:
    return {
        "subject_generator_model_path": None,
        "subject_generator_model_name": None,
        "subject_generator_auto_download": False,
        "subject_generator_model_exists": False,
        "subject_generator_mode": "chatbot_endpoint",
        "subject_generator_mode_reason": "Chatbot subject generation endpoint is used first, with heuristic fallback if unavailable",
    }


async def _generate_subject_via_chatbot(details: str) -> str:
    payload = {"details": details}
    last_error: Exception | None = None
    timeout = httpx.Timeout(connect=5.0, read=SUBJECT_ENDPOINT_TIMEOUT_SECONDS, write=10.0, pool=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(SUBJECT_ENDPOINT_RETRIES):
            for base in (CHATBOT_URL, CHATBOT_URL_LOCAL):
                try:
                    response = await client.post(f"{base}/api/suggest-subject", json=payload)
                    response.raise_for_status()
                    data = response.json() or {}
                    subject = _sanitize_subject(str(data.get("subject") or ""))
                    if subject and not _is_low_quality_subject(subject):
                        return subject
                except Exception as exc:
                    last_error = exc
            if attempt < SUBJECT_ENDPOINT_RETRIES - 1:
                await asyncio.sleep(1.5)
    if last_error:
        logger.warning("subject_generation | chatbot subject endpoint unavailable err=%s", last_error)
    return ""


async def _generate_subject(details: str) -> str:
    subject = await _generate_subject_via_chatbot(details)
    if subject:
        return subject
    subject = _sanitize_subject(_heuristic_subject(details))
    if subject and not _is_low_quality_subject(subject):
        return subject
    return _heuristic_subject(details)


async def generate_subject(state: dict) -> dict:
    state["subject_generation_mode"] = get_subject_generation_diagnostics().get("subject_generator_mode", "heuristic")
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
