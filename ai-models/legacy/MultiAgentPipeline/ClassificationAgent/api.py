"""
Classification Agent API
========================
FastAPI wrapper around ClassificationAgent/src/inference.py.

Endpoints:
    POST /classify  → {label: "complaint"|"inquiry", confidence: float}
    GET  /health

Supports mock mode (USE_MOCK_CLASSIFIER=true, default) for development
when model.pt has not been trained yet.
"""

import os
import re
import sys
import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="InnovaCX Classifier", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

USE_MOCK = os.environ.get("USE_MOCK_CLASSIFIER", "true").lower() == "true"
MODEL_DIR = os.environ.get("MODEL_DIR", "/app/src/models/classifier-v1")

predictor = None


# ---------------------------------------------------------------------------
# Mock classifier — deterministic keyword-based routing for dev/test
# ---------------------------------------------------------------------------

_COMPLAINT_KEYWORDS = re.compile(
    r"\b("
    r"broken|not working|broken down|out of order|failed|failure|"
    r"issue|problem|leaking|leak|crack|cracks|"
    r"damaged|damage|malfunction|stopped working|"
    r"flickering|no power|no electricity|no water|no heat|no ac|no air|"
    r"dirty|smell|smells|pest|rats|roaches|"
    r"unsafe|emergency|danger|urgent|immediately|"
    r"complaint|complain|report|reporting"
    r")\b",
    re.IGNORECASE,
)


class MockClassifier:
    """Deterministic keyword-based classifier for use when model.pt is absent."""

    def classify(self, text: str) -> dict:
        t0 = time.time()
        text_lower = text.lower()

        # Check for strong complaint signals
        has_complaint = bool(_COMPLAINT_KEYWORDS.search(text_lower))

        # Check for inquiry signals (questions, requests for info)
        inquiry_patterns = [
            r"\?",                          # question mark
            r"\b(how|what|when|where|who|can i|do you|is there|are there)\b",
            r"\b(hours|schedule|availability|price|cost|inquiry|inquire|lease|leasing|rent)\b",
        ]
        has_inquiry = any(re.search(p, text_lower) for p in inquiry_patterns)

        if has_complaint and not has_inquiry:
            label, confidence = "complaint", 0.92
        elif has_inquiry and not has_complaint:
            label, confidence = "inquiry", 0.89
        elif has_complaint and has_inquiry:
            # Complaint takes precedence (safer default)
            label, confidence = "complaint", 0.76
        else:
            # Ambiguous — treat as complaint (safer default, below threshold)
            label, confidence = "complaint", 0.60

        return {
            "label": label,
            "confidence": round(confidence, 4),
            "processing_time_ms": round((time.time() - t0) * 1000, 2),
            "mock_mode": True,
        }


# ---------------------------------------------------------------------------
# Real classifier — loads trained DistilRoBERTa model
# ---------------------------------------------------------------------------

class RealClassifier:
    """Wraps CallClassificationPredictor for the API."""

    def __init__(self, model_dir: str):
        sys.path.insert(0, "/app/src")
        from inference import CallClassificationPredictor  # noqa: PLC0415
        self._predictor = CallClassificationPredictor(model_dir=model_dir, device="cpu")
        logger.info("Real classifier model loaded from %s", model_dir)

    def classify(self, text: str) -> dict:
        result = self._predictor.classify(text)
        return {
            "label": result.classification,
            "confidence": round(result.confidence, 4),
            "processing_time_ms": round(result.processing_time_ms, 2),
            "mock_mode": False,
        }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    global predictor
    if USE_MOCK:
        logger.info("Classifier starting in MOCK MODE — no model loaded")
        predictor = MockClassifier()
    else:
        model_pt = os.path.join(MODEL_DIR, "model.pt")
        if not os.path.exists(model_pt):
            logger.warning(
                "model.pt not found at %s — falling back to MOCK MODE", MODEL_DIR
            )
            predictor = MockClassifier()
        else:
            try:
                predictor = RealClassifier(model_dir=MODEL_DIR)
            except Exception as exc:
                logger.error("Failed to load real model: %s — falling back to MOCK MODE", exc)
                predictor = MockClassifier()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    label: str          # "complaint" or "inquiry"
    confidence: float   # 0.0 – 1.0
    processing_time_ms: float
    mock_mode: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "healthy" if predictor else "unhealthy",
        "service": "classifier",
        "mock_mode": isinstance(predictor, MockClassifier) if predictor else None,
    }


@app.post("/classify", response_model=ClassifyResponse)
async def classify(req: ClassifyRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = predictor.classify(req.text)

    logger.info(
        "Classified | label=%s confidence=%.4f mock=%s",
        result["label"],
        result["confidence"],
        result["mock_mode"],
    )
    return ClassifyResponse(**result)
