-- =============================================================================
-- InnovaCX — Role Separation & Least-Privilege Grants
-- File: database/zzz_least_privilege.sql
--
-- PURPOSE:
--   Assigns exactly the required privileges to each runtime role.
--   Role creation and password assignment is handled by the shell script
--   zzz_least_privilege.sh, which runs first (alphabetically .sh < .sql).
--
-- ROLES CONFIGURED HERE:
--   innovacx_app      — runtime: DML only (backend / chatbot / orchestrator)
--   innovacx_readonly — read-only: SELECT only (reporting / dashboards)
--   innovacx_test     — test env: mirrors innovacx_app DML rights
--
-- WHY NO \getenv OR PASSWORD HANDLING HERE:
--   The docker-entrypoint-initdb.d mechanism pipes .sql files to psql via
--   stdin on postgres:14-alpine. In this mode, \getenv is not processed.
--   Passwords are set by zzz_least_privilege.sh before this file runs.
--
-- IDEMPOTENT:
--   All statements are safe to re-run on an already-initialised volume.
--
-- EXECUTION ORDER (alphabetical):
--   zzz_analytics_mvs.sh    — analytics MVs
--   zzz_least_privilege.sh  — role creation + passwords
--   zzz_least_privilege.sql — THIS FILE: grants/revokes
-- =============================================================================

-- =========================================================================
-- 1. Database-level privileges
-- =========================================================================

-- Remove PUBLIC's implicit database access on the application database.
REVOKE ALL ON DATABASE complaints_db FROM PUBLIC;

-- Block the postgres system database from all non-superuser roles.
-- innovacx_admin inherits PUBLIC, so revoking from PUBLIC closes the gap.
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;

-- Block the template1 default database from all non-superuser roles.
-- template1 is not used by any application service; restricting it removes
-- an unnecessary default entry point. Superusers (innovacx_admin) retain
-- access; CREATE DATABASE still works because it does not require the
-- caller to have CONNECT on the template.
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;

-- Grant only what each role needs at database level.
GRANT CONNECT, TEMPORARY ON DATABASE complaints_db TO innovacx_app;
GRANT CONNECT            ON DATABASE complaints_db TO innovacx_readonly;
GRANT CONNECT, TEMPORARY ON DATABASE complaints_db TO innovacx_test;

-- =========================================================================
-- 2. Schema-level privileges
-- =========================================================================

-- Revoke PUBLIC's default CREATE on the public schema (PostgreSQL 14 default).
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- Revoke PUBLIC's default EXECUTE on all functions.
--   PostgreSQL grants EXECUTE on new functions to PUBLIC by default.
--   Without this revoke, every role (including innovacx_readonly) can call
--   every function regardless of explicit GRANT/REVOKE statements below.
--   The explicit GRANT EXECUTE lines later in this file re-grant to the
--   roles that legitimately need it (innovacx_app, innovacx_test only).
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

-- innovacx_app: USAGE only — no CREATE.
--   Both _ensure_runtime_schema_compatibility() (main.py) and
--   _ensure_analytics_mvs() (analytics_service.py) contain an ownership
--   guard: they check pg_get_userbyid(relowner) = current_user and skip
--   all DDL silently when running as a non-owner. On every fresh volume
--   innovacx_admin owns all tables, so these code paths are always skipped
--   at runtime. CREATE on the schema is not exercised and is not granted.
GRANT USAGE ON SCHEMA public TO innovacx_app;

-- innovacx_readonly: USAGE only — required to reference objects in the schema.
GRANT USAGE ON SCHEMA public TO innovacx_readonly;

-- innovacx_test: USAGE only — mirrors innovacx_app, no CREATE.
GRANT USAGE ON SCHEMA public TO innovacx_test;

-- =========================================================================
-- 3. Table-level DML privileges
-- =========================================================================

-- innovacx_app: full DML — proven from main.py:
--   SELECT  — all read endpoints
--   INSERT  — ticket creation, notifications, pipeline logs
--   UPDATE  — ticket status, user records, notification flags
--   DELETE  — operator_delete_user(), operator_delete_ticket(),
--             report summary cleanup
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO innovacx_app;

-- innovacx_readonly: SELECT only — strictly read-only, no side effects.
GRANT SELECT ON ALL TABLES IN SCHEMA public TO innovacx_readonly;

-- innovacx_test: same DML as innovacx_app.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO innovacx_test;

-- =========================================================================
-- 4. Sequence privileges
-- =========================================================================

-- innovacx_app: USAGE (nextval) + SELECT (currval) for BIGSERIAL columns
--   (e.g. analytics_refresh_log.id).
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO innovacx_app;

-- innovacx_readonly: SELECT only (currval / COPY).
--   USAGE (nextval) intentionally NOT granted — must never advance a sequence.
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO innovacx_readonly;

-- innovacx_test: same as innovacx_app.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO innovacx_test;

-- =========================================================================
-- 5. Function EXECUTE privileges
-- =========================================================================

-- innovacx_app: EXECUTE needed for (proven from main.py):
--   apply_ticket_sla_policies()       — SLA heartbeat loop
--   compute_is_recurring_ticket(...)  — ticket creation gate
--   refresh_analytics_mvs()           — analytics MV refresh
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO innovacx_app;

-- innovacx_readonly: NO EXECUTE.
--   refresh_analytics_mvs() writes to analytics_refresh_log.
--   apply_ticket_sla_policies() updates ticket rows.
--   Neither is appropriate for a read-only role.

-- innovacx_test: same as innovacx_app.
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO innovacx_test;

-- =========================================================================
-- 6. SECURITY DEFINER on refresh_analytics_mvs()
--
--    REFRESH MATERIALIZED VIEW requires the caller to be the MV owner.
--    innovacx_admin owns all MVs. SECURITY DEFINER makes the function run
--    as innovacx_admin (its owner) regardless of the calling role, so
--    innovacx_app can call it successfully.
-- =========================================================================
ALTER FUNCTION refresh_analytics_mvs() SECURITY DEFINER;

-- =========================================================================
-- 7. Ensure password_changed_at column exists on users
--
--    Used by get_current_user() (main.py) for stale-session detection.
--    Added here by innovacx_admin (table owner). The backend's
--    _ensure_runtime_schema_compatibility() skips this DDL because
--    innovacx_app does not own the table, so this is the reliable path.
-- =========================================================================
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;

-- =========================================================================
-- 8. Default privileges
--
--    Any object created in the future by innovacx_admin (new migrations,
--    tables, functions, MVs) is automatically accessible to all runtime
--    roles. Prevents privilege drift as new migrations are applied.
-- =========================================================================

-- innovacx_app defaults
ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO innovacx_app;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO innovacx_app;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO innovacx_app;

-- innovacx_readonly defaults (SELECT only — no sequences write, no functions)
ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT SELECT ON TABLES TO innovacx_readonly;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT SELECT ON SEQUENCES TO innovacx_readonly;

-- Revoke PUBLIC's default EXECUTE on future functions created by innovacx_admin.
--   Without this, every new function created by a future migration would
--   automatically be callable by innovacx_readonly via the PUBLIC grant.
ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- innovacx_test defaults (mirrors innovacx_app)
ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO innovacx_test;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO innovacx_test;

ALTER DEFAULT PRIVILEGES FOR ROLE innovacx_admin IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO innovacx_test;
