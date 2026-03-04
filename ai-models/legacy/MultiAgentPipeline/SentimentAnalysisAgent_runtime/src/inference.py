"""
Sentiment Inference (V7)

Loads a trained RoBERTaSentimentModel and returns text_sentiment only.
text_urgency and keywords have been removed — they are handled by
downstream agents (Feature Engineering, Fuzzy Prioritization).

Public API (used by ml_wrapper.py via SignalExtractor):

    predictor = SentimentPredictor(model_dir)
    result = predictor.predict("The AC has been broken for three days")
    # result['text_sentiment'] -> float in [-1, +1]
"""

import torch
from transformers import RobertaTokenizer
from pathlib import Path
from dataclasses import dataclass
import time
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from model_architecture import RoBERTaSentimentModel


# ==============================================================================
# PREDICTION DATACLASS
# ==============================================================================

@dataclass
class SentimentPrediction:
    """Result returned by SentimentPredictor.predict()"""
    text_sentiment: float       # [-1, +1]
    processing_time_ms: float


# ==============================================================================
# PREDICTOR
# ==============================================================================

class SentimentPredictor:
    """
    Loads trained model and tokenizer from disk, runs inference.
    """

    def __init__(self, model_dir: str, device: str = 'cpu'):
        """
        Args:
            model_dir: Directory containing model.pt and tokenizer files
            device:    'cpu' or 'cuda'
        """
        self.device = device
        model_path = Path(model_dir)

        if not model_path.exists():
            raise ValueError(f"Model directory not found: {model_dir}")

        logger.info(f"Loading tokenizer from: {model_dir}")
        self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)

        logger.info(f"Loading model from: {model_dir}")
        self.model = RoBERTaSentimentModel()
        self.model.load_state_dict(
            torch.load(model_path / 'model.pt', map_location=device)
        )
        self.model = self.model.to(device)
        self.model.eval()

        logger.info(f"Model ready on {device}")

    def predict(self, text: str) -> dict:
        """
        Predict sentiment for a single text.

        Args:
            text: Input transcript / complaint text

        Returns:
            {
                'text_sentiment': float in [-1, +1],
                'processing_time_ms': float
            }
        """
        t0 = time.time()

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
            sentiment = self.model(input_ids, attention_mask)

        return {
            'text_sentiment': float(sentiment.item()),
            'processing_time_ms': (time.time() - t0) * 1000
        }

    def predict_batch(self, texts: list) -> list:
        """Predict sentiment for a list of texts."""
        return [self.predict(text) for text in texts]


# ==============================================================================
# SIGNAL EXTRACTOR  (backward-compatible shim for ml_wrapper.py)
# ==============================================================================

class _SignalResult:
    """Minimal result object that ml_wrapper.py accesses as result.text_sentiment."""
    def __init__(self, text_sentiment: float):
        self.text_sentiment = text_sentiment


class SignalExtractor:
    """
    Thin compatibility wrapper so ml_wrapper.py keeps working unchanged.

    ml_wrapper.py does:
        result = self.extractor.extract_signals(text)
        float(result.text_sentiment)

    or for a list:
        results = self.extractor.extract_signals(texts)
        for r in results: float(r.text_sentiment)
    """

    def __init__(self, model_dir: str, device: str = 'cpu'):
        self._predictor = SentimentPredictor(model_dir, device=device)

    def extract_signals(self, text_or_texts):
        if isinstance(text_or_texts, list):
            return [
                _SignalResult(r['text_sentiment'])
                for r in self._predictor.predict_batch(text_or_texts)
            ]
        result = self._predictor.predict(text_or_texts)
        return _SignalResult(result['text_sentiment'])


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: python inference.py <model_dir> <text>")
        print('\nExample: python inference.py models/sentiment-v7 "The AC is broken"')
        sys.exit(1)

    model_dir = sys.argv[1]
    text = " ".join(sys.argv[2:])

    predictor = SentimentPredictor(model_dir)
    result = predictor.predict(text)

    print("\n" + "=" * 60)
    print(f"Input:           {text}")
    print(f"text_sentiment:  {result['text_sentiment']:+.4f}")
    print(f"Processing time: {result['processing_time_ms']:.1f} ms")
    print("=" * 60)
