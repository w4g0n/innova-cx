# Synthetic Dataset Pipeline

Generate, label, and train a classifier on synthetic office leasing support tickets.

---

## Overview

A three-stage pipeline that:

1. **Generates** 2000 complaint + 500 inquiry tickets using Phi-4-mini
2. **Labels** complaints using Phi-4-mini few-shot prompting
3. **Trains** a single multi-head DeBERTa classifier on the labeled data

The trained model predicts all four labels in one forward pass:

| Label | Values |
|---|---|
| `issue_severity` | `low` / `medium` / `high` |
| `issue_urgency` | `low` / `medium` / `high` |
| `safety_concern` | `True` / `False` |
| `business_impact` | `low` / `medium` / `high` |

---

## Requirements

```bash
pip install -r requirements.txt
```

**Hardware:** T4 GPU recommended (~3.4GB VRAM peak during labeling, ~0.7GB during training)

**First run:** Phi-4-mini (~8GB) and DeBERTa (~700MB) download automatically and cache locally.

**HuggingFace authentication** is required for Phi-4-mini:
```bash
huggingface-cli login
```
Accept the license at: https://huggingface.co/microsoft/Phi-4-mini-instruct

---

## File Structure

```
pipeline/
├── phase1_generate.py      # Generate unlabeled tickets
├── label.py                # Label complaints with Phi-4-mini
├── train.py                # Fine-tune multi-head DeBERTa
├── phase2_classify.py      # Zero-shot NLI classification (standalone)
├── phase3_evaluate.py      # Evaluate classifier against test set
├── run_pipeline.sh         # Orchestrates label.py + train.py
├── requirements.txt
├── input.csv               # Your unlabeled tickets (required)
└── output/
    ├── unlabeled.csv       # Phase 1 output
    └── labeled.csv         # Phase 2 output
```

---

## Usage

### Full pipeline (label + train)

Upload your `input.csv` to the instance then run:

```bash
# Dry run first — labels 10 rows, skips training
bash run_pipeline.sh --dry-run

# Full run
bash run_pipeline.sh
```

### Run stages individually

**Generate tickets (Phase 1):**
```bash
python3 phase1_generate.py --dataset dataset.csv --output output/unlabeled.csv
```

**Label tickets:**
```bash
python3 label.py --input input.csv --output labeled.csv
```

**Train classifier:**
```bash
python3 train.py --input labeled.csv --output-dir models/
```

**Evaluate against test set:**
```bash
python3 phase3_evaluate.py --test test.csv --output output/predictions.csv
```

---

## Outputs

After a full pipeline run:

```
models/
├── deberta_multitask/
│   ├── model.pt                 ← trained weights
│   ├── tokenizer files
│   ├── label_classes.json       ← class mappings for inference
│   └── model_config.json        ← architecture config
├── labeled.csv                  ← 2000 Phi-4-mini labeled tickets
└── evaluation_report.json       ← accuracy + F1 per label
logs/
├── label.log
└── train.log
```

---

## Configuration

### phase1_generate.py

| Flag | Default | Description |
|---|---|---|
| `--dataset` | required | Reference CSV with `transcript` column |
| `--output` | `output/unlabeled.csv` | Output path |
| `--complaints` | `2000` | Number of complaints to generate |
| `--inquiries` | `500` | Number of inquiries to generate |
| `--dry-run` | off | Generate 10 tickets only |

### label.py

| Flag | Default | Description |
|---|---|---|
| `--input` | `unlabeled.csv` | Unlabeled tickets CSV |
| `--output` | `labeled.csv` | Output path |
| `--dry-run` | off | Label 10 complaints only |

### train.py

| Flag | Default | Description |
|---|---|---|
| `--input` | `labeled.csv` | Labeled CSV from label.py |
| `--output-dir` | `models/` | Where to save model + report |
| `--epochs` | `3` | Training epochs |
| `--batch-size` | `16` | Batch size |
| `--lr` | `2e-5` | Learning rate |

### run_pipeline.sh

| Flag | Description |
|---|---|
| `--dry-run` | Labels 10 rows only, skips training |
| `--epochs N` | Override training epochs |
| `--input PATH` | Override input CSV path |

---

## Time & Cost Estimates (T4)

| Step | Time | Cost |
|---|---|---|
| Model downloads (first run) | ~15 mins | — |
| `label.py` — 1600 complaints | ~93 mins | ~$0.54 |
| `train.py` — 3 epochs | ~7 mins | ~$0.04 |
| **Total** | **~1.9 hrs** | **~$0.67** |

---

## Domain Distribution

Tickets are generated across 15 office-environment domains:

| Domain | Weight |
|---|---|
| Office leasing and tenant support | 40% |
| Office building management and facilities | 18% |
| Commercial property and workspace rental | 14% |
| Office utilities and building services | 12% |
| IT and office technology support | 8% |
| Office parking and access control | 4% |
| Shared workspace and coworking | 4% |

---

## Notes

- Labels (`issue_severity`, `issue_urgency`, `safety_concern`, `business_impact`) only apply to **complaints**. Inquiries have null values for these columns.
- The pipeline checkpoints every 100 rows during labeling — if it crashes, restart and it will resume from the last checkpoint.
- After training, review `evaluation_report.json` for per-class F1 scores. If any label scores below 0.6, consider adding more few-shot examples to `label.py` or increasing epochs.