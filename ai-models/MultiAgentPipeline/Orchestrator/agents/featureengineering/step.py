"""
Step 5 — Feature Engineering Agent
==================================
Runs inference from saved RF model state bundle and writes:
  business_impact, safety_concern, issue_severity, issue_urgency, is_recurring
"""

from __future__ import annotations

import os
import logging
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from langchain_core.runnables import RunnableLambda

MODEL_STATE_DIR = Path(
    os.getenv(
        "FEATURE_ENGINEERING_STATE_DIR",
        "/app/feature_engineering_models",
    )
)
TARGETS = ["business_impact", "safety_concern", "issue_severity", "issue_urgency"]
logger = logging.getLogger(__name__)

SAFETY_KEYWORDS = (
    "fire",
    "smoke",
    "gas leak",
    "electrical",
    "electric shock",
    "shock",
    "sparking",
    "short circuit",
    "flood",
    "water leak",
    "leak",
    "hazard",
    "unsafe",
    "emergency",
    "alarm",
    "chemical",
    "toxic",
)


def _normalize_level(v: str, default: str = "medium") -> str:
    s = str(v or "").strip().lower()
    return s if s in {"low", "medium", "high", "critical"} else default


def _to_bool(value, default=False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return default


def _has_safety_signal(text: str) -> bool:
    t = str(text or "").lower()
    return any(keyword in t for keyword in SAFETY_KEYWORDS)


@lru_cache(maxsize=1)
def _load_artifacts():
    artifacts = {}
    for target in TARGETS:
        target_dir = MODEL_STATE_DIR / target
        model_path = target_dir / "rf.pkl"
        le_path = target_dir / "label_encoder.pkl"
        vec_path = target_dir / "tfidf_vectorizer.pkl"
        if not (model_path.exists() and le_path.exists() and vec_path.exists()):
            continue
        artifacts[target] = {
            "model": joblib.load(model_path),
            "label_encoder": joblib.load(le_path),
            "vectorizer": joblib.load(vec_path),
        }
    return artifacts


def _predict_target(artifacts, target: str, text: str):
    payload = artifacts.get(target)
    if not payload:
        return None
    vec = payload["vectorizer"].transform([text]).toarray().astype(np.float32)
    pred = payload["model"].predict(vec)
    label = payload["label_encoder"].inverse_transform(pred)[0]
    return str(label).strip()


async def engineer_features(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("feature_engineering | skipped (label=%s)", state.get("label"))
        return state

    text = str(state.get("text") or "").strip()
    artifacts = _load_artifacts()

    # Model-based predictions
    business_impact = _predict_target(artifacts, "business_impact", text) or "medium"
    safety_concern = _predict_target(artifacts, "safety_concern", text)
    issue_severity = _predict_target(artifacts, "issue_severity", text) or "medium"
    issue_urgency = _predict_target(artifacts, "issue_urgency", text) or "medium"

    severity_norm = _normalize_level(issue_severity, default="medium")
    safety_from_model = _to_bool(safety_concern, default=False)
    safety_from_keywords = _has_safety_signal(text)
    safety_from_severity = severity_norm in {"high", "critical"}

    state["business_impact"] = _normalize_level(business_impact, default="medium")
    # Conservative safety flag to reduce false positives:
    # require model positive + concrete safety signal.
    state["safety_concern"] = bool(
        safety_from_model and (safety_from_keywords or safety_from_severity)
    )
    state["issue_severity"] = severity_norm
    state["issue_urgency"] = _normalize_level(issue_urgency, default="medium")

    # Recurrence currently comes from upstream ticket context or defaults False.
    state["is_recurring"] = _to_bool(state.get("is_recurring"), default=False)
    logger.info(
        "feature_engineering | business_impact=%s safety_concern=%s issue_severity=%s issue_urgency=%s is_recurring=%s safety_model=%s safety_keywords=%s",
        state["business_impact"],
        state["safety_concern"],
        state["issue_severity"],
        state["issue_urgency"],
        state["is_recurring"],
        safety_from_model,
        safety_from_keywords,
    )

    return state


feature_engineering_step = RunnableLambda(engineer_features)
