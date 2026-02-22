import torch
import torch.nn as nn
from transformers import RobertaModel
from typing import Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RoBERTaMultiTaskModel(nn.Module):
    def __init__(self, model_name: str = 'roberta-base', dropout: float = 0.1, hidden_dim: int = 256):
        super().__init__()
        self.model_name = model_name
        logger.info(f"Loading RoBERTa model: {model_name}")
        self.roberta = RobertaModel.from_pretrained(model_name)
        self.hidden_size = self.roberta.config.hidden_size
        logger.info(f"✓ RoBERTa loaded (hidden_size={self.hidden_size})")
        self.dropout = nn.Dropout(dropout)
        self.sentiment_head = nn.Sequential(
            nn.Linear(self.hidden_size, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1),
            nn.Tanh()
        )
        logger.info(f"✓ Built sentiment head: {self.hidden_size}→{hidden_dim}→1")

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> Dict[str, torch.Tensor]:
        outputs = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]
        cls_output = self.dropout(cls_output)
        sentiment = self.sentiment_head(cls_output).squeeze(-1)
        return {'sentiment': sentiment}

    def freeze_base_encoder(self):
        for param in self.roberta.parameters():
            param.requires_grad = False

    def unfreeze_base_encoder(self):
        for param in self.roberta.parameters():
            param.requires_grad = True


def create_model(model_name: str = 'roberta-base', dropout: float = 0.1, hidden_dim: int = 256, freeze_base: bool = False) -> RoBERTaMultiTaskModel:
    model = RoBERTaMultiTaskModel(model_name=model_name, dropout=dropout, hidden_dim=hidden_dim)
    if freeze_base:
        model.freeze_base_encoder()
    return model