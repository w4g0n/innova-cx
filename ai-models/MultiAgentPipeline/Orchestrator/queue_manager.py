"""
Pipeline Queue Manager
======================
Manages the persistent pipeline_queue table and executes tickets
one at a time through the pipeline, stage by stage.

Key behaviours (per agreed spec):
  - Serial processing — one ticket at a time; held tickets don't block the queue.
  - Critical stages: if they time-out or raise, the pipeline stops, the ticket
    is marked 'held', and the operator receives a notification.
  - Non-critical stages: failures fall back to a mock output and the pipeline
    continues.
  - On release: operator corrections are merged into the checkpoint state, then
    only stages AFTER the failed stage re-run (always includes Prioritization
    and SLA when the failed stage is upstream of them).
  - Retry: up to 3 attempts; each retry the ticket goes to the bottom of the
    queue. After 3 failures the ticket stays permanently held.

Stages in order:
    step  1  RecurrenceAgent             CRITICAL      (V11: first check — links recurring tickets)
    step  2  SubjectGenerationAgent      non-critical
    step  3  SuggestedResolutionAgent    non-critical
    step  4  ClassificationAgent         CRITICAL
    step  5  SentimentAgent              CRITICAL
    step  6  AudioAnalysisAgent          CRITICAL  (optional)
    step  7  SentimentCombinerAgent      CRITICAL
    step  8  FeatureEngineeringAgent     CRITICAL
    step  9  PrioritizationAgent         CRITICAL
    step 10  DepartmentRoutingAgent      CRITICAL
    step 11  ReviewAgent                 CRITICAL
"""

import asyncio
import copy
import json
import logging
import math
import os
import time
import uuid
from typing import Any

from db import db_connect
from execution_logger import _write_stage_event

from agents.step01_subjectgeneration.step import generate_subject
from agents.step02_suggestedresolution.step import generate_suggested_resolution
from agents.step03_classifier.step import classify
from agents.step04_sentimentanalysis.step import analyze_sentiment
from agents.step05_audioanalysis.step import analyze_audio
from agents.step06_sentimentcombiner.step import combine_sentiment
from agents.step01_recurrence.step import check_recurrence
from agents.step08_featureengineering.step import engineer_features
from agents.step09_priority.step import score_priority
from agents.step10_router.step import route_and_store
from agents.step11_reviewagent.step import review_pipeline

logger = logging.getLogger(__name__)

STAGE_TIMEOUT_SECONDS = max(1.0, float(os.getenv("PIPELINE_STAGE_TIMEOUT_SECONDS", "60")))
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
MAX_RETRIES = 3
REVIEW_AGENT_STAGE_TIMEOUT_SECONDS = 180.0

# ---------------------------------------------------------------------------
# Stage registry
# ---------------------------------------------------------------------------

STAGES = [
    # (name, fn, step_order, is_critical)
    # Step 1: Recurrence check — runs first, before any AI processing.
    # Detects recurring submissions via transformer similarity and applies
    # 4-way branch logic (A/B/C stop the pipeline; D continues with context).
    ("RecurrenceAgent",            check_recurrence,               1,  True),
    ("SubjectGenerationAgent",     generate_subject,               2,  False),
    ("SuggestedResolutionAgent",   generate_suggested_resolution,  3,  False),
    ("ClassificationAgent",        classify,                       4,  True),
    ("SentimentAgent",             analyze_sentiment,              5,  True),
    ("AudioAnalysisAgent",         analyze_audio,                  6,  True),
    ("SentimentCombinerAgent",     combine_sentiment,              7,  True),
    ("FeatureEngineeringAgent",    engineer_features,              8,  True),
    ("PrioritizationAgent",        score_priority,                 9,  True),
    ("DepartmentRoutingAgent",     route_and_store,                10, True),
    # Step 11: Review Agent — automated quality gate and final release
    # is_critical=True: if this fails, ticket must not be silently released
    # without validation. Every other critical stage has the Review Agent
    # above it to catch issues; the Review Agent has no such safety net.
    ("ReviewAgent",                review_pipeline,                11, True),
]

STAGE_BY_NAME = {name: (fn, order, critical) for name, fn, order, critical in STAGES}
STAGE_BY_ORDER = {order: (name, fn, critical) for name, fn, order, critical in STAGES}
PIPELINE_TOTAL_STEPS = len(STAGES)


def _stage_timeout_seconds(stage_name: str) -> float:
    if stage_name == "ReviewAgent":
        return max(STAGE_TIMEOUT_SECONDS, REVIEW_AGENT_STAGE_TIMEOUT_SECONDS)
    return STAGE_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _safe_value(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_value(i) for i in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_value(v) for k, v in obj.items()}
    return str(obj)


def _safe_json(obj: Any) -> Any:
    try:
        return json.loads(json.dumps(obj, default=str, allow_nan=False))
    except (TypeError, ValueError):
        cleaned = _safe_value(obj)
        try:
            return json.loads(json.dumps(cleaned, allow_nan=False))
        except (TypeError, ValueError):
            return {"_serialization_error": str(obj)[:500]}


# ---------------------------------------------------------------------------
# Mock/fallback outputs for critical stages
# ---------------------------------------------------------------------------

def _mock_output_for_stage(stage_name: str, state: dict) -> dict:
    """Return a minimal mock output so downstream stages can proceed."""
    out = copy.deepcopy(state)
    name = str(stage_name or "")
    if name == "ClassificationAgent":
        out["label"] = out.get("label") or None
        out["class_confidence"] = float(out.get("class_confidence", 0.0) or 0.0)
        out["classification_source"] = "mock_fallback"
    elif name == "SentimentAgent":
        out["text_sentiment"] = float(out.get("text_sentiment", 0.0) or 0.0)
        out["sentiment_mode"] = "mock_fallback"
    elif name == "AudioAnalysisAgent":
        out["audio_analysis_mode"] = "mock_fallback"
    elif name == "SentimentCombinerAgent":
        out["sentiment_score_numeric"] = float(out.get("text_sentiment", 0.0) or 0.0)
        out["sentiment_score"] = "Neutral"
        out["sentiment_combiner_mode"] = "mock_fallback"
    elif name == "FeatureEngineeringAgent":
        out["business_impact"] = out.get("business_impact") or "medium"
        out["issue_severity"] = out.get("issue_severity") or "medium"
        out["issue_urgency"] = out.get("issue_urgency") or "medium"
        out["safety_concern"] = out.get("safety_concern") or False
        out["feature_labeler_mode"] = "mock_fallback"
    elif name == "PrioritizationAgent":
        out["priority_label"] = out.get("priority_label") or "Medium"
        out["priority_score"] = out.get("priority_score") or 2
        out["priority_mode"] = "mock_fallback"
    elif name == "DepartmentRoutingAgent":
        out["department_routing_source"] = "mock_fallback"
    elif name == "ReviewAgent":
        out["review_agent_verdict"] = "held_operator_review"
        out["review_agent_verdict_reason"] = "stage_failure_fallback"
        out["review_agent_mode"] = "mock_fallback"
    out["_mock_fallback_stage"] = name
    return out


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_NEXT_POSITION_SQL = (
    "SELECT COALESCE(MAX(queue_position), 0) + 1 FROM pipeline_queue "
    "WHERE status IN ('queued','processing','held')"
)


def _next_queue_position(cur) -> int:
    """Return the next available queue position within an open cursor."""
    cur.execute(_NEXT_POSITION_SQL)
    return cur.fetchone()[0]


def ensure_pipeline_control_table() -> None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runtime_control (
                    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton = TRUE),
                    is_paused BOOLEAN NOT NULL DEFAULT FALSE,
                    paused_at TIMESTAMPTZ NULL,
                    resumed_at TIMESTAMPTZ NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute(
                """
                INSERT INTO pipeline_runtime_control (singleton, is_paused)
                VALUES (TRUE, FALSE)
                ON CONFLICT (singleton) DO NOTHING
                """
            )


def is_pipeline_paused() -> bool:
    ensure_pipeline_control_table()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT is_paused FROM pipeline_runtime_control WHERE singleton = TRUE"
            )
            row = cur.fetchone()
            return bool(row[0]) if row else False


def get_pipeline_control_state() -> dict:
    ensure_pipeline_control_table()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT is_paused, paused_at, resumed_at, updated_at
                FROM pipeline_runtime_control
                WHERE singleton = TRUE
                """
            )
            row = cur.fetchone()
            return {
                "is_paused": bool(row[0]) if row else False,
                "paused_at": row[1] if row else None,
                "resumed_at": row[2] if row else None,
                "updated_at": row[3] if row else None,
            }


def _db_enqueue(ticket_id: str, ticket_code: str, ticket_input: dict) -> str:
    """Insert a new row into pipeline_queue and return its UUID."""
    queue_id = str(uuid.uuid4())
    with db_connect() as conn:
        with conn.cursor() as cur:
            pos = _next_queue_position(cur)
            cur.execute(
                """
                INSERT INTO pipeline_queue
                    (id, ticket_id, ticket_code, status, queue_position, ticket_input)
                VALUES (%s, %s::uuid, %s, 'queued', %s, %s::jsonb)
                """,
                (queue_id, ticket_id, ticket_code,
                 pos, json.dumps(_safe_json(ticket_input))),
            )
    return queue_id


def _db_set_processing(queue_id: str, execution_id: str) -> None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'processing',
                    started_at = now(),
                    execution_id = %s::uuid,
                    failed_stage = NULL,
                    failed_at_step = NULL,
                    held_at = NULL,
                    failure_reason = NULL,
                    failure_category = NULL,
                    released_at = NULL
                WHERE id = %s::uuid
                """,
                (execution_id, queue_id),
            )


def _db_set_completed(queue_id: str) -> None:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'completed',
                    completed_at = now(),
                    queue_position = NULL,
                    execution_id = NULL,
                    failed_stage = NULL,
                    failed_at_step = NULL,
                    failure_reason = NULL,
                    failure_category = NULL,
                    checkpoint_state = '{}'::jsonb,
                    operator_corrections = '{}'
                WHERE id = %s::uuid
                """,
                (queue_id,),
            )


def _db_execution_is_current(queue_id: str, execution_id: str) -> bool:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM pipeline_queue
                WHERE id = %s::uuid
                  AND status = 'processing'
                  AND execution_id = %s::uuid
                """,
                (queue_id, execution_id),
            )
            return cur.fetchone() is not None


def _db_update_progress_checkpoint(
    queue_id: str,
    execution_id: str,
    stage_name: str,
    step_order: int,
    state: dict,
) -> None:
    """
    Persist the latest safe resume point for an in-flight execution.
    This lets restart recovery and manual pause resume from the most recent
    completed stage instead of an older checkpoint.
    """
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_queue
                SET checkpoint_state = %s::jsonb,
                    failed_stage = %s,
                    failed_at_step = %s
                WHERE id = %s::uuid
                  AND status = 'processing'
                  AND execution_id = %s::uuid
                """,
                (
                    json.dumps(_safe_json(state)),
                    stage_name,
                    step_order,
                    queue_id,
                    execution_id,
                ),
            )


def _categorise_failure(reason: str) -> str:
    r = str(reason or "").lower()
    if "timeout" in r:
        return "timeout"
    if any(k in r for k in ("connection", "connect", "refused", "unreachable", "network")):
        return "connection_error"
    if any(k in r for k in ("error", "exception", "traceback", "failed", "crash")):
        return "model_error"
    return "unknown"


def _db_set_held(
    queue_id: str,
    failed_stage: str,
    failed_at_step: int,
    failure_reason: str,
    checkpoint_state: dict,
) -> None:
    category = _categorise_failure(failure_reason)
    with db_connect() as conn:
        with conn.cursor() as cur:
            # Append to failure_history array
            history_entry = json.dumps({
                "stage": failed_stage,
                "category": category,
                "reason": failure_reason,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'held',
                    held_at = now(),
                    queue_position = NULL,
                    failed_stage = %s,
                    failed_at_step = %s,
                    failure_reason = %s,
                    failure_category = %s,
                    failure_history = failure_history || %s::jsonb,
                    checkpoint_state = %s::jsonb
                WHERE id = %s::uuid
                """,
                (
                    failed_stage,
                    failed_at_step,
                    failure_reason,
                    category,
                    f"[{history_entry}]",
                    json.dumps(_safe_json(checkpoint_state)),
                    queue_id,
                ),
            )


def _db_retry_to_bottom(queue_id: str) -> None:
    """Increment retry count and move ticket to bottom of queue."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            new_pos = _next_queue_position(cur)
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'queued',
                    queue_position = %s,
                    retry_count = retry_count + 1,
                    failed_stage = NULL,
                    failed_at_step = NULL,
                    failure_reason = NULL,
                    failure_category = NULL,
                    checkpoint_state = '{}',
                    operator_corrections = '{}',
                    started_at = NULL,
                    held_at = NULL
                WHERE id = %s::uuid
                """,
                (new_pos, queue_id),
            )


def _db_permanently_held(queue_id: str, failure_reason: str) -> None:
    """Mark a ticket as permanently held (max retries exceeded)."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'held',
                    held_at = now(),
                    queue_position = NULL,
                    failure_reason = %s
                WHERE id = %s::uuid
                """,
                (failure_reason, queue_id),
            )


def _db_dequeue_next() -> dict | None:
    """Fetch the next queued item (lowest queue_position) and return it."""
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, ticket_id, ticket_code, retry_count, ticket_input,
                       checkpoint_state, operator_corrections, failed_stage, failed_at_step,
                       failure_category
                FROM pipeline_queue
                WHERE status = 'queued'
                ORDER BY queue_position ASC NULLS LAST, entered_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """,
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": str(row[0]),
                "ticket_id": str(row[1]) if row[1] else None,
                "ticket_code": row[2],
                "retry_count": row[3],
                "ticket_input": row[4] or {},
                "checkpoint_state": row[5] or {},
                "operator_corrections": row[6] or {},
                "failed_stage": row[7],
                "failed_at_step": row[8],
                "failure_category": row[9],
            }


def _build_initial_state(
    ticket_id: str | None,
    ticket_code: str | None,
    ticket_input: dict,
    execution_id: str | None,
) -> dict:
    inp = ticket_input or {}
    return {
        "text": inp.get("text", ""),
        "ticket_id": ticket_id,
        "ticket_code": ticket_code,
        "subject": inp.get("subject"),
        "has_audio": bool(inp.get("has_audio", False)),
        "audio_features": inp.get("audio_features") or {},
        "created_by_user_id": inp.get("created_by_user_id"),
        "ticket_source": inp.get("ticket_source"),
        "label": None,
        "status": "Open",
        "_execution_id": execution_id,
        "_pipeline_total_steps": PIPELINE_TOTAL_STEPS,
    }


def pause_queue_item(queue_id: str) -> bool:
    """
    Pause a queued or processing ticket and hold it at its current checkpoint.
    Resume continues from the next stage after the last completed stage.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_id, ticket_code, status, execution_id, ticket_input
                    FROM pipeline_queue
                    WHERE id = %s::uuid
                    FOR UPDATE
                    """,
                    (queue_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False

                ticket_id, ticket_code, status, execution_id, ticket_input = row
                if status not in {"queued", "processing"}:
                    return False

                checkpoint_state = _build_initial_state(ticket_id, ticket_code, ticket_input or {}, execution_id)
                failed_stage = None
                failed_at_step = 1
                resume_from_step = 2
                resume_stage = STAGE_BY_ORDER.get(resume_from_step, (None, None, None))[0]

                if status == "processing" and execution_id:
                    cur.execute(
                        """
                        SELECT stage_name, step_order, output_state
                        FROM pipeline_stage_events
                        WHERE execution_id = %s::uuid
                          AND event_type = 'output'
                        ORDER BY step_order DESC, created_at DESC
                        LIMIT 1
                        """,
                        (execution_id,),
                    )
                    stage_row = cur.fetchone()
                    if stage_row:
                        failed_stage = stage_row[0]
                        failed_at_step = stage_row[1]
                        checkpoint_state = stage_row[2] or checkpoint_state
                        resume_from_step = max(2, int(failed_at_step) + 1)
                        resume_stage = STAGE_BY_ORDER.get(resume_from_step, (failed_stage, None, None))[0]

                checkpoint_state["_resume_from_step"] = resume_from_step
                checkpoint_state["_resume_stage"] = resume_stage

                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET status = 'held',
                        queue_position = NULL,
                        held_at = now(),
                        failed_stage = %s,
                        failed_at_step = %s,
                        failure_reason = 'Paused by operator',
                        failure_category = 'manual_pause',
                        checkpoint_state = %s::jsonb,
                        operator_corrections = '{}'
                    WHERE id = %s::uuid
                    """,
                    (
                        resume_stage,
                        resume_from_step,
                        json.dumps(_safe_json(checkpoint_state)),
                        queue_id,
                    ),
                )
        logger.info("queue | paused queue_id=%s", queue_id)
        return True
    except Exception as exc:
        logger.error("queue | pause_queue_item failed queue_id=%s err=%s", queue_id, exc)
        return False


def resume_paused_queue_item(queue_id: str) -> bool:
    """
    Resume a manually paused ticket from its stored checkpoint.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, failure_category
                    FROM pipeline_queue
                    WHERE id = %s::uuid
                    FOR UPDATE
                    """,
                    (queue_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                status, failure_category = row
                if status != "held" or failure_category != "manual_pause":
                    return False

                new_pos = _next_queue_position(cur)
                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET status = 'queued',
                        queue_position = %s,
                        failed_stage = NULL,
                        failed_at_step = NULL,
                        failure_reason = NULL,
                        failure_category = NULL,
                        held_at = NULL,
                        started_at = NULL,
                        released_at = now()
                    WHERE id = %s::uuid
                    """,
                    (new_pos, queue_id),
                )
        logger.info("queue | resumed paused queue_id=%s", queue_id)
        return True
    except Exception as exc:
        logger.error("queue | resume_paused_queue_item failed queue_id=%s err=%s", queue_id, exc)
        return False


def _db_resume_manual_pause_items_to_front() -> int:
    resumed = 0
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text
                FROM pipeline_queue
                WHERE status = 'held'
                  AND failure_category = 'manual_pause'
                ORDER BY held_at ASC NULLS LAST, entered_at ASC
                FOR UPDATE
                """
            )
            paused_ids = [row_id for (row_id,) in (cur.fetchall() or [])]
            if not paused_ids:
                return 0

            cur.execute(
                """
                UPDATE pipeline_queue
                SET queue_position = queue_position + %s
                WHERE status = 'queued'
                  AND queue_position IS NOT NULL
                """,
                (len(paused_ids),),
            )

            for idx, queue_id in enumerate(paused_ids, start=1):
                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET status = 'queued',
                        queue_position = %s,
                        failed_stage = NULL,
                        failed_at_step = NULL,
                        failure_reason = NULL,
                        failure_category = NULL,
                        held_at = NULL,
                        started_at = NULL,
                        released_at = now()
                    WHERE id = %s::uuid
                    """,
                    (idx, queue_id),
                )
                resumed += 1
    return resumed


def pause_pipeline_globally() -> dict:
    ensure_pipeline_control_table()
    processing_queue_id = None
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runtime_control
                SET is_paused = TRUE,
                    paused_at = COALESCE(paused_at, now()),
                    updated_at = now()
                WHERE singleton = TRUE
                """
            )
            cur.execute(
                """
                SELECT id::text
                FROM pipeline_queue
                WHERE status = 'processing'
                ORDER BY started_at ASC NULLS LAST, entered_at ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            processing_queue_id = row[0] if row else None

    paused_processing = False
    if processing_queue_id:
        paused_processing = pause_queue_item(processing_queue_id)

    logger.info(
        "queue | global pause enabled processing_queue_id=%s paused_processing=%s",
        processing_queue_id,
        paused_processing,
    )
    return {
        "ok": True,
        "is_paused": True,
        "processing_queue_id": processing_queue_id,
        "paused_processing": paused_processing,
    }


def resume_pipeline_globally() -> dict:
    ensure_pipeline_control_table()
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runtime_control
                SET is_paused = FALSE,
                    resumed_at = now(),
                    updated_at = now()
                WHERE singleton = TRUE
                """
            )
    resumed_items = _db_resume_manual_pause_items_to_front()
    logger.info("queue | global pause disabled resumed_items=%d", resumed_items)
    return {
        "ok": True,
        "is_paused": False,
        "resumed_items": resumed_items,
    }


def _db_requeue_orphaned_processing_items() -> int:
    """
    Recover queue items left in 'processing' after an orchestrator restart/crash.

    These rows already have a checkpoint_state/failed_at_step that reflects the
    last completed stage. Recovery should therefore resume from that checkpoint,
    not restart the whole ticket or count as a manual retry.
    """
    recovered = 0
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text
                FROM pipeline_queue
                WHERE status = 'processing'
                ORDER BY started_at ASC NULLS LAST, entered_at ASC
                FOR UPDATE
                """
            )
            rows = [queue_id for (queue_id,) in (cur.fetchall() or [])]
            if not rows:
                return 0

            # Clear the recovered rows out of the active ordering first so they
            # do not count themselves when we assign fresh queue positions.
            cur.execute(
                """
                UPDATE pipeline_queue
                SET status = 'queued',
                    queue_position = NULL,
                    started_at = NULL,
                    held_at = NULL,
                    released_at = now(),
                    retry_count = retry_count + 1,
                    failure_category = 'recovered_restart',
                    failure_reason = 'Recovered after orchestrator restart'
                WHERE id = ANY(%s::uuid[])
                """,
                (rows,),
            )

            for queue_id in rows:
                new_pos = _next_queue_position(cur)
                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET queue_position = %s
                    WHERE id = %s::uuid
                    """,
                    (new_pos, queue_id),
                )
                recovered += 1
    return recovered


def _notify_operator(ticket_id: str, ticket_code: str, failed_stage: str, queue_id: str) -> None:
    """Notify all operators of a held ticket via the backend notification service."""
    try:
        import httpx as _httpx
        _httpx.post(
            f"{BACKEND_URL}/api/internal/notify-operators",
            json={
                "ticket_id": ticket_id,
                "ticket_code": ticket_code,
                "title": f"Pipeline Held — {ticket_code or ticket_id}",
                "message": (
                    f"Stage '{failed_stage}' failed for ticket {ticket_code or ticket_id}. "
                    f"Review and correct the output in the Pipeline Queue. Queue ID: {queue_id}"
                ),
            },
            timeout=5.0,
        )
    except Exception as exc:
        logger.error("queue | failed to send operator notification: %s", exc)


def _notify_operator_noncritical(
    queue_id: str, stage_name: str, reason: str, execution_id: str
) -> None:
    """Informational notification when a non-critical stage falls back to mock output."""
    try:
        import httpx as _httpx
        _httpx.post(
            f"{BACKEND_URL}/api/internal/notify-operators",
            json={
                "ticket_id": None,
                "ticket_code": None,
                "queue_id": queue_id,
                "notification_type": "system",
                "title": f"Pipeline Warning — {stage_name} used fallback",
                "message": (
                    f"Non-critical stage '{stage_name}' failed and a mock output was used. "
                    f"The ticket continues processing normally. Reason: {reason} "
                    f"(queue_id: {queue_id})"
                ),
            },
            timeout=5.0,
        )
    except Exception as exc:
        logger.error("queue | failed to send non-critical notification: %s", exc)


# ---------------------------------------------------------------------------
# Single stage runner
# ---------------------------------------------------------------------------

async def _run_stage(
    stage_name: str,
    fn,
    step_order: int,
    is_critical: bool,
    state: dict,
    execution_id: str,
) -> tuple[dict, bool, str | None]:
    """
    Run one pipeline stage with timeout.

    Returns:
        (output_state, stage_failed_critically, failure_reason)

    For non-critical stages: always returns (output_state, False, None)
    For critical stages on failure: returns (mock_output, True, reason)
    """
    ticket_id = state.get("ticket_id")
    ticket_code = state.get("ticket_code") or state.get("ticket_id")
    input_snapshot = {k: v for k, v in state.items() if not k.startswith("_")}

    start = time.monotonic()
    stage_timeout = _stage_timeout_seconds(stage_name)
    try:
        result = await asyncio.wait_for(fn(state), timeout=stage_timeout)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "queue_stage_ok | stage=%s step=%d time_ms=%d exec=%s",
            stage_name, step_order, elapsed_ms, execution_id,
        )
        output_snapshot = {k: v for k, v in result.items() if not k.startswith("_")}
        _write_stage_event(
            execution_id=execution_id,
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            agent_name=stage_name,
            step_order=step_order,
            event_type="output",
            status="success",
            input_state=input_snapshot,
            output_state=output_snapshot,
            inference_time_ms=elapsed_ms,
            confidence_score=None,
            error_message=None,
        )
        return result, False, None

    except asyncio.TimeoutError:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        reason = f"Timeout after {stage_timeout:.0f}s"
        logger.warning(
            "queue_stage_timeout | stage=%s step=%d exec=%s timeout_s=%.0f",
            stage_name, step_order, execution_id, stage_timeout,
        )
        mock = _mock_output_for_stage(stage_name, state)
        output_snapshot = {k: v for k, v in mock.items() if not k.startswith("_")}
        _write_stage_event(
            execution_id=execution_id,
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            agent_name=stage_name,
            step_order=step_order,
            event_type="output",
            status="failed" if is_critical else "running",
            input_state=input_snapshot,
            output_state=output_snapshot,
            inference_time_ms=elapsed_ms,
            confidence_score=None,
            error_message=reason,
        )
        if is_critical:
            return mock, True, reason
        else:
            return mock, False, reason

    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            "queue_stage_error | stage=%s step=%d exec=%s err=%s",
            stage_name, step_order, execution_id, reason,
        )
        mock = _mock_output_for_stage(stage_name, state)
        output_snapshot = {k: v for k, v in mock.items() if not k.startswith("_")}
        _write_stage_event(
            execution_id=execution_id,
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            agent_name=stage_name,
            step_order=step_order,
            event_type="output",
            status="failed" if is_critical else "running",
            input_state=input_snapshot,
            output_state=output_snapshot,
            inference_time_ms=elapsed_ms,
            confidence_score=None,
            error_message=reason,
        )
        if is_critical:
            return mock, True, reason
        else:
            return mock, False, reason


# ---------------------------------------------------------------------------
# Pipeline runner (from a given step_order)
# ---------------------------------------------------------------------------

async def run_pipeline_from(
    state: dict,
    from_step: int,
    queue_id: str,
    execution_id: str,
) -> tuple[dict, str | None, int | None, str | None]:
    """
    Run pipeline stages starting from `from_step` (inclusive).

    Returns:
        (final_state, failed_stage_name, failed_at_step, failure_reason)
        If all stages succeed, failed_stage_name is None.
    """
    first_critical_failure: tuple[str, int, str | None] | None = None

    for stage_name, fn, step_order, is_critical in STAGES:
        if step_order < from_step:
            continue

        # Recurrence branches A/B/C absorb the ticket into an existing one —
        # no further pipeline processing needed.
        if state.get("_recurrence_handled"):
            logger.info(
                "pipeline | early exit after RecurrenceAgent (branch=%s) — ticket absorbed",
                state.get("recurrence_branch"),
            )
            break

        if not _db_execution_is_current(queue_id, execution_id):
            return state, "__cancelled__", None, "Execution superseded by rerun"

        # Snapshot state just before this stage (for checkpoint on failure)
        checkpoint = copy.deepcopy(state)

        result, critical_failed, reason = await _run_stage(
            stage_name, fn, step_order, is_critical, state, execution_id
        )

        if not _db_execution_is_current(queue_id, execution_id):
            return state, "__cancelled__", None, "Execution superseded by rerun"

        state = result

        try:
            _db_update_progress_checkpoint(
                queue_id=queue_id,
                execution_id=execution_id,
                stage_name=stage_name,
                step_order=step_order,
                state=state,
            )
        except Exception as exc:
            logger.error(
                "queue_checkpoint_error | queue_id=%s stage=%s step=%d exec=%s err=%s",
                queue_id, stage_name, step_order, execution_id, exc,
            )

        if critical_failed:
            if stage_name == "ReviewAgent":
                return state, stage_name, step_order, reason

            if first_critical_failure is None:
                first_critical_failure = (stage_name, step_order, reason)

            logger.warning(
                "pipeline | pre-review critical failure stage=%s step=%d exec=%s reason=%s; continuing with fallback state to ReviewAgent",
                stage_name,
                step_order,
                execution_id,
                reason,
            )
            continue

        if reason:
            # Non-critical stage used a fallback — notify operator but keep going
            _notify_operator_noncritical(
                queue_id, stage_name, reason, execution_id
            )

    if first_critical_failure is not None:
        failed_stage, failed_step, failed_reason = first_critical_failure
        state["_pre_review_critical_failure_stage"] = failed_stage
        state["_pre_review_critical_failure_step"] = failed_step
        state["_pre_review_critical_failure_reason"] = failed_reason

    return state, None, None, None


# ---------------------------------------------------------------------------
# Public API: enqueue
# ---------------------------------------------------------------------------

def enqueue_ticket(
    ticket_id: str,
    ticket_code: str,
    text: str,
    subject: str | None,
    has_audio: bool,
    audio_features: dict,
    created_by_user_id: str | None,
    ticket_source: str | None,
) -> str:
    """
    Add a ticket to the persistent queue. Returns the queue_id.
    Called from the orchestrator's /process/text endpoint.
    """
    ticket_input = {
        "text": text,
        "subject": subject,
        "has_audio": has_audio,
        "audio_features": audio_features,
        "created_by_user_id": created_by_user_id,
        "ticket_source": ticket_source,
    }
    queue_id = _db_enqueue(ticket_id, ticket_code, ticket_input)
    logger.info("queue | enqueued ticket_id=%s queue_id=%s", ticket_id, queue_id)
    return queue_id


# ---------------------------------------------------------------------------
# Public API: release (operator correction)
# ---------------------------------------------------------------------------

def release_held_ticket(queue_id: str, corrections: dict) -> bool:
    """
    Apply operator corrections and release a held ticket.
    - For final ReviewAgent holds, operator release completes the queue item
      immediately and removes it from Queue Management.
    - For earlier-stage holds, corrections are stored and the ticket is
      re-enqueued to continue from the next stage.
    `corrections` is a dict of the failed stage's corrected output fields.
    Returns True on success.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, retry_count, failed_stage, failed_at_step, ticket_id
                    FROM pipeline_queue
                    WHERE id = %s::uuid
                    """,
                    (queue_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                status, retry_count, failed_stage, failed_at_step, ticket_id = row
                if status != "held":
                    return False

                # Store corrections
                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET operator_corrections = %s::jsonb,
                        released_at = now()
                    WHERE id = %s::uuid
                    """,
                    (json.dumps(_safe_json(corrections)), queue_id),
                )

                is_final_review_hold = (
                    str(failed_stage or "").strip() == "ReviewAgent"
                    or int(failed_at_step or 0) >= 12
                )

                if is_final_review_hold:
                    corrected_department = str(corrections.get("department") or "").strip() or None
                    corrected_priority = str(corrections.get("priority_label") or "").strip() or None
                    corrected_label = str(corrections.get("label") or "").strip().lower() or None

                    if corrected_department:
                        cur.execute(
                            """
                            UPDATE tickets t
                               SET department_id = d.id,
                                   updated_at = now()
                              FROM departments d
                             WHERE d.name = %s
                               AND t.id = %s::uuid
                            """,
                            (corrected_department, ticket_id),
                        )
                        cur.execute(
                            """
                            UPDATE department_routing
                               SET final_department = %s,
                                   is_confident = TRUE,
                                   updated_at = now()
                             WHERE ticket_id = %s::uuid
                            """,
                            (corrected_department, ticket_id),
                        )

                    if corrected_priority:
                        priority_title = corrected_priority.capitalize()
                        cur.execute(
                            """
                            UPDATE tickets
                               SET priority = %s::ticket_priority,
                                   model_priority = %s::ticket_priority,
                                   priority_assigned_at = COALESCE(priority_assigned_at, now()),
                                   updated_at = now()
                             WHERE id = %s::uuid
                            """,
                            (priority_title, priority_title, ticket_id),
                        )

                    if corrected_label in {"complaint", "inquiry"}:
                        ticket_type = "Complaint" if corrected_label == "complaint" else "Inquiry"
                        cur.execute(
                            """
                            UPDATE tickets
                               SET ticket_type = %s,
                                   updated_at = now()
                             WHERE id = %s::uuid
                            """,
                            (ticket_type, ticket_id),
                        )

                    cur.execute(
                        """
                        UPDATE tickets
                           SET status = CASE
                               WHEN department_id IS NOT NULL THEN 'Assigned'::ticket_status
                               ELSE 'Open'::ticket_status
                           END,
                               updated_at = now()
                         WHERE id = %s::uuid
                        """,
                        (ticket_id,),
                    )

                    cur.execute(
                        """
                        UPDATE pipeline_queue
                        SET status = 'completed',
                            completed_at = now(),
                            queue_position = NULL,
                            execution_id = NULL,
                            failed_stage = NULL,
                            failed_at_step = NULL,
                            failure_reason = NULL,
                            failure_category = NULL,
                            checkpoint_state = '{}'::jsonb,
                            operator_corrections = '{}',
                            held_at = NULL
                        WHERE id = %s::uuid
                        """,
                        (queue_id,),
                    )
                    logger.info(
                        "queue | operator_release_completed queue_id=%s stage=%s retries=%d",
                        queue_id, failed_stage, retry_count,
                    )
                    return True

        if retry_count >= MAX_RETRIES:
            _db_permanently_held(queue_id, f"Max retries ({MAX_RETRIES}) exceeded after operator release")
            return False

        _db_retry_to_bottom(queue_id)
        logger.info("queue | released queue_id=%s retries=%d", queue_id, retry_count)
        return True
    except Exception as exc:
        logger.error("queue | release_held_ticket failed queue_id=%s err=%s", queue_id, exc)
        return False


def rerun_queue_item(queue_id: str) -> bool:
    """
    Reset a queue item and re-enqueue it from the start of the pipeline.
    This is an operator-driven full rerun, not a single-stage rerun.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, retry_count
                    FROM pipeline_queue
                    WHERE id = %s::uuid
                    FOR UPDATE
                    """,
                    (queue_id,),
                )
                row = cur.fetchone()
                if not row:
                    return False

                status, retry_count = row
                if status == "completed":
                    return False
                if retry_count >= MAX_RETRIES:
                    return False

                # Fetch ticket_code and old execution_id so we can wipe stage history
                cur.execute(
                    "SELECT ticket_code, execution_id FROM pipeline_queue WHERE id = %s::uuid",
                    (queue_id,),
                )
                meta = cur.fetchone()
                ticket_code = meta[0] if meta else None
                old_exec_id = meta[1] if meta else None

                # Delete all stage events for this ticket's previous runs so the
                # detail page starts with a clean slate after rerun
                if ticket_code:
                    cur.execute(
                        "DELETE FROM pipeline_stage_events WHERE ticket_code = %s",
                        (ticket_code,),
                    )
                    logger.info(
                        "queue | cleared stage events for rerun ticket_code=%s old_exec=%s",
                        ticket_code, old_exec_id,
                    )

                new_pos = _next_queue_position(cur)
                cur.execute(
                    """
                    UPDATE pipeline_queue
                    SET status = 'queued',
                        queue_position = %s,
                        retry_count = retry_count + 1,
                        execution_id = NULL,
                        failed_stage = NULL,
                        failed_at_step = NULL,
                        failure_reason = NULL,
                        failure_category = NULL,
                        checkpoint_state = '{}',
                        operator_corrections = '{}',
                        started_at = NULL,
                        held_at = NULL,
                        completed_at = NULL,
                        released_at = now()
                    WHERE id = %s::uuid
                    """,
                    (new_pos, queue_id),
                )
        logger.info("queue | rerun queued queue_id=%s", queue_id)
        return True
    except Exception as exc:
        logger.error("queue | rerun_queue_item failed queue_id=%s err=%s", queue_id, exc)
        return False


# ---------------------------------------------------------------------------
# Worker: process one item
# ---------------------------------------------------------------------------

async def _process_queue_item(item: dict) -> None:
    """Process a single queue item end-to-end."""
    queue_id    = item["id"]
    ticket_id   = item["ticket_id"]
    ticket_code = item["ticket_code"]
    retry_count = item["retry_count"]
    ticket_input = item["ticket_input"]
    checkpoint_state = item["checkpoint_state"]
    operator_corrections = item["operator_corrections"]
    failed_stage = item.get("failed_stage")
    failed_at_step = item.get("failed_at_step")
    failure_category = item.get("failure_category")

    execution_id = str(uuid.uuid4())
    _db_set_processing(queue_id, execution_id)

    logger.info(
        "queue_worker | start queue_id=%s ticket=%s retry=%d exec=%s",
        queue_id, ticket_code or ticket_id, retry_count, execution_id,
    )

    # Build initial state
    if checkpoint_state and failed_at_step is not None and (
        operator_corrections or failure_category in {"manual_pause", "recovered_restart"}
    ):
        # Resuming after operator correction:
        # merge corrections into checkpoint (which is state BEFORE failed stage)
        # then skip to the stage AFTER the failed one
        state = {**checkpoint_state, **(operator_corrections or {})}
        if failure_category == "manual_pause" and checkpoint_state.get("_resume_from_step") is not None:
            start_step = max(1, int(checkpoint_state.get("_resume_from_step") or 1))
        else:
            start_step = max(1, failed_at_step + 1)
        logger.info(
            "queue_worker | resuming from step %d reason=%s stage=%s",
            start_step, failure_category or "operator_corrections", failed_stage,
        )
    else:
        # Fresh run from beginning
        state = _build_initial_state(ticket_id, ticket_code, ticket_input, execution_id)
        start_step = 1

    final_state, fail_stage, fail_step, fail_reason = await run_pipeline_from(
        state, start_step, queue_id, execution_id
    )

    if fail_stage == "__cancelled__":
        logger.info(
            "queue_worker | cancelled queue_id=%s ticket=%s exec=%s",
            queue_id, ticket_code or ticket_id, execution_id,
        )
        return

    if fail_stage:
        # Critical stage failed
        logger.warning(
            "queue_worker | critical failure stage=%s queue_id=%s retry=%d",
            fail_stage, queue_id, retry_count,
        )
        if retry_count >= MAX_RETRIES:
            _db_permanently_held(
                queue_id,
                f"Permanently held after {MAX_RETRIES} retries. Last failure: {fail_reason}",
            )
            _notify_operator(ticket_id, ticket_code, fail_stage, queue_id)
        else:
            # Save checkpoint (state as it was just entering the failed stage)
            # We re-build checkpoint from the state at the failure point minus mock outputs
            _db_set_held(
                queue_id,
                fail_stage,
                fail_step,
                fail_reason,
                # Store the state before the failed stage ran:
                # final_state contains the mock output, we want the INPUT to the failed stage.
                # We rebuild by running up to (but not including) the failed stage.
                # Simpler: store final_state minus the mock fields — the orchestrator
                # already saved the per-stage snapshots in pipeline_stage_events.
                # For resume we'll store the state as-of-failure (the mock is still
                # usable as a starting point; operator corrections overwrite it).
                _safe_json(final_state),
            )
            _notify_operator(ticket_id, ticket_code, fail_stage, queue_id)
    else:
        review_verdict = str(final_state.get("review_agent_verdict") or "").strip().lower()
        if review_verdict == "held_operator_review":
            review_reason = (
                str(final_state.get("review_agent_verdict_reason") or "").strip()
                or "Review Agent held the ticket for operator review."
            )
            _db_set_held(
                queue_id,
                "ReviewAgent",
                12,
                review_reason,
                _safe_json(final_state),
            )
            logger.info(
                "queue_worker | held_by_review queue_id=%s ticket=%s exec=%s",
                queue_id, ticket_code or ticket_id, execution_id,
            )
        else:
            _db_set_completed(queue_id)
            logger.info(
                "queue_worker | completed queue_id=%s ticket=%s exec=%s",
                queue_id, ticket_code or ticket_id, execution_id,
            )


# ---------------------------------------------------------------------------
# Public API: rerun failed stage
# ---------------------------------------------------------------------------

async def rerun_failed_stage(queue_id: str) -> dict:
    """
    Re-run only the failed stage through the AI (no operator corrections).
    - If it succeeds: store the real output in checkpoint_state and re-enqueue
      the ticket to resume from the next stage.
    - If it fails again: update failure history and keep the ticket held.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_id, ticket_code, failed_stage, failed_at_step,
                           checkpoint_state, retry_count
                    FROM pipeline_queue
                    WHERE id = %s::uuid AND status = 'held'
                    """,
                    (queue_id,),
                )
                row = cur.fetchone()
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    if not row:
        return {"ok": False, "error": "Queue item not found or not held"}

    ticket_id, ticket_code, failed_stage, failed_at_step, checkpoint_state, retry_count = row
    checkpoint_state = checkpoint_state or {}

    stage_entry = STAGE_BY_NAME.get(failed_stage)
    if not stage_entry:
        return {"ok": False, "error": f"Unknown stage: {failed_stage}"}

    fn, step_order, is_critical = stage_entry
    execution_id = str(uuid.uuid4())

    try:
        _db_set_processing(queue_id, execution_id)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

    # Run just this one stage
    result_state, critical_failed, reason = await _run_stage(
        failed_stage, fn, step_order, is_critical, checkpoint_state, execution_id
    )

    if not critical_failed:
        # Stage succeeded — merge output into checkpoint and re-enqueue
        merged = {**checkpoint_state, **result_state}
        try:
            with db_connect() as conn:
                with conn.cursor() as cur:
                    new_pos = _next_queue_position(cur)
                    cur.execute(
                        """
                        UPDATE pipeline_queue
                        SET status = 'queued',
                            queue_position = %s,
                            checkpoint_state = %s::jsonb,
                            operator_corrections = '{}',
                            retry_count = retry_count + 1,
                            failed_stage = NULL,
                            failed_at_step = NULL,
                            failure_reason = NULL,
                            failure_category = NULL,
                            released_at = now()
                        WHERE id = %s::uuid
                        """,
                        (new_pos, json.dumps(_safe_json(merged)), queue_id),
                    )
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        logger.info("queue | rerun_stage success stage=%s queue_id=%s", failed_stage, queue_id)
        return {"ok": True, "queue_id": queue_id, "stage": failed_stage, "succeeded": True}
    else:
        # Still failing — update failure history, keep held
        _db_set_held(queue_id, failed_stage, failed_at_step, reason, checkpoint_state)
        logger.warning("queue | rerun_stage still failing stage=%s queue_id=%s", failed_stage, queue_id)
        return {"ok": True, "queue_id": queue_id, "stage": failed_stage, "succeeded": False, "reason": reason}


# ---------------------------------------------------------------------------
# Background worker loop
# ---------------------------------------------------------------------------

async def queue_worker_loop() -> None:
    """
    Background asyncio task.
    Continuously polls the queue and processes one ticket at a time.
    Held tickets are skipped — they wait for operator action.
    """
    recovered = 0
    try:
        ensure_pipeline_control_table()
        recovered = _db_requeue_orphaned_processing_items()
    except Exception as exc:
        logger.error("queue_worker | failed startup recovery: %s", exc)
    logger.info("queue_worker | started recovered_processing=%d", recovered)
    while True:
        try:
            if is_pipeline_paused():
                await asyncio.sleep(2)
                continue
            item = _db_dequeue_next()
            if item:
                await _process_queue_item(item)
            else:
                await asyncio.sleep(2)
        except Exception as exc:
            logger.error("queue_worker | unhandled error: %s", exc)
            await asyncio.sleep(5)
