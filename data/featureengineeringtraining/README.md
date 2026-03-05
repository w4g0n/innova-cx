# Feature Engineering Training Pipeline

This folder runs a full synthetic-training cycle by reusing scripts from:

- `data/synthesizerv7phase2/generate_balanced_phi4.py`
- `data/synthesizerv7phase2/train.py`
- `data/synthesizerv7phase2/evaluate_checkpoint.py`

## What it does

1. Generate **balanced + labeled** synthetic complaints (`2500` by default)
2. Train the multitask NLI model (DeBERTa)
3. Evaluate on an external test set you already have

## Run

From repo root:

```bash
cd /Users/mayood/Documents_local/Study/Uni/Y3/innova-cx
source .venv/bin/activate   # if you use a venv
pip install -r data/featureengineeringtraining/requirements.txt
bash data/featureengineeringtraining/run_pipeline.sh \
  --rows 2500 \
  --epochs 3 \
  --test data/synthesizerv7phase2/test/test_dataset_v2.csv
```

## Outputs

- Synthetic CSV: `data/featureengineeringtraining/output/balanced_synth_2500.csv`
- Model: `data/featureengineeringtraining/output/models_2500/deberta_multitask/model.pt`
- Eval report: `data/featureengineeringtraining/output/eval_external_report_2500.json`
- Eval preds: `data/featureengineeringtraining/output/eval_external_predictions_2500.csv`
- Logs: `data/featureengineeringtraining/output/logs/{generate,train,eval}.log`

Output paths are anchored to `data/featureengineeringtraining/`, regardless of your current shell location.

## Quick sanity run

```bash
bash data/featureengineeringtraining/run_pipeline.sh --dry-run
```

This uses `20` rows and `1` epoch.
