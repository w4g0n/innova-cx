"""Evaluate trained checkpoint on holdout test set."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import accuracy_score, classification_report, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from tqdm import tqdm

LABEL_COLS = ["safety_concern", "business_impact", "issue_severity", "issue_urgency"]
THRESHOLDS = {
    "safety_concern": {"accuracy": 0.80, "f1_macro": 0.78},
    "business_impact": {"accuracy": 0.75, "f1_macro": 0.72},
    "issue_severity": {"accuracy": 0.75, "f1_macro": 0.72},
    "issue_urgency": {"accuracy": 0.75, "f1_macro": 0.72},
}


def normalise_safety(val) -> str:
    return "true" if str(val).strip().lower() in ("true", "1", "yes") else "false"


class EvalDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length=128):
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


class DebertaMultitask(nn.Module):
    def __init__(self, base_model_name: str):
        super().__init__()
        self.backbone = AutoModel.from_pretrained(base_model_name)
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


def main():
    parser = argparse.ArgumentParser(description="Evaluate feature model checkpoint")
    parser.add_argument("--test", default="test/test.csv")
    parser.add_argument("--model-dir", default="models/deberta_multitask")
    parser.add_argument("--output-report", default="output/eval_external_report.json")
    parser.add_argument("--output-preds", default="output/eval_external_predictions.csv")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--text-col", default="text")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    model_cfg = json.loads((model_dir / "model_config.json").read_text())
    class_map = json.loads((model_dir / "label_classes.json").read_text())

    df = pd.read_csv(args.test)
    required = [args.text_col] + LABEL_COLS
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Test CSV missing columns: {missing}")

    df = df.dropna(subset=required).reset_index(drop=True)

    df["safety_concern"] = df["safety_concern"].apply(normalise_safety)
    for col in ("business_impact", "issue_severity", "issue_urgency"):
        df[col] = df[col].astype(str).str.strip().str.lower()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))

    model = DebertaMultitask(model_cfg["base_model"]).to(device)
    model.load_state_dict(torch.load(model_dir / "model.pt", map_location=device))
    model.eval()

    ds = EvalDataset(df[args.text_col].astype(str).tolist(), tokenizer, int(model_cfg.get("max_length", 128)))
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=False)

    preds_idx = {c: [] for c in LABEL_COLS}
    confs = {c: [] for c in LABEL_COLS}

    with torch.no_grad():
        for batch in tqdm(dl, desc="Evaluating", leave=False):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            logits = model(input_ids, attention_mask)

            for c in LABEL_COLS:
                probs = torch.softmax(logits[c], dim=1).cpu().numpy()
                preds_idx[c].extend(np.argmax(probs, axis=1).tolist())
                confs[c].extend(np.max(probs, axis=1).tolist())

    metrics = {}
    pred_df = df.copy()

    for c in LABEL_COLS:
        classes = class_map[c]
        y_pred = [classes[i] for i in preds_idx[c]]
        y_true = df[c].astype(str).tolist()

        if c == "safety_concern":
            y_true = [normalise_safety(v) for v in y_true]
            y_pred = [normalise_safety(v) for v in y_pred]

        all_labels = sorted(list(set(y_true) | set(y_pred)))
        idx_map = {name: i for i, name in enumerate(all_labels)}
        true_idx = [idx_map[x] for x in y_true]
        pred_idx = [idx_map[x] for x in y_pred]

        report = classification_report(
            true_idx,
            pred_idx,
            labels=list(range(len(all_labels))),
            target_names=all_labels,
            output_dict=True,
            zero_division=0,
        )

        acc = float(accuracy_score(true_idx, pred_idx))
        f1m = float(f1_score(true_idx, pred_idx, average="macro", zero_division=0))

        metrics[c] = {
            "accuracy": round(acc, 4),
            "f1_macro": round(f1m, 4),
            "meets_threshold": {
                "accuracy": acc >= THRESHOLDS[c]["accuracy"],
                "f1_macro": f1m >= THRESHOLDS[c]["f1_macro"],
            },
            "threshold": THRESHOLDS[c],
            "per_class": {
                name: {k: round(float(v), 4) for k, v in report[name].items()}
                for name in all_labels
            },
        }

        pred_df[f"pred_{c}"] = y_pred
        pred_df[f"pred_{c}_conf"] = [round(float(x), 4) for x in confs[c]]

    summary_ok = all(
        metrics[c]["meets_threshold"]["accuracy"] and metrics[c]["meets_threshold"]["f1_macro"]
        for c in LABEL_COLS
    )

    out_report = Path(args.output_report)
    out_preds = Path(args.output_preds)
    out_report.parent.mkdir(parents=True, exist_ok=True)
    out_preds.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "rows_evaluated": len(pred_df),
        "meets_all_thresholds": summary_ok,
        "metrics": metrics,
    }
    out_report.write_text(json.dumps(payload, indent=2))
    pred_df.to_csv(out_preds, index=False)

    print(f"Saved report: {out_report}")
    print(f"Saved preds : {out_preds}")
    print(f"Rows eval   : {len(pred_df)}")
    print(f"All thresholds met: {summary_ok}")


if __name__ == "__main__":
    main()
