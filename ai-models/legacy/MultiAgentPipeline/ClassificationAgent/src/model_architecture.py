"""
Classification Agent — Model Architecture
==========================================

Task: Binary classification of call transcripts.
    complaint  → label 0  (Tenant Support)
    inquiry    → label 1  (Leasing Inquiry)

Backbone: distilroberta-base
    Chosen over roberta-base because:
    - This is a binary classification task with strong lexical signals.
      "We need space urgently" vs "The AC has been broken" are easily
      separable with a smaller model.
    - distilroberta-base retains ~97% of roberta-base accuracy on
      classification tasks while running at ~2x inference speed.
    - Speed matters here: every single call passes through this gate
      before anything downstream runs. Latency at this stage multiplies.

Head: single nn.Linear(768, 2) on top of the [CLS] pooler output.

Output:
    logits tensor of shape [batch, 2]
    Class indices: complaint=0, inquiry=1
"""

import torch
import torch.nn as nn
from transformers import RobertaModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMPLAINT_LABEL = 0
INQUIRY_LABEL = 1
LABEL_NAMES = {COMPLAINT_LABEL: "complaint", INQUIRY_LABEL: "inquiry"}


class CallClassifier(nn.Module):
    """
    DistilRoBERTa-based binary call classifier.

    Architecture:
        Input transcript
              ↓
        distilroberta-base encoder  (6 transformer layers, 768d hidden)
              ↓
        [CLS] pooler output  [batch, 768]
              ↓
        Dropout(0.1)
              ↓
        Linear(768 → 2)
              ↓
        logits  [batch, 2]  →  complaint | inquiry
    """

    MODEL_NAME = "distilroberta-base"

    def __init__(self, dropout: float = 0.1):
        super().__init__()

        logger.info(f"Loading backbone: {self.MODEL_NAME}")
        self.roberta = RobertaModel.from_pretrained(self.MODEL_NAME)
        self.hidden_size = self.roberta.config.hidden_size  # 768

        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.hidden_size, 2)

        logger.info(
            f"CallClassifier ready — "
            f"backbone: {self.MODEL_NAME}, "
            f"head: {self.hidden_size} → 2"
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            input_ids:      [batch, seq_len]
            attention_mask: [batch, seq_len]

        Returns:
            logits [batch, 2]  (raw, un-softmaxed)
        """
        outputs = self.roberta(
            input_ids=input_ids,
            attention_mask=attention_mask,
        )
        cls = outputs.last_hidden_state[:, 0, :]  # [batch, 768]
        cls = self.dropout(cls)
        return self.classifier(cls)  # [batch, 2]

    def freeze_backbone(self):
        """Freeze all backbone weights — only train the classifier head."""
        for param in self.roberta.parameters():
            param.requires_grad = False
        logger.info("Backbone frozen — training classifier head only")

    def unfreeze_backbone(self):
        """Unfreeze backbone for end-to-end fine-tuning."""
        for param in self.roberta.parameters():
            param.requires_grad = True
        logger.info("Backbone unfrozen — training end-to-end")


def count_parameters(model: nn.Module) -> tuple:
    """Return (trainable, total) parameter counts."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def create_model(dropout: float = 0.1, freeze_backbone: bool = False) -> CallClassifier:
    """
    Instantiate and return a CallClassifier.

    Args:
        dropout:         Dropout rate on the CLS representation
        freeze_backbone: If True, only the classification head is trained.
                         Useful for a quick first pass before full fine-tuning.

    Returns:
        Initialized CallClassifier
    """
    model = CallClassifier(dropout=dropout)

    if freeze_backbone:
        model.freeze_backbone()

    trainable, total = count_parameters(model)
    logger.info(
        f"Parameters — trainable: {trainable:,} / total: {total:,} "
        f"({trainable / total * 100:.1f}%)"
    )
    return model


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CallClassifier — architecture test")
    print("=" * 60)

    m = create_model(freeze_backbone=False)

    b, seq = 2, 64
    ids = torch.randint(0, 50000, (b, seq))
    mask = torch.ones(b, seq)
    logits = m(ids, mask)

    print(f"\nOutput shape:  {logits.shape}")   # [2, 2]
    print(f"Sample logits: {logits.detach().numpy()}")
    print("\nTest passed.")
    print("=" * 60)
