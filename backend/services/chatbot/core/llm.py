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

logger.info(f"Loading model: {MODEL_NAME} ...")

_tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    token=HF_TOKEN,
)

_model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    token=HF_TOKEN,
    dtype=torch.bfloat16,
)

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
        output_ids = _model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=DO_SAMPLE,
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )

    # Decode only the newly generated tokens (strip the prompt)
    generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    response = _tokenizer.decode(generated_ids, skip_special_tokens=True).strip()

    return response
