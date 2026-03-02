-- =========================================================
-- Migration 001: Agent Execution Logging Tables
-- =========================================================
-- Fully idempotent — safe to re-run on any database.
--
-- Updated schema: matches what init.sql seed inserts expect.
-- Added columns: triggered_by, started_at, completed_at,
--                status, input_token_count, output_token_count,
--                infra_metadata
-- ENUMs are created here so they exist before init.sql seeds
-- try to cast values to them.
-- =========================================================

-- ---------------------------------------------------------
-- ENUMs (idempotent)
-- ---------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE agent_name_type AS ENUM (
        'sentiment', 'priority', 'routing', 'sla', 'resolution', 'feature'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE execution_status AS ENUM (
        'running', 'success', 'failed', 'skipped'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE trigger_source AS ENUM (
        'ingest', 'reprocess', 'manual', 'scheduled'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------
-- model_execution_log
-- One row per agent step per pipeline execution.
-- Used by analytics materialized views for Model Health.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_execution_log (
    id                  UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id        UUID             NOT NULL DEFAULT gen_random_uuid(),
    ticket_id           UUID             REFERENCES tickets(id) ON DELETE CASCADE,
    agent_name          agent_name_type,
    model_version       VARCHAR(50),
    triggered_by        trigger_source   NOT NULL DEFAULT 'ingest',
    started_at          TIMESTAMPTZ      NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    status              execution_status NOT NULL DEFAULT 'success',
    input_token_count   INTEGER,
    output_token_count  INTEGER,
    infra_metadata      JSONB            NOT NULL DEFAULT '{}'::jsonb,
    -- legacy columns kept for backward compatibility
    inference_time_ms   INTEGER          NOT NULL DEFAULT 0,
    confidence_score    NUMERIC(5,4),
    error_flag          BOOLEAN          NOT NULL DEFAULT FALSE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mel_execution_id ON model_execution_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_mel_ticket_id    ON model_execution_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_mel_agent_name   ON model_execution_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_mel_created_at   ON model_execution_log(created_at);
CREATE INDEX IF NOT EXISTS idx_mel_status       ON model_execution_log(status);
CREATE INDEX IF NOT EXISTS idx_mel_started_at   ON model_execution_log(started_at DESC);

-- ---------------------------------------------------------
-- agent_output_log
-- Full JSON capture of each agent's input/output state.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS agent_output_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id      UUID        NOT NULL,
    ticket_id         UUID,
    agent_name        VARCHAR(80) NOT NULL,
    step_order        INTEGER     NOT NULL,
    input_state       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    output_state      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    state_diff        JSONB       NOT NULL DEFAULT '{}'::jsonb,
    inference_time_ms INTEGER     NOT NULL DEFAULT 0,
    error_flag        BOOLEAN     NOT NULL DEFAULT FALSE,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aol_execution_id ON agent_output_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_aol_ticket_id    ON agent_output_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_aol_agent_name   ON agent_output_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_aol_created_at   ON agent_output_log(created_at);