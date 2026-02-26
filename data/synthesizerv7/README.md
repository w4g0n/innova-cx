# Synthesizer v7

Four-phase synthetic data pipeline:

1. `phase1-generate.py`  
Generates synthetic support tickets (`unlabeled.csv`) with Phi-3.5 Mini.
Default target size: 10,000 rows (7,500 complaints + 2,500 inquiries).
2. `phase2-classify.py`  
Adds complaint labels with DeBERTa zero-shot NLI (`labeled.csv`).
3. `phase3-evaluate.py`  
Evaluates classifier predictions against a labeled test set.
4. `phase4-deduplicate.py`  
Removes exact and near-duplicate rows from generated/classified data.

## Files

- `phase1-generate.py`
- `phase2-classify.py`
- `phase3-evaluate.py`
- `phase4-deduplicate.py`
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

- `microsoft/Phi-3.5-mini-instruct` to `data/synthesizerv7/models/generator/phi-3.5-mini-instruct/`
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

Use 8-bit quantization explicitly (recommended for 16GB GPUs like T4):

```bash
python data/synthesizerv7/phase1-generate.py \
  --dataset data/synthesizerv7/input.csv \
  --output data/synthesizerv7/output/unlabeled.csv \
  --quantization 8bit
```

If GPU memory is tight, lower generation length:

```bash
python data/synthesizerv7/phase1-generate.py \
  --dataset data/synthesizerv7/input.csv \
  --output data/synthesizerv7/output/unlabeled.csv \
  --quantization 8bit \
  --max-new-tokens 128
```

All model phases (1/2/3) now include automatic runtime fallback:
- Try GPU (and 8-bit if enabled)
- If CUDA OOM happens during processing, they switch to CPU fallback and continue

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

Use 8-bit quantization explicitly:

```bash
python data/synthesizerv7/phase2-classify.py \
  --input data/synthesizerv7/output/unlabeled.csv \
  --output data/synthesizerv7/output/labeled.csv \
  --quantization 8bit
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

Use 8-bit quantization explicitly:

```bash
python data/synthesizerv7/phase3-evaluate.py \
  --test data/synthesizerv7/test.csv \
  --output data/synthesizerv7/output/predictions.csv \
  --quantization 8bit
```

### Phase 4: Deduplicate non-exact duplicates

```bash
python data/synthesizerv7/phase4-deduplicate.py \
  --input data/synthesizerv7/output/labeled.csv \
  --output data/synthesizerv7/output/labeled_deduplicated.csv
```

Adjust near-duplicate threshold:

```bash
python data/synthesizerv7/phase4-deduplicate.py \
  --input data/synthesizerv7/output/labeled.csv \
  --output data/synthesizerv7/output/labeled_deduplicated.csv \
  --similarity-threshold 0.92
```

## Model path behavior in scripts

Each script first checks for local model directories:

- Generator: `data/synthesizerv7/models/generator/phi-3.5-mini-instruct/`
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
