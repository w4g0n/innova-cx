"""
evaluate_checkpoint.py — Evaluate trained checkpoint on an external test set.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from tqdm import tqdm

LABEL_COLS = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]


def normalise_safety(val):
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


class EvalDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length=256):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )

    def __len__(self):
        return self.encodings["input_ids"].shape[0]

    def __getitem__(self, idx):
        return {
            "input_ids": self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
        }


class MultiTaskDeBERTa(nn.Module):
    def __init__(self, base_model_name: str, num_labels_per_task: dict):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(base_model_name)
        hidden_size = self.encoder.config.hidden_size
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

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        pooled = outputs.last_hidden_state[:, 0, :]
        return {col: head(pooled) for col, head in self.heads.items()}


def main():
    parser = argparse.ArgumentParser(description="Evaluate checkpoint on external test set")
    parser.add_argument("--test", required=True, help="CSV with gold labels")
    parser.add_argument("--model-dir", default="models/deberta_multitask")
    parser.add_argument("--output-report", default="output/eval_external_report.json")
    parser.add_argument("--output-preds", default="output/eval_external_predictions.csv")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--text-col", default="text")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    cfg = json.loads((model_dir / "model_config.json").read_text())
    class_map = json.loads((model_dir / "label_classes.json").read_text())
    base_model = cfg["base_model"]
    max_length = int(cfg.get("max_length", 256))
    num_labels_per_task = {col: len(class_map[col]) for col in LABEL_COLS}

    df = pd.read_csv(args.test)
    text_col = args.text_col
    if text_col not in df.columns:
        for candidate in ("issue_text", "transcript", "message", "description"):
            if candidate in df.columns:
                print(f"[WARN] --text-col '{text_col}' not found. Falling back to '{candidate}'.")
                text_col = candidate
                break

    required = [text_col] + LABEL_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Test CSV missing columns: {missing}")

    df = df.dropna(subset=required).copy().reset_index(drop=True)
    if "ticket_type" in df.columns:
        df = df[df["ticket_type"].astype(str).str.lower().eq("complaint")].copy().reset_index(drop=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = MultiTaskDeBERTa(base_model, num_labels_per_task).to(device)
    model.load_state_dict(torch.load(model_dir / "model.pt", map_location=device))
    model.eval()

    ds = EvalDataset(df[text_col].astype(str).tolist(), tokenizer, max_length=max_length)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=False)

    pred_idx = {c: [] for c in LABEL_COLS}
    pred_conf = {c: [] for c in LABEL_COLS}
    with torch.no_grad():
        cursor = 0
        for batch in tqdm(dl, desc="Evaluating", leave=False):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            logits = model(input_ids, attention_mask)
            bs = input_ids.shape[0]
            for c in LABEL_COLS:
                probs = torch.softmax(logits[c], dim=1).cpu().numpy()
                pred_idx[c].extend(np.argmax(probs, axis=1).tolist())
                pred_conf[c].extend(np.max(probs, axis=1).tolist())
            cursor += bs

    metrics = {}
    pred_df = df.copy()
    for c in LABEL_COLS:
        classes = class_map[c]
        y_pred_labels = [classes[i] for i in pred_idx[c]]
        if c == "safety_concern":
            y_true = df[c].apply(normalise_safety).tolist()
            y_pred = [normalise_safety(v) for v in y_pred_labels]
            class_names = ["False", "True"]
            y_true_idx = [1 if x else 0 for x in y_true]
            y_pred_idx = [1 if x else 0 for x in y_pred]
        else:
            y_true = df[c].astype(str).str.lower().tolist()
            y_pred = [str(v).lower() for v in y_pred_labels]
            class_names = sorted(list(set(y_true) | set(y_pred)))
            name_to_idx = {n: i for i, n in enumerate(class_names)}
            y_true_idx = [name_to_idx[x] for x in y_true]
            y_pred_idx = [name_to_idx[x] for x in y_pred]

        rep = classification_report(
            y_true_idx,
            y_pred_idx,
            labels=list(range(len(class_names))),
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        )
        metrics[c] = {
            "accuracy": round(accuracy_score(y_true_idx, y_pred_idx), 4),
            "f1_macro": round(f1_score(y_true_idx, y_pred_idx, average="macro", zero_division=0), 4),
            "per_class": {k: {m: round(v, 4) for m, v in rep[k].items()} for k in class_names},
        }
        if c == "safety_concern":
            cm = confusion_matrix(y_true_idx, y_pred_idx, labels=[0, 1]).tolist()
            metrics[c]["confusion_matrix"] = {
                "labels": ["False", "True"],
                "matrix": cm,
            }

        pred_df[f"pred_{c}"] = y_pred
        pred_df[f"pred_{c}_conf"] = [round(float(x), 4) for x in pred_conf[c]]

    report = {
        "rows_evaluated": len(pred_df),
        "model_dir": str(model_dir),
        "text_col_used": text_col,
        "metrics": metrics,
    }
    output_report = Path(args.output_report)
    output_preds = Path(args.output_preds)
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_preds.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text(json.dumps(report, indent=2))
    pred_df.to_csv(output_preds, index=False)

    print(f"Saved report: {output_report}")
    print(f"Saved preds : {output_preds}")
    print(f"Rows eval   : {len(pred_df)}")
    print(f"Safety F1   : {metrics['safety_concern']['f1_macro']}")


if __name__ == "__main__":
    main()
