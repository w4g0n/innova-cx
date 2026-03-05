import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

# Provider: "template" (default, no LLM) | "local" (transformers model)
CHATBOT_LLM_PROVIDER = os.environ.get("CHATBOT_LLM_PROVIDER", "template").strip().lower()

MAX_NEW_TOKENS = int(os.environ.get("CHATBOT_MAX_NEW_TOKENS", "128"))
DO_SAMPLE = os.environ.get("CHATBOT_DO_SAMPLE", "true").lower() == "true"
TEMPERATURE = float(os.environ.get("CHATBOT_TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("CHATBOT_TOP_P", "0.9"))
QUANTIZATION = os.environ.get("CHATBOT_QUANTIZATION", "4bit").strip().lower()
HF_TOKEN = os.environ.get("HF_TOKEN") or None

CHATBOT_MODEL_PATH = os.environ.get(
    "CHATBOT_MODEL_PATH", "Qwen/Qwen2.5-0.5B-Instruct"
).strip()

# Legacy env var — now ignored in favour of CHATBOT_LLM_PROVIDER
CHATBOT_USE_MOCK = os.environ.get("CHATBOT_USE_MOCK", "true").lower() in {"1", "true", "yes"}

_tokenizer = None
_model = None
_model_init_attempted = False


# ── Public helpers ───────────────────────────────────────────────────────────

def llm_available() -> bool:
    """Returns True if a real LLM is loaded and ready for inference."""
    if CHATBOT_LLM_PROVIDER == "template":
        return False
    _init_model_once()
    return _model is not None and _tokenizer is not None


def get_llm_diagnostics() -> dict[str, Any]:
    return {
        "chatbot_llm_provider": CHATBOT_LLM_PROVIDER,
        "chatbot_model_path": CHATBOT_MODEL_PATH or None,
        "chatbot_model_loaded": _model is not None and _tokenizer is not None,
        "chatbot_quantization": QUANTIZATION,
        "chatbot_max_new_tokens": MAX_NEW_TOKENS,
    }


# ── Model loading ────────────────────────────────────────────────────────────

def _init_model_once() -> None:
    global _tokenizer, _model, _model_init_attempted

    if _model_init_attempted:
        return
    _model_init_attempted = True

    if CHATBOT_LLM_PROVIDER == "template":
        logger.info("chatbot_llm | provider=template, no model to load")
        return

    if not CHATBOT_MODEL_PATH:
        logger.warning("chatbot_llm | CHATBOT_MODEL_PATH is empty, falling back to template mode")
        return

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_name = CHATBOT_MODEL_PATH
        logger.info("chatbot_llm | loading model %s (quantization=%s)", model_name, QUANTIZATION)

        _tokenizer = AutoTokenizer.from_pretrained(model_name, token=HF_TOKEN, trust_remote_code=True)

        use_cuda = torch.cuda.is_available()
        model_kwargs: dict[str, Any] = {
            "token": HF_TOKEN,
            "trust_remote_code": True,
            "torch_dtype": torch.bfloat16 if use_cuda else torch.float32,
        }

        if QUANTIZATION in {"4bit", "8bit"} and use_cuda:
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
                logger.info("chatbot_llm | quantization=%s enabled", QUANTIZATION)
            except Exception as exc:
                logger.warning("chatbot_llm | quantization setup failed (%s), loading without", exc)
        elif not use_cuda:
            logger.info("chatbot_llm | CUDA unavailable, loading in float32 on CPU")

        _model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        if not use_cuda and not hasattr(_model, "hf_device_map"):
            _model = _model.to("cpu")

        logger.info("chatbot_llm | model loaded successfully")

    except Exception as exc:
        logger.error("chatbot_llm | failed to load model: %s", exc)
        _model = None
        _tokenizer = None


# ── Template response ────────────────────────────────────────────────────────

def _template_response(messages: list[dict]) -> str:
    """
    Generate a response without an LLM by extracting context from the system
    prompt and formatting it as a helpful answer.
    """
    system_msg = ""
    user_msg = ""
    for msg in messages:
        role = str(msg.get("role", "")).lower()
        content = str(msg.get("content", "")).strip()
        if role == "system":
            system_msg = content
        elif role == "user":
            user_msg = content  # last user message

    # If system prompt contains KB context, use it as the answer
    if "Context:" in system_msg:
        context = system_msg.split("Context:")[-1].strip()
        # Clean up the context for a natural response
        lines = [ln.strip().lstrip("- ") for ln in context.split("\n") if ln.strip()]
        if lines:
            best = lines[0][:500]
            return (
                f"Based on our records: {best}\n\n"
                "Is there anything else you would like to know?"
            )

    # If system prompt contains guidelines/context
    if "Guidelines:" in system_msg:
        return (
            "I understand your frustration and I sincerely apologise for the inconvenience. "
            "Your concern is important to us and I want to make sure it is addressed properly. "
            "Could you please describe the issue in detail so I can create a support ticket for you?"
        )

    # De-escalation template
    if "empathy" in system_msg.lower() or "acknowledge" in system_msg.lower():
        return (
            "I completely understand how frustrating this must be, and I am truly sorry "
            "for the inconvenience you are experiencing. Your concern is valid and important "
            "to us. I want to make sure we address this properly."
        )

    # Generic helpful response
    return (
        "I understand your concern. Let me help you with that. "
        "Could you provide more details so I can assist you better?"
    )


# ── Local model response ─────────────────────────────────────────────────────

def _local_model_response(messages: list[dict]) -> str:
    _init_model_once()
    if _model is None or _tokenizer is None:
        return _template_response(messages)

    import torch

    text = _tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = _tokenizer([text], return_tensors="pt").to(_model.device)
    with torch.no_grad():
        gen_kwargs: dict[str, Any] = {
            "max_new_tokens": MAX_NEW_TOKENS,
            "do_sample": DO_SAMPLE,
        }
        if DO_SAMPLE:
            gen_kwargs["temperature"] = TEMPERATURE
            gen_kwargs["top_p"] = TOP_P
        output_ids = _model.generate(**inputs, **gen_kwargs)

    generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    response = _tokenizer.decode(generated_ids, skip_special_tokens=True).strip()
    return response or _template_response(messages)


# ── Public API ───────────────────────────────────────────────────────────────

def generate_response(messages: list[dict]) -> str:
    """
    Generate a chatbot response using the configured provider.
    - template: fast rule-based/KB responses (~1ms)
    - local: Qwen2.5-0.5B-Instruct or other HF model
    """
    if CHATBOT_LLM_PROVIDER == "local":
        return _local_model_response(messages)
    return _template_response(messages)
