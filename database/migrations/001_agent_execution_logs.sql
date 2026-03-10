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
    inference_time_ms INTEGER     NOT NULL DEFAULT 0,
    error_flag        BOOLEAN     NOT NULL DEFAULT FALSE,
    error_message     TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_aol_execution_id ON agent_output_log(execution_id);
CREATE INDEX IF NOT EXISTS idx_aol_ticket_id    ON agent_output_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_aol_agent_name   ON agent_output_log(agent_name);
CREATE INDEX IF NOT EXISTS idx_aol_created_at   ON agent_output_log(created_at);
-- ---------------------------------------------------------
-- Agent-specific output tables
-- Created here (inside init.sql via \ir) so they exist
-- before the extended seed inserts in init.sql run.
-- Column names match exactly what the seed INSERTs expect.
-- 000_analytics_prerequisites.sql uses IF NOT EXISTS so
-- it is safe to re-run and will be a no-op on these tables.
-- ---------------------------------------------------------

-- ticket_resolution_feedback columns: add model_version + confidence_at_time
-- (table itself is created in init.sql before this file is included,
--  but the ALTER below is idempotent)
ALTER TABLE public.ticket_resolution_feedback
    ADD COLUMN IF NOT EXISTS model_version       TEXT        NOT NULL DEFAULT 'resolution-v1.0',
    ADD COLUMN IF NOT EXISTS confidence_at_time  NUMERIC(5,4);

CREATE TABLE IF NOT EXISTS public.sentiment_outputs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id     UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id        UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version    TEXT         NOT NULL,
    sentiment_label  TEXT         NOT NULL,
    sentiment_score  NUMERIC(6,4) NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL,
    emotion_tags     TEXT[]       NOT NULL DEFAULT '{}',
    raw_scores       JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_current       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_so_ticket_id    ON public.sentiment_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_so_is_current   ON public.sentiment_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.priority_outputs (
    id               UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id     UUID            NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id        UUID            NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version    TEXT            NOT NULL,
    model_priority   ticket_priority NOT NULL,
    confidence_score NUMERIC(5,4)    NOT NULL,
    urgency_score    NUMERIC(5,4),
    impact_score     NUMERIC(5,4),
    feature_vector   JSONB           NOT NULL DEFAULT '{}'::jsonb,
    reasoning        TEXT,
    is_current       BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ     NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_po_ticket_id    ON public.priority_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_po_is_current   ON public.priority_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.routing_outputs (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id        UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id           UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version       TEXT         NOT NULL,
    suggested_dept_id   UUID         REFERENCES public.departments(id) ON DELETE SET NULL,
    suggested_dept_name TEXT,
    confidence_score    NUMERIC(5,4) NOT NULL,
    routing_reason      TEXT,
    reasoning           TEXT,
    is_current          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ro_ticket_id    ON public.routing_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ro_is_current   ON public.routing_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.sla_outputs (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id        UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id           UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version       TEXT         NOT NULL,
    sla_tier            TEXT,
    breach_risk_score   NUMERIC(5,4),
    response_deadline   TIMESTAMPTZ,
    resolution_deadline TIMESTAMPTZ,
    predicted_respond_mins INTEGER,
    predicted_resolve_mins INTEGER,
    breach_risk         NUMERIC(5,4),
    confidence_score    NUMERIC(5,4) NOT NULL DEFAULT 0,
    is_current          BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_slao_ticket_id  ON public.sla_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_slao_is_current ON public.sla_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.resolution_outputs (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id         UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id            UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version        TEXT         NOT NULL,
    suggested_resolution TEXT,
    suggested_text       TEXT,
    kb_references        JSONB        NOT NULL DEFAULT '{}'::jsonb,
    confidence_score     NUMERIC(5,4) NOT NULL,
    is_current           BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reso_ticket_id  ON public.resolution_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_reso_is_current ON public.resolution_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.feature_outputs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id     UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id        UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version    TEXT         NOT NULL,
    asset_category   TEXT,
    topic_labels     TEXT[]       NOT NULL DEFAULT '{}',
    confidence_score NUMERIC(5,4) NOT NULL,
    raw_features     JSONB        NOT NULL DEFAULT '{}'::jsonb,
    is_current       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fo_ticket_id    ON public.feature_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_fo_is_current   ON public.feature_outputs (ticket_id, is_current) WHERE is_current = TRUE;

-- enforce_single_current_output trigger (idempotent)
CREATE OR REPLACE FUNCTION enforce_single_current_output()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        EXECUTE format(
            'UPDATE %I SET is_current = FALSE WHERE ticket_id = $1 AND id <> $2',
            TG_TABLE_NAME
        ) USING NEW.ticket_id, NEW.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_single_current_sentiment  ON public.sentiment_outputs;
CREATE TRIGGER trg_single_current_sentiment
AFTER INSERT OR UPDATE OF is_current ON public.sentiment_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();

DROP TRIGGER IF EXISTS trg_single_current_priority   ON public.priority_outputs;
CREATE TRIGGER trg_single_current_priority
AFTER INSERT OR UPDATE OF is_current ON public.priority_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();

DROP TRIGGER IF EXISTS trg_single_current_routing    ON public.routing_outputs;
CREATE TRIGGER trg_single_current_routing
AFTER INSERT OR UPDATE OF is_current ON public.routing_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();

DROP TRIGGER IF EXISTS trg_single_current_sla        ON public.sla_outputs;
CREATE TRIGGER trg_single_current_sla
AFTER INSERT OR UPDATE OF is_current ON public.sla_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();

DROP TRIGGER IF EXISTS trg_single_current_resolution ON public.resolution_outputs;
CREATE TRIGGER trg_single_current_resolution
AFTER INSERT OR UPDATE OF is_current ON public.resolution_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();

DROP TRIGGER IF EXISTS trg_single_current_feature    ON public.feature_outputs;
CREATE TRIGGER trg_single_current_feature
AFTER INSERT OR UPDATE OF is_current ON public.feature_outputs
FOR EACH ROW WHEN (NEW.is_current = TRUE)
EXECUTE FUNCTION enforce_single_current_output();
