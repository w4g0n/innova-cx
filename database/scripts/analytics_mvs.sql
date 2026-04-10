-- =============================================================================
-- InnovaCX  –  Analytics Materialized Views
-- File: database/scripts/analytics_mvs.sql
-- =============================================================================
-- SAFE TO RE-RUN: every CREATE uses IF NOT EXISTS / OR REPLACE.
--
-- FIRST-RUN (fresh DB):
--   Executed automatically by zzz_analytics_mvs.sh after init.sql.
--
-- MANUAL INSTALL (existing volume):
--   docker exec -i innovacx-db psql -U $POSTGRES_USER -d $POSTGRES_DB \
--     < database/scripts/analytics_mvs.sql
--
-- MV LIST AND DEPENDENCY ORDER:
--   1. mv_ticket_base          → base tables (tickets, departments, user_profiles)
--   2. mv_daily_volume         → mv_ticket_base
--   3. mv_employee_daily       → mv_ticket_base
--   4. mv_acceptance_daily     → suggested_resolution_usage + tickets (base)
--   5. mv_operator_qc_daily    → tickets + approval_requests (base)
--   6. mv_chatbot_daily        → sessions + user_chat_logs (base)
--   7. mv_sentiment_daily      → sentiment_outputs + tickets + departments (base)
--   8. mv_feature_daily        → feature_outputs + tickets + departments (base)
--
-- MVs 4-8 read base tables directly (not via mv_ticket_base) because they
-- join tables that mv_ticket_base does not include.
-- The refresh function handles all 8 in the correct order.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- CLEANUP: drop any incorrectly-schemed views created by a previous migration
-- attempt that placed mv_chatbot_daily in the analytics schema instead of public.
-- These DROPs are safe (IF EXISTS = no error if they were never created).
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    -- Drop the wrongly-schemed chatbot MV if it exists
    IF EXISTS (
        SELECT 1 FROM pg_matviews
        WHERE schemaname = 'analytics' AND matviewname = 'mv_chatbot_daily'
    ) THEN
        DROP MATERIALIZED VIEW analytics.mv_chatbot_daily;
        RAISE NOTICE 'Dropped analytics.mv_chatbot_daily (wrong schema)';
    END IF;

    -- Drop any other analytics-schema MVs from the same bad migration
    IF EXISTS (
        SELECT 1 FROM pg_matviews WHERE schemaname = 'analytics'
          AND matviewname = 'mv_ticket_current_state'
    ) THEN
        DROP MATERIALIZED VIEW IF EXISTS analytics.mv_ticket_current_state CASCADE;
    END IF;

    -- Drop the bad analytics.refresh_all_materialized_views function
    IF EXISTS (
        SELECT 1 FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'analytics'
          AND p.proname = 'refresh_all_materialized_views'
    ) THEN
        DROP FUNCTION IF EXISTS analytics.refresh_all_materialized_views();
        RAISE NOTICE 'Dropped analytics.refresh_all_materialized_views (superseded by public.refresh_analytics_mvs)';
    END IF;
END $$;


-- =============================================================================
-- PREREQUISITE COLUMNS — safe to re-run (all IF NOT EXISTS)
-- Ensures this file can be applied to existing volumes that never ran
-- 000_analytics_prerequisites.sql, without requiring that file first.
-- =============================================================================

-- tickets: analytics columns (added by 000_analytics_prerequisites.sql)
ALTER TABLE public.tickets
    ADD COLUMN IF NOT EXISTS human_overridden BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS override_reason  TEXT,
    ADD COLUMN IF NOT EXISTS is_recurring     BOOLEAN     NOT NULL DEFAULT FALSE;

-- sessions: chatbot tracking columns (added by 000_analytics_prerequisites.sql)
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

-- user_chat_logs: sentiment columns (added by 000_analytics_prerequisites.sql)
ALTER TABLE public.user_chat_logs
    ADD COLUMN IF NOT EXISTS sentiment_score  NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS category         TEXT,
    ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;

-- bot_response_logs: extra columns (added by 000_analytics_prerequisites.sql)
ALTER TABLE public.bot_response_logs
    ADD COLUMN IF NOT EXISTS kb_match_score NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS response_type  TEXT,
    ADD COLUMN IF NOT EXISTS ticket_id      UUID REFERENCES public.tickets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_brl_ticket_id
    ON public.bot_response_logs (ticket_id);

-- employee_reports: extra columns (added by 000_analytics_prerequisites.sql)
ALTER TABLE public.employee_reports
    ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT 'report-gen-v1.0',
    ADD COLUMN IF NOT EXISTS generated_by  TEXT NOT NULL DEFAULT 'system',
    ADD COLUMN IF NOT EXISTS period_start  DATE,
    ADD COLUMN IF NOT EXISTS period_end    DATE;

-- ENUMs for agent output tables (idempotent)
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

-- model_execution_log (needed as FK parent for sentiment_outputs/feature_outputs)
CREATE TABLE IF NOT EXISTS public.model_execution_log (
    id                  UUID             PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id        UUID             NOT NULL DEFAULT gen_random_uuid(),
    ticket_id           UUID             REFERENCES public.tickets(id) ON DELETE CASCADE,
    agent_name          agent_name_type,
    model_version       VARCHAR(50),
    triggered_by        trigger_source   NOT NULL DEFAULT 'ingest',
    started_at          TIMESTAMPTZ      NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    status              execution_status NOT NULL DEFAULT 'success',
    input_token_count   INTEGER,
    output_token_count  INTEGER,
    infra_metadata      JSONB            NOT NULL DEFAULT '{}'::jsonb,
    inference_time_ms   INTEGER          NOT NULL DEFAULT 0,
    confidence_score    NUMERIC(5,4),
    error_flag          BOOLEAN          NOT NULL DEFAULT FALSE,
    error_message       TEXT,
    created_at          TIMESTAMPTZ      NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mel_ticket_id_mv  ON public.model_execution_log (ticket_id);
CREATE INDEX IF NOT EXISTS idx_mel_status_mv     ON public.model_execution_log (status);
CREATE INDEX IF NOT EXISTS idx_mel_started_at_mv ON public.model_execution_log (started_at DESC);

-- sentiment_outputs (queried by mv_sentiment_daily)
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
CREATE INDEX IF NOT EXISTS idx_so_ticket_id_mv  ON public.sentiment_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_so_is_current_mv ON public.sentiment_outputs (ticket_id, is_current) WHERE is_current = TRUE;

-- feature_outputs (queried by mv_feature_daily)
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
CREATE INDEX IF NOT EXISTS idx_fo_ticket_id_mv  ON public.feature_outputs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_fo_is_current_mv ON public.feature_outputs (ticket_id, is_current) WHERE is_current = TRUE;



-- =============================================================================
-- EXTRA INDEXES ON BASE TABLES (safe to re-run — all IF NOT EXISTS)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_tickets_type
    ON tickets (ticket_type);
CREATE INDEX IF NOT EXISTS idx_tickets_dept_priority
    ON tickets (department_id, priority);
CREATE INDEX IF NOT EXISTS idx_tickets_resolved_at
    ON tickets (resolved_at);
CREATE INDEX IF NOT EXISTS idx_tickets_respond_breached
    ON tickets (respond_breached);
CREATE INDEX IF NOT EXISTS idx_tickets_resolve_breached
    ON tickets (resolve_breached);
CREATE INDEX IF NOT EXISTS idx_tickets_model_priority
    ON tickets (model_priority)
    WHERE model_priority IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_sru_employee_decision
    ON suggested_resolution_usage (employee_user_id, decision);
CREATE INDEX IF NOT EXISTS idx_sru_ticket_created
    ON suggested_resolution_usage (ticket_id, created_at);
CREATE INDEX IF NOT EXISTS idx_approval_requests_type_submitted
    ON approval_requests (request_type, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_escalated
    ON sessions (escalated_to_human, created_at)
    WHERE escalated_to_human = TRUE;
CREATE INDEX IF NOT EXISTS idx_so_created_at
    ON sentiment_outputs (created_at DESC)
    WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_fo_created_at
    ON feature_outputs (created_at DESC)
    WHERE is_current = TRUE;


-- =============================================================================
-- MV 1: mv_ticket_base
-- Central denormalised ticket snapshot. All manager analytics derive from here.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ticket_base AS
SELECT
    t.id                                        AS ticket_id,
    t.ticket_code,
    t.ticket_type::TEXT                         AS ticket_type,
    t.priority::TEXT                            AS priority,
    t.model_priority::TEXT                      AS model_priority,
    t.status::TEXT                              AS status,
    t.department_id,
    COALESCE(d.name, 'Unassigned')              AS department_name,
    t.assigned_to_user_id                       AS employee_id,
    up_emp.full_name                            AS employee_name,
    up_emp.employee_code,
    up_emp.job_title                            AS employee_role,
    t.created_by_user_id,
    t.created_at,
    t.first_response_at,
    t.resolved_at,
    t.respond_due_at,
    t.resolve_due_at,
    t.priority_assigned_at,
    t.assigned_at,
    t.human_overridden,
    t.override_reason,
    t.is_recurring,
    t.sentiment_score,
    t.sentiment_label,
    t.model_confidence,
    date_trunc('day',   t.created_at)::date     AS created_day,
    date_trunc('week',  t.created_at)::date     AS created_week,
    date_trunc('month', t.created_at)::date     AS created_month,
    t.respond_breached,
    t.resolve_breached,
    (t.respond_breached OR t.resolve_breached)  AS any_breached,
    (t.status = 'Escalated')                    AS is_escalated,
    (t.status = 'Resolved')                     AS is_resolved,
    CASE
        WHEN t.first_response_at IS NOT NULL THEN
            ROUND(EXTRACT(EPOCH FROM (
                t.first_response_at
                - COALESCE(t.priority_assigned_at, t.assigned_at, t.created_at)
            )) / 60.0, 1)
    END                                         AS response_time_mins,
    CASE
        WHEN t.resolved_at IS NOT NULL THEN
            ROUND(EXTRACT(EPOCH FROM (
                t.resolved_at
                - COALESCE(t.priority_assigned_at, t.created_at)
            )) / 60.0, 1)
    END                                         AS resolve_time_mins,
    CASE t.priority
        WHEN 'Critical' THEN 30
        WHEN 'High'     THEN 60
        WHEN 'Medium'   THEN 180
        ELSE                 360
    END                                         AS sla_respond_target_mins,
    CASE t.priority
        WHEN 'Critical' THEN 360
        WHEN 'High'     THEN 1080
        WHEN 'Medium'   THEN 2880
        ELSE                 4320
    END                                         AS sla_resolve_target_mins,
    (   t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
    )                                           AS was_rescored,
    (   t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
        AND (
            (t.model_priority::TEXT = 'Low'    AND t.priority::TEXT IN ('Medium','High','Critical'))
         OR (t.model_priority::TEXT = 'Medium' AND t.priority::TEXT IN ('High','Critical'))
         OR (t.model_priority::TEXT = 'High'   AND t.priority::TEXT = 'Critical')
        )
    )                                           AS was_upscored,
    (   t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
        AND (
            (t.model_priority::TEXT = 'Critical' AND t.priority::TEXT IN ('Low','Medium','High'))
         OR (t.model_priority::TEXT = 'High'     AND t.priority::TEXT IN ('Low','Medium'))
         OR (t.model_priority::TEXT = 'Medium'   AND t.priority::TEXT = 'Low')
        )
    )                                           AS was_downscored
FROM tickets t
LEFT JOIN departments   d      ON d.id           = t.department_id
LEFT JOIN user_profiles up_emp ON up_emp.user_id = t.assigned_to_user_id
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_ticket_base_uid         ON mv_ticket_base (ticket_id);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_day_dept    ON mv_ticket_base (created_day, department_name);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_month_dept  ON mv_ticket_base (created_month, department_name);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_priority    ON mv_ticket_base (priority);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_employee    ON mv_ticket_base (employee_id);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_type        ON mv_ticket_base (ticket_type);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_created_at  ON mv_ticket_base (created_at);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_status      ON mv_ticket_base (status);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_code        ON mv_ticket_base (ticket_code);
CREATE INDEX        IF NOT EXISTS mv_ticket_base_emp_created
    ON mv_ticket_base (employee_id, created_at)
    WHERE employee_id IS NOT NULL;


-- =============================================================================
-- MV 2: mv_daily_volume
-- Daily aggregate by dept / type / priority. Powers manager trend charts.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_volume AS
SELECT
    created_day,
    created_month,
    department_name,
    ticket_type,
    priority,
    COUNT(*)                                                AS total,
    COUNT(*) FILTER (WHERE any_breached)                    AS breached,
    COUNT(*) FILTER (WHERE is_escalated)                    AS escalated,
    COUNT(*) FILTER (WHERE is_resolved)                     AS resolved,
    COUNT(*) FILTER (WHERE first_response_at IS NOT NULL)   AS responded,
    ROUND(AVG(response_time_mins) FILTER (WHERE response_time_mins IS NOT NULL), 1)
                                                            AS avg_respond_mins,
    ROUND(AVG(resolve_time_mins)  FILTER (WHERE resolve_time_mins  IS NOT NULL), 1)
                                                            AS avg_resolve_mins
FROM mv_ticket_base
GROUP BY created_day, created_month, department_name, ticket_type, priority
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_daily_volume_uid
    ON mv_daily_volume (created_day, department_name, ticket_type, priority);
CREATE INDEX IF NOT EXISTS mv_daily_volume_day   ON mv_daily_volume (created_day);
CREATE INDEX IF NOT EXISTS mv_daily_volume_month ON mv_daily_volume (created_month);
CREATE INDEX IF NOT EXISTS mv_daily_volume_dept  ON mv_daily_volume (department_name);


-- =============================================================================
-- MV 3: mv_employee_daily
-- Daily per-employee performance. Powers manager employee analytics.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_employee_daily AS
SELECT
    employee_id,
    employee_name,
    employee_code,
    employee_role,
    created_day,
    created_month,
    department_name,
    COUNT(*)                                              AS total,
    COUNT(*) FILTER (WHERE is_resolved)                   AS resolved,
    COUNT(*) FILTER (WHERE any_breached)                  AS breached,
    COUNT(*) FILTER (WHERE is_escalated)                  AS escalated,
    COUNT(*) FILTER (WHERE was_rescored)                  AS rescored,
    COUNT(*) FILTER (WHERE was_upscored)                  AS upscored,
    COUNT(*) FILTER (WHERE was_downscored)                AS downscored,
    COUNT(*) FILTER (WHERE model_priority IS NOT NULL)    AS total_with_model,
    ROUND(AVG(response_time_mins) FILTER (WHERE response_time_mins IS NOT NULL), 1)
                                                          AS avg_respond_mins,
    ROUND(AVG(resolve_time_mins)  FILTER (WHERE resolve_time_mins  IS NOT NULL), 1)
                                                          AS avg_resolve_mins
FROM mv_ticket_base
WHERE employee_id IS NOT NULL
GROUP BY employee_id, employee_name, employee_code, employee_role,
         created_day, created_month, department_name
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_employee_daily_uid
    ON mv_employee_daily (employee_id, created_day, department_name);
CREATE INDEX IF NOT EXISTS mv_employee_daily_emp   ON mv_employee_daily (employee_id);
CREATE INDEX IF NOT EXISTS mv_employee_daily_day   ON mv_employee_daily (created_day);
CREATE INDEX IF NOT EXISTS mv_employee_daily_month ON mv_employee_daily (created_month);


-- =============================================================================
-- MV 4: mv_acceptance_daily
-- Daily per-employee resolution acceptance. Powers manager employee analytics.
-- Source: suggested_resolution_usage + tickets.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_acceptance_daily AS
SELECT
    sru.employee_user_id                                     AS employee_id,
    up.full_name                                             AS employee_name,
    date_trunc('day',   t.created_at)::date                  AS created_day,
    date_trunc('month', t.created_at)::date                  AS created_month,
    COUNT(*)                                                 AS total,
    COUNT(*) FILTER (WHERE sru.decision = 'accepted')        AS accepted,
    COUNT(*) FILTER (WHERE sru.decision = 'declined_custom') AS declined
FROM suggested_resolution_usage sru
JOIN tickets       t  ON t.id       = sru.ticket_id
JOIN user_profiles up ON up.user_id = sru.employee_user_id
WHERE sru.employee_user_id IS NOT NULL AND sru.decision IS NOT NULL
GROUP BY sru.employee_user_id, up.full_name,
         date_trunc('day',   t.created_at)::date,
         date_trunc('month', t.created_at)::date
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_acceptance_daily_uid
    ON mv_acceptance_daily (employee_id, created_day);
CREATE INDEX IF NOT EXISTS mv_acceptance_daily_emp   ON mv_acceptance_daily (employee_id);
CREATE INDEX IF NOT EXISTS mv_acceptance_daily_month ON mv_acceptance_daily (created_month);
CREATE INDEX IF NOT EXISTS mv_acceptance_daily_day   ON mv_acceptance_daily (created_day);


-- =============================================================================
-- MV 5: mv_operator_qc_daily
-- Daily QC aggregates for Operator / Quality Control (rescoring + rerouting).
-- Source: tickets + approval_requests (base tables).
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_operator_qc_daily AS
SELECT
    date_trunc('day',   t.created_at)::date             AS created_day,
    date_trunc('month', t.created_at)::date             AS created_month,
    COALESCE(d.name, 'Unassigned')                      AS department_name,
    COUNT(DISTINCT t.id)                                AS total,
    COUNT(DISTINCT t.id) FILTER (WHERE
        t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
    )                                                   AS rescored,
    COUNT(DISTINCT t.id) FILTER (WHERE
        t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
        AND (
            (t.model_priority::TEXT = 'Low'    AND t.priority::TEXT IN ('Medium','High','Critical'))
         OR (t.model_priority::TEXT = 'Medium' AND t.priority::TEXT IN ('High','Critical'))
         OR (t.model_priority::TEXT = 'High'   AND t.priority::TEXT = 'Critical')
        )
    )                                                   AS upscored,
    COUNT(DISTINCT t.id) FILTER (WHERE
        t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
        AND (
            (t.model_priority::TEXT = 'Critical' AND t.priority::TEXT IN ('Low','Medium','High'))
         OR (t.model_priority::TEXT = 'High'     AND t.priority::TEXT IN ('Low','Medium'))
         OR (t.model_priority::TEXT = 'Medium'   AND t.priority::TEXT = 'Low')
        )
    )                                                   AS downscored,
    COUNT(DISTINCT t.id) FILTER (WHERE t.model_priority IS NOT NULL)
                                                        AS total_with_model,
    COUNT(ar.id)                                        AS rerouting_requests,
    COUNT(DISTINCT ar.ticket_id)                        AS rerouted_tickets
FROM tickets t
LEFT JOIN departments d
    ON d.id = t.department_id
LEFT JOIN approval_requests ar
    ON ar.ticket_id     = t.id
    AND ar.request_type = 'Rerouting'
GROUP BY
    date_trunc('day',   t.created_at)::date,
    date_trunc('month', t.created_at)::date,
    COALESCE(d.name, 'Unassigned')
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_operator_qc_daily_uid
    ON mv_operator_qc_daily (created_day, department_name);
CREATE INDEX IF NOT EXISTS mv_operator_qc_daily_day   ON mv_operator_qc_daily (created_day);
CREATE INDEX IF NOT EXISTS mv_operator_qc_daily_month ON mv_operator_qc_daily (created_month);
CREATE INDEX IF NOT EXISTS mv_operator_qc_daily_dept  ON mv_operator_qc_daily (department_name);


-- =============================================================================
-- MV 6: mv_chatbot_daily
-- Daily chatbot session aggregates. Powers ModelHealth Chatbot Agent tab.
-- Source: sessions + user_chat_logs (base tables).
--
-- Containment = session did not escalate AND did not create a ticket.
-- Sentiment at escalation = avg sentiment score of chat messages in sessions
--   that escalated to human (from user_chat_logs.sentiment_score).
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_chatbot_daily AS
SELECT
    date_trunc('day',   s.created_at)::date             AS created_day,
    date_trunc('month', s.created_at)::date             AS created_month,
    COUNT(*)                                            AS total_sessions,
    COUNT(*) FILTER (WHERE s.escalated_to_human = TRUE) AS escalated_sessions,
    COUNT(*) FILTER (WHERE
        s.escalated_to_human = FALSE
        AND s.linked_ticket_id IS NULL
    )                                                   AS contained_sessions,
    ROUND(AVG(msg_counts.msg_count), 1)                 AS avg_messages_per_session,
    -- Average sentiment score of messages in escalated sessions
    -- (NULL when no sentiment data exists — handled gracefully in service)
    ROUND(AVG(esc_sentiment.avg_sentiment), 3)          AS avg_escalation_sentiment,
    -- Sentiment bucket counts at escalation (for bar chart)
    COUNT(*) FILTER (WHERE
        s.escalated_to_human = TRUE
        AND esc_sentiment.avg_sentiment <  -0.5
    )                                                   AS esc_very_negative,
    COUNT(*) FILTER (WHERE
        s.escalated_to_human = TRUE
        AND esc_sentiment.avg_sentiment >= -0.5
        AND esc_sentiment.avg_sentiment <  -0.1
    )                                                   AS esc_negative,
    COUNT(*) FILTER (WHERE
        s.escalated_to_human = TRUE
        AND esc_sentiment.avg_sentiment >= -0.1
        AND esc_sentiment.avg_sentiment <   0.1
    )                                                   AS esc_neutral,
    COUNT(*) FILTER (WHERE
        s.escalated_to_human = TRUE
        AND esc_sentiment.avg_sentiment >=  0.1
    )                                                   AS esc_positive
FROM sessions s
LEFT JOIN (
    SELECT session_id, COUNT(*) AS msg_count
    FROM user_chat_logs
    GROUP BY session_id
) msg_counts ON msg_counts.session_id = s.session_id
LEFT JOIN (
    -- Average sentiment per session (only for sessions that have scored messages)
    SELECT session_id, AVG(sentiment_score) AS avg_sentiment
    FROM user_chat_logs
    WHERE sentiment_score IS NOT NULL
    GROUP BY session_id
) esc_sentiment ON esc_sentiment.session_id = s.session_id
GROUP BY
    date_trunc('day',   s.created_at)::date,
    date_trunc('month', s.created_at)::date
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_chatbot_daily_uid   ON mv_chatbot_daily (created_day);
CREATE INDEX        IF NOT EXISTS mv_chatbot_daily_month ON mv_chatbot_daily (created_month);


-- =============================================================================
-- MV 7: mv_sentiment_daily
-- Daily sentiment agent analytics. Powers ModelHealth Sentiment Agent tab.
-- Source: sentiment_outputs + tickets + departments (base tables).
--
-- Reads only is_current = TRUE rows from sentiment_outputs so we always
-- get the latest scoring per ticket, not historical reruns.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sentiment_daily AS
SELECT
    date_trunc('day',   so.created_at)::date            AS created_day,
    date_trunc('month', so.created_at)::date            AS created_month,
    COALESCE(d.name, 'Unassigned')                      AS department_name,
    so.model_version,
    COUNT(*)                                            AS total_scored,
    -- Confidence quality
    COUNT(*) FILTER (WHERE so.confidence_score < 0.60)  AS low_confidence,
    ROUND(AVG(so.sentiment_score), 3)                   AS avg_sentiment_score,
    -- Distribution buckets (matching UI labels)
    COUNT(*) FILTER (WHERE so.sentiment_label = 'Positive')     AS positive_count,
    COUNT(*) FILTER (WHERE so.sentiment_label = 'Neutral')      AS neutral_count,
    COUNT(*) FILTER (WHERE so.sentiment_label = 'Negative')     AS negative_count,
    COUNT(*) FILTER (WHERE so.sentiment_label = 'Very Negative') AS very_negative_count
FROM sentiment_outputs so
JOIN tickets    t  ON t.id  = so.ticket_id
LEFT JOIN departments d ON d.id = t.department_id
WHERE so.is_current = TRUE
GROUP BY
    date_trunc('day',   so.created_at)::date,
    date_trunc('month', so.created_at)::date,
    COALESCE(d.name, 'Unassigned'),
    so.model_version
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_sentiment_daily_uid
    ON mv_sentiment_daily (created_day, department_name, model_version);
CREATE INDEX IF NOT EXISTS mv_sentiment_daily_day   ON mv_sentiment_daily (created_day);
CREATE INDEX IF NOT EXISTS mv_sentiment_daily_month ON mv_sentiment_daily (created_month);
CREATE INDEX IF NOT EXISTS mv_sentiment_daily_dept  ON mv_sentiment_daily (department_name);


-- =============================================================================
-- MV 8: mv_feature_daily
-- Daily feature engineering agent analytics. Powers ModelHealth Feature tab.
-- Source: feature_outputs + tickets + departments (base tables).
--
-- business_impact, safety_concern, issue_severity, issue_urgency are stored
-- as keys inside feature_outputs.raw_features JSONB — extracted here.
-- NULL raw_features → all JSONB extractions return NULL → counted as absent.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_feature_daily AS
SELECT
    date_trunc('day',   fo.created_at)::date                AS created_day,
    date_trunc('month', fo.created_at)::date                AS created_month,
    COALESCE(d.name, 'Unassigned')                          AS department_name,
    fo.model_version,
    COUNT(*)                                                AS total_processed,
    -- Confidence quality
    COUNT(*) FILTER (WHERE fo.confidence_score < 0.60)      AS low_confidence,
    -- Recurring issues (from tickets.is_recurring, set by the feature agent)
    COUNT(*) FILTER (WHERE t.is_recurring = TRUE)           AS recurring_count,
    -- Safety flags (JSONB key: raw_features->>'safety_concern' = 'true')
    COUNT(*) FILTER (WHERE
        fo.raw_features IS NOT NULL
        AND (fo.raw_features->>'safety_concern')::boolean = TRUE
    )                                                       AS safety_flag_count,
    -- Business impact distribution (JSONB key: raw_features->>'business_impact')
    COUNT(*) FILTER (WHERE fo.raw_features->>'business_impact' = 'High')
                                                            AS impact_high,
    COUNT(*) FILTER (WHERE fo.raw_features->>'business_impact' = 'Medium')
                                                            AS impact_medium,
    COUNT(*) FILTER (WHERE fo.raw_features->>'business_impact' = 'Low')
                                                            AS impact_low,
    -- Severity vs urgency mismatch (both present and ≥ 2 levels apart)
    -- Severity/urgency assumed ordinal: Low=1, Medium=2, High=3, Critical=4
    COUNT(*) FILTER (WHERE
        fo.raw_features IS NOT NULL
        AND fo.raw_features->>'issue_severity' IS NOT NULL
        AND fo.raw_features->>'issue_urgency'  IS NOT NULL
        AND ABS(
            CASE fo.raw_features->>'issue_severity'
                WHEN 'Low'      THEN 1
                WHEN 'Medium'   THEN 2
                WHEN 'High'     THEN 3
                WHEN 'Critical' THEN 4
                ELSE 0
            END
            -
            CASE fo.raw_features->>'issue_urgency'
                WHEN 'Low'      THEN 1
                WHEN 'Medium'   THEN 2
                WHEN 'High'     THEN 3
                WHEN 'Critical' THEN 4
                ELSE 0
            END
        ) >= 2
    )                                                       AS severity_urgency_mismatch
FROM feature_outputs fo
JOIN tickets    t  ON t.id  = fo.ticket_id
LEFT JOIN departments d ON d.id = t.department_id
WHERE fo.is_current = TRUE
GROUP BY
    date_trunc('day',   fo.created_at)::date,
    date_trunc('month', fo.created_at)::date,
    COALESCE(d.name, 'Unassigned'),
    fo.model_version
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_feature_daily_uid
    ON mv_feature_daily (created_day, department_name, model_version);
CREATE INDEX IF NOT EXISTS mv_feature_daily_day   ON mv_feature_daily (created_day);
CREATE INDEX IF NOT EXISTS mv_feature_daily_month ON mv_feature_daily (created_month);
CREATE INDEX IF NOT EXISTS mv_feature_daily_dept  ON mv_feature_daily (department_name);


-- =============================================================================
-- PERSISTENT REFRESH HISTORY LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics_refresh_log (
    id                  BIGSERIAL    PRIMARY KEY,
    refreshed_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ms_base             INT,
    ms_daily_volume     INT,
    ms_employee_daily   INT,
    ms_acceptance       INT,
    ms_operator_qc      INT,
    ms_chatbot          INT,
    ms_sentiment        INT,
    ms_feature          INT,
    ms_total            INT,
    success             BOOLEAN      NOT NULL DEFAULT TRUE,
    error_message       TEXT
);

CREATE INDEX IF NOT EXISTS idx_analytics_refresh_log_at
    ON analytics_refresh_log (refreshed_at DESC);


-- =============================================================================
-- REFRESH FUNCTION — all 8 MVs in dependency order
-- Uses CONCURRENT refresh (requires unique indexes created above).
-- On first-run the indexes are always present because they were created earlier
-- in this same script. The function is safe to call any number of times.
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_analytics_mvs()
RETURNS JSONB AS $$
DECLARE
    t0              TIMESTAMPTZ := clock_timestamp();
    t1              TIMESTAMPTZ;
    t2              TIMESTAMPTZ;
    t3              TIMESTAMPTZ;
    t4              TIMESTAMPTZ;
    t5              TIMESTAMPTZ;
    t6              TIMESTAMPTZ;
    t7              TIMESTAMPTZ;
    t8              TIMESTAMPTZ;
    v_ms_base       INT;
    v_ms_daily      INT;
    v_ms_employee   INT;
    v_ms_acceptance INT;
    v_ms_qc         INT;
    v_ms_chatbot    INT;
    v_ms_sentiment  INT;
    v_ms_feature    INT;
    v_ms_total      INT;
    v_result        JSONB;
    v_has_data      BOOLEAN;
BEGIN
    -- Use CONCURRENT only when the MV has been populated at least once
    -- (CONCURRENT requires a unique index AND at least one prior populate).
    -- Check mv_ticket_base as the bellwether — if it has rows, all MVs do.
    SELECT EXISTS (SELECT 1 FROM mv_ticket_base LIMIT 1) INTO v_has_data;

    IF v_has_data THEN
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ticket_base;       t1 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_volume;      t2 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_employee_daily;    t3 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_acceptance_daily;  t4 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_operator_qc_daily; t5 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_chatbot_daily;     t6 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sentiment_daily;   t7 := clock_timestamp();
        REFRESH MATERIALIZED VIEW CONCURRENTLY mv_feature_daily;     t8 := clock_timestamp();
    ELSE
        -- First populate — CONCURRENT not allowed on empty MVs
        REFRESH MATERIALIZED VIEW mv_ticket_base;       t1 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_daily_volume;      t2 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_employee_daily;    t3 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_acceptance_daily;  t4 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_operator_qc_daily; t5 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_chatbot_daily;     t6 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_sentiment_daily;   t7 := clock_timestamp();
        REFRESH MATERIALIZED VIEW mv_feature_daily;     t8 := clock_timestamp();
    END IF;

    v_ms_base       := ROUND(EXTRACT(EPOCH FROM (t1 - t0)) * 1000);
    v_ms_daily      := ROUND(EXTRACT(EPOCH FROM (t2 - t1)) * 1000);
    v_ms_employee   := ROUND(EXTRACT(EPOCH FROM (t3 - t2)) * 1000);
    v_ms_acceptance := ROUND(EXTRACT(EPOCH FROM (t4 - t3)) * 1000);
    v_ms_qc         := ROUND(EXTRACT(EPOCH FROM (t5 - t4)) * 1000);
    v_ms_chatbot    := ROUND(EXTRACT(EPOCH FROM (t6 - t5)) * 1000);
    v_ms_sentiment  := ROUND(EXTRACT(EPOCH FROM (t7 - t6)) * 1000);
    v_ms_feature    := ROUND(EXTRACT(EPOCH FROM (t8 - t7)) * 1000);
    v_ms_total      := ROUND(EXTRACT(EPOCH FROM (t8 - t0)) * 1000);

    INSERT INTO analytics_refresh_log
        (refreshed_at, ms_base, ms_daily_volume, ms_employee_daily,
         ms_acceptance, ms_operator_qc, ms_chatbot, ms_sentiment, ms_feature, ms_total, success)
    VALUES
        (t8, v_ms_base, v_ms_daily, v_ms_employee,
         v_ms_acceptance, v_ms_qc, v_ms_chatbot, v_ms_sentiment, v_ms_feature, v_ms_total, TRUE);

    v_result := jsonb_build_object(
        'ok',                TRUE,
        'refreshed_at',      t8,
        'ms_base',           v_ms_base,
        'ms_daily_volume',   v_ms_daily,
        'ms_employee_daily', v_ms_employee,
        'ms_acceptance',     v_ms_acceptance,
        'ms_operator_qc',    v_ms_qc,
        'ms_chatbot',        v_ms_chatbot,
        'ms_sentiment',      v_ms_sentiment,
        'ms_feature',        v_ms_feature,
        'ms_total',          v_ms_total
    );

    RETURN v_result;

EXCEPTION WHEN OTHERS THEN
    BEGIN
        INSERT INTO analytics_refresh_log (refreshed_at, success, error_message)
        VALUES (clock_timestamp(), FALSE, SQLERRM);
    EXCEPTION WHEN OTHERS THEN
        NULL;
    END;
    RAISE;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- INITIAL POPULATE
-- Called only when this file is first applied. The SELECT refresh_analytics_mvs()
-- call handles both first-run (non-CONCURRENT) and re-run (CONCURRENT) cases
-- automatically via the v_has_data check inside the function.
-- =============================================================================

SELECT refresh_analytics_mvs() AS initial_populate_result;


-- =============================================================================
-- SCHEDULED AUTO-REFRESH via pg_cron (every 12 hours) — optional
-- Not available in stock postgres:14-alpine.
-- Backend refresh loop handles this when pg_cron is absent.
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron') THEN
        PERFORM pg_catalog.set_config('search_path', 'public', false);
        CREATE EXTENSION IF NOT EXISTS pg_cron;
        IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'innovacx-refresh-analytics') THEN
            PERFORM cron.unschedule('innovacx-refresh-analytics');
        END IF;
        PERFORM cron.schedule(
            'innovacx-refresh-analytics',
            '0 0,12 * * *',
            'SELECT refresh_analytics_mvs();'
        );
        RAISE NOTICE 'pg_cron: scheduled innovacx-refresh-analytics every 12h';
    ELSE
        RAISE NOTICE 'pg_cron not available — MVs will refresh via backend 12-hour loop.';
    END IF;
END;
$$;
