#!/bin/bash
# Runs LAST (zzz > seed > init alphabetically in docker-entrypoint-initdb.d/)
# By this point these have already run:
#   init.sql, seedV2.sql, seed_analytics_extra.sql, seed_extra.sql
set -e

run_sql() {
    echo "==> [$(date -u '+%H:%M:%S')] $1"
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$2" \
      || { echo "ERROR: $1 failed"; exit 1; }
}

attempt=0
until psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1" >/dev/null 2>&1; do
    attempt=$((attempt+1)); [ $attempt -ge 20 ] && { echo "Postgres not ready"; exit 1; }
    echo "Waiting for Postgres ($attempt/20)..."; sleep 3
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

# ---------------------------------------------------------------------------
# Step 3: Refresh all materialized views with the full seed data.
# ---------------------------------------------------------------------------
echo "==> Refreshing analytics materialized views..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT refresh_analytics_mvs();" \
  || { echo "ERROR: MV refresh failed"; exit 1; }

echo "==> Analytics setup complete."