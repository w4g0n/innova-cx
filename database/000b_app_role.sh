#!/bin/sh
# Creates the innovacx_app role with the password from APP_DB_PASSWORD.
# Runs before init.sql (alphabetical order: 000b < i).
# Compatible with PostgreSQL 14 — no \getenv needed.
set -e

if [ -z "$APP_DB_PASSWORD" ]; then
  echo "ERROR: APP_DB_PASSWORD is not set" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'innovacx_app') THEN
    CREATE ROLE innovacx_app WITH LOGIN;
  END IF;
END \$\$;
ALTER ROLE innovacx_app PASSWORD '$APP_DB_PASSWORD';
SQL

echo "==> [000b_app_role.sh] innovacx_app role ready."
