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
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pipeline import pipeline

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
    ticket_type: str | None = Form(default=None),
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

    state = {
        "text": text.strip(),
        "ticket_type": ticket_type.lower().strip() if ticket_type else None,
        "has_audio": bool(has_audio),
        "audio_features": parsed_audio_features,
    }

    result = await pipeline.ainvoke(state)
    if result.get("label") == "inquiry":
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f priority=%s/%s ticket_id=%s",
            result.get("label"),
            float(result.get("class_confidence", 0.0) or 0.0),
            float(result.get("text_sentiment", 0.0) or 0.0),
            float(result.get("audio_sentiment", 0.0) or 0.0),
            float(result.get("sentiment_score_numeric", 0.0) or 0.0),
            result.get("priority_label"),
            result.get("priority_score"),
            result.get("ticket_id"),
        )
    else:
        logger.info(
            "pipeline_done | type=%s class_conf=%.3f text_sent=%.3f audio_sent=%.3f combined_sent=%.3f impact=%s safety=%s severity=%s urgency=%s priority=%s/%s ticket_id=%s",
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
        )
    return _build_response(result)


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _build_response(result: dict) -> dict:
    if result.get("label") == "inquiry":
        return {
            "type": "inquiry",
            "ticket_id": result.get("ticket_id"),
            "priority": result.get("priority_score"),
            "priority_label": result.get("priority_label"),
        }
    return {
        "type": "complaint",
        "ticket_id": result.get("ticket_id"),
        "priority": result.get("priority_score"),
        "priority_label": result.get("priority_label"),
        "department": result.get("department"),
        "sentiment": result.get("text_sentiment"),
        "classification_confidence": result.get("class_confidence"),
    }
