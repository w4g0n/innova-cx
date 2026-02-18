"""
Multi-Task Inference

Predicts 3 things from text:
1. text_sentiment: -1 to +1
2. text_urgency: 0 to 1
3. keywords: List of extracted keywords

This REPLACES your current inference.py
"""

import torch
from transformers import RobertaTokenizer
from pathlib import Path
import time
import logging
from model_architecture import RoBERTaMultiTaskModel, keyword_indices_to_words

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# INFERENCE CLASS
# ==============================================================================

class MultiTaskPredictor:
    """
    Loads trained model and predicts sentiment, urgency, and keywords.
    """
    
    def __init__(
        self,
        model_dir: str,
        device: str = 'cpu',
        keyword_threshold: float = 0.5
    ):
        """
        Initialize predictor.
        
        Args:
            model_dir: Directory with model.pt and tokenizer files
            device: 'cpu' or 'cuda'
            keyword_threshold: Probability threshold for keyword extraction
        """
        self.device = device
        self.keyword_threshold = keyword_threshold
        
        model_path = Path(model_dir)
        if not model_path.exists():
            raise ValueError(f"❌ Model directory not found: {model_dir}")
        
        # Load tokenizer
        logger.info(f"📝 Loading tokenizer from: {model_dir}")
        self.tokenizer = RobertaTokenizer.from_pretrained(model_dir)
        
        # Load model
        logger.info(f"🤖 Loading model from: {model_dir}")
        self.model = RoBERTaMultiTaskModel()
        self.model.load_state_dict(
            torch.load(model_path / 'model.pt', map_location=device)
        )
        self.model = self.model.to(device)
        self.model.eval()
        
        logger.info(f"✓ Model loaded on {device}")
    
    def predict(self, text: str) -> dict:
        """
        Predict sentiment, urgency, and keywords for text.
        
        Args:
            text: Input complaint text
        
        Returns:
            {
                'text_sentiment': float in [-1, 1],
                'text_urgency': float in [0, 1],
                'keywords': list of strings,
                'keyword_scores': dict {keyword: probability},
                'processing_time_ms': float
            }
        """
        start_time = time.time()
        
        # Tokenize
        encoding = self.tokenizer(
            text,
            max_length=128,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        input_ids = encoding['input_ids'].to(self.device)
        attention_mask = encoding['attention_mask'].to(self.device)
        
        # Predict
        with torch.no_grad():
            outputs = self.model(input_ids, attention_mask)
        
        # Extract outputs
        sentiment = outputs['sentiment'].item()
        urgency = outputs['urgency'].item()
        keyword_probs = outputs['keywords'][0].cpu().numpy()  # [50]
        
        # Extract keywords above threshold
        keyword_indices = [i for i, prob in enumerate(keyword_probs) 
                          if prob >= self.keyword_threshold]
        keywords = keyword_indices_to_words(keyword_indices)
        
        # Keyword scores dict
        keyword_scores = {
            keyword_indices_to_words([i])[0]: float(keyword_probs[i])
            for i in range(len(keyword_probs))
            if keyword_probs[i] >= self.keyword_threshold
        }
        
        processing_time = (time.time() - start_time) * 1000  # ms
        
        return {
            'text_sentiment': sentiment,
            'text_urgency': urgency,
            'keywords': keywords,
            'keyword_scores': keyword_scores,
            'processing_time_ms': processing_time
        }
    
    def predict_batch(self, texts: list) -> list:
        """Predict for multiple texts"""
        return [self.predict(text) for text in texts]


# ==============================================================================
# SIMPLIFIED API (Like your current ml_wrapper.py)
# ==============================================================================

class MLModelWrapper:
    """
    Simplified wrapper compatible with your existing code.
    
    Usage:
        model = MLModelWrapper('models/multi-task-model')
        result = model.predict_sentiment("The AC is broken")
        
        # result = {
        #     'text_sentiment': -0.75,
        #     'text_urgency': 0.82,
        #     'keywords': ["AC", "broken"],
        #     'processing_time_ms': 21.5
        # }
    """
    
    def __init__(self, model_dir: str, device: str = 'cpu'):
        logger.info(f"📦 Loading model from: {model_dir}")
        self.predictor = MultiTaskPredictor(model_dir, device=device)
        logger.info("✓ Model ready")
    
    def predict_sentiment(self, text: str) -> dict:
        """
        Predict sentiment + urgency + keywords.
        
        Returns:
            {
                'sentiment': float (backward compatible),
                'text_sentiment': float,
                'text_urgency': float,
                'keywords': list,
                'processing_time_ms': float
            }
        """
        result = self.predictor.predict(text)
        
        # Add backward-compatible 'sentiment' key
        result['sentiment'] = result['text_sentiment']
        
        return result


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("\nUsage: python inference_UPDATED.py <model_dir> <text>")
        print("\nExample:")
        print('  python inference_UPDATED.py models/multi-task-model "The AC is broken"')
        print()
        sys.exit(1)
    
    model_dir = sys.argv[1]
    text = sys.argv[2]
    
    # Load model
    predictor = MultiTaskPredictor(model_dir)
    
    # Predict
    print("\n" + "="*70)
    print("Multi-Task Inference")
    print("="*70)
    print(f"\nInput: {text}")
    print("\nPredicting...")
    
    result = predictor.predict(text)
    
    print("\n" + "="*70)
    print("Results:")
    print("="*70)
    print(f"\n💭 Sentiment:  {result['text_sentiment']:+.3f}", end="")
    if result['text_sentiment'] < -0.6:
        print("  (very negative)")
    elif result['text_sentiment'] < -0.2:
        print("  (negative)")
    elif result['text_sentiment'] < 0.2:
        print("  (neutral)")
    elif result['text_sentiment'] < 0.6:
        print("  (positive)")
    else:
        print("  (very positive)")
    
    print(f"🚨 Urgency:    {result['text_urgency']:.3f}", end="")
    if result['text_urgency'] < 0.4:
        print("  (low)")
    elif result['text_urgency'] < 0.7:
        print("  (medium)")
    else:
        print("  (high)")
    
    print(f"\n🏷️ Keywords:   {', '.join(result['keywords']) if result['keywords'] else 'None'}")
    
    if result['keyword_scores']:
        print("\n📊 Keyword Scores:")
        for keyword, score in sorted(result['keyword_scores'].items(), 
                                     key=lambda x: x[1], reverse=True):
            print(f"   {keyword}: {score:.2f}")
    
    print(f"\n⚡ Processing:  {result['processing_time_ms']:.1f}ms")
    print("\n" + "="*70)
