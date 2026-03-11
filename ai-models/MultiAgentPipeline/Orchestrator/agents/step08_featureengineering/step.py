"""
Step 6 — Feature Engineering Agent
==================================
Single agent that executes:
  1) feature labeling (NLI model or mock fallback)
  2) deterministic safety/normalization rules
"""

from __future__ import annotations

import logging
import os
import json
import gc
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.runnables import RunnableLambda

logger = logging.getLogger(__name__)

FEATURE_LABELER_MODEL_PATH = os.getenv(
    "FEATURE_LABELER_MODEL_PATH",
    "/app/agents/step08_featureengineering/model",
).strip()
FEATURE_LABELER_MODEL_NAME = os.getenv(
    "FEATURE_LABELER_MODEL_NAME",
    "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
).strip()
FEATURE_LABELER_AUTO_DOWNLOAD = os.getenv("FEATURE_LABELER_AUTO_DOWNLOAD", "false").lower() in {"1", "true", "yes"}
HF_TOKEN = os.getenv("HF_TOKEN", "").strip() or None
FEATURE_RUNTIME_WORKER_PATH = Path(__file__).with_name("feature_labeler_runtime_worker.py")
FEATURE_RUNTIME_TIMEOUT_SECONDS = float(os.getenv("FEATURE_RUNTIME_TIMEOUT_SECONDS", "60"))
FEATURE_RUNTIME_MODE = os.getenv("FEATURE_RUNTIME_MODE", "subprocess").strip().lower()
UNLOAD_FEATURE_LABELER_AFTER_USE = os.getenv(
    "UNLOAD_FEATURE_LABELER_AFTER_USE",
    "false",
).lower() in {"1", "true", "yes"}

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
LOW_SEVERITY_KEYWORDS = (
    "noise",
    "noisy",
    "loud",
    "music",
    "ceremony",
    "cleaning",
    "garbage",
    "trash",
    "parking",
    "billing",
    "invoice",
)
HIGH_SEVERITY_KEYWORDS = (
    "outage",
    "no power",
    "power outage",
    "elevator stuck",
    "stuck in elevator",
    "water leak",
    "flood",
    "flooding",
    "gas leak",
    "smoke",
    "fire",
)
LOW_IMPACT_KEYWORDS = (
    "noise",
    "noisy",
    "loud",
    "music",
    "cleaning",
    "garbage",
    "trash",
    "parking",
    "billing",
    "invoice",
    "minor",
    "cosmetic",
)
HIGH_IMPACT_KEYWORDS = (
    "cannot work",
    "can't work",
    "unable to work",
    "operations stopped",
    "operations are blocked",
    "business halted",
    "staff cannot",
    "users cannot",
    "cannot login",
    "can't login",
    "financial loss",
    "client-facing",
)
HIGH_URGENCY_KEYWORDS = (
    "urgent",
    "asap",
    "immediate",
    "immediately",
    "right now",
    "today",
    "emergency",
    "third time",
    "second time",
    "again",
    "repeated",
    "repeatedly",
    "outage",
)
LOW_URGENCY_KEYWORDS = (
    "whenever possible",
    "no rush",
    "not urgent",
    "scheduled maintenance",
    "routine",
)

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
    if s == "critical":
        return "high"
    return s if s in {"low", "medium", "high"} else default


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


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    t = str(text or "").lower()
    return any(keyword in t for keyword in keywords)


def _apply_feature_calibration(state: dict, text: str) -> None:
    severity = _normalize_level(state.get("issue_severity"), default="medium")
    urgency = _normalize_level(state.get("issue_urgency"), default="medium")
    impact = _normalize_level(state.get("business_impact"), default="medium")
    t = str(text or "").lower()

    if _contains_any(t, HIGH_SEVERITY_KEYWORDS):
        severity = "high"
    elif _contains_any(t, LOW_SEVERITY_KEYWORDS) and severity == "medium":
        severity = "low"

    if _contains_any(t, HIGH_IMPACT_KEYWORDS):
        impact = "high"
    elif _contains_any(t, LOW_IMPACT_KEYWORDS) and impact == "medium":
        impact = "low"

    if _contains_any(t, HIGH_URGENCY_KEYWORDS):
        urgency = "high"
    elif _contains_any(t, LOW_URGENCY_KEYWORDS):
        urgency = "low"

    # Noise/disturbance complaints are rarely severe business-impacting incidents
    # unless the text explicitly says work is blocked.
    if _contains_any(t, ("noise", "noisy", "loud", "music", "disturbance")) and not _contains_any(t, HIGH_IMPACT_KEYWORDS):
        severity = "low"
        impact = "low"
        if urgency == "high" and not _contains_any(t, ("urgent", "emergency", "asap", "immediate")):
            urgency = "medium"

    state["issue_severity"] = severity
    state["issue_urgency"] = urgency
    state["business_impact"] = impact


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


def _load_multitask_feature_labeler(model_dir: Path):
    model_pt = model_dir / "model.pt"
    model_cfg = model_dir / "model_config.json"
    label_classes = model_dir / "label_classes.json"
    if not (model_pt.exists() and model_cfg.exists() and label_classes.exists()):
        return None

    try:
        import torch  # type: ignore
        import torch.nn as nn  # type: ignore
        from transformers import AutoModel, AutoTokenizer  # type: ignore
    except Exception as exc:
        logger.info("feature_engineering | torch/transformers unavailable for multitask loader (%s)", exc)
        return None

    cfg = json.loads(model_cfg.read_text(encoding="utf-8"))
    class_map = json.loads(label_classes.read_text(encoding="utf-8"))
    base_model_name = str(cfg.get("base_model") or "").strip()
    if not base_model_name:
        logger.warning("feature_engineering | multitask model config missing base_model")
        return None

    num_labels_per_task = {col: len(values) for col, values in class_map.items()}

    class MultiTaskDeBERTa(nn.Module):
        def __init__(self, base_model_name: str, num_labels_per_task: dict):
            super().__init__()
            self.encoder = AutoModel.from_pretrained(base_model_name)
            hidden_size = self.encoder.config.hidden_size
            self.heads = nn.ModuleDict({
                col: nn.Sequential(
                    nn.Dropout(0.1),
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.GELU(),
                    nn.Dropout(0.1),
                    nn.Linear(hidden_size // 2, n_classes),
                )
                for col, n_classes in num_labels_per_task.items()
            })

        def forward(self, input_ids, attention_mask):
            outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
            pooled = outputs.last_hidden_state[:, 0, :]
            logits = {}
            for col, head in self.heads.items():
                head_dtype = next(head.parameters()).dtype
                logits[col] = head(pooled.to(dtype=head_dtype))
            return logits

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = MultiTaskDeBERTa(base_model_name, num_labels_per_task).to("cpu")
    model.load_state_dict(torch.load(model_pt, map_location="cpu"))
    model = model.to(dtype=torch.float32)
    model.eval()
    logger.info("feature_engineering | loaded multitask checkpoint from %s", model_pt)
    return {
        "kind": "multitask_pt",
        "tokenizer": tokenizer,
        "model": model,
        "torch": torch,
        "class_map": class_map,
        "max_length": int(cfg.get("max_length", 256)),
    }


@lru_cache(maxsize=1)
def _load_feature_labeler():
    try:
        import torch  # type: ignore
        from transformers import pipeline  # type: ignore
    except Exception as exc:
        logger.info("feature_engineering | torch/transformers unavailable (%s); using mock", exc)
        return None

    model_name = FEATURE_LABELER_MODEL_PATH
    if not model_name:
        logger.info("feature_engineering | no FEATURE_LABELER_MODEL_PATH provided; using mock labeler")
        return None

    model_path = Path(model_name)
    multitask_loaded = _load_multitask_feature_labeler(model_path)
    if multitask_loaded is not None:
        return multitask_loaded

    if not (model_path / "config.json").exists() and FEATURE_LABELER_AUTO_DOWNLOAD and FEATURE_LABELER_MODEL_NAME:
        try:
            from huggingface_hub import snapshot_download  # type: ignore

            logger.info(
                "feature_engineering | downloading labeler model=%s to %s",
                FEATURE_LABELER_MODEL_NAME,
                model_name,
            )
            snapshot_download(
                repo_id=FEATURE_LABELER_MODEL_NAME,
                local_dir=model_name,
                token=HF_TOKEN,
            )
        except Exception as exc:
            logger.warning("feature_engineering | labeler auto-download failed (%s), using mock", exc)

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
    if isinstance(classifier, dict) and classifier.get("kind") == "multitask_pt":
        torch = classifier["torch"]
        tokenizer = classifier["tokenizer"]
        model = classifier["model"]
        class_map = classifier["class_map"]
        max_length = classifier["max_length"]
        encoded = tokenizer(
            [text],
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = model(
                encoded["input_ids"].to("cpu"),
                encoded["attention_mask"].to("cpu"),
            )
        output_labels: dict[str, Any] = {}
        for label_name, task_logits in logits.items():
            probs = torch.softmax(task_logits, dim=1)[0]
            idx = int(torch.argmax(probs).item())
            classes = class_map[label_name]
            value = classes[idx]
            if label_name == "safety_concern":
                output_labels[label_name] = str(value).strip().lower() in {"true", "1", "yes"}
            else:
                output_labels[label_name] = str(value).strip().lower()
        return output_labels

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


def _apply_labeling_step(state: dict, text: str) -> None:
    if FEATURE_RUNTIME_MODE == "subprocess":
        try:
            completed = subprocess.run(
                [sys.executable, str(FEATURE_RUNTIME_WORKER_PATH), text],
                capture_output=True,
                text=True,
                timeout=FEATURE_RUNTIME_TIMEOUT_SECONDS,
                check=False,
            )
            if completed.returncode == 0:
                payload = json.loads((completed.stdout or "").strip())
                labels = {
                    "issue_severity": str(payload.get("issue_severity") or "medium").lower(),
                    "issue_urgency": str(payload.get("issue_urgency") or "medium").lower(),
                    "business_impact": str(payload.get("business_impact") or "medium").lower(),
                    "safety_concern": bool(payload.get("safety_concern")),
                }
                label_source = str(payload.get("feature_labels_source") or "nli").strip().lower() or "nli"
            else:
                raise RuntimeError((completed.stderr or "").strip() or f"rc={completed.returncode}")
        except subprocess.TimeoutExpired:
            logger.warning("feature_engineering | subprocess timed out after %.1fs, using mock", FEATURE_RUNTIME_TIMEOUT_SECONDS)
            labels = _mock_labels(text)
            label_source = "mock"
        except Exception as exc:
            logger.warning("feature_engineering | subprocess failed (%s), using mock", exc)
            labels = _mock_labels(text)
            label_source = "mock"
    else:
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


def _release_feature_labeler() -> None:
    try:
        loaded = _load_feature_labeler()
    except Exception:
        loaded = None
    try:
        if isinstance(loaded, dict):
            loaded.clear()
    finally:
        _load_feature_labeler.cache_clear()
        gc.collect()


def get_feature_engineering_diagnostics() -> dict[str, object]:
    labeler_model = FEATURE_LABELER_MODEL_PATH or None
    labeler_path = Path(labeler_model) if labeler_model else None
    hf_labeler_exists = bool(labeler_path and (labeler_path / "config.json").exists())
    multitask_labeler_exists = bool(
        labeler_path
        and (labeler_path / "model.pt").exists()
        and (labeler_path / "model_config.json").exists()
        and (labeler_path / "label_classes.json").exists()
    )
    labeler_exists = hf_labeler_exists or multitask_labeler_exists
    return {
        "feature_engineering_mode": "nli+rules",
        "feature_labeler_model": labeler_model,
        "feature_labeler_model_name": FEATURE_LABELER_MODEL_NAME or None,
        "feature_labeler_auto_download": FEATURE_LABELER_AUTO_DOWNLOAD,
        "feature_labeler_model_exists": labeler_exists,
        "feature_runtime_mode": FEATURE_RUNTIME_MODE,
        "feature_runtime_timeout_seconds": FEATURE_RUNTIME_TIMEOUT_SECONDS,
        "feature_labeler_artifact_type": (
            "multitask_pt" if multitask_labeler_exists else "hf_zero_shot" if hf_labeler_exists else None
        ),
        "feature_labeler_mode": "model" if labeler_exists else "mock",
    }


async def engineer_features(state: dict) -> dict:
    if state.get("label") != "complaint":
        logger.info("feature_engineering | skipped (label=%s)", state.get("label"))
        return state

    text = str(state.get("text") or "").strip()

    try:
        # Step 1: labeling (NLI model/mock)
        _apply_labeling_step(state, text)
    finally:
        if UNLOAD_FEATURE_LABELER_AFTER_USE:
            _release_feature_labeler()

    # Step 2: deterministic safety/normalization rules on top of NLI labels
    business_impact = state.get("business_impact") or "medium"
    issue_severity = state.get("issue_severity") or "medium"
    issue_urgency = state.get("issue_urgency") or "medium"
    explicit_safety = _optional_bool(state.get("safety_concern"))

    severity_norm = _normalize_level(issue_severity, default="medium")
    safety_from_keywords = _has_safety_signal(text)
    safety_from_severity = severity_norm == "high"

    state["business_impact"] = _normalize_level(business_impact, default="medium")
    if explicit_safety is not None:
        state["safety_concern"] = explicit_safety
    else:
        state["safety_concern"] = bool(safety_from_keywords or safety_from_severity)
    state["issue_severity"] = severity_norm
    state["issue_urgency"] = _normalize_level(issue_urgency, default="medium")
    _apply_feature_calibration(state, text)
    if state["issue_severity"] == "high" and explicit_safety is None:
        state["safety_concern"] = bool(state["safety_concern"] or _has_safety_signal(text))

    logger.info(
        "feature_engineering | labels_source=%s impact=%s safety=%s severity=%s urgency=%s",
        state.get("feature_labels_source"),
        state["business_impact"],
        state["safety_concern"],
        state["issue_severity"],
        state["issue_urgency"],
    )
    logger.info(
        "feature_decision | business_impact=%s issue_severity=%s issue_urgency=%s safety_concern=%s source=%s",
        state["business_impact"],
        state["issue_severity"],
        state["issue_urgency"],
        state["safety_concern"],
        state.get("feature_labels_source"),
    )

    return state


feature_engineering_step = RunnableLambda(engineer_features)
