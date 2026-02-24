-- =============================================================================
-- Suggested Resolution + Retraining schema
-- PostgreSQL 14+ | Safe to run multiple times (idempotent)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Ticket-level generated suggestion fields
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_model TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_generated_at TIMESTAMPTZ;

-- Employee decision outcomes for retraining
CREATE TABLE IF NOT EXISTS ticket_resolution_feedback (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id            UUID        NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    employee_user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    decision             TEXT        NOT NULL CHECK (decision IN ('accepted', 'declined_custom')),
    suggested_resolution TEXT,
    employee_resolution  TEXT,
    final_resolution     TEXT        NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_resolution_feedback_ticket
    ON ticket_resolution_feedback (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_resolution_feedback_employee
    ON ticket_resolution_feedback (employee_user_id);
