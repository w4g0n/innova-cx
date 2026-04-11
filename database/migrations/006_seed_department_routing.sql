-- Migration 006: seed_department_routing
-- Demo data for the AI Routing Review Queue tab.
-- All ticket codes verified to exist in init.sql.
-- Run after: 004_ticket_status_slim, 005_department_routing


DO $$
DECLARE
  -- departments
  d_facilities  UUID := (SELECT id FROM departments WHERE name = 'Facilities Management' LIMIT 1);
  d_legal       UUID := (SELECT id FROM departments WHERE name = 'Legal & Compliance'    LIMIT 1);
  d_safety      UUID := (SELECT id FROM departments WHERE name = 'Safety & Security'     LIMIT 1);
  d_hr          UUID := (SELECT id FROM departments WHERE name = 'HR'                    LIMIT 1);
  d_maintenance UUID := (SELECT id FROM departments WHERE name = 'Maintenance'           LIMIT 1);
  d_it          UUID := (SELECT id FROM departments WHERE name = 'IT'                    LIMIT 1);

  -- ticket IDs — all verified present in init.sql
  t_m54   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M54'  LIMIT 1);
  t_m52   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M52'  LIMIT 1);
  t_m53   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M53'  LIMIT 1);
  t_m51   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M51'  LIMIT 1);
  t_4725  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4725' LIMIT 1);
  t_4630  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4630' LIMIT 1);
  t_3862  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-3862' LIMIT 1);
  t_4780  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4780' LIMIT 1);
  t_2011  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-2011' LIMIT 1);

  -- first manager in the system for already-decided rows
  mgr UUID := (SELECT u.id FROM users u WHERE u.role = 'manager' ORDER BY u.created_at LIMIT 1);

BEGIN

  IF EXISTS (SELECT 1 FROM department_routing LIMIT 1) THEN
    RAISE NOTICE 'department_routing already has rows — skipping seed.';
    RETURN;
  END IF;

  -- PENDING (low confidence, awaiting manager decision)

  INSERT INTO department_routing
    (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id)
  VALUES
    -- 42% → Facilities Management
    (t_m54,  'Facilities Management', 42.30, FALSE, NULL, NULL, NULL),

    -- 38% → Safety & Security
    (t_m52,  'Safety & Security',     38.10, FALSE, NULL, NULL, NULL),

    -- 55% → IT  (below 70% threshold)
    (t_4725, 'IT',                    55.80, FALSE, NULL, NULL, NULL),

    -- 48% → Legal & Compliance
    (t_4630, 'Legal & Compliance',    48.60, FALSE, NULL, NULL, NULL),

    -- 61% → HR  (still below threshold)
    (t_2011, 'HR',                    61.20, FALSE, NULL, NULL, NULL);

  -- CONFIRMED (manager agreed with AI suggestion)

  INSERT INTO department_routing
    (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id, updated_at)
  VALUES
    -- Manager confirmed: Maintenance → Maintenance
    (t_m51,  'Maintenance',           44.90, FALSE, 'Maintenance',         'manager', mgr, now() - INTERVAL '2 hours'),

    -- Manager confirmed: IT → IT
    (t_4780, 'IT',                    58.30, FALSE, 'IT',                  'manager', mgr, now() - INTERVAL '6 hours');

  -- OVERRIDDEN (manager picked a different department)

  INSERT INTO department_routing
    (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id, updated_at)
  VALUES
    -- AI said Maintenance (52%), manager overrode to Facilities Management
    (t_m53,  'Maintenance',           52.40, FALSE, 'Facilities Management', 'manager', mgr, now() - INTERVAL '5 hours'),

    -- AI said HR (45%), manager overrode to Legal & Compliance
    (t_3862, 'HR',                    45.00, FALSE, 'Legal & Compliance',    'manager', mgr, now() - INTERVAL '1 day');

  RAISE NOTICE 'department_routing seed complete — 5 pending, 2 confirmed, 2 overridden.';

END $$;