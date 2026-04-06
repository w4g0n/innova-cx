#!/bin/bash
# =============================================================================
# InnovaCX — Role Creation with Password Injection
# File: database/zzz_least_privilege.sh
#
# PURPOSE:
#   Creates the three runtime database roles (innovacx_app, innovacx_readonly,
#   innovacx_test) and sets their passwords from environment variables.
#   Runs BEFORE zzz_least_privilege.sql (alphabetically .sh < .sql with the
#   same prefix), which then handles all GRANT/REVOKE statements.
#
# WHY A SHELL SCRIPT:
#   The docker-entrypoint-initdb.d mechanism pipes .sql files to psql via
#   stdin redirection. In that mode, psql meta-commands like \getenv are NOT
#   reliably processed on postgres:14-alpine. Shell scripts (.sh) in the same
#   directory receive the full container environment and call psql -c directly,
#   which is the correct and reliable way to inject env var values into SQL.
#   This is the same pattern used by zzz_analytics_mvs.sh.
#
# EXECUTION ORDER (alphabetical within docker-entrypoint-initdb.d):
#   zzz_analytics_mvs.sh       — runs first  (analytics MVs)
#   zzz_least_privilege.sh     — runs second (THIS FILE: role creation)
#   zzz_least_privilege.sql    — runs third  (grants/revokes)
#
# REQUIRED ENV VARS (set in .env, passed via docker-compose postgres environment):
#   APP_DB_PASSWORD         — password for innovacx_app
#   READONLY_DB_PASSWORD    — password for innovacx_readonly
#   TEST_DB_PASSWORD        — password for innovacx_test
#   POSTGRES_USER           — superuser name (innovacx_admin)
#   POSTGRES_DB             — database name (complaints_db)
#
# IDEMPOTENT:
#   Uses CREATE ROLE IF NOT EXISTS logic via DO $$ guards.
#   Safe to re-run on an already-initialised volume.
# =============================================================================

set -e

echo "==> [zzz_least_privilege.sh] Validating role password environment variables..."

# ── Validate all required passwords are set ──────────────────────────────────
fail=0
for varname in APP_DB_PASSWORD READONLY_DB_PASSWORD TEST_DB_PASSWORD; do
    if [ -z "${!varname}" ]; then
        echo "ERROR: Required env var '$varname' is not set or is empty."
        fail=1
    fi
done

if [ "$fail" -eq 1 ]; then
    echo ""
    echo "FATAL: One or more required DB role passwords are missing."
    echo "       Set APP_DB_PASSWORD, READONLY_DB_PASSWORD, and TEST_DB_PASSWORD"
    echo "       in your .env file before starting the container."
    exit 1
fi

echo "==> [zzz_least_privilege.sh] All passwords present. Creating roles..."

# ── Helper: run a SQL statement as the superuser ─────────────────────────────
run_sql() {
    psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"
}

# ── 1. innovacx_app — runtime application role ───────────────────────────────
run_sql "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'innovacx_app') THEN
        CREATE ROLE innovacx_app
            WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
        RAISE NOTICE 'Role innovacx_app created.';
    ELSE
        RAISE NOTICE 'Role innovacx_app already exists.';
    END IF;
END \$\$;
"

# Set password separately so the shell variable expands correctly.
# Single-quoting the password and escaping any embedded single quotes.
APP_PW_ESCAPED=$(printf "%s" "$APP_DB_PASSWORD" | sed "s/'/''/g")
run_sql "ALTER ROLE innovacx_app PASSWORD '${APP_PW_ESCAPED}';"

echo "==> [zzz_least_privilege.sh] innovacx_app: OK"

# ── 2. innovacx_readonly — read-only reporting role ──────────────────────────
run_sql "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'innovacx_readonly') THEN
        CREATE ROLE innovacx_readonly
            WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
        RAISE NOTICE 'Role innovacx_readonly created.';
    ELSE
        RAISE NOTICE 'Role innovacx_readonly already exists.';
    END IF;
END \$\$;
"

READONLY_PW_ESCAPED=$(printf "%s" "$READONLY_DB_PASSWORD" | sed "s/'/''/g")
run_sql "ALTER ROLE innovacx_readonly PASSWORD '${READONLY_PW_ESCAPED}';"

echo "==> [zzz_least_privilege.sh] innovacx_readonly: OK"

# ── 3. innovacx_test — test environment role ─────────────────────────────────
run_sql "
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'innovacx_test') THEN
        CREATE ROLE innovacx_test
            WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
        RAISE NOTICE 'Role innovacx_test created.';
    ELSE
        RAISE NOTICE 'Role innovacx_test already exists.';
    END IF;
END \$\$;
"

TEST_PW_ESCAPED=$(printf "%s" "$TEST_DB_PASSWORD" | sed "s/'/''/g")
run_sql "ALTER ROLE innovacx_test PASSWORD '${TEST_PW_ESCAPED}';"

echo "==> [zzz_least_privilege.sh] innovacx_test: OK"
echo "==> [zzz_least_privilege.sh] All roles created. zzz_least_privilege.sql will now run grants."
