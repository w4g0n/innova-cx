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
    "CHATBOT_MODEL_PATH", ""
).strip()
CHATBOT_MODEL_NAME = os.environ.get(
    "CHATBOT_MODEL_NAME", "Qwen/Qwen2.5-0.5B-Instruct"
).strip()
CHATBOT_AUTO_DOWNLOAD = os.environ.get("CHATBOT_AUTO_DOWNLOAD", "true").lower() in {"1", "true", "yes"}

# Legacy env var — now ignored in favour of CHATBOT_LLM_PROVIDER
CHATBOT_USE_MOCK = os.environ.get("CHATBOT_USE_MOCK", "true").lower() in {"1", "true", "yes"}

_tokenizer = None
_model = None
_model_init_attempted = False
_resolved_model_path = ""


def _model_dir_name(model_name: str) -> str:
    return (model_name or "").strip().lower().replace("/", "-")


def _is_valid_model_dir(path: Path) -> bool:
    if not path:
        return False
    if not (path / "config.json").exists():
        return False
    return any(
        (path / fname).exists()
        for fname in ("model.safetensors", "pytorch_model.bin", "pytorch_model.bin.index.json")
    )


def _resolve_model_path() -> str:
    """
    Resolve model directory in this order:
    1) Explicit CHATBOT_MODEL_PATH
    2) Common cache/model locations derived from CHATBOT_MODEL_NAME
    """
    explicit = CHATBOT_MODEL_PATH.strip()
    if explicit:
        return explicit

    hf_home = os.environ.get("HF_HOME", "/app/hf_cache").strip() or "/app/hf_cache"
    slug = _model_dir_name(CHATBOT_MODEL_NAME)
    candidates = [
        Path(hf_home) / slug,
        Path("/app/hf_cache") / slug,
        Path("/app/models/chatbot") / slug,
        Path("/app/models/chatbot"),
    ]

    for candidate in candidates:
        if _is_valid_model_dir(candidate):
            logger.info("chatbot_llm | discovered local model at %s", candidate)
            return str(candidate)
    return ""


# ── Public helpers ───────────────────────────────────────────────────────────

def llm_available() -> bool:
    """Returns True if a real LLM is loaded and ready for inference."""
    if CHATBOT_LLM_PROVIDER == "template":
        return False
    _init_model_once()
    return _model is not None and _tokenizer is not None


def get_llm_diagnostics() -> dict[str, Any]:
    model_path = _resolved_model_path or _resolve_model_path()
    local_model_exists = bool(model_path and _is_valid_model_dir(Path(model_path)))
    return {
        "chatbot_llm_provider": CHATBOT_LLM_PROVIDER,
        "chatbot_model_path": model_path or None,
        "chatbot_model_name": CHATBOT_MODEL_NAME or None,
        "chatbot_auto_download": CHATBOT_AUTO_DOWNLOAD,
        "chatbot_local_model_exists": local_model_exists,
        "chatbot_model_loaded": _model is not None and _tokenizer is not None,
        "chatbot_quantization": QUANTIZATION,
        "chatbot_max_new_tokens": MAX_NEW_TOKENS,
        "chatbot_mode": "model" if (_model is not None and _tokenizer is not None) else "mock",
    }


# ── Model loading ────────────────────────────────────────────────────────────

def _init_model_once() -> None:
    global _tokenizer, _model, _model_init_attempted, _resolved_model_path

    if _model_init_attempted:
        return
    _model_init_attempted = True

    if CHATBOT_LLM_PROVIDER == "template":
        logger.info("chatbot_llm | provider=template, no model to load")
        return

    model_path_str = _resolve_model_path()
    if not model_path_str:
        # No explicit path and no discovered local model: choose default cache target
        # for optional auto-download; otherwise fall back to template/rule generator.
        hf_home = os.environ.get("HF_HOME", "/app/hf_cache").strip() or "/app/hf_cache"
        model_path_str = str(Path(hf_home) / _model_dir_name(CHATBOT_MODEL_NAME))

    model_path = Path(model_path_str)
    _resolved_model_path = model_path_str
    if not _is_valid_model_dir(model_path) and CHATBOT_AUTO_DOWNLOAD and CHATBOT_MODEL_NAME:
        try:
            from huggingface_hub import snapshot_download

            logger.info("chatbot_llm | downloading model=%s to %s", CHATBOT_MODEL_NAME, model_path_str)
            snapshot_download(
                repo_id=CHATBOT_MODEL_NAME,
                local_dir=model_path_str,
                token=HF_TOKEN,
            )
        except Exception as exc:
            logger.warning("chatbot_llm | auto-download failed (%s), falling back to template mode", exc)

    if not _is_valid_model_dir(model_path):
        logger.warning(
            "chatbot_llm | no local model found at %s (missing config.json), falling back to template mode",
            model_path_str,
        )
        return

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_name = model_path_str
        logger.info("chatbot_llm | loading local model %s (quantization=%s)", model_name, QUANTIZATION)

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

    def _clean_context_lines(ctx: str) -> list[str]:
        lines = [ln.strip().lstrip("- ").strip() for ln in ctx.split("\n") if ln.strip()]
        cleaned = []
        for ln in lines:
            low = ln.lower()
            if low.startswith(("agent:", "caller:", "tenant:")):
                ln = ln.split(":", 1)[1].strip()
                low = ln.lower()
            if "industrial park leasing desk" in low and "good morning" in low:
                continue
            if len(ln) < 8:
                continue
            cleaned.append(ln)
        return cleaned

    # If system prompt contains KB context, use it as the answer
    if "Context:" in system_msg:
        context = system_msg.split("Context:")[-1].strip()
        lines = _clean_context_lines(context)
        if lines:
            combined = " ".join(lines).lower()
            user_low = user_msg.lower()
            if any(x in user_low for x in ("cost", "price", "pricing", "rent", "quote", "how much")):
                return (
                    "Pricing depends on unit type, location, size, and lease terms. "
                    "I can help prepare a quote if you share your preferred asset type, location, and approximate square footage."
                )
            if "parking" in user_low and "parking" in combined:
                return (
                    "Parking is typically allocated based on unit size. "
                    "If you share the unit size, I can help estimate expected parking allocation."
                )
            return lines[0][:420]

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
