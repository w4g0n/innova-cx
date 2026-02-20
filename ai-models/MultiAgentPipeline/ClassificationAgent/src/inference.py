"""
Classification Agent — Inference
=================================

Public API:
    predictor = CallClassificationPredictor(model_dir)
    result = predictor.classify("Hi I need to find office space urgently")

    result.classification      → "inquiry"
    result.confidence          → 0.94
    result.complaint_score     → 0.06
    result.inquiry_score       → 0.94

Pipeline routing logic (matches Jan 16 meeting decision):
    confidence >= 0.75  → route automatically
    confidence <  0.75  → flag for chatbot to ask clarifying question

Pipeline position:
    Whisper → [ClassificationAgent] → complaint path  → SentimentAgent → DSPy
                                    ↘ inquiry path    → Chatbot / FAQ
                                    ↘ low confidence  → Chatbot clarification
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from transformers import RobertaTokenizer
from dataclasses import dataclass
from pathlib import Path
import time
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from model_architecture import CallClassifier, COMPLAINT_LABEL, INQUIRY_LABEL

CONFIDENCE_THRESHOLD = 0.75


# ==============================================================================
# RESULT DATACLASS
# ==============================================================================

@dataclass
class ClassificationResult:
    """
    Typed result returned by CallClassificationPredictor.classify().

    Fields:
        classification:   "complaint" or "inquiry"
        confidence:       probability of the predicted class  [0.0 – 1.0]
        complaint_score:  raw probability for complaint class [0.0 – 1.0]
        inquiry_score:    raw probability for inquiry class   [0.0 – 1.0]
        low_confidence:   True if confidence < CONFIDENCE_THRESHOLD (0.75)
                          When True the pipeline coordinator should ask a
                          clarifying question before routing.
        processing_time_ms: wall-clock inference time
    """
    classification:      str
    confidence:          float
    complaint_score:     float
    inquiry_score:       float
    low_confidence:      bool
    processing_time_ms:  float


# ==============================================================================
# PREDICTOR
# ==============================================================================

class CallClassificationPredictor:
    """
    Loads a trained CallClassifier and exposes classify() for the pipeline.
    """

    def __init__(self, model_dir: str, device: str = "cpu"):
        """
        Args:
            model_dir: Directory containing model.pt and tokenizer files
                       (saved by train.py)
            device:    'cpu' or 'cuda'
        """
        self.device = device
        model_path = Path(model_dir)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        logger.info(f"Loading tokenizer from: {model_dir}")
        self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)

        logger.info(f"Loading model from: {model_dir}")
        self.model = CallClassifier()
        self.model.load_state_dict(
            torch.load(model_path / "model.pt", map_location=device)
        )
        self.model = self.model.to(device)
        self.model.eval()

        logger.info(f"CallClassificationPredictor ready on {device}")

    def classify(self, text: str) -> ClassificationResult:
        """
        Classify a single transcript.

        Args:
            text: Raw transcript text (full dialogue or extracted tenant speech)

        Returns:
            ClassificationResult with classification, confidence, scores
        """
        t0 = time.time()

        enc = self.tokenizer(
            text,
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        input_ids      = enc["input_ids"].to(self.device)
        attention_mask = enc["attention_mask"].to(self.device)

        with torch.no_grad():
            logits = self.model(input_ids, attention_mask)   # [1, 2]
            probs  = F.softmax(logits, dim=1).squeeze(0)     # [2]

        complaint_score = float(probs[COMPLAINT_LABEL].item())
        inquiry_score   = float(probs[INQUIRY_LABEL].item())

        predicted_label = int(probs.argmax().item())
        confidence      = float(probs[predicted_label].item())

        classification  = "complaint" if predicted_label == COMPLAINT_LABEL else "inquiry"
        low_confidence  = confidence < CONFIDENCE_THRESHOLD

        return ClassificationResult(
            classification=classification,
            confidence=confidence,
            complaint_score=complaint_score,
            inquiry_score=inquiry_score,
            low_confidence=low_confidence,
            processing_time_ms=(time.time() - t0) * 1000,
        )

    def classify_batch(self, texts: list[str]) -> list[ClassificationResult]:
        """Classify a list of transcripts sequentially."""
        return [self.classify(t) for t in texts]


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: python inference.py <model_dir> <text>")
        print('\nExample: python inference.py models/classifier-v1 "The AC is broken"')
        sys.exit(1)

    model_dir = sys.argv[1]
    text      = " ".join(sys.argv[2:])

    predictor = CallClassificationPredictor(model_dir)
    result    = predictor.classify(text)

    print("\n" + "=" * 60)
    print(f"Input:            {text}")
    print(f"Classification:   {result.classification}")
    print(f"Confidence:       {result.confidence:.4f}")
    print(f"Complaint score:  {result.complaint_score:.4f}")
    print(f"Inquiry score:    {result.inquiry_score:.4f}")
    print(f"Low confidence:   {result.low_confidence}")
    print(f"Processing time:  {result.processing_time_ms:.1f} ms")
    print("=" * 60)
