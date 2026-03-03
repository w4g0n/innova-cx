import uuid
import json
from datetime import datetime, timezone

from sqlalchemy import text

from .db import engine

VALID_CATEGORIES = {"inquiry", "complaint"}


def _predict_is_recurring(*, user_id: str, subject: str, details: str) -> bool:
    """
    Uses the shared SQL function compute_is_recurring_ticket(...) when available.
    Falls back to False if DB function is missing or query fails.
    """
    if not user_id:
        return False
    try:
        with engine.begin() as conn:
            exists_row = conn.execute(
                text(
                    "SELECT to_regprocedure('compute_is_recurring_ticket(uuid,text,text,integer)') "
                    "IS NOT NULL AS exists"
                )
            ).mappings().first() or {}
            if not bool(exists_row.get("exists")):
                return False

            result = conn.execute(
                text(
                    "SELECT compute_is_recurring_ticket("
                    "CAST(:user_id AS uuid), :subject, :details"
                    ") AS is_recurring"
                ),
                {
                    "user_id": user_id,
                    "subject": subject or "",
                    "details": details or "",
                },
            ).mappings().first() or {}
            return bool(result.get("is_recurring"))
    except Exception:
        return False


def create_ticket(
    user_id: str,
    session_id: str,
    category: str,
    description: str,
    title: str = "",
) -> dict:
    category = category.strip().lower()

    if category not in VALID_CATEGORIES:
        return {"success": False, "ticket_id": None, "error": f"Invalid category: {category}"}
    if not description.strip():
        return {"success": False, "ticket_id": None, "error": "Description cannot be empty"}

    ticket_id = str(uuid.uuid4())
    if not title:
        title = description[:80]

    ticket_code = f"CX-{uuid.uuid4().hex[:10].upper()}"
    ticket_type = "Inquiry" if category == "inquiry" else "Complaint"
    status = "Open"
    is_recurring = _predict_is_recurring(user_id=user_id, subject=title, details=description)
    model_suggestion = json.dumps({"is_recurring": is_recurring})

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tickets "
                    "(id, ticket_code, subject, details, ticket_type, status, created_by_user_id, model_suggestion, ticket_source, created_at, updated_at) "
                    "VALUES (:tid, :code, :subject, :details, :type, :status, :uid, :suggestion, :source, :now, :now)"
                ),
                {
                    "tid": ticket_id,
                    "code": ticket_code,
                    "subject": title,
                    "details": description,
                    "type": ticket_type,
                    "status": status,
                    "uid": user_id,
                    "suggestion": model_suggestion,
                    "source": "chatbot",
                    "now": datetime.now(timezone.utc),
                },
            )
    except Exception as e:
        return {"success": False, "ticket_id": None, "error": str(e)}

    return {"success": True, "ticket_id": ticket_code, "error": None, "is_recurring": is_recurring}
