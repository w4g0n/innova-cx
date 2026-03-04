# Is Recurring (Simple)

## What it means
- `is_recurring` tells us if this ticket likely repeats a previous issue from the same user.

## How it is checked
- SQL function: `compute_is_recurring_ticket(user_id, subject, details)`
- It checks recent tickets for the same user:
  - exact subject match first
  - then basic text overlap on details.

## Where it is used
- Backend `predict_is_recurring(...)` calls this SQL function first.
- If SQL function is unavailable, backend falls back to `false`.
- Value is saved in `model_suggestion` as JSON, for example:
  - `{"is_recurring": true}`
- Chatbot ticket creation uses the same SQL function and also stores
  `{"is_recurring": ...}` in `model_suggestion`.

## Relation to feature engineering
- Feature engineering step reads `state["is_recurring"]` if provided.
- If not provided in state, it loads the ticket owner + subject/details and calls
  the same SQL function `compute_is_recurring_ticket(...)`.
- If SQL function/data is unavailable, it falls back to `false`.

## Where implemented
- SQL function: `database/scripts/is_recurring.sql`
- Backend usage: `backend/api/main.py`
- Chatbot usage: `backend/services/chatbot/core/ticket.py`
- Orchestrator feature engineering usage:
  `ai-models/MultiAgentPipeline/Orchestrator/agents/featureengineering/step.py`
