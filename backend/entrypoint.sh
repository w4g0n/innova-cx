#!/bin/sh
# InnovaCX Backend Entrypoint
#
# Runs on every container start (fresh volumes AND restarts).
# All steps are fully idempotent — safe to run multiple times.
#
# SEQUENCE:
#   1. Wait for PostgreSQL to accept connections (belt-and-suspenders on top
#      of the Docker healthcheck — guards against slow cold starts)
#   2. Run schema migrations 001–003 via Python/psycopg2 using the admin URL
#      (CREATE TABLE, CREATE INDEX, INSERT — require superuser privileges)
#   3. Run backfill_employee_reports.py via the app URL (SELECT/INSERT/DELETE)
#   4. Start Uvicorn
#
# ENV VARS REQUIRED:
#   DATABASE_URL        — runtime app user  (innovacx_app)   — used by backfill + uvicorn
#   DATABASE_ADMIN_URL  — superuser         (innovacx_admin) — used by migrations only


set -e

echo "[entrypoint] === InnovaCX backend starting ==="
echo "[entrypoint] $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

#  Step 1: Wait for DB 
echo "[entrypoint] Waiting for PostgreSQL..."
python3 - << 'PYEOF'
import os, sys, time
import psycopg2

url = os.environ.get("DATABASE_ADMIN_URL") or os.environ.get("DATABASE_URL")
if not url:
    print("[entrypoint] ERROR: No DATABASE_URL or DATABASE_ADMIN_URL set", flush=True)
    sys.exit(1)

for attempt in range(1, 31):
    try:
        conn = psycopg2.connect(url, connect_timeout=3)
        conn.close()
        print(f"[entrypoint] PostgreSQL ready (attempt {attempt})", flush=True)
        break
    except Exception as e:
        print(f"[entrypoint] Attempt {attempt}/30: {e}", flush=True)
        time.sleep(3)
else:
    print("[entrypoint] ERROR: PostgreSQL not ready after 90s", flush=True)
    sys.exit(1)
PYEOF

# Step 2: Run migrations
echo "[entrypoint] Running schema migrations..."
python3 - << 'PYEOF'
import os, sys
import psycopg2

admin_url = os.environ.get("DATABASE_ADMIN_URL")
if not admin_url:
    print("[entrypoint] WARNING: DATABASE_ADMIN_URL not set — skipping migrations", flush=True)
    sys.exit(0)

# Migration files in the correct order
# Path: /app/database/scripts/ (mounted from ./database at build time)
migration_files = [
    "/app/database/scripts/001_employee_report_subtables.sql",
    "/app/database/scripts/002_cleanup_legacy_employee_reports.sql",
    "/app/database/scripts/003_user_cleanup_and_coverage.sql",
]

for path in migration_files:
    if not os.path.exists(path):
        print(f"[entrypoint] SKIP (not found): {path}", flush=True)
        continue

    filename = os.path.basename(path)
    print(f"[entrypoint] Running: {filename}", flush=True)

    with open(path, "r") as f:
        sql = f.read()

    try:
        conn = psycopg2.connect(admin_url)
        conn.autocommit = True   # let the SQL files manage their own BEGIN/COMMIT
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print(f"[entrypoint] OK: {filename}", flush=True)
    except Exception as e:
        print(f"[entrypoint] ERROR in {filename}: {e}", flush=True)
        # Migrations are idempotent — a non-fatal error (e.g. already-applied DDL)
        # should not block startup.
        try:
            conn.close()
        except Exception:
            pass

print("[entrypoint] Migrations complete.", flush=True)
PYEOF

# Step 3: Run backfill
echo "[entrypoint] Running employee report backfill..."
BACKFILL="/app/scripts/backfill_employee_reports.py"
if [ -f "$BACKFILL" ]; then
    python3 "$BACKFILL" || echo "[entrypoint] WARNING: Backfill had issues (see above) — continuing startup"
else
    echo "[entrypoint] WARNING: Backfill script not found at $BACKFILL — skipping"
fi

# Step 4: Start Uvicorn
echo "[entrypoint] Starting Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
