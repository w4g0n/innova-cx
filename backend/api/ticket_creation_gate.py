import os
import time
import urllib.parse
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


def create_ticket_via_gate(
    cur,
    *,
    created_by_user_id: str,
    ticket_type: str,
    subject: str,
    details: str,
    priority: Optional[str],
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
    logger.info(
        "ticket_gate_create_start | ticket_code=%s source=%s type=%s status=%s priority=%s",
        ticket_code,
        ticket_source,
        ticket_type,
        status,
        priority,
    )
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
            %s, %s, %s, %s, %s::ticket_priority, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
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
    logger.info(
        "ticket_gate_create_done | ticket_code=%s id=%s status=%s priority=%s priority_assigned_at=%s",
        row[1],
        row[0],
        row[2],
        row[3],
        row[4],
    )
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

    dispatch_timeout = float(os.getenv("TICKET_GATE_ORCHESTRATOR_TIMEOUT_SECONDS", "180"))
    base_candidates = [orchestrator_url, orchestrator_url_local, "http://innovacx-orchestrator:8004"]
    bases = []
    for base in base_candidates:
        normalized = (base or "").rstrip("/")
        if normalized and normalized not in bases:
            bases.append(normalized)

    for base in bases:
        try:
            logger.info(
                "ticket_gate_dispatch_attempt | ticket_code=%s target=%s type=%s has_audio=%s",
                ticket_code,
                base,
                type_value,
                payload.get("has_audio"),
            )
            with httpx.Client(timeout=dispatch_timeout) as client:
                response = client.post(f"{base}/process/text", content=encoded, headers=headers)
                response.raise_for_status()
                logger.info(
                    "ticket_gate_dispatch_done | ticket_code=%s target=%s status_code=%s",
                    ticket_code,
                    base,
                    response.status_code,
                )
                return True
        except Exception as exc:
            logger.warning(
                "ticket_gate_dispatch_failed | ticket_code=%s target=%s err=%s",
                ticket_code,
                base,
                exc,
            )
            continue
    logger.error("ticket_gate_dispatch_exhausted | ticket_code=%s", ticket_code)
    return False
