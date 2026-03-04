# Suggested Resolution Model (Flan-T5-Base)

## Goal
Generate a suggested employee resolution after priority and department are first assigned, capture employee acceptance/decline, and continuously improve future suggestions using captured outcomes.

## Components
- Suggested Resolution agent (backend service, chatbot-decoupled):
  - model: `google/flan-t5-base` (with deterministic fallback when model is unavailable)
  - files: `backend/api/main.py`
- Pipeline trigger step (orchestrator):
  - step: `SuggestedResolutionAgent` (step 9)
  - file: `ai-models/MultiAgentPipeline/Orchestrator/agents/suggestedresolution/step.py`
- Backend integration and resolve workflow:
  - `backend/api/main.py`
- Employee resolve UI:
  - `frontend/src/pages/employee/ComplaintDetails.jsx`
- Suggestion schema (separate SQL file):
  - `database/services/suggested.sql`

## Runtime Toggle
- Current default: mock mode enabled (`SUGGESTED_RESOLUTION_USE_MOCK=true`).
- Later, to use a saved downloaded model:
  - set `SUGGESTED_RESOLUTION_USE_MOCK=false`
  - set `SUGGESTED_RESOLUTION_MODEL_PATH` to the local model directory
  - keep `SUGGESTED_RESOLUTION_MODEL_NAME` as fallback model id.

## Prompt (Current)
System prompt used for suggestion generation:
- "You are a senior support resolution assistant..."
- Constraints:
  - practical/safe/concise
  - no invented access
  - include verification/closure steps
  - under 180 words
  - plain text only

If retraining examples exist, they are injected as few-shot style guidance.

## End-to-End Workflow
1. Ticket receives first priority assignment (`priority_assigned_at`) with department.
2. Orchestrator final step triggers backend suggestion generation and stores on ticket:
   - `suggested_resolution`
   - `suggested_resolution_model`
   - `suggested_resolution_generated_at`
3. Employee opens Resolve modal:
   - UI fetches suggestion via:
     - `GET /api/employee/tickets/{ticket_code}/resolution-suggestion`
4. Employee chooses:
   - `accepted` (use suggestion), or
   - `declined_custom` (provide own final resolution)
5. Resolve submit API:
   - `POST /api/employee/tickets/{ticket_code}/resolve`
   - Saves ticket as resolved and writes `final_resolution`.
   - Captures feedback row in `ticket_resolution_feedback`.
6. Backend rebuilds few-shot examples from feedback:
   - `ticket_resolution_feedback` (database source of truth)
   - `/app/data/suggested_resolution/examples.json` (latest few-shot cache)
7. Next suggestions use latest examples in prompt context.

## Retraining Data Captured
`ticket_resolution_feedback` includes:
- `decision` (`accepted` | `declined_custom`)
- `suggested_resolution`
- `employee_resolution`
- `final_resolution`
- `ticket_id`, `employee_user_id`, timestamps

## Important Clarification
Current relearning is prompt-level (few-shot memory refresh), not weight fine-tuning.
If full fine-tuning (LoRA/SFT) is required, add a dedicated training pipeline consuming `ticket_resolution_feedback`.

## Pipeline-Only Guard
Suggested Resolution is intentionally enabled only in pipeline mode.
If pipeline mode is inactive, suggestion endpoints return HTTP `409`.
