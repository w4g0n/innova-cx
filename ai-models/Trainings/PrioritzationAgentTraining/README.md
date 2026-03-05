# PrioritzationAgentTraining

This folder is for one-time offline bootstrap training.

## What it does
- Generates synthetic labels from fuzzy logic.
- Trains XGBoost using the full signal set.
- Exports a saved model state to reuse in runtime.

## Signals
- `ticket_type` (`complaint|inquiry`)
- `is_recurring` (`true|false`)
- `business_impact_val` (`low|medium|high`)
- `safety_concern` (`true|false`)
- `sentiment_score` (`negative|neutral|positive`)
- `issue_severity_val` (`low|medium|high`)
- `issue_urgency_val` (`low|medium|high`)

## Run once
```bash
python3 ai-models/MultiAgentPipeline/PrioritzationAgentTraining/train_once.py \
  --output-dir ai-models/MultiAgentPipeline/PrioritzationAgentTraining/output \
  --epochs 600
```

This creates:
- `synthetic_training_data.csv`
- `priority_xgb_model.json`
- `priority_xgb_metadata.json`
- `train_set_eval.json`

## Post-train test
Training automatically runs a test on the generated dataset itself and reports:
- `accuracy`
- `correct`
- `total`

This is saved in `train_set_eval.json` and embedded in `priority_xgb_metadata.json`.

## Deploy model state to runtime
Copy/export those artifacts into runtime `PRIORITY_MODEL_DIR`
(default: `/app/models/prioritization` in orchestrator container).

Runtime then predicts from model only and uses manager approvals for relearning.
