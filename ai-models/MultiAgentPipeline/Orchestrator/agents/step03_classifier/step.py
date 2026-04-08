"""
Step 2 — Classification Agent
==============================
Routes the transcript to the complaint or inquiry path using local
in-process heuristic classification only.

If classifier confidence < CONFIDENCE_THRESHOLD, falls back to "complaint"
(the safer default that ensures the tenant always gets a response).
"""

import logging
import os
import gc
import json
import subprocess
import sys
from pathlib import Path
from functools import lru_cache

from langchain_core.runnables import RunnableLambda

CONFIDENCE_THRESHOLD = 0.75
logger = logging.getLogger(__name__)

INQUIRY_HINTS = (
    "how", "what", "where", "when", "can i", "could i", "would it",
    "help", "guide", "question", "information", "status", "track",
    "follow up", "follow-up",
)
COMPLAINT_HINTS = (
    "broken", "not working", "fault", "issue", "problem", "outage",
    "leak", "urgent", "angry", "frustrated", "complaint", "failed",
    "error", "can't", "cannot",
)

MODEL_PATH_ENV = "CLASSIFIER_MODEL_PATH"
VECTORIZER_PATH_ENV = "CLASSIFIER_VECTORIZER_PATH"
MODEL_DIR_ENV = "CLASSIFIER_MODEL_DIR"
PT_MODEL_FILENAMES = ("model.pt", "classifier_model.pt")
CLASSIFIER_RUNTIME_WORKER_PATH = Path(__file__).with_name("classifier_runtime_worker.py")
CLASSIFIER_TIMEOUT_SECONDS = float(os.getenv("CLASSIFIER_TIMEOUT_SECONDS", "60"))
CLASSIFIER_RUNTIME_MODE = os.getenv("CLASSIFIER_RUNTIME_MODE", "subprocess").strip().lower()
UNLOAD_CLASSIFIER_MODEL_AFTER_USE = os.getenv(
    "UNLOAD_CLASSIFIER_MODEL_AFTER_USE",
    "false",
).lower() in {"1", "true", "yes"}


def _heuristic_classify(text: str) -> tuple[str, float]:
    t = (text or "").strip().lower()
    if not t:
        return "complaint", 0.0

    inquiry_score = sum(1 for k in INQUIRY_HINTS if k in t)
    complaint_score = sum(1 for k in COMPLAINT_HINTS if k in t)
    is_question = "?" in t
    if is_question:
        inquiry_score += 1

    if complaint_score > inquiry_score:
        return "complaint", 0.65
    if inquiry_score > complaint_score:
        return "inquiry", 0.65
    return "complaint", 0.5


@lru_cache(maxsize=1)
def _load_optional_model():
    model_dir = os.getenv(MODEL_DIR_ENV, "/app/agents/step03_classifier/model").strip()
    model_path = os.getenv(MODEL_PATH_ENV, "").strip() or str(Path(model_dir) / "model.pkl")
    model_dir_path = Path(model_dir)

    pt_model_path = next((model_dir_path / name for name in PT_MODEL_FILENAMES if (model_dir_path / name).exists()), None)
    if pt_model_path is not None:
        try:
            import torch  # type: ignore
            import torch.nn as nn  # type: ignore
            import torch.nn.functional as F  # type: ignore
            from transformers import RobertaModel, RobertaTokenizer  # type: ignore

            complaint_label = 0
            inquiry_label = 1

            class CallClassifier(nn.Module):
                def __init__(self, dropout: float = 0.1):
                    super().__init__()
                    self.roberta = RobertaModel.from_pretrained("distilroberta-base")
                    hidden_size = self.roberta.config.hidden_size
                    self.dropout = nn.Dropout(dropout)
                    self.classifier = nn.Linear(hidden_size, 2)

                def forward(self, input_ids, attention_mask):
                    outputs = self.roberta(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                    )
                    cls = outputs.last_hidden_state[:, 0, :]
                    cls = self.dropout(cls)
                    return self.classifier(cls)

            tokenizer = RobertaTokenizer.from_pretrained(model_dir)
            model = CallClassifier()
            model.load_state_dict(torch.load(pt_model_path, map_location="cpu"))
            model = model.to("cpu")
            model.eval()
            logger.info("classifier | loaded torch checkpoint from %s", pt_model_path)
            return {
                "kind": "torch",
                "model": model,
                "tokenizer": tokenizer,
                "torch": torch,
                "F": F,
                "complaint_label": complaint_label,
                "inquiry_label": inquiry_label,
                "model_path": str(pt_model_path),
            }
        except Exception as exc:
            logger.warning("classifier | failed to load torch model (%s); using heuristic", exc)

    if not model_path:
        return None
    if not Path(model_path).exists():
        logger.warning("classifier | model file not found at %s; using heuristic", model_path)
        return None
    try:
        import joblib  # type: ignore

        model = joblib.load(model_path)
        vectorizer_path = os.getenv(VECTORIZER_PATH_ENV, "").strip() or str(
            Path(model_dir) / "vectorizer.pkl"
        )
        vectorizer = None
        if vectorizer_path:
            if Path(vectorizer_path).exists():
                vectorizer = joblib.load(vectorizer_path)
            else:
                logger.warning(
                    "classifier | vectorizer file not found at %s; model input will be raw text",
                    vectorizer_path,
                )
        logger.info("classifier | loaded optional sklearn model from %s", model_path)
        return {"kind": "sklearn", "model": model, "vectorizer": vectorizer, "model_path": model_path}
    except Exception as exc:
        logger.warning("classifier | failed to load optional model (%s); using heuristic", exc)
        return None


def get_classifier_diagnostics() -> dict[str, object]:
    model_dir = os.getenv(MODEL_DIR_ENV, "/app/agents/step03_classifier/model").strip()
    model_path = os.getenv(MODEL_PATH_ENV, "").strip() or str(Path(model_dir) / "model.pkl")
    pt_model_path = next(
        (str(Path(model_dir) / name) for name in PT_MODEL_FILENAMES if (Path(model_dir) / name).exists()),
        None,
    )
    vectorizer_path = os.getenv(VECTORIZER_PATH_ENV, "").strip() or str(
        Path(model_dir) / "vectorizer.pkl"
    )
    model_exists = bool((model_path and Path(model_path).exists()) or pt_model_path)
    vectorizer_exists = bool(vectorizer_path and Path(vectorizer_path).exists())
    return {
        "classifier_model_dir": model_dir or None,
        "classifier_model_path": pt_model_path or model_path or None,
        "classifier_model_exists": model_exists,
        "classifier_vectorizer_path": vectorizer_path or None,
        "classifier_vectorizer_exists": vectorizer_exists,
        "classifier_runtime_mode": CLASSIFIER_RUNTIME_MODE,
        "classifier_timeout_seconds": CLASSIFIER_TIMEOUT_SECONDS,
        "classifier_mode": "model" if model_exists else "mock",
    }


def warm_classifier_model() -> None:
    try:
        loaded = _load_optional_model()
        if loaded:
            logger.info(
                "classifier | warm startup load complete from %s",
                get_classifier_diagnostics().get("classifier_model_path"),
            )
    except Exception as exc:
        logger.warning("classifier | warm startup load failed (%s)", exc)


def _model_classify(text: str) -> tuple[str, float] | None:
    loaded = _load_optional_model()
    if not loaded:
        return None
    try:
        if loaded.get("kind") == "torch":
            torch = loaded["torch"]
            F = loaded["F"]
            tokenizer = loaded["tokenizer"]
            model = loaded["model"]
            enc = tokenizer(
                text,
                max_length=128,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to("cpu")
            attention_mask = enc["attention_mask"].to("cpu")
            with torch.no_grad():
                logits = model(input_ids, attention_mask)
                probs = F.softmax(logits, dim=1).squeeze(0)
            complaint_score = float(probs[loaded["complaint_label"]].item())
            inquiry_score = float(probs[loaded["inquiry_label"]].item())
            if complaint_score >= inquiry_score:
                return "complaint", complaint_score
            return "inquiry", inquiry_score

        model = loaded["model"]
        vectorizer = loaded["vectorizer"]
        if vectorizer is not None:
            X = vectorizer.transform([text])
            pred = model.predict(X)[0]
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(X)[0]
                conf = min(float(max(probs)), 0.92)   # cap overfit overconfidence
            else:
                conf = 0.65                            # no basis for 0.9 without proba
        else:
            # Pipeline with embedded vectorizer — predict and get real probabilities
            pred = model.predict([text])[0]
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba([text])[0]
                conf = min(float(max(probs)), 0.92)   # cap overfit overconfidence
            else:
                conf = 0.65                            # no basis without proba
        label = str(pred).strip().lower()
        if label not in {"complaint", "inquiry"}:
            return None
        return label, conf
    except Exception as exc:
        logger.warning("classifier | optional model inference failed (%s); using heuristic", exc)
        return None


def _release_optional_model() -> None:
    try:
        loaded = _load_optional_model()
    except Exception:
        loaded = None
    try:
        if isinstance(loaded, dict):
            loaded.clear()
    finally:
        _load_optional_model.cache_clear()
        gc.collect()


def _predict_via_subprocess(text: str) -> tuple[str, float, str] | None:
    try:
        completed = subprocess.run(
            [sys.executable, str(CLASSIFIER_RUNTIME_WORKER_PATH), text],
            capture_output=True,
            text=True,
            timeout=CLASSIFIER_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning("classifier | subprocess timed out after %.1fs", CLASSIFIER_TIMEOUT_SECONDS)
        return None
    except Exception as exc:
        logger.warning("classifier | subprocess launch failed (%s)", exc)
        return None

    if completed.returncode != 0:
        logger.warning("classifier | subprocess failed rc=%s err=%s", completed.returncode, (completed.stderr or "").strip())
        return None
    try:
        payload = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError as exc:
        logger.warning("classifier | invalid subprocess JSON (%s)", exc)
        return None
    label = str(payload.get("label") or "").strip().lower()
    if label not in {"complaint", "inquiry"}:
        return None
    try:
        confidence = float(payload.get("class_confidence", 0.0) or 0.0)
    except Exception:
        confidence = 0.0
    source = str(payload.get("classification_source") or "model").strip().lower() or "model"
    return label, confidence, source


async def classify(state: dict) -> dict:
    """
    Classifies transcript in-process and sets state["label"].
    """
    if not state.get("text", "").strip():
        # Empty transcript — treat as complaint so it gets a ticket
        state["label"] = "complaint"
        state["class_confidence"] = 0.0
        state["classification_source"] = "heuristic"
        logger.info("classifier | empty text fallback -> complaint")
        return state

    try:
        subprocess_result = None
        model_result = None
        if CLASSIFIER_RUNTIME_MODE == "subprocess":
            subprocess_result = _predict_via_subprocess(state.get("text", ""))
        else:
            model_result = _model_classify(state.get("text", ""))

        if subprocess_result:
            label, conf, source = subprocess_result
            state["classification_source"] = source
            logger.info("classifier | using subprocess runtime")
        elif model_result:
            label, conf = model_result
            state["classification_source"] = "model"
            logger.info(
                "classifier | using optional model from %s",
                get_classifier_diagnostics().get("classifier_model_path"),
            )
        else:
            label, conf = _heuristic_classify(state.get("text", ""))
            state["classification_source"] = "heuristic"
            logger.info("classifier | using local in-process heuristic")
    finally:
        if UNLOAD_CLASSIFIER_MODEL_AFTER_USE:
            _release_optional_model()
    state["label"] = label
    state["class_confidence"] = conf

    # Fallback to complaint if below threshold — model/subprocess predictions only.
    # Heuristic confidence is intentionally ≤0.65 by design; applying the threshold
    # here would negate every heuristic "inquiry" classification.
    if state.get("classification_source") != "heuristic" and state["class_confidence"] < CONFIDENCE_THRESHOLD:
        state["label"] = "complaint"
    logger.info(
        "classifier | label=%s confidence=%.3f",
        state["label"],
        float(state.get("class_confidence", 0.0) or 0.0),
    )
    logger.info(
        "classifier_decision | ticket_type=%s confidence=%.3f source=%s threshold=%.2f",
        state["label"],
        float(state.get("class_confidence", 0.0) or 0.0),
        state.get("classification_source"),
        CONFIDENCE_THRESHOLD,
    )

    return state


classifier_step = RunnableLambda(classify)
