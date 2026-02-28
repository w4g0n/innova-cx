"""
train.py — Fine-tune a single multi-head DeBERTa classifier
=============================================================
Trains one DeBERTa model with 4 classification heads:
    - issue_severity  (low / medium / high)
    - issue_urgency   (low / medium / high)
    - safety_concern  (True / False)
    - business_impact (low / medium / high)

One forward pass produces all 4 labels simultaneously.

Outputs:
    models/deberta_multitask/   — saved model + tokenizer
    models/labeled.csv          — labeled training data
    models/evaluation_report.json

Usage:
    python train.py --input labeled.csv --output-dir models/
    python train.py --input labeled.csv --output-dir models/ --epochs 5
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoModel,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)
from tqdm import tqdm

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

BASE_MODEL = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"

LABEL_CONFIGS = {
    "issue_severity":  ["low", "medium", "high"],
    "issue_urgency":   ["low", "medium", "high"],
    "safety_concern":  [False, True],
    "business_impact": ["low", "medium", "high"],
}

LABEL_COLS = list(LABEL_CONFIGS.keys())


# ─────────────────────────────────────────────
# DATASET
# ─────────────────────────────────────────────

class MultiTaskDataset(Dataset):
    def __init__(self, texts, label_dict, tokenizer, max_length=256):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = {col: torch.tensor(vals, dtype=torch.long)
                       for col, vals in label_dict.items()}

    def __len__(self):
        return len(self.labels[LABEL_COLS[0]])

    def __getitem__(self, idx):
        item = {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
        }
        for col, tensor in self.labels.items():
            item[col] = tensor[idx]
        return item


# ─────────────────────────────────────────────
# MULTI-HEAD MODEL
# ─────────────────────────────────────────────

class MultiTaskDeBERTa(nn.Module):
    def __init__(self, base_model_name: str, num_labels_per_task: dict):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base_model_name)
        hidden_size  = self.encoder.config.hidden_size

        # One classification head per label
        self.heads = nn.ModuleDict({
            col: nn.Sequential(
                nn.Dropout(0.1),
                nn.Linear(hidden_size, hidden_size // 2),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(hidden_size // 2, n_classes),
            )
            for col, n_classes in num_labels_per_task.items()
        })

    def forward(self, input_ids, attention_mask, labels=None):
        outputs     = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled      = outputs.last_hidden_state[:, 0, :]  # [CLS] token

        logits_dict = {col: head(pooled) for col, head in self.heads.items()}

        loss = None
        if labels is not None:
            loss_fn = nn.CrossEntropyLoss(label_smoothing=0.1)
            loss = sum(
                loss_fn(logits_dict[col], labels[col])
                for col in self.heads
            )

        return loss, logits_dict


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def normalise_safety(val):
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


def prepare_labels(df: pd.DataFrame, encoders: dict) -> dict:
    label_dict = {}
    for col, le in encoders.items():
        if col == "safety_concern":
            vals = df[col].apply(normalise_safety)
        else:
            vals = df[col].apply(lambda v: str(v).strip().lower())
        label_dict[col] = le.transform(vals).tolist()
    return label_dict


# ─────────────────────────────────────────────
# TRAIN EPOCH
# ─────────────────────────────────────────────

def train_epoch(model, dataloader, optimizer, scheduler, device):
    model.train()
    total_loss = 0
    for batch in tqdm(dataloader, desc="  Training", leave=False):
        input_ids      = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        batch_labels   = {col: batch[col].to(device) for col in LABEL_COLS}

        optimizer.zero_grad()
        loss, _ = model(input_ids, attention_mask, labels=batch_labels)
        loss.backward()

        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        total_loss += loss.item()

    return total_loss / len(dataloader)


# ─────────────────────────────────────────────
# EVALUATE
# ─────────────────────────────────────────────

def evaluate(model, dataloader, device, encoders) -> dict:
    model.eval()
    all_preds  = {col: [] for col in LABEL_COLS}
    all_labels = {col: [] for col in LABEL_COLS}

    with torch.no_grad():
        for batch in tqdm(dataloader, desc="  Evaluating", leave=False):
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            _, logits_dict = model(input_ids, attention_mask)

            for col in LABEL_COLS:
                preds = torch.argmax(logits_dict[col], dim=1).cpu().numpy()
                all_preds[col].extend(preds)
                all_labels[col].extend(batch[col].numpy())

    results = {}
    for col in LABEL_COLS:
        le          = encoders[col]
        class_names = [str(c) for c in le.classes_]
        y_true      = all_labels[col]
        y_pred      = all_preds[col]
        report      = classification_report(
            y_true, y_pred,
            labels=list(range(len(class_names))),
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        )
        results[col] = {
            "accuracy":  round(accuracy_score(y_true, y_pred), 4),
            "f1_macro":  round(f1_score(y_true, y_pred, average="macro", zero_division=0), 4),
            "per_class": {cls: {k: round(v, 4) for k, v in report[cls].items()}
                          for cls in class_names},
        }
    return results


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train multi-head DeBERTa on labeled tickets")
    parser.add_argument("--input",      default="labeled.csv",  help="Labeled CSV from label.py")
    parser.add_argument("--output-dir", default="models/",      help="Directory to save model")
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--epochs",     type=int,   default=3)
    parser.add_argument("--batch-size", type=int,   default=16)
    parser.add_argument("--lr",         type=float, default=2e-5)
    parser.add_argument("--max-length", type=int,   default=256)
    args = parser.parse_args()

    device     = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output_dir)
    model_dir  = output_dir / "deberta_multitask"
    model_dir.mkdir(parents=True, exist_ok=True)

    print(f"Device     : {device}")
    print(f"Base model : {args.base_model}")

    # ── Load data ──
    print(f"\nLoading: {args.input}")
    df = pd.read_csv(args.input)
    df = df[df["ticket_type"] == "complaint"].copy().reset_index(drop=True)

    before = len(df)
    df     = df.dropna(subset=LABEL_COLS)
    print(f"Training rows: {len(df)} (dropped {before - len(df)} null label rows)")

    # ── Label encoders ──
    encoders = {}
    for col, classes in LABEL_CONFIGS.items():
        le = LabelEncoder()
        if col == "safety_concern":
            le.fit([False, True])
        else:
            le.fit([str(c) for c in classes])
        encoders[col] = le

    num_labels_per_task = {col: len(le.classes_) for col, le in encoders.items()}

    # ── Train/val split ──
    stratify_vals = df["issue_severity"].apply(lambda v: str(v).strip().lower())
    can_stratify = True
    if len(df) < 12:
        can_stratify = False
    else:
        class_counts = stratify_vals.value_counts()
        if class_counts.min() < 2:
            can_stratify = False

    if can_stratify:
        train_df, val_df = train_test_split(
            df, test_size=0.15, random_state=42,
            stratify=stratify_vals,
        )
    else:
        print("Skipping stratified split (dataset too small or class has <2 samples).")
        train_df, val_df = train_test_split(
            df, test_size=0.15, random_state=42, stratify=None
        )
    print(f"Train: {len(train_df)}  |  Val: {len(val_df)}")

    print("\nClass distributions (train):")
    for col in LABEL_COLS:
        counts = train_df[col].value_counts()
        print(f"  {col}: {dict(counts)}")

    # ── Tokenizer ──
    print(f"\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    # ── Datasets & loaders ──
    train_dataset = MultiTaskDataset(
        train_df["text"].tolist(),
        prepare_labels(train_df, encoders),
        tokenizer, args.max_length,
    )
    val_dataset = MultiTaskDataset(
        val_df["text"].tolist(),
        prepare_labels(val_df, encoders),
        tokenizer, args.max_length,
    )
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader   = DataLoader(val_dataset,   batch_size=args.batch_size * 2)

    # ── Model ──
    print("Loading model...")
    model = MultiTaskDeBERTa(args.base_model, num_labels_per_task).to(device)

    total_params     = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Parameters : {total_params:,} total  |  {trainable_params:,} trainable")

    # ── Optimizer + scheduler ──
    optimizer   = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_loader) * args.epochs
    scheduler   = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * 0.1),
        num_training_steps=total_steps,
    )

    # ── Training loop ──
    print(f"\nTraining {args.epochs} epochs...\n")
    best_avg_f1  = 0.0
    best_results = None

    for epoch in range(1, args.epochs + 1):
        print(f"Epoch {epoch}/{args.epochs}")
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device)
        results    = evaluate(model, val_loader, device, encoders)
        avg_f1     = float(np.mean([r["f1_macro"] for r in results.values()]))

        print(f"  Loss: {train_loss:.4f}  |  Avg F1: {avg_f1:.4f}")
        for col, r in results.items():
            print(f"    {col:<22}  Acc={r['accuracy']:.3f}  F1={r['f1_macro']:.3f}")

        if avg_f1 > best_avg_f1:
            best_avg_f1  = avg_f1
            best_results = results
            torch.save(model.state_dict(), model_dir / "model.pt")
            print(f"  ✓ Best model saved (avg F1: {best_avg_f1:.4f})")

    # ── Save tokenizer + metadata ──
    tokenizer.save_pretrained(str(model_dir))

    label_classes = {col: [str(c) for c in le.classes_] for col, le in encoders.items()}
    with open(model_dir / "label_classes.json", "w") as f:
        json.dump(label_classes, f, indent=2)

    with open(model_dir / "model_config.json", "w") as f:
        json.dump({
            "base_model":          args.base_model,
            "num_labels_per_task": num_labels_per_task,
            "max_length":          args.max_length,
        }, f, indent=2)

    # ── Evaluation report ──
    report = {
        "base_model":    args.base_model,
        "training_rows": len(train_df),
        "val_rows":      len(val_df),
        "epochs":        args.epochs,
        "best_avg_f1":   round(best_avg_f1, 4),
        "results":       best_results,
    }
    report_path = output_dir / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    # ── Save labeled CSV ──
    labeled_csv_path = output_dir / "labeled.csv"
    pd.read_csv(args.input).to_csv(labeled_csv_path, index=False)

    # ── Summary ──
    print(f"\n{'='*55}")
    print("TRAINING SUMMARY")
    print(f"{'='*55}")
    print(f"  {'Label':<22}  {'Accuracy':>10}  {'F1 Macro':>10}")
    print("  " + "-" * 46)
    for col, r in best_results.items():
        print(f"  {col:<22}  {r['accuracy']:>10.3f}  {r['f1_macro']:>10.3f}")
    print(f"\n  Best avg F1       : {best_avg_f1:.4f}")
    print(f"  Model saved to    : {model_dir}")
    print(f"  Evaluation report : {report_path}")
    print(f"  Labeled CSV       : {labeled_csv_path}")


if __name__ == "__main__":
    main()
