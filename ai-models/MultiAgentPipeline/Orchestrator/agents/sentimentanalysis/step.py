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
from pathlib import Path
from functools import lru_cache

from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)

# Local sentiment pipeline source copied into orchestrator image.
sys.path.insert(0, "/app/sentiment_pipeline")


def _categorize_sentiment(score: float) -> str:
    if score < -0.6:
        return "very_negative"
    if score < -0.2:
        return "negative"
    if score < 0.2:
        return "neutral"
    if score < 0.6:
        return "positive"
    return "very_positive"


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
    model_dir = os.getenv("SENTIMENT_MODEL_DIR", "/app/sentiment_models/sentiment-v7")
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


async def analyze_sentiment(state: dict) -> dict:
    if state["label"] != "complaint":
        logger.info("sentiment | skipped (label=%s)", state.get("label"))
        return state

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
