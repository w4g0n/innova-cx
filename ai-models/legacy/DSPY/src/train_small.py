"""
CPU-Friendly Training Script for Small Datasets

Optimized for quick testing and validation without GPU.

Principles Applied:
- Fail-Fast: Validate all inputs before training starts
- Observability: Structured logging with timing and metrics
- Single Responsibility: Each function has ONE job
- Guard Clauses: Early returns for invalid states
- Design by Contract: Explicit preconditions
- Immutability: Config frozen after creation
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field
import logging
import time
from tqdm import tqdm
import json
from datetime import datetime

# Import custom modules
from model_architecture import create_model, count_parameters, ModelConfig

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION (Parse, Don't Validate)
# ==============================================================================

@dataclass  # Note: Not frozen due to validation needing field access
class TrainingConfig:
    """
    Validated training configuration.
    Type proves validity.
    
    Note: Not frozen to allow __post_init__ validation.
    Treat as immutable in practice.
    """
    data_path: str
    output_dir: str
    task: str
    num_epochs: int
    batch_size: int
    learning_rate: float
    max_length: int
    freeze_base: bool
    validation_split: float
    
    def __post_init__(self):
        """Fail-fast: Design by Contract"""
        # Validate data path exists
        if not Path(self.data_path).exists():
            raise FileNotFoundError(f"❌ Data file not found: {self.data_path}")
        
        # Validate task
        valid_tasks = ['sentiment', 'urgency', 'multi']
        if self.task not in valid_tasks:
            raise ValueError(f"❌ Invalid task: {self.task}. Must be in {valid_tasks}")
        
        # Validate numeric ranges
        if self.num_epochs <= 0:
            raise ValueError(f"❌ num_epochs must be positive, got {self.num_epochs}")
        
        if self.batch_size <= 0:
            raise ValueError(f"❌ batch_size must be positive, got {self.batch_size}")
        
        if self.learning_rate <= 0:
            raise ValueError(f"❌ learning_rate must be positive, got {self.learning_rate}")
        
        if self.max_length <= 0:
            raise ValueError(f"❌ max_length must be positive, got {self.max_length}")
        
        if not 0.0 <= self.validation_split < 1.0:
            raise ValueError(f"❌ validation_split must be in [0, 1), got {self.validation_split}")


# ==============================================================================
# DATASET
# ==============================================================================

class ComplaintDataset(Dataset):
    """
    PyTorch Dataset for complaint transcripts with proxy labels.
    
    Single Responsibility: Only handles data loading and tokenization.
    """
    
    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer: RobertaTokenizer,
        max_length: int,
        task: str
    ):
        """
        Initialize dataset.
        
        Args:
            dataframe: DataFrame with 'transcript' and proxy labels
            tokenizer: RoBERTa tokenizer
            max_length: Maximum sequence length
            task: Task type ('sentiment', 'urgency', 'multi')
        """
        # Fail-fast validation
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(f"❌ Expected DataFrame, got {type(dataframe)}")
        
        if 'transcript' not in dataframe.columns:
            raise ValueError("❌ DataFrame must contain 'transcript' column")
        
        self.df = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.task = task
        
        logger.info(f"✓ Created dataset: {len(self.df)} samples, max_len={max_length}")
    
    def __len__(self) -> int:
        return len(self.df)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Get single sample.
        
        Returns:
            Dict with input_ids, attention_mask, and labels
        """
        row = self.df.iloc[idx]
        
        # Tokenize
        encoding = self.tokenizer(
            row['transcript'],
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        # Prepare item
        item = {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0)
        }
        
        # Add labels based on task
        item = self._add_labels(item, row)
        
        return item
    
    def _add_labels(self, item: Dict, row: pd.Series) -> Dict:
        """
        Single Responsibility: Add task-specific labels.
        Guard clause: Returns item unchanged if task invalid.
        """
        if self.task == 'sentiment':
            item['labels'] = torch.tensor(row['proxy_sentiment'], dtype=torch.float)
        
        elif self.task == 'urgency':
            item['labels'] = torch.tensor(row['proxy_urgency'], dtype=torch.float)
        
        elif self.task == 'multi':
            item['sentiment_label'] = torch.tensor(row['proxy_sentiment'], dtype=torch.float)
            item['urgency_label'] = torch.tensor(row['proxy_urgency'], dtype=torch.float)
            
            # Encode categorical features if available
            if 'issue_severity' in row and pd.notna(row['issue_severity']):
                severity_map = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
                item['severity_label'] = torch.tensor(
                    severity_map.get(row['issue_severity'], 1),
                    dtype=torch.long
                )
            
            if 'business_impact' in row and pd.notna(row['business_impact']):
                impact_map = {'low': 0, 'medium': 1, 'medium-high': 2, 'high': 3}
                item['impact_label'] = torch.tensor(
                    impact_map.get(row['business_impact'], 1),
                    dtype=torch.long
                )
        
        return item


# ==============================================================================
# TRAINING LOOP
# ==============================================================================

def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    task: str
) -> float:
    """
    Train for one epoch.
    
    Single Responsibility: Only trains, doesn't evaluate.
    Observability: Progress bar with metrics.
    
    Returns:
        Average loss for epoch
    """
    model.train()
    total_loss = 0.0
    num_batches = len(dataloader)
    
    # Progress bar for observability
    progress_bar = tqdm(dataloader, desc='Training', leave=False)
    
    for batch in progress_bar:
        # Move to device
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        
        # Compute loss (delegated to specialized function)
        loss = _compute_loss(model, batch, input_ids, attention_mask, device, task)
        
        # Backward pass
        optimizer.zero_grad()
        loss.backward()
        
        # Gradient clipping for stability
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        
        optimizer.step()
        
        # Update metrics
        total_loss += loss.item()
        progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})
    
    return total_loss / num_batches


def _compute_loss(
    model: nn.Module,
    batch: Dict,
    input_ids: torch.Tensor,
    attention_mask: torch.Tensor,
    device: torch.device,
    task: str
) -> torch.Tensor:
    """
    Single Responsibility: Compute loss only.
    
    Returns:
        Loss tensor
    """
    if task in ['sentiment', 'urgency']:
        # Single-task loss
        labels = batch['labels'].to(device)
        outputs = model(input_ids, attention_mask)
        loss = nn.MSELoss()(outputs, labels)
    
    elif task == 'multi':
        # Multi-task loss
        outputs = model(input_ids, attention_mask)
        loss = _compute_multitask_loss(outputs, batch, device)
    
    else:
        raise ValueError(f"❌ Unknown task: {task}")
    
    return loss


def _compute_multitask_loss(
    outputs: Dict[str, torch.Tensor],
    batch: Dict,
    device: torch.device
) -> torch.Tensor:
    """
    Single Responsibility: Compute multi-task loss only.
    
    Combines losses with fixed weights.
    """
    loss = torch.tensor(0.0, device=device)
    
    # Sentiment loss (40%)
    if 'sentiment_label' in batch:
        sentiment_loss = nn.MSELoss()(
            outputs['sentiment'],
            batch['sentiment_label'].to(device)
        )
        loss += 0.4 * sentiment_loss
    
    # Urgency loss (40%)
    if 'urgency_label' in batch:
        urgency_loss = nn.MSELoss()(
            outputs['urgency'],
            batch['urgency_label'].to(device)
        )
        loss += 0.4 * urgency_loss
    
    # Severity loss (10%)
    if 'severity_label' in batch:
        severity_loss = nn.CrossEntropyLoss()(
            outputs['severity'],
            batch['severity_label'].to(device)
        )
        loss += 0.1 * severity_loss
    
    # Impact loss (10%)
    if 'impact_label' in batch:
        impact_loss = nn.CrossEntropyLoss()(
            outputs['impact'],
            batch['impact_label'].to(device)
        )
        loss += 0.1 * impact_loss
    
    return loss


# ==============================================================================
# EVALUATION
# ==============================================================================

def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
    task: str
) -> Dict[str, float]:
    """
    Evaluate model on validation set.
    
    Single Responsibility: Only evaluates, doesn't train.
    
    Returns:
        Dict with loss, MAE, RMSE, correlation metrics
    """
    model.eval()
    total_loss = 0.0
    all_predictions = []
    all_labels = []
    
    with torch.no_grad():
        for batch in tqdm(dataloader, desc='Evaluating', leave=False):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            
            if task in ['sentiment', 'urgency']:
                labels = batch['labels'].to(device)
                outputs = model(input_ids, attention_mask)
                
                loss = nn.MSELoss()(outputs, labels)
                total_loss += loss.item()
                
                all_predictions.extend(outputs.cpu().numpy())
                all_labels.extend(labels.cpu().numpy())
            
            elif task == 'multi':
                outputs = model(input_ids, attention_mask)
                loss = _compute_multitask_loss(outputs, batch, device)
                total_loss += loss.item()
                
                # Track sentiment metrics
                if 'sentiment_label' in batch:
                    all_predictions.extend(outputs['sentiment'].cpu().numpy())
                    all_labels.extend(batch['sentiment_label'].cpu().numpy())
    
    # Compute metrics
    metrics = _compute_metrics(all_predictions, all_labels, total_loss, len(dataloader))
    
    return metrics


def _compute_metrics(
    predictions: list,
    labels: list,
    total_loss: float,
    num_batches: int
) -> Dict[str, float]:
    """
    Single Responsibility: Compute evaluation metrics only.
    
    Returns:
        Dict with loss, MAE, RMSE, correlation
    """
    avg_loss = total_loss / num_batches
    
    # Guard clause: Check if we have predictions
    if not predictions or not labels:
        return {'loss': avg_loss, 'mae': 0.0, 'rmse': 0.0, 'correlation': 0.0}
    
    preds = np.array(predictions)
    labs = np.array(labels)
    
    mae = np.mean(np.abs(preds - labs))
    rmse = np.sqrt(np.mean((preds - labs) ** 2))
    
    # Guard clause: Need at least 2 points for correlation
    if len(preds) < 2:
        correlation = 0.0
    else:
        correlation = np.corrcoef(preds, labs)[0, 1]
    
    return {
        'loss': avg_loss,
        'mae': mae,
        'rmse': rmse,
        'correlation': correlation
    }


# ==============================================================================
# MAIN TRAINING FUNCTION
# ==============================================================================

def train_model(config: TrainingConfig) -> tuple[nn.Module, Dict]:
    """
    Main training function.
    
    Design by Contract:
    - Precondition: config must be valid TrainingConfig
    - Postcondition: Returns trained model and history
    
    Args:
        config: Validated TrainingConfig
        
    Returns:
        Tuple of (trained_model, history_dict)
    """
    start_time = time.perf_counter()
    
    logger.info("=" * 60)
    logger.info("🚀 STARTING TRAINING")
    logger.info("=" * 60)
    logger.info(f"Task: {config.task}")
    logger.info(f"Data: {config.data_path}")
    logger.info(f"Device: CPU (optimized)")
    logger.info(f"Frozen base: {config.freeze_base}")
    
    # Load and split data
    train_df, val_df = _load_and_split_data(config)
    
    # Initialize model and tokenizer
    tokenizer = RobertaTokenizer.from_pretrained('roberta-base')
    model = create_model(
        task=config.task,
        freeze_base=config.freeze_base
    )
    
    # Device
    device = torch.device('cpu')
    model = model.to(device)
    
    # Log model info
    params = count_parameters(model)
    logger.info(f"📊 Model: {params['trainable']:,} trainable / {params['total']:,} total")
    
    # Create datasets and dataloaders
    train_dataset = ComplaintDataset(train_df, tokenizer, config.max_length, config.task)
    val_dataset = ComplaintDataset(val_df, tokenizer, config.max_length, config.task)
    
    train_loader = DataLoader(
        train_dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=0  # CPU: must be 0
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=config.batch_size,
        num_workers=0
    )
    
    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=0.01
    )
    
    # Training loop
    best_val_loss = float('inf')
    history = {'train_loss': [], 'val_loss': [], 'val_mae': [], 'val_correlation': []}
    
    for epoch in range(config.num_epochs):
        logger.info(f"\n{'='*60}")
        logger.info(f"📅 Epoch {epoch + 1}/{config.num_epochs}")
        logger.info(f"{'='*60}")
        
        # Train
        train_loss = train_epoch(model, train_loader, optimizer, device, config.task)
        history['train_loss'].append(train_loss)
        logger.info(f"Train Loss: {train_loss:.4f}")
        
        # Evaluate
        val_metrics = evaluate(model, val_loader, device, config.task)
        history['val_loss'].append(val_metrics['loss'])
        history['val_mae'].append(val_metrics['mae'])
        history['val_correlation'].append(val_metrics['correlation'])
        
        logger.info(f"Val Loss: {val_metrics['loss']:.4f}")
        logger.info(f"Val MAE: {val_metrics['mae']:.4f}")
        logger.info(f"Val RMSE: {val_metrics['rmse']:.4f}")
        logger.info(f"Val Correlation: {val_metrics['correlation']:.4f}")
        
        # Save best model
        if val_metrics['loss'] < best_val_loss:
            best_val_loss = val_metrics['loss']
            _save_checkpoint(model, tokenizer, config, best_val_loss, epoch + 1)
    
    # Save history
    _save_history(history, config.output_dir)
    
    # Final summary
    elapsed_sec = time.perf_counter() - start_time
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ TRAINING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total time: {elapsed_sec:.1f}s")
    logger.info(f"Best val loss: {best_val_loss:.4f}")
    logger.info(f"Model saved: {config.output_dir}")
    
    return model, history


def _load_and_split_data(config: TrainingConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Single Responsibility: Load and split data only.
    
    Returns:
        Tuple of (train_df, val_df)
    """
    logger.info(f"📂 Loading data from {config.data_path}")
    df = pd.read_csv(config.data_path)
    logger.info(f"✓ Loaded {len(df)} records")
    
    # Split
    val_size = int(len(df) * config.validation_split)
    
    # Guard clause: Ensure we have validation data
    if val_size == 0 and len(df) > 10:
        val_size = min(10, len(df) // 10)
    
    train_df = df.iloc[:-val_size] if val_size > 0 else df
    val_df = df.iloc[-val_size:] if val_size > 0 else df.sample(min(10, len(df)))
    
    logger.info(f"✓ Train: {len(train_df)} samples")
    logger.info(f"✓ Val: {len(val_df)} samples")
    
    return train_df, val_df


def _save_checkpoint(
    model: nn.Module,
    tokenizer: RobertaTokenizer,
    config: TrainingConfig,
    best_loss: float,
    epoch: int
) -> None:
    """
    Single Responsibility: Save model checkpoint only.
    Observability: Logs save action.
    """
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save model weights
    torch.save(model.state_dict(), output_path / 'model.pt')
    
    # Save tokenizer
    tokenizer.save_pretrained(output_path)
    
    # Save config
    config_dict = {
        'task': config.task,
        'max_length': config.max_length,
        'freeze_base': config.freeze_base,
        'best_val_loss': best_loss,
        'best_epoch': epoch,
        'timestamp': datetime.now().isoformat()
    }
    
    with open(output_path / 'config.json', 'w') as f:
        json.dump(config_dict, f, indent=2)
    
    logger.info(f"💾 Saved checkpoint (val_loss: {best_loss:.4f})")


def _save_history(history: Dict, output_dir: str) -> None:
    """Single Responsibility: Save training history only"""
    history_df = pd.DataFrame(history)
    output_path = Path(output_dir)
    history_df.to_csv(output_path / 'training_history.csv', index=False)
    logger.info(f"💾 Saved training history")


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    # Guard clause: Check arguments
    if len(sys.argv) < 2:
        print("Usage: python train_small.py <data_path> [task] [output_dir]")
        print("Example: python train_small.py data/processed/processed_n50.csv sentiment models/test")
        sys.exit(1)
    
    # Parse arguments
    data_path = sys.argv[1]
    task = sys.argv[2] if len(sys.argv) > 2 else 'sentiment'
    output_dir = sys.argv[3] if len(sys.argv) > 3 else f'models/{task}-small'
    
    # Create validated config
    config = TrainingConfig(
        data_path=data_path,
        output_dir=output_dir,
        task=task,
        num_epochs=5,
        batch_size=4,
        learning_rate=3e-5,
        max_length=256,
        freeze_base=True,
        validation_split=0.2
    )
    
    # Train
    model, history = train_model(config)
    
    print(f"\n✅ Training complete!")
    print(f"   Model: {output_dir}")
    print(f"   History: {output_dir}/training_history.csv")
