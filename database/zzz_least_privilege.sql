-- =============================================================================
-- InnovaCX — Least-Privilege Role Setup
-- File: database/zzz_least_privilege.sql
--
-- PURPOSE:
--   Creates the innovacx_app runtime role and grants it exactly the
--   permissions needed by the backend, chatbot, and orchestrator services.
--
-- EXECUTION:
--   Runs automatically during docker-entrypoint-initdb.d processing on a
--   fresh volume. .sql files are executed by the postgres entrypoint via
--   psql redirection — no execute permission is required on the file.
--   The zzz_ prefix guarantees this runs AFTER init.sql, all seed files,
--   and zzz_analytics_mvs.sh.
--
-- IDEMPOTENT:
--   All statements use IF NOT EXISTS / DO $$ guards. Safe to re-run.
--
-- PASSWORD:
--   Uses the same value as APP_DB_PASSWORD in .env (changeme123).
--   This is consistent with how POSTGRES_PASSWORD is stored in the repo.
-- =============================================================================

-- -------------------------------------------------------------------------
-- 1. Create the runtime application role
--    If it already exists (re-run scenario), update the password to keep
--    it in sync with the value in .env.
-- -------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'innovacx_app') THEN
        CREATE ROLE innovacx_app
            WITH LOGIN
                 NOSUPERUSER
                 NOCREATEDB
                 NOCREATEROLE
                 NOREPLICATION
                 PASSWORD 'changeme123';
        RAISE NOTICE 'Role innovacx_app created.';
    ELSE
        ALTER ROLE innovacx_app PASSWORD 'changeme123';
        RAISE NOTICE 'Role innovacx_app already exists — password refreshed.';
    END IF;
END $$;

-- -------------------------------------------------------------------------
-- 2. Database-level privileges
-- -------------------------------------------------------------------------

-- Remove PUBLIC's implicit database access on the application database.
REVOKE ALL ON DATABASE complaints_db FROM PUBLIC;

-- Confine the runtime role to the application database only.
-- In PostgreSQL 14, CONNECT on the postgres system database is granted to
-- PUBLIC by default. Revoking directly from innovacx_app is insufficient
-- because the role inherits the PUBLIC grant. Revoking from PUBLIC closes
-- the gap for all non-superuser roles including innovacx_app.
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;

-- Grant only what the runtime role needs.
GRANT CONNECT   ON DATABASE complaints_db TO innovacx_app;
GRANT TEMPORARY ON DATABASE complaints_db TO innovacx_app;

-- -------------------------------------------------------------------------
-- 3. Revoke PUBLIC's CREATE on the public schema
--    PostgreSQL 14 grants this to PUBLIC by default.
--    Any authenticated user could otherwise create tables.
-- -------------------------------------------------------------------------
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- -------------------------------------------------------------------------
-- 4. Schema-level privileges for innovacx_app
--
--    USAGE  — required to reference any object in the schema.
--    CREATE — required by proven runtime DDL:
--             • analytics_service.py (_ANALYTICS_MVS_DDL):
--               ALTER TABLE, CREATE TABLE IF NOT EXISTS,
--               CREATE INDEX IF NOT EXISTS, CREATE MATERIALIZED VIEW
--             • main.py (_ensure_runtime_schema_compatibility):
--               ALTER TABLE, CREATE TABLE IF NOT EXISTS,
--               CREATE INDEX IF NOT EXISTS
--             Without CREATE the app crashes on first boot.
-- -------------------------------------------------------------------------
GRANT USAGE, CREATE ON SCHEMA public TO innovacx_app;

-- -------------------------------------------------------------------------
-- 5. Table-level DML privileges
--
--    All four verbs proven from main.py source:
--      SELECT  — all read endpoints
--      INSERT  — ticket creation, notifications, logs
--      UPDATE  — ticket status, user records, notification flags
--      DELETE  — operator_delete_user(), operator_delete_ticket(),
--                report summary item cleanup
--
--    Granted on ALL TABLES rather than a fixed list because
--    analytics_service.py and main.py create tables at runtime —
--    a fixed list would become stale immediately.
-- -------------------------------------------------------------------------
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO innovacx_app;

-- -------------------------------------------------------------------------
-- 6. Sequence privileges
--    analytics_refresh_log uses BIGSERIAL. Granted on ALL SEQUENCES for
--    forward-compatibility.
-- -------------------------------------------------------------------------
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO innovacx_app;

-- -------------------------------------------------------------------------
-- 7. Function EXECUTE privileges
--
--    Directly called from application code (proven from main.py):
--      apply_ticket_sla_policies()       — SLA heartbeat loop
--      compute_is_recurring_ticket(...)  — ticket creation gate
--      refresh_analytics_mvs()           — analytics MV refresh
--    Trigger functions are fired by the DB engine but EXECUTE on ALL
--    FUNCTIONS covers direct calls correctly.
-- -------------------------------------------------------------------------
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO innovacx_app;

-- -------------------------------------------------------------------------
-- 8. Make refresh_analytics_mvs() run as its owner (innovacx_admin)
--
--    analytics_mvs.sql creates refresh_analytics_mvs() without SECURITY
--    DEFINER (confirmed from source). When innovacx_app calls it, the
--    function runs as innovacx_app, which does not own the materialized
--    views, causing REFRESH MATERIALIZED VIEW to fail with "must be owner".
--
--    ALTER FUNCTION ... SECURITY DEFINER makes the function execute as its
--    owner (innovacx_admin) regardless of the calling role. innovacx_admin
--    owns all MVs and can REFRESH them. This fixes the startup MV refresh
--    and the 12-hour background analytics refresh loop.
--
--    This statement runs as innovacx_admin (who owns the function), so it
--    is fully permitted.
-- -------------------------------------------------------------------------
ALTER FUNCTION refresh_analytics_mvs() SECURITY DEFINER;

-- -------------------------------------------------------------------------
-- 9. Default privileges
--    Any object created in the future by innovacx_admin (new migration
--    tables, functions, MVs) is automatically accessible to innovacx_app.
--    Without this each new migration would need a manual re-grant.
-- -------------------------------------------------------------------------
ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO innovacx_app;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO innovacx_app;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO innovacx_app;
