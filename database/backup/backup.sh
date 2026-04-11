#!/bin/sh

# InnovaCX — Daily Database Backup

# Produces: /backups/YYYY-MM-DD_HH-MM-SS.dump.gz.gpg
#
# Flow:
#   1. pg_dump (plain format) → temp file   [exit code checked explicitly]
#   2. gzip compression       → temp file   [size checked]
#   3. gpg symmetric AES-256  → final .dump.gz.gpg file
#   4. temp files deleted
#
# Why two steps instead of a pipeline:
#   A pipe (pg_dump | gzip | gpg) cannot detect pg_dump failure reliably —
#   gpg writes a valid-looking file even when its input is empty, causing
#   silent corrupt backups that appear to succeed. Two steps with explicit
#   exit-code and size checks prevent this entirely.
#
# Connection note:
#   pg_dump connects as innovacx_app (the runtime role) over TCP.
#   pg_hba.conf blocks innovacx_admin from TCP — innovacx_app is allowed.
#   innovacx_app has SELECT on all tables, which is sufficient for pg_dump.
#
# Required env vars (from docker-compose / .env):
#   APP_DB_USER         — runtime role (innovacx_app)
#   APP_DB_PASSWORD     — runtime role password
#   POSTGRES_DB         — database name
#   BACKUP_PASSPHRASE   — encryption passphrase (never logged)
#   BACKUP_RETAIN_DAYS  — how many days of backups to keep (default: 14)


set -e


# 1. Validate required env vars

: "${APP_DB_USER:?APP_DB_USER must be set}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${BACKUP_PASSPHRASE:?BACKUP_PASSPHRASE must be set}"

BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"
BACKUP_DIR="/backups"
TIMESTAMP="$(date -u '+%Y-%m-%d_%H-%M-%S')"
TEMP_DUMP="/tmp/backup_$$.dump"
BACKUP_FILE="${BACKUP_DIR}/${TIMESTAMP}.dump.gz.gpg"
PG_HOST="${PG_HOST:-postgres}"
PG_PORT="${PG_PORT:-5432}"

mkdir -p "${BACKUP_DIR}"

echo "[backup] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — starting backup of '${POSTGRES_DB}' on ${PG_HOST}:${PG_PORT}"

# Cleanup temp file on exit (covers both success and error paths)
trap 'rm -f "${TEMP_DUMP}"' EXIT


# 2. Step 1: pg_dump to a temp file
#    -Fc  : custom format (most flexible for pg_restore)
#    Connects as APP_DB_USER (innovacx_app) — allowed by pg_hba.conf over TCP.
#    Exit code is captured explicitly. If pg_dump fails, the script stops here
#    and never produces an encrypted file, preventing silent corrupt backups.

export PGPASSWORD="${APP_DB_PASSWORD}"

echo "[backup] running pg_dump..."

pg_dump \
    --host="${PG_HOST}" \
    --port="${PG_PORT}" \
    --username="${APP_DB_USER}" \
    --dbname="${POSTGRES_DB}" \
    --format=custom \
    --no-password \
    --file="${TEMP_DUMP}"

DUMP_EXIT=$?
unset PGPASSWORD

if [ "${DUMP_EXIT}" -ne 0 ]; then
    echo "[backup] ERROR: pg_dump failed with exit code ${DUMP_EXIT}" >&2
    exit 1
fi

# Verify dump file is non-empty (a zero-byte dump means something went wrong)
if [ ! -s "${TEMP_DUMP}" ]; then
    echo "[backup] ERROR: pg_dump produced an empty file — aborting" >&2
    exit 1
fi

DUMP_SIZE=$(du -sh "${TEMP_DUMP}" | cut -f1)
echo "[backup] pg_dump succeeded. Raw dump size: ${DUMP_SIZE}"


# 3. Step 2: compress + encrypt the dump file
#    gzip first (--compress-algo none in gpg avoids double-compression).
#    Passphrase passed via file descriptor 3 to keep it out of process list.

echo "[backup] compressing and encrypting..."

gzip --stdout "${TEMP_DUMP}" \
  | gpg \
      --batch \
      --yes \
      --symmetric \
      --cipher-algo AES256 \
      --compress-algo none \
      --passphrase-fd 3 \
      --output "${BACKUP_FILE}" \
      3<<EOF
${BACKUP_PASSPHRASE}
EOF


# 4. Final size check on the encrypted file
#    GPG will always write some bytes (headers) even on empty input, so we
#    enforce a minimum size of 10KB to catch near-empty encryptions.

if [ ! -s "${BACKUP_FILE}" ]; then
    echo "[backup] ERROR: encrypted backup file missing or empty: ${BACKUP_FILE}" >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

ACTUAL_BYTES=$(wc -c < "${BACKUP_FILE}")
if [ "${ACTUAL_BYTES}" -lt 10240 ]; then
    echo "[backup] ERROR: encrypted backup is suspiciously small (${ACTUAL_BYTES} bytes) — dump may be corrupt. Deleting." >&2
    rm -f "${BACKUP_FILE}"
    exit 1
fi

FILESIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)
echo "[backup] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — backup complete: ${BACKUP_FILE} (${FILESIZE})"


# 5. Prune backups older than BACKUP_RETAIN_DAYS

find "${BACKUP_DIR}" -name "*.dump.gz.gpg" -mtime "+${BACKUP_RETAIN_DAYS}" -type f | while read -r old_file; do
    echo "[backup] pruning old backup: ${old_file}"
    rm -f "${old_file}"
done

echo "[backup] retention: kept last ${BACKUP_RETAIN_DAYS} days of backups"
echo "[backup] done."
