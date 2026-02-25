-- Runtime utility script (no CREATE/ALTER DDL).
-- The function `compute_is_recurring_ticket(...)` is created in database/init.sql.
--
-- Usage (manual run with parameters):
--   \set user_id  '00000000-0000-0000-0000-000000000000'
--   \set subject  'Air conditioning not working'
--   \set details  'AC stopped cooling in office area'
--   \i database/scripts/is_recurring.sql
--
-- If no params are provided, this script does nothing (safe during init include).

\if :{?user_id}
SELECT compute_is_recurring_ticket(
  :'user_id'::uuid,
  COALESCE(:'subject', ''),
  COALESCE(:'details', '')
) AS is_recurring;

-- Optional visibility query: show similar recent tickets for the same user.
SELECT
  ticket_code,
  subject,
  created_at,
  status,
  priority
FROM tickets
WHERE created_by_user_id = :'user_id'::uuid
  AND created_at >= now() - interval '180 days'
ORDER BY created_at DESC
LIMIT 20;
\endif
