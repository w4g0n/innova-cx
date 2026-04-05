"""
Shared Qwen Model Service
=========================
Single in-process Qwen2.5-0.5B-Instruct instance shared across:
  - SubjectGenerationAgent (step01) — in-process fallback
  - SuggestedResolutionAgent (step02) — primary inference
  - DepartmentRoutingAgent (step10) — routing via generation
  - ReviewAgent (step11) — consistency check + routing validation

Model weights live in the ReviewAgent's model directory:
  /app/agents/step11_reviewagent/model  (gitignored)

All callers import get_shared_qwen() from here.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SHARED_QWEN_MODEL_PATH: str = os.getenv(
    "SHARED_QWEN_MODEL_PATH",
    "/app/agents/step11_reviewagent/model",
).strip()
SHARED_QWEN_MODEL_NAME: str = os.getenv(
    "SHARED_QWEN_MODEL_NAME",
    "Qwen/Qwen2.5-0.5B-Instruct",
).strip()
SHARED_QWEN_AUTO_DOWNLOAD: bool = os.getenv(
    "SHARED_QWEN_AUTO_DOWNLOAD", "false"
).lower() in {"1", "true", "yes"}
HF_TOKEN: str | None = os.getenv("HF_TOKEN", "").strip() or None


@lru_cache(maxsize=1)
def get_shared_qwen() -> dict[str, Any] | None:
    """
    Load and cache the shared Qwen model.
    Returns {"tokenizer", "model", "device"} or None if unavailable.

    The lru_cache keeps the model resident for the lifetime of the process.
    Do NOT call cache_clear() — the shared instance is never unloaded.
    """
    if not SHARED_QWEN_MODEL_PATH:
        logger.info("shared_model_service | SHARED_QWEN_MODEL_PATH is empty, model disabled")
        return None

    model_path = Path(SHARED_QWEN_MODEL_PATH)

    if not (model_path / "config.json").exists():
        if SHARED_QWEN_AUTO_DOWNLOAD and SHARED_QWEN_MODEL_NAME:
            try:
                from huggingface_hub import snapshot_download  # type: ignore

                logger.info(
                    "shared_model_service | downloading model=%s to %s",
                    SHARED_QWEN_MODEL_NAME,
                    SHARED_QWEN_MODEL_PATH,
                )
                snapshot_download(
                    repo_id=SHARED_QWEN_MODEL_NAME,
                    local_dir=SHARED_QWEN_MODEL_PATH,
                    token=HF_TOKEN,
                )
            except Exception as exc:
                logger.warning(
                    "shared_model_service | auto-download failed (%s), model disabled", exc
                )
        if not (model_path / "config.json").exists():
            logger.info(
                "shared_model_service | no local model at %s, model disabled",
                SHARED_QWEN_MODEL_PATH,
            )
            return None

    try:
        import torch  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore

        force_cpu = os.getenv("SHARED_QWEN_FORCE_CPU", "false").lower() in {"1", "true", "yes"}
        device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")

        logger.info(
            "shared_model_service | loading model=%s device=%s",
            SHARED_QWEN_MODEL_PATH,
            device,
        )
        tokenizer = AutoTokenizer.from_pretrained(
            SHARED_QWEN_MODEL_PATH,
            trust_remote_code=True,
            token=HF_TOKEN,
        )
        model = AutoModelForCausalLM.from_pretrained(
            SHARED_QWEN_MODEL_PATH,
            trust_remote_code=True,
            token=HF_TOKEN,
            torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
            low_cpu_mem_usage=True,
        )
        model = model.to(device)
        model.eval()
        logger.info("shared_model_service | model loaded successfully on %s", device)
        return {"tokenizer": tokenizer, "model": model, "device": device}
    except Exception as exc:
        logger.warning("shared_model_service | model load failed (%s), model disabled", exc)
        return None


def get_shared_qwen_diagnostics() -> dict[str, object]:
    model_path = Path(SHARED_QWEN_MODEL_PATH) if SHARED_QWEN_MODEL_PATH else None
    model_exists = bool(model_path and (model_path / "config.json").exists())
    return {
        "shared_qwen_model_path": SHARED_QWEN_MODEL_PATH or None,
        "shared_qwen_model_name": SHARED_QWEN_MODEL_NAME or None,
        "shared_qwen_auto_download": SHARED_QWEN_AUTO_DOWNLOAD,
        "shared_qwen_model_exists": model_exists,
        "shared_qwen_cached": get_shared_qwen.cache_info().currsize > 0,
    }
