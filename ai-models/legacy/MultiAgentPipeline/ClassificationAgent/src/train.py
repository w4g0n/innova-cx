"""
Classification Agent — Training Script
=======================================

Trains CallClassifier on the V6 augmented dataset.

Data:
    Reads the processed CSV produced by data_preparation.py.
    Both Tenant Support (complaint=0) and Leasing Inquiry (inquiry=1)
    records are used. N/A label rows are kept — the labels here are
    derived purely from call_category, not from the sentiment/urgency
    columns that are N/A for inquiries.

Split:   80% train / 10% val / 10% test
Loss:    CrossEntropyLoss with class_weights=[1.0, 1.5]
         The 60/40 complaint/inquiry split means without weighting the
         model could achieve ~60% accuracy by predicting "complaint"
         every time. The 1.5× weight on inquiries corrects this bias.

Expected accuracy: >96%  (the two classes are linguistically very
                          distinct — complaints discuss issues/problems,
                          inquiries ask about space/rent/leasing)

Confidence threshold: 0.75
    Below this the pipeline coordinator should ask a clarifying question
    rather than routing automatically.

Usage:
    python train.py <csv_path> <output_dir>

Example:
    python train.py data/processed/processed_multi_task_n7955.csv models/classifier-v1
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import classification_report, confusion_matrix
import time
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from model_architecture import create_model, COMPLAINT_LABEL, INQUIRY_LABEL, LABEL_NAMES


# ==============================================================================
# DATASET
# ==============================================================================

class CallCategoryDataset(Dataset):
    """
    Loads transcript + call_category label from processed CSV.

    call_category values accepted:
        'Tenant Support'  → complaint (0)
        'Leasing Inquiry' → inquiry   (1)

    All other rows (e.g. rows with unknown category) are silently dropped.
    N/A values in sentiment/urgency columns are irrelevant — we only use
    transcript and call_category.
    """

    LABEL_MAP = {
        "tenant support": COMPLAINT_LABEL,
        "leasing inquiry": INQUIRY_LABEL,
    }

    def __init__(
        self,
        csv_path: str,
        tokenizer: RobertaTokenizer,
        max_length: int = 128,
    ):
        raw = pd.read_csv(csv_path)

        for col in ("transcript", "call_category"):
            if col not in raw.columns:
                raise ValueError(f"Missing required column: {col}")

        raw["_category_norm"] = (
            raw["call_category"].astype(str).str.strip().str.lower()
        )
        raw = raw[raw["_category_norm"].isin(self.LABEL_MAP)].copy()
        raw["label"] = raw["_category_norm"].map(self.LABEL_MAP)
        raw = raw.reset_index(drop=True)

        self.transcripts = raw["transcript"].astype(str).tolist()
        self.labels = raw["label"].tolist()
        self.tokenizer = tokenizer
        self.max_length = max_length

        n_complaint = sum(1 for l in self.labels if l == COMPLAINT_LABEL)
        n_inquiry = sum(1 for l in self.labels if l == INQUIRY_LABEL)
        logger.info(
            f"Dataset loaded: {len(self.labels)} samples — "
            f"complaint: {n_complaint}, inquiry: {n_inquiry}"
        )

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.transcripts[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label":          torch.tensor(self.labels[idx], dtype=torch.long),
        }


# ==============================================================================
# TRAIN / EVAL LOOPS
# ==============================================================================

def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch in loader:
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels         = batch["label"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
        loss   = criterion(logits, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()
        preds = logits.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total   += labels.size(0)

    return total_loss / len(loader), correct / total


def eval_epoch(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    all_preds  = []
    all_labels = []

    with torch.no_grad():
        for batch in loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels         = batch["label"].to(device)

            logits = model(input_ids, attention_mask)
            loss   = criterion(logits, labels)

            total_loss += loss.item()
            preds = logits.argmax(dim=1)
            correct += (preds == labels).sum().item()
            total   += labels.size(0)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())

    return total_loss / len(loader), correct / total, all_preds, all_labels


# ==============================================================================
# MAIN TRAINING FUNCTION
# ==============================================================================

def train_model(
    csv_path: str,
    output_dir: str,
    batch_size: int = 16,
    epochs: int = 5,
    learning_rate: float = 2e-5,
    device: str = "cpu",
):
    """
    Train the call classifier from scratch.

    Args:
        csv_path:      Path to processed CSV (must have transcript + call_category)
        output_dir:    Directory to save model.pt, tokenizer, and history
        batch_size:    Training batch size
        epochs:        Number of epochs
        learning_rate: AdamW learning rate
        device:        'cpu' or 'cuda'
    """
    logger.info("=" * 70)
    logger.info("Call Classification Agent — Training")
    logger.info("=" * 70)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Tokenizer
    logger.info("\nLoading tokenizer: distilroberta-base")
    tokenizer = RobertaTokenizer.from_pretrained("distilroberta-base")

    # Dataset
    logger.info(f"\nLoading dataset: {csv_path}")
    full_dataset = CallCategoryDataset(csv_path, tokenizer)
    n = len(full_dataset)

    # 80 / 10 / 10 split
    n_train = int(n * 0.80)
    n_val   = int(n * 0.10)
    n_test  = n - n_train - n_val

    generator = torch.Generator().manual_seed(42)
    train_ds, val_ds, test_ds = torch.utils.data.random_split(
        full_dataset, [n_train, n_val, n_test], generator=generator
    )

    logger.info(f"Split: {n_train} train / {n_val} val / {n_test} test")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=batch_size, shuffle=False)
    test_loader  = DataLoader(test_ds,  batch_size=batch_size, shuffle=False)

    # Model
    model = create_model(dropout=0.1, freeze_backbone=False)
    model = model.to(device)

    # Loss with class weights to correct the 60/40 imbalance.
    # complaint (60%) weight=1.0, inquiry (40%) weight=1.5
    class_weights = torch.tensor([1.0, 1.5], dtype=torch.float32).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    logger.info(f"\nTraining config:")
    logger.info(f"  Epochs:        {epochs}")
    logger.info(f"  Batch size:    {batch_size}")
    logger.info(f"  Learning rate: {learning_rate}")
    logger.info(f"  Device:        {device}")
    logger.info(f"  Class weights: complaint=1.0, inquiry=1.5")

    best_val_acc  = 0.0
    history = []

    for epoch in range(epochs):
        t0 = time.time()
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Epoch {epoch + 1}/{epochs}")
        logger.info(f"{'=' * 70}")

        train_loss, train_acc = train_epoch(
            model, train_loader, criterion, optimizer, device
        )
        val_loss, val_acc, _, _ = eval_epoch(
            model, val_loader, criterion, device
        )
        elapsed = time.time() - t0

        logger.info(f"  Train loss: {train_loss:.4f}  acc: {train_acc:.4f}")
        logger.info(f"  Val   loss: {val_loss:.4f}  acc: {val_acc:.4f}")
        logger.info(f"  Time:       {elapsed:.1f}s")

        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss, "train_acc": train_acc,
            "val_loss":   val_loss,   "val_acc":   val_acc,
        })

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            logger.info(f"  New best — saving checkpoint...")
            torch.save(model.state_dict(), out / "model.pt")
            tokenizer.save_pretrained(out)

    # Final evaluation on held-out test set
    logger.info(f"\n{'=' * 70}")
    logger.info("Final Test Evaluation")
    logger.info(f"{'=' * 70}")

    # Load best checkpoint
    model.load_state_dict(torch.load(out / "model.pt", map_location=device))
    test_loss, test_acc, test_preds, test_labels = eval_epoch(
        model, test_loader, criterion, device
    )

    logger.info(f"\n  Test loss:     {test_loss:.4f}")
    logger.info(f"  Test accuracy: {test_acc:.4f}")
    logger.info(
        f"\n  Classification report:\n"
        + classification_report(
            test_labels, test_preds,
            target_names=["complaint", "inquiry"]
        )
    )
    logger.info(
        f"\n  Confusion matrix:\n"
        + str(confusion_matrix(test_labels, test_preds))
    )

    # Save history
    pd.DataFrame(history).to_csv(out / "training_history.csv", index=False)

    logger.info(f"\n{'=' * 70}")
    logger.info("Training complete!")
    logger.info(f"Best val accuracy: {best_val_acc:.4f}")
    logger.info(f"Test accuracy:     {test_acc:.4f}")
    logger.info(f"Model saved to:    {out}")
    logger.info(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: python train.py <csv_path> <output_dir>")
        print("\nExample:")
        print("  python train.py data/processed/processed_multi_task_n7955.csv models/classifier-v1")
        sys.exit(1)

    csv_path   = sys.argv[1]
    output_dir = sys.argv[2]

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    train_model(
        csv_path=csv_path,
        output_dir=output_dir,
        batch_size=16,
        epochs=5,
        learning_rate=2e-5,
        device=device,
    )
