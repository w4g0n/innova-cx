-- Sample inserts for department_routing table
-- Covers confident model routes and non-confident manager overrides.

WITH sample AS (
  SELECT
    ROW_NUMBER() OVER () AS rn,
    v.suggested_department,
    v.confidence_score,
    v.is_confident,
    v.final_department,
    v.routed_by,
    v.manager_id,
    v.created_at,
    v.updated_at
  FROM (
  VALUES
    -- confident, finalized by model
    (
      'IT',
      93.40::numeric,
      TRUE,
      'IT',
      'model',
      NULL::uuid,
      now() - interval '9 days',
      now() - interval '9 days'
    ),
    (
      'Facilities',
      88.10::numeric,
      TRUE,
      'Facilities',
      'model',
      NULL::uuid,
      now() - interval '6 days',
      now() - interval '6 days'
    ),
    -- non-confident, still pending manager review
    (
      'HR',
      64.30::numeric,
      FALSE,
      NULL,
      NULL,
      NULL::uuid,
      now() - interval '2 days',
      now() - interval '2 days'
    ),
    (
      'Security',
      58.90::numeric,
      FALSE,
      NULL,
      NULL,
      NULL::uuid,
      now() - interval '26 hours',
      now() - interval '26 hours'
    ),
    -- non-confident, manager override examples
    (
      'IT',
      61.80::numeric,
      FALSE,
      'Operations',
      'manager',
      (SELECT u.id FROM users u WHERE u.role = 'manager' ORDER BY u.created_at LIMIT 1),
      now() - interval '4 days',
      now() - interval '4 days' + interval '2 hours'
    ),
    (
      'Facilities',
      67.00::numeric,
      FALSE,
      'Security',
      'manager',
      (SELECT u.id FROM users u WHERE u.role = 'manager' ORDER BY u.created_at DESC LIMIT 1),
      now() - interval '1 day',
      now() - interval '20 hours'
    ) v(
      suggested_department,
      confidence_score,
      is_confident,
      final_department,
      routed_by,
      manager_id,
      created_at,
      updated_at
    )
),
tickets_ranked AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY created_at DESC, id) AS rn
  FROM tickets
),
ticket_count AS (
  SELECT COUNT(*) AS cnt FROM tickets_ranked
)
INSERT INTO department_routing (
  ticket_id,
  suggested_department,
  confidence_score,
  is_confident,
  final_department,
  routed_by,
  manager_id,
  created_at,
  updated_at
)
SELECT
  tr.id AS ticket_id,
  s.suggested_department,
  s.confidence_score,
  s.is_confident,
  s.final_department,
  s.routed_by,
  s.manager_id,
  s.created_at,
  s.updated_at
FROM sample s
JOIN ticket_count tc ON tc.cnt > 0
JOIN tickets_ranked tr
  ON tr.rn = ((s.rn - 1) % tc.cnt) + 1;
