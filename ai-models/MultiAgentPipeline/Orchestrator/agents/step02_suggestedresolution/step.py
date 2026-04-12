"""
Step 2 — Suggested Resolution Agent
====================================
Generates suggested resolution in the orchestrator using the shared Qwen
model (loaded via shared_model_service), with a deterministic template
fallback if unavailable.

Learning examples are read directly from the suggested_resolution_usage
table so prompt guidance stays in SQL.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from langchain_core.runnables import RunnableLambda
from db import db_connect
from backend_client import internal_backend_headers

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
SUGGESTED_RESOLUTION_PROMPT_EXAMPLES = max(
    0,
    int(os.getenv("SUGGESTED_RESOLUTION_PROMPT_EXAMPLES", "1")),
)
SUGGESTED_RESOLUTION_TIMEOUT_SECONDS = max(
    1.0,
    float(os.getenv("SUGGESTED_RESOLUTION_TIMEOUT_SECONDS", "60")),
)
SUGGESTED_RESOLUTION_MAX_INPUT_CHARS = max(
    80,
    int(os.getenv("SUGGESTED_RESOLUTION_MAX_INPUT_CHARS", "240")),
)
SUGGESTED_RESOLUTION_MAX_PROMPT_TOKENS = max(
    128,
    int(os.getenv("SUGGESTED_RESOLUTION_MAX_PROMPT_TOKENS", "256")),
)
SUGGESTED_RESOLUTION_MAX_NEW_TOKENS = max(
    8,
    int(os.getenv("SUGGESTED_RESOLUTION_MAX_NEW_TOKENS", "14")),
)

logger = logging.getLogger(__name__)
_BACKGROUND_SUGGESTED_RESOLUTION_TASKS: set[asyncio.Task] = set()
_PROMPT_LEAKAGE_FRAGMENTS: tuple[str, ...] = (
    "employee-accepted patterns",
    "employee-accepted outcome",
    "tone of each pattern",
    "reply json only",
    "ticket subject:",
    "ticket text:",
    "preferred instruction style:",
    "avoid these rejected phrasing patterns",
    "rejected example",
    "better outcome:",
)


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
        department = "Facilities Management"
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
    cleaned = re.sub(
        r"(?:^|\s)(?:subject|details|ticket|ticket subject|ticket text|input|output)\s*:\s*.*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" -")


def _contains_prompt_leakage(text: str) -> bool:
    cleaned = str(text or "").strip().lower()
    if not cleaned:
        return False
    return any(fragment in cleaned for fragment in _PROMPT_LEAKAGE_FRAGMENTS)


def _looks_like_past_tense_resolution(text: str) -> bool:
    cleaned = str(text or "").strip().lower()
    if not cleaned:
        return False
    past_tense_markers = (
        " replaced",
        " repaired",
        " restored",
        " checked",
        " inspected",
        " resolved",
        " completed",
        " fixed",
        " dispatched",
        " escalated",
        " verified",
        " assigned",
        " was ",
        " were ",
        " has been ",
        " have been ",
    )
    prefixed = f" {cleaned}"
    return any(marker in prefixed for marker in past_tense_markers)


def _is_low_quality_resolution(text: str) -> bool:
    cleaned = str(text or "").strip().lower()
    if not cleaned:
        return True
    if _contains_prompt_leakage(cleaned):
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
    if _looks_like_past_tense_resolution(cleaned):
        return True
    return len(cleaned.split()) < 8


def _compact_prompt_text(value: object, limit: int = SUGGESTED_RESOLUTION_MAX_INPUT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].strip()


def _load_resolution_examples(limit: int = 3, department: str | None = None) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                if department:
                    cur.execute(
                        """
                        SELECT
                          sru.department,
                          sru.suggested_text AS suggested_resolution,
                          sru.final_text AS final_resolution,
                          sru.created_at,
                          t.ticket_code,
                          t.ticket_type,
                          t.priority,
                          t.subject,
                          t.details
                        FROM suggested_resolution_usage sru
                        JOIN tickets t ON t.id = sru.ticket_id
                        WHERE sru.used = TRUE
                          AND sru.department = %s
                          AND sru.final_text IS NOT NULL
                          AND btrim(sru.final_text) <> ''
                          AND sru.created_at >= now() - INTERVAL '3 months'
                        ORDER BY sru.created_at DESC
                        LIMIT %s
                        """,
                        (department, limit),
                    )
                    rows = cur.fetchall() or []
                    if rows:
                        cols = [desc[0] for desc in cur.description]
                        return [dict(zip(cols, row)) for row in rows]

                cur.execute(
                    """
                    SELECT
                      sru.department,
                      sru.suggested_text AS suggested_resolution,
                      sru.final_text AS final_resolution,
                      sru.created_at,
                      t.ticket_code,
                      t.ticket_type,
                      t.priority,
                      t.subject,
                      t.details
                    FROM suggested_resolution_usage sru
                    JOIN tickets t ON t.id = sru.ticket_id
                    WHERE sru.used = TRUE
                      AND sru.final_text IS NOT NULL
                      AND btrim(sru.final_text) <> ''
                      AND sru.created_at >= now() - INTERVAL '3 months'
                    ORDER BY sru.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
    except Exception as exc:
        logger.warning("suggested_resolution | failed loading prompt examples from DB (%s)", exc)
        return []


def _load_declined_resolution_examples(limit: int = 2, department: str | None = None) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                if department:
                    cur.execute(
                        """
                        SELECT
                          sru.department,
                          sru.suggested_text AS suggested_resolution,
                          sru.final_text AS final_resolution,
                          sru.created_at,
                          t.ticket_code,
                          t.ticket_type,
                          t.priority,
                          t.subject,
                          t.details
                        FROM suggested_resolution_usage sru
                        JOIN tickets t ON t.id = sru.ticket_id
                        WHERE sru.used = FALSE
                          AND sru.department = %s
                          AND sru.suggested_text IS NOT NULL
                          AND btrim(sru.suggested_text) <> ''
                          AND sru.final_text IS NOT NULL
                          AND btrim(sru.final_text) <> ''
                          AND sru.created_at >= now() - INTERVAL '3 months'
                        ORDER BY sru.created_at DESC
                        LIMIT %s
                        """,
                        (department, limit),
                    )
                    rows = cur.fetchall() or []
                    if rows:
                        cols = [desc[0] for desc in cur.description]
                        return [dict(zip(cols, row)) for row in rows]

                cur.execute(
                    """
                    SELECT
                      sru.department,
                      sru.suggested_text AS suggested_resolution,
                      sru.final_text AS final_resolution,
                      sru.created_at,
                      t.ticket_code,
                      t.ticket_type,
                      t.priority,
                      t.subject,
                      t.details
                    FROM suggested_resolution_usage sru
                    JOIN tickets t ON t.id = sru.ticket_id
                    WHERE sru.used = FALSE
                      AND sru.suggested_text IS NOT NULL
                      AND btrim(sru.suggested_text) <> ''
                      AND sru.final_text IS NOT NULL
                      AND btrim(sru.final_text) <> ''
                      AND sru.created_at >= now() - INTERVAL '3 months'
                    ORDER BY sru.created_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in (cur.fetchall() or [])]
    except Exception as exc:
        logger.warning("suggested_resolution | failed loading declined examples from DB (%s)", exc)
        return []


def _format_examples_for_prompt(limit: int, department: str | None = None) -> str:
    examples = _load_resolution_examples(limit=limit, department=department)
    if not examples:
        return ""
    lines = []
    for i, ex in enumerate(examples, start=1):
        subject = _compact_prompt_text(ex.get("subject"), 120) or "No subject"
        details = _compact_prompt_text(ex.get("details")) or "No details"
        resolution = _compact_prompt_text(ex.get("final_resolution"), 180) or "No resolution"
        lines.append(
            (
                f"Example {i}\n"
                f"Input: type={ex.get('ticket_type')}; priority={ex.get('priority')}; subject={subject}; details={details}\n"
                f"Preferred instruction style: {resolution}"
            )
        )
    return "\n\n".join(lines)


def _format_learning_rules_for_prompt(limit: int, department: str | None = None) -> str:
    examples = _load_resolution_examples(limit=limit, department=department)
    if not examples:
        return ""
    lines = []
    for i, ex in enumerate(examples, start=1):
        resolution = _compact_prompt_text(ex.get("final_resolution"), 180)
        if not resolution:
            continue
        lines.append(f"{i}. Employee-accepted outcome: {resolution}")
    return "\n".join(lines)


def _format_declined_examples_for_prompt(limit: int, department: str | None = None) -> str:
    examples = _load_declined_resolution_examples(limit=limit, department=department)
    if not examples:
        return ""
    lines = []
    for i, ex in enumerate(examples, start=1):
        subject = _compact_prompt_text(ex.get("subject"), 120) or "No subject"
        details = _compact_prompt_text(ex.get("details")) or "No details"
        suggested = _compact_prompt_text(ex.get("suggested_resolution"), 180) or "No suggestion"
        final_resolution = _compact_prompt_text(ex.get("final_resolution"), 180) or "No final resolution"
        lines.append(
            (
                f"Rejected Example {i}\n"
                f"Input: type={ex.get('ticket_type')}; priority={ex.get('priority')}; subject={subject}; details={details}\n"
                f"Avoid suggestion: {suggested}\n"
                f"Better outcome: {final_resolution}"
            )
        )
    return "\n\n".join(lines)


def _build_generation_prompt(ticket: dict[str, Any]) -> str:
    details = _compact_prompt_text(ticket.get("details")) or "No details"
    department = str(ticket.get("department_name") or "").strip() or None

    prompt = (
        "Write one resolution sentence for a support employee handling the following facilities ticket.\n\n"
        "Rules:\n"
        "1. Use imperative style with direct action verbs like \"check,\" \"replace,\" \"isolate,\" \"dispatch,\" or \"confirm.\"\n"
        "2. Begin with the first containment or triage action.\n"
        "3. Name the responsible team (infer from the issue if not stated).\n"
        "4. End with a verification step.\n"
        "5. For fire, flooding, gas, smoke, exposed wiring, or injury risk: lead with isolation or evacuation before any other step.\n"
        "6. Do not repeat ticket wording verbatim.\n"
        "7. Do not use vague terms like \"appropriate team,\" \"someone should,\" or \"investigate the issue.\"\n"
        "8. Do not write in past tense. Avoid phrases like \"replaced,\" \"checked,\" \"repaired,\" or \"restored.\"\n"
        "9. Describe what the employee should do next, not what has already been done.\n"
        "10. If there are multiple actions, connect them in one sentence with \"then\" or \"and\".\n"
        "11. Length: 18–40 words.\n\n"
        "12. Return only the final resolution sentence.\n"
        "13. Do not output prompt headers, examples, labels, JSON, or notes.\n\n"
    )

    if SUGGESTED_RESOLUTION_PROMPT_EXAMPLES > 0:
        learning_rules = _format_learning_rules_for_prompt(
            min(2, SUGGESTED_RESOLUTION_PROMPT_EXAMPLES),
            department=department,
        )
        if learning_rules:
            prompt += (
                "Employee-accepted patterns:\n"
                "Match the specificity, action order, and instruction style below unless the current ticket facts clearly require something different.\n\n"
                f"{learning_rules}\n\n"
            )

        declined_examples = _format_declined_examples_for_prompt(
            min(1, SUGGESTED_RESOLUTION_PROMPT_EXAMPLES),
            department=department,
        )
        if declined_examples:
            prompt += (
                "Avoid these rejected phrasing patterns; prefer the better outcomes shown instead.\n\n"
                f"{declined_examples}\n\n"
            )

    prompt += f"Ticket: {details}"
    return prompt

def retrain_resolution_examples_from_db(max_examples: int = 12) -> dict[str, Any]:
    """
    Compatibility hook for callers that still hit the legacy refresh endpoint.
    Prompt examples are already loaded directly from suggested_resolution_usage,
    so this returns a learning-data summary instead of rebuilding cached files.
    """
    max_examples = max(1, min(int(max_examples), 50))
    query = """
        SELECT
          sru.department,
          sru.suggested_text  AS suggested_resolution,
          sru.final_text      AS final_resolution,
          sru.created_at,
          t.ticket_code,
          t.ticket_type,
          t.priority,
          t.subject,
          t.details
        FROM suggested_resolution_usage sru
        JOIN tickets t ON t.id = sru.ticket_id
        WHERE sru.used = TRUE
          AND sru.final_text IS NOT NULL
          AND btrim(sru.final_text) <> ''
          AND sru.created_at >= now() - INTERVAL '3 months'
        ORDER BY sru.created_at DESC
        LIMIT 1000
    """
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in (cur.fetchall() or [])]

    if not rows:
        return {
            "ok": True,
            "learning_source": "suggested_resolution_usage",
            "departments_available": 0,
            "total_rows": 0,
            "reason": "no_usage_rows",
        }

    by_dept: dict[str, int] = {}
    for row in rows:
        dept = str(row.get("department") or "General").strip()
        by_dept[dept] = by_dept.get(dept, 0) + 1

    return {
        "ok": True,
        "learning_source": "suggested_resolution_usage",
        "departments_available": len(by_dept),
        "departments": sorted(by_dept.keys()),
        "total_rows": len(rows),
        "max_examples": max_examples,
    }


def _get_model() -> dict[str, Any] | None:
    try:
        from shared_model_service import get_shared_qwen
        return get_shared_qwen()
    except Exception as exc:
        logger.warning("suggested_resolution | shared model service unavailable (%s)", exc)
        return None


def get_suggested_resolution_diagnostics() -> dict[str, object]:
    try:
        from shared_model_service import SHARED_QWEN_MODEL_PATH
        model_path = Path(SHARED_QWEN_MODEL_PATH) if SHARED_QWEN_MODEL_PATH else None
        model_name = os.getenv("SHARED_QWEN_MODEL_NAME", "Qwen2.5")
    except Exception:
        model_path = None
        model_name = None
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "suggested_resolution_model_path": str(model_path) if model_path else None,
        "suggested_resolution_model_name": model_name,
        "suggested_resolution_model_exists": model_exists,
        "suggested_resolution_timeout_seconds": SUGGESTED_RESOLUTION_TIMEOUT_SECONDS,
        "suggested_resolution_prompt_examples": SUGGESTED_RESOLUTION_PROMPT_EXAMPLES,
        "suggested_resolution_max_prompt_tokens": SUGGESTED_RESOLUTION_MAX_PROMPT_TOKENS,
        "suggested_resolution_max_new_tokens": SUGGESTED_RESOLUTION_MAX_NEW_TOKENS,
        "suggested_resolution_learning_source": "suggested_resolution_usage",
        "suggested_resolution_mode": "model" if model_exists else "unavailable",
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


async def _generate_resolution_text(ticket: dict[str, Any]) -> tuple[str | None, str | None, str]:
    """Returns (text, model_label, mode). text is None when model unavailable."""
    loaded = _get_model()
    if loaded is None:
        return None, None, "unavailable"

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
                    "Return plain text only. "
                    "Output exactly one actionable sentence and never repeat prompt sections, labels, examples, or ticket headers."
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
            inputs = tokenizer(
                [rendered_prompt],
                return_tensors="pt",
                truncation=True,
                max_length=SUGGESTED_RESOLUTION_MAX_PROMPT_TOKENS,
            ).to(device)
        else:
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=SUGGESTED_RESOLUTION_MAX_PROMPT_TOKENS,
            ).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=SUGGESTED_RESOLUTION_MAX_NEW_TOKENS,
                do_sample=False,
                no_repeat_ngram_size=3,
                repetition_penalty=1.2,
                use_cache=True,
            )
        prompt_tokens = inputs["input_ids"].shape[1]
        generated_ids = output_ids[0][prompt_tokens:] if output_ids.shape[1] > prompt_tokens else output_ids[0]
        text = tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
        text = _clean_generated_resolution(text, ticket)
        if text and not _is_low_quality_resolution(text):
            try:
                from shared_model_service import SHARED_QWEN_MODEL_NAME
                model_label = SHARED_QWEN_MODEL_NAME or "Qwen2.5"
            except Exception:
                model_label = "Qwen2.5"
            return text, model_label, "qwen"
        logger.warning("suggested_resolution | generated low-quality output, using deterministic fallback")
    except Exception as exc:
        logger.warning("suggested_resolution | inference failed (%s), using deterministic fallback", exc)

    return fallback_resolution_suggestion(ticket), "deterministic_template", "template_fallback"


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
        response = await client.post(
            f"{BACKEND_URL}/api/complaints",
            json=payload,
            headers=internal_backend_headers(),
        )
        response.raise_for_status()


def _write_background_stage_event(base_state: dict[str, Any], output_state: dict[str, Any]) -> None:
    execution_id = str(base_state.get("_execution_id") or "").strip()
    ticket_id = str(base_state.get("ticket_id") or "").strip() or None
    ticket_code = str(base_state.get("ticket_code") or base_state.get("ticket_id") or "").strip() or None
    if not execution_id or not ticket_code:
        return

    from execution_logger import _write_stage_event

    input_snapshot = {k: v for k, v in base_state.items() if not str(k).startswith("_")}
    output_snapshot = {k: v for k, v in output_state.items() if not str(k).startswith("_")}
    _write_stage_event(
        execution_id=execution_id,
        ticket_id=ticket_id,
        ticket_code=ticket_code,
        agent_name="SuggestedResolutionAgent",
        step_order=3,
        event_type="output",
        status="fixed",
        input_state=input_snapshot,
        output_state=output_snapshot,
        inference_time_ms=None,
        confidence_score=None,
        error_message=None,
    )


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
        _write_background_stage_event(base_state, background_state)
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
    except Exception as exc:
        logger.warning("suggested_resolution | generation failed ticket_id=%s err=%s", ticket_id, exc)
        return state
    logger.info(
        "suggested_resolution | ticket_id=%s model=%s",
        ticket_id,
        state.get("suggested_resolution_model"),
    )
    return state


suggested_resolution_step = RunnableLambda(generate_suggested_resolution)
