import os
import re
from datetime import datetime

from sqlalchemy import create_engine, text

from .db import DATABASE_URL

READONLY_DB_URL = os.environ.get("READONLY_DATABASE_URL") or DATABASE_URL
_ro_engine = create_engine(READONLY_DB_URL, pool_pre_ping=True)

OPEN_TICKET_LIMIT = 20


def _format_ts(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else "-"


def _clean_subject(value) -> str:
    subject = str(value or "No subject").strip()
    # Keep response layout stable and one ticket per row.
    subject = re.sub(r"\s+", " ", subject)
    subject = subject.replace("|", "/")
    return subject or "No subject"


def _fetch_open_ticket_rows(user_id: str):
    query = (
        "SELECT ticket_code, subject, status, created_at "
        "FROM tickets "
        "WHERE created_by_user_id = :user_id AND status IN ('Open', 'Unassigned', 'Assigned', 'In Progress', 'Escalated', 'Overdue', 'Reopened') "
        f"ORDER BY created_at DESC LIMIT {OPEN_TICKET_LIMIT}"
    )
    with _ro_engine.connect() as conn:
        rows = conn.execute(text(query), {"user_id": user_id.strip()}).fetchall()
    return rows, query


def get_ticket_status(ticket_id: str, user_id: str) -> dict:
    query = (
        "SELECT ticket_code, status, subject, assigned_to_user_id, updated_at "
        "FROM tickets WHERE ticket_code = :ticket_code AND created_by_user_id = :user_id LIMIT 1"
    )

    try:
        with _ro_engine.connect() as conn:
            row = conn.execute(
                text(query),
                {"ticket_code": ticket_id.strip(), "user_id": user_id.strip()},
            ).fetchone()

        if row is None:
            return {
                "found": True,
                "raw": "I could not find that ticket for your account. Please check the ticket ID and try again.",
                "query": query,
            }

        assigned_to = row.assigned_to_user_id or "Unassigned"
        response = (
            f"Ticket {row.ticket_code}:\n"
            f"- Status: {row.status}\n"
            f"- Subject: {row.subject}\n"
            f"- Assigned to: {assigned_to}\n"
            f"- Last updated: {_format_ts(row.updated_at)}"
        )
        return {"found": True, "raw": response, "query": query}
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}


def get_open_tickets(user_id: str) -> dict:
    try:
        rows, query = _fetch_open_ticket_rows(user_id)

        if not rows:
            return {
                "found": True,
                "raw": "You currently have no open tickets.",
                "query": query,
            }

        lines = []
        for row in rows:
            ticket_code = (row.ticket_code or "").strip() or "-"
            subject = _clean_subject(row.subject)
            created_at = _format_ts(row.created_at)
            status = (row.status or "Unknown").strip() or "Unknown"
            lines.append(f"{ticket_code} | {subject} | {created_at} | {status}")

        return {"found": True, "raw": "\n".join(lines), "query": query}
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}