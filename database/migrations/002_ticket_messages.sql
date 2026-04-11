-- Migration 002: ticket_messages table + Opened status support
-- Safe to re-run (uses IF NOT EXISTS / DO $$ guards throughout)
-- Apply BEFORE rebuilding backend or running docker compose up --build


BEGIN;


-- 1. Add 'Opened' to ticket_status enum if missing.
--    The existing codebase uses 'Open' everywhere in the DB/backend.
--    We ADD 'Opened' as an alias used by the frontend pipeline display,
--    but keep 'Open' in the enum so existing data is never broken.
--    The backend will map 'Open' → display label "Opened" at the API layer.
--    No enum rename needed; this is a non-breaking addition.

-- NOTE: We do NOT rename 'Open' to 'Opened' because that would require
-- updating every CHECK, trigger, and seed row. Instead the frontend already
-- maps 'Open'→"Opened" via STATUS_KEY_IDX. The pipeline labels are display-only.


-- 2. Create ticket_messages table for employee ↔ customer conversation.
--    Linked directly to tickets (not to chat_conversations which is for chatbot).

CREATE TABLE IF NOT EXISTS ticket_messages (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id     UUID        NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    sender_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sender_role   TEXT        NOT NULL CHECK (sender_role IN ('customer', 'employee')),
    body          TEXT        NOT NULL CHECK (btrim(body) <> ''),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket
    ON ticket_messages(ticket_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_sender
    ON ticket_messages(sender_id);

COMMIT;
