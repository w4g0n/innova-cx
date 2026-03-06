import os
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, Optional

import httpx


def create_ticket_via_gate(
    cur,
    *,
    created_by_user_id: str,
    ticket_type: str,
    subject: str,
    details: str,
    priority: str,
    status: str,
    ticket_source: str,
    model_suggestion: Optional[str] = None,
    department_id: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    sentiment_label: Optional[str] = None,
    model_priority: Optional[str] = None,
    model_department_id: Optional[str] = None,
    model_confidence: Optional[float] = None,
    priority_assigned_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Single DB gate for ticket creation writes.
    """
    ticket_code = f"CX-{int(time.time() * 1000)}-{os.urandom(2).hex().upper()}"
    cur.execute(
        """
        INSERT INTO tickets (
            ticket_code,
            ticket_type,
            subject,
            details,
            priority,
            status,
            created_by_user_id,
            model_suggestion,
            ticket_source,
            department_id,
            sentiment_score,
            sentiment_label,
            model_priority,
            model_department_id,
            model_confidence,
            priority_assigned_at,
            created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        RETURNING id, ticket_code, status, priority, priority_assigned_at, respond_due_at, resolve_due_at;
        """,
        (
            ticket_code,
            ticket_type,
            (subject or "").strip(),
            details or "",
            priority,
            status,
            created_by_user_id,
            model_suggestion,
            ticket_source,
            department_id,
            sentiment_score,
            sentiment_label,
            model_priority,
            model_department_id,
            model_confidence,
            priority_assigned_at,
        ),
    )
    row = cur.fetchone()
    return {
        "id": row[0],
        "ticket_code": row[1],
        "status": row[2],
        "priority": row[3],
        "priority_assigned_at": row[4],
        "respond_due_at": row[5],
        "resolve_due_at": row[6],
    }


def dispatch_ticket_to_orchestrator(
    *,
    ticket_code: str,
    details: str,
    orchestrator_url: str,
    orchestrator_url_local: str,
    ticket_type: Optional[str] = None,
    subject: Optional[str] = None,
) -> bool:
    """
    Best-effort dispatch to orchestrator post-submit pipeline.
    Never raises to caller.
    Returns True when at least one orchestrator endpoint accepted the request.
    """
    text_value = (details or "").strip()
    if not ticket_code or not text_value:
        return False

    type_value = (ticket_type or "complaint").strip().lower()
    if type_value not in {"complaint", "inquiry"}:
        type_value = "complaint"

    payload = {
        "text": text_value,
        "ticket_id": ticket_code,
        "ticket_type": type_value,
        "has_audio": "false",
    }
    if subject and subject.strip():
        payload["subject"] = subject.strip()

    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    for base in [orchestrator_url, orchestrator_url_local]:
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.post(f"{base}/process/text", content=encoded, headers=headers)
                response.raise_for_status()
                return True
        except Exception:
            continue
    return False
