import os
import re
from datetime import datetime

from sqlalchemy import create_engine, text

from .db import DATABASE_URL

READONLY_DB_URL = os.environ.get("READONLY_DATABASE_URL") or DATABASE_URL
_ro_engine = create_engine(READONLY_DB_URL, pool_pre_ping=True)
OPEN_TICKET_LIMIT = 10
_HINT_STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "to", "of", "on", "in", "is", "it",
    "this", "that", "my", "me", "i", "with", "please", "ticket", "status", "open",
    "progress", "follow", "up", "id", "cx",
}


def _format_ts(value):
    if isinstance(value, datetime):
        # Keep timestamps compact and readable for chat responses.
        if value.tzinfo is not None:
            return value.strftime("%Y-%m-%d %H:%M UTC")
        return value.strftime("%Y-%m-%d %H:%M")
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
                "ticket_found": False,
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
        return {
            "found": True,
            "ticket_found": True,
            "ticket_code": row.ticket_code,
            "status": row.status,
            "subject": row.subject,
            "raw": response,
            "query": query,
        }
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}


def get_open_tickets(user_id: str) -> dict:
    query = ""
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


def resolve_ticket_id_from_hint(hint_text: str, user_id: str) -> dict:
    """
    Best-effort resolver when users paste part of the ticket list line
    (e.g. status/subject) instead of a strict ticket ID.
    """
    query = ""
    try:
        rows, query = _fetch_open_ticket_rows(user_id)
        if not rows:
            return {"found": False, "query": query}

        hint = (hint_text or "").strip().lower()
        if not hint:
            return {"found": False, "query": query}

        # Allow selecting by list number, e.g. "3" or "#3".
        idx_match = re.search(r"(?:^|[^0-9])#?([1-9]|10)(?:[^0-9]|$)", hint)
        if idx_match:
            idx = int(idx_match.group(1)) - 1
            if 0 <= idx < len(rows):
                return {"found": True, "ticket_id": rows[idx].ticket_code, "query": query}

        hint_tokens = {
            t for t in re.findall(r"[a-z0-9]+", hint)
            if len(t) >= 3 and t not in _HINT_STOPWORDS
        }
        best_row = None
        best_score = 0
        second_score = 0

        for row in rows:
            ticket_code = (row.ticket_code or "").strip()
            subject = (row.subject or "").strip()
            status = (row.status or "").strip()

            score = 0
            code_lower = ticket_code.lower()
            subject_lower = subject.lower()
            status_lower = status.lower()

            if code_lower and code_lower in hint:
                score += 100
            if subject_lower and subject_lower in hint:
                score += 75
            if hint in subject_lower and len(hint) >= 8:
                score += 50
            if status_lower and status_lower in hint:
                score += 10

            subject_tokens = set(re.findall(r"[a-z0-9]+", subject_lower))
            if hint_tokens and subject_tokens:
                overlap = len(hint_tokens & subject_tokens)
                if overlap:
                    # Boost strong token overlap (e.g. "this is my ticket testing audio model")
                    score += int(70 * (overlap / len(hint_tokens)))
                    score += int(30 * (overlap / len(subject_tokens)))

                    # If all significant subject tokens are present in hint, treat as strong match.
                    core_subject_tokens = {
                        t for t in subject_tokens if t not in _HINT_STOPWORDS
                    }
                    if core_subject_tokens and core_subject_tokens.issubset(hint_tokens):
                        score += 60

            if score > best_score:
                second_score = best_score
                best_score = score
                best_row = row
            elif score > second_score:
                second_score = score

        if best_row is None or best_score < 30:
            return {"found": False, "query": query}

        # Avoid weak/ambiguous matches.
        if best_score < 60 and (best_score - second_score) <= 10:
            return {"found": False, "query": query}

        return {
            "found": True,
            "ticket_id": best_row.ticket_code,
            "query": query,
        }
    except Exception as e:
        return {"found": False, "error": str(e), "query": query}
