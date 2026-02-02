"""
Multi-Task RoBERTa Model Architecture

Outputs THREE things simultaneously:
1. text_sentiment: -1 to +1 (how negative/positive)
2. text_urgency: 0 to 1 (how urgent)
3. keywords: List of extracted keywords

This REPLACES your current model_architecture.py
"""

import torch
import torch.nn as nn
from transformers import RobertaModel
from typing import Dict, List
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# KEYWORD VOCABULARY - Define your domain keywords
# ==============================================================================

KEYWORD_VOCABULARY = [
    # HVAC (8)
    "air conditioning", "AC", "heating", "temperature", 
    "cooling", "HVAC", "thermostat", "ventilation",
    
    # Plumbing (9)
    "water", "leak", "flooding", "drain", "pipe", 
    "plumbing", "toilet", "sink", "faucet",
    
    # Electrical (8)
    "power", "electricity", "lights", "lighting", 
    "electrical", "outlet", "circuit", "power outage",
    
    # Elevators (2)
    "elevator", "lift",
    
    # Parking (3)
    "parking", "gate", "barrier",
    
    # Security (4)
    "security", "alarm", "fire alarm", "safety",
    
    # Maintenance (4)
    "cleaning", "maintenance", "trash", "garbage",
    
    # Noise (3)
    "noise", "loud", "disturbance",
    
    # Internet (4)
    "internet", "WiFi", "connectivity", "network",
    
    # Status words (5)
    "broken", "not working", "repair", "emergency", "urgent"
]

# Total: 50 keywords


def get_keyword_vocabulary() -> List[str]:
    """Get keyword vocabulary for training and inference"""
    return KEYWORD_VOCABULARY


def keyword_indices_to_words(indices: List[int]) -> List[str]:
    """Convert keyword indices back to words"""
    vocab = get_keyword_vocabulary()
    return [vocab[idx] for idx in indices if 0 <= idx < len(vocab)]


# ==============================================================================
# MODEL ARCHITECTURE
# ==============================================================================

class RoBERTaMultiTaskModel(nn.Module):
    """
    Multi-task RoBERTa with 3 output heads:
    
    Architecture:
    ────────────────────────────────────────────────────────────────
    Input: "The AC has been broken for three days!"
                            ↓
                    RoBERTa Encoder
                      (shared, 768d)
                            ↓
              ┌─────────────┼─────────────┐
              ↓             ↓             ↓
        Sentiment      Urgency       Keywords
        Head           Head          Head
        (768→256→1)    (768→256→1)   (768→256→50)
              ↓             ↓             ↓
        Tanh [-1,1]    Sigmoid [0,1]  Sigmoid [0,1]^50
              ↓             ↓             ↓
        -0.75          0.82          [1,0,0,1,1,...0]
    (very negative)   (high urgent)  (AC, broken, days)
    ────────────────────────────────────────────────────────────────
    """
    
    def __init__(
        self,
        model_name: str = 'roberta-base',
        dropout: float = 0.1,
        hidden_dim: int = 256
    ):
        super().__init__()
        
        self.model_name = model_name
        self.num_keywords = len(KEYWORD_VOCABULARY)
        
        logger.info(f"Loading RoBERTa model: {model_name}")
        
        # Shared RoBERTa encoder
        self.roberta = RobertaModel.from_pretrained(model_name)
        self.hidden_size = self.roberta.config.hidden_size  # 768
        
        logger.info(f"✓ RoBERTa loaded (hidden_size={self.hidden_size})")
        
        # Dropout
        self.dropout = nn.Dropout(dropout)
        
        # Head 1: Sentiment regression (-1 to +1)
        self.sentiment_head = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
            nn.Tanh()  # Output in [-1, 1]
        )
        
        # Head 2: Urgency regression (0 to 1)
        self.urgency_head = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid()  # Output in [0, 1]
        )
        
        # Head 3: Keyword multi-label classification (50 keywords)
        self.keyword_head = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, self.num_keywords),
            nn.Sigmoid()  # Each keyword independently in [0, 1]
        )
        
        logger.info(f"✓ Built 3 task heads:")
        logger.info(f"  - Sentiment: {self.hidden_size}→{hidden_dim}→1")
        logger.info(f"  - Urgency:   {self.hidden_size}→{hidden_dim}→1")
        logger.info(f"  - Keywords:  {self.hidden_size}→{hidden_dim}→{self.num_keywords}")
    
    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            input_ids: [batch, seq_len] token IDs
            attention_mask: [batch, seq_len] attention mask
        
        Returns:
            {
                'sentiment': [batch] sentiment scores in [-1, 1],
                'urgency': [batch] urgency scores in [0, 1],
                'keywords': [batch, 50] keyword probabilities in [0, 1]
            }
        """
        # Shared encoder
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask
        )
        
        # Extract [CLS] token (first token, represents whole sentence)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [batch, 768]
        cls_output = self.dropout(cls_output)
        
        # Pass through each head
        sentiment = self.sentiment_head(cls_output).squeeze(-1)  # [batch]
        urgency = self.urgency_head(cls_output).squeeze(-1)      # [batch]
        keywords = self.keyword_head(cls_output)                 # [batch, 50]
        
        return {
            'sentiment': sentiment,
            'urgency': urgency,
            'keywords': keywords
        }
    
    def freeze_base_encoder(self):
        """Freeze RoBERTa weights (only train heads) - faster training"""
        logger.info("❄️ Freezing RoBERTa base encoder")
        for param in self.roberta.parameters():
            param.requires_grad = False
    
    def unfreeze_base_encoder(self):
        """Unfreeze RoBERTa (train everything) - better accuracy"""
        logger.info("🔥 Unfreezing RoBERTa base encoder")
        for param in self.roberta.parameters():
            param.requires_grad = True


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def count_parameters(model: nn.Module) -> tuple:
    """Count trainable and total parameters"""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def create_model(
    model_name: str = 'roberta-base',
    dropout: float = 0.1,
    hidden_dim: int = 256,
    freeze_base: bool = False
) -> RoBERTaMultiTaskModel:
    """
    Create multi-task model.
    
    Args:
        model_name: HuggingFace model name
        dropout: Dropout rate
        hidden_dim: Hidden layer size for task heads
        freeze_base: If True, only train heads (faster)
    
    Returns:
        Initialized model
    """
    model = RoBERTaMultiTaskModel(
        model_name=model_name,
        dropout=dropout,
        hidden_dim=hidden_dim
    )
    
    if freeze_base:
        model.freeze_base_encoder()
    
    trainable, total = count_parameters(model)
    logger.info(f"✓ Model parameters:")
    logger.info(f"  Trainable: {trainable:,}")
    logger.info(f"  Total:     {total:,}")
    logger.info(f"  Trainable: {trainable/total*100:.1f}%")
    
    return model


# ==============================================================================
# EXAMPLE / TEST
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("Multi-Task RoBERTa Model Test")
    print("="*70)
    
    # Create model
    model = create_model(
        model_name='roberta-base',
        dropout=0.1,
        hidden_dim=256,
        freeze_base=False
    )
    
    # Test forward pass
    print("\n🧪 Testing forward pass...")
    batch_size = 2
    seq_len = 64
    
    # Dummy input
    input_ids = torch.randint(0, 50000, (batch_size, seq_len))
    attention_mask = torch.ones(batch_size, seq_len)
    
    # Forward
    outputs = model(input_ids, attention_mask)
    
    print("\n📊 Output shapes:")
    print(f"  sentiment: {outputs['sentiment'].shape}")
    print(f"             range: [{outputs['sentiment'].min():.2f}, {outputs['sentiment'].max():.2f}]")
    print(f"  urgency:   {outputs['urgency'].shape}")
    print(f"             range: [{outputs['urgency'].min():.2f}, {outputs['urgency'].max():.2f}]")
    print(f"  keywords:  {outputs['keywords'].shape}")
    print(f"             range: [{outputs['keywords'].min():.2f}, {outputs['keywords'].max():.2f}]")
    
    # Show first few keywords
    print("\n📝 Keyword vocabulary (first 10):")
    vocab = get_keyword_vocabulary()
    for i in range(10):
        print(f"  [{i:2d}] {vocab[i]}")
    
    print("\n" + "="*70)
    print("✅ Model test complete!")
    print("="*70 + "\n")
