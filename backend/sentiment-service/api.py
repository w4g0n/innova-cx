from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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

USE_MOCK = os.environ.get("USE_MOCK_MODEL", "true").lower() == "true"
MODEL_PATH = os.environ.get("MODEL_PATH", "/app/models")

predictor = None


class TextInput(BaseModel):
    text: str


class SentimentResponse(BaseModel):
    text_sentiment: float
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
                def __init__(self, model):
                    se