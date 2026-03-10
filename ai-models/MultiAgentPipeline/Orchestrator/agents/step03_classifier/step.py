"""
Step 2 — Classification Agent
==============================
Routes the transcript to the complaint or inquiry path using local
in-process heuristic classification only.

If classifier confidence < CONFIDENCE_THRESHOLD, falls back to "complaint"
(the safer default that ensures the tenant always gets a response).
"""

import logging
import os
from pathlib import Path
from functools import lru_cache

from langchain_core.runnables import RunnableLambda

CONFIDENCE_THRESHOLD = 0.75
logger = logging.getLogger(__name__)

INQUIRY_HINTS = (
    "how", "what", "where", "when", "can i", "could i", "would it",
    "help", "guide", "question", "information", "status", "track",
    "follow up", "follow-up",
)
COMPLAINT_HINTS = (
    "broken", "not working", "fault", "issue", "problem", "outage",
    "leak", "urgent", "angry", "frustrated", "complaint", "failed",
    "error", "can't", "cannot",
)

MODEL_PATH_ENV = "CLASSIFIER_MODEL_PATH"
VECTORIZER_PATH_ENV = "CLASSIFIER_VECTORIZER_PATH"
MODEL_DIR_ENV = "CLASSIFIER_MODEL_DIR"


def _heuristic_classify(text: str) -> tuple[str, float]:
    t = (text or "").strip().lower()
    if not t:
        return "complaint", 0.0

    inquiry_score = sum(1 for k in INQUIRY_HINTS if k in t)
    complaint_score = sum(1 for k in COMPLAINT_HINTS if k in t)
    is_question = "?" in t
    if is_question:
        inquiry_score += 1

    if complaint_score > inquiry_score:
        return "complaint", 0.65
    if inquiry_score > complaint_score:
        return "inquiry", 0.65
    return "complaint", 0.5


@lru_cache(maxsize=1)
def _load_optional_model():
    model_dir = os.getenv(MODEL_DIR_ENV, "/app/agents/step03_classifier/model").strip()
    model_path = os.getenv(MODEL_PATH_ENV, "").strip() or str(Path(model_dir) / "model.pkl")
    if not model_path:
        return None
    if not Path(model_path).exists():
        logger.warning("classifier | model file not found at %s; using heuristic", model_path)
        return None
    try:
        import joblib  # type: ignore

        model = joblib.load(model_path)
        vectorizer_path = os.getenv(VECTORIZER_PATH_ENV, "").strip() or str(
            Path(model_dir) / "vectorizer.pkl"
        )
        vectorizer = None
        if vectorizer_path:
            if Path(vectorizer_path).exists():
                vectorizer = joblib.load(vectorizer_path)
            else:
                logger.warning(
                    "classifier | vectorizer file not found at %s; model input will be raw text",
                    vectorizer_path,
                )
        logger.info("classifier | loaded optional model from %s", model_path)
        return {"model": model, "vectorizer": vectorizer}
    except Exception as exc:
        logger.warning("classifier | failed to load optional model (%s); using heuristic", exc)
        return None


def get_classifier_diagnostics() -> dict[str, object]:
    model_dir = os.getenv(MODEL_DIR_ENV, "/app/agents/step03_classifier/model").strip()
    model_path = os.getenv(MODEL_PATH_ENV, "").strip() or str(Path(model_dir) / "model.pkl")
    vectorizer_path = os.getenv(VECTORIZER_PATH_ENV, "").strip() or str(
        Path(model_dir) / "vectorizer.pkl"
    )
    model_exists = bool(model_path and Path(model_path).exists())
    vectorizer_exists = bool(vectorizer_path and Path(vectorizer_path).exists())
    return {
        "classifier_model_dir": model_dir or None,
        "classifier_model_path": model_path or None,
        "classifier_model_exists": model_exists,
        "classifier_vectorizer_path": vectorizer_path or None,
        "classifier_vectorizer_exists": vectorizer_exists,
        "classifier_mode": "model" if model_exists else "mock",
    }


def _model_classify(text: str) -> tuple[str, float] | None:
    loaded = _load_optional_model()
    if not loaded:
        return None
    model = loaded["model"]
    vectorizer = loaded["vectorizer"]
    try:
        if vectorizer is not None:
            X = vectorizer.transform([text])
            pred = model.predict(X)[0]
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)[0]
                conf = float(max(probs))
            else:
                conf = 0.9
        else:
            pred = model.predict([text])[0]
            conf = 0.9
        label = str(pred).strip().lower()
        if label not in {"complaint", "inquiry"}:
            return None
        return label, conf
    except Exception as exc:
        logger.warning("classifier | optional model inference failed (%s); using heuristic", exc)
        return None


async def classify(state: dict) -> dict:
    """
    Classifies transcript in-process and sets state["label"].
    """
    if not state.get("text", "").strip():
        # Empty transcript — treat as complaint so it gets a ticket
        state["label"] = "complaint"
        state["class_confidence"] = 0.0
        state["classification_source"] = "heuristic"
        logger.info("classifier | empty text fallback -> complaint")
        return state

    model_result = _model_classify(state.get("text", ""))
    if model_result:
        label, conf = model_result
        state["classification_source"] = "model"
        logger.info("classifier | using optional model from %s", os.getenv(MODEL_PATH_ENV, "").strip())
    else:
        label, conf = _heuristic_classify(state.get("text", ""))
        state["classification_source"] = "heuristic"
        logger.info("classifier | using local in-process heuristic")
    state["label"] = label
    state["class_confidence"] = conf

    # Fallback to complaint if below threshold (safer default)
    if state["class_confidence"] < CONFIDENCE_THRESHOLD:
        state["label"] = "complaint"
    logger.info(
        "classifier | label=%s confidence=%.3f",
        state["label"],
        float(state.get("class_confidence", 0.0) or 0.0),
    )
    logger.info(
        "classifier_decision | ticket_type=%s confidence=%.3f source=%s threshold=%.2f",
        state["label"],
        float(state.get("class_confidence", 0.0) or 0.0),
        "model" if model_result else "heuristic",
        CONFIDENCE_THRESHOLD,
    )

    return state


classifier_step = RunnableLambda(classify)
