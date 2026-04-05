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
  CASE WHEN used THEN 'accepted' ELSE 'declined_custom' END AS decision,
  COUNT(*) AS count
FROM suggested_resolution_usage
GROUP BY decision
ORDER BY count DESC;
\endif
