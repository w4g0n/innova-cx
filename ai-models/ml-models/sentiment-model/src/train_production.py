"""
Multi-Task Training Script

Trains RoBERTa to output 3 things:
1. Sentiment (-1 to +1)
2. Urgency (0 to 1)
3. Keywords (multi-label classification)

This REPLACES your current train_production.py
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from model_architecture_UPDATED import create_model, get_keyword_vocabulary


# ==============================================================================
# DATASET
# ==============================================================================

class MultiTaskDataset(Dataset):
    """
    Dataset for multi-task training.
    
    Loads data with:
    - transcript (text)
    - proxy_sentiment (float)
    - proxy_urgency (float)
    - proxy_keywords_str (comma-separated indices)
    """
    
    def __init__(
        self,
        csv_path: str,
        tokenizer: RobertaTokenizer,
        max_length: int = 128
    ):
        self.df = pd.read_csv(csv_path)
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.num_keywords = len(get_keyword_vocabulary())
        
        # Validate columns
        required = ['transcript', 'proxy_sentiment', 'proxy_urgency', 'proxy_keywords_str']
        for col in required:
            if col not in self.df.columns:
                raise ValueError(f"❌ Missing column: {col}")
        
        logger.info(f"✓ Dataset loaded: {len(self.df)} samples")
    
    def __len__(self):
        return len(self.df)
    
    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        
        # Tokenize text
        text = str(row['transcript'])
        encoding = self.tokenizer(
            text,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        # Labels
        sentiment = torch.tensor(row['proxy_sentiment'], dtype=torch.float32)
        urgency = torch.tensor(row['proxy_urgency'], dtype=torch.float32)
        
        # Parse keywords (convert "1,5,12" → [0,1,0,0,0,1,0,...,1,...])
        keywords_binary = torch.zeros(self.num_keywords, dtype=torch.float32)
        keywords_str = str(row['proxy_keywords_str'])
        
        # Handle NaN, empty, or invalid values
        if keywords_str and keywords_str != 'nan' and keywords_str.strip():
            try:
                indices = [int(x) for x in keywords_str.split(',') if x.strip()]
                for idx in indices:
                    if 0 <= idx < self.num_keywords:
                        keywords_binary[idx] = 1.0
            except (ValueError, AttributeError):
                # If parsing fails, leave as all zeros
                pass
        
        return {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0),
            'sentiment': sentiment,
            'urgency': urgency,
            'keywords': keywords_binary
        }


# ==============================================================================
# MULTI-TASK LOSS
# ==============================================================================

class MultiTaskLoss(nn.Module):
    """
    Combined loss for all 3 tasks.
    
    Loss = w1*sentiment_loss + w2*urgency_loss + w3*keyword_loss
    
    Where:
    - sentiment_loss: MSE (regression)
    - urgency_loss: MSE (regression)
    - keyword_loss: BCE (multi-label classification)
    """
    
    def __init__(
        self,
        sentiment_weight: float = 1.0,
        urgency_weight: float = 1.0,
        keyword_weight: float = 0.5
    ):
        super().__init__()
        
        self.sentiment_weight = sentiment_weight
        self.urgency_weight = urgency_weight
        self.keyword_weight = keyword_weight
        
        # Loss functions
        self.mse = nn.MSELoss()
        self.bce = nn.BCELoss()
        
        logger.info(f"✓ MultiTaskLoss initialized")
        logger.info(f"  Weights: sentiment={sentiment_weight}, urgency={urgency_weight}, keywords={keyword_weight}")
    
    def forward(
        self,
        predictions: Dict[str, torch.Tensor],
        targets: Dict[str, torch.Tensor]
    ) -> Dict[str, torch.Tensor]:
        """
        Calculate loss for all tasks.
        
        Returns:
            {
                'total': combined loss,
                'sentiment': sentiment loss,
                'urgency': urgency loss,
                'keywords': keyword loss
            }
        """
        # Individual losses
        sentiment_loss = self.mse(predictions['sentiment'], targets['sentiment'])
        urgency_loss = self.mse(predictions['urgency'], targets['urgency'])
        keyword_loss = self.bce(predictions['keywords'], targets['keywords'])
        
        # Combined loss
        total_loss = (
            self.sentiment_weight * sentiment_loss +
            self.urgency_weight * urgency_loss +
            self.keyword_weight * keyword_loss
        )
        
        return {
            'total': total_loss,
            'sentiment': sentiment_loss,
            'urgency': urgency_loss,
            'keywords': keyword_loss
        }


# ==============================================================================
# TRAINING LOOP
# ==============================================================================

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
    Train multi-task model.
    
    Args:
        csv_path: Path to processed CSV with proxy labels
        output_dir: Where to save trained model
        model_name: HuggingFace model name
        batch_size: Batch size
        epochs: Number of epochs
        learning_rate: Learning rate
        train_split: Train/val split ratio
        device: 'cpu' or 'cuda'
    """
    logger.info("="*70)
    logger.info("Multi-Task Model Training")
    logger.info("="*70)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load tokenizer
    logger.info(f"\n📝 Loading tokenizer: {model_name}")
    tokenizer = RobertaTokenizer.from_pretrained(model_name)
    
    # Load dataset
    logger.info(f"\n📂 Loading dataset: {csv_path}")
    full_dataset = MultiTaskDataset(csv_path, tokenizer)
    
    # Train/val split
    train_size = int(len(full_dataset) * train_split)
    val_size = len(full_dataset) - train_size
    
    train_dataset, val_dataset = torch.utils.data.random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42)
    )
    
    logger.info(f"✓ Split: {train_size} train, {val_size} val")
    
    # Dataloaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    # Create model
    logger.info(f"\n🤖 Creating model...")
    model = create_model(model_name=model_name, dropout=0.1, freeze_base=False)
    model = model.to(device)
    
    # Loss and optimizer
    criterion = MultiTaskLoss(
        sentiment_weight=1.0,
        urgency_weight=1.0,
        keyword_weight=0.5
    )
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    
    # Training
    logger.info(f"\n🏃 Starting training...")
    logger.info(f"  Epochs: {epochs}")
    logger.info(f"  Batch size: {batch_size}")
    logger.info(f"  Learning rate: {learning_rate}")
    logger.info(f"  Device: {device}")
    
    best_val_loss = float('inf')
    history = []
    
    for epoch in range(epochs):
        epoch_start = time.time()
        logger.info(f"\n{'='*70}")
        logger.info(f"Epoch {epoch+1}/{epochs}")
        logger.info(f"{'='*70}")
        
        # Train
        train_metrics = train_epoch(model, train_loader, criterion, optimizer, device)
        
        # Validate
        val_metrics = validate_epoch(model, val_loader, criterion, device)
        
        epoch_time = time.time() - epoch_start
        
        # Log
        logger.info(f"\n📊 Epoch {epoch+1} Results:")
        logger.info(f"  Train Loss: {train_metrics['total']:.4f} " +
                   f"(sent: {train_metrics['sentiment']:.4f}, " +
                   f"urg: {train_metrics['urgency']:.4f}, " +
                   f"key: {train_metrics['keywords']:.4f})")
        logger.info(f"  Val Loss:   {val_metrics['total']:.4f} " +
                   f"(sent: {val_metrics['sentiment']:.4f}, " +
                   f"urg: {val_metrics['urgency']:.4f}, " +
                   f"key: {val_metrics['keywords']:.4f})")
        logger.info(f"  Time: {epoch_time:.1f}s")
        
        # Save history
        history.append({
            'epoch': epoch + 1,
            'train_loss': train_metrics['total'],
            'val_loss': val_metrics['total'],
            **{f'train_{k}': v for k, v in train_metrics.items() if k != 'total'},
            **{f'val_{k}': v for k, v in val_metrics.items() if k != 'total'}
        })
        
        # Save best model
        if val_metrics['total'] < best_val_loss:
            best_val_loss = val_metrics['total']
            logger.info(f"  ✓ New best! Saving model...")
            
            # Save model
            torch.save(model.state_dict(), output_path / 'model.pt')
            tokenizer.save_pretrained(output_path)
            logger.info(f"  ✓ Saved to: {output_path}")
    
    # Save history
    history_df = pd.DataFrame(history)
    history_df.to_csv(output_path / 'training_history.csv', index=False)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ Training complete!")
    logger.info(f"{'='*70}")
    logger.info(f"Best val loss: {best_val_loss:.4f}")
    logger.info(f"Model saved to: {output_path}")


def train_epoch(model, loader, criterion, optimizer, device):
    """Train for one epoch"""
    model.train()
    total_losses = {'total': 0, 'sentiment': 0, 'urgency': 0, 'keywords': 0}
    
    for batch in loader:
        # Move to device
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        targets = {
            'sentiment': batch['sentiment'].to(device),
            'urgency': batch['urgency'].to(device),
            'keywords': batch['keywords'].to(device)
        }
        
        # Forward
        optimizer.zero_grad()
        outputs = model(input_ids, attention_mask)
        
        # Loss
        losses = criterion(outputs, targets)
        
        # Backward
        losses['total'].backward()
        optimizer.step()
        
        # Accumulate
        for k, v in losses.items():
            total_losses[k] += v.item()
    
    # Average
    return {k: v / len(loader) for k, v in total_losses.items()}


def validate_epoch(model, loader, criterion, device):
    """Validate for one epoch"""
    model.eval()
    total_losses = {'total': 0, 'sentiment': 0, 'urgency': 0, 'keywords': 0}
    
    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            targets = {
                'sentiment': batch['sentiment'].to(device),
                'urgency': batch['urgency'].to(device),
                'keywords': batch['keywords'].to(device)
            }
            
            outputs = model(input_ids, attention_mask)
            losses = criterion(outputs, targets)
            
            for k, v in losses.items():
                total_losses[k] += v.item()
    
    return {k: v / len(loader) for k, v in total_losses.items()}


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("\nUsage: python train_production_UPDATED.py <csv_path> <output_dir>")
        print("\nExample:")
        print("  python train_production_UPDATED.py data/processed/processed_multi_task_n1000.csv models/multi-task-model")
        print()
        sys.exit(1)
    
    csv_path = sys.argv[1]
    output_dir = sys.argv[2]
    
    train_model(
        csv_path=csv_path,
        output_dir=output_dir,
        batch_size=8,
        epochs=10,
        learning_rate=2e-5,
        device='cpu'  # Change to 'cuda' if GPU available
    )
