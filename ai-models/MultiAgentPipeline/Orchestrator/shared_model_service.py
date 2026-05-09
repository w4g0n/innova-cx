"""
Shared Model Service
====================
Provides singleton loaders for two in-process models:

Qwen2.5-0.5B-Instruct  (get_shared_qwen)
  - SubjectGenerationAgent (step02) — in-process fallback
  - SuggestedResolutionAgent (step03) — primary inference
  - ReviewAgent (step11) — consistency check + routing validation
  Model path: /app/models/reviewagent/qwen2.5-0.5B-Instruct
  Legacy fallback: /app/agents/step11_reviewagent/model

DeBERTa-v3 NLI department router  (get_shared_deberta)
  - DepartmentRoutingAgent (step10) — NLI scoring across 7 departments
  Model path: DEPARTMENT_ROUTER_MODEL_PATH env var
  Default:    /app/agents/step10_router/model
  Tar:        department_routing_agent.tar (auto-extracted on first load)
"""

from __future__ import annotations

import logging
import os
import tarfile
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SHARED_MODEL_PATH = "/app/models/reviewagent/qwen2.5-0.5B-Instruct"
_LEGACY_MODEL_PATH = "/app/agents/step11_reviewagent/model"

SHARED_QWEN_MODEL_PATH: str = os.getenv(
    "SHARED_QWEN_MODEL_PATH",
    _SHARED_MODEL_PATH,
).strip()
SHARED_QWEN_MODEL_NAME: str = os.getenv(
    "SHARED_QWEN_MODEL_NAME",
    "Qwen2.5",
).strip()
SHARED_QWEN_AUTO_DOWNLOAD: bool = False

# Module-level singleton — only set on successful load.
# None means "not yet loaded" or "load failed" (retry is allowed).
# Using a lock so that concurrent pipeline runs don't attempt parallel loads.
_qwen_lock: threading.Lock = threading.Lock()
_qwen_instance: dict[str, Any] | None = None
_qwen_loaded: bool = False  # True only after a successful load

def _resolve_shared_qwen_model_path() -> str:
    requested = SHARED_QWEN_MODEL_PATH.strip()
    if requested and (Path(requested) / "config.json").exists():
        return requested

    if (_SHARED_MODEL_PATH and (Path(_SHARED_MODEL_PATH) / "config.json").exists()):
        logger.info("shared_model_service | using shared host model path %s", _SHARED_MODEL_PATH)
        return _SHARED_MODEL_PATH

    if requested and Path(requested).exists():
        logger.warning(
            "shared_model_service | requested model path %s is incomplete; falling back",
            requested,
        )

    if (Path(_LEGACY_MODEL_PATH) / "config.json").exists():
        logger.info("shared_model_service | using legacy model path %s", _LEGACY_MODEL_PATH)
        return _LEGACY_MODEL_PATH

    return requested

def get_shared_qwen() -> dict[str, Any] | None:
    """
    Load and return the shared Qwen model.
    Returns {"tokenizer", "model", "device"} or None if unavailable.

    Successful loads are cached permanently (singleton).
    Failed loads are NOT cached — each call retries until the model is ready.
    This prevents lru_cache from permanently locking out the model after a
    transient failure (OOM at startup, model not yet downloaded, etc.).
    """
    global _qwen_instance, _qwen_loaded

    # Fast path — already loaded successfully.
    if _qwen_loaded:
        return _qwen_instance

    with _qwen_lock:
        # Re-check inside the lock (another thread may have loaded it).
        if _qwen_loaded:
            return _qwen_instance

        model_path_str = _resolve_shared_qwen_model_path()

        if not model_path_str:
            logger.info("shared_model_service | SHARED_QWEN_MODEL_PATH is empty, model disabled")
            return None

        model_path = Path(model_path_str)

        if not (model_path / "config.json").exists():
            logger.info(
                "shared_model_service | no local model at %s, model disabled",
                model_path_str,
            )
            return None

        try:
            import torch  # type: ignore
            from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

            force_cpu = os.getenv("SHARED_QWEN_FORCE_CPU", "false").lower() in {"1", "true", "yes"}
            device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")

            logger.info(
                "shared_model_service | loading model=%s device=%s",
                model_path_str,
                device,
            )
            tokenizer = AutoTokenizer.from_pretrained(
                model_path_str,
                trust_remote_code=True,
            )
            model = AutoModelForCausalLM.from_pretrained(
                model_path_str,
                trust_remote_code=True,
                torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
                low_cpu_mem_usage=True,
            )
            model = model.to(device)
            model.eval()
            logger.info("shared_model_service | model loaded successfully on %s", device)
            _qwen_instance = {"tokenizer": tokenizer, "model": model, "device": device}
            _qwen_loaded = True
            return _qwen_instance
        except Exception as exc:
            logger.warning("shared_model_service | model load failed (%s), will retry next call", exc)
            return None


def get_shared_qwen_diagnostics() -> dict[str, object]:
    resolved_path = _resolve_shared_qwen_model_path()
    model_path = Path(resolved_path) if resolved_path else None
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "shared_qwen_model_path": resolved_path or None,
        "shared_qwen_model_name": SHARED_QWEN_MODEL_NAME or None,
        "shared_qwen_auto_download": SHARED_QWEN_AUTO_DOWNLOAD,
        "shared_qwen_model_exists": model_exists,
        "shared_qwen_cached": _qwen_loaded,
    }


# ---------------------------------------------------------------------------
# DeBERTa NLI department router
# ---------------------------------------------------------------------------

_DEBERTA_BASE_PATH = "/app/agents/step10_router/model"
_DEBERTA_TAR_NAME  = "department_routing_agent.tar"
_DEBERTA_TAR_SUBDIR = "models/department_router"   # path inside the tar

DEPARTMENT_ROUTER_MODEL_PATH: str = os.getenv(
    "DEPARTMENT_ROUTER_MODEL_PATH",
    _DEBERTA_BASE_PATH,
).strip()

_deberta_lock: threading.Lock = threading.Lock()
_deberta_instance: dict[str, Any] | None = None
_deberta_loaded: bool = False


def _resolve_deberta_model_path() -> str | None:
    """
    Returns the directory that contains config.json for the DeBERTa router.
    Checks three locations in order:
      1. DEPARTMENT_ROUTER_MODEL_PATH directly (already-extracted model)
      2. DEPARTMENT_ROUTER_MODEL_PATH/models/department_router (tar extracted in-place)
      3. Extracts the tar if found and returns the extraction target
    """
    base = Path(DEPARTMENT_ROUTER_MODEL_PATH)

    # 1. Direct path already contains model files
    if (base / "config.json").exists():
        return str(base)

    # 2. Previously extracted tar lives in a subdirectory
    subdir = base / _DEBERTA_TAR_SUBDIR
    if (subdir / "config.json").exists():
        return str(subdir)

    # 3. Try to extract the tar
    tar_path = base / _DEBERTA_TAR_NAME
    if tar_path.exists():
        try:
            logger.info("shared_model_service | extracting %s", tar_path)
            with tarfile.open(tar_path, "r") as tf:
                tf.extractall(path=base)
            if (subdir / "config.json").exists():
                logger.info("shared_model_service | deberta model extracted to %s", subdir)
                return str(subdir)
        except Exception as exc:
            logger.warning("shared_model_service | tar extraction failed: %s", exc)

    return None


def get_shared_deberta() -> dict[str, Any] | None:
    """
    Load and return the DeBERTa NLI department router.
    Returns {"tokenizer", "model", "torch"} or None if unavailable.
    Singleton — cached on first successful load, retried on failure.
    """
    global _deberta_instance, _deberta_loaded

    if _deberta_loaded:
        return _deberta_instance

    with _deberta_lock:
        if _deberta_loaded:
            return _deberta_instance

        model_path_str = _resolve_deberta_model_path()
        if not model_path_str:
            logger.info("shared_model_service | deberta model not found, routing will use heuristic fallback")
            return None

        try:
            import torch  # type: ignore
            from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore

            logger.info("shared_model_service | loading deberta router from %s", model_path_str)
            tokenizer = AutoTokenizer.from_pretrained(model_path_str)
            model = AutoModelForSequenceClassification.from_pretrained(
                model_path_str,
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
            model.eval()
            logger.info("shared_model_service | deberta router loaded")
            _deberta_instance = {"tokenizer": tokenizer, "model": model, "torch": torch}
            _deberta_loaded = True
            return _deberta_instance
        except Exception as exc:
            logger.warning("shared_model_service | deberta load failed (%s), will retry next call", exc)
            return None


def get_shared_deberta_diagnostics() -> dict[str, object]:
    resolved = _resolve_deberta_model_path()
    return {
        "deberta_model_path": resolved or None,
        "deberta_model_exists": bool(resolved),
        "deberta_cached": _deberta_loaded,
    }
