"""
Simplified ML Inference Wrapper

Provides a simple Python interface for model inference.
Other team members will wrap this in their API layer.

No FastAPI - just pure inference functions.
"""

import torch
from pathlib import Path
from typing import Union, List, Dict
import logging
import time
from dataclasses import dataclass

from inference import SignalExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# SIMPLIFIED INFERENCE CLASS
# ==============================================================================

class MLModelWrapper:
    """
    Simplified wrapper for ML model inference.
    
    This is what other team members will use in their API.
    No FastAPI, no HTTP - just pure Python functions.
    """
    
    def __init__(self, model_path: str, device: str = 'cpu'):
        """
        Initialize the model wrapper.
        
        Args:
            model_path: Path to trained model directory
            device: 'cpu' or 'cuda'
        """
        logger.info("📂 Loading ML model...")
        start_time = time.perf_counter()
        
        self.extractor = SignalExtractor(model_path, device=device)
        self.model_path = model_path
        self.device = device
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"✅ Model loaded in {elapsed_ms:.0f}ms")
    
    def predict_sentiment(self, text: str) -> Dict[str, float]:
        """
        Predict sentiment from text.
        
        Args:
            text: Complaint transcript text
            
        Returns:
            Dict with 'sentiment' score (-1 to 1)
            
        Example:
            >>> model = MLModelWrapper('models/sentiment-production')
            >>> result = model.predict_sentiment("AC is broken")
            >>> print(result['sentiment'])  # -0.42
        """
        if not text or not text.strip():
            raise ValueError("❌ Text cannot be empty")
        
        start_time = time.perf_counter()
        result = self.extractor.extract_signals(text.strip())
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            'sentiment': float(result.text_sentiment),
            'processing_time_ms': elapsed_ms
        }
    
    def predict_batch(self, texts: List[str]) -> List[Dict[str, float]]:
        """
        Predict sentiment for multiple texts (faster than individual calls).
        
        Args:
            texts: List of complaint transcripts
            
        Returns:
            List of dicts with sentiment scores
            
        Example:
            >>> texts = ["AC broken", "Thank you", "Emergency!"]
            >>> results = model.predict_batch(texts)
            >>> for r in results:
            ...     print(r['sentiment'])
        """
        if not texts:
            raise ValueError("❌ Texts list cannot be empty")
        
        # Validate all texts
        clean_texts = []
        for text in texts:
            if not text or not text.strip():
                raise ValueError("❌ All texts must be non-empty")
            clean_texts.append(text.strip())
        
        start_time = time.perf_counter()
        results = self.extractor.extract_signals(clean_texts)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        if not isinstance(results, list):
            results = [results]
        
        return [
            {
                'sentiment': float(r.text_sentiment),
                'processing_time_ms': elapsed_ms / len(results)
            }
            for r in results
        ]


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def categorize_sentiment(score: float) -> str:
    """
    Convert sentiment score to human-readable category.
    
    Args:
        score: Sentiment score from -1 to 1
        
    Returns:
        Category string: 'very_negative', 'negative', 'neutral', 'positive', 'very_positive'
    """
    if score < -0.6:
        return "very_negative"
    elif score < -0.2:
        return "negative"
    elif score < 0.2:
        return "neutral"
    elif score < 0.6:
        return "positive"
    else:
        return "very_positive"


# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python ml_wrapper.py <model_path> [text]")
        print("Example: python ml_wrapper.py models/sentiment-production \"AC is broken\"")
        sys.exit(1)
    
    model_path = sys.argv[1]
    
    # Load model
    logger.info("="*60)
    model = MLModelWrapper(model_path)
    logger.info("="*60)
    
    # Test texts
    test_texts = [
        "The air conditioning is broken and it's very uncomfortable",
        "This is unacceptable! We've been calling for days!",
        "Thank you for the quick response, appreciate your help",
        "I need to report an emergency - water flooding storage area"
    ]
    
    # Override with CLI text if provided
    if len(sys.argv) > 2:
        test_texts = [' '.join(sys.argv[2:])]
    
    logger.info(f"\n🧪 Testing ML Model\n")
    
    # Single predictions
    for i, text in enumerate(test_texts, 1):
        logger.info(f"{i}. Text: {text}")
        
        try:
            result = model.predict_sentiment(text)
            sentiment = result['sentiment']
            category = categorize_sentiment(sentiment)
            
            logger.info(f"   Sentiment: {sentiment:.3f} ({category})")
            logger.info(f"   Time: {result['processing_time_ms']:.1f}ms\n")
        except Exception as e:
            logger.error(f"   ❌ Error: {e}\n")
    
    # Batch prediction
    logger.info("\n🚀 Testing Batch Processing")
    try:
        batch_results = model.predict_batch(test_texts)
        logger.info(f"✓ Processed {len(batch_results)} samples in batch\n")
        
        for text, result in zip(test_texts, batch_results):
            sentiment = result['sentiment']
            category = categorize_sentiment(sentiment)
            logger.info(f"{text[:50]}...")
            logger.info(f"  → {sentiment:.3f} ({category})\n")
    except Exception as e:
        logger.error(f"❌ Batch error: {e}")
    
    logger.info("✅ Testing complete!")
