"""
Sentiment Combiner Agent
========================
Uses the shared AudioSentimentAnalyzer from SentimentCombiner package.
"""

import sys
import logging
from langchain_core.runnables import RunnableLambda

# Copied in Docker to /app/sentiment_combiner/
sys.path.insert(0, "/app/sentiment_combiner")
from sentiment_combiner import AudioSentimentAnalyzer  # noqa: E402


_analyzer = AudioSentimentAnalyzer()
logger = logging.getLogger(__name__)


def _bucket(score: float) -> str:
    if score < -0.25:
        return "negative"
    if score > 0.25:
        return "positive"
    return "neutral"


async def combine_sentiment(state: dict) -> dict:
    """
    Inputs:
      - state["text_sentiment"]  in [-1,1]
      - state["audio_sentiment"] in [-1,1] (optional)

    Outputs:
      - state["sentiment_score_numeric"] in [-1,1]
      - state["sentiment_score"] in {negative, neutral, positive}
    """
    text = float(state.get("text_sentiment", 0.0) or 0.0)
    audio_features = state.get("audio_features") or {}
    has_audio = bool(state.get("has_audio")) or bool(audio_features)

    combined = text
    audio_sentiment = state.get("audio_sentiment")
    mode = "text_only"
    if has_audio and audio_features:
        features = {
            "mean_energy": float(audio_features.get("mean_energy", 0.05) or 0.05),
            "std_energy": float(audio_features.get("std_energy", 0.01) or 0.01),
            "mean_pitch": float(audio_features.get("mean_pitch", 150.0) or 150.0),
            "std_pitch": float(audio_features.get("std_pitch", 25.0) or 25.0),
            "mean_zero_crossing_rate": float(audio_features.get("mean_zero_crossing_rate", 0.08) or 0.08),
        }
        signals = _analyzer.extract_sentiment_signals(features)
        result = _analyzer.combine_text_audio_sentiment(text, signals, text_weight=0.7, audio_weight=0.3)
        combined = float(result["combined_sentiment"])
        audio_sentiment = float(result["audio_sentiment"])
        mode = "text_audio_combined"
    elif has_audio and audio_sentiment is not None:
        combined = (0.7 * text) + (0.3 * float(audio_sentiment))
        mode = "text_audio_weighted"

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
