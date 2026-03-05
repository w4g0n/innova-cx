import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from .db import engine

EXAMPLES_PATH = Path(__file__).parent / "data" / "resolution_examples.json"


def _table_exists(table_name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT to_regclass(:tbl) IS NOT NULL AS exists"),
            {"tbl": f"public.{table_name}"},
        ).fetchone()
    return bool(row and row.exists)


def retrain_resolution_examples(max_examples: int = 12) -> dict:
    """
    Lightweight retraining:
    build a curated few-shot examples file from historical employee outcomes.
    """
    max_examples = max(1, min(int(max_examples), 50))

    if not _table_exists("ticket_resolution_feedback"):
        return {"ok": True, "examples_written": 0, "feedback_rows": 0, "reason": "feedback_table_missing"}

    query = text(
        """
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
    )
    with engine.connect() as conn:
        rows = conn.execute(query).fetchall()

    if not rows:
        payload = {"updated_at": datetime.now(timezone.utc).isoformat(), "examples": []}
        EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXAMPLES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"ok": True, "examples_written": 0, "feedback_rows": 0, "reason": "no_feedback_rows"}

    examples: list[dict] = []
    seen_keys: set[str] = set()
    for row in rows:
        ticket_code = str(row.ticket_code or "").strip()
        final_resolution = str(row.final_resolution or "").strip()
        details = str(row.details or "").strip()
        if not final_resolution or not details:
            continue

        # Prefer one example per ticket to reduce overfitting/memorization.
        if ticket_code and ticket_code in seen_keys:
            continue
        if ticket_code:
            seen_keys.add(ticket_code)

        examples.append(
            {
                "ticket_code": ticket_code,
                "ticket_type": str(row.ticket_type or ""),
                "priority": str(row.priority or ""),
                "subject": str(row.subject or ""),
                "details": details,
                "decision": str(row.decision or ""),
                "suggested_resolution": str(row.suggested_resolution or ""),
                "employee_resolution": str(row.employee_resolution or ""),
                "final_resolution": final_resolution,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
        if len(examples) >= max_examples:
            break

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "examples": examples,
    }
    EXAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLES_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "examples_written": len(examples),
        "feedback_rows": len(rows),
        "path": str(EXAMPLES_PATH),
    }


def load_resolution_examples(limit: int = 4) -> list[dict]:
    if not EXAMPLES_PATH.exists():
        return []
    try:
        payload = json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    examples = payload.get("examples") if isinstance(payload, dict) else []
    if not isinstance(examples, list):
        return []
    return examples[: max(0, int(limit))]


def format_examples_for_prompt(limit: int = 4) -> str:
    examples = load_resolution_examples(limit=limit)
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
