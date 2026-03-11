"""
Step 11 — Suggested Resolution Agent
====================================
Generates suggested resolution in the orchestrator using the dedicated local
model artifact, with a deterministic template fallback if unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import gc
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
from langchain_core.runnables import RunnableLambda
from db import db_connect

BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:8000").rstrip("/")
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
SUGGESTED_RESOLUTION_MODEL_PATH = os.getenv(
    "SUGGESTED_RESOLUTION_MODEL_PATH",
    "/app/agents/step02_suggestedresolution/model",
).strip()
SUGGESTED_RESOLUTION_MODEL_NAME = os.getenv(
    "SUGGESTED_RESOLUTION_MODEL_NAME",
    "Qwen/Qwen2.5-0.5B-Instruct",
).strip()
SUGGESTED_RESOLUTION_AUTO_DOWNLOAD = os.getenv(
    "SUGGESTED_RESOLUTION_AUTO_DOWNLOAD",
    "false",
).lower() in {"1", "true", "yes"}
SUGGESTED_RESOLUTION_EXAMPLES_PATH = Path(
    os.getenv(
        "SUGGESTED_RESOLUTION_EXAMPLES_PATH",
        "/app/agents/step02_suggestedresolution/model/suggested_resolution_examples.json",
    ).strip()
)
SUGGESTED_RESOLUTION_PROMPT_EXAMPLES = max(
    0,
    int(os.getenv("SUGGESTED_RESOLUTION_PROMPT_EXAMPLES", "3")),
)

logger = logging.getLogger(__name__)
SUGGESTED_RESOLUTION_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("SUGGESTED_RESOLUTION_TIMEOUT_SECONDS", "20")),
)
_BACKGROUND_SUGGESTED_RESOLUTION_TASKS: set[asyncio.Task] = set()
UNLOAD_SUGGESTED_RESOLUTION_MODEL_AFTER_USE = os.getenv(
    "UNLOAD_SUGGESTED_RESOLUTION_MODEL_AFTER_USE",
    "false",
).lower() in {"1", "true", "yes"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _infer_resolution_plan(ticket: dict[str, Any]) -> tuple[str, str, str]:
    details = str(ticket.get("details") or "").lower()
    department = str(ticket.get("department_name") or "").strip()
    if not department or department.lower() in {"general", "unassigned"}:
        department = "Maintenance"

    first_action = "triage the reported issue"
    verify_action = "confirm the issue is resolved with the reporter"

    if any(term in details for term in ("exposed wire", "electrical wire", "electric shock", "sparking", "short circuit")):
        first_action = "isolate power to the affected area and secure access immediately"
        department = "Maintenance"
        verify_action = "confirm the electrical hazard is removed and the area is safe to reopen"
    elif any(term in details for term in ("water leak", "water leakage", "leak", "flood", "pipe burst")):
        first_action = "shut off the leak source if possible and contain the water immediately"
        department = "Maintenance"
        verify_action = "confirm the leak has stopped and no active water ingress remains"
    elif any(term in details for term in ("fire", "smoke", "alarm", "gas leak")):
        first_action = "escalate emergency response, isolate the area, and protect occupants immediately"
        department = "Safety & Security"
        verify_action = "confirm the site has been declared safe and the immediate danger is cleared"
    elif any(term in details for term in ("wifi", "internet", "network", "server", "system", "login")):
        first_action = "check the affected service status and restore connectivity for impacted users"
        department = "IT"
        verify_action = "confirm users can access the service normally again"
    elif any(term in details for term in ("rat", "rodent", "mouse", "mice", "pest", "cockroach", "insect", "exterminator")):
        first_action = "isolate the affected area and dispatch pest control immediately"
        department = "Facilities"
        verify_action = "confirm the infestation risk is removed and the area is safe for normal use"
    elif any(term in details for term in ("rent", "lease", "pricing", "cost", "office cost", "offices cost")):
        first_action = "review the customer’s pricing or leasing request and provide the correct commercial information"
        department = "Leasing"
        verify_action = "confirm the customer received the requested pricing details"

    return first_action, department, verify_action


def fallback_resolution_suggestion(ticket: dict[str, Any]) -> str:
    first_action, department, verify_action = _infer_resolution_plan(ticket)
    return f"{first_action.capitalize()}; assign to {department} and {verify_action}."


def _clean_generated_resolution(text: str, ticket: dict[str, Any]) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    cleaned = cleaned.splitlines()[0].strip()
    cleaned = re.sub(r"^(suggested resolution|resolution)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(?:^|\s)(?:subject|details|ticket|input|output)\s*:\s*.*$', "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" -")


def _is_low_quality_resolution(text: str) -> bool:
    cleaned = str(text or "").strip().lower()
    if not cleaned:
        return True
    banned_phrases = (
        "investigate issue",
        "appropriate team",
        "relevant department",
        "follow standard procedure",
        "someone should",
        "general team",
        "general issue",
        "assign to general",
        "priority:",
        "root-cause remediation",
        "service recovery",
        "verify and stabilize",
    )
    if any(phrase in cleaned for phrase in banned_phrases):
        return True
    if "(" in cleaned or ")" in cleaned:
        return True
    if "general" in cleaned and "facilities" not in cleaned and "maintenance" not in cleaned and "it" not in cleaned and "leasing" not in cleaned and "safety" not in cleaned:
        return True
    return len(cleaned.split()) < 8


def _load_resolution_examples(limit: int = 3) -> list[dict[str, Any]]:
    if limit <= 0 or not SUGGESTED_RESOLUTION_EXAMPLES_PATH.exists():
        return []
    try:
        payload = json.loads(SUGGESTED_RESOLUTION_EXAMPLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    examples = payload.get("examples") if isinstance(payload, dict) else []
    if not isinstance(examples, list):
        return []
    return [ex for ex in examples[:limit] if isinstance(ex, dict)]


def _format_examples_for_prompt(limit: int) -> str:
    examples = _load_resolution_examples(limit=limit)
    if not examples:
        return ""
    lines = []
    for i, ex in enumerate(examples, start=1):
        subject = str(ex.get("subject") or "").strip() or "No subject"
        details = str(ex.get("details") or "").strip() or "No details"
        resolution = str(ex.get("final_resolution") or "").strip() or "No resolution"
        lines.append(
            (
                f"Example {i}\n"
                f"Input: type={ex.get('ticket_type')}; priority={ex.get('priority')}; subject={subject}; details={details}\n"
                f"Output: {resolution}"
            )
        )
    return "\n\n".join(lines)


def _build_generation_prompt(ticket: dict[str, Any]) -> str:
    details = str(ticket.get("details") or "").strip() or "No details"

    prompt = (
        "Write one resolution sentence for a support employee handling the following facilities ticket.\n\n"
        "Rules:\n"
        "1. Use imperative style.\n"
        "2. Begin with the first containment or triage action.\n"
        "3. Name the responsible team (infer from the issue if not stated).\n"
        "4. End with a verification step.\n"
        "5. For fire, flooding, gas, smoke, exposed wiring, or injury risk: lead with isolation or evacuation before any other step.\n"
        "6. Do not repeat ticket wording verbatim.\n"
        "7. Do not use vague terms like \"appropriate team,\" \"someone should,\" or \"investigate the issue.\"\n"
        "8. Length: 18–40 words.\n\n"
    )

    learned_examples = _format_examples_for_prompt(SUGGESTED_RESOLUTION_PROMPT_EXAMPLES)
    if learned_examples:
        prompt += (
            "Use these past successful resolutions as style guidance:\n\n"
            f"{learned_examples}\n\n"
        )

    prompt += f"Ticket: {details}"
    return prompt


def retrain_resolution_examples_from_rows(rows: list[dict[str, Any]], max_examples: int = 12) -> dict[str, Any]:
    max_examples = max(1, min(int(max_examples), 50))
    if not rows:
        payload = {"updated_at": _utc_now_iso(), "examples": []}
        SUGGESTED_RESOLUTION_EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUGGESTED_RESOLUTION_EXAMPLES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "examples_written": 0, "feedback_rows": 0, "reason": "no_feedback_rows", "path": str(SUGGESTED_RESOLUTION_EXAMPLES_PATH)}

    examples: list[dict[str, Any]] = []
    seen_keys = set()
    for row in rows:
        ticket_code = str((row or {}).get("ticket_code") or "").strip()
        final_resolution = str((row or {}).get("final_resolution") or "").strip()
        details = str((row or {}).get("details") or "").strip()
        if not final_resolution or not details:
            continue
        if ticket_code and ticket_code in seen_keys:
            continue
        if ticket_code:
            seen_keys.add(ticket_code)
        examples.append(
            {
                "ticket_code": ticket_code,
                "ticket_type": str((row or {}).get("ticket_type") or ""),
                "priority": str((row or {}).get("priority") or ""),
                "subject": str((row or {}).get("subject") or ""),
                "details": details,
                "decision": str((row or {}).get("decision") or ""),
                "suggested_resolution": str((row or {}).get("suggested_resolution") or ""),
                "employee_resolution": str((row or {}).get("employee_resolution") or ""),
                "final_resolution": final_resolution,
                "created_at": str((row or {}).get("created_at") or ""),
            }
        )
        if len(examples) >= max_examples:
            break

    payload = {
        "updated_at": _utc_now_iso(),
        "examples": examples,
    }
    SUGGESTED_RESOLUTION_EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUGGESTED_RESOLUTION_EXAMPLES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "examples_written": len(examples),
        "feedback_rows": len(rows),
        "path": str(SUGGESTED_RESOLUTION_EXAMPLES_PATH),
    }


def retrain_resolution_examples_from_db(max_examples: int = 12) -> dict[str, Any]:
    max_examples = max(1, min(int(max_examples), 50))
    query = """
        SELECT
          trf.decision,
          trf.suggested_resolution,
          trf.employee_resolution,
          trf.final_resolution,
          trf.created_at,
          t.ticket_code,
          t.ticket_type,
          t.priority,
          t.subject,
          t.details
        FROM ticket_resolution_feedback trf
        JOIN tickets t ON t.id = trf.ticket_id
        WHERE trf.final_resolution IS NOT NULL
          AND btrim(trf.final_resolution) <> ''
        ORDER BY trf.created_at DESC
        LIMIT 500
    """
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in (cur.fetchall() or [])]
    return retrain_resolution_examples_from_rows(rows, max_examples=max_examples)


@lru_cache(maxsize=1)
def _load_suggested_resolution_model() -> dict[str, Any] | None:
    if not SUGGESTED_RESOLUTION_MODEL_PATH:
        return None

    model_path = Path(SUGGESTED_RESOLUTION_MODEL_PATH)
    if not (model_path / "config.json").exists() and SUGGESTED_RESOLUTION_AUTO_DOWNLOAD and SUGGESTED_RESOLUTION_MODEL_NAME:
        try:
            from huggingface_hub import snapshot_download  # type: ignore

            snapshot_download(
                repo_id=SUGGESTED_RESOLUTION_MODEL_NAME,
                local_dir=SUGGESTED_RESOLUTION_MODEL_PATH,
                token=HF_TOKEN,
            )
        except Exception as exc:
            logger.warning("suggested_resolution | auto-download failed (%s), using fallback", exc)

    if not (model_path / "config.json").exists():
        return None

    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

        tokenizer = AutoTokenizer.from_pretrained(
            SUGGESTED_RESOLUTION_MODEL_PATH,
            trust_remote_code=True,
            token=HF_TOKEN,
        )
        model = AutoModelForCausalLM.from_pretrained(
            SUGGESTED_RESOLUTION_MODEL_PATH,
            trust_remote_code=True,
            token=HF_TOKEN,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            low_cpu_mem_usage=True,
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        return {"tokenizer": tokenizer, "model": model, "device": device}
    except Exception as exc:
        logger.warning("suggested_resolution | model load failed (%s), using fallback", exc)
        return None


def _release_suggested_resolution_model() -> None:
    try:
        loaded = _load_suggested_resolution_model()
    except Exception:
        loaded = None
    try:
        if isinstance(loaded, dict):
            loaded.pop("model", None)
            loaded.pop("tokenizer", None)
    finally:
        _load_suggested_resolution_model.cache_clear()
        gc.collect()
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass


def get_suggested_resolution_diagnostics() -> dict[str, object]:
    model_path = Path(SUGGESTED_RESOLUTION_MODEL_PATH) if SUGGESTED_RESOLUTION_MODEL_PATH else None
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "suggested_resolution_model_path": SUGGESTED_RESOLUTION_MODEL_PATH or None,
        "suggested_resolution_model_name": SUGGESTED_RESOLUTION_MODEL_NAME or None,
        "suggested_resolution_auto_download": SUGGESTED_RESOLUTION_AUTO_DOWNLOAD,
        "suggested_resolution_model_exists": model_exists,
        "suggested_resolution_timeout_seconds": SUGGESTED_RESOLUTION_TIMEOUT_SECONDS,
        "suggested_resolution_examples_path": str(SUGGESTED_RESOLUTION_EXAMPLES_PATH),
        "suggested_resolution_mode": "model" if model_exists else "template",
    }


def _ticket_context_from_state(state: dict) -> dict[str, Any]:
    return {
        "ticket_code": state.get("ticket_id"),
        "ticket_type": "Inquiry" if str(state.get("label") or "").strip().lower() == "inquiry" else "Complaint",
        "priority": str(state.get("priority_label") or "Medium").strip().title(),
        "department_name": str(
            state.get("department")
            or state.get("department_selected")
            or "Unassigned"
        ).strip(),
        "subject": str(state.get("subject") or "").strip(),
        "details": str(state.get("text") or "").strip(),
        "asset_type": str(state.get("asset_type") or "General").strip(),
        "safety_concern": bool(state.get("safety_concern")),
        "is_recurring": bool(state.get("is_recurring")),
    }


async def _generate_resolution_text(ticket: dict[str, Any]) -> tuple[str, str, str]:
    loaded = _load_suggested_resolution_model()
    if loaded is None:
        return fallback_resolution_suggestion(ticket), "template_fallback", "template"

    try:
        import torch  # type: ignore

        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        device = loaded["device"]
        prompt = _build_generation_prompt(ticket)
        messages = [
            {
                "role": "system",
                "content": (
                    "You generate one suggested resolution for the employee handling the ticket. "
                    "Return plain text only."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        if hasattr(tokenizer, "apply_chat_template"):
            rendered_prompt = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            inputs = tokenizer([rendered_prompt], return_tensors="pt", truncation=True).to(device)
        else:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=40,
                do_sample=False,
                no_repeat_ngram_size=3,
                repetition_penalty=1.2,
                use_cache=torch.cuda.is_available(),
            )
        prompt_tokens = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0][prompt_tokens:] if output_ids.shape[1] > prompt_tokens else output_ids[0]
        text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        text = _clean_generated_resolution(text, ticket)
        if text and not _is_low_quality_resolution(text):
            return text, (SUGGESTED_RESOLUTION_MODEL_NAME or "local_causal_lm"), "local_model"
        logger.warning("suggested_resolution | generated empty output, using fallback")
    except Exception as exc:
        logger.warning("suggested_resolution | local model inference failed (%s), using fallback", exc)

    return fallback_resolution_suggestion(ticket), "template_fallback", "template"


async def _generate_resolution_text_in_thread(ticket: dict[str, Any]) -> tuple[str, str, str]:
    return await asyncio.to_thread(lambda: asyncio.run(_generate_resolution_text(ticket)))


async def _persist_suggested_resolution(state: dict) -> None:
    payload = {
        "ticket_id": state.get("ticket_id"),
        "subject": state.get("subject"),
        "transcript": state.get("text"),
        "priority": state.get("priority_score"),
        "department": state.get("department") or state.get("department_selected"),
        "label": state.get("label"),
        "status": state.get("status"),
        "suggested_resolution": state.get("suggested_resolution"),
        "suggested_resolution_model": state.get("suggested_resolution_model"),
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(f"{BACKEND_URL}/api/complaints", json=payload)
        response.raise_for_status()


async def _complete_suggested_resolution_in_background(base_state: dict[str, Any], task: asyncio.Task) -> None:
    ticket_id = str(base_state.get("ticket_id") or "").strip()
    try:
        suggestion, model_label, mode = await task
        if not suggestion:
            return
        background_state = dict(base_state)
        background_state["suggested_resolution"] = suggestion
        background_state["suggested_resolution_model"] = model_label
        background_state["suggested_resolution_mode"] = mode
        await _persist_suggested_resolution(background_state)
        logger.info(
            "suggested_resolution | background completion persisted ticket_id=%s model=%s",
            ticket_id,
            model_label,
        )
    except Exception as exc:
        logger.warning(
            "suggested_resolution | background completion failed ticket_id=%s err=%s",
            ticket_id,
            exc,
        )
    finally:
        if UNLOAD_SUGGESTED_RESOLUTION_MODEL_AFTER_USE:
            _release_suggested_resolution_model()
        _BACKGROUND_SUGGESTED_RESOLUTION_TASKS.discard(task)


async def generate_suggested_resolution(state: dict) -> dict:
    ticket_id = str(state.get("ticket_id") or "").strip()
    if not ticket_id:
        return state
    if str(state.get("label") or "").strip().lower() == "inquiry":
        state["suggested_resolution"] = None
        state["suggested_resolution_model"] = None
        state["suggested_resolution_mode"] = "skipped"
        return state

    ticket = _ticket_context_from_state(state)
    base_state = dict(state)
    generation_task = asyncio.create_task(_generate_resolution_text_in_thread(ticket))
    try:
        try:
            suggestion, model_label, mode = await asyncio.wait_for(
                asyncio.shield(generation_task),
                timeout=SUGGESTED_RESOLUTION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "suggested_resolution | timed out after %.1fs ticket_id=%s; continuing in background",
                SUGGESTED_RESOLUTION_TIMEOUT_SECONDS,
                ticket_id,
            )
            state["suggested_resolution"] = None
            state["suggested_resolution_model"] = None
            state["suggested_resolution_mode"] = "timeout_background"
            followup_task = asyncio.create_task(
                _complete_suggested_resolution_in_background(base_state, generation_task)
            )
            _BACKGROUND_SUGGESTED_RESOLUTION_TASKS.add(followup_task)
            followup_task.add_done_callback(_BACKGROUND_SUGGESTED_RESOLUTION_TASKS.discard)
            return state

        state["suggested_resolution"] = suggestion
        state["suggested_resolution_model"] = model_label
        state["suggested_resolution_mode"] = mode

        try:
            await _persist_suggested_resolution(state)
        except Exception as exc:
            logger.warning("suggested_resolution | failed to persist ticket_id=%s err=%s", ticket_id, exc)
            return state
    finally:
        if UNLOAD_SUGGESTED_RESOLUTION_MODEL_AFTER_USE and generation_task.done():
            _release_suggested_resolution_model()

    logger.info(
        "suggested_resolution | ticket_id=%s model=%s",
        ticket_id,
        state.get("suggested_resolution_model"),
    )
    return state


suggested_resolution_step = RunnableLambda(generate_suggested_resolution)
