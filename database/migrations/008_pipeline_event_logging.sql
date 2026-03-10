-- =========================================================
-- Migration 008: Pipeline + Application Event Logging
-- =========================================================
-- Adds:
--   1) pipeline_executions     (one row per orchestrator run)
--   2) pipeline_stage_events   (one row per stage event: start/output/error)
--   3) application_event_log   (backend/orchestrator operational events)
-- =========================================================

CREATE TABLE IF NOT EXISTS pipeline_executions (
    id             UUID PRIMARY KEY,
    ticket_id      UUID REFERENCES tickets(id) ON DELETE SET NULL,
    ticket_code    TEXT,
    trigger_source TEXT NOT NULL DEFAULT 'ingest',
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at   TIMESTAMPTZ,
    status         TEXT NOT NULL DEFAULT 'running',
    error_message  TEXT
);

CREATE INDEX IF NOT EXISTS idx_pipeline_exec_ticket_id
    ON pipeline_executions(ticket_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_exec_ticket_code
    ON pipeline_executions(ticket_code);
CREATE INDEX IF NOT EXISTS idx_pipeline_exec_started_at
    ON pipeline_executions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_exec_status
    ON pipeline_executions(status);

CREATE TABLE IF NOT EXISTS pipeline_stage_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id      UUID NOT NULL REFERENCES pipeline_executions(id) ON DELETE CASCADE,
    ticket_id         UUID REFERENCES tickets(id) ON DELETE SET NULL,
    ticket_code       TEXT,
    step_order        INTEGER NOT NULL,
    stage_name        TEXT NOT NULL,
    event_type        TEXT NOT NULL CHECK (event_type IN ('start', 'output', 'error')),
    status            TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    inference_time_ms INTEGER,
    confidence_score  NUMERIC(8,4),
    input_state       JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_state      JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pse_execution_id
    ON pipeline_stage_events(execution_id);
CREATE INDEX IF NOT EXISTS idx_pse_ticket_id
    ON pipeline_stage_events(ticket_id);
CREATE INDEX IF NOT EXISTS idx_pse_ticket_code
    ON pipeline_stage_events(ticket_code);
CREATE INDEX IF NOT EXISTS idx_pse_stage
    ON pipeline_stage_events(stage_name, step_order);
CREATE INDEX IF NOT EXISTS idx_pse_created_at
    ON pipeline_stage_events(created_at DESC);

CREATE TABLE IF NOT EXISTS application_event_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service      TEXT NOT NULL CHECK (service IN ('backend', 'orchestrator')),
    event_key    TEXT NOT NULL,
    ticket_id    UUID REFERENCES tickets(id) ON DELETE SET NULL,
    ticket_code  TEXT,
    execution_id UUID,
    level        TEXT NOT NULL DEFAULT 'INFO',
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ael_service_event
    ON application_event_log(service, event_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ael_ticket_id
    ON application_event_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ael_ticket_code
    ON application_event_log(ticket_code);
CREATE INDEX IF NOT EXISTS idx_ael_execution_id
    ON application_event_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_ael_created_at
    ON application_event_log(created_at DESC);
