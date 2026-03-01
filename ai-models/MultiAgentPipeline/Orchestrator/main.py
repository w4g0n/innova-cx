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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pipeline import pipeline
from db import ensure_log_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Keep orchestrator step logs, hide noisy client/access logs.
for noisy_logger in ("httpx", "httpcore", "urllib3", "uvicorn.access"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

app = FastAPI(title="InnovaCX Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BACKEND_URL = "http://backend:8000"


# ---------------------------------------------------------------------------
# Startup — ensure logging tables exist
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup():
    ensure_log_tables()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}


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
    ticket_type: str | None = Form(default=None),
    asset_type: str | None = Form(default=None),
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
    selected_asset = asset_type.strip() if asset_type else None

    initial_payload = {
        "transcript": text.strip(),
        "ticket_id": ticket_id.strip() if ticket_id else None,
        "label": selected_type if selected_type in {"complaint", "inquiry"} else "complaint",
        "asset_type": selected_asset or "General",
        "department": selected_asset or "general",
        "status": "Open",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{BACKEND_URL}/api/complaints", json=initial_payload)
            response.raise_for_status()
            open_ticket = response.json()
            ticket_id = open_ticket.get("ticket_id")
            logger.info(
                "ticket_status_update | ticket_id=%s status=%s asset_type=%s department=%s priority=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                ticket_id,
                open_ticket.get("status", "Open"),
                open_ticket.get("asset_type") or initial_payload["asset_type"],
                open_ticket.get("department") or initial_payload["department"],
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
        "ticket_type": selected_type,
        "asset_type": selected_asset,
        "has_audio": bool(has_audio),
        "audio_features": parsed_audio_features,
        "_execution_id": str(uuid.uuid4()),
    }

    execution_id = state["_execution_id"]
    result = await pipeline.ainvoke(state)
    if result.get("label") == "inquiry":
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f "
            "priority=%s/%s ticket_id=%s status=%s department=%s asset_type=%s "
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
            result.get("asset_type"),
            result.get("priority_assigned_at"),
            result.get("respond_due_at"),
            result.get("resolve_due_at"),
        )
    else:
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f "
            "impact=%s safety=%s severity=%s urgency=%s priority=%s/%s ticket_id=%s "
            "status=%s department=%s asset_type=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
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
            result.get("asset_type"),
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
