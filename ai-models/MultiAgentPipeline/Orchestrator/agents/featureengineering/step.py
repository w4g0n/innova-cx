"""
Step 5 — Feature Engineering Agent
==================================
Single agent that executes:
  1) recurrence check
  2) feature labeling (model or mock)
  3) feature engineering (RF artifacts or rule fallback)
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import torch
from langchain_core.runnables import RunnableLambda
from transformers import pipeline

logger = logging.getLogger(__name__)

FEATURE_ENGINEERING_STATE_DIR = Path(
    os.getenv(
        "FEATURE_ENGINEERING_STATE_DIR",
        "/app/models/featureengineering",
    )
)
FEATURE_LABELER_MODEL_PATH = os.getenv(
    "FEATURE_LABELER_MODEL_PATH",
    "/app/models/featureengineering/feature_labeler",
).strip()
TARGETS = ["business_impact", "safety_concern", "issue_severity", "issue_urgency"]

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

_RECURRING_PATTERNS = (
    r"\\bagain\\b",
    r"\\brepeatedly\\b",
    r"\\bmultiple times\\b",
    r"\\bstill not fixed\\b",
    r"\\bnot the first time\\b",
    r"\\bfor weeks\\b",
    r"\\bfor months\\b",
    r"\\bfifth time\\b",
    r"\\bthird time\\b",
    r"\\bsecond time\\b",
    r"\\bcalled before\\b",
    r"\\breported (this )?before\\b",
)
_RECURRING_REGEX = re.compile("|".join(_RECURRING_PATTERNS), re.IGNORECASE)

LABEL_CONFIGS = {
    "issue_severity": {
        "low": [
            "the issue is minor and mostly cosmetic with no impact on operations",
            "the complaint describes a small inconvenience that does not affect work",
            "core building systems are fully functional and unaffected",
        ],
        "medium": [
            "the issue partially disrupts operations but work can continue",
            "some systems are degraded but not completely failed",
            "the complaint describes a moderate problem requiring attention",
        ],
        "high": [
            "core building systems have completely failed",
            "the issue has made the premises unusable or unsafe",
            "operations have been fully halted due to this problem",
        ],
    },
    "issue_urgency": {
        "low": [
            "the issue is minor and can wait for a scheduled maintenance visit",
            "there is no time pressure mentioned in this complaint",
            "the problem has existed for a while without major consequence",
        ],
        "medium": [
            "the issue needs to be resolved within the next few days",
            "the complaint implies growing frustration but no immediate crisis",
            "action is needed soon but the situation is not yet critical",
        ],
        "high": [
            "the complaint explicitly demands same-day or immediate resolution",
            "the situation is described as an emergency requiring instant response",
            "every hour of delay causes direct measurable harm to operations",
        ],
    },
    "safety_concern": {
        True: [
            "the complaint explicitly describes a physical danger or injury risk",
            "someone could be directly harmed by this issue if left unresolved",
            "the problem involves fire, flooding, electrical hazard, or structural danger",
        ],
        False: [
            "the complaint is about a service, billing, or administrative issue",
            "the issue is an inconvenience or operational problem with no physical danger",
            "there is no mention of injury risk, hazardous conditions, or physical harm",
        ],
    },
    "business_impact": {
        "low": [
            "the issue is a minor annoyance that does not affect productivity",
            "staff can work normally and the complaint has negligible business impact",
            "the problem affects a small cosmetic or non-essential aspect of the office",
        ],
        "medium": [
            "the issue is reducing team productivity but work is still happening",
            "some workflows are disrupted but the business is partially operational",
            "the complaint describes a meaningful but not critical operational disruption",
        ],
        "high": [
            "the complaint states that business operations have stopped or cannot continue",
            "staff are unable to work due to this issue",
            "the problem is causing significant financial loss or client-facing disruption",
        ],
    },
}


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


def _optional_bool(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _has_safety_signal(text: str) -> bool:
    t = str(text or "").lower()
    return any(keyword in t for keyword in SAFETY_KEYWORDS)


def _mock_labels(text: str) -> dict[str, Any]:
    t = text.lower()
    issue_severity = "medium"
    issue_urgency = "medium"
    business_impact = "medium"
    safety_concern = False

    if any(k in t for k in ("fire", "smoke", "electric", "shock", "gas leak", "flood", "hazard", "unsafe")):
        safety_concern = True
        issue_severity = "high"
    if any(k in t for k in ("urgent", "asap", "immediate", "today", "right now", "emergency")):
        issue_urgency = "high"
    if any(k in t for k in ("operations stopped", "cannot work", "business halted", "financial loss", "losing money")):
        business_impact = "high"
    if any(k in t for k in ("minor", "cosmetic", "small inconvenience")):
        issue_severity = "low"
        issue_urgency = "low"
        business_impact = "low"

    return {
        "issue_severity": issue_severity,
        "issue_urgency": issue_urgency,
        "business_impact": business_impact,
        "safety_concern": safety_concern,
    }


@lru_cache(maxsize=1)
def _load_feature_labeler():
    model_name = FEATURE_LABELER_MODEL_PATH
    if not model_name:
        logger.info("feature_engineering | no FEATURE_LABELER_MODEL_PATH provided; using mock labeler")
        return None
    model_path = Path(model_name)
    if not (model_path / "config.json").exists():
        logger.info("feature_engineering | labeler model missing config.json at %s; using mock", model_name)
        return None

    force_cpu = os.getenv("FEATURE_LABELER_FORCE_CPU", "false").lower() in {"1", "true", "yes"}
    device = -1 if force_cpu else (0 if torch.cuda.is_available() else -1)
    device_name = "CPU" if device == -1 else "GPU"

    try:
        logger.info("feature_engineering | loading labeler=%s device=%s", model_name, device_name)
        return pipeline(
            task="zero-shot-classification",
            model=model_name,
            tokenizer=model_name,
            device=device,
        )
    except Exception as exc:
        logger.warning("feature_engineering | labeler load failed (%s), using mock", exc)
        return None


def _average_hypothesis_scores(
    score_map: dict[str, float],
    class_hypotheses: dict[Any, list[str]],
) -> dict[Any, float]:
    return {
        class_label: (
            sum(score_map[hypothesis] for hypothesis in hypotheses) / float(len(hypotheses))
        )
        for class_label, hypotheses in class_hypotheses.items()
    }


def _classify_ticket(classifier, text: str) -> dict[str, Any]:
    output_labels: dict[str, Any] = {}
    for label_name, class_hypotheses in LABEL_CONFIGS.items():
        all_hypotheses = []
        for hypotheses in class_hypotheses.values():
            all_hypotheses.extend(hypotheses)
        result = classifier(text, candidate_labels=all_hypotheses, multi_label=False)
        score_map = dict(zip(result["labels"], result["scores"]))
        class_scores = _average_hypothesis_scores(score_map, class_hypotheses)
        output_labels[label_name] = max(class_scores, key=class_scores.get)
    return output_labels


def _apply_recurrence_step(state: dict, text: str) -> None:
    explicit = _optional_bool(state.get("is_recurring"))
    if explicit is not None:
        state["is_recurring"] = explicit
        state["is_recurring_source"] = "state"
    else:
        state["is_recurring"] = bool(_RECURRING_REGEX.search(text))
        state["is_recurring_source"] = "heuristic"


def _apply_labeling_step(state: dict, text: str) -> None:
    classifier = _load_feature_labeler()
    if classifier is None:
        labels = _mock_labels(text)
        label_source = "mock"
    else:
        try:
            labels = _classify_ticket(classifier, text)
            label_source = "nli"
        except Exception as exc:
            logger.warning("feature_engineering | labeler inference failed (%s), using mock", exc)
            labels = _mock_labels(text)
            label_source = "mock"

    state["issue_severity"] = str(labels["issue_severity"]).lower()
    state["issue_urgency"] = str(labels["issue_urgency"]).lower()
    state["business_impact"] = str(labels["business_impact"]).lower()
    state["safety_concern"] = bool(labels["safety_concern"])
    state["feature_labels_source"] = label_source


@lru_cache(maxsize=1)
def _load_artifacts():
    if not str(FEATURE_ENGINEERING_STATE_DIR).strip():
        logger.info("feature_engineering | FEATURE_ENGINEERING_STATE_DIR not set, using labels/rules")
        return {}
    artifacts = {}
    for target in TARGETS:
        target_dir = FEATURE_ENGINEERING_STATE_DIR / target
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


def get_feature_engineering_diagnostics() -> dict[str, object]:
    state_dir = str(FEATURE_ENGINEERING_STATE_DIR).strip()
    state_dir_enabled = bool(state_dir)
    target_count = 0
    if state_dir_enabled:
        for target in TARGETS:
            target_dir = Path(state_dir) / target
            if (
                (target_dir / "rf.pkl").exists()
                and (target_dir / "label_encoder.pkl").exists()
                and (target_dir / "tfidf_vectorizer.pkl").exists()
            ):
                target_count += 1

    labeler_model = FEATURE_LABELER_MODEL_PATH or None
    labeler_exists = bool(labeler_model and (Path(labeler_model) / "config.json").exists())

    return {
        "feature_engineering_model_dir": state_dir or None,
        "feature_engineering_model_enabled": state_dir_enabled,
        "feature_engineering_targets_loaded": target_count,
        "feature_engineering_mode": "model" if target_count > 0 else "labels+rules",
        "feature_labeler_model": labeler_model,
        "feature_labeler_model_exists": labeler_exists,
        "feature_labeler_mode": "model" if labeler_exists else "mock",
    }


async def engineer_features(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("feature_engineering | skipped (label=%s)", state.get("label"))
        return state

    text = str(state.get("text") or "").strip()

    # Step 1: recurrence check
    _apply_recurrence_step(state, text)

    # Step 2: labeling (model/mock)
    _apply_labeling_step(state, text)

    # Step 3: optional RF refinement / fallback rules
    artifacts = _load_artifacts()
    business_impact = (
        state.get("business_impact")
        or _predict_target(artifacts, "business_impact", text)
        or "medium"
    )
    issue_severity = (
        state.get("issue_severity")
        or _predict_target(artifacts, "issue_severity", text)
        or "medium"
    )
    issue_urgency = (
        state.get("issue_urgency")
        or _predict_target(artifacts, "issue_urgency", text)
        or "medium"
    )
    predicted_safety = _predict_target(artifacts, "safety_concern", text)
    explicit_safety = _optional_bool(state.get("safety_concern"))

    severity_norm = _normalize_level(issue_severity, default="medium")
    safety_from_model = _to_bool(predicted_safety, default=False)
    safety_from_keywords = _has_safety_signal(text)
    safety_from_severity = severity_norm in {"high", "critical"}

    state["business_impact"] = _normalize_level(business_impact, default="medium")
    if explicit_safety is not None:
        state["safety_concern"] = explicit_safety
    else:
        state["safety_concern"] = bool(
            safety_from_model and (safety_from_keywords or safety_from_severity)
        )
    state["issue_severity"] = severity_norm
    state["issue_urgency"] = _normalize_level(issue_urgency, default="medium")

    logger.info(
        "feature_engineering | recurring=%s recurring_source=%s labels_source=%s impact=%s safety=%s severity=%s urgency=%s",
        state.get("is_recurring"),
        state.get("is_recurring_source"),
        state.get("feature_labels_source"),
        state["business_impact"],
        state["safety_concern"],
        state["issue_severity"],
        state["issue_urgency"],
    )

    return state


feature_engineering_step = RunnableLambda(engineer_features)
