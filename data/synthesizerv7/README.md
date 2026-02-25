# Synthesizer v7

Three-phase synthetic data pipeline:

1. `phase1-generate.py`  
Generates synthetic support tickets (`unlabeled.csv`) with Phi-4.
2. `phase2-classify.py`  
Adds complaint labels with DeBERTa zero-shot NLI (`labeled.csv`).
3. `phase3-evaluate.py`  
Evaluates classifier predictions against a labeled test set.

## Files

- `phase1-generate.py`
- `phase2-classify.py`
- `phase3-evaluate.py`
- `setup_models.py` (downloads local model copies once)
- `requirements.txt`
- `models/` (local model storage)

## Install

From repo root:

```bash
pip install -r data/synthesizerv7/requirements.txt
```

## One-time model download (recommended)

```bash
python data/synthesizerv7/setup_models.py
```

This downloads:

- `microsoft/phi-4` to `data/synthesizerv7/models/generator/phi-4/`
- `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` to `data/synthesizerv7/models/classifier/deberta-v3-base-mnli-fever-anli/`

Download behavior:

- By default, existing local models are reused and skipped.
- Re-download only if you explicitly run:

```bash
python data/synthesizerv7/setup_models.py --force
```

## Run Pipeline

### Phase 1: Generate synthetic tickets

```bash
python data/synthesizerv7/phase1-generate.py \
  --dataset data/synthesizerv7/input.csv \
  --output data/synthesizerv7/output/unlabeled.csv
```

Dry run:

```bash
python data/synthesizerv7/phase1-generate.py \
  --dataset data/synthesizerv7/input.csv \
  --output data/synthesizerv7/output/unlabeled.csv \
  --dry-run
```

### Phase 2: Derive labels

```bash
python data/synthesizerv7/phase2-classify.py \
  --input data/synthesizerv7/output/unlabeled.csv \
  --output data/synthesizerv7/output/labeled.csv
```

Dry run:

```bash
python data/synthesizerv7/phase2-classify.py \
  --input data/synthesizerv7/output/unlabeled.csv \
  --output data/synthesizerv7/output/labeled.csv \
  --dry-run
```

### Phase 3: Evaluate on test set

```bash
python data/synthesizerv7/phase3-evaluate.py \
  --test data/synthesizerv7/test.csv
```

Default output CSV path for predictions:

- `output/predictions.csv`

Override output:

```bash
python data/synthesizerv7/phase3-evaluate.py \
  --test data/synthesizerv7/test.csv \
  --output data/synthesizerv7/output/predictions.csv
```

## Model path behavior in scripts

Each script first checks for local model directories:

- Generator: `data/synthesizerv7/models/generator/phi-4/`
- Classifier: `data/synthesizerv7/models/classifier/deberta-v3-base-mnli-fever-anli/`

If present, local paths are used.  
If not present, scripts fall back to Hugging Face model IDs.

## Required input schemas

### Phase 1 input (`--dataset`)

Must include column:

- `transcript`

### Phase 2 input (`--input`)

Must include columns:

- `ticket_type`
- `subject`
- `text`

### Phase 3 input (`--test`)

Must include columns:

- `ticket_type`
- `text`
- `issue_severity`
- `issue_urgency`
- `safety_concern`
- `business_impact`
