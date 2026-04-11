-- InnovaCX — Coverage Gap Fix
-- File: database/scripts/004_seed_coverage_apr2026.sql
--
-- PURPOSE
-- Fills the real MV coverage gaps identified for 2026 so that every active
-- employee has at least one ticket row in every month Jan–Apr 2026.
--
-- GAPS FILLED
--   ahmed  → 2026-04   (CX-CV001)
--   bilal  → 2026-01   (CX-CV002)
--   bilal  → 2026-04   (CX-CV003)
--   sameer → 2026-04   (CX-CV004)
--   yousef → 2026-04   (CX-CV005)
--   sarah  → 2026-04   (CX-CV006)
--
-- SAFE TO RE-RUN: uses ON CONFLICT (ticket_code) DO NOTHING.
--
-- APPLY ORDER
-- After: init.sql, 000–003 scripts, zzz_seedV2.sql
--
-- Command (apply while containers are running):
--   docker exec -i innovacx-db psql -U innovacx_admin -d complaints_db \
--     < database/scripts/004_seed_coverage_apr2026.sql

BEGIN;

-- STEP 1 — Insert 6 targeted coverage tickets

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

-- CX-CV001: ahmed → April 2026
(
    'CX-CV001',
    'Email archiving policy not applied – IT department',
    'Emails older than 90 days are not being archived per the retention policy. IT staff flagged missing archive folder.',
    'Complaint', 'Resolved', 'Medium',
    'Software',
    (SELECT id FROM departments WHERE name = 'IT'),
    (SELECT id FROM users WHERE email = 'customer1@innovacx.net'),
    (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
    '2026-04-05 09:00:00+00', '2026-04-05 09:18:00+00', '2026-04-05 09:45:00+00',
    '2026-04-05 17:30:00+00',
    '2026-04-06 09:00:00+00', '2026-04-07 09:00:00+00',
    FALSE, FALSE, '2026-04-05 09:00:00+00',
    -0.30, 'Negative', 'Medium',
    (SELECT id FROM departments WHERE name = 'IT'), 85.00,
    'Enable email archiving rule in Exchange admin center.',
    FALSE, FALSE
),

-- CX-CV002: bilal → January 2026
(
    'CX-CV002',
    'Printer driver conflict causing print queue lockup – Maintenance',
    'Maintenance office shared printer queue freezes after every third job. Driver conflict identified.',
    'Complaint', 'Resolved', 'Medium',
    'Hardware',
    (SELECT id FROM departments WHERE name = 'Maintenance'),
    (SELECT id FROM users WHERE email = 'customer2@innovacx.net'),
    (SELECT id FROM users WHERE email = 'bilal@innovacx.net'),
    '2026-01-08 10:00:00+00', '2026-01-08 10:20:00+00', '2026-01-08 10:50:00+00',
    '2026-01-08 18:00:00+00',
    '2026-01-09 10:00:00+00', '2026-01-10 10:00:00+00',
    FALSE, FALSE, '2026-01-08 10:00:00+00',
    -0.25, 'Negative', 'Medium',
    (SELECT id FROM departments WHERE name = 'Maintenance'), 82.00,
    'Reinstall latest vendor driver and clear print spooler.',
    FALSE, FALSE
),

-- CX-CV003: bilal → April 2026
(
    'CX-CV003',
    'Badge reader offline at maintenance bay entrance',
    'Access control badge reader at maintenance bay B2 not responding. Staff using manual log.',
    'Complaint', 'Resolved', 'High',
    'Security',
    (SELECT id FROM departments WHERE name = 'Maintenance'),
    (SELECT id FROM users WHERE email = 'customer3@innovacx.net'),
    (SELECT id FROM users WHERE email = 'bilal@innovacx.net'),
    '2026-04-06 08:30:00+00', '2026-04-06 08:45:00+00', '2026-04-06 09:10:00+00',
    '2026-04-06 15:00:00+00',
    '2026-04-07 08:30:00+00', '2026-04-08 08:30:00+00',
    FALSE, FALSE, '2026-04-06 08:30:00+00',
    -0.40, 'Negative', 'High',
    (SELECT id FROM departments WHERE name = 'Maintenance'), 88.00,
    'Replace reader firmware and re-pair with access control server.',
    FALSE, FALSE
),

-- CX-CV004: sameer → April 2026
(
    'CX-CV004',
    'Legal document management system slow search – Legal',
    'Document search in the legal DMS timing out on queries spanning more than 6 months of records.',
    'Complaint', 'Resolved', 'Medium',
    'Software',
    (SELECT id FROM departments WHERE name = 'Legal & Compliance'),
    (SELECT id FROM users WHERE email = 'customer1@innovacx.net'),
    (SELECT id FROM users WHERE email = 'sameer@innovacx.net'),
    '2026-04-04 11:00:00+00', '2026-04-04 11:22:00+00', '2026-04-04 11:55:00+00',
    '2026-04-04 19:00:00+00',
    '2026-04-05 11:00:00+00', '2026-04-06 11:00:00+00',
    FALSE, FALSE, '2026-04-04 11:00:00+00',
    -0.20, 'Neutral', 'Medium',
    (SELECT id FROM departments WHERE name = 'Legal & Compliance'), 80.00,
    'Add composite index on document_date and re-run ANALYZE on DMS database.',
    FALSE, FALSE
),

-- CX-CV005: yousef → April 2026
(
    'CX-CV005',
    'CCTV blind spot reported at east parking entrance – Security',
    'Camera at east parking entrance not covering the pedestrian gate. Security officer flagged gap.',
    'Complaint', 'Resolved', 'High',
    'Security',
    (SELECT id FROM departments WHERE name = 'Safety & Security'),
    (SELECT id FROM users WHERE email = 'customer2@innovacx.net'),
    (SELECT id FROM users WHERE email = 'yousef@innovacx.net'),
    '2026-04-03 07:30:00+00', '2026-04-03 07:48:00+00', '2026-04-03 08:15:00+00',
    '2026-04-03 14:00:00+00',
    '2026-04-04 07:30:00+00', '2026-04-05 07:30:00+00',
    FALSE, FALSE, '2026-04-03 07:30:00+00',
    -0.35, 'Negative', 'High',
    (SELECT id FROM departments WHERE name = 'Safety & Security'), 87.00,
    'Reposition camera arm 15° east and verify coverage via NVR live view.',
    FALSE, FALSE
),

-- CX-CV006: sarah → April 2026
(
    'CX-CV006',
    'Facilities booking calendar not syncing with Outlook – FM',
    'Facilities management room booking calendar shows stale data in Outlook. Double-bookings reported.',
    'Complaint', 'Resolved', 'Medium',
    'Software',
    (SELECT id FROM departments WHERE name = 'Facilities Management'),
    (SELECT id FROM users WHERE email = 'customer3@innovacx.net'),
    (SELECT id FROM users WHERE email = 'sarah@innovacx.net'),
    '2026-04-07 09:00:00+00', '2026-04-07 09:18:00+00', '2026-04-07 09:45:00+00',
    '2026-04-07 17:00:00+00',
    '2026-04-08 09:00:00+00', '2026-04-09 09:00:00+00',
    FALSE, FALSE, '2026-04-07 09:00:00+00',
    -0.25, 'Negative', 'Medium',
    (SELECT id FROM departments WHERE name = 'Facilities Management'), 83.00,
    'Reconnect calendar sync connector and force a full calendar re-publish.',
    FALSE, FALSE
)

ON CONFLICT (ticket_code) DO NOTHING;

-- STEP 2 — Refresh analytics materialized views

SELECT refresh_analytics_mvs();

-- STEP 3 — Verification: no employee×month gap should remain in 2026

DO $$
DECLARE
    v_cv_tickets  INTEGER;
    v_gaps        INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_cv_tickets
    FROM tickets WHERE ticket_code LIKE 'CX-CV%';

    -- Check: every active employee has MV rows for all 4 months Jan–Apr 2026
    SELECT COUNT(*) INTO v_gaps
    FROM (
        SELECT u.id, u.email, m.mo
        FROM users u
        CROSS JOIN (VALUES (1),(2),(3),(4)) AS m(mo)
        WHERE u.role = 'employee' AND u.is_active = TRUE
    ) required
    LEFT JOIN LATERAL (
        SELECT 1
        FROM mv_employee_daily med
        WHERE med.employee_id = required.id
          AND EXTRACT(YEAR  FROM med.created_month)::int = 2026
          AND EXTRACT(MONTH FROM med.created_month)::int = required.mo
        LIMIT 1
    ) has_data ON TRUE
    WHERE has_data IS NULL;

    RAISE NOTICE '--- 004_seed_coverage_apr2026 verification ---';
    RAISE NOTICE 'CX-CV tickets present : %  (expected 6)', v_cv_tickets;
    RAISE NOTICE 'Employee×month gaps in Jan–Apr 2026 : %  (expected 0)', v_gaps;

    IF v_cv_tickets < 6 THEN
        RAISE EXCEPTION 'CX-CV ticket count wrong: got %, expected 6', v_cv_tickets;
    END IF;

    IF v_gaps > 0 THEN
        RAISE EXCEPTION
            'Coverage gaps remain: % employee×month combinations still missing MV data. '
            'Check that the employees exist and their email matches the seed.', v_gaps;
    END IF;

    RAISE NOTICE 'Verification PASSED — all employees have Jan–Apr 2026 MV coverage.';
END $$;

COMMIT;
