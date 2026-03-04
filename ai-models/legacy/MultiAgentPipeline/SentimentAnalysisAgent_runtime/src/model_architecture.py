"""
Single-Head RoBERTa Sentiment Model (V7 Architecture)

One job: text_sentiment [-1, +1]

Architecture:
    Input text
        ↓
    RoBERTa Encoder (shared, 768d)
        ↓
    CLS embedding
        ↓
    sentiment_head (768 → 256 → 1)
        ↓
    Tanh → [-1, +1]

Urgency and keyword heads removed — those concerns belong to
Feature Engineering and Fuzzy Prioritization agents respectively.
"""

import torch
import torch.nn as nn
from transformers import RobertaModel
from typing import List
import logging


# ==============================================================================
# KEYWORD VOCABULARY — kept as a standalone export so pipeline scripts
# (step2_augment.py, data_preparation.py) can import get_keyword_vocabulary
# without depending on any model head. The vocabulary is not used by the
# single-head sentiment model itself.
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
    "broken", "not working", "repair", "emergency", "urgent",
]


def get_keyword_vocabulary() -> List[str]:
    """Return the 50-word domain keyword vocabulary."""
    return KEYWORD_VOCABULARY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoBERTaSentimentModel(nn.Module):
    """
    Single-task RoBERTa regression model for sentiment.

    Outputs text_sentiment in [-1, +1] via Tanh.
    """

    def __init__(
        self,
        model_name: str = 'roberta-base',
        dropout: float = 0.1,
        hidden_dim: int = 256
    ):
        super().__init__()

        self.model_name = model_name

        logger.info(f"Loading RoBERTa model: {model_name}")

        # Shared RoBERTa encoder
        self.roberta = RobertaModel.from_pretrained(model_name)
        self.hidden_size = self.roberta.config.hidden_size  # 768

        logger.info(f"RoBERTa loaded (hidden_size={self.hidden_size})")

        self.dropout = nn.Dropout(dropout)

        # Single head: sentiment regression [-1, +1]
        self.sentiment_head = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
            nn.Tanh()
        )

        logger.info(f"Sentiment head: {self.hidden_size} -> {hidden_dim} -> 1")

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            input_ids:      [batch, seq_len]
            attention_mask: [batch, seq_len]

        Returns:
            sentiment scores [batch] in [-1, +1]
        """
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [batch, 768]
        cls_output = self.dropout(cls_output)
        sentiment = self.sentiment_head(cls_output).squeeze(-1)  # [batch]
        return sentiment

    def freeze_base_encoder(self):
        """Freeze RoBERTa weights — only train the sentiment head."""
        logger.info("Freezing RoBERTa base encoder")
        for param in self.roberta.parameters():
            param.requires_grad = False

    def unfreeze_base_encoder(self):
        """Unfreeze RoBERTa — train everything end-to-end."""
        logger.info("Unfreezing RoBERTa base encoder")
        for param in self.roberta.parameters():
            param.requires_grad = True


def count_parameters(model: nn.Module) -> tuple:
    """Return (trainable_params, total_params)."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def create_model(
    model_name: str = 'roberta-base',
    dropout: float = 0.1,
    hidden_dim: int = 256,
    freeze_base: bool = False
) -> RoBERTaSentimentModel:
    """
    Instantiate and return the single-head sentiment model.

    Args:
        model_name:  HuggingFace model identifier
        dropout:     Dropout rate for the head
        hidden_dim:  Width of the intermediate layer in the head
        freeze_base: If True, only the head will be trained

    Returns:
        Initialized RoBERTaSentimentModel
    """
    model = RoBERTaSentimentModel(
        model_name=model_name,
        dropout=dropout,
        hidden_dim=hidden_dim
    )

    if freeze_base:
        model.freeze_base_encoder()

    trainable, total = count_parameters(model)
    logger.info(f"Model parameters — trainable: {trainable:,} / total: {total:,} "
                f"({trainable / total * 100:.1f}%)")

    return model


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("RoBERTaSentimentModel — single-head test")
    print("=" * 60)

    model = create_model(freeze_base=False)

    batch_size, seq_len = 2, 64
    input_ids = torch.randint(0, 50000, (batch_size, seq_len))
    attention_mask = torch.ones(batch_size, seq_len)

    sentiment = model(input_ids, attention_mask)

    print(f"\nOutput shape: {sentiment.shape}")
    print(f"Range:        [{sentiment.min():.4f}, {sentiment.max():.4f}]")
    print("\nTest passed.")
    print("=" * 60)
