"""
=============================================================================
STEP 3: THREE-MODEL SENTIMENT COMPARISON
=============================================================================

Trains/initializes three sentiment models, evaluates on same test set,
generates comparison report. See reasoning in step2_augment.py header.

MODELS:
  1. RoBERTa - Fine-tuned transformer on our domain data
  2. VADER   - Rule-based lexicon (zero-shot baseline)
  3. TweetNLP - Pre-trained social media sentiment (transfer learning)

USAGE:
    python step3_compare_models.py <augmented_csv> [output_dir]

DEPENDENCIES:
    pip install torch transformers vaderSentiment scipy scikit-learn
=============================================================================
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import time
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset, DataLoader
from transformers import RobertaTokenizer, RobertaModel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class ComparisonConfig:
    """
    REASONING for defaults:
    - test_split=0.20: Standard 80/20 split. 20% gives reliable metrics
      without wasting too much training data.
    - roberta_epochs=5: Fine-tuning on ~1000-2000 samples converges in 3-5
      epochs. More risks overfitting on augmented data.
    - roberta_lr=2e-5: Standard RoBERTa fine-tuning rate from original paper.
    - roberta_batch_size=8: CPU-safe. Use 16-32 on GPU.
    """
    input_csv: str
    output_dir: str = 'results'
    test_split: float = 0.20
    random_seed: int = 42
    roberta_model_name: str = 'roberta-base'
    roberta_epochs: int = 5
    roberta_lr: float = 2e-5
    roberta_batch_size: int = 8
    roberta_max_length: int = 128
    roberta_freeze_base: bool = False
    device: str = 'cuda' if torch.cuda.is_available() else 'cpu'

    def __post_init__(self):
        if not Path(self.input_csv).exists():
            raise FileNotFoundError(f"Input file not found: {self.input_csv}")


# ==============================================================================
# DATASET
# ==============================================================================

class SentimentDataset(Dataset):
    """PyTorch Dataset for sentiment training."""
    def __init__(self, dataframe, tokenizer, max_length):
        self.df = dataframe.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length

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
            'sentiment': torch.tensor(row['proxy_sentiment'], dtype=torch.float32),
            'urgency': torch.tensor(row.get('proxy_urgency', 0.3), dtype=torch.float32),
        }


# ==============================================================================
# ROBERTA MODEL (Architecture matches project's model_architecture.py)
# ==============================================================================

class SentimentRoBERTa(nn.Module):
    """
    RoBERTa multi-task model matching the project architecture:
    - Shared encoder (768-dim)
    - Sentiment head: 768->256->1 (tanh, outputs [-1,1])
    - Urgency head: 768->256->1 (sigmoid, outputs [0,1])
    - Keyword head: 768->256->50 (sigmoid, multi-label)

    REASONING: Multi-task architecture provides regularization through shared
    representations. The sentiment and urgency tasks are correlated (negative
    complaints tend to be urgent), so joint training leverages this signal.
    """
    def __init__(self, model_name='roberta-base', hidden_dim=256, dropout=0.1):
        super().__init__()
        self.roberta = RobertaModel.from_pretrained(model_name)
        hs = self.roberta.config.hidden_size  # 768
        self.dropout = nn.Dropout(dropout)

        self.sentiment_head = nn.Sequential(
            nn.Linear(hs, hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1), nn.Tanh()
        )
        self.urgency_head = nn.Sequential(
            nn.Linear(hs, hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, 1), nn.Sigmoid()
        )
        self.keyword_head = nn.Sequential(
            nn.Linear(hs, hidden_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, 50), nn.Sigmoid()
        )

    def forward(self, input_ids, attention_mask):
        out = self.roberta(input_ids=input_ids, attention_mask=attention_mask)
        cls = self.dropout(out.last_hidden_state[:, 0, :])
        return {
            'sentiment': self.sentiment_head(cls).squeeze(-1),
            'urgency': self.urgency_head(cls).squeeze(-1),
            'keywords': self.keyword_head(cls),
        }


# ==============================================================================
# MODEL 1: ROBERTA (Fine-tuned on our domain data)
# ==============================================================================

class RoBERTaSentimentModel:
    """
    Fine-tuned RoBERTa for sentiment regression.

    REASONING:
    - We fine-tune ALL layers (freeze_base=False) because our complaint
      domain differs significantly from RoBERTa's pre-training data (English
      Wikipedia + BookCorpus). The lower transformer layers need to adapt
      their attention patterns to complaint-specific syntax.
    - We use MSE loss because sentiment is a continuous regression target.
    - Gradient clipping at norm=1.0 prevents catastrophic updates during
      fine-tuning on small datasets.
    - We track validation loss and restore the best checkpoint to prevent
      overfitting — essential when augmented data is 3-4x the original.
    """

    def __init__(self, config: ComparisonConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.name = "RoBERTa (Fine-tuned)"

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict:
        logger.info(f"\n{'='*60}")
        logger.info(f"Training: {self.name}")
        logger.info(f"{'='*60}")

        self.tokenizer = RobertaTokenizer.from_pretrained(self.config.roberta_model_name)
        self.model = SentimentRoBERTa(self.config.roberta_model_name)

        if self.config.roberta_freeze_base:
            for p in self.model.roberta.parameters():
                p.requires_grad = False
            logger.info("  Frozen base encoder")

        self.model = self.model.to(self.config.device)

        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in self.model.parameters())
        logger.info(f"  Params: {trainable:,} trainable / {total:,} total")

        train_ds = SentimentDataset(train_df, self.tokenizer, self.config.roberta_max_length)
        val_ds = SentimentDataset(val_df, self.tokenizer, self.config.roberta_max_length)
        train_loader = DataLoader(train_ds, batch_size=self.config.roberta_batch_size, shuffle=True)
        val_loader = DataLoader(val_ds, batch_size=self.config.roberta_batch_size, shuffle=False)

        optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.config.roberta_lr, weight_decay=0.01)
        criterion = nn.MSELoss()

        history = []
        best_val_loss = float('inf')
        best_state = None

        for epoch in range(self.config.roberta_epochs):
            # Train
            self.model.train()
            train_losses = []
            for batch in train_loader:
                ids = batch['input_ids'].to(self.config.device)
                mask = batch['attention_mask'].to(self.config.device)
                labels = batch['sentiment'].to(self.config.device)

                optimizer.zero_grad()
                out = self.model(ids, mask)
                loss = criterion(out['sentiment'], labels)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                train_losses.append(loss.item())

            # Validate
            self.model.eval()
            val_losses = []
            with torch.no_grad():
                for batch in val_loader:
                    ids = batch['input_ids'].to(self.config.device)
                    mask = batch['attention_mask'].to(self.config.device)
                    labels = batch['sentiment'].to(self.config.device)
                    out = self.model(ids, mask)
                    loss = criterion(out['sentiment'], labels)
                    val_losses.append(loss.item())

            avg_t = np.mean(train_losses)
            avg_v = np.mean(val_losses)
            history.append({'epoch': epoch+1, 'train_loss': avg_t, 'val_loss': avg_v})
            logger.info(f"  Epoch {epoch+1}/{self.config.roberta_epochs} — Train: {avg_t:.6f}, Val: {avg_v:.6f}")

            if avg_v < best_val_loss:
                best_val_loss = avg_v
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}

        if best_state:
            self.model.load_state_dict(best_state)
            logger.info(f"  Restored best model (val_loss={best_val_loss:.6f})")

        return {'history': history, 'best_val_loss': best_val_loss}

    def predict(self, texts: List[str]) -> np.ndarray:
        self.model.eval()
        preds = []
        with torch.no_grad():
            for text in texts:
                enc = self.tokenizer(text, max_length=self.config.roberta_max_length,
                                     padding='max_length', truncation=True, return_tensors='pt')
                ids = enc['input_ids'].to(self.config.device)
                mask = enc['attention_mask'].to(self.config.device)
                out = self.model(ids, mask)
                preds.append(out['sentiment'].item())
        return np.array(preds)

    def save(self, path: str):
        p = Path(path); p.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), p / 'model.pt')
        self.tokenizer.save_pretrained(p)
        logger.info(f"  Saved RoBERTa to {p}")


# ==============================================================================
# MODEL 2: VADER (Rule-based, zero-shot)
# ==============================================================================

class VADERSentimentModel:
    """
    VADER: Rule-based sentiment with lexicon + heuristics.

    REASONING for inclusion:
    - Establishes a LOWER BOUND — if RoBERTa doesn't beat VADER, our
      fine-tuning isn't adding value.
    - VADER handles CAPS emphasis, punctuation, degree modifiers, negation,
      and conjunctions via hand-crafted rules.
    - Outputs compound score in [-1,1] matching our proxy_sentiment scale.
    - No training needed: purely rule-based evaluation.
    - 1000x faster than transformers — quantifies the speed-accuracy tradeoff.
    """

    def __init__(self):
        self.analyzer = None
        self.name = "VADER (Rule-based)"

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        logger.info(f"\n{'='*60}")
        logger.info(f"Model: {self.name} — No training required")
        logger.info(f"{'='*60}")
        self.analyzer = SentimentIntensityAnalyzer()
        # Quick val check
        val_preds = self.predict(val_df['transcript'].astype(str).tolist())
        val_mae = mean_absolute_error(val_df['proxy_sentiment'].values, val_preds)
        logger.info(f"  Val MAE (zero-shot): {val_mae:.4f}")
        return {'val_mae_zeroshot': val_mae}

    def predict(self, texts: List[str]) -> np.ndarray:
        return np.array([self.analyzer.polarity_scores(str(t))['compound'] for t in texts])

    def save(self, path: str):
        logger.info(f"  VADER is rule-based — nothing to save")


# ==============================================================================
# MODEL 3: TWEETNLP (Pre-trained social sentiment, zero-shot transfer)
# ==============================================================================

class TweetNLPSentimentModel:
    """
    Cardiff NLP twitter-roberta-base-sentiment-latest.

    REASONING for inclusion:
    - Tests TRANSFER LEARNING: does a model pre-trained on 124M tweets
      generalize to formal business complaints?
    - If TweetNLP matches our fine-tuned RoBERTa, domain-specific training
      isn't needed. If it falls short, it validates our data investment.
    - Outputs 3-class probabilities [negative, neutral, positive].

    SCORE MAPPING:
        score = P(positive) - P(negative), giving continuous [-1, 1].
        REASONING: This preserves confidence as a continuous signal.
        Confident negative: neg=0.9, pos=0.1 -> score=-0.8
        Confident positive: neg=0.1, pos=0.9 -> score=+0.8
        Neutral: neg=0.2, neu=0.6, pos=0.2 -> score=0.0
    """

    def __init__(self):
        self.pipe = None
        self.name = "TweetNLP (Transfer)"

    def train(self, train_df: pd.DataFrame, val_df: pd.DataFrame) -> Dict:
        from transformers import pipeline
        logger.info(f"\n{'='*60}")
        logger.info(f"Model: {self.name} — Loading pre-trained")
        logger.info(f"{'='*60}")
        self.pipe = pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
            tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest",
            top_k=None, max_length=128, truncation=True
        )
        val_preds = self.predict(val_df['transcript'].astype(str).tolist())
        val_mae = mean_absolute_error(val_df['proxy_sentiment'].values, val_preds)
        logger.info(f"  Val MAE (zero-shot): {val_mae:.4f}")
        return {'val_mae_zeroshot': val_mae}

    def predict(self, texts: List[str]) -> np.ndarray:
        preds = []
        for text in texts:
            try:
                result = self.pipe(str(text)[:512])[0]
                probs = {r['label'].lower(): r['score'] for r in result}
                preds.append(probs.get('positive', 0) - probs.get('negative', 0))
            except Exception:
                preds.append(0.0)
        return np.array(preds)

    def save(self, path: str):
        logger.info(f"  TweetNLP is pre-trained — nothing to save")


# ==============================================================================
# EVALUATION
# ==============================================================================

def evaluate_model(name: str, preds: np.ndarray, labels: np.ndarray, times: List[float]) -> Dict:
    """
    Compute metrics for one model.

    METRICS REASONING:
    - MAE: Most interpretable. "Predictions off by X on average."
    - RMSE: Penalizes large errors. If RMSE >> MAE, model has outlier failures.
    - Pearson: Linear correlation. High = model understands relative sentiment.
    - Spearman: Rank correlation. Most important for our use case — priority
      system needs correct RANKING of complaints, not exact scores.
    - Per-category accuracy: Reveals if model excels on negative but fails
      on positive (common failure mode).
    - Inference time: Production latency constraint.
    """
    r = {'model_name': name}
    r['mae'] = round(mean_absolute_error(labels, preds), 6)
    r['rmse'] = round(np.sqrt(mean_squared_error(labels, preds)), 6)

    if len(set(preds)) > 1 and len(set(labels)) > 1:
        pr, _ = pearsonr(labels, preds)
        sr, _ = spearmanr(labels, preds)
        r['pearson_r'] = round(pr, 6)
        r['spearman_r'] = round(sr, 6)
    else:
        r['pearson_r'] = r['spearman_r'] = 0.0

    # Per-category (neg/neu/pos bins)
    l_bins = np.digitize(labels, bins=[-0.2, 0.2])
    p_bins = np.digitize(preds, bins=[-0.2, 0.2])
    for idx, cat in enumerate(['negative', 'neutral', 'positive']):
        mask = l_bins == idx
        if mask.sum() > 0:
            r[f'accuracy_{cat}'] = round((p_bins[mask] == idx).mean(), 4)
            r[f'count_{cat}'] = int(mask.sum())
        else:
            r[f'accuracy_{cat}'] = None
            r[f'count_{cat}'] = 0

    r['accuracy_overall'] = round((l_bins == p_bins).mean(), 4)
    r['avg_inference_ms'] = round(np.mean(times) * 1000, 3)
    r['median_inference_ms'] = round(np.median(times) * 1000, 3)
    return r


def measure_inference_time(model, texts: List[str]) -> Tuple[np.ndarray, List[float]]:
    """Predict one-by-one, measuring per-sample latency (production-realistic)."""
    preds, times = [], []
    for t in texts:
        s = time.perf_counter()
        p = model.predict([t])
        times.append(time.perf_counter() - s)
        preds.append(p[0])
    return np.array(preds), times


# ==============================================================================
# REPORT GENERATION
# ==============================================================================

def generate_report(results: List[Dict], output_dir: str) -> str:
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)

    with open(out / 'comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    lines = [
        "=" * 70,
        "SENTIMENT MODEL COMPARISON REPORT",
        "InnovaCX — AI-Powered Complaint Management System",
        "=" * 70, "",
        "OVERALL METRICS:",
        "-" * 70,
        f"{'Model':<30} {'MAE':>8} {'RMSE':>8} {'Pearson':>8} {'Spearman':>9} {'ms/pred':>8}",
        "-" * 70,
    ]

    for r in results:
        lines.append(
            f"{r['model_name']:<30} {r['mae']:>8.4f} {r['rmse']:>8.4f} "
            f"{r['pearson_r']:>8.4f} {r['spearman_r']:>9.4f} {r['avg_inference_ms']:>8.2f}"
        )

    lines += ["-" * 70, "", "PER-CATEGORY ACCURACY:", "-" * 70,
              f"{'Model':<30} {'Negative':>10} {'Neutral':>10} {'Positive':>10} {'Overall':>10}",
              "-" * 70]

    for r in results:
        def fmt(v):
            return f"{v:.4f}" if v is not None else "N/A"
        lines.append(
            f"{r['model_name']:<30} {fmt(r.get('accuracy_negative')):>10} "
            f"{fmt(r.get('accuracy_neutral')):>10} {fmt(r.get('accuracy_positive')):>10} "
            f"{fmt(r.get('accuracy_overall')):>10}"
        )

    lines += ["-" * 70, "", "INFERENCE SPEED:", "-" * 70]
    srt = sorted(results, key=lambda x: x['avg_inference_ms'])
    fastest = srt[0]['avg_inference_ms']
    for r in srt:
        sp = r['avg_inference_ms'] / max(fastest, 0.001)
        lines.append(f"  {r['model_name']:<30} {r['avg_inference_ms']:>8.2f} ms  ({sp:.1f}x vs fastest)")

    lines += ["", "WINNER ANALYSIS:", "-" * 70]
    best_mae = min(results, key=lambda x: x['mae'])
    best_sp = max(results, key=lambda x: x['spearman_r'])
    best_fast = min(results, key=lambda x: x['avg_inference_ms'])
    lines.append(f"  Best accuracy (MAE):     {best_mae['model_name']} ({best_mae['mae']:.4f})")
    lines.append(f"  Best ranking (Spearman): {best_sp['model_name']} ({best_sp['spearman_r']:.4f})")
    lines.append(f"  Fastest inference:       {best_fast['model_name']} ({best_fast['avg_inference_ms']:.2f}ms)")
    lines += ["", "=" * 70]

    report = '\n'.join(lines)
    with open(out / 'comparison_report.txt', 'w') as f:
        f.write(report)
    pd.DataFrame(results).to_csv(out / 'comparison_metrics.csv', index=False)
    logger.info(f"  Report: {out / 'comparison_report.txt'}")
    return report


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================

def run_comparison(config: ComparisonConfig) -> List[Dict]:
    """
    Full pipeline:
    1. Load augmented data
    2. Stratified train/test split (ensures proportional sentiment bins)
    3. Train RoBERTa, initialize VADER + TweetNLP
    4. Evaluate all three on SAME test set
    5. Generate comparison report

    REASONING for stratified split:
    Without stratification, random chance might put all positive samples
    in the test set, making every model appear unable to predict positive
    sentiment. Stratification guarantees the test set mirrors the training
    distribution.
    """
    t0 = time.perf_counter()
    logger.info("=" * 70)
    logger.info("STEP 3: THREE-MODEL SENTIMENT COMPARISON")
    logger.info("=" * 70)

    df = pd.read_csv(config.input_csv)
    logger.info(f"Loaded {len(df)} samples")

    for col in ['transcript', 'proxy_sentiment']:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")

    # Stratified split
    df['_bin'] = pd.cut(df['proxy_sentiment'], bins=[-1.01, -0.2, 0.2, 1.01],
                        labels=['neg', 'neu', 'pos'])
    train_df, test_df = train_test_split(df, test_size=config.test_split,
                                          random_state=config.random_seed, stratify=df['_bin'])
    train_rob, val_rob = train_test_split(train_df, test_size=0.15,
                                           random_state=config.random_seed, stratify=train_df['_bin'])

    logger.info(f"  Train: {len(train_rob)}, Val: {len(val_rob)}, Test: {len(test_df)}")

    test_texts = test_df['transcript'].astype(str).tolist()
    test_labels = test_df['proxy_sentiment'].values

    models = [
        RoBERTaSentimentModel(config),
        VADERSentimentModel(),
        TweetNLPSentimentModel(),
    ]

    all_results = []
    for m in models:
        info = m.train(train_rob, val_rob)
        logger.info(f"  Evaluating {m.name} on {len(test_texts)} test samples...")
        preds, times = measure_inference_time(m, test_texts)
        res = evaluate_model(m.name, preds, test_labels, times)
        res['train_info'] = info
        all_results.append(res)

        logger.info(f"  {m.name}: MAE={res['mae']:.4f} Spearman={res['spearman_r']:.4f} "
                    f"Speed={res['avg_inference_ms']:.2f}ms")

        m.save(str(Path(config.output_dir) / m.name.split('(')[0].strip().lower()))

    report = generate_report(all_results, config.output_dir)
    print(f"\n{report}")
    logger.info(f"\nDone in {time.perf_counter()-t0:.1f}s")
    return all_results


# ==============================================================================
# CLI
# ==============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("\nUsage: python step3_compare_models.py <augmented_csv> [output_dir]")
        print("\nExample:")
        print("  python step3_compare_models.py data/processed/augmented_n1500.csv results/")
        print("\nRun AFTER step2_augment.py.")
        print("\nDependencies:")
        print("  pip install torch transformers vaderSentiment scipy scikit-learn")
        sys.exit(1)

    cfg = ComparisonConfig(
        input_csv=sys.argv[1],
        output_dir=sys.argv[2] if len(sys.argv) > 2 else 'results'
    )
    run_comparison(cfg)
