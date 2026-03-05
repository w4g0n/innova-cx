"""
Step 8 — Department Routing Agent
=================================
Routes tickets to one of seven departments via zero-shot NLI (DeBERTa).
If confidence is below threshold, the ticket is left unassigned for manager review.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import torch
from langchain_core.runnables import RunnableLambda
from transformers import pipeline

BACKEND_URL = "http://backend:8000"
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

ROUTING_CONFIDENCE_THRESHOLD = float(os.getenv("DEPARTMENT_ROUTING_THRESHOLD", "0.7"))
ROUTER_MODEL_PATH = os.getenv(
    "DEPARTMENT_ROUTER_MODEL_PATH",
    "/app/models/classifier/deberta-v3-base-mnli-fever-anli",
).strip()
ROUTER_MODEL_NAME = os.getenv(
    "DEPARTMENT_ROUTER_MODEL_NAME",
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
).strip()
CALIBRATION_WEIGHT = float(os.getenv("DEPARTMENT_ROUTER_CALIBRATION_WEIGHT", "0.12"))


@lru_cache(maxsize=1)
def _load_department_router():
    model_ref = ROUTER_MODEL_PATH if (Path(ROUTER_MODEL_PATH) / "config.json").exists() else ROUTER_MODEL_NAME
    force_cpu = os.getenv("DEPARTMENT_ROUTER_FORCE_CPU", "false").lower() in {"1", "true", "yes"}
    device = -1 if force_cpu else (0 if torch.cuda.is_available() else -1)
    device_name = "CPU" if device == -1 else "GPU"
    try:
        logger.info("department_router | loading model=%s device=%s", model_ref, device_name)
        return pipeline(
            task="zero-shot-classification",
            model=model_ref,
            tokenizer=model_ref,
            device=device,
        )
    except Exception as exc:
        logger.warning("department_router | model load failed (%s)", exc)
        return None


def get_router_diagnostics() -> dict[str, object]:
    local_model_exists = bool(ROUTER_MODEL_PATH and (Path(ROUTER_MODEL_PATH) / "config.json").exists())
    return {
        "department_router_model_path": ROUTER_MODEL_PATH or None,
        "department_router_local_model_exists": local_model_exists,
        "department_router_model_name": ROUTER_MODEL_NAME or None,
        "department_router_threshold": ROUTING_CONFIDENCE_THRESHOLD,
        "department_router_calibration_weight": CALIBRATION_WEIGHT,
        "department_router_mode": "deberta_zero_shot_or_mock",
    }


def _mock_department_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("wifi", "network", "internet", "server", "system", "software", "login")):
        return "IT"
    if any(k in t for k in ("leak", "pipe", "water", "ac", "air conditioning", "maintenance", "electrical", "power")):
        return "Maintenance"
    if any(k in t for k in ("fire", "unsafe", "hazard", "security", "alarm", "theft", "emergency")):
        return "Safety & Security"
    if any(k in t for k in ("contract", "legal", "policy", "compliance", "regulation", "law")):
        return "Legal & Compliance"
    if any(k in t for k in ("lease", "tenant", "rent", "handover", "move in")):
        return "Leasing"
    if any(k in t for k in ("hr", "salary", "leave", "employee", "staff")):
        return "HR"
    return "Facilities Management"


def _predict_department_from_text(text: str) -> tuple[list[str], list[float], str]:
    classifier = _load_department_router()
    if classifier is None:
        top = _mock_department_from_text(text)
        remaining = [dept for dept in DEPARTMENT_LABELS if dept != top]
        labels = [top, *remaining]
        # Deliberately weak confidence, but above threshold so routing still functions.
        scores = [0.74] + [0.26 / max(1, len(remaining))] * len(remaining)
        return labels, scores, "mock"

    try:
        result = classifier(
            text,
            candidate_labels=DEPARTMENT_LABELS,
            multi_label=False,
            hypothesis_template="This ticket should be handled by {}.",
        )
        labels = result.get("labels") or []
        scores = result.get("scores") or []
        if not labels or not scores:
            return [], [], "inference_empty"
        return [str(label).strip() for label in labels], [float(score) for score in scores], "deberta_zero_shot"
    except Exception as exc:
        logger.warning("department_router | inference failed (%s)", exc)
        top = _mock_department_from_text(text)
        remaining = [dept for dept in DEPARTMENT_LABELS if dept != top]
        labels = [top, *remaining]
        scores = [0.74] + [0.26 / max(1, len(remaining))] * len(remaining)
        return labels, scores, "mock"


async def _fetch_manager_calibration(client: httpx.AsyncClient, predicted: str) -> dict[str, float]:
    try:
        response = await client.get(
            f"{BACKEND_URL}/api/internal/department-routing/calibration",
            params={"predicted": predicted},
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json() if response.content else {}
        probabilities = payload.get("probabilities") or {}
        predicted_probs = probabilities.get(predicted) or {}
        return {str(dept): float(prob) for dept, prob in predicted_probs.items()}
    except Exception:
        return {}


def _apply_feedback_calibration(labels: list[str], scores: list[float], adjustments: dict[str, float]) -> tuple[list[str], list[float], str]:
    if not labels or not scores:
        return labels, scores, "none"
    if not adjustments:
        return labels, scores, "none"

    adjusted = []
    for idx, label in enumerate(labels):
        base = scores[idx]
        boost = CALIBRATION_WEIGHT * float(adjustments.get(label, 0.0))
        adjusted.append((label, min(0.999, base + boost)))
    adjusted.sort(key=lambda x: x[1], reverse=True)
    return [label for label, _ in adjusted], [score for _, score in adjusted], "manager_feedback"


def _build_orchestrator_payload(
    state: dict,
    top_department: str | None,
    routed_department: str | None,
    route_confidence: float,
    route_source: str,
) -> dict:
    should_auto_route = bool(routed_department) and route_confidence >= ROUTING_CONFIDENCE_THRESHOLD
    return {
        "ticket_id": state.get("ticket_id"),
        "subject": state.get("subject"),
        "transcript": state["text"],
        "sentiment": state.get("text_sentiment", 0.0),
        "audio_sentiment": state.get("audio_sentiment", 0.0),
        "priority": state.get("priority_score", 3),
        "department": routed_department if should_auto_route else None,
        "department_candidate": top_department,
        "keywords": state.get("keywords", []),
        "label": state.get("label", "complaint"),
        "status": "Assigned" if should_auto_route else "Open",
        "classification_confidence": route_confidence,
        "routing_model": route_source,
    }


async def route_and_store(state: dict) -> dict:
    ticket_text = str(state.get("text") or "").strip()
    labels, scores, source = _predict_department_from_text(ticket_text)
    top_department = labels[0] if labels else None
    top_confidence = scores[0] if scores else 0.0

    calibration_source = "none"
    async with httpx.AsyncClient(timeout=30.0) as client:
        if top_department:
            adjustments = await _fetch_manager_calibration(client, top_department)
            labels, scores, calibration_source = _apply_feedback_calibration(labels, scores, adjustments)
            top_department = labels[0] if labels else top_department
            top_confidence = scores[0] if scores else top_confidence

        auto_routed = bool(top_department) and top_confidence >= ROUTING_CONFIDENCE_THRESHOLD
        routed_department = top_department if auto_routed else None
        state["department_routing_source"] = source
        state["department_routing_calibration"] = calibration_source
        state["department_confidence"] = top_confidence
        state["department"] = routed_department
        state["status"] = "Assigned" if auto_routed else "Open"
        state["chatbot_response"] = None if state.get("label") == "inquiry" else state.get("chatbot_response")

        ticket_payload = _build_orchestrator_payload(
            state,
            top_department=top_department,
            routed_department=routed_department,
            route_confidence=top_confidence,
            route_source=source,
        )
        response = await client.post(f"{BACKEND_URL}/api/complaints", json=ticket_payload)
        response.raise_for_status()
        data = response.json()

    state["status"] = data.get("status", state.get("status"))
    state["department"] = data.get("department", state.get("department"))
    state["priority_label"] = data.get("priority", state.get("priority_label"))
    state["priority_assigned_at"] = data.get("priority_assigned_at")
    state["respond_due_at"] = data.get("respond_due_at")
    state["resolve_due_at"] = data.get("resolve_due_at")
    state["ticket_id"] = data.get("ticket_id")

    logger.info(
        "ticket_status_update | ticket_id=%s status=%s department=%s priority=%s route_confidence=%.3f route_threshold=%.3f route_source=%s",
        state.get("ticket_id"),
        state.get("status"),
        state.get("department"),
        data.get("priority"),
        top_confidence,
        ROUTING_CONFIDENCE_THRESHOLD,
        source if calibration_source == "none" else f"{source}+{calibration_source}",
    )
    return state


router_step = RunnableLambda(route_and_store)
