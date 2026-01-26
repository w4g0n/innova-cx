"""
Inference Pipeline for InnovaCX Signal Extraction

Production-ready prediction interface with fail-fast validation and observability.

Principles Applied:
- Fail-Fast: Validate inputs immediately
- Parse Don't Validate: Typed prediction results
- Single Responsibility: Each method has ONE job
- Guard Clauses: Early returns for invalid states
- Observability: Structured logging and timing
- Immutability: Config frozen after load
"""

import torch
import torch.nn as nn
from transformers import RobertaTokenizer
from pathlib import Path
from typing import Dict, List, Union, Optional
from dataclasses import dataclass
import json
import logging
import time
import numpy as np

from model_architecture import create_model

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# PREDICTION RESULT TYPES (Parse, Don't Validate)
# ==============================================================================

@dataclass(frozen=True)  # Immutability
class SentimentPrediction:
    """
    Validated sentiment prediction result.
    Type proves validity.
    """
    text_sentiment: float
    
    def __post_init__(self):
        """Fail-fast: Enforce invariants"""
        if not -1.0 <= self.text_sentiment <= 1.0:
            raise ValueError(
                f"❌ Sentiment must be in [-1, 1], got {self.text_sentiment}"
            )


@dataclass(frozen=True)
class UrgencyPrediction:
    """Validated urgency prediction result"""
    text_urgency: float
    
    def __post_init__(self):
        """Fail-fast validation"""
        if not 0.0 <= self.text_urgency <= 1.0:
            raise ValueError(
                f"❌ Urgency must be in [0, 1], got {self.text_urgency}"
            )


@dataclass(frozen=True)
class MultiTaskPrediction:
    """Validated multi-task prediction result"""
    text_sentiment: float
    text_urgency: float
    predicted_severity: str
    predicted_impact: str
    
    def __post_init__(self):
        """Fail-fast validation"""
        if not -1.0 <= self.text_sentiment <= 1.0:
            raise ValueError(f"❌ Sentiment out of range")
        
        if not 0.0 <= self.text_urgency <= 1.0:
            raise ValueError(f"❌ Urgency out of range")
        
        valid_severities = ['low', 'medium', 'high', 'critical']
        if self.predicted_severity not in valid_severities:
            raise ValueError(f"❌ Invalid severity: {self.predicted_severity}")
        
        valid_impacts = ['low', 'medium', 'medium-high', 'high']
        if self.predicted_impact not in valid_impacts:
            raise ValueError(f"❌ Invalid impact: {self.predicted_impact}")


# ==============================================================================
# MODEL CONFIGURATION
# ==============================================================================

@dataclass  # Note: Not frozen due to validation needing field access
class InferenceConfig:
    """
    Validated inference configuration.
    Loaded from saved model directory.
    
    Note: Not frozen to allow __post_init__ validation.
    Treat as immutable in practice.
    """
    task: str
    max_length: int
    model_path: Path
    device: str
    
    def __post_init__(self):
        """Fail-fast validation"""
        valid_tasks = ['sentiment', 'urgency', 'multi']
        if self.task not in valid_tasks:
            raise ValueError(f"❌ Invalid task: {self.task}")
        
        if self.max_length <= 0:
            raise ValueError(f"❌ max_length must be positive")
        
        if not self.model_path.exists():
            raise FileNotFoundError(f"❌ Model path not found: {self.model_path}")
        
        valid_devices = ['cpu', 'cuda']
        if self.device not in valid_devices:
            raise ValueError(f"❌ Invalid device: {self.device}")


# ==============================================================================
# SIGNAL EXTRACTOR
# ==============================================================================

class SignalExtractor:
    """
    Production inference class for signal extraction.
    
    Single Responsibility: Only performs inference.
    Immutability: Config frozen after loading.
    Fail-Fast: Validates all inputs before processing.
    """
    
    def __init__(self, model_path: str, device: str = 'cpu'):
        """
        Initialize signal extractor.
        
        Args:
            model_path: Path to saved model directory
            device: Device to run inference on ('cpu' or 'cuda')
            
        Raises:
            FileNotFoundError: If model_path doesn't exist
            ValueError: If config is invalid
        """
        start_time = time.perf_counter()
        
        # Fail-fast: Validate path
        model_path_obj = Path(model_path)
        if not model_path_obj.exists():
            raise FileNotFoundError(f"❌ Model path not found: {model_path}")
        
        logger.info(f"📂 Loading model from {model_path}")
        
        # Load and validate config
        self._config = self._load_config(model_path_obj, device)
        
        # Load tokenizer
        self._tokenizer = self._load_tokenizer(model_path_obj)
        
        # Load model
        self._model = self._load_model(model_path_obj)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"✅ Model loaded in {elapsed_ms:.0f}ms")
        logger.info(f"   Task: {self._config.task}")
        logger.info(f"   Device: {self._config.device}")
    
    def _load_config(self, model_path: Path, device: str) -> InferenceConfig:
        """
        Single Responsibility: Load and validate config only.
        
        Returns:
            Validated InferenceConfig
        """
        config_file = model_path / 'config.json'
        
        # Guard clause: Use defaults if config missing
        if not config_file.exists():
            logger.warning("⚠️ No config.json found, using defaults")
            return InferenceConfig(
                task='sentiment',
                max_length=256,
                model_path=model_path,
                device=device
            )
        
        with open(config_file) as f:
            config_dict = json.load(f)
        
        return InferenceConfig(
            task=config_dict.get('task', 'sentiment'),
            max_length=config_dict.get('max_length', 256),
            model_path=model_path,
            device=device
        )
    
    def _load_tokenizer(self, model_path: Path) -> RobertaTokenizer:
        """Single Responsibility: Load tokenizer only"""
        try:
            tokenizer = RobertaTokenizer.from_pretrained(model_path)
            logger.info("✓ Loaded tokenizer from checkpoint")
        except Exception as e:
            logger.warning(f"⚠️ Failed to load tokenizer from checkpoint: {e}")
            logger.info("  Loading default roberta-base tokenizer")
            tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
        
        return tokenizer
    
    def _load_model(self, model_path: Path) -> nn.Module:
        """
        Single Responsibility: Load and prepare model only.
        
        Returns:
            Loaded model in eval mode
        """
        # Create model architecture
        model = create_model(
            task=self._config.task,
            freeze_base=False  # No freezing for inference
        )
        
        # Load weights
        weights_file = model_path / 'model.pt'
        
        # Guard clause: Check if weights exist
        if not weights_file.exists():
            logger.warning(f"⚠️ No weights found at {weights_file}")
            logger.warning("  Using randomly initialized model")
        else:
            device = torch.device(self._config.device)
            model.load_state_dict(
                torch.load(weights_file, map_location=device)
            )
            logger.info("✓ Loaded model weights")
        
        # Prepare for inference
        model = model.to(torch.device(self._config.device))
        model.eval()
        
        return model
    
    def extract_signals(
        self,
        text: Union[str, List[str]]
    ) -> Union[SentimentPrediction, UrgencyPrediction, MultiTaskPrediction, 
               List[Union[SentimentPrediction, UrgencyPrediction, MultiTaskPrediction]]]:
        """
        Extract signals from text(s).
        
        Design by Contract:
        - Precondition: text must be non-empty string or list
        - Postcondition: Returns validated prediction type(s)
        
        Args:
            text: Single string or list of strings
            
        Returns:
            Validated prediction(s)
            
        Raises:
            ValueError: If text is empty or invalid
        """
        start_time = time.perf_counter()
        
        # Fail-fast: Validate input
        if not text:
            raise ValueError("❌ Text cannot be empty")
        
        # Handle single vs batch
        single_input = isinstance(text, str)
        texts = [text] if single_input else text
        
        # Guard clause: Check all texts are non-empty
        if not all(t and isinstance(t, str) for t in texts):
            raise ValueError("❌ All texts must be non-empty strings")
        
        # Tokenize
        encodings = self._tokenize_texts(texts)
        
        # Inference
        predictions = self._run_inference(encodings)
        
        # Log timing
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"⚡ Predicted {len(texts)} samples in {elapsed_ms:.1f}ms "
                   f"({elapsed_ms/len(texts):.1f}ms/sample)")
        
        # Return single or list
        return predictions[0] if single_input else predictions
    
    def _tokenize_texts(self, texts: List[str]) -> Dict[str, torch.Tensor]:
        """
        Single Responsibility: Tokenize texts only.
        
        Returns:
            Dict with input_ids and attention_mask tensors
        """
        encodings = self._tokenizer(
            texts,
            add_special_tokens=True,
            max_length=self._config.max_length,
            padding=True,
            truncation=True,
            return_tensors='pt'
        )
        
        return encodings
    
    def _run_inference(
        self,
        encodings: Dict[str, torch.Tensor]
    ) -> List[Union[SentimentPrediction, UrgencyPrediction, MultiTaskPrediction]]:
        """
        Single Responsibility: Run model inference only.
        
        Returns:
            List of validated predictions
        """
        device = torch.device(self._config.device)
        
        # Move to device
        input_ids = encodings['input_ids'].to(device)
        attention_mask = encodings['attention_mask'].to(device)
        
        # Inference
        with torch.no_grad():
            if self._config.task == 'sentiment':
                outputs = self._model(input_ids, attention_mask)
                predictions = self._create_sentiment_predictions(outputs)
            
            elif self._config.task == 'urgency':
                outputs = self._model(input_ids, attention_mask)
                predictions = self._create_urgency_predictions(outputs)
            
            elif self._config.task == 'multi':
                outputs = self._model(input_ids, attention_mask)
                predictions = self._create_multitask_predictions(outputs)
            
            else:
                raise ValueError(f"❌ Unknown task: {self._config.task}")
        
        return predictions
    
    def _create_sentiment_predictions(
        self,
        outputs: torch.Tensor
    ) -> List[SentimentPrediction]:
        """
        Single Responsibility: Create sentiment prediction objects only.
        
        Returns:
            List of validated SentimentPrediction objects
        """
        scores = outputs.cpu().numpy()
        return [
            SentimentPrediction(text_sentiment=float(score))
            for score in scores
        ]
    
    def _create_urgency_predictions(
        self,
        outputs: torch.Tensor
    ) -> List[UrgencyPrediction]:
        """Single Responsibility: Create urgency prediction objects only"""
        scores = outputs.cpu().numpy()
        return [
            UrgencyPrediction(text_urgency=float(score))
            for score in scores
        ]
    
    def _create_multitask_predictions(
        self,
        outputs: Dict[str, torch.Tensor]
    ) -> List[MultiTaskPrediction]:
        """Single Responsibility: Create multi-task prediction objects only"""
        sentiment = outputs['sentiment'].cpu().numpy()
        urgency = outputs['urgency'].cpu().numpy()
        severity = torch.argmax(outputs['severity'], dim=1).cpu().numpy()
        impact = torch.argmax(outputs['impact'], dim=1).cpu().numpy()
        
        severity_labels = ['low', 'medium', 'high', 'critical']
        impact_labels = ['low', 'medium', 'medium-high', 'high']
        
        return [
            MultiTaskPrediction(
                text_sentiment=float(sent),
                text_urgency=float(urg),
                predicted_severity=severity_labels[sev],
                predicted_impact=impact_labels[imp]
            )
            for sent, urg, sev, imp in zip(sentiment, urgency, severity, impact)
        ]


# ==============================================================================
# PUBLIC API
# ==============================================================================

def load_extractor(model_path: str, device: str = 'cpu') -> SignalExtractor:
    """
    Convenience function to load signal extractor.
    
    Args:
        model_path: Path to saved model
        device: Device to use ('cpu' or 'cuda')
        
    Returns:
        Initialized SignalExtractor
    """
    return SignalExtractor(model_path, device)


# ==============================================================================
# CLI TESTING
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    # Guard clause: Check arguments
    if len(sys.argv) < 2:
        print("Usage: python inference.py <model_path> [text]")
        print("Example: python inference.py models/sentiment-small \"The AC is broken\"")
        sys.exit(1)
    
    model_path = sys.argv[1]
    
    # Load extractor
    logger.info("="*60)
    extractor = SignalExtractor(model_path)
    logger.info("="*60)
    
    # Test texts
    test_texts = [
        "The air conditioning is broken and it's very uncomfortable",
        "This is unacceptable! We've been calling for days!",
        "Thank you for the quick response, appreciate your help",
        "I need to report an emergency - water is flooding the storage area"
    ]
    
    # Override with CLI text if provided
    if len(sys.argv) > 2:
        test_texts = [' '.join(sys.argv[2:])]
    
    logger.info(f"\n🧪 Testing Signal Extraction\n")
    
    # Single predictions
    for i, text in enumerate(test_texts, 1):
        logger.info(f"{i}. Text: {text}")
        
        try:
            result = extractor.extract_signals(text)
            logger.info(f"   Result: {result}\n")
        except Exception as e:
            logger.error(f"   ❌ Error: {e}\n")
    
    # Batch prediction
    logger.info("\n🚀 Testing Batch Processing")
    try:
        batch_results = extractor.extract_signals(test_texts)
        logger.info(f"✓ Processed {len(batch_results)} samples in batch\n")
        
        for text, result in zip(test_texts, batch_results):
            logger.info(f"Text: {text[:50]}...")
            logger.info(f"  → {result}\n")
    except Exception as e:
        logger.error(f"❌ Batch error: {e}")
    
    logger.info("✅ Inference testing complete!")
