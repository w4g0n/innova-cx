"""
Step 4 — Audio Analysis
========================
Runs local audio sentiment extraction from provided audio features.
Only runs when audio was provided and the complaint path is active.

For text-only inputs, this step marks the ticket as no-audio and leaves
sentiment combination to text-only logic.
"""

import logging
import sys

from langchain_core.runnables import RunnableLambda

# Copied in Docker to /app/sentiment_combiner/
sys.path.insert(0, "/app/sentiment_combiner")
try:
    from sentiment_combiner import AudioSentimentAnalyzer  # noqa: E402
    _AUDIO_MODEL_AVAILABLE = True
except Exception as exc:  # pragma: no cover - runtime fallback guard
    AudioSentimentAnalyzer = None
    _AUDIO_MODEL_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "audio_analysis | sentiment combiner package unavailable, using mock audio sentiment. err=%s",
        exc,
    )

logger = logging.getLogger(__name__)
_analyzer = AudioSentimentAnalyzer() if _AUDIO_MODEL_AVAILABLE else None


def get_audio_analysis_diagnostics() -> dict[str, object]:
    return {
        "audio_analysis_model_available": _AUDIO_MODEL_AVAILABLE,
        "audio_analysis_mode": "model" if _AUDIO_MODEL_AVAILABLE else "mock",
        "audio_analysis_mode_reason": (
            "AudioSentimentAnalyzer loaded from /app/sentiment_combiner"
            if _AUDIO_MODEL_AVAILABLE
            else "AudioSentimentAnalyzer missing; using neutral mock fallback when audio is present"
        ),
    }


async def analyze_audio(state: dict) -> dict:
    has_audio_ticket = bool(state.get("has_audio")) or bool(state.get("audio_features"))
    state["has_audio"] = has_audio_ticket
    state["audio_analysis_mode"] = "model" if _analyzer is not None else "mock"
    if state["label"] != "complaint" or not has_audio_ticket:
        state["audio_sentiment"] = None
        logger.info(
            "audio_analysis | skipped (label=%s has_audio=%s)",
            state.get("label"),
            has_audio_ticket,
        )
        return state

    audio_features = state.get("audio_features") or {}
    features = {
        "mean_energy": float(audio_features.get("mean_energy", 0.05) or 0.05),
        "std_energy": float(audio_features.get("std_energy", 0.01) or 0.01),
        "mean_pitch": float(audio_features.get("mean_pitch", 150.0) or 150.0),
        "std_pitch": float(audio_features.get("std_pitch", 25.0) or 25.0),
        "mean_zero_crossing_rate": float(audio_features.get("mean_zero_crossing_rate", 0.08) or 0.08),
    }
    if _analyzer is None:
        state["audio_sentiment"] = 0.5
        logger.info("audio_analysis | model unavailable, using mock audio_sentiment=0.5")
        return state

    signals = _analyzer.extract_sentiment_signals(features)
    state["audio_sentiment"] = float(signals.overall_audio_sentiment)
    logger.info(
        "audio_analysis | audio_sentiment=%.3f",
        float(state.get("audio_sentiment", 0.0) or 0.0),
    )
    return state


audio_analysis_step = RunnableLambda(analyze_audio)
