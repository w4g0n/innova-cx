# Prioritization Agent (Runtime)

This folder is runtime-only and is loaded by the orchestrator pipeline.

## Runtime behavior
- Loads pre-trained `XGBoost` model artifacts from `PRIORITY_MODEL_DIR`.
- Predicts priority from these signals:
  - `ticket_type` (`complaint|inquiry`)
  - `is_recurring` (`true|false`)
  - `business_impact_val` (`low|medium|high`)
  - `safety_concern` (`true|false`)
  - `sentiment_score` (`negative|neutral|positive`)
  - `issue_severity_val` (`low|medium|high`)
  - `issue_urgency_val` (`low|medium|high`)
- If no model is found, returns safe fallback (`medium`) until artifacts are deployed.

## Relearning loop
- Manager-approved rescoring is appended as labeled feedback.
- Runtime retrains periodically (`PRIORITY_RETRAIN_EVERY_N_FEEDBACK`, default `5`) using:
  - base synthetic dataset from training phase
  - accumulated manager feedback labels

## Offline training source
Use:
- `ai-models/MultiAgentPipeline/PrioritzationAgentTraining`

That folder is where fuzzy logic + synthetic generation + initial training happen once.
