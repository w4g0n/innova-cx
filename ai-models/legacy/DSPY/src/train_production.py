"""
Full-Scale Production Training Script

For AWS deployment with GPU support, larger datasets, and full fine-tuning.

Key Changes from train_small.py:
- GPU support (CUDA)
- Unfrozen base model (fine-tune all layers)
- Larger batch sizes
- Learning rate scheduling
- Early stopping
- Model checkpointing
- Weights & Biases integration (optional)
- Multi-task training support
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer, get_linear_schedule_with_warmup
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass
import logging
import time
from tqdm import tqdm
import json
from datetime import datetime
import os

# Import custom modules
from model_architecture import create_model, count_parameters

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# PRODUCTION CONFIGURATION
# ==============================================================================

@dataclass
class ProductionConfig:
    """
    Production training configuration for AWS deployment.
    Optimized for GPU training on full datasets.
    """
    # Data
    data_path: str
    output_dir: str
    task: str = 'sentiment'  # 'sentiment', 'urgency', 'multi'
    
    # Training
    num_epochs: int = 10
    batch_size: int = 16  # GPU can handle larger batches
    learning_rate: float = 2e-5  # Lower for fine-tuning
    weight_decay: float = 0.01
    warmup_steps: int = 100
    max_grad_norm: float = 1.0
    
    # Model
    model_name: str = 'roberta-base'
    max_length: int = 512  # Longer sequences for full model
    dropout: float = 0.1
    freeze_base: bool = False  # Fine-tune all layers!
    
    # Validation
    validation_split: float = 0.15
    eval_steps: int = 100  # Evaluate every N steps
    
    # Checkpointing
    save_steps: int = 500
    save_total_limit: int = 3
    early_stopping_patience: int = 5
    
    # Hardware
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'
    num_workers: int = 4  # DataLoader workers
    fp16: bool = torch.cuda.is_available()  # Mixed precision
    
    # Logging
    logging_steps: int = 50
    wandb_project: Optional[str] = None  # Set to enable W&B
    
    def __post_init__(self):
        """Validate configuration"""
        if not Path(self.data_path).exists():
            raise FileNotFoundError(f"❌ Data file not found: {self.data_path}")
        
        if self.task not in ['sentiment', 'urgency', 'multi']:
            raise ValueError(f"❌ Invalid task: {self.task}")
        
        if self.device == 'cpu' and self.fp16:
            logger.warning("⚠️ FP16 not available on CPU, disabling")
            self.fp16 = False
        
        # Create output directory
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ Config validated")
        logger.info(f"   Device: {self.device}")
        logger.info(f"   FP16: {self.fp16}")
        logger.info(f"   Freeze base: {self.freeze_base}")


# ==============================================================================
# DATASET (Same as train_small.py)
# ==============================================================================

class ComplaintDataset(Dataset):
    """PyTorch Dataset for complaint transcripts"""
    
    def __init__(
        self,
        dataframe: pd.DataFrame,
        tokenizer: RobertaTokenizer,
        max_length: int,
        task: str
    ):
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(f"❌ Expected DataFrame, got {type(dataframe)}")
        
        if 'transcript' not in dataframe.columns:
            raise ValueError("❌ DataFrame must contain 'transcript' column")
        
        self.df = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.task = task
    
    def __len__(self) -> int:
        return len(self.df)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        row = self.df.iloc[idx]
        
        encoding = self.tokenizer(
            row['transcript'],
            add_special_tokens=True,
            max_length=self.max_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        
        item = {
            'input_ids': encoding['input_ids'].squeeze(0),
            'attention_mask': encoding['attention_mask'].squeeze(0)
        }
        
        # Add task-specific labels
        if self.task == 'sentiment':
            item['labels'] = torch.tensor(row['proxy_sentiment'], dtype=torch.float)
        elif self.task == 'urgency':
            item['labels'] = torch.tensor(row['proxy_urgency'], dtype=torch.float)
        elif self.task == 'multi':
            item['sentiment_label'] = torch.tensor(row['proxy_sentiment'], dtype=torch.float)
            item['urgency_label'] = torch.tensor(row['proxy_urgency'], dtype=torch.float)
            
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
# TRAINING WITH FULL FEATURES
# ==============================================================================

class Trainer:
    """
    Production trainer with:
    - GPU support
    - Mixed precision (FP16)
    - Learning rate scheduling
    - Early stopping
    - Checkpointing
    - Weights & Biases logging
    """
    
    def __init__(self, config: ProductionConfig):
        self.config = config
        self.device = torch.device(config.device)
        
        # Initialize tracking
        self.global_step = 0
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        
        # Load data
        self.train_df, self.val_df = self._load_and_split_data()
        
        # Initialize model
        self.tokenizer = RobertaTokenizer.from_pretrained(config.model_name)
        self.model = self._create_model()
        
        # Create dataloaders
        self.train_loader, self.val_loader = self._create_dataloaders()
        
        # Initialize optimizer and scheduler
        self.optimizer, self.scheduler = self._create_optimizer()
        
        # Mixed precision scaler
        self.scaler = torch.cuda.amp.GradScaler() if config.fp16 else None
        
        # Weights & Biases
        if config.wandb_project:
            self._init_wandb()
    
    def _load_and_split_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load and split dataset"""
        logger.info(f"📂 Loading data from {self.config.data_path}")
        df = pd.read_csv(self.config.data_path)
        logger.info(f"✓ Loaded {len(df)} records")
        
        # Split
        val_size = int(len(df) * self.config.validation_split)
        val_size = max(val_size, min(10, len(df) // 10))
        
        train_df = df.iloc[:-val_size]
        val_df = df.iloc[-val_size:]
        
        logger.info(f"✓ Train: {len(train_df)} samples")
        logger.info(f"✓ Val: {len(val_df)} samples")
        
        return train_df, val_df
    
    def _create_model(self) -> nn.Module:
        """Create and configure model"""
        model = create_model(
            task=self.config.task,
            model_name=self.config.model_name,
            freeze_base=self.config.freeze_base,
            dropout=self.config.dropout
        )
        
        model = model.to(self.device)
        
        params = count_parameters(model)
        logger.info(f"📊 Model parameters:")
        logger.info(f"   Total: {params['total']:,}")
        logger.info(f"   Trainable: {params['trainable']:,} ({params['trainable_pct']:.1f}%)")
        
        return model
    
    def _create_dataloaders(self) -> tuple[DataLoader, DataLoader]:
        """Create train and validation dataloaders"""
        train_dataset = ComplaintDataset(
            self.train_df,
            self.tokenizer,
            self.config.max_length,
            self.config.task
        )
        
        val_dataset = ComplaintDataset(
            self.val_df,
            self.tokenizer,
            self.config.max_length,
            self.config.task
        )
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=self.config.num_workers,
            pin_memory=True if self.config.device == 'cuda' else False
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=self.config.batch_size,
            num_workers=self.config.num_workers,
            pin_memory=True if self.config.device == 'cuda' else False
        )
        
        return train_loader, val_loader
    
    def _create_optimizer(self) -> tuple[torch.optim.Optimizer, torch.optim.lr_scheduler.LambdaLR]:
        """Create optimizer with weight decay and learning rate scheduler"""
        # Separate parameters for weight decay
        no_decay = ['bias', 'LayerNorm.weight']
        optimizer_grouped_parameters = [
            {
                'params': [p for n, p in self.model.named_parameters() 
                          if not any(nd in n for nd in no_decay)],
                'weight_decay': self.config.weight_decay
            },
            {
                'params': [p for n, p in self.model.named_parameters() 
                          if any(nd in n for nd in no_decay)],
                'weight_decay': 0.0
            }
        ]
        
        optimizer = torch.optim.AdamW(
            optimizer_grouped_parameters,
            lr=self.config.learning_rate
        )
        
        # Learning rate scheduler
        num_training_steps = len(self.train_loader) * self.config.num_epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=self.config.warmup_steps,
            num_training_steps=num_training_steps
        )
        
        logger.info(f"✓ Optimizer: AdamW (lr={self.config.learning_rate})")
        logger.info(f"✓ Scheduler: Linear warmup ({self.config.warmup_steps} steps)")
        
        return optimizer, scheduler
    
    def _init_wandb(self):
        """Initialize Weights & Biases logging"""
        try:
            import wandb
            wandb.init(
                project=self.config.wandb_project,
                config=vars(self.config)
            )
            logger.info(f"✓ Initialized Weights & Biases")
        except ImportError:
            logger.warning("⚠️ wandb not installed, skipping W&B logging")
            self.config.wandb_project = None
    
    def train(self):
        """Main training loop"""
        logger.info("="*60)
        logger.info("🚀 STARTING PRODUCTION TRAINING")
        logger.info("="*60)
        
        start_time = time.perf_counter()
        
        for epoch in range(self.config.num_epochs):
            logger.info(f"\n{'='*60}")
            logger.info(f"📅 Epoch {epoch + 1}/{self.config.num_epochs}")
            logger.info(f"{'='*60}")
            
            # Train
            train_metrics = self._train_epoch()
            
            # Evaluate
            val_metrics = self._evaluate()
            
            # Log
            self._log_metrics(epoch, train_metrics, val_metrics)
            
            # Save checkpoint
            self._save_checkpoint(epoch, val_metrics['loss'])
            
            # Early stopping
            if self._check_early_stopping(val_metrics['loss']):
                logger.info(f"🛑 Early stopping triggered after {epoch + 1} epochs")
                break
        
        # Final summary
        elapsed_sec = time.perf_counter() - start_time
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ TRAINING COMPLETE")
        logger.info(f"{'='*60}")
        logger.info(f"Total time: {elapsed_sec/60:.1f} minutes")
        logger.info(f"Best val loss: {self.best_val_loss:.4f}")
        logger.info(f"Model saved: {self.config.output_dir}")
    
    def _train_epoch(self) -> Dict[str, float]:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0.0
        
        progress_bar = tqdm(
            self.train_loader,
            desc='Training',
            leave=False
        )
        
        for batch in progress_bar:
            # Move to device
            input_ids = batch['input_ids'].to(self.device)
            attention_mask = batch['attention_mask'].to(self.device)
            
            # Mixed precision training
            if self.config.fp16:
                with torch.cuda.amp.autocast():
                    loss = self._compute_loss(batch, input_ids, attention_mask)
                
                self.scaler.scale(loss).backward()
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.max_grad_norm
                )
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                loss = self._compute_loss(batch, input_ids, attention_mask)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    self.model.parameters(),
                    self.config.max_grad_norm
                )
                self.optimizer.step()
            
            self.scheduler.step()
            self.optimizer.zero_grad()
            
            total_loss += loss.item()
            self.global_step += 1
            
            progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})
            
            # Periodic logging
            if self.global_step % self.config.logging_steps == 0:
                self._log_step(loss.item())
        
        return {'loss': total_loss / len(self.train_loader)}
    
    def _compute_loss(
        self,
        batch: Dict,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor
    ) -> torch.Tensor:
        """Compute loss based on task"""
        if self.config.task in ['sentiment', 'urgency']:
            labels = batch['labels'].to(self.device)
            outputs = self.model(input_ids, attention_mask)
            loss = nn.MSELoss()(outputs, labels)
        
        elif self.config.task == 'multi':
            outputs = self.model(input_ids, attention_mask)
            loss = torch.tensor(0.0, device=self.device)
            
            if 'sentiment_label' in batch:
                sentiment_loss = nn.MSELoss()(
                    outputs['sentiment'],
                    batch['sentiment_label'].to(self.device)
                )
                loss += 0.4 * sentiment_loss
            
            if 'urgency_label' in batch:
                urgency_loss = nn.MSELoss()(
                    outputs['urgency'],
                    batch['urgency_label'].to(self.device)
                )
                loss += 0.4 * urgency_loss
            
            if 'severity_label' in batch:
                severity_loss = nn.CrossEntropyLoss()(
                    outputs['severity'],
                    batch['severity_label'].to(self.device)
                )
                loss += 0.1 * severity_loss
            
            if 'impact_label' in batch:
                impact_loss = nn.CrossEntropyLoss()(
                    outputs['impact'],
                    batch['impact_label'].to(self.device)
                )
                loss += 0.1 * impact_loss
        
        return loss
    
    def _evaluate(self) -> Dict[str, float]:
        """Evaluate on validation set"""
        self.model.eval()
        total_loss = 0.0
        all_predictions = []
        all_labels = []
        
        with torch.no_grad():
            for batch in tqdm(self.val_loader, desc='Evaluating', leave=False):
                input_ids = batch['input_ids'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)
                
                if self.config.task in ['sentiment', 'urgency']:
                    labels = batch['labels'].to(self.device)
                    outputs = self.model(input_ids, attention_mask)
                    
                    loss = nn.MSELoss()(outputs, labels)
                    total_loss += loss.item()
                    
                    all_predictions.extend(outputs.cpu().numpy())
                    all_labels.extend(labels.cpu().numpy())
                
                elif self.config.task == 'multi':
                    outputs = self.model(input_ids, attention_mask)
                    loss = self._compute_loss(batch, input_ids, attention_mask)
                    total_loss += loss.item()
                    
                    if 'sentiment_label' in batch:
                        all_predictions.extend(outputs['sentiment'].cpu().numpy())
                        all_labels.extend(batch['sentiment_label'].cpu().numpy())
        
        # Compute metrics
        avg_loss = total_loss / len(self.val_loader)
        
        if all_predictions and all_labels:
            preds = np.array(all_predictions)
            labs = np.array(all_labels)
            
            mae = np.mean(np.abs(preds - labs))
            rmse = np.sqrt(np.mean((preds - labs) ** 2))
            correlation = np.corrcoef(preds, labs)[0, 1] if len(preds) > 1 else 0.0
        else:
            mae = rmse = correlation = 0.0
        
        return {
            'loss': avg_loss,
            'mae': mae,
            'rmse': rmse,
            'correlation': correlation
        }
    
    def _log_metrics(self, epoch: int, train_metrics: Dict, val_metrics: Dict):
        """Log metrics to console and W&B"""
        logger.info(f"Train Loss: {train_metrics['loss']:.4f}")
        logger.info(f"Val Loss: {val_metrics['loss']:.4f}")
        logger.info(f"Val MAE: {val_metrics['mae']:.4f}")
        logger.info(f"Val RMSE: {val_metrics['rmse']:.4f}")
        logger.info(f"Val Correlation: {val_metrics['correlation']:.4f}")
        
        if self.config.wandb_project:
            try:
                import wandb
                wandb.log({
                    'epoch': epoch,
                    'train_loss': train_metrics['loss'],
                    'val_loss': val_metrics['loss'],
                    'val_mae': val_metrics['mae'],
                    'val_rmse': val_metrics['rmse'],
                    'val_correlation': val_metrics['correlation'],
                    'learning_rate': self.scheduler.get_last_lr()[0]
                })
            except:
                pass
    
    def _log_step(self, loss: float):
        """Log individual training step"""
        if self.config.wandb_project:
            try:
                import wandb
                wandb.log({
                    'step': self.global_step,
                    'step_loss': loss,
                    'learning_rate': self.scheduler.get_last_lr()[0]
                })
            except:
                pass
    
    def _save_checkpoint(self, epoch: int, val_loss: float):
        """Save model checkpoint"""
        output_path = Path(self.config.output_dir)
        
        # Save if best
        if val_loss < self.best_val_loss:
            self.best_val_loss = val_loss
            
            # Save model
            torch.save(self.model.state_dict(), output_path / 'model.pt')
            
            # Save tokenizer
            self.tokenizer.save_pretrained(output_path)
            
            # Save config
            config_dict = {
                'task': self.config.task,
                'max_length': self.config.max_length,
                'freeze_base': self.config.freeze_base,
                'best_val_loss': val_loss,
                'best_epoch': epoch + 1,
                'timestamp': datetime.now().isoformat()
            }
            
            with open(output_path / 'config.json', 'w') as f:
                json.dump(config_dict, f, indent=2)
            
            logger.info(f"💾 Saved best checkpoint (val_loss: {val_loss:.4f})")
    
    def _check_early_stopping(self, val_loss: float) -> bool:
        """Check if early stopping should trigger"""
        if val_loss < self.best_val_loss:
            self.patience_counter = 0
            return False
        
        self.patience_counter += 1
        
        if self.patience_counter >= self.config.early_stopping_patience:
            return True
        
        logger.info(f"⏳ Patience: {self.patience_counter}/{self.config.early_stopping_patience}")
        return False


# ==============================================================================
# CLI ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python train_production.py <data_path> [task] [output_dir]")
        print("Example: python train_production.py data/processed/processed_n1000.csv sentiment models/production")
        sys.exit(1)
    
    # Parse arguments
    data_path = sys.argv[1]
    task = sys.argv[2] if len(sys.argv) > 2 else 'sentiment'
    output_dir = sys.argv[3] if len(sys.argv) > 3 else f'models/{task}-production'
    
    # Create production config
    config = ProductionConfig(
        data_path=data_path,
        output_dir=output_dir,
        task=task,
        num_epochs=10,
        batch_size=16,
        learning_rate=2e-5,
        max_length=512,
        freeze_base=False,  # Full fine-tuning
        validation_split=0.15,
        early_stopping_patience=5
    )
    
    # Train
    trainer = Trainer(config)
    trainer.train()
    
    print(f"\n✅ Production training complete!")
    print(f"   Model: {output_dir}")
