-- Runtime utility script (no CREATE/ALTER DDL).
-- Ticket status triggers/functions are created in database/init.sql.
--
-- Optional manual status summary:
--   \set show_ticket_status 1
--   \i database/scripts/ticket_status.sql
--
-- If `show_ticket_status` is not set, this script does nothing (safe during init include).

\if :{?show_ticket_status}
SELECT status, COUNT(*) AS count
FROM tickets
GROUP BY status
ORDER BY count DESC;
\endif
