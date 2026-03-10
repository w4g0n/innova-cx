import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("chatbot-model-bootstrap")
CHATBOT_SERVICE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CHATBOT_MODEL_PATH = CHATBOT_SERVICE_DIR / "model"


def ensure_model() -> str:
    model_path = Path(os.environ.get("CHATBOT_MODEL_PATH", str(DEFAULT_CHATBOT_MODEL_PATH)).strip())
    if model_path and (model_path / "config.json").exists():
        logger.info("Using provided local chatbot model at %s", model_path)
        return str(model_path)
    logger.info("No local chatbot model found at %s. Template mode will be used.", model_path)
    return ""


if __name__ == "__main__":
    print(ensure_model())
