import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chatbot-model-bootstrap")


def ensure_model() -> str:
    model_path = Path(os.environ.get("CHATBOT_MODEL_PATH", "").strip())
    if model_path and (model_path / "config.json").exists():
        logger.info("Using provided local chatbot model at %s", model_path)
        return str(model_path)
    logger.info("No local chatbot model path provided. Mock mode will be used.")
    return ""


if __name__ == "__main__":
    print(ensure_model())
