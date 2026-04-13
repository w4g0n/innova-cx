"""
Pipeline Queue API — Operator Endpoints

Provides the operator with full visibility and control over the pipeline queue.

Endpoints:
    GET  /api/operator/pipeline-queue              — list all queue items
    GET  /api/operator/pipeline-queue/stats        — queue statistics
    GET  /api/operator/pipeline-queue/{queue_id}   — detail + stage events + AI explainability
    PATCH /api/operator/pipeline-queue/{queue_id}/correct  — save operator stage corrections
    POST  /api/operator/pipeline-queue/{queue_id}/release  — release a held ticket
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import httpx
import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004").rstrip("/")
ORCHESTRATOR_URL_LOCAL = os.getenv("ORCHESTRATOR_URL_LOCAL", "http://localhost:8004").rstrip("/")

_ORCHESTRATOR_DEFAULT_TIMEOUT = 15.0
_ORCHESTRATOR_RERUN_STAGE_TIMEOUT = 240.0  # ReviewAgent can take up to 180s; keep a real buffer
_ORCHESTRATOR_RELEASE_TIMEOUT = 10.0
_REDISPATCH_HTTP_TIMEOUT = 10


# DB helpers

def _get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return dsn
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_app")
    pw   = os.getenv("DB_PASSWORD", "changeme123")
    return f"host={host} port={port} dbname={name} user={user} password={pw}"


def _db_connect():
    return psycopg2.connect(_get_dsn())


def _ensure_pipeline_control_table() -> None:
    """
    Ensures the pipeline_runtime_control table has its required seed row.

    The table itself is created by the database migration (init.sql / zzz scripts)
    running as innovacx_admin.  The runtime role (innovacx_app) has INSERT/SELECT
    on the table but NOT CREATE TABLE on the public schema — so we never issue DDL
    here.  If the table is missing entirely (e.g. a very old volume) we log a
    warning and return gracefully rather than crashing the endpoint.
    """
    try:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pipeline_runtime_control (singleton, is_paused)
                    VALUES (TRUE, FALSE)
                    ON CONFLICT (singleton) DO NOTHING
                    """
                )
    except Exception as exc:
        # Table may not exist on very old volumes — log and continue.
        # The /stats and /control endpoints degrade gracefully when the row
        # is absent (they return {} / default values).
        logger.warning(
            "pipeline_queue | pipeline_runtime_control upsert skipped: %s", exc
        )


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
            return [dict(r) for r in cur.fetchall()]


def _execute(sql: str, params: Optional[tuple] = None) -> None:
    with _db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())


# Pydantic models

class CorrectStageRequest(BaseModel):
    corrections: Dict[str, Any]


class ReleaseRequest(BaseModel):
    corrections: Dict[str, Any]


class RerunStageRequest(BaseModel):
    pass  # no body needed — reruns the failed stage as-is


class RerunQueueRequest(BaseModel):
    pass  # no body needed — resets and reruns the ticket from the top


# AI Explainability helpers

_SENTIMENT_NEGATIVE_THRESHOLD = -0.25
_SENTIMENT_POSITIVE_THRESHOLD = 0.25
_SUGGESTION_PREVIEW_MAX_LEN = 120

_STAGE_STEP_ORDER = {
    "RecurrenceAgent":           1,
    "SubjectGenerationAgent":    2,
    "ClassificationAgent":       3,
    "SentimentAgent":            4,
    "AudioAnalysisAgent":        5,
    "SentimentCombinerAgent":    6,
    "FeatureEngineeringAgent":   7,
    "PrioritizationAgent":       8,
    "DepartmentRoutingAgent":    9,
    "SuggestedResolutionAgent":  10,
    "ReviewAgent":               11,
}

_STAGE_DESCRIPTIONS = {
    "SubjectGenerationAgent":    "Generates a short 2–4 word subject line for the ticket.",
    "SuggestedResolutionAgent":  "Generates a final complaint suggestion or an inquiry answer using the latest ticket context.",
    "ClassificationAgent":       "Determines whether the ticket is a Complaint or an Inquiry.",
    "SentimentAgent":            "Extracts the emotional tone of the ticket text (negative / neutral / positive).",
    "AudioAnalysisAgent":        "Analyzes vocal and acoustic patterns from the audio attachment.",
    "SentimentCombinerAgent":    "Combines text and audio sentiment into a single sentiment score.",
    "RecurrenceAgent":           "Checks whether this is a recurring issue from the same customer.",
    "FeatureEngineeringAgent":   "Labels severity, urgency, business impact, and safety concern.",
    "PrioritizationAgent":       "Applies the company rule set to assign a final priority (Low / Medium / High / Critical).",
    "DepartmentRoutingAgent":    "Routes the ticket to the most relevant department.",
    "ReviewAgent":               "Cross-checks all pipeline outputs, validates routing, and releases or holds the ticket.",
}

_CRITICAL_STAGES = {
    "ClassificationAgent", "SentimentAgent", "AudioAnalysisAgent",
    "SentimentCombinerAgent", "FeatureEngineeringAgent",
    "PrioritizationAgent", "DepartmentRoutingAgent", "ReviewAgent",
}

# Fields the operator can correct per stage (shown in the correction form)
_STAGE_CORRECTABLE_FIELDS = {
    "ClassificationAgent":     ["label", "class_confidence"],
    "SentimentAgent":          ["text_sentiment"],
    "AudioAnalysisAgent":      ["audio_sentiment"],
    "SentimentCombinerAgent":  ["sentiment_score_numeric", "sentiment_score"],
    "FeatureEngineeringAgent": ["issue_severity", "issue_urgency", "business_impact", "safety_concern"],
    "PrioritizationAgent":     ["priority_label", "priority_score"],
    "DepartmentRoutingAgent":  ["department", "model_confidence"],
    "ReviewAgent":             ["review_agent_verdict", "department", "priority_label"],
}


def _explain_stage(stage_name: str, output_state: Dict, error_message: Optional[str]) -> str:
    name = stage_name or ""

    if error_message:
        return f"Stage failed: {error_message}"

    if name == "ClassificationAgent":
        label = str(output_state.get("label") or "unknown").capitalize()
        conf = output_state.get("class_confidence")
        conf_str = f" ({conf * 100:.0f}% confidence)" if conf is not None else ""
        return f"Classified as {label}{conf_str}."

    if name == "SentimentAgent":
        score = output_state.get("text_sentiment")
        if score is not None:
            tone = (
                "negative" if float(score) < _SENTIMENT_NEGATIVE_THRESHOLD
                else ("positive" if float(score) > _SENTIMENT_POSITIVE_THRESHOLD else "neutral")
            )
            return f"Text sentiment score: {float(score):.3f} → {tone}."
        return "Sentiment extracted from ticket text."

    if name == "AudioAnalysisAgent":
        mode = output_state.get("audio_analysis_mode", "")
        if "fallback" in str(mode) or "mock" in str(mode):
            return "No audio provided or audio analysis unavailable — skipped."
        score = output_state.get("audio_sentiment")
        return f"Audio sentiment score: {float(score):.3f}." if score is not None else "No audio provided — input/output null."

    if name == "SentimentCombinerAgent":
        score = output_state.get("sentiment_score_numeric")
        label = output_state.get("sentiment_score", "")
        if score is not None:
            return f"Combined sentiment: {label} (score {float(score):.3f})."
        return "Sentiment scores combined."

    if name == "RecurrenceAgent":
        recurring = output_state.get("is_recurring", False)
        return "Flagged as a recurring issue." if recurring else "No prior matching ticket found — treated as new."

    if name == "FeatureEngineeringAgent":
        severity = output_state.get("issue_severity", "—")
        urgency  = output_state.get("issue_urgency", "—")
        impact   = output_state.get("business_impact", "—")
        safety   = output_state.get("safety_concern", False)
        safety_str = " Safety concern flagged." if safety else ""
        return f"Severity: {severity} | Urgency: {urgency} | Business impact: {impact}.{safety_str}"

    if name == "PrioritizationAgent":
        priority = output_state.get("priority_label", "—")
        score    = output_state.get("priority_score")
        score_str = f" (score {score})" if score is not None else ""
        return f"Priority assigned: {priority}{score_str}."

    if name == "DepartmentRoutingAgent":
        dept = output_state.get("department", "—")
        conf = output_state.get("model_confidence")
        conf_str = f" ({float(conf) * 100:.0f}% confidence)" if conf is not None else ""
        source = output_state.get("department_routing_source", "")
        if "fallback" in str(source) or "mock" in str(source):
            return f"Routing fallback used — department: {dept}."
        return f"Routed to {dept}{conf_str}."

    if name == "ReviewAgent":
        verdict = output_state.get("review_agent_verdict", "—")
        reason = output_state.get("review_agent_verdict_reason", "")
        mode = output_state.get("review_agent_mode", "")
        if error_message:
            return f"Review Agent failed: {error_message}"
        if "mock" in str(mode) or "fallback" in str(mode):
            return "Review Agent used mock fallback — review may be incomplete."
        reason_str = f" Reason: {reason}" if reason else ""
        return f"Review verdict: {verdict}.{reason_str}"

    if name == "SubjectGenerationAgent":
        subject = output_state.get("subject", "")
        return f'Subject: "{subject}".' if subject else "Subject generated."

    if name == "SuggestedResolutionAgent":
        res = output_state.get("suggested_resolution", "")
        mode = str(output_state.get("suggested_resolution_mode", "") or "").strip().lower()
        if mode == "timeout_background" and not res:
            return "Suggested resolution did not finish in time for this run. No suggestion was available to the operator or employee."
        if mode in {"skipped", "skipped_inquiry"}:
            return "Suggested resolution skipped for inquiry ticket."
        if mode == "inquiry_kb_answer" and res:
            preview = (res[:_SUGGESTION_PREVIEW_MAX_LEN] + "…") if len(str(res)) > _SUGGESTION_PREVIEW_MAX_LEN else res
            return f'Inquiry answer: "{preview}"'
        preview = (res[:_SUGGESTION_PREVIEW_MAX_LEN] + "…") if len(str(res)) > _SUGGESTION_PREVIEW_MAX_LEN else res
        return f'Suggested: "{preview}"' if preview else "Resolution suggestion generated."

    return "Stage completed."


# Route: GET /stats

@router.get("/stats")
def get_queue_stats():
    _ensure_pipeline_control_table()
    row = _fetch_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'queued')     AS queued,
            COUNT(*) FILTER (WHERE status = 'processing') AS processing,
            COUNT(*) FILTER (WHERE status = 'held')       AS held,
            COUNT(*) FILTER (WHERE status = 'completed')  AS completed,
            COUNT(*) FILTER (WHERE status = 'failed')     AS failed,
            COUNT(*)                                       AS total
        FROM pipeline_queue
        WHERE entered_at >= now() - INTERVAL '24 hours'
        """
    )
    return row or {}


@router.get("/control")
def get_pipeline_control():
    _ensure_pipeline_control_table()
    row = _fetch_one(
        """
        SELECT is_paused, paused_at, resumed_at, updated_at
        FROM pipeline_runtime_control
        WHERE singleton = TRUE
        """
    )
    return row or {
        "is_paused": False,
        "paused_at": None,
        "resumed_at": None,
        "updated_at": None,
    }


# Route: GET / (list)

@router.get("")
def list_queue():
    return _fetch_all(
        """
        WITH ranked_queue AS (
            SELECT
                pq.id,
                ROW_NUMBER() OVER (
                    ORDER BY
                        CASE pq.status
                            WHEN 'processing' THEN 0
                            WHEN 'queued'     THEN 1
                            WHEN 'held'       THEN 2
                            WHEN 'failed'     THEN 3
                            WHEN 'completed'  THEN 4
                            ELSE 5
                        END,
                        pq.queue_position ASC NULLS LAST,
                        pq.entered_at ASC
                ) AS display_position
            FROM pipeline_queue pq
        )
        SELECT
            pq.id,
            pq.ticket_id,
            pq.ticket_code,
            pq.status,
            pq.queue_position,
            rq.display_position,
            pq.retry_count,
            COALESCE(pq.retry_count, 0) AS display_retry_count,
            pq.failed_stage,
            pq.failed_at_step,
            pq.failure_reason,
            pq.failure_category,
            pq.entered_at,
            pq.started_at,
            pq.completed_at,
            pq.held_at,
            pq.released_at,
            t.subject,
            t.priority,
            t.ticket_type,
            suggested_resolution_stage.output_state ->> 'suggested_resolution_mode' AS suggested_resolution_mode,
            NULLIF(suggested_resolution_stage.output_state ->> 'suggested_resolution', '') AS suggested_resolution,
            CASE WHEN pq.status = 'processing' THEN last_stage.stage_name ELSE NULL END AS current_stage,
            CASE WHEN pq.status = 'processing' THEN last_stage.step_order ELSE NULL END AS current_step
        FROM pipeline_queue pq
        LEFT JOIN ranked_queue rq ON rq.id = pq.id
        LEFT JOIN tickets t ON t.id = pq.ticket_id
        LEFT JOIN LATERAL (
            SELECT stage_name, step_order
            FROM pipeline_stage_events
            WHERE execution_id = pq.execution_id
              AND event_type = 'output'
            ORDER BY step_order DESC, created_at DESC
            LIMIT 1
        ) last_stage ON TRUE
        LEFT JOIN LATERAL (
            SELECT output_state
            FROM pipeline_stage_events pse
            WHERE pse.ticket_code = pq.ticket_code
              AND pse.stage_name = 'SuggestedResolutionAgent'
              AND pse.event_type = 'output'
            ORDER BY pse.created_at DESC, pse.execution_id DESC
            LIMIT 1
        ) suggested_resolution_stage ON TRUE
        ORDER BY
            CASE pq.status
                WHEN 'processing' THEN 0
                WHEN 'queued'     THEN 1
                WHEN 'held'       THEN 2
                WHEN 'completed'  THEN 3
                ELSE 4
            END,
            pq.queue_position ASC NULLS LAST,
            pq.entered_at DESC
        LIMIT 200
        """
    )


# Route: GET /{queue_id}

@router.get("/{queue_id}")
def get_queue_item(queue_id: str):
    item = _fetch_one(
        """
        WITH ranked_queue AS (
            SELECT
                pq.id,
                ROW_NUMBER() OVER (
                    ORDER BY
                        CASE pq.status
                            WHEN 'processing' THEN 0
                            WHEN 'queued'     THEN 1
                            WHEN 'held'       THEN 2
                            WHEN 'failed'     THEN 3
                            WHEN 'completed'  THEN 4
                            ELSE 5
                        END,
                        pq.queue_position ASC NULLS LAST,
                        pq.entered_at ASC
                ) AS display_position
            FROM pipeline_queue pq
        )
        SELECT
            pq.id,
            pq.ticket_id,
            pq.ticket_code,
            pq.status,
            pq.queue_position,
            rq.display_position,
            pq.retry_count,
            COALESCE(pq.retry_count, 0) AS display_retry_count,
            pq.failed_stage,
            pq.failed_at_step,
            pq.failure_reason,
            pq.failure_category,
            pq.failure_history,
            pq.checkpoint_state,
            pq.operator_corrections,
            pq.ticket_input,
            pq.execution_id,
            pq.entered_at,
            pq.started_at,
            pq.completed_at,
            pq.held_at,
            pq.released_at,
            t.subject,
            t.details,
            t.priority,
            t.ticket_type,
            t.status AS ticket_status,
            CASE WHEN pq.status = 'processing' THEN last_stage.stage_name ELSE NULL END AS current_stage,
            CASE WHEN pq.status = 'processing' THEN last_stage.step_order ELSE NULL END AS current_step
        FROM pipeline_queue pq
        LEFT JOIN ranked_queue rq ON rq.id = pq.id
        LEFT JOIN tickets t ON t.id = pq.ticket_id
        LEFT JOIN LATERAL (
            SELECT stage_name, step_order
            FROM pipeline_stage_events
            WHERE execution_id = pq.execution_id
              AND event_type = 'output'
            ORDER BY step_order DESC, created_at DESC
            LIMIT 1
        ) last_stage ON TRUE
        WHERE pq.id = %s::uuid
        """,
        (queue_id,),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # Fetch stage events for AI explainability.
    # Use the latest output per step_order across the whole ticket_code so a
    # recovered restart still shows previously completed stages from the prior
    # execution rather than only the newest partial execution.
    stages = []
    ticket_code = item.get("ticket_code")
    if ticket_code:
        raw_stages = _fetch_all(
            """
            WITH ranked_stage_events AS (
                SELECT
                    stage_name,
                    step_order,
                    event_type,
                    status,
                    inference_time_ms,
                    confidence_score,
                    input_state,
                    output_state,
                    error_message,
                    created_at,
                    execution_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY step_order
                        ORDER BY
                            CASE
                                WHEN COALESCE(status, '') IN ('success', 'fixed') THEN 0
                                WHEN COALESCE(status, '') = 'warning' THEN 1
                                ELSE 2
                            END,
                            created_at DESC,
                            execution_id DESC
                    ) AS rn
                FROM pipeline_stage_events
                WHERE ticket_code = %s
                  AND event_type = 'output'
            )
            SELECT
                stage_name,
                step_order,
                event_type,
                status,
                inference_time_ms,
                confidence_score,
                input_state,
                output_state,
                error_message,
                created_at,
                execution_id
            FROM ranked_stage_events
            WHERE rn = 1
            ORDER BY step_order ASC, created_at ASC
            """,
            (ticket_code,),
        )
        for stage in raw_stages:
            out = stage.get("output_state") or {}
            stage["explanation"]          = _explain_stage(stage["stage_name"], out, stage.get("error_message"))
            stage["description"]          = _STAGE_DESCRIPTIONS.get(stage["stage_name"], "")
            stage["is_critical"]          = stage["stage_name"] in _CRITICAL_STAGES
            stage["correctable_fields"]   = _STAGE_CORRECTABLE_FIELDS.get(stage["stage_name"], [])
            stages.append(stage)

    failed_stage_name = item.get("failed_stage")
    if (
        failed_stage_name
        and item.get("status") == "held"
        and not any(stage.get("stage_name") == failed_stage_name for stage in stages)
    ):
        synthetic_failed_stage = {
            "stage_name": failed_stage_name,
            "step_order": item.get("failed_at_step") or _STAGE_STEP_ORDER.get(failed_stage_name),
            "event_type": "output",
            "status": "failed",
            "inference_time_ms": None,
            "confidence_score": None,
            "input_state": item.get("checkpoint_state") or {},
            "output_state": {},
            "error_message": item.get("failure_reason"),
            "created_at": item.get("held_at") or item.get("started_at") or item.get("entered_at"),
            "execution_id": item.get("execution_id"),
            "description": _STAGE_DESCRIPTIONS.get(failed_stage_name, ""),
            "is_critical": failed_stage_name in _CRITICAL_STAGES,
            "correctable_fields": _STAGE_CORRECTABLE_FIELDS.get(failed_stage_name, []),
            "explanation": item.get("failure_reason") or "Stage failed before output was recorded.",
        }
        stages.append(synthetic_failed_stage)
        stages.sort(key=lambda stage: (stage.get("step_order") or 999, stage.get("created_at") or ""))

    item["stages"] = stages
    item["operator_corrections"] = item.get("operator_corrections") or {}
    return item


# Route: PATCH /{queue_id}/correct

@router.patch("/{queue_id}/correct")
def correct_stage(queue_id: str, body: CorrectStageRequest):
    """Save operator corrections for a held ticket without releasing it yet."""
    row = _fetch_one(
        "SELECT status, ticket_id, checkpoint_state FROM pipeline_queue WHERE id = %s::uuid",
        (queue_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row["status"] != "held":
        raise HTTPException(status_code=400, detail="Ticket is not in held state")

    _execute(
        "UPDATE pipeline_queue SET operator_corrections = %s::jsonb WHERE id = %s::uuid",
        (json.dumps(body.corrections), queue_id),
    )

    # Record corrections to rescore_reroute_reference so the Review Agent
    # can use them as low-weight training hints for future tickets.
    ticket_id = row.get("ticket_id")
    if ticket_id and body.corrections:
        checkpoint: dict = row.get("checkpoint_state") or {}
        _record_operator_corrections(ticket_id, checkpoint, body.corrections)

    return {"ok": True}


def _record_operator_corrections(
    ticket_id: str,
    checkpoint: dict,
    corrections: dict,
) -> None:
    """
    Record operator pipeline-queue corrections into the learning reference tables.
    - Department corrections → reroute_reference (operator_override)
    - Priority corrections   → rescore_reference (operator_correction)
    Fails silently — best-effort training signal only.
    """
    try:
        import uuid as _uuid

        dept_correction = corrections.get("department") or corrections.get("department_selected")
        priority_correction = corrections.get("priority_label") or corrections.get("priority")

        if not dept_correction and not priority_correction:
            return

        with _db_connect() as conn:
            with conn.cursor() as cur:
                if dept_correction:
                    original_dept = (
                        checkpoint.get("department_selected")
                        or checkpoint.get("department")
                        or None
                    )
                    final_dept = str(dept_correction).strip()
                    cur.execute(
                        """
                        INSERT INTO reroute_reference (
                            id, ticket_id, department,
                            original_dept, corrected_dept,
                            actor_role, source_type
                        ) VALUES (%s, %s::uuid, %s, %s, %s, 'operator', 'operator_override')
                        """,
                        (
                            str(_uuid.uuid4()),
                            ticket_id,
                            final_dept,
                            str(original_dept) if original_dept else None,
                            final_dept,
                        ),
                    )

                if priority_correction:
                    original_priority = checkpoint.get("priority_label") or None
                    final_priority = str(priority_correction).strip()
                    dept = str(
                        checkpoint.get("department_selected")
                        or checkpoint.get("department")
                        or "Unknown"
                    ).strip()
                    cur.execute(
                        """
                        INSERT INTO rescore_reference (
                            id, ticket_id, department,
                            original_priority, corrected_priority,
                            actor_role, source_type
                        ) VALUES (%s, %s::uuid, %s, %s, %s, 'operator', 'operator_correction')
                        """,
                        (
                            str(_uuid.uuid4()),
                            ticket_id,
                            dept,
                            str(original_priority) if original_priority else None,
                            final_priority,
                        ),
                    )
    except Exception as exc:
        logger.warning("pipeline_queue | training reference insert failed: %s", exc)


# Route: POST /{queue_id}/release

@router.post("/{queue_id}/release")
def release_ticket(queue_id: str, body: ReleaseRequest):
    """Apply operator corrections and re-enqueue the held ticket."""
    row = _fetch_one(
        "SELECT status, retry_count, ticket_code FROM pipeline_queue WHERE id = %s::uuid",
        (queue_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row["status"] != "held":
        raise HTTPException(status_code=400, detail="Ticket is not in held state")

    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/queue/release",
            json={"queue_id": queue_id, "corrections": body.corrections},
            timeout=_ORCHESTRATOR_RELEASE_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Orchestrator release failed: {exc}")

    return {"ok": True, "queue_id": queue_id, "ticket_code": row.get("ticket_code")}


# Route: POST /control/pause

@router.post("/control/pause")
def pause_pipeline():
    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/queue/control/pause",
            timeout=_ORCHESTRATOR_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pipeline pause failed: {exc}")


# Route: POST /control/resume

@router.post("/control/resume")
def resume_pipeline():
    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/queue/control/resume",
            timeout=_ORCHESTRATOR_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Pipeline resume failed: {exc}")


# Route: POST /{queue_id}/rerun-stage

@router.post("/{queue_id}/rerun-stage")
def rerun_stage(queue_id: str):
    """Re-run the failed stage through the AI model (no manual corrections)."""
    row = _fetch_one(
        "SELECT status, ticket_code, failed_stage FROM pipeline_queue WHERE id = %s::uuid",
        (queue_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row["status"] != "held":
        raise HTTPException(status_code=400, detail="Ticket is not in held state")

    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/queue/rerun-stage",
            json={"queue_id": queue_id},
            timeout=_ORCHESTRATOR_RERUN_STAGE_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Orchestrator rerun failed: {exc}")

    return {"ok": True, "queue_id": queue_id, "stage": row.get("failed_stage")}


# Route: POST /{queue_id}/rerun

@router.post("/{queue_id}/rerun")
def rerun_queue(queue_id: str):
    """Reset a ticket and rerun the full pipeline from the start."""
    row = _fetch_one(
        "SELECT status, retry_count, ticket_code FROM pipeline_queue WHERE id = %s::uuid",
        (queue_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row["status"] == "completed":
        raise HTTPException(status_code=400, detail="Completed tickets cannot be rerun from the queue")

    try:
        resp = httpx.post(
            f"{ORCHESTRATOR_URL}/queue/rerun",
            json={"queue_id": queue_id},
            timeout=_ORCHESTRATOR_DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Orchestrator rerun failed: {exc}")

    return {"ok": True, "queue_id": queue_id, "ticket_code": row.get("ticket_code")}


# Route: DELETE /{queue_id}

@router.post("/redispatch-unprocessed")
def redispatch_unprocessed():
    """
    Find tickets that were never enqueued (no pipeline_queue row) and re-dispatch
    them to the orchestrator. Returns the list of ticket codes attempted.
    """
    rows = _fetch_all(
        """
        SELECT t.id::text, t.ticket_code, t.details, t.ticket_type, t.subject
        FROM tickets t
        WHERE NOT EXISTS (
            SELECT 1 FROM pipeline_queue pq WHERE pq.ticket_id = t.id
        )
        ORDER BY t.created_at ASC
        LIMIT 50
        """
    )
    if not rows:
        return {"dispatched": [], "message": "No unprocessed tickets found."}

    bases = []
    for url in [ORCHESTRATOR_URL, ORCHESTRATOR_URL_LOCAL]:
        normalized = (url or "").rstrip("/")
        if normalized and normalized not in bases:
            bases.append(normalized)

    results = []
    for row in rows:
        ticket_code = row["ticket_code"]
        details = (row.get("details") or "").strip()
        if not ticket_code or not details:
            results.append({"ticket_code": ticket_code, "ok": False, "reason": "missing details"})
            continue

        payload = {
            "text": details,
            "ticket_id": ticket_code,
            "ticket_type": (row.get("ticket_type") or "complaint").lower(),
            "has_audio": "false",
        }
        if row.get("subject"):
            payload["subject"] = row["subject"]

        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        ok = False
        for base in bases:
            try:
                req = urllib.request.Request(
                    f"{base}/process/text", data=encoded, headers=headers, method="POST"
                )
                with urllib.request.urlopen(req, timeout=_REDISPATCH_HTTP_TIMEOUT) as resp:
                    if resp.status < 300:
                        ok = True
                        break
            except Exception as exc:
                logger.warning("redispatch | ticket=%s target=%s err=%s", ticket_code, base, exc)

        results.append({"ticket_code": ticket_code, "ok": ok})

    return {"dispatched": results}


@router.delete("/{queue_id}")
def delete_queue_item(queue_id: str):
    """Remove from queue and delete the associated ticket and all its data."""
    row = _fetch_one(
        "SELECT id, ticket_id FROM pipeline_queue WHERE id = %s::uuid", (queue_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    ticket_id = row.get("ticket_id")
    # Deleting the ticket cascades to pipeline_queue via FK ON DELETE CASCADE
    if ticket_id:
        _execute("DELETE FROM tickets WHERE id = %s::uuid", (str(ticket_id),))
    else:
        _execute("DELETE FROM pipeline_queue WHERE id = %s::uuid", (queue_id,))
    return {"ok": True, "deleted_queue_id": queue_id, "deleted_ticket_id": str(ticket_id) if ticket_id else None}
