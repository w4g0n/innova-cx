#!/bin/sh
# =============================================================================
# InnovaCX Backup Scheduler
# =============================================================================
# Pure POSIX shell loop — no cron daemon, no special Linux capabilities.
# Runs inside an unprivileged Docker container without any permission issues.
#
# Schedule (UTC):
#   Daily backup     — runs when hour=02 and minute=00
#   Weekly restore   — runs when weekday=0 (Sunday), hour=03, minute=00
#
# The loop sleeps 50 seconds between checks to stay close to the target
# minute without burning CPU. A "already ran" guard file prevents the
# same job from firing twice within the same minute if the check happens
# to straddle a minute boundary.
# =============================================================================

echo "[scheduler] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — backup scheduler started"
echo "[scheduler] backup schedule  : daily at 02:00 UTC"
echo "[scheduler] restore schedule : every Sunday at 03:00 UTC"

LAST_BACKUP_RUN=""
LAST_RESTORE_RUN=""

while true; do
    # Current UTC time components
    HOUR=$(date -u '+%H')
    MIN=$(date -u '+%M')
    DOW=$(date -u '+%w')   # 0 = Sunday
    TODAY=$(date -u '+%Y-%m-%d')

    # ── Daily backup at 02:00 UTC ────────────────────────────────────────────
    if [ "${HOUR}" = "02" ] && [ "${MIN}" = "00" ]; then
        if [ "${LAST_BACKUP_RUN}" != "${TODAY}" ]; then
            echo "[scheduler] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — triggering daily backup"
            /usr/local/bin/backup.sh
            LAST_BACKUP_RUN="${TODAY}"
        fi
    fi

    # ── Weekly restore test: Sunday at 03:00 UTC ─────────────────────────────
    if [ "${DOW}" = "0" ] && [ "${HOUR}" = "03" ] && [ "${MIN}" = "00" ]; then
        if [ "${LAST_RESTORE_RUN}" != "${TODAY}" ]; then
            echo "[scheduler] $(date -u '+%Y-%m-%dT%H:%M:%SZ') — triggering weekly restore test"
            /usr/local/bin/restore_test.sh
            LAST_RESTORE_RUN="${TODAY}"
        fi
    fi

    sleep 50
done
