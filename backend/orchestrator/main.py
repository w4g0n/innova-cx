"""
InnovaCX Orchestrator — FastAPI Entry Point
==========================================
Port 8004

Endpoints:
    POST /process/audio  — multipart audio upload, runs full pipeline
    POST /process/text   — form-encoded text, runs pipeline from classifier
    GET  /health         — liveness probe
"""

import logging
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pipeline import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

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
async def process_audio(audio: UploadFile = File(...)):
    """
    Accepts a WebM/MP4/WAV audio file, transcribes it via Whisper,
    then runs the full classification → sentiment → priority → routing pipeline.
    """
    logger.info("Processing audio input: %s", audio.filename)
    audio_bytes = await audio.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

    state = {
        "audio_bytes": audio_bytes,
        "text": None,
        "audio_features": {},
    }

    result = await pipeline.ainvoke(state)
    return _build_response(result)


# ---------------------------------------------------------------------------
# Text entry point
# ---------------------------------------------------------------------------

@app.post("/process/text")
async def process_text(text: str = Form(...)):
    """
    Accepts raw text (complaint or inquiry) and runs the pipeline
    starting from the classifier (skips Whisper).
    """
    if not text or not text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty")

    logger.info("Processing text input: %s...", text[:80])

    state = {
        "text": text.strip(),
        "audio_bytes": None,
        "audio_features": {},
    }

    result = await pipeline.ainvoke(state)
    return _build_response(result)


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------

def _build_response(result: dict) -> dict:
    if result.get("label") == "inquiry":
        return {
            "type": "inquiry",
            "chatbot_response": result.get("chatbot_response"),
        }
    return {
        "type": "complaint",
        "ticket_id": result.get("ticket_id"),
        "priority": result.get("priority_score"),
        "department": result.get("department"),
        "sentiment": result.get("text_sentiment"),
        "classification_confidence": result.get("class_confidence"),
    }
