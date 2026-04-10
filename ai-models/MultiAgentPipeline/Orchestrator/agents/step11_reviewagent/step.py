"""
Step 11 — Review Agent
======================
Automated quality gate. Runs stage-by-stage through every critical pipeline
output and decides per-stage: success | fixed | flagged.

Stage review order:
  1. ClassificationAgent  — label validity / mock re-classification
  2. FeatureEngineeringAgent — feature validity / Qwen consistency review / mock re-extraction
  3. PrioritizationAgent  — deterministic priority re-run / light mismatch check from human corrections
  4. DepartmentRoutingAgent — routing mock re-run / confidence check / LLM second-opinion
  Non-critical: SentimentAgent, AudioAnalysisAgent, SentimentCombinerAgent — logged only

For each stage:
  - If success:          pass through
  - If fixable:          Qwen corrects in-place, continue
  - If unfixable:        flagged → held_operator_review

If a service was down (mock fallback detected):
  - Review Agent attempts to re-run that stage itself via Qwen
  - If re-run succeeds → fixed, continue
  - If re-run fails     → flagged, operator notified

Learning tables used by the review agent:
  - reroute_reference  → routing validation prompt (manager/operator correction examples)
  - rescore_reference  → light advisory check after deterministic priority verification
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
REVIEW_AGENT_TIMEOUT_SECONDS = 45.0
REVIEW_AGENT_CLASSIFICATION_TIMEOUT_SECONDS = 15.0
REVIEW_AGENT_FEATURE_TIMEOUT_SECONDS = 20.0
REVIEW_AGENT_ROUTING_TIMEOUT_SECONDS = 15.0
ROUTING_CONFIDENCE_THRESHOLD = 0.50
CLASSIFICATION_REVIEW_CONFIDENCE_THRESHOLD = 0.80

logger = logging.getLogger(__name__)

DEPARTMENT_LABELS = [
    "Facilities Management",
    "Legal & Compliance",
    "Safety & Security",
    "HR",
    "Leasing",
    "Maintenance",
    "IT",
]
_DEPARTMENT_LIST = "\n".join(f"{i}. {d}" for i, d in enumerate(DEPARTMENT_LABELS, start=1))

_VALID_LABELS     = {"complaint", "inquiry"}
_VALID_LEVELS     = {"low", "medium", "high"}
_VALID_PRIORITIES = {"low", "medium", "high", "critical"}

# ---------------------------------------------------------------------------
# Mock stage detection
# ---------------------------------------------------------------------------

_MOCK_INDICATOR_KEYS: dict[str, str] = {
    "recurrence_mode":           "heuristic_fallback",
    "classification_source":     "mock_fallback",
    "sentiment_mode":            "mock_fallback",
    "audio_analysis_mode":       "mock_fallback",
    "sentiment_combiner_mode":   "mock_fallback",
    "feature_labeler_mode":      "mock_fallback",
    "priority_mode":             "mock_fallback",
    "department_routing_source": "mock_fallback",
}
_INDICATOR_TO_STAGE: dict[str, str] = {
    "recurrence_mode":           "RecurrenceAgent",
    "classification_source":     "ClassificationAgent",
    "sentiment_mode":            "SentimentAgent",
    "audio_analysis_mode":       "AudioAnalysisAgent",
    "sentiment_combiner_mode":   "SentimentCombinerAgent",
    "feature_labeler_mode":      "FeatureEngineeringAgent",
    "priority_mode":             "PrioritizationAgent",
    "department_routing_source": "DepartmentRoutingAgent",
}
_NON_CRITICAL_INDICATOR_KEYS = {
    "recurrence_mode", "sentiment_mode", "audio_analysis_mode", "sentiment_combiner_mode"
}
_SUPPORTED_REVIEW_STAGES = {
    "ClassificationAgent",
    "FeatureEngineeringAgent",
    "PrioritizationAgent",
    "DepartmentRoutingAgent",
}


def _detect_mock_stages(state: dict) -> list[str]:
    detected: list[str] = []
    if state.get("_mock_fallback_stage"):
        name = str(state["_mock_fallback_stage"])
        if name:
            detected.append(name)
    for key, mock_val in _MOCK_INDICATOR_KEYS.items():
        stage = _INDICATOR_TO_STAGE[key]
        if str(state.get(key, "")).lower() == mock_val and stage not in detected:
            detected.append(stage)
    return detected


def _noncritical_mock_warnings(state: dict) -> list[str]:
    return [
        _INDICATOR_TO_STAGE[k]
        for k in _NON_CRITICAL_INDICATOR_KEYS
        if str(state.get(k, "")).lower() == _MOCK_INDICATOR_KEYS[k]
    ]


def _unsupported_critical_mock_results(mock_stages: list[str]) -> list[dict[str, Any]]:
    unsupported = [
        stage for stage in mock_stages
        if stage not in _SUPPORTED_REVIEW_STAGES and stage != "ReviewAgent"
    ]
    results: list[dict[str, Any]] = []
    for stage in unsupported:
        results.append({
            "stage": stage,
            "was_mock": True,
            "status": "flagged",
            "issue": f"{stage} used fallback output and cannot be auto-corrected by Review Agent",
            "fix_applied": None,
            "operator_message": (
                f"{stage} failed earlier in the pipeline. Review Agent cannot safely auto-correct this stage, "
                "so manual operator review is required."
            ),
            "operator_override_required": False,
        })
    return results


# ---------------------------------------------------------------------------
# Shared model access
# ---------------------------------------------------------------------------

def _get_model() -> dict[str, Any] | None:
    try:
        from shared_model_service import get_shared_qwen
        return get_shared_qwen()
    except Exception as exc:
        logger.warning("review_agent | shared model service unavailable (%s)", exc)
        return None


# ---------------------------------------------------------------------------
# Qwen inference helper
# ---------------------------------------------------------------------------

def _qwen_generate(prompt: str, system: str, max_new_tokens: int = 80) -> str:
    """Synchronous Qwen generation. Returns empty string on any failure."""
    loaded = _get_model()
    if loaded is None:
        return ""
    try:
        import torch  # type: ignore
        tokenizer = loaded["tokenizer"]
        model     = loaded["model"]
        device    = loaded["device"]
        messages  = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if hasattr(tokenizer, "apply_chat_template"):
            rendered = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = tokenizer([rendered], return_tensors="pt", truncation=True).to(device)
        else:
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                no_repeat_ngram_size=3,
                repetition_penalty=1.1,
                use_cache=torch.cuda.is_available(),
            )
        prompt_len = inputs["input_ids"].shape[1]
        generated  = (
            output_ids[0][prompt_len:]
            if output_ids.shape[1] > prompt_len
            else output_ids[0]
        )
        return tokenizer.decode(generated, skip_special_tokens=True).strip()
    except Exception as exc:
        logger.warning("review_agent | qwen inference failed (%s)", exc)
        return ""


def _extract_json_array(text: str) -> list[dict]:
    if not text:
        return []
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    return []


def _extract_json_object(text: str) -> dict:
    if not text:
        return {}
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return {}


def _ensure_review_agent_schema() -> None:
    try:
        from db import db_connect
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'Review'")
                cur.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'review_agent_held'")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS review_agent_decisions (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        ticket_id UUID REFERENCES tickets(id) ON DELETE CASCADE,
                        ticket_code TEXT,
                        execution_id UUID,
                        verdict TEXT NOT NULL,
                        verdict_reason TEXT,
                        consistency_passed BOOLEAN NOT NULL DEFAULT TRUE,
                        consistency_issues JSONB NOT NULL DEFAULT '[]',
                        priority_rerun BOOLEAN NOT NULL DEFAULT FALSE,
                        priority_before TEXT,
                        priority_after TEXT,
                        priority_score_before INT,
                        priority_score_after INT,
                        routing_confidence NUMERIC(6,4),
                        routing_threshold NUMERIC(6,4),
                        routing_above_threshold BOOLEAN,
                        original_department TEXT,
                        final_department TEXT,
                        routing_overridden BOOLEAN NOT NULL DEFAULT FALSE,
                        routing_sent_to_review BOOLEAN NOT NULL DEFAULT FALSE,
                        mock_stages_detected JSONB NOT NULL DEFAULT '[]',
                        mock_overrideable BOOLEAN,
                        llm_model TEXT,
                        llm_inference_time_ms INT,
                        pipeline_state_snapshot JSONB NOT NULL DEFAULT '{}',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rad_ticket_id ON review_agent_decisions(ticket_id)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rad_ticket_code ON review_agent_decisions(ticket_code)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rad_verdict ON review_agent_decisions(verdict, created_at DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_rad_created_at ON review_agent_decisions(created_at DESC)")
    except Exception as exc:
        logger.warning("review_agent | schema ensure failed (%s)", exc)


# ---------------------------------------------------------------------------
# Learning table access
# ---------------------------------------------------------------------------

def _fetch_routing_reference(predicted_dept: str) -> list[dict]:
    """Recent routing corrections for predicted_dept (last 3 months)."""
    try:
        from db import db_connect
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT original_dept, corrected_dept, actor_role, source_type, created_at
                    FROM reroute_reference
                    WHERE (original_dept = %s OR corrected_dept = %s)
                      AND created_at >= now() - INTERVAL '3 months'
                    ORDER BY created_at DESC
                    LIMIT 10
                    """,
                    (predicted_dept, predicted_dept),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


def _fetch_rescore_reference(department: str) -> list[dict]:
    """Recent priority corrections for department (last 3 months)."""
    try:
        from db import db_connect
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT original_priority, corrected_priority, actor_role, source_type, created_at
                    FROM rescore_reference
                    WHERE department = %s
                      AND created_at >= now() - INTERVAL '3 months'
                    ORDER BY created_at DESC
                    LIMIT 10
                    """,
                    (department,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception:
        return []


_SOURCE_LABELS = {
    "manager": "manager",
    "operator": "operator",
    "employee": "employee",
    "unknown": "unknown source",
}


def _format_correction_hint(
    records: list[dict],
    original_key: str,
    corrected_key: str,
    header: str,
) -> str:
    """Format correction patterns as a prompt hint, grouped by source."""
    if not records:
        return ""
    patterns: dict[tuple[str, str], int] = {}
    source_counts: dict[str, int] = {}
    for r in records:
        orig = str(r.get(original_key) or "?")
        corr = str(r.get(corrected_key) or "?")
        patterns[(orig, corr)] = patterns.get((orig, corr), 0) + 1
        actor_role = str(r.get("actor_role") or "").strip().lower()
        source = actor_role or str(r.get("source_type") or "unknown").strip() or "unknown"
        source_counts[source] = source_counts.get(source, 0) + 1
    lines = [
        f'  - "{orig}" → "{corr}" ({n} case{"s" if n > 1 else ""})'
        for (orig, corr), n in sorted(patterns.items(), key=lambda x: -x[1])
    ]
    source_lines = [
        f"  - {_SOURCE_LABELS.get(src, src.replace('_', ' '))}: {count} case{'s' if count > 1 else ''}"
        for src, count in sorted(source_counts.items(), key=lambda x: (-x[1], x[0]))
    ]
    return header + "\n".join(lines) + "\nSources:\n" + "\n".join(source_lines)


def _format_reroute_hint(records: list[dict]) -> str:
    return _format_correction_hint(
        records,
        original_key="original_dept",
        corrected_key="corrected_dept",
        header="Recent routing corrections for this department (last 3 months):\n",
    )


def _format_rescore_hint(records: list[dict]) -> str:
    return _format_correction_hint(
        records,
        original_key="original_priority",
        corrected_key="corrected_priority",
        header="Recent priority corrections for this department (last 3 months):\n",
    )


def _light_rescore_mismatch(records: list[dict], current_priority: str) -> dict[str, Any] | None:
    """
    Treat human correction history as a light warning signal only.
    Returns a suggested mismatch pattern when recent corrections strongly cluster
    away from the current priority, but does not auto-change the priority.
    """
    current = str(current_priority or "").strip().lower()
    if current not in _VALID_PRIORITIES:
        return None

    corrections: dict[str, int] = {}
    total = 0
    for r in records:
        original = str(r.get("original_priority") or "").strip().lower()
        corrected = str(r.get("corrected_priority") or "").strip().lower()
        if original != current or corrected not in _VALID_PRIORITIES or corrected == current:
            continue
        corrections[corrected] = corrections.get(corrected, 0) + 1
        total += 1

    if not corrections:
        return None

    suggested, count = max(corrections.items(), key=lambda item: item[1])
    if count < 2 or (count / max(total, 1)) < 0.6:
        return None

    return {
        "suggested": suggested,
        "count": count,
        "total": total,
    }


# ---------------------------------------------------------------------------
# Shared feature-engineering rubric
# ---------------------------------------------------------------------------

def _feature_engineering_rubric_hint() -> str:
    try:
        from agents.step08_featureengineering.step import LABEL_CONFIGS
    except Exception:
        return ""

    lines: list[str] = []
    ordered_fields = ("issue_severity", "issue_urgency", "business_impact", "safety_concern")
    for field in ordered_fields:
        configs = LABEL_CONFIGS.get(field) or {}
        field_lines: list[str] = []
        for label, examples in configs.items():
            example_text = "; ".join(str(ex).strip() for ex in examples[:2] if str(ex).strip())
            field_lines.append(f"  - {label}: {example_text}")
        if field_lines:
            lines.append(f"{field} guidance:\n" + "\n".join(field_lines))
    return "\n\n".join(lines)


def _normalized_feature_values(values: dict[str, Any]) -> dict[str, Any] | None:
    severity = str(values.get("issue_severity") or "").strip().lower()
    urgency = str(values.get("issue_urgency") or "").strip().lower()
    impact = str(values.get("business_impact") or "").strip().lower()
    safety = values.get("safety_concern")
    if (
        severity not in _VALID_LEVELS
        or urgency not in _VALID_LEVELS
        or impact not in _VALID_LEVELS
        or safety is None
    ):
        return None
    normalized_safety = (
        safety if isinstance(safety, bool) else str(safety).lower() in {"true", "1", "yes"}
    )
    return {
        "issue_severity": severity,
        "issue_urgency": urgency,
        "business_impact": impact,
        "safety_concern": normalized_safety,
    }


def _apply_feature_values(state: dict, values: dict[str, Any]) -> list[str]:
    modified: list[str] = []
    for field, new_value in values.items():
        if state.get(field) != new_value:
            state[field] = new_value
            modified.append(field)
    return modified


def _current_feature_values(state: dict) -> dict[str, Any] | None:
    return _normalized_feature_values(
        {
            "issue_severity": state.get("issue_severity"),
            "issue_urgency": state.get("issue_urgency"),
            "business_impact": state.get("business_impact"),
            "safety_concern": state.get("safety_concern"),
        }
    )


def _should_double_check_feature_values(values: dict[str, Any] | None) -> bool:
    if not values:
        return False
    high_count = sum(
        1 for field in ("issue_severity", "issue_urgency", "business_impact")
        if str(values.get(field) or "").strip().lower() == "high"
    )
    return bool(values.get("safety_concern")) or high_count >= 2


# ---------------------------------------------------------------------------
# Stage 1 — Classification review
# ---------------------------------------------------------------------------

_CLASSIFICATION_SYSTEM = (
    "You classify support tickets. "
    "Complaint means the ticket reports a problem, failure, disruption, dissatisfaction, or request for corrective action. "
    "Inquiry means the ticket mainly asks for information, clarification, guidance, status, or a non-problem request. "
    "Reply with exactly one word: complaint or inquiry. No explanation."
)
_CLASSIFICATION_REVIEW_SYSTEM = (
    "You review whether a support ticket classification is correct. "
    'Reply with JSON only: {"correct": true/false, "suggested": "complaint|inquiry"}'
)


async def _review_classification(state: dict) -> dict:
    """
    Checks label validity and classification source.
    Qwen always reviews whether the current label makes sense.
    If mock, invalid, or Qwen disagrees, the label is corrected when possible.
    """
    result: dict[str, Any] = {
        "stage": "ClassificationAgent", "was_mock": False,
        "status": "success", "issue": None, "fix_applied": None, "operator_message": None,
        "operator_override_required": False,
    }
    label  = str(state.get("label") or "").strip().lower()
    source = str(state.get("classification_source") or "").lower()
    is_mock = (source == "mock_fallback")
    result["was_mock"] = is_mock

    subject = str(state.get("subject") or "").strip()
    text    = str(state.get("text") or "")[:700]
    prompt = (
        f"Ticket subject: {subject or 'N/A'}\n"
        f"Ticket text: {text}\n"
        "Classify this support ticket as complaint or inquiry:"
    )

    if label not in _VALID_LABELS or is_mock:
        issue = (
            "ClassificationAgent service was down — used mock fallback"
            if is_mock
            else f"Invalid label '{label}' from ClassificationAgent"
        )
        result["issue"] = issue
        logger.info("review_agent | classification issue: %s", issue)
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_qwen_generate, prompt, _CLASSIFICATION_SYSTEM, 5),
                timeout=REVIEW_AGENT_CLASSIFICATION_TIMEOUT_SECONDS,
            )
            new_label = (response.strip().lower().split()[0] if response.strip() else "")
            if new_label in _VALID_LABELS:
                state["label"] = new_label
                state["classification_source"] = "review_agent_reclassified"
                result["status"] = "fixed"
                result["fix_applied"] = f"reclassified as '{new_label}'"
                logger.info("review_agent | classification fixed → %s", new_label)
                return result
        except asyncio.TimeoutError:
            logger.warning("review_agent | classification Qwen timed out")

        result["status"] = "flagged"
        result["operator_message"] = f"{issue}. Manual classification required."
        return result

    class_confidence = float(state.get("class_confidence") or 0.0)
    if class_confidence >= CLASSIFICATION_REVIEW_CONFIDENCE_THRESHOLD:
        logger.info(
            "review_agent | classification accepted without Qwen review: label=%s confidence=%.2f",
            label,
            class_confidence,
        )
        return result

    review_prompt = (
        f"Ticket subject: {subject or 'N/A'}\n"
        f"Ticket text: {text}\n"
        f"Assigned label: {label}\n"
        "Does this label make sense? Reply JSON only:"
    )
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_qwen_generate, review_prompt, _CLASSIFICATION_REVIEW_SYSTEM, 40),
            timeout=REVIEW_AGENT_CLASSIFICATION_TIMEOUT_SECONDS,
        )
        parsed = _extract_json_object(response)
        correct = bool(parsed.get("correct", True))
        suggested = str(parsed.get("suggested") or "").strip().lower()
        if not correct:
            if suggested in _VALID_LABELS and suggested != label:
                state["label"] = suggested
                state["classification_source"] = "review_agent_reclassified"
                result["status"] = "fixed"
                result["issue"] = f"Qwen disagreed with classifier label '{label}'"
                result["operator_override_required"] = True
                result["operator_message"] = (
                    f"Review Agent changed classification from '{label}' to '{suggested}'."
                )
                result["fix_applied"] = f"reclassified as '{suggested}'"
                logger.info("review_agent | classification corrected via Qwen: %s → %s", label, suggested)
                return result

            result["status"] = "flagged"
            result["issue"] = f"Classifier label '{label}' failed Qwen review"
            result["operator_message"] = (
                f"Classification '{label}' did not make sense to Review Agent and no valid corrected label was returned."
            )
            # Tie-break with direct classification before flagging an obvious ticket.
            try:
                retry_response = await asyncio.wait_for(
                    asyncio.to_thread(_qwen_generate, prompt, _CLASSIFICATION_SYSTEM, 5),
                    timeout=REVIEW_AGENT_CLASSIFICATION_TIMEOUT_SECONDS,
                )
                retry_label = (retry_response.strip().lower().split()[0] if retry_response.strip() else "")
                if retry_label == label:
                    result["status"] = "success"
                    result["issue"] = None
                    result["operator_message"] = None
                    logger.info(
                        "review_agent | classification tie-break confirmed original label: %s",
                        label,
                    )
                    return result
                if retry_label in _VALID_LABELS and retry_label != label:
                    state["label"] = retry_label
                    state["classification_source"] = "review_agent_reclassified"
                    result["status"] = "fixed"
                    result["issue"] = f"Qwen review was inconclusive for '{label}'"
                    result["operator_override_required"] = True
                    result["operator_message"] = (
                        f"Review Agent changed classification from '{label}' to '{retry_label}' after tie-break review."
                    )
                    result["fix_applied"] = f"reclassified as '{retry_label}'"
                    return result
            except asyncio.TimeoutError:
                logger.warning("review_agent | classification tie-break Qwen timed out")
            return result
    except asyncio.TimeoutError:
        logger.warning("review_agent | classification validation Qwen timed out")
        result["operator_override_required"] = True
        result["issue"] = "Classification review timed out"
        result["operator_message"] = (
            f"Review Agent could not validate classification '{label}' in time. Operator verification recommended."
        )
        return result

    return result


# ---------------------------------------------------------------------------
# Stage 2 — Feature Engineering review
# ---------------------------------------------------------------------------

_FEATURE_SYSTEM = (
    "You extract ticket features for facilities/support tickets.\n"
    "Use these meanings when choosing values:\n"
    "- issue_severity: low = minor/cosmetic inconvenience; medium = meaningful but partial disruption; high = severe failure, unusable service, or unsafe condition.\n"
    "- issue_urgency: low = can wait for scheduled handling; medium = should be resolved soon; high = immediate, same-day, or emergency response needed.\n"
    "- business_impact: low = negligible operational impact; medium = noticeable productivity or workflow disruption; high = operations blocked, major disruption, or financial/client impact.\n"
    "- safety_concern: true only when there is physical danger, injury risk, hazardous conditions, fire, flood, electrical risk, or similar safety exposure.\n"
    "Reply with JSON only:\n"
    '{"issue_severity":"low|medium|high","issue_urgency":"low|medium|high",'
    '"business_impact":"low|medium|high","safety_concern":true|false}'
)
_FEATURE_REVIEW_SYSTEM = (
    "You review extracted ticket features for consistency with the ticket text. "
    "Use these meanings when judging values:\n"
    "- issue_severity: low = minor/cosmetic inconvenience; medium = meaningful but partial disruption; high = severe failure, unusable service, or unsafe condition.\n"
    "- issue_urgency: low = can wait for scheduled handling; medium = should be resolved soon; high = immediate, same-day, or emergency response needed.\n"
    "- business_impact: low = negligible operational impact; medium = noticeable productivity or workflow disruption; high = operations blocked, major disruption, or financial/client impact.\n"
    "- safety_concern: true only when there is physical danger, injury risk, hazardous conditions, fire, flood, electrical risk, or similar safety exposure.\n"
    "Reply with JSON only: "
    '{"correct": true/false, "issue_severity":"low|medium|high", '
    '"issue_urgency":"low|medium|high", "business_impact":"low|medium|high", '
    '"safety_concern": true|false, "reason":"one sentence"}'
)


async def _review_features(state: dict) -> tuple[dict, bool]:
    """
    Checks issue_severity, issue_urgency, business_impact, safety_concern.
    If mock or fields missing/invalid: attempts Qwen re-extraction.
    Then asks Qwen to validate/correct the extracted feature set.
    Returns (stage_result, features_changed).
    """
    result: dict[str, Any] = {
        "stage": "FeatureEngineeringAgent", "was_mock": False,
        "status": "success", "issue": None, "fix_applied": None, "operator_message": None,
        "operator_override_required": False,
    }
    mode    = str(state.get("feature_labeler_mode") or "").lower()
    is_mock = (mode == "mock_fallback")
    result["was_mock"] = is_mock

    severity = str(state.get("issue_severity") or "").strip().lower()
    urgency  = str(state.get("issue_urgency") or "").strip().lower()
    impact   = str(state.get("business_impact") or "").strip().lower()
    safety   = state.get("safety_concern")

    fields_valid = (
        severity in _VALID_LEVELS
        and urgency in _VALID_LEVELS
        and impact in _VALID_LEVELS
        and safety is not None
    )
    features_changed = False
    subject = str(state.get("subject") or "").strip()
    text = str(state.get("text") or "")[:700]
    label = str(state.get("label") or "unknown")
    rubric_hint = _feature_engineering_rubric_hint()

    extraction_prompt = (
        f"Ticket subject: {subject or 'N/A'}\n"
        f"Ticket text: {text}\n"
        f"Ticket type: {label}\n"
    )
    if rubric_hint:
        extraction_prompt += (
            f"\nUse the same feature-engineering rubric below when inferring values:\n{rubric_hint}\n"
        )
    extraction_prompt += "Extract the features as JSON:"

    if not fields_valid or is_mock:
        issue = (
            "FeatureEngineeringAgent service was down — used mock fallback"
            if is_mock
            else f"Missing/invalid feature fields: severity='{severity}' urgency='{urgency}' impact='{impact}' safety_concern={safety}"
        )
        result["issue"] = issue
        logger.info("review_agent | features issue: %s", issue)

        # Attempt Qwen re-extraction
        fixed = False
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_qwen_generate, extraction_prompt, _FEATURE_SYSTEM, 60),
                timeout=REVIEW_AGENT_FEATURE_TIMEOUT_SECONDS,
            )
            normalized = _normalized_feature_values(_extract_json_object(response))

            if normalized is not None:
                modified = _apply_feature_values(state, normalized)
                state["feature_labeler_mode"] = "review_agent_reextracted"
                fixed            = True
                features_changed = bool(modified)
                result["status"]      = "fixed"
                result["fix_applied"] = (
                    f"re-extracted: severity={state.get('issue_severity')}, urgency={state.get('issue_urgency')}, "
                    f"impact={state.get('business_impact')}, safety_concern={state.get('safety_concern')}"
                )
                logger.info("review_agent | features re-extracted: %s", result["fix_applied"])
        except asyncio.TimeoutError:
            logger.warning("review_agent | feature extraction Qwen timed out")

        if not fixed:
            result["status"]           = "flagged"
            result["operator_message"] = (
                f"{issue}. Cannot compute valid priority without feature fields."
            )
            return result, False

    current_values = _current_feature_values(state)
    if current_values is None:
        result["status"] = "flagged"
        result["issue"] = "Feature values are still incomplete after review preparation"
        result["operator_message"] = "Cannot review priority or routing because the feature fields are incomplete."
        return result, features_changed

    if not is_mock and fields_valid and not _should_double_check_feature_values(current_values):
        logger.info("review_agent | features accepted without Qwen review")
        return result, features_changed

    # Qwen consistency review on confirmed feature values
    review_prompt = (
        f"Ticket subject: {subject or 'N/A'}\n"
        f"Ticket text: {text}\n"
        f"Ticket type: {state.get('label', 'unknown')}\n"
        f"Current features: severity={state.get('issue_severity')}, "
        f"urgency={state.get('issue_urgency')}, "
        f"business_impact={state.get('business_impact')}, "
        f"safety_concern={state.get('safety_concern')}\n"
    )
    if rubric_hint:
        review_prompt += f"\nUse the same feature-engineering rubric below when judging/correcting values:\n{rubric_hint}\n"
    review_prompt += "Are these features correct? Reply JSON only:"
    tie_break_needed = False
    tie_break_reason = ""
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_qwen_generate, review_prompt, _FEATURE_REVIEW_SYSTEM, 80),
            timeout=REVIEW_AGENT_FEATURE_TIMEOUT_SECONDS,
        )
        parsed = _extract_json_object(response)
        correct = bool(parsed.get("correct", True))
        suggested_values = _normalized_feature_values(parsed)
        reason = str(parsed.get("reason") or "")

        if not correct:
            if suggested_values is None:
                tie_break_needed = True
                tie_break_reason = (
                    f"Qwen feature review found an inconsistency but did not return valid corrected features. {reason}"
                ).strip()
            else:
                modified = _apply_feature_values(state, suggested_values)
                if modified:
                    features_changed = True
                    fix_note = f"qwen corrected features {modified}"
                    if reason:
                        fix_note += f" ({reason})"
                    result["fix_applied"] = (
                        f"{result['fix_applied']}; {fix_note}" if result.get("fix_applied") else fix_note
                    )
                    result["status"] = "fixed"
                    logger.info("review_agent | feature corrections applied via Qwen: %s", modified)
        current_values = _current_feature_values(state)
        if correct and _should_double_check_feature_values(current_values):
            retry_response = await asyncio.wait_for(
                asyncio.to_thread(_qwen_generate, extraction_prompt, _FEATURE_SYSTEM, 60),
                timeout=REVIEW_AGENT_FEATURE_TIMEOUT_SECONDS,
            )
            retry_values = _normalized_feature_values(_extract_json_object(retry_response))
            if retry_values is None:
                tie_break_needed = True
                tie_break_reason = (
                    "Escalated feature values could not be independently re-verified."
                )
            elif retry_values != current_values:
                modified = _apply_feature_values(state, retry_values)
                if modified:
                    features_changed = True
                    fix_note = f"independent feature check corrected {modified}"
                    result["fix_applied"] = (
                        f"{result['fix_applied']}; {fix_note}" if result.get("fix_applied") else fix_note
                    )
                    result["status"] = "fixed"
                    logger.info(
                        "review_agent | independent feature check corrected values: %s",
                        modified,
                    )
    except asyncio.TimeoutError:
        logger.warning("review_agent | feature validation Qwen timed out")
        result["status"] = "flagged"
        result["issue"] = "Feature review timed out before confirming whether the values made sense"
        result["operator_message"] = (
            "Review Agent could not validate the feature values in time. Manual operator review required."
        )
        return result, features_changed

    if tie_break_needed:
        try:
            retry_response = await asyncio.wait_for(
                asyncio.to_thread(_qwen_generate, extraction_prompt, _FEATURE_SYSTEM, 60),
                timeout=REVIEW_AGENT_FEATURE_TIMEOUT_SECONDS,
            )
            retry_values = _normalized_feature_values(_extract_json_object(retry_response))
            if retry_values is None:
                result["status"] = "flagged"
                result["issue"] = "Feature review could not confirm or reconstruct a trustworthy feature set"
                result["operator_message"] = tie_break_reason
                return result, features_changed

            modified = _apply_feature_values(state, retry_values)
            if modified:
                features_changed = True
                fix_note = f"feature tie-break re-extracted {modified}"
                result["fix_applied"] = (
                    f"{result['fix_applied']}; {fix_note}" if result.get("fix_applied") else fix_note
                )
                result["status"] = "fixed"
                logger.info("review_agent | feature tie-break corrections applied: %s", modified)
            else:
                logger.info("review_agent | feature tie-break confirmed existing values")
        except asyncio.TimeoutError:
            logger.warning("review_agent | feature tie-break Qwen timed out")
            result["status"] = "flagged"
            result["issue"] = "Feature review timed out and tie-break extraction also timed out"
            result["operator_message"] = tie_break_reason or "Feature review could not confirm the feature values."
            return result, features_changed

    return result, features_changed


# ---------------------------------------------------------------------------
# Stage 3 — Priority review
# ---------------------------------------------------------------------------


async def _review_priority(state: dict, upstream_inputs_changed: bool) -> tuple[dict, bool]:
    """
    Re-runs score_priority to verify the rules engine output.
    If upstream fields changed, the recomputed priority becomes authoritative.
    rescore_reference is used only as a light advisory signal from human history.
    Returns (stage_result, priority_changed).
    """
    result: dict[str, Any] = {
        "stage": "PrioritizationAgent", "was_mock": False,
        "status": "success", "issue": None, "fix_applied": None, "operator_message": None,
        "operator_override_required": False,
    }
    mode    = str(state.get("priority_mode") or "").lower()
    is_mock = (mode == "mock_fallback")
    result["was_mock"] = is_mock

    priority_before_raw = state.get("priority_label")
    priority_before = str(priority_before_raw or "").strip().lower() or None
    priority_changed = False

    # Always re-run score_priority so the review agent verifies the rules engine output.
    try:
        from agents.step09_priority.step import score_priority
        state = await score_priority(state)
        priority_after_raw = state.get("priority_label")
        priority_after = str(priority_after_raw or "").strip().lower() or None
        if priority_after != priority_before:
            priority_changed = True
            result["status"] = "fixed"
            result["fix_applied"] = f"priority recomputed: {priority_before} → {priority_after}"
        logger.info("review_agent | priority re-run: %s → %s", priority_before_raw, priority_after_raw)
    except Exception as exc:
        logger.warning("review_agent | score_priority re-run failed: %s", exc)
        if is_mock or upstream_inputs_changed:
            result["status"] = "flagged"
            result["issue"] = "PrioritizationAgent verification re-run failed"
            result["operator_message"] = "Cannot verify priority because the prioritization rules engine re-run failed."
            return result, False

    priority = str(state.get("priority_label") or "").strip().lower()
    if priority not in _VALID_PRIORITIES:
        result["status"]           = "flagged"
        result["issue"]            = f"priority_label='{priority}' is not a valid value after re-run"
        result["operator_message"] = f"Invalid priority '{priority}' — could not be resolved."
        return result, priority_changed

    # Light advisory check from recent human corrections in this department.
    department      = str(state.get("department_selected") or state.get("department") or "Unknown")
    rescore_records = _fetch_rescore_reference(department)
    mismatch_hint   = _light_rescore_mismatch(rescore_records, priority)
    if mismatch_hint:
        suggested = mismatch_hint["suggested"]
        count = mismatch_hint["count"]
        total = mismatch_hint["total"]
        result["operator_override_required"] = True
        result["issue"] = (
            f"Recent human corrections in {department} often move priority from '{priority}' to '{suggested}'"
        )
        result["operator_message"] = (
            f"Priority '{priority}' matched the rules engine, but recent human corrections in {department} "
            f"often changed it to '{suggested}' ({count}/{total} similar cases)."
        )

    return result, priority_changed


# ---------------------------------------------------------------------------
# Stage 4 — Department Routing review
# ---------------------------------------------------------------------------

_ROUTING_SYSTEM = (
    "You verify department routing for a facilities support ticket system. "
    'Reply only with JSON: {"agrees": true/false, "department": "<dept or null>", "reason": "<one sentence>"}'
)
_REROUTE_SYSTEM = (
    "You are a ticket routing assistant for a facilities management company. "
    "Reply only with the number of the correct department. No explanation."
)


async def _qwen_reroute(text: str, label: str, reroute_hint: str) -> tuple[str | None, float]:
    """Re-route a ticket using Qwen numbered-list prompt. Returns (department, confidence)."""
    prompt = (
        f"Ticket: {text[:400]}\nType: {label}\n"
        f"Departments:\n{_DEPARTMENT_LIST}\n"
    )
    if reroute_hint:
        prompt += f"\n{reroute_hint}\n"
    prompt += "\nWhich department number handles this ticket? Reply with one digit only:"
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_qwen_generate, prompt, _REROUTE_SYSTEM, 5),
            timeout=REVIEW_AGENT_ROUTING_TIMEOUT_SECONDS,
        )
        m = re.search(r"[1-7]", response)
        if m:
            dept = DEPARTMENT_LABELS[int(m.group(0)) - 1]
            return dept, 0.60
    except asyncio.TimeoutError:
        logger.warning("review_agent | Qwen re-routing timed out")
    return None, 0.0


async def _qwen_validate_routing(state: dict, reroute_hint: str) -> dict:
    """Qwen second-opinion on routing. Returns {"agrees", "department", "reason"}."""
    text       = str(state.get("text") or "")[:400]
    dept       = state.get("department_selected") or state.get("department") or "Unknown"
    conf       = float(state.get("department_confidence") or 0.0)
    candidates = state.get("department_routing_candidates") or []
    top3       = [
        f"{c.get('department')} ({float(c.get('confidence', 0)):.1%})"
        for c in candidates[:3]
    ]
    prompt = (
        f"Ticket: {text}\nType: {state.get('label', 'unknown')}\n"
        f"Routed to: {dept} (confidence {conf:.1%})\n"
        f"Top candidates: {', '.join(top3) or 'N/A'}\n"
        f"Available: {', '.join(DEPARTMENT_LABELS)}\n"
    )
    if reroute_hint:
        prompt += f"\n{reroute_hint}\n"
    prompt += f'\nDoes "{dept}" make sense? If not, suggest the best department.\nReply JSON only:'
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_qwen_generate, prompt, _ROUTING_SYSTEM, 80),
            timeout=REVIEW_AGENT_ROUTING_TIMEOUT_SECONDS,
        )
        parsed   = _extract_json_object(response)
        llm_dept = str(parsed.get("department") or "").strip() or None
        if llm_dept and llm_dept not in DEPARTMENT_LABELS:
            llm_dept = next((d for d in DEPARTMENT_LABELS if d.lower() == llm_dept.lower()), None)
        return {
            "agrees":     bool(parsed.get("agrees", True)),
            "department": llm_dept,
            "reason":     str(parsed.get("reason") or ""),
            "timed_out":  False,
        }
    except asyncio.TimeoutError:
        logger.warning("review_agent | routing validation Qwen timed out")
    return {"agrees": True, "department": None, "reason": "validation timed out", "timed_out": True}


async def _review_routing(state: dict) -> dict:
    """
    Checks department routing.

    If mock:  re-route with Qwen (using reroute_reference hint from manager/operator history) → fix or flag
    Always:   Qwen second-opinion with reroute_reference hint
              above threshold + agrees      → approved
              above threshold + disagrees   → override department + operator override flag
              below threshold + agrees      → approved_routing_review
              below threshold + disagrees   → override department + operator override flag
    """
    result: dict[str, Any] = {
        "stage": "DepartmentRoutingAgent", "was_mock": False,
        "status": "success", "issue": None, "fix_applied": None, "operator_message": None,
        # routing-specific output consumed by review_pipeline
        "verdict": "approved",
        "routing_overridden": False,
        "routing_sent_to_review": False,
        "review_department": None,
        "operator_override_required": False,
    }
    source  = str(state.get("department_routing_source") or "").lower()
    is_mock = (source == "mock_fallback")
    result["was_mock"] = is_mock

    confidence      = float(state.get("department_confidence") or 0.0)
    selected        = (state.get("department_selected") or state.get("department") or "").strip()
    above_threshold = confidence >= ROUTING_CONFIDENCE_THRESHOLD
    result["review_department"] = selected

    # Fetch learning data for current selection
    reroute_records = _fetch_routing_reference(selected)
    reroute_hint    = _format_reroute_hint(reroute_records)

    # If mock routing → attempt full re-route with Qwen
    if is_mock:
        text  = str(state.get("text") or "").strip()
        label = str(state.get("label") or "complaint")
        logger.info("review_agent | routing was mock, attempting Qwen re-route")
        new_dept, new_conf = await _qwen_reroute(text, label, reroute_hint)
        if new_dept:
            state["department_selected"]     = new_dept
            state["department"]              = new_dept
            state["department_confidence"]   = new_conf
            state["department_routing_source"] = "review_agent_rerouted"
            selected        = new_dept
            confidence      = new_conf
            above_threshold = confidence >= ROUTING_CONFIDENCE_THRESHOLD
            result["status"]          = "fixed"
            result["fix_applied"]     = f"re-routed to '{new_dept}' (confidence {new_conf:.1%})"
            result["review_department"] = new_dept
            # Refresh reference for the new department
            reroute_records = _fetch_routing_reference(new_dept)
            reroute_hint    = _format_reroute_hint(reroute_records)
            logger.info("review_agent | routing re-routed → %s (%.1%)", new_dept, new_conf)
        else:
            result["status"]           = "flagged"
            result["issue"]            = "DepartmentRoutingAgent service was down and re-routing failed"
            result["operator_message"] = (
                "Cannot determine department: routing service was down and Review Agent re-routing also failed."
            )
            result["verdict"] = "held_operator_review"
            return result

    if not is_mock and above_threshold:
        logger.info(
            "review_agent | routing accepted without Qwen review: department=%s confidence=%.2f",
            selected,
            confidence,
        )
        result["verdict"] = "approved"
        return result

    # Qwen second-opinion (with learning hint)
    llm = await _qwen_validate_routing(state, reroute_hint)
    llm_agrees = llm.get("agrees", True)
    llm_dept   = llm.get("department")
    llm_reason = llm.get("reason", "")
    llm_timed_out = bool(llm.get("timed_out"))

    if above_threshold:
        if llm_timed_out:
            result["verdict"] = "approved_operator_override"
            result["operator_override_required"] = True
            result["issue"] = "Routing validation timed out"
            result["operator_message"] = (
                f"Review Agent could not validate routing to '{selected}' in time. Operator verification recommended."
            )
        elif llm_agrees or not llm_dept:
            result["verdict"] = "approved"
            # keep status as "fixed" if we re-routed, else "success"
        else:
            state["department_selected"] = llm_dept
            state["department"] = llm_dept
            result["status"] = "fixed"
            result["verdict"] = "approved"
            result["routing_overridden"] = True
            result["operator_override_required"] = True
            result["review_department"] = llm_dept
            result["operator_message"] = (
                f"Review Agent changed routing from '{selected}' to '{llm_dept}'."
                + (f" {llm_reason}" if llm_reason else "")
            )
            fix_note = f"routing overridden to '{llm_dept}'"
            if llm_reason:
                fix_note += f" ({llm_reason})"
            result["fix_applied"] = (
                f"{result['fix_applied']}; {fix_note}" if result.get("fix_applied") else fix_note
            )
            logger.info(
                "review_agent | routing above threshold but LLM disagrees, overriding to %s (%s)",
                llm_dept,
                llm_reason,
            )
    else:
        # Below confidence threshold
        if llm_timed_out:
            result["routing_sent_to_review"] = True
            result["verdict"] = "approved_routing_review"
            result["issue"] = "Routing validation timed out"
        elif not llm_agrees and llm_dept:
            # LLM suggests a better department — override
            state["department_selected"] = llm_dept
            state["department"]          = llm_dept
            fix_note = f"routing overridden to '{llm_dept}' (LLM: {llm_reason})"
            result["fix_applied"]         = (
                f"{result['fix_applied']}; {fix_note}" if result.get("fix_applied") else fix_note
            )
            result["routing_overridden"]  = True
            result["operator_override_required"] = True
            result["operator_message"] = (
                f"Review Agent changed routing from '{selected}' to '{llm_dept}'."
                + (f" {llm_reason}" if llm_reason else "")
            )
            result["review_department"]   = llm_dept
            result["verdict"]             = "approved"
            result["status"]              = "fixed"
            logger.info("review_agent | routing overridden → %s", llm_dept)
        else:
            # Below threshold, keep manager routing review as the owner of low-confidence cases.
            result["routing_sent_to_review"] = True
            result["verdict"] = "approved_routing_review"

    return result


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def _persist_review_decision(
    *,
    ticket_id: str | None,
    ticket_code: str | None,
    execution_id: str | None,
    verdict: str,
    verdict_reason: str,
    stage_results: list[dict],
    priority_rerun: bool,
    priority_before: str | None,
    priority_after: str | None,
    priority_score_before: int | None,
    priority_score_after: int | None,
    routing_confidence: float,
    routing_threshold: float,
    routing_above_threshold: bool,
    original_department: str | None,
    final_department: str | None,
    routing_overridden: bool,
    routing_sent_to_review: bool,
    mock_stages: list[str],
    llm_model: str | None,
    llm_inference_time_ms: int | None,
    state_snapshot: dict,
) -> str:
    decision_id = str(uuid.uuid4())
    try:
        _ensure_review_agent_schema()
        from db import db_connect
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO review_agent_decisions (
                        id, ticket_id, ticket_code, execution_id,
                        verdict, verdict_reason,
                        consistency_passed, consistency_issues,
                        priority_rerun, priority_before, priority_after,
                        priority_score_before, priority_score_after,
                        routing_confidence, routing_threshold, routing_above_threshold,
                        original_department, final_department,
                        routing_overridden, routing_sent_to_review,
                        mock_stages_detected, mock_overrideable,
                        llm_model, llm_inference_time_ms,
                        pipeline_state_snapshot
                    ) VALUES (
                        %s, %s::uuid, %s, %s::uuid,
                        %s, %s,
                        %s, %s::jsonb,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s::jsonb, %s,
                        %s, %s,
                        %s::jsonb
                    )
                    """,
                    (
                        decision_id, ticket_id, ticket_code, execution_id,
                        verdict, verdict_reason,
                        not any(r.get("status") == "flagged" for r in stage_results),
                        json.dumps(stage_results, default=str),
                        priority_rerun, priority_before, priority_after,
                        priority_score_before, priority_score_after,
                        routing_confidence, routing_threshold, routing_above_threshold,
                        original_department, final_department,
                        routing_overridden, routing_sent_to_review,
                        json.dumps(mock_stages, default=str),
                        None,   # mock_overrideable no longer used — replaced by stage results
                        llm_model, llm_inference_time_ms,
                        json.dumps(
                            {k: v for k, v in (state_snapshot or {}).items() if not k.startswith("_")},
                            default=str,
                        ),
                    ),
                )
    except Exception as exc:
        logger.error("review_agent | failed to persist decision ticket=%s: %s", ticket_code, exc)
    return decision_id


# ---------------------------------------------------------------------------
# Backend API calls
# ---------------------------------------------------------------------------

async def _call_review_verdict(
    *,
    ticket_id: str,
    ticket_code: str,
    verdict: str,
    final_priority: str | None,
    final_department: str | None,
    routing_overridden: bool,
    routing_sent_to_review: bool,
    review_decision_id: str,
) -> None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.post(
                f"{BACKEND_URL}/api/internal/review-verdict",
                json={
                    "ticket_id":             ticket_id,
                    "ticket_code":           ticket_code,
                    "verdict":               verdict,
                    "priority_label":        final_priority,
                    "department":            final_department,
                    "routing_overridden":    routing_overridden,
                    "routing_sent_to_review": routing_sent_to_review,
                    "review_decision_id":    review_decision_id,
                },
            )
    except Exception as exc:
        logger.error("review_agent | review-verdict call failed ticket=%s: %s", ticket_code, exc)


async def _notify_operator_hold(ticket_id: str, ticket_code: str, reason: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{BACKEND_URL}/api/internal/notify-operators",
                json={
                    "ticket_id":        ticket_id,
                    "ticket_code":      ticket_code,
                    "notification_type": "review_agent_held",
                    "title":   f"Review Agent — Ticket Held: {ticket_code}",
                    "message": (
                        f"Review Agent held ticket {ticket_code} for operator review. "
                        f"Reason: {reason}"
                    ),
                },
            )
    except Exception as exc:
        logger.warning("review_agent | operator notify failed: %s", exc)


async def _notify_operator_override(ticket_id: str, ticket_code: str, reason: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{BACKEND_URL}/api/internal/notify-operators",
                json={
                    "ticket_id": ticket_id,
                    "ticket_code": ticket_code,
                    "notification_type": "system",
                    "title": f"Review Agent Override Check: {ticket_code}",
                    "message": (
                        f"Review Agent adjusted ticket {ticket_code} without holding it. "
                        f"Operator verification recommended. Reason: {reason}"
                    ),
                },
            )
    except Exception as exc:
        logger.warning("review_agent | operator override notify failed: %s", exc)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def get_review_agent_diagnostics() -> dict[str, object]:
    try:
        from shared_model_service import SHARED_QWEN_MODEL_PATH
        model_path = Path(SHARED_QWEN_MODEL_PATH) if SHARED_QWEN_MODEL_PATH else None
    except Exception:
        model_path = Path(os.getenv("REVIEW_AGENT_MODEL_PATH", "/app/agents/step11_reviewagent/model"))
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "review_agent_model_exists":      model_exists,
        "review_agent_timeout_seconds":   REVIEW_AGENT_TIMEOUT_SECONDS,
        "review_agent_mode":              "model" if model_exists else "unavailable",
    }


# ---------------------------------------------------------------------------
# Main pipeline function
# ---------------------------------------------------------------------------

async def review_pipeline(state: dict) -> dict:
    """
    Step 11 — Review Agent.
    Called after DepartmentRoutingAgent.
    Evaluates each critical stage in order, attempts fixes, and decides
    whether to approve, recommend non-blocking operator override review,
    or hold for the operator.
    """
    ticket_id   = str(state.get("ticket_id")   or "").strip() or None
    ticket_code = str(state.get("ticket_code") or "").strip() or None
    execution_id = str(state.get("_execution_id") or uuid.uuid4())
    start_time   = time.monotonic()

    if _get_model() is None:
        verdict = "held_operator_review"
        verdict_reason = "Review Agent model unavailable. Manual operator review required."
        stage_results = [{
            "stage": "ReviewAgent",
            "was_mock": True,
            "status": "flagged",
            "issue": "Review Agent model unavailable",
            "fix_applied": None,
            "operator_message": verdict_reason,
        }]
        inference_time_ms = int((time.monotonic() - start_time) * 1000)

        try:
            from shared_model_service import SHARED_QWEN_MODEL_NAME
        except Exception:
            SHARED_QWEN_MODEL_NAME = os.getenv("REVIEW_AGENT_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")

        decision_id = _persist_review_decision(
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            execution_id=execution_id,
            verdict=verdict,
            verdict_reason=verdict_reason,
            stage_results=stage_results,
            priority_rerun=False,
            priority_before=state.get("priority_label"),
            priority_after=state.get("priority_label"),
            priority_score_before=state.get("priority_score"),
            priority_score_after=state.get("priority_score"),
            routing_confidence=float(state.get("department_confidence") or 0.0),
            routing_threshold=ROUTING_CONFIDENCE_THRESHOLD,
            routing_above_threshold=float(state.get("department_confidence") or 0.0) >= ROUTING_CONFIDENCE_THRESHOLD,
            original_department=(state.get("department_selected") or state.get("department") or ""),
            final_department=(state.get("department_selected") or state.get("department") or ""),
            routing_overridden=False,
            routing_sent_to_review=False,
            mock_stages=_detect_mock_stages(state),
            llm_model=SHARED_QWEN_MODEL_NAME,
            llm_inference_time_ms=inference_time_ms,
            state_snapshot=state,
        )

        if ticket_id and ticket_code:
            await _call_review_verdict(
                ticket_id=ticket_id,
                ticket_code=ticket_code,
                verdict=verdict,
                final_priority=str(state.get("priority_label") or "").strip().lower() or None,
                final_department=(state.get("department_selected") or state.get("department") or ""),
                routing_overridden=False,
                routing_sent_to_review=False,
                review_decision_id=decision_id,
            )
            await _notify_operator_hold(ticket_id, ticket_code, verdict_reason)

        state["review_agent_verdict"] = verdict
        state["review_agent_verdict_reason"] = verdict_reason
        state["review_agent_decision_id"] = decision_id
        state["review_agent_stage_results"] = stage_results
        state["review_agent_mode"] = "unavailable"
        return state

    # Audit all mock stages before any fixes are applied
    mock_stages = _detect_mock_stages(state)
    noncritical_warnings = _noncritical_mock_warnings(state)
    if noncritical_warnings:
        logger.info(
            "review_agent | non-critical mock stages (warning only): %s", noncritical_warnings
        )
    unsupported_mock_results = _unsupported_critical_mock_results(mock_stages)
    if unsupported_mock_results:
        logger.info(
            "review_agent | unsupported critical mock stages require operator review: %s",
            [r["stage"] for r in unsupported_mock_results],
        )

    # ---- Stage 1: Classification ----
    class_result = await _review_classification(state)

    # ---- Stage 2: Feature Engineering ----
    feat_result, features_changed = await _review_features(state)

    # ---- Stage 3: Priority ----
    priority_before      = state.get("priority_label")
    priority_score_before = state.get("priority_score")
    priority_inputs_changed = features_changed or class_result.get("status") == "fixed"
    prio_result, priority_changed = await _review_priority(state, priority_inputs_changed)
    priority_after       = state.get("priority_label")
    priority_score_after = state.get("priority_score")
    priority_rerun       = priority_inputs_changed or prio_result.get("was_mock", False)

    # ---- Stage 4: Routing ----
    original_department = (state.get("department_selected") or state.get("department") or "")
    route_result = await _review_routing(state)
    final_department      = route_result["review_department"]
    routing_overridden    = route_result["routing_overridden"]
    routing_sent_to_review = route_result["routing_sent_to_review"]
    routing_verdict        = route_result["verdict"]

    stage_results = [class_result, feat_result, prio_result, route_result, *unsupported_mock_results]

    # ---- Final verdict ----
    flagged_stages = [r for r in stage_results if r.get("status") == "flagged"]
    operator_override_stages = [
        r for r in stage_results if r.get("operator_override_required")
    ]

    if flagged_stages:
        verdict = "held_operator_review"
        operator_messages = [
            r["operator_message"] for r in flagged_stages if r.get("operator_message")
        ]
        verdict_reason = " | ".join(operator_messages) or "One or more pipeline stages could not be resolved"
    elif operator_override_stages:
        verdict = "approved_operator_override"
        override_messages = [
            r["operator_message"] for r in operator_override_stages if r.get("operator_message")
        ]
        verdict_reason = " | ".join(override_messages) or "Review Agent recommends operator verification"
    else:
        verdict        = routing_verdict
        fixed_stages   = [r["stage"] for r in stage_results if r.get("status") == "fixed"]
        verdict_reason = f"All stages passed. Fixed: {fixed_stages}" if fixed_stages else "All stages passed"

    routing_confidence      = float(state.get("department_confidence") or 0.0)
    routing_above_threshold = routing_confidence >= ROUTING_CONFIDENCE_THRESHOLD
    inference_time_ms       = int((time.monotonic() - start_time) * 1000)

    try:
        from shared_model_service import SHARED_QWEN_MODEL_NAME
    except Exception:
        SHARED_QWEN_MODEL_NAME = os.getenv("REVIEW_AGENT_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct")

    # ---- Persist decision ----
    decision_id = _persist_review_decision(
        ticket_id=ticket_id,
        ticket_code=ticket_code,
        execution_id=execution_id,
        verdict=verdict,
        verdict_reason=verdict_reason,
        stage_results=stage_results,
        priority_rerun=priority_rerun,
        priority_before=priority_before,
        priority_after=priority_after,
        priority_score_before=priority_score_before,
        priority_score_after=priority_score_after,
        routing_confidence=routing_confidence,
        routing_threshold=ROUTING_CONFIDENCE_THRESHOLD,
        routing_above_threshold=routing_above_threshold,
        original_department=original_department,
        final_department=final_department,
        routing_overridden=routing_overridden,
        routing_sent_to_review=routing_sent_to_review,
        mock_stages=mock_stages,
        llm_model=SHARED_QWEN_MODEL_NAME,
        llm_inference_time_ms=inference_time_ms,
        state_snapshot=state,
    )

    # ---- Notify backend ----
    if ticket_id and ticket_code:
        await _call_review_verdict(
            ticket_id=ticket_id,
            ticket_code=ticket_code,
            verdict=verdict,
            final_priority=str(state.get("priority_label") or "").strip().lower() or None,
            final_department=final_department,
            routing_overridden=routing_overridden,
            routing_sent_to_review=routing_sent_to_review,
            review_decision_id=decision_id,
        )
        if verdict == "held_operator_review":
            await _notify_operator_hold(ticket_id, ticket_code, verdict_reason)
        elif verdict == "approved_operator_override":
            await _notify_operator_override(ticket_id, ticket_code, verdict_reason)

    state["review_agent_verdict"]        = verdict
    state["review_agent_verdict_reason"] = verdict_reason
    state["review_agent_decision_id"]    = decision_id
    state["review_agent_stage_results"]  = stage_results
    state["review_agent_mode"]           = "model" if _get_model() is not None else "unavailable"
    state["review_agent_operator_override_required"] = bool(operator_override_stages)
    state["review_agent_operator_override_stages"] = [
        r["stage"] for r in operator_override_stages
    ]

    logger.info(
        "review_agent | ticket=%s verdict=%s fixed=%s flagged=%s "
        "priority_rerun=%s routing_overridden=%s sent_to_review=%s operator_override=%s mock_stages=%s time_ms=%d",
        ticket_code,
        verdict,
        [r["stage"] for r in stage_results if r.get("status") == "fixed"],
        [r["stage"] for r in flagged_stages],
        priority_rerun,
        routing_overridden,
        routing_sent_to_review,
        [r["stage"] for r in operator_override_stages],
        mock_stages or "none",
        inference_time_ms,
    )
    return state
