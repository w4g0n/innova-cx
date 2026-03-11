"""
Step 3 - Sentiment Analysis
===========================
Runs the sentiment model in an isolated subprocess so a native/runtime crash
does not terminate the orchestrator process mid-pipeline.
"""

import json
import logging
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)
NEUTRAL_SENTIMENT_DEADZONE = float(os.getenv("NEUTRAL_SENTIMENT_DEADZONE", "0.2"))
SENTIMENT_CALIBRATION_BIAS = float(os.getenv("SENTIMENT_CALIBRATION_BIAS", "-0.12"))
SENTIMENT_CALIBRATION_SCALE = float(os.getenv("SENTIMENT_CALIBRATION_SCALE", "1.35"))
SENTIMENT_NEGATIVE_GAIN = float(os.getenv("SENTIMENT_NEGATIVE_GAIN", "1.15"))
SENTIMENT_POSITIVE_GAIN = float(os.getenv("SENTIMENT_POSITIVE_GAIN", "0.85"))
STRONG_COMPLAINT_NEGATIVE_FLOOR = float(os.getenv("STRONG_COMPLAINT_NEGATIVE_FLOOR", "-0.45"))
STRONG_NEGATIVE_PHRASES = (
    "crisis",
    "emergency",
    "overflowing",
    "flood",
    "flooding",
    "water leak",
    "gas leak",
    "fire",
    "smoke",
    "unsafe",
    "hazard",
    "outage",
    "not working",
    "broken",
    "cannot work",
    "can't work",
    "unable to work",
    "cannot login",
    "can't login",
)
MODERATE_NEGATIVE_PHRASES = (
    "urgent",
    "asap",
    "immediately",
    "right now",
    "again",
    "repeated",
    "frustrated",
    "angry",
    "noisy",
    "loud",
    "disturbance",
    "issue",
    "problem",
    "failed",
)
POSITIVE_PHRASES = (
    "thank you",
    "thanks",
    "appreciate",
    "resolved",
    "great",
    "fixed",
)
NOISE_COMPLAINT_TERMS = (
    "neighbor",
    "neighbors",
    "neighbour",
    "neighbours",
    "noisy",
    "loud",
    "music",
    "disturbance",
)

RUNTIME_SRC = Path("/app/sentiment_pipeline")
if str(RUNTIME_SRC) not in sys.path:
    sys.path.insert(0, str(RUNTIME_SRC))

SENTIMENT_MODEL_DIR = os.getenv(
    "SENTIMENT_MODEL_DIR",
    "/app/agents/step04_sentimentanalysis/model",
).strip()
SENTIMENT_SUBPROCESS_TIMEOUT_SECONDS = float(
    os.getenv("SENTIMENT_SUBPROCESS_TIMEOUT_SECONDS", "45")
)
SENTIMENT_HELPER_PATH = Path(__file__).with_name("sentiment_runtime_worker.py")
SENTIMENT_RUNTIME_MODE = os.getenv("SENTIMENT_RUNTIME_MODE", "inprocess").strip().lower()


class _FallbackPredictor:
    def predict(self, text: str) -> dict:
        t = text.lower()
        score = 0.0
        if any(
            k in t
            for k in [
                "urgent",
                "emergency",
                "unacceptable",
                "broken",
                "not working",
                "angry",
                "frustrated",
                "leak",
                "flood",
                "outage",
            ]
        ):
            score -= 0.6
        if any(k in t for k in ["thank you", "appreciate", "resolved", "great"]):
            score += 0.4
        return {"text_sentiment": max(-1.0, min(1.0, score))}


def _runtime_model_available() -> bool:
    model_dir = Path(SENTIMENT_MODEL_DIR) if SENTIMENT_MODEL_DIR else None
    return bool(model_dir and (model_dir / "model.pt").exists())


@lru_cache(maxsize=1)
def _load_predictor():
    if not _runtime_model_available():
        return None

    from inference import SentimentPredictor  # noqa: E402

    logger.info("sentiment | loading cached model from %s", SENTIMENT_MODEL_DIR)
    return SentimentPredictor(model_dir=SENTIMENT_MODEL_DIR, device="cpu")


def get_sentiment_diagnostics() -> dict[str, Any]:
    model_dir = SENTIMENT_MODEL_DIR
    model_file_exists = bool(model_dir and (Path(model_dir) / "model.pt").exists())
    mode = "model" if _runtime_model_available() else "mock"
    return {
        "sentiment_model_dir": model_dir or None,
        "sentiment_model_enabled": bool(model_dir),
        "sentiment_model_file_exists": model_file_exists,
        "sentiment_runtime_worker": str(SENTIMENT_HELPER_PATH),
        "sentiment_runtime_worker_exists": SENTIMENT_HELPER_PATH.exists(),
        "sentiment_runtime_mode": SENTIMENT_RUNTIME_MODE,
        "sentiment_subprocess_timeout_seconds": SENTIMENT_SUBPROCESS_TIMEOUT_SECONDS,
        "sentiment_mode": mode,
    }


def _predict_inprocess(text: str) -> dict | None:
    if not _runtime_model_available():
        return None

    try:
        predictor = _load_predictor()
    except Exception as exc:
        logger.warning("sentiment | in-process model load failed (%s)", exc)
        return None

    if predictor is None:
        return None

    try:
        return predictor.predict(text)
    except Exception as exc:
        logger.warning("sentiment | in-process prediction failed (%s)", exc)
        return None


def _predict_via_subprocess(text: str) -> dict | None:
    if not _runtime_model_available():
        return None

    try:
        completed = subprocess.run(
            [sys.executable, str(SENTIMENT_HELPER_PATH), SENTIMENT_MODEL_DIR, text],
            capture_output=True,
            text=True,
            timeout=SENTIMENT_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("sentiment | subprocess timed out after %.1fs", SENTIMENT_SUBPROCESS_TIMEOUT_SECONDS)
        return None
    except Exception as exc:
        logger.warning("sentiment | subprocess launch failed (%s)", exc)
        return None

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        logger.warning("sentiment | subprocess failed rc=%s err=%s", completed.returncode, stderr)
        return None

    try:
        payload = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError as exc:
        logger.warning("sentiment | invalid subprocess JSON (%s)", exc)
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _calibrate_sentiment_score(value: Any) -> float:
    """Apply global calibration to raw regression output before complaint-specific adjustments."""
    try:
        score = float(value or 0.0)
    except Exception:
        return 0.0
    score = max(-1.0, min(1.0, score))
    score = (score * SENTIMENT_CALIBRATION_SCALE) + SENTIMENT_CALIBRATION_BIAS
    if score < 0:
        score *= SENTIMENT_NEGATIVE_GAIN
    elif score > 0:
        score *= SENTIMENT_POSITIVE_GAIN
    score = max(-1.0, min(1.0, score))
    return score


def _complaint_domain_adjustment(text: str) -> float:
    t = str(text or "").lower()
    if not t:
        return 0.0

    strong_hits = sum(1 for phrase in STRONG_NEGATIVE_PHRASES if phrase in t)
    moderate_hits = sum(1 for phrase in MODERATE_NEGATIVE_PHRASES if phrase in t)
    positive_hits = sum(1 for phrase in POSITIVE_PHRASES if phrase in t)

    uppercase_words = sum(1 for word in str(text or "").split() if len(word) >= 4 and word.isupper())
    intensity_bonus = 0.0
    if uppercase_words >= 3:
        intensity_bonus += 0.12
    if "!" in str(text or ""):
        intensity_bonus += 0.08
    noise_hits = sum(1 for phrase in NOISE_COMPLAINT_TERMS if phrase in t)
    if noise_hits >= 2:
        intensity_bonus += 0.12

    adjustment = (strong_hits * 0.24) + (moderate_hits * 0.09) + intensity_bonus - (positive_hits * 0.18)
    return max(-0.35, min(0.8, adjustment))


def _apply_complaint_sentiment_calibration(raw_score: Any, text: str) -> float:
    score = _calibrate_sentiment_score(raw_score)
    adjustment = _complaint_domain_adjustment(text)
    if adjustment > 0.0:
        score -= adjustment
        if adjustment >= 0.30 and score > STRONG_COMPLAINT_NEGATIVE_FLOOR:
            score = STRONG_COMPLAINT_NEGATIVE_FLOOR
    score = max(-1.0, min(1.0, score))
    if abs(score) < NEUTRAL_SENTIMENT_DEADZONE:
        return 0.0
    return score


async def analyze_sentiment(state: dict) -> dict:
    predictor = _FallbackPredictor()
    model_data = None
    if SENTIMENT_RUNTIME_MODE == "subprocess":
        model_data = _predict_via_subprocess(state["text"])
    else:
        model_data = _predict_inprocess(state["text"])
        if model_data is None and SENTIMENT_RUNTIME_MODE == "hybrid":
            model_data = _predict_via_subprocess(state["text"])

    data = model_data or predictor.predict(state["text"])

    state["sentiment_mode"] = "model" if "processing_time_ms" in data else "mock"
    state["text_sentiment"] = _apply_complaint_sentiment_calibration(
        data.get("text_sentiment", 0.0),
        state.get("text", ""),
    )
    state.pop("sentiment_category", None)
    state.pop("urgency", None)
    state.pop("keywords", None)
    logger.info(
        "sentiment | text_sentiment=%.3f mode=%s",
        float(state.get("text_sentiment", 0.0) or 0.0),
        state.get("sentiment_mode"),
    )
    return state


sentiment_step = RunnableLambda(analyze_sentiment)
