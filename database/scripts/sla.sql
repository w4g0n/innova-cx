-- Runtime utility script (no CREATE/ALTER DDL).
-- SLA schema + functions are created in database/init.sql.
--
-- Optional manual run:
--   \set run_sla 1
--   \i database/scripts/sla.sql
--
-- If `run_sla` is not set, this script does nothing (safe during init include).

\if :{?run_sla}
SELECT apply_ticket_sla_policies() AS sla_result;
\endif
