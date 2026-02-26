import os
import logging
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

logger = logging.getLogger(__name__)

MODEL_NAME = os.environ.get("CHATBOT_MODEL", "tiiuae/Falcon3-1B-Instruct")
HF_TOKEN = os.environ.get("HF_TOKEN") or None
MAX_NEW_TOKENS = int(os.environ.get("CHATBOT_MAX_NEW_TOKENS", "96"))
DO_SAMPLE = os.environ.get("CHATBOT_DO_SAMPLE", "true").lower() == "true"
TEMPERATURE = float(os.environ.get("CHATBOT_TEMPERATURE", "0.7"))
TOP_P = float(os.environ.get("CHATBOT_TOP_P", "0.9"))
QUANTIZATION = os.environ.get("CHATBOT_QUANTIZATION", "none").strip().lower()

logger.info(f"Loading model: {MODEL_NAME} ...")

_tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    token=HF_TOKEN,
)

def _load_model():
    use_cuda = torch.cuda.is_available()
    model_kwargs = {
        "token": HF_TOKEN,
        "torch_dtype": torch.bfloat16 if use_cuda else torch.float32,
    }

    # bitsandbytes quantization works best with CUDA GPUs.
    if QUANTIZATION in {"4bit", "8bit"}:
        if not use_cuda:
            logger.warning("Quantization '%s' requested but CUDA is unavailable; loading without quantization.", QUANTIZATION)
        else:
            try:
                from transformers import BitsAndBytesConfig

                if QUANTIZATION == "4bit":
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
                else:
                    model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                model_kwargs["device_map"] = "auto"
                logger.info("Loading model with bitsandbytes quantization: %s", QUANTIZATION)
            except Exception as exc:
                logger.warning("Failed to enable quantization '%s'; falling back to normal load. err=%s", QUANTIZATION, exc)

    return AutoModelForCausalLM.from_pretrained(MODEL_NAME, **model_kwargs)


_model = _load_model()

logger.info("Model loaded.")


def generate_response(messages: list[dict]) -> str:
    """
    Generate a response from a list of chat messages.

    Args:
        messages: List of dicts with 'role' and 'content' keys.
                  e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
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

    # Decode only the newly generated tokens (strip the prompt)
    generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    response = _tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    return response
