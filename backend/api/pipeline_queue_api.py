"""
Pipeline Queue API — Operator Endpoints
========================================
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


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CorrectStageRequest(BaseModel):
    corrections: Dict[str, Any]


class ReleaseRequest(BaseModel):
    corrections: Dict[str, Any]


class RerunStageRequest(BaseModel):
    pass  # no body needed — reruns the failed stage as-is


# ---------------------------------------------------------------------------
# AI Explainability helpers
# ---------------------------------------------------------------------------

_STAGE_DESCRIPTIONS = {
    "SubjectGenerationAgent":    "Generates a short 2–4 word subject line for the ticket.",
    "SuggestedResolutionAgent":  "Generates a suggested resolution the employee can use.",
    "ClassificationAgent":       "Determines whether the ticket is a Complaint or an Inquiry.",
    "SentimentAgent":            "Extracts the emotional tone of the ticket text (negative / neutral / positive).",
    "AudioAnalysisAgent":        "Analyzes vocal and acoustic patterns from the audio attachment.",
    "SentimentCombinerAgent":    "Combines text and audio sentiment into a single sentiment score.",
    "RecurrenceAgent":           "Checks whether this is a recurring issue from the same customer.",
    "FeatureEngineeringAgent":   "Labels severity, urgency, business impact, and safety concern.",
    "PrioritizationAgent":       "Applies the company rule set to assign a final priority (Low / Medium / High / Critical).",
    "DepartmentRoutingAgent":    "Routes the ticket to the most relevant department.",
}

_CRITICAL_STAGES = {
    "ClassificationAgent", "SentimentAgent", "AudioAnalysisAgent",
    "SentimentCombinerAgent", "FeatureEngineeringAgent",
    "PrioritizationAgent", "DepartmentRoutingAgent",
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
}


def _explain_stage(stage_name: str, output_state: Dict, error_message: Optional[str]) -> str:
    name = stage_name or ""

    if error_message and "fallback" in error_message.lower():
        return f"Stage timed out — mock output used. {error_message}"
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
            tone = "negative" if float(score) < -0.25 else ("positive" if float(score) > 0.25 else "neutral")
            return f"Text sentiment score: {float(score):.3f} → {tone}."
        return "Sentiment extracted from ticket text."

    if name == "AudioAnalysisAgent":
        mode = output_state.get("audio_analysis_mode", "")
        if "fallback" in str(mode) or "mock" in str(mode):
            return "No audio provided or audio analysis unavailable — skipped."
        score = output_state.get("audio_sentiment")
        return f"Audio sentiment score: {float(score):.3f}." if score is not None else "Audio features extracted."

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

    if name == "SubjectGenerationAgent":
        subject = output_state.get("subject", "")
        return f'Subject: "{subject}".' if subject else "Subject generated."

    if name == "SuggestedResolutionAgent":
        res = output_state.get("suggested_resolution", "")
        preview = (res[:120] + "…") if len(str(res)) > 120 else res
        return f'Suggested: "{preview}"' if preview else "Resolution suggestion generated."

    return "Stage completed."


# ---------------------------------------------------------------------------
# Route: GET /stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_queue_stats():
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


# ---------------------------------------------------------------------------
# Route: GET / (list)
# ---------------------------------------------------------------------------

@router.get("")
def list_queue():
    return _fetch_all(
        """
        SELECT
            pq.id,
            pq.ticket_id,
            pq.ticket_code,
            pq.status,
            pq.queue_position,
            pq.retry_count,
            pq.failed_stage,
            pq.failed_at_step,
            pq.failure_reason,
            pq.entered_at,
            pq.started_at,
            pq.completed_at,
            pq.held_at,
            pq.released_at,
            t.subject,
            t.priority,
            t.ticket_type
        FROM pipeline_queue pq
        LEFT JOIN tickets t ON t.id = pq.ticket_id
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


# ---------------------------------------------------------------------------
# Route: GET /{queue_id}
# ---------------------------------------------------------------------------

@router.get("/{queue_id}")
def get_queue_item(queue_id: str):
    item = _fetch_one(
        """
        SELECT
            pq.id,
            pq.ticket_id,
            pq.ticket_code,
            pq.status,
            pq.queue_position,
            pq.retry_count,
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
            t.status AS ticket_status
        FROM pipeline_queue pq
        LEFT JOIN tickets t ON t.id = pq.ticket_id
        WHERE pq.id = %s::uuid
        """,
        (queue_id,),
    )
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # Fetch stage events for AI explainability
    stages = []
    if item.get("execution_id"):
        raw_stages = _fetch_all(
            """
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
                created_at
            FROM pipeline_stage_events
            WHERE execution_id = %s::uuid
              AND event_type = 'output'
            ORDER BY step_order ASC, created_at ASC
            """,
            (str(item["execution_id"]),),
        )
        for stage in raw_stages:
            out = stage.get("output_state") or {}
            stage["explanation"]          = _explain_stage(stage["stage_name"], out, stage.get("error_message"))
            stage["description"]          = _STAGE_DESCRIPTIONS.get(stage["stage_name"], "")
            stage["is_critical"]          = stage["stage_name"] in _CRITICAL_STAGES
            stage["correctable_fields"]   = _STAGE_CORRECTABLE_FIELDS.get(stage["stage_name"], [])
            stages.append(stage)

    item["stages"] = stages
    item["operator_corrections"] = item.get("operator_corrections") or {}
    return item


# ---------------------------------------------------------------------------
# Route: PATCH /{queue_id}/correct
# ---------------------------------------------------------------------------

@router.patch("/{queue_id}/correct")
def correct_stage(queue_id: str, body: CorrectStageRequest):
    """Save operator corrections for a held ticket without releasing it yet."""
    row = _fetch_one(
        "SELECT status FROM pipeline_queue WHERE id = %s::uuid", (queue_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Queue item not found")
    if row["status"] != "held":
        raise HTTPException(status_code=400, detail="Ticket is not in held state")

    _execute(
        "UPDATE pipeline_queue SET operator_corrections = %s::jsonb WHERE id = %s::uuid",
        (json.dumps(body.corrections), queue_id),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# Route: POST /{queue_id}/release
# ---------------------------------------------------------------------------

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
            timeout=10.0,
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Orchestrator release failed: {exc}")

    return {"ok": True, "queue_id": queue_id, "ticket_code": row.get("ticket_code")}


# ---------------------------------------------------------------------------
# Route: POST /{queue_id}/rerun-stage
# ---------------------------------------------------------------------------

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
            timeout=90.0,  # stage can take up to 60s + buffer
        )
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Orchestrator rerun failed: {exc}")

    return {"ok": True, "queue_id": queue_id, "stage": row.get("failed_stage")}


# ---------------------------------------------------------------------------
# Route: DELETE /{queue_id}
# ---------------------------------------------------------------------------

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
                with urllib.request.urlopen(req, timeout=10) as resp:
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