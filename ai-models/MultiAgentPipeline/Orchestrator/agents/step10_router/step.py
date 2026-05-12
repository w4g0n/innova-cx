"""
Step 10 — Department Routing Agent
===================================
Routes tickets to one of seven departments using Qwen generation.
A numbered list prompt is used; the model replies with a single digit.
All calibration layers (feedback, domain keywords, flat boost) run on top
of the Qwen-derived scores.

If Qwen is unavailable or returns an unparseable response the heuristic
keyword fallback takes over (same logic as _mock_department_from_text).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from langchain_core.runnables import RunnableLambda
from backend_client import internal_backend_headers

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://backend:8000").rstrip("/")
logger = logging.getLogger(__name__)

DEPARTMENT_CANDIDATES = {
    "Facilities Management": "Facilities Management for cleaning, housekeeping, pests, waste, common areas, and building upkeep",
    "Legal & Compliance": "Legal and Compliance for contracts, regulations, policy, legal matters, and compliance issues",
    "Safety & Security": "Safety and Security for hazards, alarms, emergencies, fire, smoke, gas, theft, and unsafe conditions",
    "HR": "Human Resources for employee relations, payroll, leave, staffing, and HR issues",
    "Leasing": "Leasing for rent, pricing, tenants, lease agreements, move in, and handover issues",
    "Maintenance": "Maintenance for water leaks, plumbing, ceilings, electrical faults, HVAC, repairs, and building systems",
    "IT": "IT for wifi, internet, network, software, login, server, laptop, computer, device, monitor, keyboard, and printer issues",
}

DEPARTMENT_LABELS = list(DEPARTMENT_CANDIDATES.keys())
ROUTING_CONFIDENCE_THRESHOLD = 0.75
CALIBRATION_WEIGHT = float(os.getenv("DEPARTMENT_ROUTER_CALIBRATION_WEIGHT", "0.12"))
CONFIDENCE_FLAT_BOOST = float(os.getenv("DEPARTMENT_ROUTER_CONFIDENCE_FLAT_BOOST", "0.30"))
CONFIDENCE_MAX_CAP = float(os.getenv("DEPARTMENT_ROUTER_CONFIDENCE_MAX_CAP", "0.98"))

HEURISTIC_ROUTING_BOOSTS = {
    "IT": (
        "wifi",
        "network",
        "internet",
        "server",
        "system",
        "software",
        "login",
        "email",
        "printer",
        "laptop",
        "computer",
        "pc",
        "desktop",
        "device",
        "monitor",
        "screen",
        "keyboard",
        "mouse",
        "vpn",
        "outlook",
        "teams",
    ),
    "Maintenance": (
        "leak",
        "water leak",
        "ceiling leak",
        "flood",
        "flooding",
        "pipe",
        "pipe burst",
        "plumbing",
        "drain",
        "toilet",
        "sink",
        "faucet",
        "electrical",
        "power outage",
        "outlet",
        "air conditioning",
        "ac",
        "hvac",
        "ceiling",
    ),
    "Safety & Security": ("fire", "smoke", "gas leak", "alarm", "hazard", "unsafe", "evacuate", "security", "theft"),
    "Legal & Compliance": ("contract", "legal", "policy", "compliance", "regulation", "law"),
    "Leasing": ("lease", "tenant", "rent", "handover", "move in", "pricing"),
    "HR": ("hr", "salary", "leave", "employee", "staff grievance", "payroll"),
    "Facilities Management": ("cleaning", "pest", "rat", "rodent", "cockroach", "garbage", "trash", "housekeeping"),
}


def _heuristic_department(text: str) -> str:
    t = (text or "").lower()
    if any(
        k in t
        for k in (
            "wifi",
            "network",
            "internet",
            "server",
            "system",
            "software",
            "login",
            "laptop",
            "computer",
            "pc",
            "desktop",
            "device",
            "monitor",
            "screen",
            "keyboard",
            "mouse",
            "vpn",
            "printer",
            "email",
            "outlook",
            "teams",
        )
    ):
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


_HYPOTHESIS_TEMPLATE = "This ticket should be handled by {}."
_ENTAILMENT_IDX = 2  # softmax index for entailment in the fine-tuned DeBERTa checkpoint


def _predict_department_via_deberta(text: str) -> tuple[list[str], list[float], str]:
    """
    Score each department using the fine-tuned DeBERTa NLI router.
    For each department hypothesis the entailment probability is used as
    the routing score. Falls back to heuristic if model is unavailable.
    Returns (ranked_labels, ranked_scores, source).
    """
    try:
        from shared_model_service import get_shared_deberta
        loaded = get_shared_deberta()
    except Exception:
        loaded = None

    if loaded is None:
        return _fallback_routing_result(text)

    try:
        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        torch = loaded["torch"]

        premise = str(text or "")[:400]
        dept_scores: list[tuple[str, float]] = []

        for dept in DEPARTMENT_LABELS:
            enc = tokenizer(
                premise,
                _HYPOTHESIS_TEMPLATE.format(dept),
                max_length=256,
                truncation=True,
                return_tensors="pt",
            )
            with torch.no_grad():
                logits = model(**enc).logits
            probs = torch.softmax(logits, dim=-1)[0]
            dept_scores.append((dept, float(probs[_ENTAILMENT_IDX])))

        dept_scores.sort(key=lambda x: x[1], reverse=True)
        labels = [d for d, _ in dept_scores]
        scores = [s for _, s in dept_scores]
        return labels, scores, "deberta_nli"
    except Exception as exc:
        logger.warning("department_router | deberta inference failed (%s)", exc)

    return _fallback_routing_result(text)


def _fallback_routing_result(text: str) -> tuple[list[str], list[float], str]:
    top = _heuristic_department(text)
    remaining = [d for d in DEPARTMENT_LABELS if d != top]
    labels = [top] + remaining
    scores = [0.30] + [0.70 / max(1, len(remaining))] * len(remaining)
    return labels, scores, "mock_fallback"


def get_router_diagnostics() -> dict[str, object]:
    try:
        from shared_model_service import get_shared_deberta_diagnostics, DEPARTMENT_ROUTER_MODEL_PATH
        diag = get_shared_deberta_diagnostics()
        model_exists = bool(diag.get("deberta_model_exists"))
        model_path = DEPARTMENT_ROUTER_MODEL_PATH
    except Exception:
        model_exists = False
        model_path = None
    return {
        "department_router_model_path": model_path,
        "department_router_model_name": "DeBERTa-v3-base-mnli (fine-tuned)",
        "department_router_local_model_exists": model_exists,
        "department_router_threshold": ROUTING_CONFIDENCE_THRESHOLD,
        "department_router_calibration_weight": CALIBRATION_WEIGHT,
        "department_router_runtime_mode": "deberta_nli",
        "department_router_mode": "deberta_nli" if model_exists else "heuristic_fallback",
    }


def _rerank(
    labels: list[str],
    scores: list[float],
    adjustments: dict[str, float],
    cap: float,
    source: str,
) -> tuple[list[str], list[float], str]:
    paired = [(lbl, min(cap, float(scores[i]) + adjustments.get(lbl, 0.0))) for i, lbl in enumerate(labels)]
    paired.sort(key=lambda x: x[1], reverse=True)
    return [l for l, _ in paired], [s for _, s in paired], source


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


def _apply_feedback_calibration(
    labels: list[str], scores: list[float], adjustments: dict[str, float]
) -> tuple[list[str], list[float], str]:
    if not labels or not scores or not adjustments:
        return labels, scores, "none"
    weighted = {dept: CALIBRATION_WEIGHT * float(prob) for dept, prob in adjustments.items()}
    return _rerank(labels, scores, weighted, 0.999, "manager_feedback")


def _apply_domain_routing_boost(
    text: str, labels: list[str], scores: list[float]
) -> tuple[list[str], list[float], str]:
    if not labels or not scores:
        return labels, scores, "none"
    lowered = str(text or "").lower()
    boosts: dict[str, float] = {
        dept: min(0.65, 0.22 + 0.12 * (matches - 1))
        for dept, keywords in HEURISTIC_ROUTING_BOOSTS.items()
        if (matches := sum(1 for kw in keywords if kw in lowered))
    }
    if not boosts:
        return labels, scores, "none"
    return _rerank(labels, scores, boosts, 0.999, "domain_keywords")


def _apply_flat_confidence_boost(
    labels: list[str], scores: list[float]
) -> tuple[list[str], list[float], str]:
    if not labels or not scores:
        return labels, scores, "none"
    flat = {lbl: CONFIDENCE_FLAT_BOOST for lbl in labels}
    return _rerank(labels, scores, flat, CONFIDENCE_MAX_CAP, "flat_boost")


def _build_orchestrator_payload(
    state: dict,
    top_department: str | None,
    routed_department: str | None,
    route_confidence: float,
    route_source: str,
) -> dict:
    should_auto_route = bool(routed_department) and route_confidence >= ROUTING_CONFIDENCE_THRESHOLD
    predicted_department = routed_department if should_auto_route else top_department
    return {
        "ticket_id": state.get("ticket_code") or state.get("ticket_id"),
        "subject": state.get("subject"),
        "transcript": state["text"],
        "sentiment": state.get("text_sentiment", 0.0),
        "audio_sentiment": state.get("audio_sentiment", 0.0),
        "priority": state.get("priority_score", 3),
        "department": predicted_department,
        "department_candidate": top_department,
        "keywords": state.get("keywords", []),
        "label": state.get("label", "complaint"),
        "suggested_resolution": state.get("suggested_resolution"),
        "suggested_resolution_model": state.get("suggested_resolution_model"),
        "status": "Assigned" if should_auto_route else "Open",
        "classification_confidence": route_confidence,
        "routing_model": route_source,
    }


async def route_and_store(state: dict) -> dict:
    ticket_text = str(state.get("text") or "").strip()
    label = str(state.get("label") or "complaint").strip()
    data: dict = {}

    labels, scores, source = await asyncio.to_thread(
        _predict_department_via_deberta, ticket_text
    )
    top_department = labels[0] if labels else None
    top_confidence = scores[0] if scores else 0.0

    calibration_source = "none"
    async with httpx.AsyncClient(timeout=30.0) as client:
        if top_department:
            adjustments = await _fetch_manager_calibration(client, top_department)
            labels, scores, calibration_source = _apply_feedback_calibration(labels, scores, adjustments)
            top_department = labels[0] if labels else top_department
            top_confidence = scores[0] if scores else top_confidence

        labels, scores, heuristic_source = _apply_domain_routing_boost(ticket_text, labels, scores)
        if labels:
            top_department = labels[0]
            top_confidence = scores[0]

        labels, scores, flat_boost_source = _apply_flat_confidence_boost(labels, scores)
        if labels:
            top_department = labels[0]
            top_confidence = scores[0]

        auto_routed = bool(top_department) and top_confidence >= ROUTING_CONFIDENCE_THRESHOLD
        routed_department = top_department if auto_routed else None

        state["department_routing_source"] = source
        state["department_routing_calibration"] = "+".join(
            part for part in (calibration_source, heuristic_source, flat_boost_source)
            if part != "none"
        ) or "none"
        state["department_confidence"] = top_confidence
        state["department_routing_candidates"] = [
            {"department": label, "confidence": round(float(score), 4)}
            for label, score in zip(labels, scores)
        ]
        state["department_selected"] = top_department
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
        response = await client.post(
            f"{BACKEND_URL}/api/complaints",
            json=ticket_payload,
            headers=internal_backend_headers(),
        )
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
        "ticket_status_update | ticket_id=%s status=%s department=%s priority=%s "
        "route_confidence=%.3f route_threshold=%.3f route_source=%s",
        state.get("ticket_id"),
        state.get("status"),
        state.get("department"),
        data.get("priority"),
        top_confidence,
        ROUTING_CONFIDENCE_THRESHOLD,
        "+".join(
            part for part in (source, calibration_source, heuristic_source, flat_boost_source)
            if part != "none"
        ),
    )
    return state


router_step = RunnableLambda(route_and_store)
