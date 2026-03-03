-- =============================================================================
-- InnovaCX — Analytics Prerequisites Migration
-- File: database/scripts/000_analytics_prerequisites.sql
--
-- RUN ORDER:
--   1. init.sql                           (already applied)
--   2. 000_analytics_prerequisites.sql    ← THIS FILE
--   3. analytics_mvs.sql
--
-- SAFE TO RE-RUN: all statements use IF NOT EXISTS / DO $$ guards.
-- =============================================================================

BEGIN;


-- =============================================================================
-- SECTION 1: ENUM TYPES
-- =============================================================================

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


-- =============================================================================
-- SECTION 2: MODEL EXECUTION LOG — MIGRATE EXISTING TABLE
--
-- Existing schema:
--   id (PK), execution_id (uuid, no constraint), ticket_id, agent_name (varchar),
--   model_version, inference_time_ms, confidence_score, error_flag,
--   error_message, created_at
--
-- The agent output tables will FK to id (the actual PK).
-- We add all missing columns needed by analytics_mvs.sql and seed inserts.
-- =============================================================================

ALTER TABLE public.model_execution_log
    ADD COLUMN IF NOT EXISTS triggered_by       trigger_source   NOT NULL DEFAULT 'ingest',
    ADD COLUMN IF NOT EXISTS started_at         TIMESTAMPTZ      NOT NULL DEFAULT now(),
    ADD COLUMN IF NOT EXISTS completed_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS status             execution_status NOT NULL DEFAULT 'success',
    ADD COLUMN IF NOT EXISTS input_token_count  INTEGER,
    ADD COLUMN IF NOT EXISTS output_token_count INTEGER,
    ADD COLUMN IF NOT EXISTS infra_metadata     JSONB            NOT NULL DEFAULT '{}'::jsonb;

-- Backfill started_at from created_at for existing rows
UPDATE public.model_execution_log
SET started_at = created_at
WHERE started_at <> created_at;

-- Cast agent_name varchar → agent_name_type via shadow column rename
ALTER TABLE public.model_execution_log
    ADD COLUMN IF NOT EXISTS agent_name_typed agent_name_type;

UPDATE public.model_execution_log
SET agent_name_typed = agent_name::agent_name_type
WHERE agent_name IN ('sentiment','priority','routing','sla','resolution','feature')
  AND agent_name_typed IS NULL;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE  table_schema = 'public'
          AND  table_name   = 'model_execution_log'
          AND  column_name  = 'agent_name'
          AND  udt_name     = 'varchar'
    ) THEN
        ALTER TABLE public.model_execution_log
            RENAME COLUMN agent_name TO agent_name_old;
        ALTER TABLE public.model_execution_log
            RENAME COLUMN agent_name_typed TO agent_name;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_mel_status
    ON public.model_execution_log (status);
CREATE INDEX IF NOT EXISTS idx_mel_started_at
    ON public.model_execution_log (started_at DESC);


-- =============================================================================
-- SECTION 3: AGENT OUTPUT TABLES
-- FK references public.model_execution_log(id) — the actual PK.
-- =============================================================================

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
CREATE INDEX IF NOT EXISTS idx_so_ticket_id
    ON public.sentiment_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_so_is_current
    ON public.sentiment_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.priority_outputs (
    id                 UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id       UUID            NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id          UUID            NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version      TEXT            NOT NULL,
    suggested_priority ticket_priority NOT NULL,
    confidence_score   NUMERIC(5,4)    NOT NULL,
    reasoning          TEXT,
    is_current         BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMPTZ     NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_po_ticket_id
    ON public.priority_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_po_is_current
    ON public.priority_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.routing_outputs (
    id                      UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id            UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id               UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version           TEXT         NOT NULL,
    suggested_department_id UUID         REFERENCES public.departments(id) ON DELETE SET NULL,
    confidence_score        NUMERIC(5,4) NOT NULL,
    reasoning               TEXT,
    is_current              BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ro_ticket_id
    ON public.routing_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ro_is_current
    ON public.routing_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.sla_outputs (
    id                     UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id           UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id              UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version          TEXT         NOT NULL,
    predicted_respond_mins INTEGER,
    predicted_resolve_mins INTEGER,
    breach_risk            NUMERIC(5,4),
    confidence_score       NUMERIC(5,4) NOT NULL,
    is_current             BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_slao_ticket_id
    ON public.sla_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_slao_is_current
    ON public.sla_outputs (ticket_id, is_current) WHERE is_current = TRUE;

CREATE TABLE IF NOT EXISTS public.resolution_outputs (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id     UUID         NOT NULL REFERENCES public.model_execution_log(id) ON DELETE CASCADE,
    ticket_id        UUID         NOT NULL REFERENCES public.tickets(id) ON DELETE CASCADE,
    model_version    TEXT         NOT NULL,
    suggested_text   TEXT,
    kb_references    TEXT[]       NOT NULL DEFAULT '{}',
    confidence_score NUMERIC(5,4) NOT NULL,
    is_current       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reso_ticket_id
    ON public.resolution_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_reso_is_current
    ON public.resolution_outputs (ticket_id, is_current) WHERE is_current = TRUE;

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
CREATE INDEX IF NOT EXISTS idx_fo_ticket_id
    ON public.feature_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_fo_is_current
    ON public.feature_outputs (ticket_id, is_current) WHERE is_current = TRUE;


-- =============================================================================
-- SECTION 4: ADDITIVE COLUMNS ON TICKETS
-- =============================================================================

ALTER TABLE public.tickets
    ADD COLUMN IF NOT EXISTS human_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS override_reason  TEXT,
    ADD COLUMN IF NOT EXISTS is_recurring     BOOLEAN NOT NULL DEFAULT FALSE;


-- =============================================================================
-- SECTION 5: ADDITIVE COLUMNS ON SESSIONS
-- =============================================================================

ALTER TABLE public.sessions
    ADD COLUMN IF NOT EXISTS bot_model_version  TEXT,
    ADD COLUMN IF NOT EXISTS escalated_to_human BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS escalated_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS linked_ticket_id   UUID REFERENCES public.tickets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_escalated_flag
    ON public.sessions (escalated_to_human, created_at)
    WHERE escalated_to_human = TRUE;

CREATE INDEX IF NOT EXISTS idx_sessions_linked_ticket
    ON public.sessions (linked_ticket_id)
    WHERE linked_ticket_id IS NOT NULL;


-- =============================================================================
-- SECTION 6: ADDITIVE COLUMNS ON USER_CHAT_LOGS
-- ticket_id already exists — only adding sentiment_score, category, response_time_ms
-- =============================================================================

ALTER TABLE public.user_chat_logs
    ADD COLUMN IF NOT EXISTS sentiment_score  NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS category         TEXT,
    ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;


-- =============================================================================
-- SECTION 7: ADDITIVE COLUMNS ON BOT_RESPONSE_LOGS
-- =============================================================================

ALTER TABLE public.bot_response_logs
    ADD COLUMN IF NOT EXISTS kb_match_score NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS response_type  TEXT,
    ADD COLUMN IF NOT EXISTS ticket_id      UUID REFERENCES public.tickets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_brl_ticket_id
    ON public.bot_response_logs (ticket_id);


-- =============================================================================
-- SECTION 8: ADDITIVE COLUMNS ON EMPLOYEE_REPORTS
-- =============================================================================

ALTER TABLE public.employee_reports
    ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT 'report-gen-v1.0',
    ADD COLUMN IF NOT EXISTS generated_by  TEXT NOT NULL DEFAULT 'system',
    ADD COLUMN IF NOT EXISTS period_start  DATE,
    ADD COLUMN IF NOT EXISTS period_end    DATE;


-- =============================================================================
-- SECTION 9: SINGLE CURRENT OUTPUT TRIGGER
-- =============================================================================

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


COMMIT;