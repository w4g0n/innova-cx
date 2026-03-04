# Feature Engineering Training (V8)

This folder implements the V8 training flow for the Feature Engineering Agent with the same run style as `data/synthesizerv7phase2`:
- pinned `requirements.txt`
- `run_pipeline.sh` orchestration
- predictable `Input/`, `output/`, `test/`, `logs/`, `models/` storage

## Model
- Backbone: `microsoft/deberta-v3-small`
- Heads: `safety_concern` (2 classes), `business_impact` (3), `issue_severity` (3), `issue_urgency` (3)
- Loss weights: safety=1.5, others=1.0

## Install

```bash
cd data/featureengineeringtraining
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

If your cloud environment can already pull Phi-4 without auth (same as your phase-2 setup), you can skip login.
If pulls fail due to access/rate limits, then authenticate:

```bash
huggingface-cli login
```

Cloud bootstrap shortcut:

```bash
cd data/featureengineeringtraining
bash bootstrap_cloud.sh
```

## Run

### Dry run (safe first test)

```bash
bash run_pipeline.sh --dry-run
```

### End-to-end smoke test (no torch/transformers/HF required)

```bash
bash run_pipeline.sh --smoke-test --rows 216
```

This executes all pipeline stages (generate, split, train, eval) with mock implementations and writes the same artifact paths.

### Full run

```bash
bash run_pipeline.sh --rows 2500 --epochs 5
```

### Re-train only (skip generation + splitting)

```bash
bash run_pipeline.sh --skip-generate --skip-split --epochs 5
```

Useful flags:
- `--base-model <hf-model-id>` override training backbone
- `--skip-preflight` bypass environment checks (not recommended for cloud)
- `--skip-generate`, `--skip-split`, `--skip-train`, `--skip-eval` for stage-by-stage runs

## Main scripts
- `generate_balanced_phi4.py`: combination-first synthetic generation over 54 label combinations
- `preprocess_split.py`: 80/10/10 split with combined-label stratification
- `train.py`: multitask DeBERTa-v3-small training with early stopping
- `evaluate_checkpoint.py`: holdout test evaluation + threshold checks
- `cloud_preflight.py`: validates Python version, dependencies, directories, disk, and HF auth
- `bootstrap_cloud.sh`: one-command cloud setup (venv + deps + preflight)

## Output layout
- `Input/complaints_2500.csv`
- `output/balance_report.json`
- `output/train.csv`
- `output/val.csv`
- `test/test.csv`
- `models/deberta_multitask/model.pt`
- `output/eval_external_report.json`
- `output/eval_external_predictions.csv`
- `logs/*.log`

## Threshold checks
Evaluation enforces these minimums:
- `safety_concern`: accuracy >= 0.80, macro-F1 >= 0.78
- `business_impact`: accuracy >= 0.75, macro-F1 >= 0.72
- `issue_severity`: accuracy >= 0.75, macro-F1 >= 0.72
- `issue_urgency`: accuracy >= 0.75, macro-F1 >= 0.72

## Cloud / Docker

```bash
cd data/featureengineeringtraining
docker build -t featureengineeringtraining:latest .
docker run --rm -it \\
  -v \"$PWD/Input:/app/Input\" \\
  -v \"$PWD/output:/app/output\" \\
  -v \"$PWD/test:/app/test\" \\
  -v \"$PWD/logs:/app/logs\" \\
  -v \"$PWD/models:/app/models\" \\
  featureengineeringtraining:latest \\
  bash run_pipeline.sh --skip-generate
```

For generation (`generate_balanced_phi4.py`), HuggingFace auth is optional and only needed if your runtime cannot pull the model anonymously.
