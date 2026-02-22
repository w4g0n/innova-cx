import torch
from transformers import RobertaTokenizer
from pathlib import Path
import time
import logging
from model_architecture import RoBERTaMultiTaskModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiTaskPredictor:
    def __init__(self, model_dir: str, device: str = 'cpu'):
        self.device = device
        model_path = Path(model_dir)
        if not model_path.exists():
            raise ValueError(f"Model directory not found: {model_dir}")
        logger.info(f"📝 Loading tokenizer from: {model_dir}")
        self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)
        logger.info(f"🤖 Loading model from: {model_dir}")
        self.model = RoBERTaMultiTaskModel()
        self.model.load_state_dict(
            torch.load(model_path / 'model.pt', map_location=device)
        )
        self.model = self.model.to(device)
        self.model.eval()
        logger.info(f"✓ Model loaded on {device}")

    def predict(self, text: str) -> dict:
        start_time = time.time()
        encoding = self.tokenizer(
            text,
            max_length=128,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)
        sentiment = outputs['sentiment'].item()
        processing_time = (time.time() - start_time) * 1000
        return {
            'text_sentiment': sentiment,
            'processing_time_ms': processing_time
        }

    def predict_batch(self, texts: list) -> list:
        return [self.predict(text) for text in texts]


class MLModelWrapper:
    def __init__(self, model_dir: str, device: str = 'cpu'):
        logger.info(f"📦 Loading model from: {model_dir}")
        self.predictor = MultiTaskPredictor(model_dir, device=device)
        logger.info("✓ Model ready")

    def predict_sentiment(self, text: str) -> dict:
        result = self.predictor.predict(text)
        result['sentiment'] = result['text_sentiment']
        return result