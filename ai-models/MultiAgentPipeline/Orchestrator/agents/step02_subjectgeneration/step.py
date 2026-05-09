"""
Step 1 — Subject Generation Agent
=================================
Generates a short subject when the current subject is empty.
Uses the shared Qwen model (via shared_model_service) as primary generator.
Falls back to heuristic truncation if Qwen is unavailable.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

import httpx
from langchain_core.runnables import RunnableLambda
from backend_client import internal_backend_headers

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
logger = logging.getLogger(__name__)
SUBJECT_GENERATION_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("SUBJECT_GENERATION_TIMEOUT_SECONDS", "25")),
)
SUBJECT_GENERATION_MAX_PROMPT_TOKENS = max(
    64,
    int(os.getenv("SUBJECT_GENERATION_MAX_PROMPT_TOKENS", "192")),
)
SUBJECT_GENERATION_MAX_NEW_TOKENS = max(
    4,
    int(os.getenv("SUBJECT_GENERATION_MAX_NEW_TOKENS", "8")),
)

_SUBJECT_SYSTEM = (
    "You generate short ticket subjects for a facilities management support system. "
    "Reply with the subject only — no explanation, no quotes, no labels. "
    "Use 2 to 5 words only."
)


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
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9&/'-]*", subject)
    if len(tokens) >= 2:
        subject = " ".join(tokens[:5])
    elif tokens:
        subject = " ".join(tokens[:2])
    if not subject:
        return ""
    return subject[0].upper() + subject[1:]


def _heuristic_subject(details: str) -> str:
    text = str(details or "").strip()
    if not text:
        return "Support issue"
    compact = re.sub(r"\s+", " ", text).strip()
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9&/'-]*", compact)
    if len(tokens) >= 2:
        return " ".join(tokens[:5]).capitalize()
    if tokens:
        return " ".join(tokens[:2]).capitalize()
    return "Support issue"


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
    word_count = len(s.split())
    return word_count < 2 or word_count > 5


def get_subject_generation_diagnostics() -> dict[str, object]:
    try:
        from shared_model_service import SHARED_QWEN_MODEL_PATH
        from pathlib import Path
        model_exists = bool(SHARED_QWEN_MODEL_PATH and (Path(SHARED_QWEN_MODEL_PATH) / "config.json").exists())
        model_path = SHARED_QWEN_MODEL_PATH
    except Exception:
        model_exists = False
        model_path = None
    return {
        "subject_generator_model_path": model_path,
        "subject_generator_model_name": "Qwen/Qwen2.5-0.5B-Instruct",
        "subject_generator_model_exists": model_exists,
        "subject_generator_mode": "qwen" if model_exists else "heuristic",
        "subject_generator_mode_reason": "Shared Qwen model primary, heuristic fallback if unavailable",
    }


def _generate_subject_via_qwen(details: str) -> str:
    try:
        from shared_model_service import get_shared_qwen
        loaded = get_shared_qwen()
    except Exception:
        return ""
    if loaded is None:
        return ""
    try:
        import torch  # type: ignore
        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        device = loaded["device"]
        prompt = (
            "Write a subject of 2 to 5 words for this support ticket. "
            "Keep it concise and specific.\n"
            f"{str(details or '')[:300]}"
        )
        messages = [
            {"role": "system", "content": _SUBJECT_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        if hasattr(tokenizer, "apply_chat_template"):
            rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(
                [rendered],
                return_tensors="pt",
                truncation=True,
                max_length=SUBJECT_GENERATION_MAX_PROMPT_TOKENS,
            ).to(device)
        else:
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=SUBJECT_GENERATION_MAX_PROMPT_TOKENS,
            ).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=SUBJECT_GENERATION_MAX_NEW_TOKENS,
                do_sample=False,
                no_repeat_ngram_size=3,
                use_cache=torch.cuda.is_available(),
            )
        prompt_len = inputs["input_ids"].shape[1]
        generated = (
            output_ids[0][prompt_len:]
            if output_ids.shape[1] > prompt_len
            else output_ids[0]
        )
        raw = tokenizer.decode(generated, skip_special_tokens=True).strip()
        return _sanitize_subject(raw)
    except Exception as exc:
        logger.warning("subject_generation | qwen inference failed (%s)", exc)
        return ""


async def _generate_subject(details: str) -> str:
    try:
        subject = await asyncio.wait_for(
            asyncio.to_thread(_generate_subject_via_qwen, details),
            timeout=SUBJECT_GENERATION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "subject_generation | qwen timed out after %.1fs; using heuristic fallback",
            SUBJECT_GENERATION_TIMEOUT_SECONDS,
        )
        subject = ""
    subject = _sanitize_subject(subject)
    if subject and not _is_low_quality_subject(subject):
        return subject
    return _heuristic_subject(details)


async def generate_subject(state: dict) -> dict:
    diagnostics = get_subject_generation_diagnostics()
    state["subject_generation_mode"] = diagnostics.get("subject_generator_mode", "heuristic")
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
        response = await client.post(
            f"{BACKEND_URL}/api/complaints",
            json=payload,
            headers=internal_backend_headers(),
        )
        response.raise_for_status()
        data = response.json()

    state["ticket_id"] = data.get("ticket_id", state.get("ticket_id"))
    logger.info(
        "subject_generation | ticket_id=%s subject=%s mode=%s",
        state.get("ticket_id"),
        generated_subject,
        state.get("subject_generation_mode"),
    )
    return state


subject_generation_step = RunnableLambda(generate_subject)
