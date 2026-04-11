-- Migration 009: Pipeline Queue Management

-- Adds:
--   1) pipeline_queue_status enum
--   2) pipeline_queue table (persisted queue with retry/hold logic)
--   3) pipeline_held notification_type value


-- Add pipeline_held to the notification_type enum
ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'pipeline_held';

-- Queue status enum
DO $$ BEGIN
  CREATE TYPE pipeline_queue_status AS ENUM (
    'queued',
    'processing',
    'held',
    'completed',
    'failed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Main queue table
CREATE TABLE IF NOT EXISTS pipeline_queue (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id            UUID REFERENCES tickets(id) ON DELETE CASCADE,
    ticket_code          TEXT,

    -- Queue state
    status               pipeline_queue_status NOT NULL DEFAULT 'queued',
    queue_position       INT,                          -- lower = processed first; NULL when not queued
    retry_count          INT NOT NULL DEFAULT 0,

    -- Failure tracking
    failed_stage         TEXT,                         -- agent name that failed
    failed_at_step       INT,                          -- step_order of failed stage
    failure_reason       TEXT,

    -- State snapshots for resume
    checkpoint_state     JSONB NOT NULL DEFAULT '{}',  -- full pipeline state just before failed stage
    operator_corrections JSONB NOT NULL DEFAULT '{}',  -- operator-supplied outputs for the failed stage

    -- Initial ticket data needed to start / restart pipeline
    ticket_input         JSONB NOT NULL DEFAULT '{}',  -- text, has_audio, audio_features, subject, etc.

    -- Execution linkage
    execution_id         UUID,

    -- Timestamps
    entered_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ,
    held_at              TIMESTAMPTZ,
    released_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pq_status
    ON pipeline_queue(status, queue_position NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_pq_ticket_id
    ON pipeline_queue(ticket_id);

CREATE INDEX IF NOT EXISTS idx_pq_ticket_code
    ON pipeline_queue(ticket_code);

CREATE INDEX IF NOT EXISTS idx_pq_entered_at
    ON pipeline_queue(entered_at DESC);
