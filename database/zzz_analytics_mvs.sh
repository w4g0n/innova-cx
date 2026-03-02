#!/bin/bash
# zzz_analytics_mvs.sh
# Runs AFTER init.sql (files execute alphabetically — "zzz" ensures last).
# Applies the materialized views and refresh function so the manager
# analytics work immediately without any manual steps.
set -e

echo "==> Applying analytics materialized views..."
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/analytics_mvs.sql
echo "==> Analytics MVs applied successfully."
