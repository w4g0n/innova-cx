-- Benchmark Test Data Cleanup

-- Removes all rows created by the E2E smoke suite.
-- Safe to re-run (DELETE with NOT EXISTS clauses not needed — simple deletes are idempotent
-- because the session IDs are unique UUIDs that only exist once).
--
-- The session_ids list is passed as a PostgreSQL array literal from the run_benchmark.sh script:
--
--   docker exec -i innovacx-db psql -U innovacx_user -d complaints_db \
--       -v session_ids="'{uuid1,uuid2,...}'" \
--       -f /tmp/cleanup.sql
--
-- Alternatively, to run manually with a hardcoded list:
--   \set session_ids '{uuid1,uuid2}'

BEGIN;

-- 1. Remove bot response logs (references sessions)
DELETE FROM bot_response_logs
WHERE session_id = ANY(:session_ids::uuid[]);

-- 2. Remove user chat logs (references sessions)
DELETE FROM user_chat_logs
WHERE session_id = ANY(:session_ids::uuid[]);

-- 3. Remove tickets created during the E2E benchmark
--    Identified by the [benchmark] marker in the description field.
--    Also scoped to the test session_ids via the session reference in user_chat_logs.
DELETE FROM tickets
WHERE description LIKE '%[benchmark]%';

-- 4. Remove sessions themselves
DELETE FROM sessions
WHERE session_id = ANY(:session_ids::uuid[]);

COMMIT;

-- Confirm what was cleaned
SELECT
    (SELECT COUNT(*) FROM sessions WHERE session_id = ANY(:session_ids::uuid[]))       AS remaining_sessions,
    (SELECT COUNT(*) FROM user_chat_logs WHERE session_id = ANY(:session_ids::uuid[])) AS remaining_chat_logs,
    (SELECT COUNT(*) FROM bot_response_logs WHERE session_id = ANY(:session_ids::uuid[])) AS remaining_bot_logs,
    (SELECT COUNT(*) FROM tickets WHERE description LIKE '%[benchmark]%')               AS remaining_benchmark_tickets;
