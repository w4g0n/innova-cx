# Chatbot Agent Architecture

## Scope
This document describes the current chatbot implementation across frontend, backend proxy, chatbot service, database, and orchestrator handoff.

## Components
- Frontend chat UI:
  - `frontend/src/pages/customer/CustomerChatbot.jsx`
- Backend proxy/API gateway:
  - `backend/api/main.py` (`POST /api/chatbot/chat`)
- Chatbot service:
  - `backend/services/chatbot/api/chat.py` (`POST /api/chat`)
  - `backend/services/chatbot/core/controller.py` (state machine)
- Chatbot data schema:
  - `database/services/chatbot.sql`

## State Flow (Customer)
1. Frontend initializes chat with `__init__`.
2. Chatbot returns greeting and moves to `await_primary_intent`.
3. Primary split:
   - `follow_up` -> ask for ticket ID -> status lookup or list open tickets.
   - `create_ticket` -> ask `inquiry` vs `complaint`.
4. Inquiry path:
   - Retrieve KB context from CSV (`retriever.py`) and answer with Falcon fallback.
   - Ask user if answer helped.
   - If user says no with clarification, latest clarification is used for retry.
   - After max attempts, escalate to ticket collection.
5. Complaint path:
   - De-escalation response first.
   - Collect ticket fields (`asset_type`, `description`).
6. Ticket creation:
   - Creates ticket in DB.
   - Sends combined user chat transcript to orchestrator endpoint for downstream pipeline.
7. Aggression handling:
   - If aggressive tone detected, chatbot returns action buttons:
     - `create_ticket`
     - `track_ticket`
   - User can still continue chatting.

## Logging Model
- Session table: `sessions`
- User messages: `user_chat_logs`
- Bot responses: `bot_response_logs`
- All linked by `session_id`.

## DB Safety/Access
- Session ownership enforced in chatbot API:
  - `session_id` must belong to `user_id`.
- SQL status lookups use parameterized queries.
- Chatbot service requires `DATABASE_URL` (no sqlite fallback).

## Integration Notes
- Chatbot service runs in Docker `dev` profile.
- Backend still proxies chatbot service to keep frontend surface stable.
- For fresh schema setup:
  - run chatbot schema from `database/services/chatbot.sql`.

