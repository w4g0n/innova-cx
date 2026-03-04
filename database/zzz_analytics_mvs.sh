#!/bin/bash
# zzz_analytics_mvs.sh
# Runs AFTER init.sql (files execute alphabetically — "zzz" ensures last).
# Step 1: applies prerequisite columns/tables/ENUMs that init.sql seeds depend on
#         but that 001_agent_execution_logs.sql did not create in its original form.
# Step 2: applies the materialized views and refresh function.
#
# IMPORTANT: init.sql already adds the sessions/user_chat_logs analytics columns
# inline (via ALTER TABLE IF NOT EXISTS). This script is therefore safe to re-run
# on existing volumes — every statement is idempotent.
set -e

# ---------------------------------------------------------------------------
# Helper: run psql and exit with a clear error on failure.
# ---------------------------------------------------------------------------
run_sql() {
    local label="$1"
    local file="$2"
    echo "==> [$(date -u '+%H:%M:%S')] Applying: ${label} ..."
    if ! psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$file"; then
        echo "ERROR: Failed to apply ${label}. Aborting." >&2
        exit 1
    fi
    echo "==> [$(date -u '+%H:%M:%S')] Done: ${label}"
}

# ---------------------------------------------------------------------------
# Retry loop: postgres may still be initialising when this script starts on
# the very first boot.  Give it up to 60 s before giving up.
# ---------------------------------------------------------------------------
MAX_RETRIES=20
RETRY_DELAY=3
attempt=0

until psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge "$MAX_RETRIES" ]; then
        echo "ERROR: Postgres not ready after $((MAX_RETRIES * RETRY_DELAY))s. Aborting." >&2
        exit 1
    fi
    echo "==> Waiting for Postgres to be ready (attempt ${attempt}/${MAX_RETRIES})..."
    sleep "$RETRY_DELAY"
done

echo "==> Postgres is ready."

# ---------------------------------------------------------------------------
# Step 0: Migration 001 — model_execution_log + agent_output_log tables.
#         Must run BEFORE prerequisites, which ALTER TABLE on these tables.
#         Safe to re-run — uses CREATE TABLE IF NOT EXISTS throughout.
# ---------------------------------------------------------------------------
run_sql \
    "migration 001 (model_execution_log, agent_output_log)" \
    "/docker-entrypoint-initdb.d/migrations/001_agent_execution_logs.sql"

# ---------------------------------------------------------------------------
# Step 1: Prerequisites (ENUMs, missing columns, agent output tables).
#         Safe to re-run — all statements use IF NOT EXISTS / DO $$ guards.
# ---------------------------------------------------------------------------
run_sql \
    "analytics prerequisites (ENUMs, missing columns, agent output tables)" \
    "/docker-entrypoint-initdb.d/scripts/000_analytics_prerequisites.sql"

# ---------------------------------------------------------------------------
# Step 2: Materialized views + refresh function.
#         Safe to re-run — every CREATE uses IF NOT EXISTS / OR REPLACE.
# ---------------------------------------------------------------------------
run_sql \
    "analytics materialized views" \
    "/docker-entrypoint-initdb.d/scripts/analytics_mvs.sql"

echo "==> Analytics setup complete."