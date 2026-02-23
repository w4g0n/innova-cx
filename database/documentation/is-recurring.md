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
- If SQL function is unavailable, backend falls back to legacy model logic.
- Value is saved in `model_suggestion` as JSON, for example:
  - `{"is_recurring": true}`

## Relation to feature engineering
- Feature engineering step reads `state["is_recurring"]` if provided.
- It does not call SQL directly.

## Where implemented
- SQL function: `database/scripts/is_recurring.sql`
- Backend usage: `backend/api/main.py`
