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
    state["text_sentiment"] = float(data.get("text_sentiment", 0.0) or 0.0)
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
