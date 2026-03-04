"""
RoBERTa Model Architecture for InnovaCX Signal Extraction

Provides single-task and multi-task RoBERTa models for sentiment/urgency extraction.

Principles Applied:
- Fail-Fast: Validate configs immediately
- Immutability: Frozen config dataclasses
- Single Responsibility: Each model class does ONE thing
- Design by Contract: Explicit preconditions/postconditions
- Observability: Structured logging with timing
- KISS: Simple, clear architecture
"""

import torch
import torch.nn as nn
from transformers import RobertaModel, RobertaConfig
from typing import Dict, Optional
from dataclasses import dataclass
import logging
import time

# Structured logging with emojis
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION TYPES (Parse, Don't Validate)
# ==============================================================================

@dataclass(frozen=True)  # Immutability
class ModelConfig:
    """
    Validated model configuration.
    Type proves validity - if you have this, config is valid.
    """
    model_name: str
    dropout: float
    freeze_base: bool
    hidden_size: int = 768  # RoBERTa-base default
    
    def __post_init__(self):
        """Fail-fast: Design by Contract"""
        # Guard clauses for validation
        if not 0.0 <= self.dropout <= 1.0:
            raise ValueError(f"❌ Dropout must be in [0, 1], got {self.dropout}")
        
        if self.hidden_size <= 0:
            raise ValueError(f"❌ Hidden size must be positive, got {self.hidden_size}")
        
        if not isinstance(self.freeze_base, bool):
            raise TypeError(f"❌ freeze_base must be bool, got {type(self.freeze_base)}")


@dataclass(frozen=True)
class MultiTaskConfig(ModelConfig):
    """Configuration for multi-task model"""
    num_severity_classes: int = 4
    num_impact_classes: int = 4
    
    def __post_init__(self):
        """Validate parent config + child-specific constraints"""
        super().__post_init__()  # Validate parent
        
        if self.num_severity_classes <= 0:
            raise ValueError(f"❌ num_severity_classes must be positive")
        
        if self.num_impact_classes <= 0:
            raise ValueError(f"❌ num_impact_classes must be positive")


# ==============================================================================
# SINGLE-TASK MODELS
# ==============================================================================

class RobertaSentimentRegressor(nn.Module):
    """
    Single-task RoBERTa for sentiment regression [-1, 1].
    
    Single Responsibility: Only predicts sentiment, nothing else.
    Immutability: Config frozen at construction.
    """
    
    def __init__(self, config: ModelConfig):
        """
        Initialize sentiment model.
        
        Args:
            config: Validated ModelConfig (type proves validity)
            
        Raises:
            TypeError: If config is invalid type
        """
        super().__init__()
        
        # Fail-fast: Validate input type
        if not isinstance(config, ModelConfig):
            raise TypeError(f"❌ Expected ModelConfig, got {type(config)}")
        
        start_time = time.perf_counter()
        
        # Store immutable config
        self._config = config
        
        # Load pretrained RoBERTa
        self.roberta = RobertaModel.from_pretrained(config.model_name)
        
        # Apply freezing if requested
        if config.freeze_base:
            self._freeze_base_layers()
        
        # Build regression head
        self.dropout = nn.Dropout(config.dropout)
        self.regressor = self._build_regression_head(config)
        
        # Log initialization
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        params = self._count_parameters()
        logger.info(f"✓ Initialized RobertaSentimentRegressor in {elapsed_ms:.0f}ms")
        logger.info(f"  Trainable params: {params['trainable']:,} / {params['total']:,}")
    
    def _freeze_base_layers(self) -> None:
        """
        Single Responsibility: Freeze RoBERTa base only.
        Observability: Logs action.
        """
        for param in self.roberta.parameters():
            param.requires_grad = False
        logger.info("  🔒 Frozen RoBERTa base layers")
    
    def _build_regression_head(self, config: ModelConfig) -> nn.Sequential:
        """
        Single Responsibility: Build regression head only.
        Returns complete regression head module.
        """
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, 1),
            nn.Tanh()  # Output: -1 to 1
        )
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for sentiment prediction.
        
        Design by Contract:
        - Precondition: input_ids and attention_mask must match shapes
        - Postcondition: Returns tensor in range [-1, 1]
        
        Args:
            input_ids: Token IDs [batch_size, seq_len]
            attention_mask: Attention mask [batch_size, seq_len]
            
        Returns:
            sentiment: Sentiment scores [batch_size] in range [-1, 1]
        """
        # Fail-fast: Validate inputs
        if input_ids.shape != attention_mask.shape:
            raise ValueError(
                f"❌ Shape mismatch: input_ids {input_ids.shape} "
                f"!= attention_mask {attention_mask.shape}"
            )
        
        # Get RoBERTa representations
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output  # [batch_size, hidden_size]
        
        # Apply dropout
        pooled = self.dropout(pooled)
        
        # Regression head
        sentiment = self.regressor(pooled).squeeze(-1)  # [batch_size]
        
        # Postcondition: Verify output range
        assert sentiment.min() >= -1.0 and sentiment.max() <= 1.0, \
            "Sentiment output must be in [-1, 1]"
        
        return sentiment
    
    def _count_parameters(self) -> Dict[str, int]:
        """
        Single Responsibility: Count parameters only.
        Observability: Provides transparency into model size.
        """
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        return {
            'total': total,
            'trainable': trainable,
            'frozen': total - trainable,
            'trainable_pct': (trainable / total * 100) if total > 0 else 0.0
        }


class RobertaUrgencyClassifier(nn.Module):
    """
    Single-task RoBERTa for urgency regression [0, 1].
    
    Single Responsibility: Only predicts urgency, nothing else.
    """
    
    def __init__(self, config: ModelConfig):
        """Initialize urgency model"""
        super().__init__()
        
        # Fail-fast validation
        if not isinstance(config, ModelConfig):
            raise TypeError(f"❌ Expected ModelConfig, got {type(config)}")
        
        start_time = time.perf_counter()
        
        self._config = config
        
        # Load RoBERTa
        self.roberta = RobertaModel.from_pretrained(config.model_name)
        
        # Freeze if requested
        if config.freeze_base:
            self._freeze_base_layers()
        
        # Build classification head
        self.dropout = nn.Dropout(config.dropout)
        self.classifier = self._build_classification_head(config)
        
        # Log initialization
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        params = self._count_parameters()
        logger.info(f"✓ Initialized RobertaUrgencyClassifier in {elapsed_ms:.0f}ms")
        logger.info(f"  Trainable params: {params['trainable']:,} / {params['total']:,}")
    
    def _freeze_base_layers(self) -> None:
        """Freeze RoBERTa base"""
        for param in self.roberta.parameters():
            param.requires_grad = False
        logger.info("  🔒 Frozen RoBERTa base layers")
    
    def _build_classification_head(self, config: ModelConfig) -> nn.Sequential:
        """Build classification head"""
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, 1),
            nn.Sigmoid()  # Output: 0 to 1
        )
    
    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for urgency prediction.
        
        Returns:
            urgency: Urgency scores [batch_size] in range [0, 1]
        """
        # Fail-fast validation
        if input_ids.shape != attention_mask.shape:
            raise ValueError(f"❌ Shape mismatch")
        
        # Get representations
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output
        
        # Apply dropout and classifier
        pooled = self.dropout(pooled)
        urgency = self.classifier(pooled).squeeze(-1)
        
        # Postcondition check
        assert urgency.min() >= 0.0 and urgency.max() <= 1.0, \
            "Urgency output must be in [0, 1]"
        
        return urgency
    
    def _count_parameters(self) -> Dict[str, int]:
        """Count parameters"""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        return {
            'total': total,
            'trainable': trainable,
            'frozen': total - trainable,
            'trainable_pct': (trainable / total * 100) if total > 0 else 0.0
        }


# ==============================================================================
# MULTI-TASK MODEL
# ==============================================================================

class RobertaMultiTaskModel(nn.Module):
    """
    Multi-task RoBERTa for simultaneous prediction of:
    - Sentiment (regression: -1 to 1)
    - Urgency (regression: 0 to 1)
    - Severity (classification: 4 classes)
    - Impact (classification: 4 classes)
    
    Single Responsibility: Multi-task prediction only.
    Shares encoder across all tasks for efficiency.
    """
    
    def __init__(self, config: MultiTaskConfig):
        """
        Initialize multi-task model.
        
        Args:
            config: Validated MultiTaskConfig
        """
        super().__init__()
        
        # Fail-fast validation
        if not isinstance(config, MultiTaskConfig):
            raise TypeError(f"❌ Expected MultiTaskConfig, got {type(config)}")
        
        start_time = time.perf_counter()
        
        self._config = config
        
        # Shared encoder
        self.roberta = RobertaModel.from_pretrained(config.model_name)
        
        # Freeze if requested
        if config.freeze_base:
            self._freeze_base_layers()
        
        # Shared dropout
        self.dropout = nn.Dropout(config.dropout)
        
        # Build task-specific heads
        self.sentiment_head = self._build_sentiment_head(config)
        self.urgency_head = self._build_urgency_head(config)
        self.severity_head = self._build_severity_head(config)
        self.impact_head = self._build_impact_head(config)
        
        # Log initialization
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        params = self._count_parameters()
        logger.info(f"✓ Initialized RobertaMultiTaskModel in {elapsed_ms:.0f}ms")
        logger.info(f"  Trainable params: {params['trainable']:,} / {params['total']:,}")
    
    def _freeze_base_layers(self) -> None:
        """Freeze shared RoBERTa encoder"""
        for param in self.roberta.parameters():
            param.requires_grad = False
        logger.info("  🔒 Frozen RoBERTa base layers")
    
    def _build_sentiment_head(self, config: MultiTaskConfig) -> nn.Sequential:
        """Build sentiment regression head"""
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, 1),
            nn.Tanh()
        )
    
    def _build_urgency_head(self, config: MultiTaskConfig) -> nn.Sequential:
        """Build urgency regression head"""
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, 1),
            nn.Sigmoid()
        )
    
    def _build_severity_head(self, config: MultiTaskConfig) -> nn.Sequential:
        """Build severity classification head"""
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, config.num_severity_classes)
        )
    
    def _build_impact_head(self, config: MultiTaskConfig) -> nn.Sequential:
        """Build impact classification head"""
        return nn.Sequential(
            nn.Linear(config.hidden_size, 256),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(256, config.num_impact_classes)
        )
    
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Multi-task forward pass.
        
        Returns:
            Dict with keys: 'sentiment', 'urgency', 'severity', 'impact'
        """
        # Fail-fast validation
        if input_ids.shape != attention_mask.shape:
            raise ValueError(f"❌ Shape mismatch")
        
        # Shared encoder
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.pooler_output
        pooled = self.dropout(pooled)
        
        # Task-specific predictions
        results = {
            'sentiment': self.sentiment_head(pooled).squeeze(-1),
            'urgency': self.urgency_head(pooled).squeeze(-1),
            'severity': self.severity_head(pooled),
            'impact': self.impact_head(pooled)
        }
        
        return results
    
    def _count_parameters(self) -> Dict[str, int]:
        """Count parameters"""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        
        return {
            'total': total,
            'trainable': trainable,
            'frozen': total - trainable,
            'trainable_pct': (trainable / total * 100) if total > 0 else 0.0
        }


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_model(
    task: str = 'sentiment',
    model_name: str = 'roberta-base',
    freeze_base: bool = False,
    dropout: float = 0.1
) -> nn.Module:
    """
    Factory function to create appropriate model based on task.
    
    Design by Contract:
    - Precondition: task must be valid
    - Postcondition: Returns initialized model
    
    Args:
        task: One of 'sentiment', 'urgency', 'multi'
        model_name: Pretrained RoBERTa model name
        freeze_base: Whether to freeze base layers
        dropout: Dropout probability
        
    Returns:
        Initialized model
        
    Raises:
        ValueError: If task is invalid
    """
    # Fail-fast: Validate task
    valid_tasks = ['sentiment', 'urgency', 'multi']
    if task not in valid_tasks:
        raise ValueError(
            f"❌ Invalid task: '{task}'. "
            f"Must be one of {valid_tasks}"
        )
    
    # Create validated config
    if task == 'multi':
        config = MultiTaskConfig(
            model_name=model_name,
            dropout=dropout,
            freeze_base=freeze_base
        )
        return RobertaMultiTaskModel(config)
    else:
        config = ModelConfig(
            model_name=model_name,
            dropout=dropout,
            freeze_base=freeze_base
        )
        
        if task == 'sentiment':
            return RobertaSentimentRegressor(config)
        else:  # urgency
            return RobertaUrgencyClassifier(config)


def count_parameters(model: nn.Module) -> Dict[str, int]:
    """
    Count parameters in any model.
    
    Single Responsibility: Only counts, doesn't modify.
    
    Args:
        model: PyTorch model
        
    Returns:
        Dict with total, trainable, frozen counts
    """
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    return {
        'total': total,
        'trainable': trainable,
        'frozen': total - trainable,
        'trainable_pct': (trainable / total * 100) if total > 0 else 0.0
    }


# ==============================================================================
# CLI TESTING
# ==============================================================================

if __name__ == "__main__":
    logger.info("🧪 Testing Model Architectures\n")
    
    # Test 1: Sentiment model with frozen base
    logger.info("1️⃣ Testing Sentiment Regressor (Frozen Base)")
    model_sentiment = create_model('sentiment', freeze_base=True)
    params = count_parameters(model_sentiment)
    logger.info(f"   Total: {params['total']:,}")
    logger.info(f"   Trainable: {params['trainable']:,} "
                f"({params['trainable_pct']:.1f}%)\n")
    
    # Test 2: Urgency model with full training
    logger.info("2️⃣ Testing Urgency Classifier (Full Training)")
    model_urgency = create_model('urgency', freeze_base=False)
    params = count_parameters(model_urgency)
    logger.info(f"   Total: {params['total']:,}")
    logger.info(f"   Trainable: {params['trainable']:,} "
                f"({params['trainable_pct']:.1f}%)\n")
    
    # Test 3: Multi-task model
    logger.info("3️⃣ Testing Multi-Task Model (Frozen Base)")
    model_multi = create_model('multi', freeze_base=True)
    params = count_parameters(model_multi)
    logger.info(f"   Total: {params['total']:,}")
    logger.info(f"   Trainable: {params['trainable']:,} "
                f"({params['trainable_pct']:.1f}%)\n")
    
    # Test 4: Forward pass
    logger.info("4️⃣ Testing Forward Pass")
    dummy_ids = torch.randint(0, 1000, (2, 128))
    dummy_mask = torch.ones(2, 128)
    
    with torch.no_grad():
        sent_out = model_sentiment(dummy_ids, dummy_mask)
        logger.info(f"   Sentiment shape: {sent_out.shape}")
        logger.info(f"   Sentiment range: [{sent_out.min():.3f}, {sent_out.max():.3f}]")
        
        urg_out = model_urgency(dummy_ids, dummy_mask)
        logger.info(f"   Urgency shape: {urg_out.shape}")
        logger.info(f"   Urgency range: [{urg_out.min():.3f}, {urg_out.max():.3f}]")
        
        multi_out = model_multi(dummy_ids, dummy_mask)
        logger.info(f"   Multi-task outputs: {list(multi_out.keys())}")
    
    logger.info("\n✅ All models initialized successfully!")
