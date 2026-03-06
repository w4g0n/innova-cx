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
from functools import lru_cache
from pathlib import Path

import httpx
from langchain_core.runnables import RunnableLambda

BACKEND_URL = "http://backend:8000"
SUBJECT_GENERATOR_MODEL_PATH = os.getenv("SUBJECT_GENERATOR_MODEL_PATH", "").strip()
SUBJECT_GENERATOR_MODEL_NAME = os.getenv("SUBJECT_GENERATOR_MODEL_NAME", "google/flan-t5-small").strip()
SUBJECT_GENERATOR_AUTO_DOWNLOAD = os.getenv("SUBJECT_GENERATOR_AUTO_DOWNLOAD", "true").lower() in {"1", "true", "yes"}
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None

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
    return f"{compact[:25].rstrip()}..."


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


@lru_cache(maxsize=1)
def _load_subject_generator():
    if not SUBJECT_GENERATOR_MODEL_PATH:
        logger.info("subject_generation | SUBJECT_GENERATOR_MODEL_PATH is empty, using heuristic")
        return None

    model_path = Path(SUBJECT_GENERATOR_MODEL_PATH)
    if not (model_path / "config.json").exists() and SUBJECT_GENERATOR_AUTO_DOWNLOAD and SUBJECT_GENERATOR_MODEL_NAME:
        try:
            from huggingface_hub import snapshot_download  # type: ignore

            logger.info(
                "subject_generation | downloading model=%s to %s",
                SUBJECT_GENERATOR_MODEL_NAME,
                SUBJECT_GENERATOR_MODEL_PATH,
            )
            snapshot_download(
                repo_id=SUBJECT_GENERATOR_MODEL_NAME,
                local_dir=SUBJECT_GENERATOR_MODEL_PATH,
                token=HF_TOKEN,
            )
        except Exception as exc:
            logger.warning("subject_generation | auto-download failed (%s), using heuristic", exc)

    if not (model_path / "config.json").exists():
        logger.info("subject_generation | model not configured, using heuristic")
        return None

    try:
        import torch  # type: ignore
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

        tokenizer = AutoTokenizer.from_pretrained(SUBJECT_GENERATOR_MODEL_PATH)
        model = AutoModelForSeq2SeqLM.from_pretrained(SUBJECT_GENERATOR_MODEL_PATH)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        return {"tokenizer": tokenizer, "model": model, "device": device}
    except Exception as exc:
        logger.warning("subject_generation | model load failed (%s), using heuristic", exc)
        return None


def get_subject_generation_diagnostics() -> dict[str, object]:
    model_exists = bool(
        SUBJECT_GENERATOR_MODEL_PATH and (Path(SUBJECT_GENERATOR_MODEL_PATH) / "config.json").exists()
    )
    mode = "model" if model_exists else "mock"
    return {
        "subject_generator_model_path": SUBJECT_GENERATOR_MODEL_PATH or None,
        "subject_generator_model_name": SUBJECT_GENERATOR_MODEL_NAME or None,
        "subject_generator_auto_download": SUBJECT_GENERATOR_AUTO_DOWNLOAD,
        "subject_generator_model_exists": model_exists,
        "subject_generator_mode": mode,
    }


async def _generate_subject(details: str) -> str:
    loaded = _load_subject_generator()
    if loaded is not None:
        try:
            import torch  # type: ignore

            prompt = (
                "Generate one clear support ticket subject (5-8 words). "
                "Use sentence case and output only the subject.\n\n"
                f"Ticket details: {details}"
            )
            tokenizer = loaded["tokenizer"]
            model = loaded["model"]
            device = loaded["device"]
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=24,
                    do_sample=False,
                    num_beams=4,
                )
            text = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
            subject = _sanitize_subject(text)
            if subject and not _is_low_quality_subject(subject):
                return subject
        except Exception as exc:
            logger.warning("subject_generation | model inference failed (%s), using heuristic", exc)
    return _heuristic_subject(details)


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
