"""
Step 8 — Department Routing Agent
=================================
Routes tickets to one of seven departments via zero-shot NLI (DeBERTa).
If confidence is below threshold, the ticket is left unassigned for manager review.
"""

from __future__ import annotations

import logging
import os
import tarfile
import gc
import json
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx
import torch
from langchain_core.runnables import RunnableLambda
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BACKEND_URL = "http://backend:8000"
logger = logging.getLogger(__name__)

DEPARTMENT_CANDIDATES = {
    "Facilities Management": "Facilities Management for cleaning, housekeeping, pests, waste, common areas, and building upkeep",
    "Legal & Compliance": "Legal and Compliance for contracts, regulations, policy, legal matters, and compliance issues",
    "Safety & Security": "Safety and Security for hazards, alarms, emergencies, fire, smoke, gas, theft, and unsafe conditions",
    "HR": "Human Resources for employee relations, payroll, leave, staffing, and HR issues",
    "Leasing": "Leasing for rent, pricing, tenants, lease agreements, move in, and handover issues",
    "Maintenance": "Maintenance for water leaks, plumbing, ceilings, electrical faults, HVAC, repairs, and building systems",
    "IT": "IT for wifi, internet, network, software, login, server, device, and printer issues",
}

DEPARTMENT_LABELS = list(DEPARTMENT_CANDIDATES.keys())
ROUTING_CONFIDENCE_THRESHOLD = float(os.getenv("DEPARTMENT_ROUTING_THRESHOLD", "0.50"))
ROUTER_MODEL_PATH = os.getenv(
    "DEPARTMENT_ROUTER_MODEL_PATH",
    "/app/agents/step10_router/model",
).strip()
ROUTER_MODEL_NAME = os.getenv(
    "DEPARTMENT_ROUTER_MODEL_NAME",
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
).strip()
ROUTER_AUTO_DOWNLOAD = os.getenv("DEPARTMENT_ROUTER_AUTO_DOWNLOAD", "false").lower() in {"1", "true", "yes"}
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
CALIBRATION_WEIGHT = float(os.getenv("DEPARTMENT_ROUTER_CALIBRATION_WEIGHT", "0.12"))
CONFIDENCE_FLAT_BOOST = float(os.getenv("DEPARTMENT_ROUTER_CONFIDENCE_FLAT_BOOST", "0.50"))
CONFIDENCE_MAX_CAP = float(os.getenv("DEPARTMENT_ROUTER_CONFIDENCE_MAX_CAP", "0.98"))
ROUTER_TAR_NAME = "department_routing_agent.tar"
ROUTER_RUNTIME_WORKER_PATH = Path(__file__).with_name("router_runtime_worker.py")
ROUTER_TIMEOUT_SECONDS = float(os.getenv("ROUTER_TIMEOUT_SECONDS", "60"))
ROUTER_RUNTIME_MODE = os.getenv("ROUTER_RUNTIME_MODE", "subprocess").strip().lower()
UNLOAD_ROUTER_MODEL_AFTER_USE = os.getenv(
    "UNLOAD_ROUTER_MODEL_AFTER_USE",
    "true",
).lower() in {"1", "true", "yes"}
HYPOTHESIS_TEMPLATE = "This ticket should be handled by {}."
TRAINED_CONTRADICTION_ID = 0
TRAINED_ENTAILMENT_ID = 2

HEURISTIC_ROUTING_BOOSTS = {
    "IT": ("wifi", "network", "internet", "server", "system", "software", "login", "email", "printer"),
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


def _contains_routing_keyword(text: str, keyword: str) -> bool:
    escaped = re.escape(str(keyword or "").strip().lower())
    if not escaped:
        return False
    return bool(re.search(rf"\b{escaped}\b", str(text or "").lower()))


def _resolve_router_model_dir() -> Path | None:
    if not ROUTER_MODEL_PATH:
        return None

    model_path = Path(ROUTER_MODEL_PATH)
    if (model_path / "config.json").exists():
        return model_path

    packaged_dir = model_path / "models" / "department_router"
    if (packaged_dir / "config.json").exists():
        return packaged_dir

    tar_path = model_path / ROUTER_TAR_NAME
    if tar_path.exists():
        try:
            with tarfile.open(tar_path) as archive:
                archive.extractall(model_path)
            if (packaged_dir / "config.json").exists():
                logger.info("department_router | extracted packaged model from %s", tar_path)
                return packaged_dir
        except Exception as exc:
            logger.warning("department_router | failed extracting %s (%s)", tar_path, exc)

    return None


@lru_cache(maxsize=1)
def _load_department_router():
    if not ROUTER_MODEL_PATH:
        logger.info("department_router | DEPARTMENT_ROUTER_MODEL_PATH is empty, using mock routing")
        return None

    model_dir = _resolve_router_model_dir()
    if model_dir is None and ROUTER_AUTO_DOWNLOAD and ROUTER_MODEL_NAME:
        try:
            from huggingface_hub import snapshot_download  # type: ignore

            logger.info("department_router | downloading model=%s to %s", ROUTER_MODEL_NAME, ROUTER_MODEL_PATH)
            snapshot_download(
                repo_id=ROUTER_MODEL_NAME,
                local_dir=ROUTER_MODEL_PATH,
                token=HF_TOKEN,
            )
        except Exception as exc:
            logger.warning("department_router | auto-download failed (%s), using mock routing", exc)
        model_dir = _resolve_router_model_dir()

    if model_dir is None:
        logger.info("department_router | no local model at %s, using mock routing", ROUTER_MODEL_PATH)
        return None

    force_cpu = os.getenv("DEPARTMENT_ROUTER_FORCE_CPU", "false").lower() in {"1", "true", "yes"}
    device = -1 if force_cpu else (0 if torch.cuda.is_available() else -1)
    device_name = "CPU" if device == -1 else "GPU"
    try:
        logger.info("department_router | loading local model=%s device=%s", model_dir, device_name)
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), token=HF_TOKEN)
        model = AutoModelForSequenceClassification.from_pretrained(str(model_dir), token=HF_TOKEN)
        if device == -1:
            model = model.to("cpu")
            runtime_device = "cpu"
        else:
            model = model.to("cuda")
            runtime_device = "cuda"
        model.eval()
        return {
            "tokenizer": tokenizer,
            "model": model,
            "device": runtime_device,
            "contradiction_id": TRAINED_CONTRADICTION_ID,
            "entailment_id": TRAINED_ENTAILMENT_ID,
            "model_dir": str(model_dir),
        }
    except Exception as exc:
        logger.warning("department_router | model load failed (%s)", exc)
        return None


def get_router_diagnostics() -> dict[str, object]:
    resolved_model_dir = _resolve_router_model_dir()
    tar_path = (Path(ROUTER_MODEL_PATH) / ROUTER_TAR_NAME) if ROUTER_MODEL_PATH else None
    local_model_exists = resolved_model_dir is not None
    return {
        "department_router_model_path": ROUTER_MODEL_PATH or None,
        "department_router_model_name": ROUTER_MODEL_NAME or None,
        "department_router_auto_download": ROUTER_AUTO_DOWNLOAD,
        "department_router_local_model_exists": local_model_exists,
        "department_router_resolved_model_dir": str(resolved_model_dir) if resolved_model_dir else None,
        "department_router_packaged_tar": str(tar_path) if tar_path and tar_path.exists() else None,
        "department_router_threshold": ROUTING_CONFIDENCE_THRESHOLD,
        "department_router_calibration_weight": CALIBRATION_WEIGHT,
        "department_router_runtime_mode": ROUTER_RUNTIME_MODE,
        "department_router_timeout_seconds": ROUTER_TIMEOUT_SECONDS,
        "department_router_mode": "model" if local_model_exists else "mock",
    }


def _mock_department_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(_contains_routing_keyword(t, k) for k in ("wifi", "network", "internet", "server", "system", "software", "login")):
        return "IT"
    if any(_contains_routing_keyword(t, k) for k in ("leak", "pipe", "water", "ac", "air conditioning", "maintenance", "electrical", "power")):
        return "Maintenance"
    if any(_contains_routing_keyword(t, k) for k in ("fire", "unsafe", "hazard", "security", "alarm", "theft", "emergency")):
        return "Safety & Security"
    if any(_contains_routing_keyword(t, k) for k in ("contract", "legal", "policy", "compliance", "regulation", "law")):
        return "Legal & Compliance"
    if any(_contains_routing_keyword(t, k) for k in ("lease", "tenant", "rent", "handover", "move in")):
        return "Leasing"
    if any(_contains_routing_keyword(t, k) for k in ("hr", "salary", "leave", "employee", "staff")):
        return "HR"
    return "Facilities Management"


def _mock_routing_result(text: str) -> tuple[list[str], list[float], str]:
    top = _mock_department_from_text(text)
    remaining = [dept for dept in DEPARTMENT_LABELS if dept != top]
    labels = [top, *remaining]
    scores = [0.49] + [0.51 / max(1, len(remaining))] * len(remaining)
    return labels, scores, "mock"


def _predict_department_from_text(text: str) -> tuple[list[str], list[float], str]:
    loaded = _load_department_router()
    if loaded is None:
        return _mock_routing_result(text)

    try:
        tokenizer = loaded["tokenizer"]
        model = loaded["model"]
        device = loaded["device"]
        contradiction_id = loaded["contradiction_id"]
        entailment_id = loaded["entailment_id"]

        department_scores: list[tuple[str, float]] = []
        for department in DEPARTMENT_LABELS:
            hypothesis = HYPOTHESIS_TEMPLATE.format(department)
            encoded = tokenizer(
                text,
                hypothesis,
                truncation=True,
                padding="max_length",
                max_length=256,
                return_tensors="pt",
            )
            encoded = {k: v.to(device) for k, v in encoded.items()}
            with torch.no_grad():
                logits = model(**encoded).logits[0]
                pair_logits = torch.stack([logits[contradiction_id], logits[entailment_id]])
                entailment_prob = float(torch.softmax(pair_logits, dim=0)[1].item())
            department_scores.append((department, entailment_prob))

        if not department_scores:
            return [], [], "inference_empty"

        total = sum(score for _, score in department_scores) or 1.0
        normalized_scores = [(department, score / total) for department, score in department_scores]
        normalized_scores.sort(key=lambda item: item[1], reverse=True)
        labels = [department for department, _ in normalized_scores]
        scores = [float(score) for _, score in normalized_scores]
        return labels, scores, "deberta_pairwise_nli"
    except Exception as exc:
        logger.warning("department_router | inference failed (%s)", exc)
        return _mock_routing_result(text)


def _release_department_router() -> None:
    try:
        loaded = _load_department_router()
    except Exception:
        loaded = None
    try:
        if loaded is not None:
            del loaded
    finally:
        _load_department_router.cache_clear()
        gc.collect()


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


def _apply_domain_routing_boost(text: str, labels: list[str], scores: list[float]) -> tuple[list[str], list[float], str]:
    if not labels or not scores:
        return labels, scores, "none"

    lowered = str(text or "").lower()
    adjustments: dict[str, float] = {}
    for department, keywords in HEURISTIC_ROUTING_BOOSTS.items():
        matches = sum(1 for keyword in keywords if _contains_routing_keyword(lowered, keyword))
        if matches:
            adjustments[department] = min(0.65, 0.22 + (0.12 * (matches - 1)))

    if not adjustments:
        return labels, scores, "none"

    adjusted = []
    for idx, label in enumerate(labels):
        base = float(scores[idx])
        adjusted.append((label, min(0.999, base + adjustments.get(label, 0.0))))
    adjusted.sort(key=lambda x: x[1], reverse=True)
    return [label for label, _ in adjusted], [score for _, score in adjusted], "domain_keywords"


def _apply_flat_confidence_boost(labels: list[str], scores: list[float]) -> tuple[list[str], list[float], str]:
    if not labels or not scores:
        return labels, scores, "none"

    adjusted = []
    for idx, label in enumerate(labels):
        adjusted.append((label, min(CONFIDENCE_MAX_CAP, float(scores[idx]) + CONFIDENCE_FLAT_BOOST)))
    adjusted.sort(key=lambda x: x[1], reverse=True)
    return [label for label, _ in adjusted], [score for _, score in adjusted], "flat_boost"


def _build_orchestrator_payload(
    state: dict,
    top_department: str | None,
    routed_department: str | None,
    route_confidence: float,
    route_source: str,
) -> dict:
    should_auto_route = bool(routed_department) and route_confidence >= ROUTING_CONFIDENCE_THRESHOLD
    # Always send the top predicted department so backend can queue
    # low-confidence routes for manager review.
    predicted_department = routed_department if should_auto_route else top_department
    return {
        "ticket_id": state.get("ticket_id"),
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
    try:
        if ROUTER_RUNTIME_MODE == "subprocess":
            try:
                completed = subprocess.run(
                    [sys.executable, str(ROUTER_RUNTIME_WORKER_PATH), ticket_text],
                    capture_output=True,
                    text=True,
                    timeout=ROUTER_TIMEOUT_SECONDS,
                    check=False,
                )
                if completed.returncode == 0:
                    payload = json.loads((completed.stdout or "").strip())
                    labels = [str(x) for x in (payload.get("labels") or [])]
                    scores = [float(x) for x in (payload.get("scores") or [])]
                    source = str(payload.get("source") or "mock").strip() or "mock"
                else:
                    raise RuntimeError((completed.stderr or "").strip() or f"rc={completed.returncode}")
            except subprocess.TimeoutExpired:
                logger.warning("department_router | subprocess timed out after %.1fs", ROUTER_TIMEOUT_SECONDS)
                labels, scores, source = _mock_routing_result(ticket_text)
            except Exception as exc:
                logger.warning("department_router | subprocess failed (%s)", exc)
                labels, scores, source = _mock_routing_result(ticket_text)
        else:
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
                part
                for part in (calibration_source, heuristic_source, flat_boost_source)
                if part != "none"
            ) or "none"
            state["department_confidence"] = top_confidence
            state["department_routing_candidates"] = [
                {"department": label, "confidence": round(float(score), 4)}
                for label, score in zip(labels, scores)
            ]
            state["department_selected"] = routed_department if auto_routed else top_department
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
    finally:
        if UNLOAD_ROUTER_MODEL_AFTER_USE:
            _release_department_router()

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
        "+".join(
            part
            for part in (source, calibration_source, heuristic_source, flat_boost_source)
            if part != "none"
        ),
    )
    return state


router_step = RunnableLambda(route_and_store)
