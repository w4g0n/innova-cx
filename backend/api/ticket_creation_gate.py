import os
import uuid
import urllib.parse
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
import string
import secrets
import httpx
try:
    from api.event_logger import log_application_event
except Exception:
    from event_logger import log_application_event

logger = logging.getLogger(__name__)


def create_ticket_via_gate(
    cur,
    *,
    created_by_user_id: str,
    ticket_type: Optional[str],
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

    ticket_code = "CX-" + "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    # App-level SLA rule: do not start SLA clocks until routed + assigned.
    effective_priority_assigned_at = None
    log_application_event(
        service="backend",
        event_key="ticket_gate_create_start",
        ticket_code=ticket_code,
        payload={
            "source": ticket_source,
            "type": ticket_type,
            "status": status,
            "priority": priority,
        },
        cur=cur,
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
            effective_priority_assigned_at,
        ),
    )
    row = cur.fetchone()
    cur.execute(
        """
        UPDATE tickets
        SET
          priority_assigned_at = NULL,
          respond_due_at = NULL,
          resolve_due_at = NULL,
          respond_time_left_seconds = NULL,
          resolve_time_left_seconds = NULL,
          respond_breached = FALSE,
          resolve_breached = FALSE,
          status = CASE WHEN status = 'Overdue'::ticket_status THEN 'Open'::ticket_status ELSE status END
        WHERE id = %s
          AND status <> 'Resolved'::ticket_status
          AND (department_id IS NULL OR assigned_to_user_id IS NULL)
        RETURNING status, priority, priority_assigned_at, respond_due_at, resolve_due_at;
        """,
        (row[0],),
    )
    normalized = cur.fetchone()
    if normalized:
        row = (row[0], row[1], normalized[0], normalized[1], normalized[2], normalized[3], normalized[4])
    execution_id = str(uuid.uuid4())
    log_application_event(
        service="backend",
        event_key="ticket_gate_create_done",
        ticket_id=row[0],
        ticket_code=row[1],
        payload={
            "status": row[2],
            "priority": row[3],
            "priority_assigned_at": row[4],
        },
        cur=cur,
    )
    return {
        "id": row[0],
        "ticket_code": row[1],
        "status": row[2],
        "priority": row[3],
        "priority_assigned_at": row[4],
        "respond_due_at": row[5],
        "resolve_due_at": row[6],
        "execution_id": execution_id,
    }


def dispatch_ticket_to_orchestrator(
    *,
    ticket_code: str,
    details: str,
    orchestrator_url: str,
    orchestrator_url_local: str,
    ticket_type: Optional[str] = None,
    subject: Optional[str] = None,
    execution_id: Optional[str] = None,
    has_audio: bool = False,
    audio_features: Optional[Dict[str, Any]] = None,
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
        "has_audio": "true" if has_audio else "false",
    }
    if subject and subject.strip():
        payload["subject"] = subject.strip()
    if execution_id and str(execution_id).strip():
        payload["execution_id"] = str(execution_id).strip()
    if has_audio and isinstance(audio_features, dict) and audio_features:
        payload["audio_features"] = json.dumps(audio_features)

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
            log_application_event(
                service="backend",
                event_key="ticket_gate_dispatch_attempt",
                ticket_code=ticket_code,
                payload={
                    "target": base,
                    "type": type_value,
                    "has_audio": payload.get("has_audio"),
                },
            )
            with httpx.Client(timeout=dispatch_timeout) as client:
                response = client.post(f"{base}/process/text", content=encoded, headers=headers)
                response.raise_for_status()
                log_application_event(
                    service="backend",
                    event_key="ticket_gate_dispatch_done",
                    ticket_code=ticket_code,
                    payload={
                        "target": base,
                        "status_code": response.status_code,
                    },
                )
                return True
        except Exception as exc:
            log_application_event(
                service="backend",
                event_key="ticket_gate_dispatch_failed",
                level="WARNING",
                ticket_code=ticket_code,
                payload={
                    "target": base,
                    "error": str(exc),
                },
            )
            logger.warning(
                "ticket_gate_dispatch_failed | ticket_code=%s target=%s err=%s",
                ticket_code,
                base,
                exc,
            )
            continue
    log_application_event(
        service="backend",
        event_key="ticket_gate_dispatch_exhausted",
        level="ERROR",
        ticket_code=ticket_code,
        payload={},
    )
    logger.error("ticket_gate_dispatch_exhausted | ticket_code=%s", ticket_code)
    return False
