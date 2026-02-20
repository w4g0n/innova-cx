"""
Single-Task Sentiment Training Script (V7)

Trains RoBERTaSentimentModel on proxy_sentiment labels only.
Loss: MSE between predicted sentiment and proxy_sentiment.

Multi-task loss (urgency + keywords) has been removed.
The urgency and keyword columns in the CSV are simply ignored.

Usage:
    python train_production.py <csv_path> <output_dir>

Example:
    python train_production.py data/processed/processed_multi_task_n1500.csv models/sentiment-v7
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer
import pandas as pd
from pathlib import Path
import time
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from model_architecture import create_model


# ==============================================================================
# DATASET
# ==============================================================================

class SentimentDataset(Dataset):
    """
    Loads transcript and proxy_sentiment columns.
    Any additional columns in the CSV (proxy_urgency, proxy_keywords_str, etc.)
    are ignored — they cause no harm sitting there unused.
    """

    def __init__(self, csv_path: str, tokenizer: RobertaTokenizer, max_length: int = 128):
        self.df = pd.read_csv(csv_path)
        self.tokenizer = tokenizer
        self.max_length = max_length

        for col in ('transcript', 'proxy_sentiment'):
            if col not in self.df.columns:
                raise ValueError(f"Missing required column: {col}")

        logger.info(f"Dataset loaded: {len(self.df)} samples")

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]

        encoding = self.tokenizer(
            str(row['transcript']),
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'sentiment': torch.tensor(float(row['proxy_sentiment']), dtype=torch.float32)
        }


# ==============================================================================
# TRAINING LOOP
# ==============================================================================

def train_epoch(model, loader, criterion, optimizer, device):
    model.train()
    total_loss = 0.0

    for batch in loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        targets = batch['sentiment'].to(device)

        optimizer.zero_grad()
        predictions = model(input_ids, attention_mask)
        loss = criterion(predictions, targets)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(loader)


def validate_epoch(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0

    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            targets = batch['sentiment'].to(device)

            predictions = model(input_ids, attention_mask)
            loss = criterion(predictions, targets)
            total_loss += loss.item()

    return total_loss / len(loader)


def train_model(
    csv_path: str,
    output_dir: str,
    model_name: str = 'roberta-base',
    batch_size: int = 8,
    epochs: int = 10,
    learning_rate: float = 2e-5,
    train_split: float = 0.8,
    device: str = 'cpu'
):
    """
    Train the single-head sentiment model from scratch.

    Args:
        csv_path:      Path to processed CSV (must have transcript + proxy_sentiment)
        output_dir:    Directory where model.pt and tokenizer will be saved
        model_name:    HuggingFace base model
        batch_size:    Training batch size
        epochs:        Number of training epochs
        learning_rate: AdamW learning rate
        train_split:   Fraction of data used for training (rest = validation)
        device:        'cpu' or 'cuda'
    """
    logger.info("=" * 70)
    logger.info("Sentiment Model Training (V7 — single-task MSE)")
    logger.info("=" * 70)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Tokenizer
    logger.info(f"\nLoading tokenizer: {model_name}")
    tokenizer = RobertaTokenizer.from_pretrained(model_name)

    # Dataset
    logger.info(f"\nLoading dataset: {csv_path}")
    full_dataset = SentimentDataset(csv_path, tokenizer)

    train_size = int(len(full_dataset) * train_split)
    val_size = len(full_dataset) - train_size

    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )

    logger.info(f"Split: {train_size} train / {val_size} val")

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    # Model
    logger.info(f"\nCreating model...")
    model = create_model(model_name=model_name, dropout=0.1, freeze_base=False)
    model = model.to(device)

    # Loss: MSE only — no urgency, no keywords
    criterion = nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    logger.info(f"\nStarting training")
    logger.info(f"  Epochs:        {epochs}")
    logger.info(f"  Batch size:    {batch_size}")
    logger.info(f"  Learning rate: {learning_rate}")
    logger.info(f"  Device:        {device}")

    best_val_loss = float('inf')
    history = []

    for epoch in range(epochs):
        t0 = time.time()
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Epoch {epoch + 1}/{epochs}")
        logger.info(f"{'=' * 70}")

        train_loss = train_epoch(model, train_loader, criterion, optimizer, device)
        val_loss = validate_epoch(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        logger.info(f"  Train loss: {train_loss:.4f}")
        logger.info(f"  Val loss:   {val_loss:.4f}")
        logger.info(f"  Time:       {elapsed:.1f}s")

        history.append({'epoch': epoch + 1, 'train_loss': train_loss, 'val_loss': val_loss})

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            logger.info(f"  New best — saving model...")
            torch.save(model.state_dict(), output_path / 'model.pt')
            tokenizer.save_pretrained(output_path)
            logger.info(f"  Saved to: {output_path}")

    pd.DataFrame(history).to_csv(output_path / 'training_history.csv', index=False)

    logger.info(f"\n{'=' * 70}")
    logger.info(f"Training complete!")
    logger.info(f"Best val loss: {best_val_loss:.4f}")
    logger.info(f"Model saved to: {output_path}")
    logger.info(f"{'=' * 70}")


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\nUsage: python train_production.py <csv_path> <output_dir>")
        print("\nExample:")
        print("  python train_production.py data/processed/processed_multi_task_n1500.csv models/sentiment-v7")
        sys.exit(1)

    csv_path = sys.argv[1]
    output_dir = sys.argv[2]

    # Auto-detect GPU
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"Device: {device}")

    train_model(
        csv_path=csv_path,
        output_dir=output_dir,
        batch_size=8,
        epochs=10,
        learning_rate=2e-5,
        device=device
    )
