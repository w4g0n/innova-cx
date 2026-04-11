-- InnovaCX — User Cleanup & Coverage Migration
-- File: database/scripts/003_user_cleanup_and_coverage.sql
--
-- STEP 1 — Rename operator@innova.cx → operator@innovacx.net
-- STEP 2 — Delete orphan innova.cx users (no tickets attached, safe)
-- STEP 3 — Add Lena & Talya coverage tickets (Jan/Mar/Apr 2026)
-- STEP 4 — Refresh analytics MVs
--
-- SAFE TO RE-RUN: all statements are idempotent.
--
-- Command:
--   docker exec -i innovacx-db psql -U innovacx_admin -d complaints_db \
--     < database/scripts/003_user_cleanup_and_coverage.sql


BEGIN;



-- STEP 1 — Rename operator email domain


UPDATE users
SET email = 'operator@innovacx.net'
WHERE email = 'operator@innova.cx'
  AND NOT EXISTS (
    SELECT 1 FROM users WHERE email = 'operator@innovacx.net'
  );

UPDATE public.ticket_updates
SET message = REPLACE(message, 'operator@innova.cx', 'operator@innovacx.net')
WHERE message LIKE '%operator@innova.cx%';



-- STEP 2 — Delete orphan innova.cx duplicate users (no tickets attached)


DELETE FROM users
WHERE email LIKE '%@innova.cx'
  AND NOT EXISTS (
    SELECT 1 FROM tickets t
    WHERE t.assigned_to_user_id = users.id
       OR t.created_by_user_id  = users.id
  );



-- STEP 3 — Lena & Talya coverage tickets
-- Uses the exact same column list as seed_analytics_extra.sql (27 columns).


INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, status, priority,
  asset_type, department_id, created_by_user_id, assigned_to_user_id,
  created_at, assigned_at, first_response_at, resolved_at,
  respond_due_at, resolve_due_at,
  respond_breached, resolve_breached,
  priority_assigned_at,
  sentiment_score, sentiment_label,
  model_priority, model_department_id, model_confidence, model_suggestion,
  human_overridden, is_recurring
)
VALUES

-- CX-LT001: Lena — January 2026
('CX-LT001', 'Network switch intermittent failures – HR floor',
 'HR floor network switch dropping connections every few hours. Staff unable to access shared drives.',
 'Complaint', 'Resolved', 'High',
 'Networking', (SELECT id FROM departments WHERE name='HR'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='lena@innovacx.net'),
 '2026-01-12 08:00:00+00', '2026-01-12 08:15:00+00', '2026-01-12 08:45:00+00',
 '2026-01-12 16:00:00+00',
 '2026-01-13 08:00:00+00', '2026-01-14 08:00:00+00',
 FALSE, FALSE, '2026-01-12 08:00:00+00',
 -0.45, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='HR'), 87.00,
 'Replace faulty switch module and test failover path.',
 FALSE, FALSE),

-- CX-LT002: Lena — April 2026
('CX-LT002', 'VoIP handsets not registering after firmware update – HR',
 'HR VoIP handsets lost registration after automated firmware push. Calls routing to voicemail.',
 'Complaint', 'Resolved', 'Medium',
 'Telephony', (SELECT id FROM departments WHERE name='HR'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='lena@innovacx.net'),
 '2026-04-02 09:00:00+00', '2026-04-02 09:20:00+00', '2026-04-02 09:50:00+00',
 '2026-04-02 17:00:00+00',
 '2026-04-03 09:00:00+00', '2026-04-04 09:00:00+00',
 FALSE, FALSE, '2026-04-02 09:00:00+00',
 -0.30, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='HR'), 83.00,
 'Roll back firmware on affected handsets; re-register SIP accounts.',
 FALSE, FALSE),

-- CX-LT003: Talya — January 2026
('CX-LT003', 'Leasing portal login errors – tenant portal',
 'Tenants unable to log in to the leasing portal since the Sunday maintenance window.',
 'Complaint', 'Resolved', 'High',
 'Portal', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-01-20 10:00:00+00', '2026-01-20 10:18:00+00', '2026-01-20 10:45:00+00',
 '2026-01-20 17:00:00+00',
 '2026-01-21 10:00:00+00', '2026-01-22 10:00:00+00',
 FALSE, FALSE, '2026-01-20 10:00:00+00',
 -0.50, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Leasing'), 90.00,
 'Restore session token configuration from pre-maintenance backup.',
 FALSE, FALSE),

-- CX-LT004: Talya — March 2026
('CX-LT004', 'Lease document upload failing – admin portal',
 'Lease coordinators unable to upload PDF documents larger than 2 MB to the admin portal.',
 'Complaint', 'Resolved', 'Medium',
 'Portal', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-03-10 11:00:00+00', '2026-03-10 11:22:00+00', '2026-03-10 11:55:00+00',
 '2026-03-10 19:00:00+00',
 '2026-03-11 11:00:00+00', '2026-03-12 11:00:00+00',
 FALSE, FALSE, '2026-03-10 11:00:00+00',
 -0.25, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Leasing'), 80.00,
 'Increase upload limit in portal config and test with sample 5 MB PDF.',
 FALSE, FALSE),

-- CX-LT005: Talya — April 2026
('CX-LT005', 'Rental agreement template missing clauses – new template',
 'New rental agreement template is missing the early termination and renewal clauses.',
 'Complaint', 'Resolved', 'Medium',
 'Documentation', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-04-03 08:30:00+00', '2026-04-03 08:48:00+00', '2026-04-03 09:15:00+00',
 '2026-04-03 17:00:00+00',
 '2026-04-04 08:30:00+00', '2026-04-05 08:30:00+00',
 FALSE, FALSE, '2026-04-03 08:30:00+00',
 -0.20, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Leasing'), 78.00,
 'Reinstate missing clauses from approved template version 2.1.',
 FALSE, FALSE)

ON CONFLICT (ticket_code) DO NOTHING;



-- STEP 4 — Refresh analytics MVs


SELECT refresh_analytics_mvs();



-- VERIFICATION


DO $$
DECLARE
    v_operator_ok    BOOLEAN;
    v_bad_users      INTEGER;
    v_lt_tickets     INTEGER;
    v_lena_months    INTEGER;
    v_talya_months   INTEGER;
BEGIN
    SELECT EXISTS(SELECT 1 FROM users WHERE email='operator@innovacx.net' AND role='operator')
    INTO v_operator_ok;

    SELECT COUNT(*) INTO v_bad_users
    FROM users
    WHERE email LIKE '%@innova.cx'
      AND NOT EXISTS (
        SELECT 1 FROM tickets t
        WHERE t.assigned_to_user_id = users.id OR t.created_by_user_id = users.id
      );

    SELECT COUNT(*) INTO v_lt_tickets
    FROM tickets WHERE ticket_code LIKE 'CX-LT%';

    SELECT COUNT(DISTINCT created_month) INTO v_lena_months
    FROM mv_employee_daily
    WHERE employee_id = (SELECT id FROM users WHERE email='lena@innovacx.net')
      AND created_month >= '2026-01-01';

    SELECT COUNT(DISTINCT created_month) INTO v_talya_months
    FROM mv_employee_daily
    WHERE employee_id = (SELECT id FROM users WHERE email='talya@innovacx.net')
      AND created_month >= '2026-01-01';

    RAISE NOTICE '--- 003_user_cleanup_and_coverage verification ---';
    RAISE NOTICE 'operator@innovacx.net exists : %  (expected TRUE)', v_operator_ok;
    RAISE NOTICE 'Orphan innova.cx users remain : %  (expected 0)',    v_bad_users;
    RAISE NOTICE 'CX-LT tickets inserted        : %  (expected 5)',    v_lt_tickets;
    RAISE NOTICE 'Lena 2026 MV months           : %  (expected 4)',    v_lena_months;
    RAISE NOTICE 'Talya 2026 MV months          : %  (expected 4)',    v_talya_months;

    IF v_lt_tickets < 5 THEN
        RAISE EXCEPTION 'CX-LT ticket count wrong: got %, expected 5', v_lt_tickets;
    END IF;

    RAISE NOTICE 'Verification complete.';
END $$;


COMMIT;
