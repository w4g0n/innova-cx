"""
Step 11 — Suggested Resolution Agent
====================================
Generates suggested resolution inside the orchestrator using a local model
when present, otherwise a deterministic fallback template.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
    "google/flan-t5-small",
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
    cleaned = re.sub(r"^(suggested resolution|resolution)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


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
    subject = str(ticket.get("subject") or "").strip() or "No subject"
    details = str(ticket.get("details") or "").strip() or "No details"
    ticket_type = str(ticket.get("ticket_type") or "Complaint").strip()
    priority = str(ticket.get("priority") or "Medium").strip()
    department = str(ticket.get("department_name") or "Unassigned").strip()
    asset_type = str(ticket.get("asset_type") or "General").strip()
    safety_flag = bool(ticket.get("safety_concern"))
    recurring_flag = bool(ticket.get("is_recurring"))
    department_hint = department if department and department.lower() not in {"general", "unassigned"} else "infer from issue"

    prompt = (
        "Task: write one concise suggested resolution for a support employee handling a facilities/service ticket.\n"
        "Rules:\n"
        "- Write only the resolution.\n"
        "- Write one sentence in imperative style.\n"
        "- Start with the first containment or triage action.\n"
        "- Then name the responsible team.\n"
        "- End with a verification step.\n"
        "- For fire, exposed electrical wire, leak, flooding, gas, smoke, or injury risk: prioritize immediate isolation and site safety.\n"
        "- If department is unknown, infer the most likely team from the issue instead of saying General or Unassigned.\n"
        "- Do not repeat the subject or quote the ticket details verbatim.\n"
        "- Do not write labels like Subject:, Details:, Ticket:, Input:, or Output:.\n"
        "- Do not mention the priority explicitly in the answer.\n"
        "- Do not use placeholders like General team, appropriate team, relevant department, someone should, or investigate issue.\n"
        "- Keep it between 18 and 40 words.\n\n"
    )

    learned_examples = _format_examples_for_prompt(SUGGESTED_RESOLUTION_PROMPT_EXAMPLES)
    if learned_examples:
        prompt += f"{learned_examples}\n\n"

    prompt += (
        "Input: "
        f"type={ticket_type}; "
        f"priority={priority}; "
        f"department_hint={department_hint}; "
        f"asset_type={asset_type}; "
        f"safety_concern={'true' if safety_flag else 'false'}; "
        f"is_recurring={'true' if recurring_flag else 'false'}; "
        f"subject={subject}; "
        f"details={details}\n"
        "Output:"
    )
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
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore

        tokenizer = AutoTokenizer.from_pretrained(SUGGESTED_RESOLUTION_MODEL_PATH)
        model = AutoModelForSeq2SeqLM.from_pretrained(SUGGESTED_RESOLUTION_MODEL_PATH)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = model.to(device)
        return {"tokenizer": tokenizer, "model": model, "device": device}
    except Exception as exc:
        logger.warning("suggested_resolution | model load failed (%s), using fallback", exc)
        return None


def get_suggested_resolution_diagnostics() -> dict[str, object]:
    model_path = Path(SUGGESTED_RESOLUTION_MODEL_PATH) if SUGGESTED_RESOLUTION_MODEL_PATH else None
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "suggested_resolution_model_path": SUGGESTED_RESOLUTION_MODEL_PATH or None,
        "suggested_resolution_model_name": SUGGESTED_RESOLUTION_MODEL_NAME or None,
        "suggested_resolution_auto_download": SUGGESTED_RESOLUTION_AUTO_DOWNLOAD,
        "suggested_resolution_model_exists": model_exists,
        "suggested_resolution_examples_path": str(SUGGESTED_RESOLUTION_EXAMPLES_PATH),
        "suggested_resolution_mode": "model" if model_exists else "template",
    }


def get_resolution_model_label() -> str:
    loaded = _load_suggested_resolution_model()
    if loaded is None:
        return "mock_template"
    if SUGGESTED_RESOLUTION_MODEL_NAME:
        return SUGGESTED_RESOLUTION_MODEL_NAME
    model_path = Path(SUGGESTED_RESOLUTION_MODEL_PATH)
    return model_path.name or "local_seq2seq"


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


def _generate_resolution_text(ticket: dict[str, Any]) -> str:
    loaded = _load_suggested_resolution_model()
    if loaded is None:
        return fallback_resolution_suggestion(ticket)

    try:
        import torch  # type: ignore

        prompt = _build_generation_prompt(ticket)
        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        device = loaded["device"]
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=96,
                min_new_tokens=12,
                do_sample=True,
                temperature=0.3,
                top_p=0.9,
                num_beams=4,
                no_repeat_ngram_size=3,
                repetition_penalty=1.2,
                early_stopping=True,
            )
        text = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        text = _clean_generated_resolution(text, ticket)
        if text:
            return text
        logger.warning("suggested_resolution | generated empty output, using fallback")
    except Exception as exc:
        logger.warning("suggested_resolution | local model inference failed (%s), using fallback", exc)

    return fallback_resolution_suggestion(ticket)


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
    suggestion = _generate_resolution_text(ticket)
    state["suggested_resolution"] = suggestion
    state["suggested_resolution_model"] = get_resolution_model_label()
    state["suggested_resolution_mode"] = get_suggested_resolution_diagnostics().get("suggested_resolution_mode", "template")

    try:
        await _persist_suggested_resolution(state)
    except Exception as exc:
        logger.warning("suggested_resolution | failed to persist ticket_id=%s err=%s", ticket_id, exc)
        return state

    logger.info(
        "suggested_resolution | ticket_id=%s model=%s",
        ticket_id,
        state.get("suggested_resolution_model"),
    )
    return state


suggested_resolution_step = RunnableLambda(generate_suggested_resolution)
