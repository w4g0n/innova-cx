from typing import Any, Dict, List, Optional
import os
import json
import uuid

import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

try:
    from .pipeline_queue_api import _STAGE_DESCRIPTIONS, _explain_stage  # noqa: F401
except Exception:
    from pipeline_queue_api import _STAGE_DESCRIPTIONS, _explain_stage  # noqa: F401

router = APIRouter()
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004").rstrip("/")
ORCHESTRATOR_URL_LOCAL = os.getenv("ORCHESTRATOR_URL_LOCAL", "http://localhost:8004").rstrip("/")


def _iso(val) -> Optional[str]:
    return val.isoformat() if val else None


def _flt(val) -> Optional[float]:
    return float(val) if val is not None else None

PRIORITY_LEVELS = ["low", "medium", "high", "critical"]
PRIORITY_TO_INDEX = {name: idx for idx, name in enumerate(PRIORITY_LEVELS)}

_SENTIMENT_NEGATIVE_THRESHOLD = -0.25
_SENTIMENT_POSITIVE_THRESHOLD = 0.25


def _normalize_3level(value: Any, default: str = "medium") -> str:
    s = str(value or "").strip().lower()
    return s if s in {"low", "medium", "high"} else default


def _normalize_sentiment(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"negative", "neutral", "positive"}:
        return s
    try:
        n = float(value)
        if n < _SENTIMENT_NEGATIVE_THRESHOLD:
            return "negative"
        if n > _SENTIMENT_POSITIVE_THRESHOLD:
            return "positive"
        return "neutral"
    except Exception:
        return "neutral"


def _compute_priority_rule(
    *,
    sentiment: str,
    issue_severity: str,
    issue_urgency: str,
    business_impact: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
) -> Dict[str, Any]:
    severity = _normalize_3level(issue_severity)
    urgency = _normalize_3level(issue_urgency)
    impact = _normalize_3level(business_impact)
    sentiment_norm = _normalize_sentiment(sentiment)
    ticket_type_norm = str(ticket_type or "complaint").strip().lower()
    if ticket_type_norm not in {"complaint", "inquiry"}:
        ticket_type_norm = "complaint"

    levels = [impact, severity, urgency]
    high_count = sum(1 for lvl in levels if lvl == "high")
    medium_count = sum(1 for lvl in levels if lvl == "medium")

    if high_count >= 2:
        base_priority = "critical"
    elif high_count == 1:
        base_priority = "medium"
    elif medium_count == 3:
        base_priority = "high"
    elif medium_count == 2:
        base_priority = "medium"
    else:
        base_priority = "low"

    priority_idx = PRIORITY_TO_INDEX[base_priority]
    modifiers_applied: List[str] = []
    safety_floor_idx = PRIORITY_TO_INDEX["high"] if bool(safety_concern) else PRIORITY_TO_INDEX["low"]

    if bool(safety_concern):
        modifiers_applied.append("safety_concern=true(min_high)")
        if priority_idx < safety_floor_idx:
            priority_idx = safety_floor_idx

    if bool(is_recurring):
        priority_idx += 1
        modifiers_applied.append("is_recurring=true(+1)")

    if ticket_type_norm == "inquiry":
        priority_idx -= 1
        modifiers_applied.append("ticket_type=inquiry(-1)")
    else:
        modifiers_applied.append("ticket_type=complaint(0)")

    if sentiment_norm == "negative":
        priority_idx += 1
        modifiers_applied.append("sentiment=negative(+1)")
    elif sentiment_norm == "positive":
        priority_idx -= 1
        modifiers_applied.append("sentiment=positive(-1)")
    else:
        modifiers_applied.append("sentiment=neutral(0)")

    priority_idx = max(PRIORITY_TO_INDEX["low"], min(PRIORITY_TO_INDEX["critical"], priority_idx))
    priority_idx = max(priority_idx, safety_floor_idx)
    final_priority = PRIORITY_LEVELS[priority_idx]
    modifiers_applied.append("fallback=rule_no_model")

    return {
        "raw_score": float(priority_idx + 1),
        "base_priority": base_priority,
        "final_priority": final_priority,
        "modifiers_applied": modifiers_applied,
        "confidence": 1.0,
        "engine": "rule_based_v2",
    }


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}


class PipelineOverrideRequest(BaseModel):
    ticket_type: str
    business_impact: str
    issue_severity: str
    issue_urgency: str
    safety_concern: bool = False
    is_recurring: bool = False
    similar_ticket_code: Optional[str] = None


@router.get("/operator/ai-explainability/ticket-search")
def search_tickets_for_recurrence(
    q: str = Query(default="", min_length=1, max_length=120),
    exclude_ticket_code: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
):
    term = f"%{q.strip()}%"
    rows = _fetch_all(
        """
        SELECT
            ticket_code,
            subject,
            status::text AS status
        FROM tickets
        WHERE (ticket_code ILIKE %s OR subject ILIKE %s)
          AND (%s IS NULL OR ticket_code <> %s)
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (term, term, exclude_ticket_code, exclude_ticket_code, limit),
    ) or []
    return {
        "items": [
            {
                "ticketCode": r.get("ticket_code"),
                "subject": r.get("subject") or "",
                "status": r.get("status") or "",
            }
            for r in rows
        ]
    }


def _build_default_dsn() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_app")
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError("DB_PASSWORD env var must be set")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _get_dsn() -> str:
    return os.getenv("DATABASE_URL") or _build_default_dsn()


def _db_connect():
    return psycopg2.connect(_get_dsn())


def _fetch_one(sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
    with _db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def _fetch_all(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    with _db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]


@router.get("/operator/ai-explainability")
def get_operator_ai_explainability_runs(limit: int = Query(default=50, ge=1, le=200)):
    try:
        rows = _fetch_all(
            """
            SELECT
                pe.id::text             AS execution_id,
                pe.ticket_id::text      AS ticket_id,
                pe.ticket_code          AS ticket_code,
                t.subject               AS subject,
                pe.trigger_source       AS trigger_source,
                pe.status               AS status,
                pe.started_at           AS started_at,
                pe.completed_at         AS completed_at
            FROM pipeline_executions pe
            LEFT JOIN tickets t ON t.id = pe.ticket_id
            ORDER BY pe.started_at DESC
            LIMIT %s
            """,
            (limit,),
        ) or []
    except Exception:
        rows = []

    return {
        "items": [
            {
                "executionId": r.get("execution_id"),
                "ticketId": r.get("ticket_id"),
                "ticketCode": r.get("ticket_code"),
                "subject": r.get("subject") or "",
                "triggerSource": r.get("trigger_source") or "ingest",
                "status": r.get("status") or "running",
                "startedAt": _iso(r.get("started_at")),
                "completedAt": _iso(r.get("completed_at")),
            }
            for r in rows
        ]
    }


@router.get("/operator/ai-explainability/tickets")
def get_operator_ai_explainability_tickets(limit: int = Query(default=500, ge=1, le=2000)):
    items = _fetch_all(
        """
        SELECT
            t.id::text AS ticket_id,
            t.ticket_code AS ticket_code,
            t.subject AS subject,
            CASE
                WHEN pq.status = 'completed' THEN 'Completed'
                ELSE t.status::text
            END AS status,
            t.priority::text AS priority,
            d.name AS department_name,
            up_assigned.full_name AS assigned_to_name,
            t.created_at AS created_at,
            pq.completed_at AS pipeline_completed_at
        FROM tickets t
        LEFT JOIN pipeline_queue pq ON pq.ticket_id = t.id
        LEFT JOIN departments d ON d.id = t.department_id
        LEFT JOIN user_profiles up_assigned ON up_assigned.user_id = t.assigned_to_user_id
        WHERE pq.status = 'completed'
           OR lower(coalesce(t.status::text, '')) IN ('completed', 'resolved')
        ORDER BY COALESCE(pq.completed_at, t.created_at) DESC
        LIMIT %s
        """,
        (limit,),
    ) or []

    return {
        "items": [
            {
                "ticketId": r.get("ticket_id"),
                "ticketCode": r.get("ticket_code"),
                "subject": r.get("subject") or "",
                "status": r.get("status") or "Open",
                "priority": r.get("priority") or "",
                "department": r.get("department_name") or "Unassigned",
                "assignedTo": r.get("assigned_to_name") or "Unassigned",
                "createdAt": _iso(r.get("created_at")),
                "pipelineCompletedAt": _iso(r.get("pipeline_completed_at")),
            }
            for r in items
        ],
        "statusCounts": {
            "Completed": len(items),
        },
    }


@router.get("/operator/ai-explainability/tickets/{ticket_id}")
def get_operator_ai_explainability_ticket(ticket_id: str):
    ticket_row = _fetch_one(
        """
        SELECT
            t.id               AS ticket_id,
            t.ticket_code      AS ticket_code,
            t.subject          AS subject,
            t.details          AS details,
            t.priority         AS priority,
            t.status           AS status,
            t.created_at       AS created_at,
            t.priority_assigned_at AS priority_assigned_at,
            t.assigned_at      AS assigned_at,
            t.respond_due_at   AS respond_due_at,
            t.resolve_due_at   AS resolve_due_at,
            t.first_response_at AS first_response_at,
            t.resolved_at      AS resolved_at,
            t.suggested_resolution AS suggested_resolution,
            t.model_suggestion AS model_suggestion,
            t.final_resolution AS final_resolution,
            d.name             AS department_name,
            up.full_name       AS submitter_name,
            up.phone           AS submitter_phone,
            up.location        AS submitter_location
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        JOIN users u ON u.id = t.created_by_user_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE t.ticket_code = %s OR t.id::text = %s
        LIMIT 1
        """,
        (ticket_id, ticket_id),
    )
    if not ticket_row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    tid = ticket_row["ticket_id"]

    pipeline_executions = _fetch_all(
        """
        SELECT
            id::text         AS execution_id,
            trigger_source,
            status,
            started_at,
            completed_at,
            error_message
        FROM pipeline_executions
        WHERE ticket_id = %s OR ticket_code = %s
        ORDER BY started_at ASC
        """,
        (tid, ticket_row.get("ticket_code")),
    ) or []

    pipeline_stages = _fetch_all(
        """
        SELECT
            execution_id::text AS execution_id,
            step_order,
            stage_name,
            event_type,
            status,
            inference_time_ms,
            confidence_score,
            input_state,
            output_state,
            error_message,
            created_at
        FROM pipeline_stage_events
        WHERE ticket_id = %s OR ticket_code = %s
        ORDER BY created_at ASC, step_order ASC
        """,
        (tid, ticket_row.get("ticket_code")),
    ) or []

    if not pipeline_stages:
        pipeline_stages = _fetch_all(
            """
            SELECT
                execution_id::text AS execution_id,
                step_order,
                agent_name         AS stage_name,
                'output'::text     AS event_type,
                CASE WHEN error_flag THEN 'failed' ELSE 'success' END AS status,
                inference_time_ms,
                NULL::numeric      AS confidence_score,
                input_state,
                output_state,
                error_message,
                created_at
            FROM agent_output_log
            WHERE ticket_id = %s
            ORDER BY created_at ASC, step_order ASC
            """,
            (tid,),
        ) or []

    attachments = _fetch_all(
        """
        SELECT
          file_name,
          COALESCE(file_url, '/uploads/' || file_name) AS file_url
        FROM ticket_attachments
        WHERE ticket_id = %s
        ORDER BY uploaded_at ASC
        """,
        (tid,),
    ) or []

    steps_taken = _fetch_all(
        """
        SELECT
          tws.step_no AS step,
          COALESCE(tp.full_name, tu.email) AS technician,
          tws.occurred_at AS occurred_at,
          tws.notes AS notes
        FROM ticket_work_steps tws
        LEFT JOIN users tu ON tu.id = tws.technician_user_id
        LEFT JOIN user_profiles tp ON tp.user_id = tu.id
        WHERE tws.ticket_id = %s
        ORDER BY tws.step_no ASC
        """,
        (tid,),
    ) or []

    created_at = ticket_row.get("created_at")
    issue_date = created_at.date().isoformat() if created_at else ""

    return {
        "ticketCode": ticket_row.get("ticket_code"),
        "subject": ticket_row.get("subject"),
        "details": ticket_row.get("details"),
        "status": ticket_row.get("status"),
        "priority": ticket_row.get("priority"),
        "ticket": {
            "ticketId": ticket_row.get("ticket_code"),
            "priority": ticket_row.get("priority"),
            "status": ticket_row.get("status"),
            "issueDate": issue_date,
            "suggestedResolution": ticket_row.get("suggested_resolution") or "",
            "modelSuggestion": ticket_row.get("model_suggestion"),
            "finalResolution": ticket_row.get("final_resolution") or "",
            "submittedBy": {
                "name": ticket_row.get("submitter_name") or "Unknown",
                "contact": ticket_row.get("submitter_phone") or "",
                "location": ticket_row.get("submitter_location") or "",
            },
            "description": {
                "subject": ticket_row.get("subject"),
                "details": ticket_row.get("details"),
            },
            "department": ticket_row.get("department_name") or "",
            "sla": {
                "priorityAssignedAt": _iso(ticket_row.get("priority_assigned_at")),
                "assignedAt": _iso(ticket_row.get("assigned_at")),
                "respondDueAt": _iso(ticket_row.get("respond_due_at")),
                "resolveDueAt": _iso(ticket_row.get("resolve_due_at")),
                "firstResponseAt": _iso(ticket_row.get("first_response_at")),
                "resolvedAt": _iso(ticket_row.get("resolved_at")),
            },
            "attachments": [
                {"fileName": a.get("file_name"), "fileUrl": a.get("file_url")}
                for a in attachments
            ],
            "stepsTaken": [
                {
                    "step": s.get("step"),
                    "technician": s.get("technician"),
                    "time": _iso(s.get("occurred_at")),
                    "notes": s.get("notes") or "",
                }
                for s in steps_taken
            ],
        },
        "pipelineExecutions": [
            {
                "executionId": e.get("execution_id"),
                "triggerSource": e.get("trigger_source") or "ingest",
                "status": e.get("status") or "running",
                "startedAt": _iso(e.get("started_at")),
                "completedAt": _iso(e.get("completed_at")),
                "errorMessage": e.get("error_message"),
            }
            for e in pipeline_executions
        ],
        "pipelineStages": [
            {
                "executionId": s.get("execution_id"),
                "stepOrder": s.get("step_order"),
                "stageName": s.get("stage_name"),
                "eventType": s.get("event_type"),
                "status": s.get("status"),
                "inferenceTimeMs": s.get("inference_time_ms"),
                "confidenceScore": _flt(s.get("confidence_score")),
                "inputState": s.get("input_state") or {},
                "outputState": s.get("output_state") or {},
                "errorMessage": s.get("error_message"),
                "description": _STAGE_DESCRIPTIONS.get(s.get("stage_name"), ""),
                "explanation": _explain_stage(
                    s.get("stage_name"),
                    s.get("output_state") or {},
                    s.get("error_message"),
                ),
                "createdAt": _iso(s.get("created_at")),
            }
            for s in pipeline_stages
        ],
    }


@router.post("/operator/ai-explainability/tickets/{ticket_id}/pipeline-rerun")
def rerun_operator_ai_pipeline(ticket_id: str):
    ticket_row = _fetch_one(
        """
        SELECT
            t.id::text          AS ticket_id,
            t.ticket_code       AS ticket_code,
            t.ticket_type::text AS ticket_type,
            t.details           AS details
        FROM tickets t
        WHERE t.ticket_code = %s OR t.id::text = %s
        LIMIT 1
        """,
        (ticket_id, ticket_id),
    )
    if not ticket_row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_code = str(ticket_row.get("ticket_code") or "").strip()
    details = str(ticket_row.get("details") or "").strip()
    ticket_type = str(ticket_row.get("ticket_type") or "Complaint").strip().lower()
    if ticket_type not in {"complaint", "inquiry"}:
        ticket_type = "complaint"
    if not ticket_code or not details:
        raise HTTPException(status_code=422, detail="Ticket is missing ticket_code or details")

    execution_id = str(uuid.uuid4())
    payload = {
        "text": details,
        "ticket_id": ticket_code,
        "ticket_type": ticket_type,
        "execution_id": execution_id,
        # Blank subject forces step 1 to regenerate it from the beginning.
        "subject": "",
    }
    timeout = float(os.getenv("AI_EXPLAINABILITY_RERUN_TIMEOUT_SECONDS", "240"))
    last_error = None
    for base in (ORCHESTRATOR_URL, ORCHESTRATOR_URL_LOCAL):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f"{base}/process/text", data=payload)
                response.raise_for_status()
                body = response.json() if response.content else {}
                return {
                    "ok": True,
                    "ticketId": ticket_code,
                    "executionId": execution_id,
                    "orchestratorExecutionId": body.get("execution_id") or execution_id,
                    "priority": body.get("priority"),
                    "priorityLabel": body.get("priority_label"),
                    "department": body.get("department"),
                    "type": body.get("type"),
                }
        except Exception as exc:
            last_error = exc
            continue

    raise HTTPException(status_code=503, detail=f"Failed to rerun pipeline: {last_error}")


@router.patch("/operator/ai-explainability/tickets/{ticket_id}/pipeline-overrides")
def apply_operator_pipeline_overrides(ticket_id: str, body: PipelineOverrideRequest):
    ticket_type_norm = str(body.ticket_type or "").strip().lower()
    if ticket_type_norm not in {"complaint", "inquiry"}:
        raise HTTPException(status_code=422, detail="ticket_type must be complaint or inquiry")

    business_impact = _normalize_3level(body.business_impact)
    issue_severity = _normalize_3level(body.issue_severity)
    issue_urgency = _normalize_3level(body.issue_urgency)
    safety_concern = bool(body.safety_concern)
    is_recurring = bool(body.is_recurring)
    similar_ticket_code = (body.similar_ticket_code or "").strip() or None

    if is_recurring and not similar_ticket_code:
        raise HTTPException(status_code=422, detail="similar_ticket_code is required when is_recurring is true")

    with _db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    t.id::text          AS ticket_id,
                    t.ticket_code       AS ticket_code,
                    t.ticket_type::text AS ticket_type,
                    t.priority::text    AS priority,
                    t.details           AS details,
                    t.sentiment_score,
                    t.sentiment_label,
                    t.model_suggestion
                FROM tickets t
                WHERE t.ticket_code = %s OR t.id::text = %s
                LIMIT 1
                """,
                (ticket_id, ticket_id),
            )
            ticket = cur.fetchone()
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            current_ticket_code = str(ticket.get("ticket_code") or "")
            linked_ticket_subject = None

            if is_recurring:
                cur.execute(
                    """
                    SELECT ticket_code, subject
                    FROM tickets
                    WHERE ticket_code = %s
                      AND ticket_code <> %s
                    LIMIT 1
                    """,
                    (similar_ticket_code, current_ticket_code),
                )
                linked = cur.fetchone()
                if not linked:
                    raise HTTPException(status_code=422, detail="similar_ticket_code not found")
                linked_ticket_subject = linked.get("subject")

            cur.execute(
                """
                SELECT output_state
                FROM pipeline_stage_events
                WHERE (ticket_id::text = %s OR ticket_code = %s)
                  AND stage_name = 'SentimentCombinerAgent'
                  AND event_type = 'output'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (ticket.get("ticket_id"), current_ticket_code),
            )
            combiner_row = cur.fetchone()
            combiner_out = _safe_json_dict(combiner_row.get("output_state")) if combiner_row else {}

            sentiment_value = (
                combiner_out.get("sentiment_score")
                or combiner_out.get("sentiment_score_numeric")
                or ticket.get("sentiment_label")
                or ticket.get("sentiment_score")
                or "neutral"
            )
            sentiment_norm = _normalize_sentiment(sentiment_value)

            priority_result = _compute_priority_rule(
                sentiment=sentiment_norm,
                issue_severity=issue_severity,
                issue_urgency=issue_urgency,
                business_impact=business_impact,
                safety_concern=safety_concern,
                is_recurring=is_recurring,
                ticket_type=ticket_type_norm,
            )

            final_priority_lower = str(priority_result.get("final_priority") or "medium").lower()
            final_priority_title = final_priority_lower.capitalize()
            previous_priority = str(ticket.get("priority") or "")

            model_suggestion = _safe_json_dict(ticket.get("model_suggestion"))
            model_suggestion["operator_overrides"] = {
                "ticket_type": ticket_type_norm,
                "business_impact": business_impact,
                "issue_severity": issue_severity,
                "issue_urgency": issue_urgency,
                "safety_concern": safety_concern,
                "is_recurring": is_recurring,
                "similar_ticket_code": similar_ticket_code if is_recurring else None,
                "similar_ticket_subject": linked_ticket_subject if is_recurring else None,
                "sentiment_for_priority": sentiment_norm,
            }

            cur.execute(
                """
                UPDATE tickets
                SET
                    ticket_type = %s::ticket_type,
                    is_recurring = %s,
                    priority = %s::ticket_priority,
                    model_priority = %s::ticket_priority,
                    model_confidence = %s,
                    model_suggestion = %s,
                    updated_at = now()
                WHERE id::text = %s
                RETURNING id::text, ticket_code, priority::text, ticket_type::text, is_recurring;
                """,
                (
                    ticket_type_norm.capitalize(),
                    is_recurring,
                    final_priority_title,
                    final_priority_title,
                    float(priority_result.get("confidence") or 1.0),
                    json.dumps(model_suggestion),
                    ticket.get("ticket_id"),
                ),
            )
            updated = cur.fetchone()

    return {
        "ok": True,
        "ticketCode": updated.get("ticket_code"),
        "ticketType": updated.get("ticket_type"),
        "isRecurring": updated.get("is_recurring"),
        "priority": updated.get("priority"),
        "previousPriority": previous_priority,
        "priorityChanged": str(previous_priority or "").lower() != str(updated.get("priority") or "").lower(),
        "priorityDetails": priority_result,
        "linkedTicket": {
            "ticketCode": similar_ticket_code if is_recurring else None,
            "subject": linked_ticket_subject if is_recurring else None,
        },
    }
