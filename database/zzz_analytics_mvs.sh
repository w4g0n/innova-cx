#!/bin/bash
# zzz_analytics_mvs.sh
# Runs AFTER init.sql (files execute alphabetically — "zzz" ensures last).
# Step 1: applies prerequisite columns/tables/ENUMs that init.sql seeds depend on
#         but that 001_agent_execution_logs.sql did not create in its original form.
# Step 2: applies the materialized views and refresh function.
set -e

echo "==> Applying analytics prerequisites (ENUMs, missing columns, agent output tables)..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/000_analytics_prerequisites.sql
echo "==> Prerequisites applied."

echo "==> Applying analytics materialized views..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/analytics_mvs.sql
echo "==> Analytics MVs applied successfully."