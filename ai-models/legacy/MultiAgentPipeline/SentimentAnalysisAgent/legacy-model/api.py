"""
Sentiment Analysis API Service

Provides text sentiment analysis using RoBERTa model or mock mode.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="InnovaCX Sentiment Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
USE_MOCK = os.environ.get("USE_MOCK_MODEL", "true").lower() == "true"
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models")

# Global predictor
predictor = None


class TextInput(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    text_sentiment: float
    text_urgency: float
    keywords: List[str]
    category: str
    processing_time_ms: float
    mock_mode: bool


class CombinedInput(BaseModel):
    text: str
    audio_features: Optional[dict] = None


class CombinedResponse(BaseModel):
    text_sentiment: float
    audio_sentiment: Optional[float]
    combined_sentiment: float
    urgency: float
    keywords: List[str]
    confidence: float
    mock_mode: bool


def categorize_sentiment(score: float) -> str:
    if score < -0.6:
        return "very_negative"
    elif score < -0.2:
        return "negative"
    elif score < 0.2:
        return "neutral"
    elif score < 0.6:
        return "positive"
    return "very_positive"


@app.on_event("startup")
async def startup():
    global predictor
    if USE_MOCK:
        logger.info("Starting in MOCK MODE - no model loaded")
        from mock_predictor import MockPredictor
        predictor = MockPredictor()
    else:
        logger.info(f"Loading real model from {MODEL_PATH}")
        try:
            from inference import MultiTaskPredictor
            real_model = MultiTaskPredictor(MODEL_PATH, device="cpu")

            class RealPredictor:
                """Adapter around MultiTaskPredictor to match api.py interface."""
                def __init__(self, model):
                    self._model = model

                def predict(self, text):
                    return self._model.predict(text)

                def predict_combined(self, text, audio_features=None):
                    result = self._model.predict(text)
                    audio_sentiment = None
                    if audio_features:
                        energy = audio_features.get("mean_energy", 0.05)
                        audio_sentiment = -0.3 if energy > 0.1 else 0.0
                    if audio_sentiment is not None:
                        combined = result["text_sentiment"] * 0.7 + audio_sentiment * 0.3
                    else:
                        combined = result["text_sentiment"]
                    return {
                        "text_sentiment": result["text_sentiment"],
                        "audio_sentiment": audio_sentiment,
                        "combined_sentiment": round(combined, 3),
                        "urgency": result["text_urgency"],
                        "keywords": result["keywords"],
                        "confidence": 0.95,
                    }

            predictor = RealPredictor(real_model)
            logger.info("Real model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load real model: {e}")
            logger.warning("Falling back to mock mode")
            from mock_predictor import MockPredictor
            predictor = MockPredictor()


@app.get("/")
async def root():
    return {
        "service": "InnovaCX Sentiment Analysis",
        "version": "1.0.0",
        "mock_mode": USE_MOCK
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy" if predictor else "unhealthy",
        "mock_mode": USE_MOCK
    }


@app.post("/analyze", response_model=SentimentResponse)
async def analyze_text(input: TextInput):
    """Analyze sentiment of text input."""
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = predictor.predict(input.text)

    logger.info(
        "Sentiment (text) score=%.3f urgency=%.3f category=%s mock=%s",
        result["text_sentiment"],
        result["text_urgency"],
        categorize_sentiment(result["text_sentiment"]),
        USE_MOCK,
    )
    print(
        "🧠 ### SENTIMENT (TEXT) ### score={:.3f} urgency={:.3f} category={} mock={}".format(
            result["text_sentiment"],
            result["text_urgency"],
            categorize_sentiment(result["text_sentiment"]),
            USE_MOCK,
        ),
        flush=True,
    )

    return SentimentResponse(
        text_sentiment=result["text_sentiment"],
        text_urgency=result["text_urgency"],
        keywords=result["keywords"],
        category=categorize_sentiment(result["text_sentiment"]),
        processing_time_ms=result["processing_time_ms"],
        mock_mode=USE_MOCK
    )


@app.post("/analyze-combined", response_model=CombinedResponse)
async def analyze_combined(input: CombinedInput):
    """Analyze sentiment combining text and audio features."""
    if not input.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    result = predictor.predict_combined(input.text, input.audio_features)

    logger.info(
        "Sentiment (combined) text=%.3f audio=%s combined=%.3f urgency=%.3f mock=%s",
        result["text_sentiment"],
        "none" if result.get("audio_sentiment") is None else f'{result["audio_sentiment"]:.3f}',
        result["combined_sentiment"],
        result["urgency"],
        USE_MOCK,
    )
    audio_sentiment_display = (
        "none"
        if result.get("audio_sentiment") is None
        else f'{result["audio_sentiment"]:.3f}'
    )
    print(
        "🔗 ### SENTIMENT (COMBINED) ### text={:.3f} audio={} combined={:.3f} urgency={:.3f} mock={}".format(
            result["text_sentiment"],
            audio_sentiment_display,
            result["combined_sentiment"],
            result["urgency"],
            USE_MOCK,
        ),
        flush=True,
    )

    return CombinedResponse(
        text_sentiment=result["text_sentiment"],
        audio_sentiment=result.get("audio_sentiment"),
        combined_sentiment=result["combined_sentiment"],
        urgency=result["urgency"],
        keywords=result["keywords"],
        confidence=result["confidence"],
        mock_mode=USE_MOCK
    )
