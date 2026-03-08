# Prioritization Agent (Runtime)

This folder is runtime-only and is loaded by the orchestrator pipeline.

## Runtime behavior
- Computes priority using deterministic rule-based logic from these signals:
  - `ticket_type` (`complaint|inquiry`)
  - `is_recurring` (`true|false`)
  - `business_impact_val` (`low|medium|high`)
  - `safety_concern` (`true|false`)
  - `sentiment_score` (`negative|neutral|positive`)
  - `issue_severity_val` (`low|medium|high`)
  - `issue_urgency_val` (`low|medium|high`)
- Order of execution:
  - apply safety minimum (`high`) when `safety_concern=true`
  - evaluate triple-rule base priority from impact/severity/urgency
  - apply modifiers (`is_recurring`, `ticket_type`, `sentiment_score`)
  - clamp final value to `[low, critical]`

## Relearning loop
- Manager-approved rescoring is appended as labeled feedback.
- Runtime retrains periodically (`PRIORITY_RETRAIN_EVERY_N_FEEDBACK`, default `5`) using:
  - base synthetic dataset from training phase
  - accumulated manager feedback labels

## Offline training source
Use:
- `ai-models/MultiAgentPipeline/PrioritzationAgentTraining`

That folder is where fuzzy logic + synthetic generation + initial training happen once.
