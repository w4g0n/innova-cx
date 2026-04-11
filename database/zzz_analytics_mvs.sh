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


# Step 0: All numbered migrations in order.
#         init.sql covers the base schema; migrations add tables/columns that
#         analytics_mvs.sql depends on (e.g. suggested_resolution_usage,
#         pipeline_executions, pipeline_stage_events).
#         Safe to re-run — every file uses CREATE TABLE/INDEX IF NOT EXISTS.

for migration in \
    001_agent_execution_logs \
    002_ticket_messages \
    003_routing_review_queue \
    004_ticket_status_slim \
    005_department_routing \
    006_seed_department_routing \
    007_ticket_priority_nullable \
    008_pipeline_event_logging \
    009_pipeline_queue \
    010_pipeline_queue_failure_detail \
    011_review_agent \
    012_training_loop \
    013_suggested_resolution_usage_employee_fields \
    014_drop_ticket_resolution_feedback \
    015_learning_actor_roles \
    016_learning_record_views_and_seed \
    017_ticket_type_nullable \
; do
    migration_file="/docker-entrypoint-initdb.d/migrations/${migration}.sql"
    if [ -f "$migration_file" ]; then
        run_sql "migration ${migration}" "$migration_file"
    else
        echo "==> [$(date -u '+%H:%M:%S')] Skipping missing migration: ${migration}.sql"
    fi
done


# Step 1: Prerequisites (ENUMs, missing columns, agent output tables).
#         Safe to re-run — all statements use IF NOT EXISTS / DO $$ guards.

run_sql \
    "analytics prerequisites (ENUMs, missing columns, agent output tables)" \
    "/docker-entrypoint-initdb.d/scripts/000_analytics_prerequisites.sql"


# Step 2: Materialized views + refresh function.
#         Safe to re-run — every CREATE uses IF NOT EXISTS / OR REPLACE.

run_sql \
    "analytics materialized views" \
    "/docker-entrypoint-initdb.d/scripts/analytics_mvs.sql"


# Step 3: Refresh all materialized views with the full seed data.

echo "==> Refreshing analytics materialized views..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT refresh_analytics_mvs();" \
  || { echo "ERROR: MV refresh failed"; exit 1; }

echo "==> Analytics setup complete."