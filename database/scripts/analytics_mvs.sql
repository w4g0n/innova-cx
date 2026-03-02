-- =============================================================================
-- InnovaCX  –  Analytics Materialized Views
-- File: database/scripts/analytics_mvs.sql
-- =============================================================================
--
-- HOW THIS FILE FITS IN YOUR PROJECT
-- ────────────────────────────────────────────────────────────────────────────
-- docker-compose.yml mounts  ./database:/docker-entrypoint-initdb.d
-- PostgreSQL runs EVERY *.sql file in that folder alphabetically on first start.
-- init.sql starts with "0" so it runs first.
-- Name this file  "analytics_mvs.sql" (or "1_analytics_mvs.sql" to be safe).
-- On an EXISTING volume: run it manually once (see instructions below).
--
-- MANUAL INSTALL (existing database)
-- ────────────────────────────────────────────────────────────────────────────
--   docker exec -i innovacx-db psql \
--     -U $POSTGRES_USER -d $POSTGRES_DB \
--     < database/scripts/analytics_mvs.sql
--
-- REFRESH (after new tickets are created)
-- ────────────────────────────────────────────────────────────────────────────
--   SELECT refresh_analytics_mvs();              -- manual SQL call
--   POST /api/manager/analytics/refresh          -- FastAPI endpoint (manager token)
--   The FastAPI startup event also refreshes automatically.
--
-- SAFE TO RE-RUN: every CREATE uses IF NOT EXISTS / OR REPLACE.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- EXTRA INDEXES ON BASE TABLES
-- These make both the MV build and every analytics query fast.
-- ─────────────────────────────────────────────────────────────────────────────

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

CREATE INDEX IF NOT EXISTS idx_trf_employee_decision
    ON ticket_resolution_feedback (employee_user_id, decision);

CREATE INDEX IF NOT EXISTS idx_trf_ticket_created
    ON ticket_resolution_feedback (ticket_id);


-- =============================================================================
-- MV 1: mv_ticket_base  ← THE "MOTHER" VIEW
-- =============================================================================
-- One denormalised row per ticket. Every other analytics query reads from here.
-- Pre-computes: department name, employee info, time deltas, SLA flags,
-- escalation flag, rescore flags, time buckets.
--
-- Reading from this MV instead of joining 5 tables saves ~70-90% query time.
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_ticket_base AS
SELECT
    -- ── Identity ──────────────────────────────────────────────────────────
    t.id                                        AS ticket_id,
    t.ticket_code,

    -- ── Classification ────────────────────────────────────────────────────
    t.ticket_type::TEXT                         AS ticket_type,   -- 'Complaint'|'Inquiry'
    t.priority::TEXT                            AS priority,
    t.model_priority::TEXT                      AS model_priority,
    t.status::TEXT                              AS status,

    -- ── Department ────────────────────────────────────────────────────────
    t.department_id,
    COALESCE(d.name, 'Unassigned')              AS department_name,

    -- ── Assigned employee ─────────────────────────────────────────────────
    t.assigned_to_user_id                       AS employee_id,
    up_emp.full_name                            AS employee_name,
    up_emp.employee_code,
    up_emp.job_title                            AS employee_role,

    -- ── Creator (for recurring detection) ────────────────────────────────
    t.created_by_user_id,

    -- ── Timestamps ────────────────────────────────────────────────────────
    t.created_at,
    t.first_response_at,
    t.resolved_at,
    t.respond_due_at,
    t.resolve_due_at,
    t.priority_assigned_at,
    t.assigned_at,

    -- ── Pre-truncated time buckets (fast GROUP BY, no function call) ──────
    date_trunc('day',   t.created_at)::date     AS created_day,
    date_trunc('week',  t.created_at)::date     AS created_week,
    date_trunc('month', t.created_at)::date     AS created_month,

    -- ── SLA breach flags ──────────────────────────────────────────────────
    t.respond_breached,
    t.resolve_breached,
    (t.respond_breached OR t.resolve_breached)  AS any_breached,

    -- ── Status-derived flags ──────────────────────────────────────────────
    (t.status = 'Escalated')                    AS is_escalated,
    (t.status = 'Resolved')                     AS is_resolved,

    -- ── Pre-computed response/resolve time (minutes) ──────────────────────
    -- NULL when the event hasn't happened yet — never show 0 for "not done"
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

    -- ── SLA target minutes (mirrors the DB trigger logic exactly) ─────────
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

    -- ── Rescore flags (model vs final priority) ───────────────────────────
    (   t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
    )                                           AS was_rescored,

    (   t.model_priority IS NOT NULL
        AND t.priority::TEXT <> t.model_priority::TEXT
        AND (
            (t.model_priority::TEXT = 'Low'      AND t.priority::TEXT IN ('Medium','High','Critical'))
         OR (t.model_priority::TEXT = 'Medium'   AND t.priority::TEXT IN ('High','Critical'))
         OR (t.model_priority::TEXT = 'High'     AND t.priority::TEXT = 'Critical')
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
LEFT JOIN departments   d      ON d.id       = t.department_id
LEFT JOIN user_profiles up_emp ON up_emp.user_id = t.assigned_to_user_id
;

-- Required unique index: enables REFRESH CONCURRENTLY (no read-lock on refresh)
CREATE UNIQUE INDEX IF NOT EXISTS mv_ticket_base_uid
    ON mv_ticket_base (ticket_id);

-- Composite index: the two most common filter columns in every analytics query
CREATE INDEX IF NOT EXISTS mv_ticket_base_day_dept
    ON mv_ticket_base (created_day, department_name);

CREATE INDEX IF NOT EXISTS mv_ticket_base_month_dept
    ON mv_ticket_base (created_month, department_name);

CREATE INDEX IF NOT EXISTS mv_ticket_base_priority
    ON mv_ticket_base (priority);

CREATE INDEX IF NOT EXISTS mv_ticket_base_employee
    ON mv_ticket_base (employee_id);

CREATE INDEX IF NOT EXISTS mv_ticket_base_type
    ON mv_ticket_base (ticket_type);

CREATE INDEX IF NOT EXISTS mv_ticket_base_created_at
    ON mv_ticket_base (created_at);

-- Composite index for employee report generation:
-- WHERE employee_id = %s AND created_at >= %s AND created_at <= %s
CREATE INDEX IF NOT EXISTS mv_ticket_base_emp_created
    ON mv_ticket_base (employee_id, created_at)
    WHERE employee_id IS NOT NULL;


-- =============================================================================
-- MV 2: mv_daily_volume
-- =============================================================================
-- Pre-aggregated daily counts by (day × department × ticket_type × priority).
-- Feeds: complaint-vs-inquiry chart, daily volume + rolling avg, monthly bars,
--        SLA breach timeline, categories pie.
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
GROUP BY
    created_day,
    created_month,
    department_name,
    ticket_type,
    priority
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_daily_volume_uid
    ON mv_daily_volume (created_day, department_name, ticket_type, priority);

CREATE INDEX IF NOT EXISTS mv_daily_volume_day   ON mv_daily_volume (created_day);
CREATE INDEX IF NOT EXISTS mv_daily_volume_month ON mv_daily_volume (created_month);
CREATE INDEX IF NOT EXISTS mv_daily_volume_dept  ON mv_daily_volume (department_name);


-- =============================================================================
-- MV 3: mv_employee_daily
-- =============================================================================
-- Per-employee per-day KPI rollup. Used for Section C employee performance.
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
GROUP BY
    employee_id,
    employee_name,
    employee_code,
    employee_role,
    created_day,
    created_month,
    department_name
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_employee_daily_uid
    ON mv_employee_daily (employee_id, created_day, department_name);

CREATE INDEX IF NOT EXISTS mv_employee_daily_emp   ON mv_employee_daily (employee_id);
CREATE INDEX IF NOT EXISTS mv_employee_daily_day   ON mv_employee_daily (created_day);
CREATE INDEX IF NOT EXISTS mv_employee_daily_month ON mv_employee_daily (created_month);


-- =============================================================================
-- MV 4: mv_acceptance_daily
-- =============================================================================
-- Per-employee per-day AI resolution acceptance stats.
-- Feeds: Section C "acceptanceRate" and "alertLowAcceptance".
-- =============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_acceptance_daily AS
SELECT
    trf.employee_user_id                                   AS employee_id,
    up.full_name                                           AS employee_name,
    date_trunc('day',   t.created_at)::date                AS created_day,
    date_trunc('month', t.created_at)::date                AS created_month,
    COUNT(*)                                               AS total,
    COUNT(*) FILTER (WHERE trf.decision = 'accepted')      AS accepted,
    COUNT(*) FILTER (WHERE trf.decision = 'declined_custom') AS declined
FROM ticket_resolution_feedback trf
JOIN tickets       t  ON t.id       = trf.ticket_id
JOIN user_profiles up ON up.user_id = trf.employee_user_id
GROUP BY
    trf.employee_user_id,
    up.full_name,
    date_trunc('day',   t.created_at)::date,
    date_trunc('month', t.created_at)::date
;

CREATE UNIQUE INDEX IF NOT EXISTS mv_acceptance_daily_uid
    ON mv_acceptance_daily (employee_id, created_day);

CREATE INDEX IF NOT EXISTS mv_acceptance_daily_emp   ON mv_acceptance_daily (employee_id);
CREATE INDEX IF NOT EXISTS mv_acceptance_daily_month ON mv_acceptance_daily (created_month);


-- =============================================================================
-- REFRESH FUNCTION
-- =============================================================================
-- Refreshes all four MVs in dependency order.
-- Uses CONCURRENTLY so dashboards keep reading stale data during refresh
-- (no table lock, zero downtime).
-- Unique indexes above are required for CONCURRENTLY to work.
--
-- Usage:
--   SELECT refresh_analytics_mvs();
--   → returns JSONB with per-MV timing info
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_analytics_mvs()
RETURNS JSONB AS $$
DECLARE
    t0 TIMESTAMPTZ := clock_timestamp();
    t1 TIMESTAMPTZ;
    t2 TIMESTAMPTZ;
    t3 TIMESTAMPTZ;
    t4 TIMESTAMPTZ;
BEGIN
    -- Must refresh in order: base first, derived after
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_ticket_base;
    t1 := clock_timestamp();

    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_volume;
    t2 := clock_timestamp();

    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_employee_daily;
    t3 := clock_timestamp();

    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_acceptance_daily;
    t4 := clock_timestamp();

    RETURN jsonb_build_object(
        'ok',                TRUE,
        'refreshed_at',      t4,
        'ms_base',           ROUND(EXTRACT(EPOCH FROM (t1 - t0)) * 1000),
        'ms_daily_volume',   ROUND(EXTRACT(EPOCH FROM (t2 - t1)) * 1000),
        'ms_employee_daily', ROUND(EXTRACT(EPOCH FROM (t3 - t2)) * 1000),
        'ms_acceptance',     ROUND(EXTRACT(EPOCH FROM (t4 - t3)) * 1000),
        'ms_total',          ROUND(EXTRACT(EPOCH FROM (t4 - t0)) * 1000)
    );
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- INITIAL POPULATE  (runs once at install time)
-- =============================================================================
-- Blocking refresh is fine here — we're just installing, not serving traffic.

REFRESH MATERIALIZED VIEW mv_ticket_base;
REFRESH MATERIALIZED VIEW mv_daily_volume;
REFRESH MATERIALIZED VIEW mv_employee_daily;
REFRESH MATERIALIZED VIEW mv_acceptance_daily;


-- =============================================================================
-- SCHEDULED AUTO-REFRESH via pg_cron  (every 12 hours)
-- =============================================================================
-- pg_cron is a Postgres extension that runs SQL on a schedule inside the DB
-- itself — no external cron daemon, no Docker side-car needed.
--
-- HOW TO INSTALL pg_cron (do this once, requires superuser):
--   1. Add to postgresql.conf:   shared_preload_libraries = 'pg_cron'
--   2. Restart Postgres
--   3. Run once:                 CREATE EXTENSION IF NOT EXISTS pg_cron;
--
-- For Docker/docker-compose, add this to your postgres service environment:
--   POSTGRES_INITDB_ARGS: "--auth-host=md5"
-- and add to postgresql.conf (or override via command):
--   shared_preload_libraries = 'pg_cron'
--   cron.database_name = 'your_db_name'   -- must match $POSTGRES_DB
--
-- The block below is SAFE TO RUN even if pg_cron is not installed.
-- It checks for the extension first and skips silently if not found.
-- =============================================================================

DO $$
BEGIN
    -- Only proceed if pg_cron is installed
    IF EXISTS (
        SELECT 1 FROM pg_available_extensions WHERE name = 'pg_cron'
    ) THEN
        -- Ensure the extension is created in this database
        PERFORM pg_catalog.set_config('search_path', 'public', false);

        -- Create extension if not already present
        CREATE EXTENSION IF NOT EXISTS pg_cron;

        -- Remove any existing schedule with this name (idempotent re-runs)
        PERFORM cron.unschedule('innovacx-refresh-analytics')
        WHERE EXISTS (
            SELECT 1 FROM cron.job WHERE jobname = 'innovacx-refresh-analytics'
        );

        -- Schedule: twice a day at midnight and noon (every 12 hours)
        -- Cron syntax:  minute  hour   day  month  weekday
        --                 0     0,12    *     *       *
        PERFORM cron.schedule(
            'innovacx-refresh-analytics',        -- job name (unique identifier)
            '0 0,12 * * *',                      -- every 12 hours (00:00 and 12:00 UTC)
            'SELECT refresh_analytics_mvs();'    -- the function we defined above
        );

        RAISE NOTICE 'pg_cron: scheduled innovacx-refresh-analytics every 12 hours (00:00 and 12:00 UTC)';
    ELSE
        RAISE NOTICE 'pg_cron not available — skipping schedule setup. '
                     'MVs will still refresh on every backend restart and via '
                     'POST /api/manager/analytics/refresh. '
                     'To enable auto-refresh: install pg_cron and re-run this file.';
    END IF;
END;
$$;