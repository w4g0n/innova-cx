"""
Step 3 — Sentiment Analysis
============================
Runs local sentiment inference in-process inside orchestrator.
Inquiries skip this step.
"""

import os
import re
import sys
import logging
import httpx
from pathlib import Path
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)
BACKEND_URL = "http://backend:8000"

# Local sentiment pipeline source copied into orchestrator image.
sys.path.insert(0, "/app/sentiment_pipeline")


def _categorize_sentiment(score: float) -> str:
    if score < -0.25:
        return "negative"
    if score <= 0.25:
        return "neutral"
    return "positive"


_KEYWORD_REGEX = re.compile(
    r"\b(ac|air conditioning|leak|flood|pipe|power|electricity|alarm|internet|wifi|network|urgent|emergency|broken|not working)\b",
    re.IGNORECASE,
)


class _FallbackPredictor:
    def predict(self, text: str) -> dict:
        t = text.lower()
        score = 0.0
        if any(k in t for k in ["urgent", "emergency", "unacceptable", "broken", "not working", "angry", "frustrated"]):
            score -= 0.6
        if any(k in t for k in ["thank you", "appreciate", "resolved", "great"]):
            score += 0.4
        return {"text_sentiment": max(-1.0, min(1.0, score))}


@lru_cache(maxsize=1)
def _load_predictor():
    model_dir = os.getenv("SENTIMENT_MODEL_DIR", "").strip()
    if not model_dir:
        logger.info("sentiment | SENTIMENT_MODEL_DIR not set, using fallback predictor")
        return _FallbackPredictor()
    model_pt = Path(model_dir) / "model.pt"
    if model_pt.exists():
        try:
            from inference import SentimentPredictor  # noqa: E402

            logger.info("sentiment | loading local model from %s", model_dir)
            return SentimentPredictor(model_dir=model_dir, device="cpu")
        except Exception as exc:
            logger.warning("sentiment | local model load failed (%s), using fallback", exc)
    else:
        logger.warning("sentiment | model.pt not found at %s, using fallback", model_dir)
    return _FallbackPredictor()


def get_sentiment_diagnostics() -> dict[str, Any]:
    model_dir = os.getenv("SENTIMENT_MODEL_DIR", "").strip()
    model_enabled = bool(model_dir)
    model_file_exists = bool(model_dir and (Path(model_dir) / "model.pt").exists())
    mode = "model" if model_file_exists else "mock"
    return {
        "sentiment_model_dir": model_dir or None,
        "sentiment_model_enabled": model_enabled,
        "sentiment_model_file_exists": model_file_exists,
        "sentiment_mode": mode,
    }


async def analyze_sentiment(state: dict) -> dict:
    ticket_id = state.get("ticket_id")
    if ticket_id and state.get("label") == "complaint":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{BACKEND_URL}/api/complaints",
                    json={"ticket_id": ticket_id, "status": "In Progress"},
                )
                resp.raise_for_status()
                update_result = resp.json()
                logger.info(
                    "ticket_status_update | ticket_id=%s status=%s priority=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                    update_result.get("ticket_id", ticket_id),
                    update_result.get("status", "In Progress"),
                    update_result.get("priority"),
                    update_result.get("priority_assigned_at"),
                    update_result.get("respond_due_at"),
                    update_result.get("resolve_due_at"),
                )
        except Exception as exc:
            logger.warning("sentiment | failed to mark ticket In Progress ticket_id=%s err=%s", ticket_id, exc)

    predictor = _load_predictor()
    data = predictor.predict(state["text"])

    sentiment = float(data.get("text_sentiment", 0.0) or 0.0)
    state["text_sentiment"] = sentiment
    state["sentiment_category"] = _categorize_sentiment(sentiment)
    state["urgency"] = 0.5
    state["keywords"] = list({m.group(0).lower() for m in _KEYWORD_REGEX.finditer(state["text"])})
    logger.info(
        "sentiment | text_sentiment=%.3f category=%s keywords=%d",
        float(state.get("text_sentiment", 0.0) or 0.0),
        state.get("sentiment_category"),
        len(state.get("keywords", [])),
    )

    return state


sentiment_step = RunnableLambda(analyze_sentiment)
