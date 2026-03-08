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
import time
import uuid
import logging
from typing import Any, Callable, Awaitable

from langchain_core.runnables import RunnableLambda

from db import db_connect

logger = logging.getLogger(__name__)


def _coerce_uuid_or_none(value: Any) -> str | None:
    """
    DB logging tables store ticket_id as UUID.
    Pipeline state currently uses ticket code (e.g., CX-1234), so coerce
    only real UUIDs and store null otherwise to avoid write failures.
    """
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _to_model_execution_agent_name(agent_name: str) -> str:
    """
    model_execution_log.agent_name is enum(agent_name_type):
      sentiment, priority, routing, sla, resolution, feature
    Map pipeline step names into that enum while preserving original names
    in agent_output_log.
    """
    n = (agent_name or "").lower()
    if "priority" in n or "priorit" in n:
        return "priority"
    if "route" in n or "routing" in n:
        return "routing"
    if "feature" in n:
        return "feature"
    if "sentiment" in n or "audioanalysis" in n or "classif" in n:
        return "sentiment"
    return "feature"


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


def _summarize_stage_output(output_state: dict, state_diff: dict) -> dict:
    """
    Build a compact, terminal-friendly output summary for each stage.
    """
    important_keys = (
        "ticket_id",
        "subject",
        "label",
        "class_confidence",
        "text_sentiment",
        "audio_sentiment",
        "sentiment_score",
        "sentiment_score_numeric",
        "is_recurring",
        "safety_concern",
        "issue_severity",
        "issue_urgency",
        "business_impact",
        "priority_label",
        "priority_score",
        "department",
        "status",
        "suggested_resolution",
        "priority_assigned_at",
        "respond_due_at",
        "resolve_due_at",
    )
    changed_keys = sorted(list(state_diff.keys()))
    important = {k: _safe_value(output_state.get(k)) for k in important_keys if k in output_state}
    # Keep log line readable when suggestion text is long.
    if "suggested_resolution" in important and isinstance(important["suggested_resolution"], str):
        important["suggested_resolution"] = important["suggested_resolution"][:180]
    return {
        "changed_keys": changed_keys,
        "important": important,
    }


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
        db_ticket_id = _coerce_uuid_or_none(ticket_id)
        mel_agent_name = _to_model_execution_agent_name(agent_name)
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO model_execution_log
                        (execution_id, ticket_id, agent_name_old, agent_name, inference_time_ms,
                         confidence_score, error_flag, error_message, started_at, completed_at, status, infra_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), now(), %s, '{}'::jsonb)
                    """,
                    (
                        execution_id,
                        db_ticket_id,
                        agent_name,
                        mel_agent_name,
                        inference_time_ms,
                        confidence_score,
                        error_flag,
                        error_message,
                        "failed" if error_flag else "success",
                    ),
                )
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
                        db_ticket_id,
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

        logger.info(
            "STAGE_START | execution_id=%s step=%d agent=%s ticket_id=%s",
            execution_id,
            step_order,
            agent_name,
            ticket_id,
        )

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
            logger.error(
                "STAGE_ERROR | execution_id=%s step=%d agent=%s ticket_id=%s error=%s",
                execution_id,
                step_order,
                agent_name,
                ticket_id,
                error_msg,
            )
            raise

        elapsed_ms = int((time.monotonic() - start) * 1000)
        output_snapshot = {k: v for k, v in copy.deepcopy(result).items() if not k.startswith("_")}
        state_diff = _compute_diff(input_snapshot, output_snapshot)
        confidence = _extract_confidence(result)
        stage_summary = _summarize_stage_output(output_snapshot, state_diff)

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
        logger.info(
            "STAGE_OUTPUT | execution_id=%s step=%d agent=%s ticket_id=%s time_ms=%d summary=%s",
            execution_id,
            step_order,
            agent_name,
            result.get("ticket_id"),
            elapsed_ms,
            json.dumps(_safe_json(stage_summary), ensure_ascii=False),
        )
        return result

    wrapper.__name__ = f"logged_{step_fn.__name__}"
    wrapper.__qualname__ = f"logged_{step_fn.__qualname__}"
    return RunnableLambda(wrapper)
