#!/bin/bash
# =============================================================================
# Install custom pg_hba.conf into PGDATA
#
# PURPOSE:
#   Copies the project's pg_hba.conf (available at
#   /docker-entrypoint-initdb.d/pg_hba.conf because ./database is mounted
#   there) into $PGDATA so postgres uses it after init completes.
#
#   This replaces the file bind-mount + hba_file command-line approach, which
#   is unreliable on the self-hosted runner: Docker creates the mount-point
#   as a directory when the parent path (/etc/postgresql/) does not exist in
#   the postgres:14-alpine image.
#
# EXECUTION ORDER:
#   Runs first (000 prefix) so the custom pg_hba.conf is in place before any
#   subsequent init script triggers a postgres config reload.
# =============================================================================
set -e

SRC="/docker-entrypoint-initdb.d/pg_hba.conf"

if [ ! -f "$SRC" ]; then
    echo "ERROR: $SRC not found — cannot install pg_hba.conf"
    exit 1
fi

echo "==> [000_install_pg_hba.sh] Installing custom pg_hba.conf into $PGDATA"
cp "$SRC" "$PGDATA/pg_hba.conf"
echo "==> [000_install_pg_hba.sh] Done."
