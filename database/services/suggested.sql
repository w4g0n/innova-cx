-- Runtime utility script (no CREATE/ALTER DDL).
-- Suggested-resolution schema is created in database/init.sql.
--
-- Optional manual analytics query:
--   \set suggested_stats 1
--   \i database/services/suggested.sql
--
-- If `suggested_stats` is not set, this script does nothing (safe during init include).

\if :{?suggested_stats}
SELECT
  decision,
  COUNT(*) AS count
FROM ticket_resolution_feedback
GROUP BY decision
ORDER BY count DESC;
\endif
