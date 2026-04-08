"""
Sentiment Combiner Agent
========================
Combines text/audio sentiment while preserving the native [-1, 1] polarity
range used by the sentiment agent.

Calibration knobs (env vars):
  SENTIMENT_BUCKET_NEG_THRESHOLD  default -0.15  (below → negative)
  SENTIMENT_BUCKET_POS_THRESHOLD  default  0.15  (above → positive)
  Tighter than the old ±0.25 to reduce false neutral classifications.

Audio blending:
  When audio_score (0–1 quality metric from transcriber) is present,
  audio weight scales up to 0.5 proportionally with quality.
  Without audio_score the blend defaults to 70/30 text-dominant.
"""

import logging
import os
from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)

_NEG_THRESHOLD = float(os.getenv("SENTIMENT_BUCKET_NEG_THRESHOLD", "-0.15"))
_POS_THRESHOLD = float(os.getenv("SENTIMENT_BUCKET_POS_THRESHOLD", "0.15"))


def _normalize_unit(value: float | None) -> float:
    v = float(value or 0.0)
    return max(-1.0, min(1.0, v))


def _bucket(score: float) -> str:
    if score < _NEG_THRESHOLD:
        return "negative"
    if score > _POS_THRESHOLD:
        return "positive"
    return "neutral"


def _to_display_score(score: float) -> float:
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


async def combine_sentiment(state: dict) -> dict:
    """
    Inputs:
      - state["text_sentiment"]  in [-1,1]
      - state["audio_sentiment"] in [-1,1] (optional)

    Outputs:
      - state["sentiment_score_numeric"] in [-1,1]
      - state["sentiment_score_display"] in [0,1] for UI friendliness
      - state["sentiment_score"] in {negative, neutral, positive}
    """
    text = _normalize_unit(state.get("text_sentiment", 0.0))
    has_audio = bool(state.get("has_audio")) or state.get("audio_sentiment") is not None

    combined = text
    audio_sentiment = state.get("audio_sentiment")
    mode = "text_only"
    if has_audio and audio_sentiment is not None:
        audio_norm = _normalize_unit(audio_sentiment)
        audio_score = state.get("audio_score")
        if audio_score is not None:
            # Scale audio weight by quality: 0 quality → 0 weight, perfect quality → 0.5 weight
            audio_weight = max(0.0, min(0.5, float(audio_score) * 0.5))
            text_weight = 1.0 - audio_weight
            mode = "text_audio_quality_weighted"
        else:
            # No quality metric — default to text-dominant 70/30
            audio_weight = 0.3
            text_weight = 0.7
            mode = "text_audio_default_weighted"
        combined = (text_weight * text) + (audio_weight * audio_norm)
        audio_sentiment = audio_norm

    state["text_sentiment"] = text
    state["audio_sentiment"] = float(audio_sentiment) if audio_sentiment is not None else None
    state["sentiment_score_numeric"] = combined
    state["sentiment_score_display"] = _to_display_score(combined)
    state["sentiment_score"] = _bucket(combined)
    state["sentiment_combiner_mode"] = mode
    state["sentiment_combiner_source"] = "deterministic"
    logger.info(
        "sentiment_combiner | mode=%s text=%.3f audio=%.3f combined=%.3f bucket=%s",
        mode,
        text,
        float(state.get("audio_sentiment", 0.0) or 0.0),
        float(state.get("sentiment_score_numeric", 0.0) or 0.0),
        state.get("sentiment_score"),
    )
    return state


sentiment_combiner_step = RunnableLambda(combine_sentiment)
