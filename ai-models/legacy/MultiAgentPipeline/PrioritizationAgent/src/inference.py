"""
Prioritization Agent Runtime (Model-Only)
========================================

This module is used by the orchestrator at runtime.
- No fuzzy logic here.
- Loads a pre-trained model state produced offline by PrioritzationAgentTraining.
- Supports live relearning using manager-approved rescoring labels.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

try:
    from xgboost import XGBClassifier
except Exception:  # pragma: no cover
    XGBClassifier = None


logger = logging.getLogger(__name__)

SENTIMENT_LEVELS = ["negative", "neutral", "positive"]
SEVERITY_LEVELS = ["low", "medium", "high"]
URGENCY_LEVELS = ["low", "medium", "high"]
IMPACT_LEVELS = ["low", "medium", "high"]
TICKET_TYPES = ["complaint", "inquiry"]
PRIORITY_LEVELS = ["low", "medium", "high", "critical"]

SENTIMENT_MAP = {"negative": 0, "neutral": 1, "positive": 2}
SEVERITY_MAP = {"low": 0, "medium": 1, "high": 2}
URGENCY_MAP = {"low": 0, "medium": 1, "high": 2}
IMPACT_MAP = {"low": 0, "medium": 1, "high": 2}
TICKET_TYPE_MAP = {"complaint": 0, "inquiry": 1}
PRIORITY_MAP = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class ModelPaths:
    base_dir: Path
    model_file: Path
    metadata_file: Path
    base_dataset_csv: Path
    feedback_dataset_csv: Path
    merged_dataset_csv: Path


def _resolve_paths() -> ModelPaths:
    default_dir = "/app/agents/step09_priority/model"
    requested_dir = Path(os.getenv("PRIORITY_MODEL_DIR", default_dir)).resolve()
    fallback_dir = (Path(__file__).resolve().parents[1] / "runtime").resolve()
    try:
        requested_dir.mkdir(parents=True, exist_ok=True)
        base_dir = requested_dir
    except Exception:
        fallback_dir.mkdir(parents=True, exist_ok=True)
        base_dir = fallback_dir
        logger.warning(
            "priority | unable to use PRIORITY_MODEL_DIR=%s, falling back to %s",
            requested_dir,
            fallback_dir,
        )

    base_dataset_override = os.getenv("PRIORITY_BASE_DATASET_PATH", "").strip()
    if base_dataset_override:
        base_dataset_csv = Path(base_dataset_override).resolve()
    else:
        base_dataset_csv = base_dir / "synthetic_training_data.csv"

    return ModelPaths(
        base_dir=base_dir,
        model_file=base_dir / "priority_xgb_model.json",
        metadata_file=base_dir / "priority_xgb_metadata.json",
        base_dataset_csv=base_dataset_csv,
        feedback_dataset_csv=base_dir / "manager_feedback_data.csv",
        merged_dataset_csv=base_dir / "runtime_training_data.csv",
    )


PATHS = _resolve_paths()
RETRAIN_EVERY_N_FEEDBACK = max(1, int(os.getenv("PRIORITY_RETRAIN_EVERY_N_FEEDBACK", "5")))
PRIORITY_USE_MOCK = os.getenv("PRIORITY_USE_MOCK", "false").lower() in {"1", "true", "yes"}

_model: XGBClassifier | None = None
_model_ready = False
_xgb_unavailable_warned = False


def _normalize_choice(value: str, allowed: set[str], default: str) -> str:
    v = str(value or "").strip().lower()
    return v if v in allowed else default


def _normalize_3level(value: str) -> str:
    v = str(value or "").strip().lower()
    if v == "critical":
        return "high"
    return _normalize_choice(v, {"low", "medium", "high"}, "medium")


def _normalize_sentiment(value: str | float) -> str:
    if isinstance(value, (int, float)):
        score = float(value)
        if score < -0.25:
            return "negative"
        if score > 0.25:
            return "positive"
        return "neutral"
    return _normalize_choice(str(value), set(SENTIMENT_LEVELS), "neutral")


def _encode_row(
    *,
    sentiment_score: str | float,
    issue_severity_val: str,
    issue_urgency_val: str,
    business_impact_val: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
) -> list[float]:
    sentiment = _normalize_sentiment(sentiment_score)
    severity = _normalize_3level(issue_severity_val)
    urgency = _normalize_3level(issue_urgency_val)
    impact = _normalize_choice(business_impact_val, set(IMPACT_LEVELS), "medium")
    ticket = _normalize_choice(ticket_type, set(TICKET_TYPES), "complaint")

    return [
        float(SENTIMENT_MAP[sentiment]),
        float(SEVERITY_MAP[severity]),
        float(URGENCY_MAP[urgency]),
        float(IMPACT_MAP[impact]),
        1.0 if bool(safety_concern) else 0.0,
        1.0 if bool(is_recurring) else 0.0,
        float(TICKET_TYPE_MAP[ticket]),
    ]


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_rows(path: Path, rows: list[dict[str, Any]], append: bool = False) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    mode = "a" if append and path.exists() else "w"
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if mode == "w":
            writer.writeheader()
        writer.writerows(rows)


def _prepare_training_arrays(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    x_rows: list[list[float]] = []
    y_rows: list[int] = []

    for row in rows:
        label = _normalize_choice(str(row.get("label_priority", "")), set(PRIORITY_LEVELS), "")
        if label not in PRIORITY_MAP:
            continue

        x_rows.append(
            _encode_row(
                sentiment_score=row.get("sentiment_score", "neutral"),
                issue_severity_val=str(row.get("issue_severity_val", "medium")),
                issue_urgency_val=str(row.get("issue_urgency_val", "medium")),
                business_impact_val=str(row.get("business_impact_val", "medium")),
                safety_concern=str(row.get("safety_concern", "false")).strip().lower() in {"1", "true", "yes", "y"},
                is_recurring=str(row.get("is_recurring", "false")).strip().lower() in {"1", "true", "yes", "y"},
                ticket_type=str(row.get("ticket_type", "complaint")),
            )
        )
        y_rows.append(PRIORITY_MAP[label])

    if not x_rows:
        return np.zeros((0, 7), dtype=np.float32), np.zeros((0,), dtype=np.int32)

    return np.asarray(x_rows, dtype=np.float32), np.asarray(y_rows, dtype=np.int32)


def _train_from_rows(rows: list[dict[str, Any]], force: bool = False) -> dict[str, Any]:
    global _model, _model_ready

    if XGBClassifier is None:
        return {"trained": False, "reason": "xgboost_not_installed"}

    X, y = _prepare_training_arrays(rows)
    if len(X) == 0:
        return {"trained": False, "reason": "no_training_rows"}

    model = XGBClassifier(
        objective="multi:softprob",
        num_class=4,
        n_estimators=260,
        max_depth=5,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="mlogloss",
        n_jobs=1,
    )
    model.fit(X, y)
    model.save_model(str(PATHS.model_file))

    metadata = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": int(len(X)),
        "base_dataset_rows": int(len(_read_rows(PATHS.base_dataset_csv))),
        "feedback_rows": int(len(_read_rows(PATHS.feedback_dataset_csv))),
        "forced_retrain": bool(force),
        "feature_order": [
            "sentiment_score",
            "issue_severity",
            "issue_urgency",
            "business_impact",
            "safety_concern",
            "is_recurring",
            "ticket_type",
        ],
    }
    PATHS.metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    _model = model
    _model_ready = True
    return {"trained": True, **metadata}


def _load_model_if_exists() -> bool:
    global _model, _model_ready
    if _model_ready and _model is not None:
        return True
    if XGBClassifier is None:
        return False
    if not PATHS.model_file.exists():
        return False
    try:
        model = XGBClassifier()
        model.load_model(str(PATHS.model_file))
        _model = model
        _model_ready = True
        return True
    except Exception as exc:
        logger.warning("priority | failed to load model: %s", exc)
        return False


def _ensure_model_ready() -> bool:
    global _xgb_unavailable_warned
    if XGBClassifier is None:
        if not _xgb_unavailable_warned:
            logger.warning("priority | xgboost unavailable; model inference disabled")
            _xgb_unavailable_warned = True
        return False
    return _load_model_if_exists()


def _merge_training_rows() -> list[dict[str, Any]]:
    base_rows = _read_rows(PATHS.base_dataset_csv)
    feedback_rows = _read_rows(PATHS.feedback_dataset_csv)
    merged = [dict(r) for r in base_rows] + [dict(r) for r in feedback_rows]

    canonical_fields = [
        "sentiment_score",
        "issue_severity_val",
        "issue_urgency_val",
        "business_impact_val",
        "safety_concern",
        "is_recurring",
        "ticket_type",
        "label_priority",
        "label_source",
        "ticket_id",
        "created_at",
    ]
    normalized = []
    for row in merged:
        normalized.append({field: row.get(field, "") for field in canonical_fields})

    merged = normalized
    if merged:
        _write_rows(PATHS.merged_dataset_csv, merged, append=False)
    return merged


def add_manager_feedback_example(
    *,
    sentiment_score: str,
    issue_severity_val: str,
    issue_urgency_val: str,
    business_impact_val: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
    approved_priority: str,
    ticket_id: str | None = None,
    retrain_now: bool = False,
) -> dict[str, Any]:
    label = _normalize_choice(approved_priority, set(PRIORITY_LEVELS), "")
    if label not in PRIORITY_MAP:
        raise ValueError(f"invalid approved_priority: {approved_priority}")

    feedback_row = {
        "sentiment_score": _normalize_sentiment(sentiment_score),
        "issue_severity_val": _normalize_3level(issue_severity_val),
        "issue_urgency_val": _normalize_3level(issue_urgency_val),
        "business_impact_val": _normalize_choice(business_impact_val, set(IMPACT_LEVELS), "medium"),
        "safety_concern": bool(safety_concern),
        "is_recurring": bool(is_recurring),
        "ticket_type": _normalize_choice(ticket_type, set(TICKET_TYPES), "complaint"),
        "label_priority": label,
        "label_source": "manager_approved_rescore",
        "ticket_id": ticket_id or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_rows(PATHS.feedback_dataset_csv, [feedback_row], append=True)

    feedback_count = len(_read_rows(PATHS.feedback_dataset_csv))
    should_retrain = bool(retrain_now or feedback_count % RETRAIN_EVERY_N_FEEDBACK == 0)
    retrain_result = None

    if should_retrain:
        merged = _merge_training_rows()
        retrain_result = _train_from_rows(merged, force=True)

    return {
        "feedback_written": True,
        "feedback_rows": feedback_count,
        "retrained": should_retrain,
        "retrain_every_n_feedback": RETRAIN_EVERY_N_FEEDBACK,
        "retrain_result": retrain_result,
    }


def prioritize(
    sentiment_score: str,
    issue_severity_val: str,
    issue_urgency_val: str,
    business_impact_val: str,
    safety_concern: bool,
    is_recurring: bool,
    ticket_type: str,
) -> dict[str, Any]:
    """Model inference with deterministic rule fallback."""
    if PRIORITY_USE_MOCK:
        return {
            "raw_score": 1.0,
            "base_priority": "medium",
            "final_priority": "medium",
            "modifiers_applied": ["mock=enabled"],
            "confidence": 0.0,
            "engine": "mock",
        }

    severity = _normalize_3level(issue_severity_val)
    urgency = _normalize_3level(issue_urgency_val)
    impact = _normalize_choice(business_impact_val, set(IMPACT_LEVELS), "medium")
    sentiment = _normalize_sentiment(sentiment_score)
    ticket = _normalize_choice(ticket_type, set(TICKET_TYPES), "complaint")

    levels = [impact, severity, urgency]
    high_count = sum(1 for lvl in levels if lvl == "high")
    medium_count = sum(1 for lvl in levels if lvl == "medium")

    # Triple-rule base priority.
    if high_count >= 2:
        base_priority = "critical"
    elif high_count == 1:
        base_priority = "medium"
    elif medium_count == 3:
        base_priority = "high"
    elif medium_count == 2:
        base_priority = "medium"
    else:
        base_priority = "low"

    priority_idx = PRIORITY_MAP[base_priority]
    modifiers_applied: list[str] = []

    # Safety is applied first and enforces a minimum of high.
    safety_floor_idx = PRIORITY_MAP["high"] if bool(safety_concern) else PRIORITY_MAP["low"]
    if bool(safety_concern):
        modifiers_applied.append("safety_concern=true(min_high)")
        if priority_idx < safety_floor_idx:
            priority_idx = safety_floor_idx

    # Modifiers after triple rules.
    if bool(is_recurring):
        priority_idx += 1
        modifiers_applied.append("is_recurring=true(+1)")

    if ticket == "inquiry":
        priority_idx -= 1
        modifiers_applied.append("ticket_type=inquiry(-1)")
    else:
        modifiers_applied.append("ticket_type=complaint(0)")

    if sentiment == "negative":
        priority_idx += 1
        modifiers_applied.append("sentiment=negative(+1)")
    elif sentiment == "positive":
        priority_idx -= 1
        modifiers_applied.append("sentiment=positive(-1)")
    else:
        modifiers_applied.append("sentiment=neutral(0)")

    # Clamp to valid range and re-apply safety floor as a hard minimum.
    priority_idx = max(PRIORITY_MAP["low"], min(PRIORITY_MAP["critical"], priority_idx))
    priority_idx = max(priority_idx, safety_floor_idx)
    rule_final_priority = PRIORITY_LEVELS[priority_idx]

    if not _ensure_model_ready() or _model is None:
        modifiers_applied.append("fallback=rule_no_model")
        return {
            "raw_score": float(priority_idx),
            "base_priority": base_priority,
            "final_priority": rule_final_priority,
            "modifiers_applied": modifiers_applied,
            "confidence": 1.0,
            "engine": "rule_based_v2",
        }

    x = np.asarray(
        [
            _encode_row(
                sentiment_score=sentiment,
                issue_severity_val=severity,
                issue_urgency_val=urgency,
                business_impact_val=impact,
                safety_concern=safety_concern,
                is_recurring=is_recurring,
                ticket_type=ticket,
            )
        ],
        dtype=np.float32,
    )
    pred_idx = int(_model.predict(x)[0])
    pred_proba = _model.predict_proba(x)[0].tolist()
    model_priority = PRIORITY_LEVELS[pred_idx]

    return {
        "raw_score": float(pred_idx),
        "base_priority": base_priority,
        "final_priority": model_priority,
        "modifiers_applied": [
            "model=xgboost",
            f"rule_reference_final={rule_final_priority}",
        ],
        "confidence": round(float(max(pred_proba)), 4),
        "engine": "xgboost",
    }
