#!/bin/sh
# =============================================================================
# InnovaCX — Restore Test (Weekly)
# =============================================================================
# Purpose:
#   Verify that the most recent encrypted backup can actually be decrypted
#   and restored without errors. Uses an ISOLATED test database that is
#   DROPPED at the end. Production data is NEVER touched.
#
# Flow:
#   1. Find most recent .dump.gz.gpg in /backups
#   2. Decrypt + decompress to a temp file
#   3. Create an isolated test database (restore_test_db) as superuser
#   4. pg_restore into restore_test_db
#   5. Run a structural integrity check query
#   6. Log result (PASS / FAIL) to /backups/restore_test.log
#   7. Drop restore_test_db regardless of outcome (cleanup)
#   8. Remove temp file
#
# Connection note:
#   All operations use POSTGRES_USER (innovacx_admin / superuser).
#   pg_hba.conf allows innovacx_admin from the Docker internal network
#   (172.16.0.0/12) with md5 — this is the targeted backup exception.
#   innovacx_app is NOT used here: pg_restore runs with --no-privileges
#   so no GRANTs exist on the test DB — only the owner can SELECT.
#
# IMPORTANT:
#   This script NEVER touches the production database (complaints_db).
# =============================================================================

set -e

# ---------------------------------------------------------------------------
# 1. Validate required env vars
# ---------------------------------------------------------------------------
: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}"
: "${APP_DB_USER:?APP_DB_USER must be set}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${BACKUP_PASSPHRASE:?BACKUP_PASSPHRASE must be set}"

BACKUP_DIR="/backups"
LOG_FILE="${BACKUP_DIR}/restore_test.log"
TEMP_DUMP="/tmp/restore_test_$$.dump"
TEST_DB="restore_test_db"
PG_HOST="${PG_HOST:-postgres}"
PG_PORT="${PG_PORT:-5432}"

# Helper: append a timestamped line to the log and echo it
log() {
    line="[restore-test] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — $1"
    echo "${line}"
    echo "${line}" >> "${LOG_FILE}"
}

# Helper: guaranteed cleanup regardless of success or failure
cleanup() {
    export PGPASSWORD="${POSTGRES_PASSWORD}"
    psql \
        --host="${PG_HOST}" \
        --port="${PG_PORT}" \
        --username="${POSTGRES_USER}" \
        --dbname="postgres" \
        --no-password \
        -c "DROP DATABASE IF EXISTS ${TEST_DB};" \
        >/dev/null 2>&1 || true
    unset PGPASSWORD
    rm -f "${TEMP_DUMP}"
}

trap cleanup EXIT

log "========================================================"
log "Restore test starting"

# ---------------------------------------------------------------------------
# 2. Find the most recent backup file
# ---------------------------------------------------------------------------
LATEST_BACKUP=$(find "${BACKUP_DIR}" -name "*.dump.gz.gpg" -type f | sort | tail -1)

if [ -z "${LATEST_BACKUP}" ]; then
    log "FAIL — no backup files found in ${BACKUP_DIR}"
    exit 1
fi

log "using backup file: ${LATEST_BACKUP}"

# ---------------------------------------------------------------------------
# 3. Decrypt and decompress to a temp file
# ---------------------------------------------------------------------------
log "decrypting and decompressing..."

gpg \
    --batch \
    --yes \
    --decrypt \
    --passphrase-fd 3 \
    --output - \
    "${LATEST_BACKUP}" \
    3<<EOF | gunzip > "${TEMP_DUMP}"
${BACKUP_PASSPHRASE}
EOF

if [ ! -s "${TEMP_DUMP}" ]; then
    log "FAIL — decrypted/decompressed dump is empty or missing"
    exit 1
fi

log "decryption successful. Temp dump size: $(du -sh "${TEMP_DUMP}" | cut -f1)"

# ---------------------------------------------------------------------------
# 4. Create the isolated test database (requires superuser)
# ---------------------------------------------------------------------------
log "creating isolated test database '${TEST_DB}'..."

export PGPASSWORD="${POSTGRES_PASSWORD}"

psql \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="postgres" \
    --no-password \
    -c "DROP DATABASE IF EXISTS ${TEST_DB};" \
    >/dev/null

psql \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="postgres" \
    --no-password \
    -c "CREATE DATABASE ${TEST_DB} OWNER ${POSTGRES_USER};" \
    >/dev/null

log "test database created."

# ---------------------------------------------------------------------------
# 5. Restore into the isolated test database (requires superuser)
#    --no-privileges: skip GRANT/REVOKE (innovacx_app role may not exist here)
#    --no-owner: skip SET ROLE
#    --exit-on-error: fail fast on any restore error
# ---------------------------------------------------------------------------
log "running pg_restore into '${TEST_DB}'..."

pg_restore \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${TEST_DB}" \
    --no-password \
    --no-privileges \
    --no-owner \
    --exit-on-error \
    "${TEMP_DUMP}"

unset PGPASSWORD

log "pg_restore completed without errors."

# ---------------------------------------------------------------------------
# 6. Structural integrity verification
#    Runs as POSTGRES_USER (superuser/owner of restored tables).
#    Using APP_DB_USER here would fail with "permission denied" because
#    --no-privileges on pg_restore means no GRANTs were applied to the
#    test database — only the owner (innovacx_admin) can SELECT.
# ---------------------------------------------------------------------------
log "running integrity verification query..."

export PGPASSWORD="${POSTGRES_PASSWORD}"

VERIFY_RESULT=$(psql \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${TEST_DB}" \
    --no-password \
    --tuples-only \
    --no-align \
    -c "
SELECT
    (SELECT COUNT(*) FROM information_schema.tables
     WHERE table_schema = 'public'
       AND table_name IN (
           'tickets',
           'users',
           'departments',
           'model_execution_log',
           'pipeline_queue'
       )
    ) AS critical_tables_found,
    (SELECT COUNT(*) FROM tickets)     AS ticket_count,
    (SELECT COUNT(*) FROM users)       AS user_count,
    (SELECT COUNT(*) FROM departments) AS dept_count;
")

unset PGPASSWORD

log "verification result: ${VERIFY_RESULT}"

TABLES_FOUND=$(echo "${VERIFY_RESULT}" | tr '|' '\n' | head -1 | tr -d ' ')

if [ "${TABLES_FOUND}" = "5" ]; then
    log "PASS — all 5 critical tables present. Counts: ${VERIFY_RESULT}"
else
    log "FAIL — only ${TABLES_FOUND}/5 critical tables found after restore"
    exit 1
fi

log "restore test PASSED. Test database will be dropped by cleanup."
log "========================================================"
