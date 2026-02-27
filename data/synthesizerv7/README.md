# Synthesizer v7

Pipeline order is fixed to:

1. `phase1-generate.py`
2. `phase4-deduplicate.py`
3. `phase2-classify.py`
4. `phase3-evaluate.py` (prediction-only mode)

Default generator model: `microsoft/Phi-4-mini-instruct`  
Default classifier model: `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli`

## Install

```bash
pip install -r requirements.txt
```

If Phase 1 fails with `SlidingWindowCache` import errors, force-upgrade:

```bash
pip install -U "transformers>=4.55.0" "accelerate>=0.34.0" "tokenizers>=0.21.0"
```

## One-time model download

```bash
python3 setup_models.py
```

Override generator model if needed:

```bash
python3 setup_models.py --generator-model microsoft/Phi-4-mini-instruct --force
```

## Run full pipeline (recommended)

```bash
python3 run_pipeline.py \
  --dataset input.csv \
  --test test.csv \
  --quantization auto
```

Useful knobs:

- `--complaints`, `--inquiries`
- `--max-new-tokens`, `--retries`
- `--similarity-threshold`
- `--summary-output`

Outputs go to `output/` by default:

- `unlabeled.csv`
- `unlabeled_deduplicated.csv`
- `labeled.csv`
- `predictions.csv`
- `deduplication_stats.json`
- `phase2_model_manifest.json`
- `pipeline_summary.json`

## Run phases manually

### Phase 1

```bash
python3 phase1-generate.py \
  --dataset input.csv \
  --output output/unlabeled.csv \
  --quantization auto
```

### Phase 4 (dedup is now second)

```bash
python3 phase4-deduplicate.py \
  --input output/unlabeled.csv \
  --output output/unlabeled_deduplicated.csv \
  --stats-output output/deduplication_stats.json
```

### Phase 2

```bash
python3 phase2-classify.py \
  --input output/unlabeled_deduplicated.csv \
  --output output/labeled.csv \
  --manifest-output output/phase2_model_manifest.json \
  --quantization auto
```

### Phase 3 (prediction-only)

```bash
python3 phase3-evaluate.py \
  --test test.csv \
  --output output/predictions.csv \
  --quantization auto
```

## Phase 3 input schema

Required:

- `issue_text`

Legacy alias also accepted:

- `text` (automatically mapped to `issue_text`)

Phase 3 outputs:

- `issue_text`
- `issue_severity`
- `issue_urgency`
- `safety_concern`
- `business_impact`

## Reusing Phase 2 model for Feature Engineering Agent

Phase 2 writes `output/phase2_model_manifest.json` with model + tokenizer metadata.

To export from SSH machine, bundle model + manifest:

```bash
tar -czf phase2_model_bundle.tar.gz \
  models/classifier/deberta-v3-base-mnli-fever-anli \
  output/phase2_model_manifest.json
```

Then download `phase2_model_bundle.tar.gz` from your SSH session.
