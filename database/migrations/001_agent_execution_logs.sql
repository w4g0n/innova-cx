-- =========================================================
-- Migration 001: Agent Execution Logging Tables
-- =========================================================
-- Fully idempotent — safe to re-run on any database.
--
-- Creates two tables:
--   model_execution_log  — one row per agent per pipeline run (metrics)
--   agent_output_log     — full JSON input/output per agent (explainability)
-- =========================================================

-- ---------------------------------------------------------
-- model_execution_log
-- One row per agent step per pipeline execution.
-- Used by analytics materialized views for Model Health.
-- ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS model_execution_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id      UUID        NOT NULL,
    ticket_id         UUID,
    agent_name        VARCHAR(80) NOT NULL,
    model_version     VARCHAR(50),
    inference_time_ms INTEGER     NOT NULL DEFAULT 0,
    confidence_score  NUMERIC(5,4),
    error_flag        BOOLEAN     NOT NULL DEFAULT FALSE,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mel_execution_id ON model_execution_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_mel_ticket_id    ON model_execution_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_mel_agent_name   ON model_execution_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_mel_created_at   ON model_execution_log(created_at);

-- ---------------------------------------------------------
-- agent_output_log
-- Full JSON capture of each agent's input state, output
-- state, and computed diff for explainability & analysis.
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
