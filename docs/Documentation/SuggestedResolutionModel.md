# Suggested Resolution Model (Falcon)

## Goal
Generate a suggested employee resolution after priority and department are first assigned, capture employee acceptance/decline, and continuously improve future suggestions using captured outcomes.

## Components
- Suggestion generation endpoint (chatbot service):
  - `POST /api/suggest-resolution`
  - file: `backend/services/chatbot/api/chat.py`
- Retraining trigger endpoint (chatbot service):
  - `POST /api/retrain-resolution-model`
  - file: `backend/services/chatbot/api/chat.py`
- Backend integration and resolve workflow:
  - `backend/api/main.py`
- Employee resolve UI:
  - `frontend/src/pages/employee/ComplaintDetails.jsx`
- Suggestion schema (separate SQL file):
  - `database/services/suggested.sql`

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
2. Backend generates suggestion immediately and stores on ticket:
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
6. Backend triggers retraining endpoint.
7. Retrainer rebuilds few-shot example file:
   - `backend/services/chatbot/core/data/resolution_examples.json`
8. Next suggestions use latest examples in prompt context.

## Retraining Data Captured
`ticket_resolution_feedback` includes:
- `decision` (`accepted` | `declined_custom`)
- `suggested_resolution`
- `employee_resolution`
- `final_resolution`
- `ticket_id`, `employee_user_id`, timestamps

## Important Clarification
Current retraining is prompt-level (few-shot memory refresh), not model weight fine-tuning.
If full fine-tune (LoRA/SFT) is required, add a separate training pipeline that consumes `ticket_resolution_feedback`.

