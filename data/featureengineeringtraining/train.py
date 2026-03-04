"""Train DeBERTa-v3-small multitask model for feature engineering labels."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup
from tqdm import tqdm

BASE_MODEL = "microsoft/deberta-v3-small"
LABEL_COLS = ["safety_concern", "business_impact", "issue_severity", "issue_urgency"]
LABEL_MAPS = {
    "safety_concern": {"false": 0, "true": 1},
    "business_impact": {"low": 0, "medium": 1, "high": 2},
    "issue_severity": {"low": 0, "medium": 1, "high": 2},
    "issue_urgency": {"low": 0, "medium": 1, "high": 2},
}
LOSS_WEIGHTS = {
    "safety_concern": 1.5,
    "business_impact": 1.0,
    "issue_severity": 1.0,
    "issue_urgency": 1.0,
}


def normalise_safety(val) -> str:
    return "true" if str(val).strip().lower() in ("true", "1", "yes") else "false"


class TicketDataset(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, max_length: int):
        texts = df["text"].astype(str).tolist()
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.labels = {}
        for col in LABEL_COLS:
            mapped = df[col].map(LABEL_MAPS[col]).tolist()
            self.labels[col] = torch.tensor(mapped, dtype=torch.long)

    def __len__(self):
        return self.encodings["input_ids"].shape[0]

    def __getitem__(self, idx):
        item = {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
        }
        for col in LABEL_COLS:
            item[col] = self.labels[col][idx]
        return item


class DebertaMultitask(nn.Module):
    def __init__(self, model_name: str = BASE_MODEL):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(model_name)
        hidden = self.backbone.config.hidden_size
        self.head_safety = nn.Linear(hidden, 2)
        self.head_impact = nn.Linear(hidden, 3)
        self.head_severity = nn.Linear(hidden, 3)
        self.head_urgency = nn.Linear(hidden, 3)

    def forward(self, input_ids, attention_mask):
        out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0, :]
        return {
            "safety_concern": self.head_safety(cls),
            "business_impact": self.head_impact(cls),
            "issue_severity": self.head_severity(cls),
            "issue_urgency": self.head_urgency(cls),
        }


def prepare_df(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = ["text"] + LABEL_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")

    df = df[required].dropna().copy()
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""].reset_index(drop=True)

    df["safety_concern"] = df["safety_concern"].apply(normalise_safety)
    for col in ("business_impact", "issue_severity", "issue_urgency"):
        df[col] = df[col].astype(str).str.strip().str.lower()

    for col, mapper in LABEL_MAPS.items():
        bad = ~df[col].isin(mapper.keys())
        if bad.any():
            raise ValueError(f"Invalid labels in {col}: {df.loc[bad, col].unique().tolist()}")

    return df


def compute_metrics(preds: dict, labels: dict) -> dict:
    metrics = {}
    f1s = []
    for col in LABEL_COLS:
        y_true = labels[col]
        y_pred = preds[col]
        acc = accuracy_score(y_true, y_pred)
        f1m = f1_score(y_true, y_pred, average="macro", zero_division=0)
        metrics[col] = {
            "accuracy": round(float(acc), 4),
            "f1_macro": round(float(f1m), 4),
        }
        f1s.append(float(f1m))

    metrics["avg_macro_f1"] = round(float(np.mean(f1s)), 4)
    return metrics


def train_epoch(model, loader, optimizer, scheduler, device):
    model.train()
    ce = nn.CrossEntropyLoss()
    total = 0.0

    for batch in tqdm(loader, desc="Train", leave=False):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = {c: batch[c].to(device) for c in LABEL_COLS}

        logits = model(input_ids, attention_mask)
        loss = 0.0
        for col in LABEL_COLS:
            loss = loss + LOSS_WEIGHTS[col] * ce(logits[col], labels[col])

        optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        total += float(loss.item())

    return total / max(len(loader), 1)


def eval_epoch(model, loader, device):
    model.eval()
    all_preds = {c: [] for c in LABEL_COLS}
    all_labels = {c: [] for c in LABEL_COLS}

    with torch.no_grad():
        for batch in tqdm(loader, desc="Eval", leave=False):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            logits = model(input_ids, attention_mask)

            for col in LABEL_COLS:
                pred = torch.argmax(logits[col], dim=1).cpu().numpy().tolist()
                gold = batch[col].numpy().tolist()
                all_preds[col].extend(pred)
                all_labels[col].extend(gold)

    return compute_metrics(all_preds, all_labels)


def main():
    parser = argparse.ArgumentParser(description="Train multitask DeBERTa feature model")
    parser.add_argument("--train", default="output/train.csv")
    parser.add_argument("--val", default="output/val.csv")
    parser.add_argument("--output-dir", default="models/deberta_multitask")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--warmup-steps", type=int, default=100)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-model", default=BASE_MODEL)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    train_path = Path(args.train)
    val_path = Path(args.val)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    train_df = prepare_df(train_path)
    val_df = prepare_df(val_path)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    train_ds = TicketDataset(train_df, tokenizer, args.max_length)
    val_ds = TicketDataset(val_df, tokenizer, args.max_length)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = DebertaMultitask(args.base_model).to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    total_steps = max(len(train_loader) * args.epochs, 1)
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=min(args.warmup_steps, total_steps // 2),
        num_training_steps=total_steps,
    )

    best_f1 = -1.0
    best_metrics = None
    no_improve = 0
    history = []

    for epoch in range(1, args.epochs + 1):
        train_loss = train_epoch(model, train_loader, optimizer, scheduler, device)
        val_metrics = eval_epoch(model, val_loader, device)
        avg_f1 = val_metrics["avg_macro_f1"]

        history.append(
            {
                "epoch": epoch,
                "train_loss": round(float(train_loss), 4),
                "val": val_metrics,
            }
        )

        print(f"Epoch {epoch}: loss={train_loss:.4f} val_avg_f1={avg_f1:.4f}")

        if avg_f1 > best_f1:
            best_f1 = avg_f1
            best_metrics = val_metrics
            no_improve = 0
            torch.save(model.state_dict(), out_dir / "model.pt")
        else:
            no_improve += 1
            if no_improve >= args.patience:
                print(f"Early stopping triggered at epoch {epoch}")
                break

    tokenizer.save_pretrained(out_dir)

    label_classes = {
        "safety_concern": ["false", "true"],
        "business_impact": ["low", "medium", "high"],
        "issue_severity": ["low", "medium", "high"],
        "issue_urgency": ["low", "medium", "high"],
    }

    (out_dir / "label_classes.json").write_text(json.dumps(label_classes, indent=2))
    (out_dir / "model_config.json").write_text(
        json.dumps(
            {
                "base_model": args.base_model,
                "max_length": args.max_length,
                "loss_weights": LOSS_WEIGHTS,
            },
            indent=2,
        )
    )

    report = {
        "best_val_metrics": best_metrics,
        "history": history,
        "rows": {
            "train": len(train_df),
            "val": len(val_df),
        },
    }
    report_path = Path("output/evaluation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2))

    print(f"Saved model: {out_dir / 'model.pt'}")
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
