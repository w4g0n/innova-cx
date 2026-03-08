"""
InnovaCX Orchestrator — FastAPI Entry Point
==========================================
Port 8004

Endpoints:
    POST /process/audio  — disabled (transcriber is frontend/backend service)
    POST /process/text   — form-encoded ticket details, runs post-submit pipeline
    GET  /health         — liveness probe
"""

import logging
import json
import uuid
import httpx
import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline import pipeline
from agents.sentimentanalysis.step import get_sentiment_diagnostics
from agents.classifier.step import get_classifier_diagnostics
from agents.featureengineering.step import get_feature_engineering_diagnostics
from agents.subjectgeneration.step import get_subject_generation_diagnostics
from agents.router.step import get_router_diagnostics
from agents.audioanalysis.step import get_audio_analysis_diagnostics
from agents.priority.step import record_manager_feedback_from_state, get_priority_diagnostics

try:
    from db import ensure_log_tables, db_connect
except Exception:  # pragma: no cover - optional dependency for backward compatibility
    ensure_log_tables = None
    db_connect = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Keep orchestrator step logs, hide noisy client/access logs.
for noisy_logger in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

app = FastAPI(title="InnovaCX Orchestrator", version="1.0.0")

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")

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


# ---------------------------------------------------------------------------
# Startup — ensure logging tables exist (if db module is available)
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup():
    if ensure_log_tables:
        ensure_log_tables()
    _log_model_mode_summary()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "orchestrator",
        **get_subject_generation_diagnostics(),
        **get_sentiment_diagnostics(),
        **get_classifier_diagnostics(),
        **get_audio_analysis_diagnostics(),
        **get_feature_engineering_diagnostics(),
        **get_router_diagnostics(),
        **get_priority_diagnostics(),
    }


def _log_model_mode_summary() -> None:
    subject_diag = get_subject_generation_diagnostics()
    sentiment_diag = get_sentiment_diagnostics()
    classifier_diag = get_classifier_diagnostics()
    audio_diag = get_audio_analysis_diagnostics()
    feature_diag = get_feature_engineering_diagnostics()
    router_diag = get_router_diagnostics()
    priority_diag = get_priority_diagnostics()

    rows = [
        (
            "SubjectGeneration",
            subject_diag.get("subject_generator_mode", "mock"),
            (
                "subject generation model artifact present"
                if subject_diag.get("subject_generator_model_exists")
                else f"model artifact missing at {subject_diag.get('subject_generator_model_path') or '(not configured)'}"
            ),
        ),
        (
            "SuggestedResolution",
            "model_or_mock",
            "delegated to backend suggested-resolution service (it applies model/mock fallback there)",
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
            audio_diag.get("audio_analysis_mode", "mock"),
            audio_diag.get("audio_analysis_mode_reason", "audio analyzer unavailable; using mock fallback"),
        ),
        (
            "SentimentCombiner",
            "model",
            "deterministic built-in combiner logic is active",
        ),
        (
            "Recurrence",
            "mock",
            "heuristic recurrence logic active (no external KNN model artifact loaded in orchestrator)",
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


# ---------------------------------------------------------------------------
# Audio entry point
# ---------------------------------------------------------------------------

@app.post("/process/audio")
async def process_audio(
    audio: UploadFile = File(...),
    ticket_type: str | None = Form(default=None),
):
    """
    Transcriber is not part of orchestrator.
    Frontend/backend transcriber service should produce transcript first.
    """
    _ = audio
    _ = ticket_type
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
    subject: str | None = Form(default=None),
    ticket_type: str | None = Form(default=None),
    created_by_user_id: str | None = Form(default=None),
    ticket_source: str | None = Form(default=None),
    has_audio: bool | None = Form(default=None),
    audio_features: str | None = Form(default=None),
):
    """
    Accepts submitted ticket details text and runs full pipeline.
    If this ticket came from audio flow, pass has_audio=true and optional
    audio_features JSON string from transcriber service.
    """
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    logger.info("Processing text input: %s...", text[:80])

    parsed_audio_features = {}
    if audio_features:
        try:
            payload = json.loads(audio_features)
            if isinstance(payload, dict):
                parsed_audio_features = payload
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="audio_features must be valid JSON object")

    selected_type = ticket_type.lower().strip() if ticket_type else None

    initial_payload = {
        "transcript": text.strip(),
        "ticket_id": ticket_id.strip() if ticket_id else None,
        "subject": subject.strip() if subject else None,
        "label": selected_type if selected_type in {"complaint", "inquiry"} else "complaint",
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
            logger.info(
                "ticket_status_update | ticket_id=%s status=%s department=%s priority=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                ticket_id,
                open_ticket.get("status", "Open"),
                open_ticket.get("department"),
                open_ticket.get("priority"),
                open_ticket.get("priority_assigned_at"),
                open_ticket.get("respond_due_at"),
                open_ticket.get("resolve_due_at"),
            )
    except Exception as exc:
        logger.error("failed to create initial open ticket: %s", exc)
        raise HTTPException(status_code=503, detail=f"Failed to create initial ticket: {exc}")

    if not ticket_id:
        raise HTTPException(status_code=503, detail="Failed to create initial ticket: missing ticket_id")

    state = {
        "text": text.strip(),
        "ticket_id": ticket_id,
        "subject": subject.strip() if subject else None,
        "ticket_type": selected_type,
        "has_audio": bool(has_audio),
        "audio_features": parsed_audio_features,
        "_execution_id": str(uuid.uuid4()),
    }

    execution_id = state["_execution_id"]
    try:
        result = await pipeline.ainvoke(state)
    except Exception as exc:
        logger.exception("pipeline_failed | ticket_id=%s err=%s", ticket_id, exc)
        raise HTTPException(status_code=503, detail=f"Pipeline failed for ticket {ticket_id}: {exc}")
    if result.get("label") == "inquiry":
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f "
            "priority=%s/%s ticket_id=%s status=%s department=%s "
            "priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
            result.get("label"),
            float(result.get("class_confidence", 0.0) or 0.0),
            float(result.get("text_sentiment", 0.0) or 0.0),
            float(result.get("audio_sentiment", 0.0) or 0.0),
            float(result.get("sentiment_score_numeric", 0.0) or 0.0),
            result.get("priority_label"),
            result.get("priority_score"),
            result.get("ticket_id"),
            result.get("status"),
            result.get("department"),
            result.get("priority_assigned_at"),
            result.get("respond_due_at"),
            result.get("resolve_due_at"),
        )
    else:
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f "
            "impact=%s safety=%s severity=%s urgency=%s priority=%s/%s ticket_id=%s "
            "status=%s department=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
            result.get("label"),
            float(result.get("class_confidence", 0.0) or 0.0),
            float(result.get("text_sentiment", 0.0) or 0.0),
            float(result.get("audio_sentiment", 0.0) or 0.0),
            float(result.get("sentiment_score_numeric", 0.0) or 0.0),
            result.get("business_impact"),
            result.get("safety_concern"),
            result.get("issue_severity"),
            result.get("issue_urgency"),
            result.get("priority_label"),
            result.get("priority_score"),
            result.get("ticket_id"),
            result.get("status"),
            result.get("department"),
            result.get("priority_assigned_at"),
            result.get("respond_due_at"),
            result.get("resolve_due_at"),
        )
    return _build_response(result, execution_id)


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
