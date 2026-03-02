import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MAX_NEW_TOKENS = int(os.environ.get("CHATBOT_MAX_NEW_TOKENS", "96"))
DO_SAMPLE = os.environ.get("CHATBOT_DO_SAMPLE", "true").lower() == "true"
TEMPERATURE = float(os.environ.get("CHATBOT_TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("CHATBOT_TOP_P", "0.9"))
QUANTIZATION = os.environ.get("CHATBOT_QUANTIZATION", "none").strip().lower()
HF_TOKEN = os.environ.get("HF_TOKEN") or None

CHATBOT_MODEL_PATH = os.environ.get("CHATBOT_MODEL_PATH", "").strip()
CHATBOT_USE_MOCK = os.environ.get("CHATBOT_USE_MOCK", "true").lower() in {"1", "true", "yes"}

_tokenizer = None
_model = None
_model_init_attempted = False


def _model_enabled() -> bool:
    return bool(CHATBOT_MODEL_PATH and (Path(CHATBOT_MODEL_PATH) / "config.json").exists())


def get_llm_diagnostics() -> dict[str, Any]:
    model_exists = _model_enabled()
    mode = "model" if model_exists and not CHATBOT_USE_MOCK else "mock"
    return {
        "chatbot_model_path": CHATBOT_MODEL_PATH or None,
        "chatbot_model_exists": model_exists,
        "chatbot_use_mock": CHATBOT_USE_MOCK,
        "chatbot_mode": mode,
        "chatbot_model_loaded": _model is not None and _tokenizer is not None,
    }


def _init_model_once() -> None:
    global _tokenizer, _model, _model_init_attempted

    if _model_init_attempted:
        return
    _model_init_attempted = True

    if CHATBOT_USE_MOCK:
        logger.info("chatbot_llm | CHATBOT_USE_MOCK=true, skipping heavy model load")
        return
    if not _model_enabled():
        logger.info("chatbot_llm | no valid CHATBOT_MODEL_PATH, using mock responses")
        return

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = CHATBOT_MODEL_PATH
    logger.info("chatbot_llm | loading model from %s", model_name)
    _tokenizer = AutoTokenizer.from_pretrained(model_name, token=HF_TOKEN)

    use_cuda = torch.cuda.is_available()
    model_kwargs = {
        "token": HF_TOKEN,
        "torch_dtype": torch.bfloat16 if use_cuda else torch.float32,
    }

    if QUANTIZATION in {"4bit", "8bit"}:
        if not use_cuda:
            logger.warning(
                "chatbot_llm | quantization '%s' requested but CUDA unavailable; loading without quantization",
                QUANTIZATION,
            )
        else:
            try:
                from transformers import BitsAndBytesConfig

                if QUANTIZATION == "4bit":
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch.bfloat16,
                    )
                else:
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                model_kwargs["device_map"] = "auto"
                logger.info("chatbot_llm | loading with quantization=%s", QUANTIZATION)
            except Exception as exc:
                logger.warning("chatbot_llm | quantization setup failed (%s), continuing without", exc)

    _model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
    logger.info("chatbot_llm | model loaded")


def _mock_response(messages: list[dict]) -> str:
    user_msg = ""
    for msg in reversed(messages or []):
        if str(msg.get("role", "")).lower() == "user":
            user_msg = str(msg.get("content", "")).strip()
            break
    if not user_msg:
        return "I can help with that. Please share the key ticket details."
    return (
        "Mock mode is active (no local LLM model path configured). "
        f"Captured request: {user_msg[:220]}"
    )


def generate_response(messages: list[dict]) -> str:
    _init_model_once()
    if _model is None or _tokenizer is None:
        return _mock_response(messages)

    import torch

    text = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = _tokenizer([text], return_tensors="pt").to(_model.device)
    with torch.no_grad():
        gen_kwargs = {
            "max_new_tokens": MAX_NEW_TOKENS,
            "do_sample": DO_SAMPLE,
        }
        if DO_SAMPLE:
            gen_kwargs["temperature"] = TEMPERATURE
            gen_kwargs["top_p"] = TOP_P
        output_ids = _model.generate(**inputs, **gen_kwargs)

    generated_ids = output_ids[0][inputs["input_ids"].shape[1] :]
    response = _tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    return response or _mock_response(messages)
