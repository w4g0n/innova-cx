"""
Shared Qwen Model Service
=========================
Single in-process Qwen2.5-0.5B-Instruct instance shared across:
  - SubjectGenerationAgent (step01) — in-process fallback
  - SuggestedResolutionAgent (step02) — primary inference
  - DepartmentRoutingAgent (step10) — routing via generation
  - ReviewAgent (step11) — consistency check + routing validation

Model weights preferably live in the shared host model store:
  /app/models/reviewagent/qwen2.5-0.5B-Instruct

Legacy fallback during migration:
  /app/agents/step11_reviewagent/model

All callers import get_shared_qwen() from here.
"""

from __future__ import annotations

import logging
import os
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
    "",
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
