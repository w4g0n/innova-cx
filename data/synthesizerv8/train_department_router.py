"""
train_department_router.py — Fine-tune DeBERTa NLI for department routing.
===========================================================================
Takes the V8 labeled dataset and fine-tunes the NLI model to better recognise
which department each complaint belongs to. Keeps the NLI format so the
existing router/step.py requires zero changes.

HOW NLI FINE-TUNING WORKS
--------------------------
Each complaint is paired with every department hypothesis:
  premise:    "My office air conditioning has been broken for two weeks..."
  hypothesis: "This ticket should be handled by Facilities Management."
  label:      entailment   (if department == "Facilities Management")
              contradiction (if department != "Facilities Management")

The model learns to score correct department hypotheses higher, making
zero-shot routing more accurate for our specific domain.

USAGE
-----
    # Full training (recommended)
    python train_department_router.py --epochs 3

    # Quick smoke-test (50 rows, 1 epoch)
    python train_department_router.py --dry-run

    # Resume from checkpoint
    python train_department_router.py --resume --epochs 3

OUTPUT
------
    models/department_router/          <- load this path in router/step.py
        config.json
        tokenizer files
        pytorch_model.bin  (or model.safetensors)

DEPLOYMENT
----------
Copy models/department_router/ to the orchestrator container path:
    /app/models/classifier/deberta-v3-base-mnli-fever-anli/
Update docker-compose.yml volume mount to include this directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

# ── Constants ─────────────────────────────────────────────────────────────────
BASE_MODEL  = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
DATA_PATH   = Path(__file__).parent / "output" / "dept_training.csv"
OUTPUT_DIR  = Path(__file__).parent / "models" / "department_router"
CHECKPOINT  = OUTPUT_DIR / "checkpoint.pt"

DEPARTMENTS = [
    "Facilities Management",
    "Legal & Compliance",
    "Safety & Security",
    "HR",
    "Leasing",
    "Maintenance",
    "IT",
]
HYPOTHESIS_TEMPLATE = "This ticket should be handled by {}."

# NLI label mapping (matches DeBERTa-mnli label order)
# 0 = contradiction, 1 = neutral, 2 = entailment
ENTAILMENT   = 2
CONTRADICTION = 0


# ── Dataset ───────────────────────────────────────────────────────────────────
class DepartmentNLIDataset(Dataset):
    """
    Each complaint generates len(DEPARTMENTS) NLI pairs.
    One entailment (correct dept), rest contradictions.
    Neutral class is not used — binary signal is cleaner for routing.
    """

    def __init__(self, rows: list[dict], tokenizer, max_length: int = 256):
        self.pairs   = []
        self.tokenizer  = tokenizer
        self.max_length = max_length

        for row in rows:
            text = row["text"].strip()
            correct_dept = row["department"].strip()
            for dept in DEPARTMENTS:
                label = ENTAILMENT if dept == correct_dept else CONTRADICTION
                self.pairs.append((text, HYPOTHESIS_TEMPLATE.format(dept), label))

        random.shuffle(self.pairs)

    def __len__(self) -> int:
        return len(self.pairs)

    def __getitem__(self, idx: int) -> dict:
        premise, hypothesis, label = self.pairs[idx]
        enc = self.tokenizer(
            premise,
            hypothesis,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "token_type_ids": enc.get("token_type_ids", torch.zeros(1)).squeeze(0),
            "labels":         torch.tensor(label, dtype=torch.long),
        }


# ── Training ──────────────────────────────────────────────────────────────────
def load_data(path: Path, limit: int | None = None) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if limit:
        rows = rows[:limit]
    return rows


def evaluate(model, loader, device) -> tuple[float, float]:
    model.eval()
    correct = total = 0
    total_loss = 0.0
    loss_fn = torch.nn.CrossEntropyLoss()
    with torch.no_grad():
        for batch in loader:
            ids  = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            lbl  = batch["labels"].to(device)
            out  = model(input_ids=ids, attention_mask=mask)
            loss = loss_fn(out.logits, lbl)
            total_loss += loss.item()
            preds = out.logits.argmax(dim=-1)
            correct += (preds == lbl).sum().item()
            total   += lbl.size(0)
    return total_loss / max(len(loader), 1), correct / max(total, 1)


def train(args) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    # ── Load data ──────────────────────────────────────────────────────────────
    limit = 50 if args.dry_run else None
    rows  = load_data(DATA_PATH, limit=limit)
    print(f"Loaded {len(rows)} rows from {DATA_PATH}")

    random.shuffle(rows)
    split      = int(0.85 * len(rows))
    train_rows = rows[:split]
    val_rows   = rows[split:]
    print(f"Train: {len(train_rows)} | Val: {len(val_rows)}")

    # ── Load model ─────────────────────────────────────────────────────────────
    print(f"Loading {BASE_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model     = AutoModelForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=3, ignore_mismatched_sizes=False
    )

    if args.resume and CHECKPOINT.exists():
        print(f"Resuming from {CHECKPOINT}")
        model.load_state_dict(torch.load(CHECKPOINT, map_location="cpu"))

    model.to(device)

    # ── Datasets / loaders ────────────────────────────────────────────────────
    train_ds = DepartmentNLIDataset(train_rows, tokenizer)
    val_ds   = DepartmentNLIDataset(val_rows,   tokenizer)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True,  num_workers=2)
    val_dl   = DataLoader(val_ds,   batch_size=args.batch_size, shuffle=False, num_workers=2)

    print(f"NLI pairs — train: {len(train_ds)} | val: {len(val_ds)}")

    # ── Optimiser ─────────────────────────────────────────────────────────────
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    total_steps = len(train_dl) * args.epochs
    scheduler   = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=max(1, total_steps // 10),
        num_training_steps=total_steps,
    )
    loss_fn = torch.nn.CrossEntropyLoss()

    best_val_acc = 0.0
    history      = []

    # ── Training loop ─────────────────────────────────────────────────────────
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for step, batch in enumerate(train_dl, 1):
            ids  = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            lbl  = batch["labels"].to(device)

            optimizer.zero_grad()
            out  = model(input_ids=ids, attention_mask=mask)
            loss = loss_fn(out.logits, lbl)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            running_loss += loss.item()
            if step % 50 == 0 or step == len(train_dl):
                print(
                    f"  Epoch {epoch}/{args.epochs} | "
                    f"Step {step}/{len(train_dl)} | "
                    f"Loss {running_loss/step:.4f}",
                    end="\r",
                )

        print()
        val_loss, val_acc = evaluate(model, val_dl, device)
        print(f"  → Val loss: {val_loss:.4f} | Val acc: {val_acc*100:.1f}%")
        history.append({"epoch": epoch, "val_loss": val_loss, "val_acc": val_acc})

        # Save checkpoint every epoch
        torch.save(model.state_dict(), CHECKPOINT)

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            model.save_pretrained(OUTPUT_DIR)
            tokenizer.save_pretrained(OUTPUT_DIR)
            print(f"  ✅ New best ({val_acc*100:.1f}%) — saved to {OUTPUT_DIR}")

    # ── Final report ──────────────────────────────────────────────────────────
    report = {
        "base_model":   BASE_MODEL,
        "train_rows":   len(train_rows),
        "val_rows":     len(val_rows),
        "nli_pairs_train": len(train_ds),
        "epochs":       args.epochs,
        "best_val_acc": best_val_acc,
        "history":      history,
    }
    with open(OUTPUT_DIR / "training_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print("Department router training complete")
    print(f"  Best val accuracy : {best_val_acc*100:.1f}%")
    print(f"  Model saved to    : {OUTPUT_DIR}")
    print()
    print("DEPLOYMENT:")
    print(f"  Copy {OUTPUT_DIR}/ to the orchestrator container at:")
    print("  /app/models/classifier/deberta-v3-base-mnli-fever-anli/")
    print("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fine-tune DeBERTa NLI for department routing")
    parser.add_argument("--epochs",     type=int,   default=3)
    parser.add_argument("--batch-size", type=int,   default=16)
    parser.add_argument("--lr",         type=float, default=2e-5)
    parser.add_argument("--dry-run",    action="store_true",
                        help="Use 50 rows and 1 epoch for a smoke-test")
    parser.add_argument("--resume",     action="store_true",
                        help="Resume from checkpoint.pt if it exists")
    args = parser.parse_args()

    if args.dry_run:
        args.epochs = 1
        print("[DRY RUN] 50 rows, 1 epoch")

    train(args)
