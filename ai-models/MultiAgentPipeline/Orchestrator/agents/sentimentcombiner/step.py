"""
Sentiment Combiner Agent
========================
Combines text/audio sentiment according to VX rules:
  A) with audio: (audio * 0.5) + (text * 0.5)
  B) without audio: sentiment_score = text
All sentiment values are normalized to [0, 1].
"""

import logging
from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)


def _normalize_unit(value: float | None) -> float:
    v = float(value or 0.0)
    if v < 0.0:
        return max(0.0, min(1.0, (v + 1.0) / 2.0))
    if v > 1.0:
        return 1.0
    return v


def _bucket(score: float) -> str:
    if score < 0.3:
        return "negative"
    if score < 0.65:
        return "neutral"
    return "positive"


async def combine_sentiment(state: dict) -> dict:
    """
    Inputs:
      - state["text_sentiment"]  in [0,1]
      - state["audio_sentiment"] in [0,1] (optional)

    Outputs:
      - state["sentiment_score_numeric"] in [0,1]
      - state["sentiment_score"] in {negative, neutral, positive}
    """
    text = _normalize_unit(state.get("text_sentiment", 0.0))
    has_audio = bool(state.get("has_audio")) or state.get("audio_sentiment") is not None

    combined = text
    audio_sentiment = state.get("audio_sentiment")
    mode = "text_only"
    if has_audio and audio_sentiment is not None:
        audio_norm = _normalize_unit(audio_sentiment)
        combined = (0.5 * audio_norm) + (0.5 * text)
        audio_sentiment = audio_norm
        mode = "text_audio_equal_weight"

    state["text_sentiment"] = text
    state["audio_sentiment"] = float(audio_sentiment) if audio_sentiment is not None else None
    state["sentiment_score_numeric"] = combined
    state["sentiment_score"] = _bucket(combined)
    state["sentiment_combiner_mode"] = mode
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
