"""
Execution Logger — wraps pipeline steps with JSON logging to PostgreSQL.

Usage in pipeline.py:
    from execution_logger import logged_step
    pipeline = (
        logged_step("ClassificationAgent", classify, 1)
        | logged_step("SentimentAgent", analyze_sentiment, 2)
        | ...
    )

Each wrapped step:
  1. Snapshots the input state (deep copy)
  2. Runs the agent function and measures wall-clock time
  3. Snapshots the output state
  4. Computes a diff (keys added or changed)
  5. Writes to model_execution_log and agent_output_log
  6. On error: logs with error_flag=True, then re-raises

Logging failures never crash the pipeline.
"""

import copy
import json
import math
import os
import time
import uuid
import logging
from typing import Any, Callable, Awaitable

from langchain_core.runnables import RunnableLambda

from db import db_connect

logger = logging.getLogger(__name__)


def _compute_diff(before: dict, after: dict) -> dict:
    """Compute keys added or changed between two state dicts."""
    diff = {}
    for key in after:
        if key not in before:
            diff[key] = {"action": "added", "value": _safe_value(after[key])}
        else:
            try:
                equal = before[key] == after[key]
                # Handle numpy arrays where == returns an array instead of bool
                if hasattr(equal, "__iter__") and not isinstance(equal, str):
                    equal = all(equal)
            except (ValueError, TypeError):
                equal = False
            if not equal:
                diff[key] = {
                    "action": "changed",
                    "old": _safe_value(before[key]),
                    "new": _safe_value(after[key]),
                }
    return diff


def _safe_value(obj: Any) -> Any:
    """Convert a single value to something JSON-safe."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        # Replace NaN/Infinity with None (null in JSON) to avoid JSONB rejection
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_value(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _safe_value(v) for k, v in obj.items()}
    # numpy scalars, UUIDs, datetimes, etc.
    return str(obj)


def _safe_json(obj: Any) -> Any:
    """Make an entire dict JSON-serializable (handles numpy, UUID, datetime, NaN, etc.)."""
    try:
        # allow_nan=False forces NaN/Infinity to raise ValueError so we catch them
        return json.loads(json.dumps(obj, default=str, allow_nan=False))
    except (TypeError, ValueError):
        # Fallback: convert with _safe_value which stringifies non-serializable types
        try:
            cleaned = _safe_value(obj)
            return json.loads(json.dumps(cleaned, allow_nan=False))
        except (TypeError, ValueError):
            return {"_serialization_error": str(obj)[:500]}


def _extract_confidence(state: dict) -> float | None:
    """Extract the most relevant confidence score from the output state."""
    for key in ("class_confidence", "model_confidence", "classification_confidence", "confidence_score"):
        val = state.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None


def _extract_agent_confidence(agent_name: str, state: dict) -> float | None:
    """
    Agent-specific confidence extraction to avoid cross-step leakage
    (e.g. classification confidence being reused for sentiment/feature steps).
    """
    agent = (agent_name or "").strip().lower()

    candidates_by_agent = {
        "classificationagent": ("class_confidence", "classification_confidence", "confidence_score"),
        "sentimentagent": ("sentiment_confidence", "confidence_score"),
        "featureengineeringagent": ("feature_confidence", "confidence_score"),
        "prioritizationagent": ("model_confidence", "confidence_score"),
        "departmentroutingagent": ("routing_confidence", "confidence_score"),
        "audioanalysisagent": ("audio_confidence", "confidence_score"),
    }
    keys = candidates_by_agent.get(agent, ("confidence_score", "model_confidence"))
    for key in keys:
        val = state.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _normalize_sentiment_label(label: Any, score: float) -> str:
    raw = str(label or "").strip().lower()
    mapping = {
        "positive": "Positive",
        "very_positive": "Positive",
        "neutral": "Neutral",
        "negative": "Negative",
        "very_negative": "Very Negative",
    }
    if raw in mapping:
        return mapping[raw]
    if score < -0.6:
        return "Very Negative"
    if score < -0.2:
        return "Negative"
    if score < 0.2:
        return "Neutral"
    return "Positive"


def _insert_agent_outputs(
    cur,
    *,
    mel_id: str,
    ticket_id: str | None,
    agent_name: str,
    output_state: dict,
    confidence_score: float | None,
) -> None:
    """
    Persist agent-specific outputs needed by analytics MVs.
    Safe no-op when ticket_id is missing.
    """
    if not ticket_id:
        return

    agent = (agent_name or "").strip().lower()

    if agent == "sentimentagent":
        score = float(output_state.get("text_sentiment", 0.0) or 0.0)
        label = _normalize_sentiment_label(output_state.get("sentiment_category"), score)
        # Fallback confidence when model does not provide one.
        conf = confidence_score if confidence_score is not None else _clamp01(abs(score) + 0.35)
        cur.execute(
            """
            INSERT INTO sentiment_outputs (
                execution_id, ticket_id, model_version,
                sentiment_label, sentiment_score, confidence_score,
                emotion_tags, raw_scores, is_current
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, TRUE)
            """,
            (
                mel_id,
                ticket_id,
                os.getenv("SENTIMENT_MODEL_VERSION", "sentiment-v1.0"),
                label,
                score,
                conf,
                [],
                json.dumps({"text_sentiment": score}),
            ),
        )
        return

    if agent == "featureengineeringagent":
        raw_features = {
            "business_impact": str(output_state.get("business_impact") or "").capitalize() or "Medium",
            "safety_concern": bool(output_state.get("safety_concern", False)),
            "issue_severity": str(output_state.get("issue_severity") or "").capitalize() or "Medium",
            "issue_urgency": str(output_state.get("issue_urgency") or "").capitalize() or "Medium",
            "is_recurring": bool(output_state.get("is_recurring", False)),
            "source": output_state.get("feature_labels_source"),
        }
        source = str(output_state.get("feature_labels_source") or "").lower()
        inferred_conf = 0.8 if source == "nli" else 0.55
        conf = confidence_score if confidence_score is not None else inferred_conf
        cur.execute(
            """
            INSERT INTO feature_outputs (
                execution_id, ticket_id, model_version,
                asset_category, topic_labels, confidence_score,
                raw_features, is_current
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, TRUE)
            """,
            (
                mel_id,
                ticket_id,
                os.getenv("FEATURE_MODEL_VERSION", "feature-v1.0"),
                str(output_state.get("asset_type") or "General"),
                list(output_state.get("keywords") or []),
                conf,
                json.dumps(raw_features),
            ),
        )
        return


def _write_logs(
    execution_id: str,
    ticket_id: str | None,
    agent_name: str,
    step_order: int,
    input_state: dict,
    output_state: dict,
    state_diff: dict,
    inference_time_ms: int,
    confidence_score: float | None,
    error_flag: bool,
    error_message: str | None,
) -> None:
    """Write to both model_execution_log and agent_output_log. Never raises."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO model_execution_log
                        (execution_id, ticket_id, agent_name, inference_time_ms,
                         confidence_score, error_flag, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        execution_id,
                        ticket_id,
                        agent_name,
                        inference_time_ms,
                        confidence_score,
                        error_flag,
                        error_message,
                    ),
                )
                mel_id_row = cur.fetchone()
                mel_id = str(mel_id_row[0]) if mel_id_row and mel_id_row[0] else None
                cur.execute(
                    """
                    INSERT INTO agent_output_log
                        (execution_id, ticket_id, agent_name, step_order,
                         input_state, output_state, state_diff,
                         inference_time_ms, error_flag, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        execution_id,
                        ticket_id,
                        agent_name,
                        step_order,
                        json.dumps(_safe_json(input_state)),
                        json.dumps(_safe_json(output_state)),
                        json.dumps(_safe_json(state_diff)),
                        inference_time_ms,
                        error_flag,
                        error_message,
                    ),
                )
                # Persist analytics source tables from real pipeline outputs.
                if mel_id and not error_flag:
                    _insert_agent_outputs(
                        cur,
                        mel_id=mel_id,
                        ticket_id=ticket_id,
                        agent_name=agent_name,
                        output_state=output_state,
                        confidence_score=confidence_score,
                    )
    except Exception as exc:
        logger.error("execution_log | write failed agent=%s err=%s", agent_name, exc)


def logged_step(
    agent_name: str,
    step_fn: Callable[[dict], Awaitable[dict]],
    step_order: int,
) -> RunnableLambda:
    """
    Wrap an async agent step function with execution logging.
    Returns a RunnableLambda suitable for use in a LangChain pipeline.
    """

    async def wrapper(state: dict) -> dict:
        execution_id = state.get("_execution_id", str(uuid.uuid4()))
        ticket_id = state.get("ticket_id")

        # Strip internal keys from the snapshot we log (keep state clean)
        input_snapshot = {k: v for k, v in copy.deepcopy(state).items() if not k.startswith("_")}

        start = time.monotonic()

        try:
            result = await step_fn(state)
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            error_msg = f"{type(exc).__name__}: {exc}"
            _write_logs(
                execution_id=execution_id,
                ticket_id=ticket_id,
                agent_name=agent_name,
                step_order=step_order,
                input_state=input_snapshot,
                output_state=input_snapshot,
                state_diff={},
                inference_time_ms=elapsed_ms,
                confidence_score=None,
                error_flag=True,
                error_message=error_msg,
            )
            raise

        elapsed_ms = int((time.monotonic() - start) * 1000)
        output_snapshot = {k: v for k, v in copy.deepcopy(result).items() if not k.startswith("_")}
        state_diff = _compute_diff(input_snapshot, output_snapshot)
        confidence = _extract_agent_confidence(agent_name, result)

        _write_logs(
            execution_id=execution_id,
            ticket_id=ticket_id,
            agent_name=agent_name,
            step_order=step_order,
            input_state=input_snapshot,
            output_state=output_snapshot,
            state_diff=state_diff,
            inference_time_ms=elapsed_ms,
            confidence_score=confidence,
            error_flag=False,
            error_message=None,
        )

        logger.info(
            "execution_log | agent=%s step=%d time_ms=%d confidence=%s error=%s",
            agent_name,
            step_order,
            elapsed_ms,
            f"{confidence:.4f}" if confidence is not None else "n/a",
            False,
        )

        return result

    wrapper.__name__ = f"logged_{step_fn.__name__}"
    wrapper.__qualname__ = f"logged_{step_fn.__qualname__}"
    return RunnableLambda(wrapper)
