"""
InnovaCX Orchestrator — FastAPI Entry Point
==========================================
Port 8004

Endpoints:
    POST /process/audio  — disabled (transcriber is frontend/backend service)
    POST /process/text   — form-encoded ticket details, runs post-submit pipeline
    GET  /health         — liveness probe
"""

import asyncio
import logging
import json
import uuid
import httpx
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import pipeline
from queue_manager import enqueue_ticket, queue_worker_loop, release_held_ticket, rerun_failed_stage
from agents.step04_sentimentanalysis.step import get_sentiment_diagnostics
from agents.step03_classifier.step import get_classifier_diagnostics
from agents.step08_featureengineering.step import get_feature_engineering_diagnostics
from agents.step01_subjectgeneration.step import get_subject_generation_diagnostics
from agents.step02_suggestedresolution.step import (
    get_suggested_resolution_diagnostics,
    retrain_resolution_examples_from_db,
)
from agents.step10_router.step import get_router_diagnostics
from agents.step05_audioanalysis.step import get_audio_analysis_diagnostics
from agents.step09_priority.step import record_manager_feedback_from_state, get_priority_diagnostics

try:
    from db import ensure_log_tables, db_connect
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    ensure_log_tables = None
    db_connect = None

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "WARNING").upper(), logging.WARNING),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Keep orchestrator step logs, hide noisy client/access logs.
for noisy_logger in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

app = FastAPI(title="InnovaCX Orchestrator", version="1.0.0")

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
CHATBOT_URL = os.getenv("CHATBOT_URL", "http://chatbot:8000").rstrip("/")
CHATBOT_URL_LOCAL = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001").rstrip("/")
CHATBOT_STARTUP_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_STARTUP_TIMEOUT_SECONDS", "240"))
CHATBOT_STARTUP_POLL_INTERVAL_SECONDS = float(os.getenv("CHATBOT_STARTUP_POLL_INTERVAL_SECONDS", "5"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PriorityRelearnRequest(BaseModel):
    ticket_id: str
    approved_priority: str
    retrain_now: bool = False


class SuggestedResolutionRelearnRequest(BaseModel):
    max_examples: int = 12


# ---------------------------------------------------------------------------
# Startup — ensure logging tables exist (if db module is available)
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup():
    await _wait_for_chatbot_health()
    if ensure_log_tables:
        ensure_log_tables()
    _log_model_mode_summary()
    # Start the persistent queue background worker
    asyncio.create_task(queue_worker_loop())


async def _wait_for_chatbot_health() -> None:
    import time

    if CHATBOT_STARTUP_TIMEOUT_SECONDS <= 0:
        logger.info("startup | chatbot health gate disabled")
        return

    timeout = httpx.Timeout(10.0)
    last_error = None
    started_at = time.monotonic()
    health_urls = [f"{CHATBOT_URL}/health"]
    if CHATBOT_URL_LOCAL and CHATBOT_URL_LOCAL != CHATBOT_URL:
        health_urls.append(f"{CHATBOT_URL_LOCAL}/health")

    async with httpx.AsyncClient(timeout=timeout) as client:
        while True:
            for health_url in health_urls:
                try:
                    response = await client.get(health_url)
                    response.raise_for_status()
                    payload = response.json() or {}
                    if str(payload.get("status") or "").lower() == "healthy":
                        logger.info("startup | chatbot dependency ready url=%s", health_url)
                        return
                    last_error = RuntimeError(f"unhealthy response from {health_url}: {payload}")
                except Exception as exc:
                    last_error = exc

            if (time.monotonic() - started_at) >= CHATBOT_STARTUP_TIMEOUT_SECONDS:
                break

            logger.info(
                "startup | waiting for chatbot dependency timeout=%ss poll=%ss err=%s",
                CHATBOT_STARTUP_TIMEOUT_SECONDS,
                CHATBOT_STARTUP_POLL_INTERVAL_SECONDS,
                last_error,
            )
            await _sleep_for_chatbot_poll()

    raise RuntimeError(f"chatbot dependency did not become healthy before startup deadline: {last_error}")


async def _sleep_for_chatbot_poll() -> None:
    import asyncio

    await asyncio.sleep(max(1.0, CHATBOT_STARTUP_POLL_INTERVAL_SECONDS))


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator",
        **get_subject_generation_diagnostics(),
        **get_suggested_resolution_diagnostics(),
        **get_sentiment_diagnostics(),
        **get_classifier_diagnostics(),
        **get_audio_analysis_diagnostics(),
        **get_feature_engineering_diagnostics(),
        **get_router_diagnostics(),
        **get_priority_diagnostics(),
    }


def _log_model_mode_summary() -> None:
    subject_diag = get_subject_generation_diagnostics()
    suggested_resolution_diag = get_suggested_resolution_diagnostics()
    sentiment_diag = get_sentiment_diagnostics()
    classifier_diag = get_classifier_diagnostics()
    audio_diag = get_audio_analysis_diagnostics()
    feature_diag = get_feature_engineering_diagnostics()
    router_diag = get_router_diagnostics()
    priority_diag = get_priority_diagnostics()

    rows = [
        (
            "SubjectGeneration",
            subject_diag.get("subject_generator_mode", "heuristic"),
            subject_diag.get(
                "subject_generator_mode_reason",
                "built-in heuristic subject generation is active",
            ),
        ),
        (
            "SuggestedResolution",
            suggested_resolution_diag.get("suggested_resolution_mode", "template"),
            (
                "local suggested resolution model artifact present"
                if suggested_resolution_diag.get("suggested_resolution_model_exists")
                else f"local suggested resolution model artifact missing at {suggested_resolution_diag.get('suggested_resolution_model_path') or '(not configured)'}"
            ),
        ),
        (
            "Classification",
            classifier_diag.get("classifier_mode", "mock"),
            (
                "classifier model artifact present"
                if classifier_diag.get("classifier_model_exists")
                else f"model artifact missing at {classifier_diag.get('classifier_model_path') or '(default path)'}"
            ),
        ),
        (
            "SentimentAnalysis",
            sentiment_diag.get("sentiment_mode", "mock"),
            (
                "sentiment model artifact present"
                if sentiment_diag.get("sentiment_model_file_exists")
                else f"model artifact missing at {sentiment_diag.get('sentiment_model_dir') or '(not configured)'}"
            ),
        ),
        (
            "AudioAnalysis",
            audio_diag.get("audio_analysis_mode", "fallback"),
            audio_diag.get("audio_analysis_mode_reason", "audio analyzer unavailable; using fallback"),
        ),
        (
            "SentimentCombiner",
            "deterministic",
            "deterministic built-in combiner logic is active",
        ),
        (
            "Recurrence",
            "heuristic",
            "heuristic recurrence logic is active; no per-agent model artifact is loaded in orchestrator",
        ),
        (
            "FeatureEngineering",
            feature_diag.get("feature_labeler_mode", "mock"),
            (
                "feature labeler artifact present"
                if feature_diag.get("feature_labeler_model_exists")
                else f"model artifact missing at {feature_diag.get('feature_labeler_model') or '(not configured)'}"
            ),
        ),
        (
            "Prioritization",
            priority_diag.get("priority_mode", "mock"),
            priority_diag.get("priority_mode_reason", "prioritization runtime unavailable; using mock fallback"),
        ),
        (
            "DepartmentRouting",
            router_diag.get("department_router_mode", "mock"),
            (
                "router model artifact present"
                if router_diag.get("department_router_local_model_exists")
                else f"model artifact missing at {router_diag.get('department_router_model_path') or '(not configured)'}"
            ),
        ),
    ]

    logger.info("MODEL_MODE_SUMMARY | startup model resolution")
    for stage, mode, reason in rows:
        logger.info("MODEL_MODE | stage=%s mode=%s reason=%s", stage, mode, reason)


def _coerce_uuid_or_none(value):
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _log_application_event(
    *,
    event_key: str,
    level: str = "INFO",
    ticket_id=None,
    ticket_code=None,
    execution_id=None,
    payload: dict | None = None,
) -> None:
    if not db_connect:
        return
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO application_event_log
                        (service, event_key, ticket_id, ticket_code, execution_id, level, payload)
                    VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        "orchestrator",
                        event_key,
                        _coerce_uuid_or_none(ticket_id),
                        ticket_code,
                        _coerce_uuid_or_none(execution_id),
                        level,
                        json.dumps(payload or {}, default=str),
                    ),
                )
    except Exception:
        return


def _json_to_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _fetch_latest_priority_state(ticket_id: str) -> dict | None:
    if not db_connect:
        return None
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT input_state, output_state
                    FROM agent_output_log
                    WHERE ticket_id::text = %s
                      AND agent_name = 'PrioritizationAgent'
                      AND error_flag = FALSE
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                input_state = _json_to_dict(row[0])
                output_state = _json_to_dict(row[1])
                merged = dict(input_state)
                merged.update(output_state)
                return merged
    except Exception as exc:
        logger.warning("priority_relearn | failed fetching state for ticket=%s err=%s", ticket_id, exc)
        return None


@app.post("/priority/relearn/manager-approval")
async def priority_relearn_from_manager_approval(body: PriorityRelearnRequest):
    allowed = {"low", "medium", "high", "critical"}
    approved_priority = str(body.approved_priority or "").strip().lower()
    if approved_priority not in allowed:
        raise HTTPException(status_code=422, detail=f"approved_priority must be one of {sorted(allowed)}")

    ticket_id = str(body.ticket_id or "").strip()
    if not ticket_id:
        raise HTTPException(status_code=422, detail="ticket_id is required")

    state = _fetch_latest_priority_state(ticket_id)
    if not state:
        raise HTTPException(status_code=404, detail="No prioritization state found for ticket_id")

    try:
        feedback = record_manager_feedback_from_state(
            state=state,
            approved_priority=approved_priority,
            ticket_id=ticket_id,
            retrain_now=bool(body.retrain_now),
        )
    except Exception as exc:
        logger.error("priority_relearn | failed for ticket=%s err=%s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"Failed to apply relearning feedback: {exc}")

    return {
        "ok": True,
        "ticket_id": ticket_id,
        "approved_priority": approved_priority,
        **feedback,
    }


class QueueReleaseRequest(BaseModel):
    queue_id: str
    corrections: dict = {}


class QueueRerunStageRequest(BaseModel):
    queue_id: str


@app.post("/queue/release")
async def queue_release(body: QueueReleaseRequest):
    """
    Called by the backend operator API when the operator releases a held ticket.
    Applies corrections and re-enqueues the ticket at the bottom of the queue.
    """
    ok = release_held_ticket(body.queue_id, body.corrections)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Release failed — ticket may not be held or max retries exceeded",
        )
    return {"ok": True, "queue_id": body.queue_id}


@app.post("/queue/rerun-stage")
async def queue_rerun_stage(body: QueueRerunStageRequest):
    """
    Re-run only the failed stage through the AI model without operator corrections.
    If it succeeds, the stage output is stored and the pipeline resumes from the next stage.
    If it fails again, the ticket remains held with an updated failure record.
    """
    result = await rerun_failed_stage(body.queue_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Rerun failed"))
    return result


@app.post("/suggested-resolution/relearn")
async def suggested_resolution_relearn(body: SuggestedResolutionRelearnRequest):
    try:
        result = retrain_resolution_examples_from_db(max_examples=body.max_examples)
    except Exception as exc:
        logger.error("suggested_resolution_relearn | failed err=%s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to rebuild suggested resolution examples: {exc}")
    return result


# ---------------------------------------------------------------------------
# Audio entry point
# ---------------------------------------------------------------------------

@app.post("/process/audio")
async def process_audio(
    audio: UploadFile = File(...),
):
    """
    Transcriber is not part of orchestrator.
    Frontend/backend transcriber service should produce transcript first.
    """
    _ = audio
    raise HTTPException(
        status_code=400,
        detail="Audio endpoint is disabled. Submit transcript/details to /process/text with optional audio_features.",
    )


# ---------------------------------------------------------------------------
# Text entry point
# ---------------------------------------------------------------------------

@app.post("/process/text")
async def process_text(
    text: str = Form(...),
    ticket_id: str | None = Form(default=None),
    execution_id: str | None = Form(default=None),
    subject: str | None = Form(default=None),
    created_by_user_id: str | None = Form(default=None),
    ticket_source: str | None = Form(default=None),
    has_audio: bool | None = Form(default=None),
    audio_features: str | None = Form(default=None),
):
    """
    Accepts submitted ticket details and enqueues them for processing.
    The pipeline_queue worker picks the ticket up and runs it stage by stage.
    Returns immediately with queue_id and ticket_id.
    """
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    parsed_audio_features = {}
    if audio_features:
        try:
            payload = json.loads(audio_features)
            if isinstance(payload, dict):
                parsed_audio_features = payload
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="audio_features must be valid JSON object")

    # Create the initial open ticket in the backend first
    initial_payload = {
        "transcript": text.strip(),
        "ticket_id": ticket_id.strip() if ticket_id else None,
        "subject": subject.strip() if subject else None,
        "label": "complaint",
        "status": "Open",
        "created_by_user_id": created_by_user_id.strip() if created_by_user_id else None,
        "ticket_source": ticket_source.strip() if ticket_source else None,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{BACKEND_URL}/api/complaints", json=initial_payload)
            response.raise_for_status()
            open_ticket = response.json()
            ticket_id = open_ticket.get("ticket_id")
            ticket_code = open_ticket.get("ticket_code") or ticket_id
    except Exception as exc:
        logger.error("failed to create initial open ticket: %s", exc)
        raise HTTPException(status_code=503, detail=f"Failed to create initial ticket: {exc}")

    if not ticket_id:
        raise HTTPException(status_code=503, detail="Failed to create initial ticket: missing ticket_id")

    # Enqueue for background processing
    try:
        queue_id = enqueue_ticket(
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            text=text.strip(),
            subject=subject.strip() if subject else None,
            has_audio=bool(has_audio),
            audio_features=parsed_audio_features,
            created_by_user_id=created_by_user_id.strip() if created_by_user_id else None,
            ticket_source=ticket_source.strip() if ticket_source else None,
        )
    except Exception as exc:
        logger.error("failed to enqueue ticket_id=%s err=%s", ticket_id, exc)
        raise HTTPException(status_code=503, detail=f"Failed to enqueue ticket: {exc}")

    _log_application_event(
        event_key="pipeline_queued",
        ticket_id=ticket_id,
        ticket_code=ticket_code if _coerce_uuid_or_none(ticket_code) is None else None,
        payload={"queue_id": queue_id, "has_audio": bool(has_audio)},
    )
    logger.info("process_text | enqueued ticket_id=%s queue_id=%s", ticket_id, queue_id)

    return {
        "queued": True,
        "ticket_id": ticket_id,
        "ticket_code": ticket_code,
        "queue_id": queue_id,
    }


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _build_response(result: dict, execution_id: str = "") -> dict:
    if result.get("label") == "inquiry":
        return {
            "type": "inquiry",
            "ticket_id": result.get("ticket_id"),
            "execution_id": execution_id,
            "priority": result.get("priority_score"),
            "priority_label": result.get("priority_label"),
        }
    return {
        "type": "complaint",
        "ticket_id": result.get("ticket_id"),
        "execution_id": execution_id,
        "priority": result.get("priority_score"),
        "priority_label": result.get("priority_label"),
        "department": result.get("department"),
        "sentiment": result.get("text_sentiment"),
        "classification_confidence": result.get("class_confidence"),
    }
