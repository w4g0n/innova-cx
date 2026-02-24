import os
from datetime import datetime

from sqlalchemy import create_engine, text

from .db import DATABASE_URL

READONLY_DB_URL = os.environ.get("READONLY_DATABASE_URL") or DATABASE_URL
_ro_engine = create_engine(READONLY_DB_URL, pool_pre_ping=True)


def _format_ts(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value) if value is not None else "-"


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
    query = (
        "SELECT ticket_code, subject, status, created_at "
        "FROM tickets "
        "WHERE created_by_user_id = :user_id AND status IN ('Open', 'Unassigned', 'Assigned', 'In Progress', 'Escalated', 'Overdue', 'Reopened') "
        "ORDER BY created_at DESC LIMIT 20"
    )

    try:
        with _ro_engine.connect() as conn:
            rows = conn.execute(text(query), {"user_id": user_id.strip()}).fetchall()

        if not rows:
            return {
                "found": True,
                "raw": "You currently have no open tickets.",
                "query": query,
            }

        lines = ["Here are your open tickets:"]
        for i, row in enumerate(rows, start=1):
            lines.append(
                f"{i}. {row.ticket_code} | {row.status} | {row.subject} | created {_format_ts(row.created_at)}"
            )

        return {"found": True, "raw": "\n".join(lines), "query": query}
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}
