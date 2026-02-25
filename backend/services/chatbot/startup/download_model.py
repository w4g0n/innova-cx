import logging
import os
from pathlib import Path

from huggingface_hub import snapshot_download


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chatbot-model-bootstrap")


def ensure_model() -> str:
    model_source = os.environ.get("CHATBOT_MODEL_SOURCE", "tiiuae/Falcon3-1B-Instruct")
    local_dir = Path(os.environ.get("CHATBOT_MODEL_LOCAL_DIR", "/app/models/falcon3-1b-instruct"))
    hf_token = os.environ.get("HF_TOKEN") or None

    # Basic marker check to avoid re-downloading on every container restart.
    if (local_dir / "config.json").exists():
        logger.info("Using cached chatbot model at %s", local_dir)
        return str(local_dir)

    local_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading chatbot model %s to %s", model_source, local_dir)

    snapshot_download(
        repo_id=model_source,
        local_dir=str(local_dir),
        token=hf_token,
        local_dir_use_symlinks=False,
        resume_download=True,
    )
    logger.info("Chatbot model ready at %s", local_dir)
    return str(local_dir)


if __name__ == "__main__":
    print(ensure_model())
