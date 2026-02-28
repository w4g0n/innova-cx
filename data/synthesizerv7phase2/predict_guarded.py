"""
predict_guarded.py — Run multitask model inference with no-retrain guardrails.
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer
from tqdm import tqdm

LABEL_COLS = ["issue_severity", "issue_urgency", "safety_concern", "business_impact"]

SAFETY_TERMS = [
    "fire",
    "smoke",
    "gas leak",
    "carbon monoxide",
    "electrical",
    "electrocution",
    "sparking",
    "short circuit",
    "water leak",
    "flooding",
    "ceiling collapse",
    "collapse",
    "injury",
    "hazard",
    "unsafe",
    "evacuat",
    "alarm",
]


class TextDataset(Dataset):
    def __init__(self, texts, tokenizer, max_length):
        self.enc = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )

    def __len__(self):
        return self.enc["input_ids"].shape[0]

    def __getitem__(self, idx):
        return {
            "input_ids": self.enc["input_ids"][idx],
            "attention_mask": self.enc["attention_mask"][idx],
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


def parse_bool_class(value):
    v = str(value).strip().lower()
    return v in ("true", "1", "yes")


def build_safety_regex():
    escaped = [re.escape(t) for t in SAFETY_TERMS]
    # Prefix matching for terms like "evacuat" captures evacuate/evacuation.
    pattern = r"(" + r"|".join(escaped) + r")"
    return re.compile(pattern, flags=re.IGNORECASE)


def compute_margin(prob_row: np.ndarray) -> float:
    if len(prob_row) < 2:
        return 1.0
    top2 = np.partition(prob_row, -2)[-2:]
    return float(np.max(top2) - np.min(top2))


def main():
    parser = argparse.ArgumentParser(description="Predict with model + guardrails (no retraining)")
    parser.add_argument("--input", required=True, help="Input CSV with at least text column")
    parser.add_argument("--output", required=True, help="Output CSV path for predictions")
    parser.add_argument("--model-dir", default="models/deberta_multitask", help="Path to trained model dir")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--text-col", default="text")
    parser.add_argument("--ticket-type-col", default="ticket_type")
    parser.add_argument("--safety-threshold", type=float, default=0.30,
                        help="If P(safety_concern=True) >= threshold, force True")
    parser.add_argument("--uncertainty-margin", type=float, default=0.15,
                        help="If top2 prob margin for any task < this value, mark needs_review=True")
    args = parser.parse_args()

    model_dir = Path(args.model_dir)
    cfg = json.loads((model_dir / "model_config.json").read_text())
    class_map = json.loads((model_dir / "label_classes.json").read_text())

    base_model = cfg["base_model"]
    max_length = int(cfg.get("max_length", args.max_length))
    num_labels_per_task = {col: len(class_map[col]) for col in LABEL_COLS}

    print(f"Loading input: {args.input}")
    df = pd.read_csv(args.input)
    if args.text_col not in df.columns:
        raise ValueError(f"Missing text column: {args.text_col}")

    if args.ticket_type_col in df.columns:
        complaint_mask = df[args.ticket_type_col].astype(str).str.lower().eq("complaint")
    else:
        complaint_mask = pd.Series([True] * len(df))

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = MultiTaskDeBERTa(base_model, num_labels_per_task).to(device)
    state_dict = torch.load(model_dir / "model.pt", map_location=device)
    model.load_state_dict(state_dict)
    model.eval()

    texts = df.loc[complaint_mask, args.text_col].fillna("").astype(str).tolist()
    dataset = TextDataset(texts, tokenizer, max_length=max_length)
    loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)

    pred_store = {col: [] for col in LABEL_COLS}
    conf_store = {col: [] for col in LABEL_COLS}
    margin_store = {col: [] for col in LABEL_COLS}
    safety_true_probs = []

    with torch.no_grad():
        for batch in tqdm(loader, desc="Predicting", leave=False):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            logits = model(input_ids, attention_mask)

            for col in LABEL_COLS:
                probs = torch.softmax(logits[col], dim=1).cpu().numpy()
                idx = np.argmax(probs, axis=1)
                classes = class_map[col]
                pred_vals = [classes[i] for i in idx]
                pred_store[col].extend(pred_vals)
                conf_store[col].extend(np.max(probs, axis=1).tolist())
                margin_store[col].extend([compute_margin(row) for row in probs])

                if col == "safety_concern":
                    true_idx = next((i for i, x in enumerate(classes) if parse_bool_class(x)), 1)
                    safety_true_probs.extend(probs[:, true_idx].tolist())

    safety_regex = build_safety_regex()
    complaint_indices = df.index[complaint_mask].tolist()

    for out_col in [
        "pred_issue_severity",
        "pred_issue_urgency",
        "pred_safety_concern",
        "pred_business_impact",
        "needs_review",
        "review_reason",
        "safety_true_prob",
    ]:
        df[out_col] = None

    for pos, row_idx in enumerate(complaint_indices):
        pred_sev = str(pred_store["issue_severity"][pos]).lower()
        pred_urg = str(pred_store["issue_urgency"][pos]).lower()
        pred_saf_raw = pred_store["safety_concern"][pos]
        pred_biz = str(pred_store["business_impact"][pos]).lower()
        pred_saf = parse_bool_class(pred_saf_raw)
        saf_prob = float(safety_true_probs[pos])

        txt = str(df.at[row_idx, args.text_col])
        rule_match = safety_regex.search(txt) is not None
        if saf_prob >= args.safety_threshold:
            pred_saf = True
        if rule_match:
            pred_saf = True

        low_margin_cols = [
            col for col in LABEL_COLS
            if float(margin_store[col][pos]) < args.uncertainty_margin
        ]
        needs_review = len(low_margin_cols) > 0
        reason_parts = []
        if low_margin_cols:
            reason_parts.append("low_margin:" + ",".join(low_margin_cols))
        if rule_match:
            reason_parts.append("safety_rule_match")
        if saf_prob >= args.safety_threshold:
            reason_parts.append("safety_threshold_trigger")

        df.at[row_idx, "pred_issue_severity"] = pred_sev
        df.at[row_idx, "pred_issue_urgency"] = pred_urg
        df.at[row_idx, "pred_safety_concern"] = bool(pred_saf)
        df.at[row_idx, "pred_business_impact"] = pred_biz
        df.at[row_idx, "needs_review"] = bool(needs_review)
        df.at[row_idx, "review_reason"] = ";".join(reason_parts)
        df.at[row_idx, "safety_true_prob"] = round(saf_prob, 4)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    reviewed = int(pd.Series(df["needs_review"]).fillna(False).astype(bool).sum())
    safety_true = int(pd.Series(df["pred_safety_concern"]).fillna(False).astype(bool).sum())
    print(f"Saved predictions: {output_path}")
    print(f"Rows marked for review: {reviewed}")
    print(f"Predicted safety_concern=True: {safety_true}")


if __name__ == "__main__":
    main()
