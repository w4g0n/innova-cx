from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, List

HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
SUGGESTED_RESOLUTION_MODEL_PATH = os.getenv(
    "SUGGESTED_RESOLUTION_MODEL_PATH",
    "",
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
        "/app/data/suggested_resolution_examples.json",
    ).strip()
)
SUGGESTED_RESOLUTION_PROMPT_EXAMPLES = max(
    0,
    int(os.getenv("SUGGESTED_RESOLUTION_PROMPT_EXAMPLES", "3")),
)


def fallback_resolution_suggestion(ticket: Dict[str, Any]) -> str:
    department = str(ticket.get("department_name") or "operations").strip()
    asset_type = str(ticket.get("asset_type") or "general infrastructure").strip()
    priority = str(ticket.get("priority") or "Medium").strip()
    details = str(ticket.get("details") or "").strip()
    symptom = "reported issue"
    if details:
        symptom_tokens = re.findall(r"[A-Za-z0-9]+", details)
        if symptom_tokens:
            symptom = " ".join(symptom_tokens[:8]).lower()
    return (
        f"Verify and stabilize the {asset_type} issue ({symptom}); "
        f"assign to {department} for root-cause remediation and confirm service recovery. "
        f"Priority: {priority}."
    )


def _load_resolution_examples(limit: int = 3) -> List[Dict[str, Any]]:
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
        lines.append(
            (
                f"Example {i}\n"
                f"Type: {ex.get('ticket_type')}\n"
                f"Priority: {ex.get('priority')}\n"
                f"Subject: {ex.get('subject')}\n"
                f"Details: {ex.get('details')}\n"
                f"Final Resolution: {ex.get('final_resolution')}"
            )
        )
    return "\n\n".join(lines)


@lru_cache(maxsize=1)
def _load_suggested_resolution_model() -> Optional[Dict[str, Any]]:
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
        except Exception:
            return None

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
    except Exception:
        return None


def get_resolution_model_label() -> str:
    loaded = _load_suggested_resolution_model()
    if loaded is None:
        return "mock_template"
    if SUGGESTED_RESOLUTION_MODEL_NAME:
        return SUGGESTED_RESOLUTION_MODEL_NAME
    model_path = Path(SUGGESTED_RESOLUTION_MODEL_PATH)
    return model_path.name or "local_seq2seq"


def retrain_resolution_examples_from_rows(rows: List[Dict[str, Any]], max_examples: int = 12) -> Dict[str, Any]:
    max_examples = max(1, min(int(max_examples), 50))
    if not rows:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "examples": []}
        SUGGESTED_RESOLUTION_EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUGGESTED_RESOLUTION_EXAMPLES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "examples_written": 0, "feedback_rows": 0, "reason": "no_feedback_rows"}

    examples: List[Dict[str, Any]] = []
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
                "created_at": (
                    row.get("created_at").isoformat()
                    if isinstance(row, dict) and row.get("created_at") is not None and hasattr(row.get("created_at"), "isoformat")
                    else None
                ),
            }
        )
        if len(examples) >= max_examples:
            break

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
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


def generate_resolution_suggestion(ticket: Dict[str, Any], logger) -> str:
    loaded = _load_suggested_resolution_model()
    if loaded is None:
        return fallback_resolution_suggestion(ticket)

    try:
        import torch  # type: ignore

        prompt = (
            "Generate one practical, safe, concise suggested resolution for a support employee. "
            "Include verification/closure steps. Keep under 120 words. Output plain text only.\n\n"
            f"Ticket: {ticket.get('ticket_code')}\n"
            f"Type: {ticket.get('ticket_type') or 'Complaint'}\n"
            f"Priority: {ticket.get('priority') or 'Medium'}\n"
            f"Department: {ticket.get('department_name') or 'General'}\n"
            f"Subject: {ticket.get('subject') or 'No subject'}\n"
            f"Details: {ticket.get('details') or ''}\n"
        )
        learned_examples = _format_examples_for_prompt(SUGGESTED_RESOLUTION_PROMPT_EXAMPLES)
        if learned_examples:
            prompt += f"\nUse these successful examples as style guidance:\n{learned_examples}\n"
        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        device = loaded["device"]
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=160,
                do_sample=False,
                num_beams=4,
            )
        text = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("suggested_resolution | dedicated model failed, using fallback err=%s", exc)

    return fallback_resolution_suggestion(ticket)
