-- InnovaCX — Presentation Seed
-- File: database/seeds/seed_presentation.sql
--
-- PURPOSE
--   Populate reroute_reference and rescore_reference so the Learning tab
--   (Quality Control → C) shows real correction records.
--   Then refresh all materialized views so every KPI/chart on the Operator
--   pages (Model Health + Quality Control) reflects the data that was already
--   inserted by seed_analytics_extra.sql.
--
-- PREREQUISITES (must already be applied before running this file)
--   1. init.sql
--   2. zzz_seedV2.sql   (or seed_extra.sql — users/departments/tickets)
--   3. analytics_mvs.sql  (creates MVs + refresh function)
--   4. seed_analytics_extra.sql  (tickets, sessions, model_execution_log,
--        sentiment_outputs, feature_outputs, suggested_resolution_usage,
--        approval_requests, user_chat_logs)
--
-- SAFE TO RE-RUN
--   All inserts use WHERE NOT EXISTS guards.
--   The final SELECT refresh_analytics_mvs() is idempotent.
--
-- HOW TO RUN
--   docker exec -i innovacx-db psql -U innovacx_admin -d complaints_db \
--     < database/seeds/seed_presentation.sql
--
-- REAL SCHEMA (confirmed from pipeline_queue_api.py _record_operator_corrections):
--
--   reroute_reference:
--     id UUID, ticket_id UUID, department TEXT,
--     original_dept TEXT, corrected_dept TEXT,
--     actor_role TEXT NOT NULL,   <- 'employee' | 'manager' | 'operator'
--     source_type TEXT
--
--   rescore_reference:
--     id UUID, ticket_id UUID, department TEXT,
--     original_priority TEXT, corrected_priority TEXT,
--     actor_role TEXT NOT NULL,   <- 'employee' | 'manager' | 'operator'
--     source_type TEXT

BEGIN;

-- SECTION 1: reroute_reference
-- Feeds: GET /operator/learning/reroute
-- actor_role NOT NULL: 'employee' | 'manager' | 'operator'
-- source_type matches SOURCE_LABEL map in QualityControl.jsx:
--   'manager_routing_review' | 'approval_rerouting' | 'operator_correction'

INSERT INTO reroute_reference (
    ticket_id,
    department,
    original_dept,
    corrected_dept,
    actor_role,
    source_type
)
SELECT
    t.id,
    v.dept,
    v.orig,
    v.corr,
    v.actor_role,
    v.src
FROM (VALUES
    -- REQ-5005: CX-J003 — Safety & Security → Facilities Management
    ('CX-J003',
     'Safety & Security',
     'Safety & Security',
     'Facilities Management',
     'manager',
     'manager_routing_review'),

    -- REQ-5007: CX-N003 — Facilities Management → Safety & Security
    ('CX-N003',
     'Facilities Management',
     'Facilities Management',
     'Safety & Security',
     'manager',
     'manager_routing_review'),

    -- REQ-5001: CX-F002 — HR → IT (employee requested)
    ('CX-F002',
     'HR',
     'HR',
     'IT',
     'employee',
     'approval_rerouting'),

    -- REQ-5003: CX-F008 — Safety & Security → IT (employee requested)
    ('CX-F008',
     'Safety & Security',
     'Safety & Security',
     'IT',
     'employee',
     'approval_rerouting'),

    -- REQ-5009: CX-S002 — Facilities Management → Maintenance (employee requested)
    ('CX-S002',
     'Facilities Management',
     'Facilities Management',
     'Maintenance',
     'employee',
     'approval_rerouting'),

    -- CX-G001 — Facilities Management → Maintenance (manager approved)
    ('CX-G001',
     'Facilities Management',
     'Facilities Management',
     'Maintenance',
     'manager',
     'manager_routing_review'),

    -- CX-D004 — Maintenance → Safety & Security (manager approved)
    ('CX-D004',
     'Maintenance',
     'Maintenance',
     'Safety & Security',
     'manager',
     'manager_routing_review'),

    -- CX-O002 — IT → Facilities Management (employee requested)
    ('CX-O002',
     'IT',
     'IT',
     'Facilities Management',
     'employee',
     'approval_rerouting'),

    -- CX-L001 — Maintenance → Facilities Management (operator override)
    ('CX-L001',
     'Maintenance',
     'Maintenance',
     'Facilities Management',
     'operator',
     'operator_correction')

) AS v(tc, dept, orig, corr, actor_role, src)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
    SELECT 1 FROM reroute_reference rr
    WHERE rr.ticket_id     = t.id
      AND rr.original_dept  = v.orig
      AND rr.corrected_dept = v.corr
);

-- SECTION 2: rescore_reference
-- Feeds: GET /operator/learning/rescore
-- actor_role NOT NULL: 'employee' | 'manager' | 'operator'
-- source_type matches SOURCE_LABEL map in QualityControl.jsx:
--   'approval_rescoring' | 'manager_review' | 'operator_correction'

INSERT INTO rescore_reference (
    ticket_id,
    department,
    original_priority,
    corrected_priority,
    actor_role,
    source_type
)
SELECT
    t.id,
    v.dept,
    v.orig_p,
    v.corr_p,
    v.actor_role,
    v.src
FROM (VALUES
    -- REQ-5002: CX-F005 — Medium → High (manager approved)
    ('CX-F005',
     'Safety & Security',
     'Medium', 'High',
     'manager',
     'approval_rescoring'),

    -- REQ-5006: CX-D004 — High → Critical (manager approved)
    ('CX-D004',
     'Maintenance',
     'High', 'Critical',
     'manager',
     'approval_rescoring'),

    -- REQ-5010: CX-F009 — High → Critical (manager approved)
    ('CX-F009',
     'Facilities Management',
     'High', 'Critical',
     'manager',
     'approval_rescoring'),

    -- REQ-5004: CX-F010 — Critical → High (employee requested)
    ('CX-F010',
     'Leasing',
     'Critical', 'High',
     'employee',
     'approval_rescoring'),

    -- REQ-5008: CX-O001 — Medium → Low (employee requested)
    ('CX-O001',
     'Facilities Management',
     'Medium', 'Low',
     'employee',
     'approval_rescoring'),

    -- CX-N004 — High → Critical (manager review)
    ('CX-N004',
     'Safety & Security',
     'High', 'Critical',
     'manager',
     'manager_review'),

    -- CX-J002 — High → Critical (manager review: data-loss risk)
    ('CX-J002',
     'IT',
     'High', 'Critical',
     'manager',
     'manager_review'),

    -- CX-G002 — Critical → High (operator correction post-resolution)
    ('CX-G002',
     'IT',
     'Critical', 'High',
     'operator',
     'operator_correction'),

    -- CX-S001 — High → Critical (manager review: health+safety risk)
    ('CX-S001',
     'Facilities Management',
     'High', 'Critical',
     'manager',
     'manager_review')

) AS v(tc, dept, orig_p, corr_p, actor_role, src)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
    SELECT 1 FROM rescore_reference rsc
    WHERE rsc.ticket_id          = t.id
      AND rsc.original_priority  = v.orig_p
      AND rsc.corrected_priority = v.corr_p
);

-- SECTION 3: Ensure priority_assigned_at is set for ALL tickets
-- mv_ticket_base uses COALESCE(priority_assigned_at, assigned_at, created_at)
-- for response_time_mins. NULL here produces NULL response times.
UPDATE tickets
SET priority_assigned_at = created_at
WHERE priority_assigned_at IS NULL;

-- SECTION 4: Backfill tickets.is_recurring from feature_outputs.raw_features
-- mv_feature_daily counts tickets.is_recurring = TRUE for recurring_count.
UPDATE tickets t
SET is_recurring = TRUE
FROM feature_outputs fo
WHERE fo.ticket_id  = t.id
  AND fo.is_current = TRUE
  AND (fo.raw_features->>'is_recurring')::boolean = TRUE
  AND t.is_recurring = FALSE;

-- SECTION 5: Ensure model_priority is set for all seeded tickets
-- QC Section B counts WHERE model_priority IS NOT NULL for total_with_model.
-- Guard against partial seed runs leaving model_priority NULL.
UPDATE tickets t
SET model_priority = t.priority::ticket_priority
WHERE t.model_priority IS NULL
  AND t.ticket_code IN (
    'CX-F001','CX-F002','CX-F003','CX-F004','CX-F005',
    'CX-F006','CX-F007','CX-F008','CX-F009','CX-F010',
    'CX-J001','CX-J002','CX-J003','CX-J004','CX-J005','CX-J006',
    'CX-D001','CX-D002','CX-D003','CX-D004',
    'CX-N001','CX-N002','CX-N003','CX-N004',
    'CX-O001','CX-O002','CX-O003',
    'CX-S001','CX-S002',
    'CX-G001','CX-G002',
    'CX-L001','CX-E001','CX-M001','CX-P001'
  );

-- SECTION 6: Add positive/neutral sessions and chat logs
-- Adds variety to Chatbot -> Sentiment at Escalation bar chart so all
-- three buckets (Negative, Neutral, Positive) render with bars.
INSERT INTO sessions (
    user_id, current_state, context, history,
    created_at, updated_at,
    bot_model_version, escalated_to_human, escalated_at, linked_ticket_id
)
SELECT
    (SELECT id FROM users WHERE email = v.email),
    'resolved',
    v.ctx::jsonb,
    v.hist::jsonb,
    v.ts::timestamptz,
    (v.ts::timestamptz + interval '15 minutes'),
    'chatbot-v2.1',
    v.escalated::boolean,
    CASE WHEN v.escalated::boolean
         THEN v.ts::timestamptz + interval '3 minutes'
         ELSE NULL END,
    NULL
FROM (VALUES
    ('customer1@innovacx.net',
     '{"last_intent":"inquiry","topic":"maintenance_schedule"}',
     '[{"role":"user","msg":"When is the next planned maintenance?"},{"role":"bot","msg":"Quarterly schedule shared."}]',
     '2026-02-28 10:00:00+00', 'false'),

    ('customer2@innovacx.net',
     '{"last_intent":"inquiry","topic":"parking_booking"}',
     '[{"role":"user","msg":"How do I reserve a parking spot?"},{"role":"bot","msg":"Booking link sent."}]',
     '2026-02-27 14:00:00+00', 'false'),

    ('customer3@innovacx.net',
     '{"last_intent":"inquiry","topic":"lease_renewal"}',
     '[{"role":"user","msg":"Can I renew my lease online?"},{"role":"bot","msg":"Yes, portal link provided."}]',
     '2026-02-15 09:00:00+00', 'false'),

    ('customer1@innovacx.net',
     '{"last_intent":"report_issue","asset":"Plumbing","type":"minor_leak"}',
     '[{"role":"user","msg":"Small drip under sink in room 204."},{"role":"bot","msg":"Logging ticket."}]',
     '2026-01-28 11:00:00+00', 'true'),

    ('customer2@innovacx.net',
     '{"last_intent":"request_confirmation","topic":"resolved_ticket"}',
     '[{"role":"user","msg":"AC seems fixed, can someone confirm?"},{"role":"bot","msg":"Escalating to confirm closure."}]',
     '2025-12-10 13:00:00+00', 'true')

) AS v(email, ctx, hist, ts, escalated)
WHERE NOT EXISTS (
    SELECT 1 FROM sessions s2
    WHERE s2.user_id    = (SELECT id FROM users WHERE email = v.email)
      AND s2.created_at = v.ts::timestamptz
);

INSERT INTO user_chat_logs (
    user_id, session_id, message,
    intent_detected, aggression_flag, aggression_score,
    created_at, sentiment_score, category, response_time_ms, ticket_id
)
SELECT
    (SELECT id FROM users WHERE email = v.email),
    s.session_id,
    v.msg,
    v.intent,
    FALSE,
    0.003,
    v.ts::timestamptz,
    v.sent,
    v.cat,
    v.resp_ms,
    NULL
FROM (VALUES
    ('customer1@innovacx.net', '2026-02-28 10:00:30+00',
     'When is the next planned maintenance window?',
     'inquiry', 0.35, 'General', 610),

    ('customer2@innovacx.net', '2026-02-27 14:00:30+00',
     'How do I reserve a visitor parking spot?',
     'inquiry', 0.28, 'Parking', 590),

    ('customer3@innovacx.net', '2026-02-15 09:00:30+00',
     'Can I renew my lease agreement online through the portal?',
     'inquiry', 0.42, 'Leasing', 600),

    ('customer1@innovacx.net', '2026-01-28 11:00:30+00',
     'There is a small drip under the sink in room 204 -- not urgent.',
     'report_issue', -0.05, 'Plumbing', 820),

    ('customer2@innovacx.net', '2025-12-10 13:00:30+00',
     'My AC issue seems resolved -- can a technician confirm before closing?',
     'request_confirmation', 0.22, 'HVAC', 750)

) AS v(email, ts, msg, intent, sent, cat, resp_ms)
JOIN sessions s
  ON s.user_id    = (SELECT id FROM users WHERE email = v.email)
 AND s.created_at = (
     SELECT created_at FROM sessions
     WHERE user_id = (SELECT id FROM users WHERE email = v.email)
     ORDER BY ABS(EXTRACT(EPOCH FROM (created_at - v.ts::timestamptz)))
     LIMIT 1
 )
WHERE NOT EXISTS (
    SELECT 1 FROM user_chat_logs ucl
    WHERE ucl.user_id = (SELECT id FROM users WHERE email = v.email)
      AND ucl.message  = v.msg
);

-- SECTION 7: Add routing agent execution log rows
-- QC B "AI Reroute Suggestion Rate" counts model_execution_log WHERE
-- agent_name = 'routing' AND status = 'success'.
-- Uses deterministic confidence values derived from created_at to avoid RANDOM().
INSERT INTO model_execution_log (
    ticket_id, agent_name, model_version, triggered_by,
    started_at, completed_at, status,
    input_token_count, output_token_count,
    inference_time_ms, confidence_score, error_flag, error_message,
    infra_metadata
)
SELECT
    t.id,
    'routing'::agent_name_type,
    'routing-v1.8',
    'ingest'::trigger_source,
    (t.created_at + interval '16 seconds')::timestamptz,
    (t.created_at + interval '20 seconds')::timestamptz,
    'success'::execution_status,
    428, 24,
    4100,
    ROUND((0.72 + (EXTRACT(EPOCH FROM t.created_at)::numeric % 100) / 370)::numeric, 4),
    FALSE, NULL,
    '{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'::jsonb
FROM tickets t
WHERE t.ticket_code IN (
    'CX-F002','CX-F003','CX-F004','CX-F005','CX-F006','CX-F007',
    'CX-F008','CX-F009','CX-F010',
    'CX-J001','CX-J002','CX-J003','CX-J004','CX-J005','CX-J006',
    'CX-D001','CX-D002','CX-D003','CX-D004',
    'CX-N001','CX-N002','CX-N003','CX-N004',
    'CX-O001','CX-O002','CX-O003',
    'CX-S001','CX-S002',
    'CX-G001','CX-G002',
    'CX-L001','CX-E001','CX-M001','CX-P001'
)
AND NOT EXISTS (
    SELECT 1 FROM model_execution_log mel
    WHERE mel.ticket_id  = t.id
      AND mel.agent_name = 'routing'
      AND mel.status     = 'success'
);

-- SECTION 8: Add priority agent execution log rows
-- QC A "Avg Confidence Score" reads model_execution_log WHERE
-- agent_name = 'priority'. Extend to all remaining seeded tickets.
INSERT INTO model_execution_log (
    ticket_id, agent_name, model_version, triggered_by,
    started_at, completed_at, status,
    input_token_count, output_token_count,
    inference_time_ms, confidence_score, error_flag, error_message,
    infra_metadata
)
SELECT
    t.id,
    'priority'::agent_name_type,
    'priority-v2.4',
    'ingest'::trigger_source,
    (t.created_at + interval '10 seconds')::timestamptz,
    (t.created_at + interval '14 seconds')::timestamptz,
    'success'::execution_status,
    418, 30,
    3800,
    ROUND((0.76 + (EXTRACT(EPOCH FROM t.created_at)::numeric % 100) / 450)::numeric, 4),
    FALSE, NULL,
    '{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'::jsonb
FROM tickets t
WHERE t.ticket_code IN (
    'CX-F003','CX-F004','CX-F005','CX-F006','CX-F007',
    'CX-F008','CX-F009','CX-F010',
    'CX-J001','CX-J002','CX-J003','CX-J004','CX-J005','CX-J006',
    'CX-D001','CX-D002','CX-D003','CX-D004',
    'CX-N001','CX-N002','CX-N003','CX-N004',
    'CX-O001','CX-O002','CX-O003',
    'CX-S001','CX-S002',
    'CX-G001','CX-G002',
    'CX-L001','CX-E001','CX-M001','CX-P001'
)
AND NOT EXISTS (
    SELECT 1 FROM model_execution_log mel
    WHERE mel.ticket_id  = t.id
      AND mel.agent_name = 'priority'
      AND mel.status     = 'success'
);

-- SECTION 9: Refresh all 8 materialized views
-- Most important step -- without it all charts stay empty.
-- Function handles first-run (non-CONCURRENT) and re-runs (CONCURRENT).
-- Fix sentiment scores on escalated session chat logs so mv_chatbot_daily
-- populates the correct esc_negative / esc_neutral / esc_positive buckets.
--
-- MV bucket ranges (from avg sentiment per session):
--   esc_very_negative : avg < -0.5   (frontend ignores this bucket)
--   esc_negative      : -0.5 to -0.1 (frontend "Negative" bar)
--   esc_neutral       : -0.1 to +0.1 (frontend "Neutral" bar)
--   esc_positive      : >= +0.1      (frontend "Positive" bar)
--
-- We spread escalated sessions across all three visible buckets so all
-- three bars render in the Sentiment at Escalation chart.

-- Escalated sessions that should show as NEGATIVE (-0.5 to -0.1):
-- CX-F002 (HR biometric), CX-F008 (intercom), CX-F009 (AHU),
-- CX-MA002 (broadband), CX-AP005 (lease reminder)
UPDATE user_chat_logs
SET sentiment_score = -0.35
WHERE message IN (
    'Biometric readers on HR floor rejecting all fingerprints.',
    'All intercoms at entry points have no audio!',
    'CO2 levels high in Wing C -- AHU filter seems blocked.',
    'Monthly payroll export is timing out -- 280 staff payments at risk.'
)
AND sentiment_score < -0.5;

-- Escalated sessions that should show as NEUTRAL (-0.1 to +0.1):
-- CX-J002 (server backup), CX-L001 (water mains),
-- minor leak session, CX-MA009 (EV charging), CX-AP007 (backlog)
UPDATE user_chat_logs
SET sentiment_score = 0.00
WHERE message IN (
    'Server backup jobs have been failing since January 3rd.',
    'There is a small drip under the sink in room 204 -- not urgent.'
)
AND sentiment_score < -0.1;

-- Escalated sessions that should show as POSITIVE (>= +0.1):
-- AC confirmation session, CX-AP008 (contract dispute — calm tone),
-- CX-MA003 (lease doc — urgent but polite)
UPDATE user_chat_logs
SET sentiment_score = 0.18
WHERE message IN (
    'My AC issue seems resolved -- can a technician confirm before closing?',
    'Tenant lease document missing signature page. Tenant move-in tomorrow.',
    'Employment contract clause dispute -- L&C review needed.'
)
AND sentiment_score < 0.1;

-- 10 tickets across all 7 departments, realistic dates 2026-03-03 to 2026-03-27
-- Ticket codes: CX-MA001 … CX-MA010
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
('CX-MA001', 'Fire suppression system fault -- server room',
 'Server room fire suppression system showing fault LED. Last inspection 6 months ago.',
 'Complaint', 'Resolved', 'Critical',
 'Fire Safety', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-03-03 07:30:00+00','2026-03-03 07:38:00+00','2026-03-03 07:55:00+00','2026-03-03 16:00:00+00',
 '2026-03-03 08:00:00+00','2026-03-03 19:30:00+00',
 FALSE, FALSE, '2026-03-03 07:30:00+00',
 -0.74, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 96.00,
 'Shut down suppression zone; call certified engineer; log in fire register.',
 FALSE, FALSE),

('CX-MA002', 'Broadband link down -- admin wing',
 'Admin wing internet connection completely offline since 06:00. VPN and cloud access affected.',
 'Complaint', 'Resolved', 'High',
 'Network', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2026-03-05 08:00:00+00','2026-03-05 08:12:00+00','2026-03-05 08:45:00+00','2026-03-05 17:00:00+00',
 '2026-03-05 09:00:00+00','2026-03-06 08:00:00+00',
 FALSE, FALSE, '2026-03-05 08:00:00+00',
 -0.52, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='IT'), 89.00,
 'Failover to backup ISP; log fault with primary provider; monitor for 4 hours.',
 FALSE, FALSE),

('CX-MA003', 'Tenant lease document missing signature page',
 'Lease agreement for unit 4B uploaded without final signature page. Tenant move-in tomorrow.',
 'Complaint', 'Resolved', 'High',
 'Documentation', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-03-07 10:00:00+00','2026-03-07 10:18:00+00','2026-03-07 11:00:00+00','2026-03-07 16:00:00+00',
 '2026-03-07 11:00:00+00','2026-03-08 10:00:00+00',
 FALSE, FALSE, '2026-03-07 10:00:00+00',
 -0.43, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Leasing'), 84.00,
 'Retrieve full document; obtain missing signature; re-upload complete copy.',
 FALSE, FALSE),

('CX-MA004', 'AC unit dripping water -- Finance office',
 'Ceiling-mounted AC unit in Finance office dripping condensate onto desks. Equipment at risk.',
 'Complaint', 'Resolved', 'High',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-03-10 09:00:00+00','2026-03-10 09:20:00+00','2026-03-10 10:00:00+00','2026-03-11 14:00:00+00',
 '2026-03-10 10:00:00+00','2026-03-11 09:00:00+00',
 FALSE, FALSE, '2026-03-10 09:00:00+00',
 -0.46, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 86.00,
 'Clear blocked condensate drain; check refrigerant charge; dry affected surfaces.',
 FALSE, FALSE),

('CX-MA005', 'HR portal password reset emails not delivering',
 'Staff requesting password resets for HR portal not receiving emails. SMTP relay suspected.',
 'Complaint', 'Resolved', 'Medium',
 'Software', (SELECT id FROM departments WHERE name='HR'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='lena@innovacx.net'),
 '2026-03-12 11:00:00+00','2026-03-12 11:35:00+00','2026-03-12 12:15:00+00','2026-03-13 15:00:00+00',
 '2026-03-12 14:00:00+00','2026-03-14 11:00:00+00',
 FALSE, FALSE, '2026-03-12 11:00:00+00',
 -0.29, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='HR'), 77.00,
 'Restart SMTP relay service; test email delivery; update SPF record if needed.',
 FALSE, FALSE),

('CX-MA006', 'Scaffolding collapse risk -- south facade',
 'External scaffolding on south facade showing visible lean after high winds. Evacuation of ground level needed.',
 'Complaint', 'Resolved', 'Critical',
 'Civil', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-03-14 07:00:00+00','2026-03-14 07:06:00+00','2026-03-14 07:24:00+00','2026-03-14 18:00:00+00',
 '2026-03-14 07:30:00+00','2026-03-14 19:00:00+00',
 FALSE, FALSE, '2026-03-14 07:00:00+00',
 -0.85, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 98.00,
 'Evacuate ground level; cordon area; call structural engineer immediately.',
 FALSE, FALSE),

('CX-MA007', 'Water softener unit failed -- plant room',
 'Water softener in B1 plant room showing error code E4. Hard water causing scale buildup in pipes.',
 'Complaint', 'Resolved', 'Medium',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2026-03-17 09:00:00+00','2026-03-17 09:28:00+00','2026-03-17 10:15:00+00','2026-03-18 14:00:00+00',
 '2026-03-17 12:00:00+00','2026-03-19 09:00:00+00',
 FALSE, FALSE, '2026-03-17 09:00:00+00',
 -0.30, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Maintenance'), 80.00,
 'Replace resin bed; reset controller; run full regeneration cycle.',
 FALSE, FALSE),

('CX-MA008', 'Legal contract template outdated -- procurement',
 'Procurement team flagging that standard vendor contract template is 2 years out of date. Compliance risk.',
 'Inquiry', 'Resolved', 'Medium',
 'Documentation', (SELECT id FROM departments WHERE name='Legal & Compliance'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='bilal@innovacx.net'),
 '2026-03-19 10:00:00+00','2026-03-19 10:40:00+00','2026-03-19 11:30:00+00','2026-03-21 16:00:00+00',
 '2026-03-19 13:00:00+00','2026-03-21 10:00:00+00',
 FALSE, FALSE, '2026-03-19 10:00:00+00',
 -0.22, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Legal & Compliance'), 75.00,
 'Review current template against latest regulatory requirements; update and re-publish.',
 FALSE, FALSE),

('CX-MA009', 'EV charging station offline -- parking P1',
 'Two EV charging points on P1 level showing offline. Tenants unable to charge vehicles.',
 'Complaint', 'Resolved', 'Medium',
 'Electrical', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-03-21 08:00:00+00','2026-03-21 08:25:00+00','2026-03-21 09:10:00+00','2026-03-22 15:00:00+00',
 '2026-03-21 11:00:00+00','2026-03-23 08:00:00+00',
 FALSE, FALSE, '2026-03-21 08:00:00+00',
 -0.35, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='Facilities Management'), 82.00,
 'Reset charge point controller; check circuit breaker; update firmware.',
 FALSE, FALSE),

('CX-MA010', 'Staff access badge cloning attempt detected',
 'Security system flagged repeated failed entries with cloned badge signature on L3. Potential tailgating.',
 'Complaint', 'Resolved', 'Critical',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-03-27 06:30:00+00','2026-03-27 06:37:00+00','2026-03-27 06:55:00+00','2026-03-27 17:00:00+00',
 '2026-03-27 07:00:00+00','2026-03-27 18:30:00+00',
 FALSE, FALSE, '2026-03-27 06:30:00+00',
 -0.79, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Revoke compromised badge; audit L3 access logs; file security incident report.',
 FALSE, FALSE)

ON CONFLICT (ticket_code) DO NOTHING;

-- SECTION 11: April 2026 tickets
-- 8 tickets across all 7 departments, dates 2026-04-01 to 2026-04-08
-- Ticket codes: CX-AP001 … CX-AP008
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
('CX-AP001', 'Main lobby turnstile jammed -- peak entry time',
 'Turnstile 2 in main lobby jammed open during morning peak. Hundreds of staff queuing.',
 'Complaint', 'Resolved', 'Critical',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-04-01 07:00:00+00','2026-04-01 07:07:00+00','2026-04-01 07:26:00+00','2026-04-01 12:00:00+00',
 '2026-04-01 07:30:00+00','2026-04-01 19:00:00+00',
 FALSE, FALSE, '2026-04-01 07:00:00+00',
 -0.68, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 96.00,
 'Clear jam; run diagnostics; replace worn drive gear if needed.',
 FALSE, FALSE),

('CX-AP002', 'Payroll data export failing -- month-end',
 'Automated payroll export to bank system timing out at month-end batch. 280 staff payments at risk.',
 'Complaint', 'Resolved', 'Critical',
 'Software', (SELECT id FROM departments WHERE name='HR'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='lena@innovacx.net'),
 '2026-04-02 08:00:00+00','2026-04-02 08:06:00+00','2026-04-02 08:27:00+00','2026-04-02 18:00:00+00',
 '2026-04-02 08:30:00+00','2026-04-02 20:00:00+00',
 FALSE, FALSE, '2026-04-02 08:00:00+00',
 -0.76, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='HR'), 95.00,
 'Increase export timeout; split batch; re-run and confirm all records transmitted.',
 FALSE, FALSE),

('CX-AP003', 'Roof terrace drainage blocked -- standing water',
 'Roof terrace on L8 has 10cm standing water after last rain. Drain completely blocked with debris.',
 'Complaint', 'In Progress', 'High',
 'Civil', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-04-03 09:00:00+00','2026-04-03 09:22:00+00','2026-04-03 10:00:00+00', NULL,
 '2026-04-03 10:00:00+00','2026-04-04 09:00:00+00',
 FALSE, FALSE, '2026-04-03 09:00:00+00',
 -0.40, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 85.00,
 'Clear drain debris; inspect waterproofing membrane; schedule follow-up after next rain.',
 FALSE, FALSE),

('CX-AP004', 'IT asset register missing 47 laptops',
 'Quarterly IT audit shows 47 laptops unaccounted for. Asset register not updated since Dec 2025.',
 'Complaint', 'Assigned', 'High',
 'Software', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2026-04-04 10:00:00+00','2026-04-04 10:30:00+00','2026-04-04 11:15:00+00', NULL,
 '2026-04-04 11:00:00+00','2026-04-05 10:00:00+00',
 FALSE, FALSE, '2026-04-04 10:00:00+00',
 -0.50, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='IT'), 87.00,
 'Cross-reference DHCP logs with asset register; locate devices; update register.',
 FALSE, FALSE),

('CX-AP005', 'Lease renewal reminder system not sending',
 'Automated lease renewal reminders scheduled for April 5 batch not sent. 32 tenants affected.',
 'Complaint', 'Resolved', 'High',
 'Software', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-04-05 09:00:00+00','2026-04-05 09:17:00+00','2026-04-05 10:00:00+00','2026-04-05 17:00:00+00',
 '2026-04-05 10:00:00+00','2026-04-06 09:00:00+00',
 FALSE, FALSE, '2026-04-05 09:00:00+00',
 -0.55, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Leasing'), 88.00,
 'Fix scheduled job config; trigger manual send; confirm delivery receipts.',
 FALSE, FALSE),

('CX-AP006', 'Chemical storage labels non-compliant -- HSE audit',
 'HSE pre-audit inspection found 12 chemical storage containers missing GHS labels. Audit in 5 days.',
 'Complaint', 'Assigned', 'High',
 'Cleaning', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-04-06 08:00:00+00','2026-04-06 08:20:00+00','2026-04-06 09:00:00+00', NULL,
 '2026-04-06 09:00:00+00','2026-04-07 08:00:00+00',
 FALSE, FALSE, '2026-04-06 08:00:00+00',
 -0.62, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Safety & Security'), 91.00,
 'Print and apply GHS labels; update chemical inventory; brief storage staff.',
 FALSE, FALSE),

('CX-AP007', 'Maintenance work order backlog -- 38 open items',
 'Maintenance team reporting 38 open work orders older than 14 days. Staffing gap over Eid period.',
 'Inquiry', 'Open', 'Medium',
 'Civil', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2026-04-07 10:00:00+00','2026-04-07 10:45:00+00','2026-04-07 11:30:00+00', NULL,
 '2026-04-07 13:00:00+00','2026-04-09 10:00:00+00',
 FALSE, FALSE, '2026-04-07 10:00:00+00',
 -0.20, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Maintenance'), 74.00,
 'Triage open items by severity; engage temporary contractor for peak period.',
 FALSE, FALSE),

('CX-AP008', 'Employment contract clause dispute -- L&C review needed',
 'Employee raising dispute over non-compete clause wording in contract signed 2023. Escalated to L&C.',
 'Complaint', 'Assigned', 'Medium',
 'Documentation', (SELECT id FROM departments WHERE name='Legal & Compliance'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='bilal@innovacx.net'),
 '2026-04-08 09:00:00+00','2026-04-08 09:35:00+00','2026-04-08 10:20:00+00', NULL,
 '2026-04-08 12:00:00+00','2026-04-10 09:00:00+00',
 FALSE, FALSE, '2026-04-08 09:00:00+00',
 -0.33, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='Legal & Compliance'), 78.00,
 'Review clause against current template; advise HR and employee within 5 business days.',
 FALSE, FALSE)

ON CONFLICT (ticket_code) DO NOTHING;

-- resolved_at for tickets that are Resolved
UPDATE tickets
SET
    resolved_at         = created_at + interval '9 hours',
    resolved_by_user_id = assigned_to_user_id
WHERE ticket_code IN (
    'CX-MA001','CX-MA002','CX-MA003','CX-MA004','CX-MA005',
    'CX-MA006','CX-MA007','CX-MA008','CX-MA009','CX-MA010',
    'CX-AP001','CX-AP002','CX-AP005'
)
AND resolved_at IS NULL;

-- SECTION 12: model_execution_log for March + April tickets
-- sentiment, feature, priority, routing agents for all 18 new tickets
INSERT INTO model_execution_log (
    ticket_id, agent_name, model_version, triggered_by,
    started_at, completed_at, status,
    input_token_count, output_token_count,
    inference_time_ms, confidence_score, error_flag, error_message,
    infra_metadata
)
SELECT
    t.id,
    v.agent::agent_name_type,
    v.model_ver,
    'ingest'::trigger_source,
    (t.created_at + (v.offset_secs || ' seconds')::interval),
    (t.created_at + ((v.offset_secs + 4) || ' seconds')::interval),
    'success'::execution_status,
    v.in_tok, v.out_tok,
    v.inf_ms,
    ROUND((v.base_conf + (EXTRACT(EPOCH FROM t.created_at)::numeric % 100) / v.conf_div)::numeric, 4),
    FALSE, NULL,
    v.infra::jsonb
FROM (VALUES
    ('sentiment', 'sentiment-v3.1', 1,  415, 28, 4200, 0.84, 320, '{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
    ('feature',   'feature-v1.5',   6,  380, 44, 3100, 0.88, 360, '{"region":"me-south-1","instance":"ml-c5.large"}'),
    ('priority',  'priority-v2.4',  11, 418, 30, 3800, 0.80, 420, '{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
    ('routing',   'routing-v1.8',   16, 428, 24, 4100, 0.76, 390, '{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}')
) AS v(agent, model_ver, offset_secs, in_tok, out_tok, inf_ms, base_conf, conf_div, infra)
CROSS JOIN tickets t
WHERE t.ticket_code IN (
    'CX-MA001','CX-MA002','CX-MA003','CX-MA004','CX-MA005',
    'CX-MA006','CX-MA007','CX-MA008','CX-MA009','CX-MA010',
    'CX-AP001','CX-AP002','CX-AP003','CX-AP004','CX-AP005',
    'CX-AP006','CX-AP007','CX-AP008'
)
AND NOT EXISTS (
    SELECT 1 FROM model_execution_log mel
    WHERE mel.ticket_id  = t.id
      AND mel.agent_name = v.agent::agent_name_type
      AND mel.status     = 'success'
);

-- SECTION 13: sentiment_outputs for March + April tickets
INSERT INTO sentiment_outputs (
    execution_id, ticket_id, model_version,
    sentiment_label, sentiment_score, confidence_score,
    emotion_tags, raw_scores, is_current
)
SELECT DISTINCT ON (mel.ticket_id)
    mel.id, mel.ticket_id, mel.model_version,
    sv.label, sv.score, sv.conf,
    sv.emotions::text[], sv.raw::jsonb, TRUE
FROM (VALUES
    ('CX-MA001','Negative',    -0.7400, 0.9500, '{alarmed,safety_concerned,urgent}',     '{"negative":0.9500,"neutral":0.0350,"positive":0.0150}'),
    ('CX-MA002','Negative',    -0.5200, 0.8900, '{frustrated,business_impacted}',         '{"negative":0.8900,"neutral":0.0750,"positive":0.0350}'),
    ('CX-MA003','Negative',    -0.4300, 0.8700, '{concerned,urgent,deadline_pressure}',   '{"negative":0.8700,"neutral":0.0900,"positive":0.0400}'),
    ('CX-MA004','Negative',    -0.4600, 0.8800, '{frustrated,concerned}',                 '{"negative":0.8800,"neutral":0.0850,"positive":0.0350}'),
    ('CX-MA005','Neutral',     -0.2900, 0.7500, '{mildly_frustrated,inquiring}',          '{"negative":0.5700,"neutral":0.3200,"positive":0.1100}'),
    ('CX-MA006','Negative',    -0.8500, 0.9800, '{panicked,safety_concerned,alarmed}',    '{"negative":0.9800,"neutral":0.0150,"positive":0.0050}'),
    ('CX-MA007','Neutral',     -0.3000, 0.7600, '{neutral,mildly_concerned}',             '{"negative":0.5800,"neutral":0.3100,"positive":0.1100}'),
    ('CX-MA008','Neutral',     -0.2200, 0.7200, '{neutral,compliance_concerned}',         '{"negative":0.4900,"neutral":0.3900,"positive":0.1200}'),
    ('CX-MA009','Negative',    -0.3500, 0.8400, '{frustrated,inconvenienced}',            '{"negative":0.8400,"neutral":0.1100,"positive":0.0500}'),
    ('CX-MA010','Negative',    -0.7900, 0.9600, '{alarmed,safety_concerned,urgent}',      '{"negative":0.9600,"neutral":0.0300,"positive":0.0100}'),
    ('CX-AP001','Negative',    -0.6800, 0.9400, '{frustrated,urgent,business_impacted}',  '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
    ('CX-AP002','Negative',    -0.7600, 0.9500, '{alarmed,business_impacted,urgent}',     '{"negative":0.9500,"neutral":0.0350,"positive":0.0150}'),
    ('CX-AP003','Negative',    -0.4000, 0.8600, '{concerned,frustrated}',                 '{"negative":0.8600,"neutral":0.1000,"positive":0.0400}'),
    ('CX-AP004','Negative',    -0.5000, 0.8800, '{concerned,compliance_risk}',            '{"negative":0.8800,"neutral":0.0850,"positive":0.0350}'),
    ('CX-AP005','Negative',    -0.5500, 0.8900, '{frustrated,business_impacted}',         '{"negative":0.8900,"neutral":0.0750,"positive":0.0350}'),
    ('CX-AP006','Negative',    -0.6200, 0.9100, '{alarmed,compliance_risk,urgent}',       '{"negative":0.9100,"neutral":0.0600,"positive":0.0300}'),
    ('CX-AP007','Neutral',     -0.2000, 0.7400, '{neutral,inquiring,concerned}',          '{"negative":0.4700,"neutral":0.4000,"positive":0.1300}'),
    ('CX-AP008','Negative',    -0.3300, 0.8300, '{concerned,disputing}',                  '{"negative":0.8300,"neutral":0.1200,"positive":0.0500}')
) AS sv(tc, label, score, conf, emotions, raw)
JOIN model_execution_log mel
  ON mel.ticket_id = (SELECT id FROM tickets WHERE ticket_code = sv.tc LIMIT 1)
 AND mel.agent_name = 'sentiment'
 AND mel.status     = 'success'
WHERE NOT EXISTS (
    SELECT 1 FROM sentiment_outputs so
    WHERE so.ticket_id = mel.ticket_id AND so.is_current = TRUE
)
ORDER BY mel.ticket_id, mel.started_at;

-- SECTION 14: feature_outputs for March + April tickets
INSERT INTO feature_outputs (
    execution_id, ticket_id, model_version,
    asset_category, topic_labels, confidence_score, raw_features, is_current
)
SELECT DISTINCT ON (mel.ticket_id)
    mel.id, mel.ticket_id, mel.model_version,
    fv.asset_cat, fv.topics::text[], fv.conf, fv.raw::jsonb, TRUE
FROM (VALUES
    ('CX-MA001','Fire Safety',      '{fire-suppression,server-room,fault,safety,critical}',         0.9600, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-MA002','Network',          '{broadband,internet,admin,vpn,outage}',                         0.9000, '{"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
    ('CX-MA003','Documentation',    '{lease,signature,tenant,move-in,compliance}',                   0.8600, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
    ('CX-MA004','HVAC',             '{ac,condensate,drain,office,dripping}',                         0.8800, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"Medium","is_recurring":false}'),
    ('CX-MA005','Software',         '{hr-portal,password-reset,smtp,email,delivery}',                0.7800, '{"business_impact":"Low","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
    ('CX-MA006','Civil',            '{scaffolding,collapse,wind,safety,evacuation}',                 0.9800, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-MA007','Plumbing',         '{water-softener,scale,plant-room,maintenance,e4-error}',        0.8100, '{"business_impact":"Low","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
    ('CX-MA008','Documentation',    '{contract,template,compliance,procurement,outdated}',           0.7600, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Medium","is_recurring":false}'),
    ('CX-MA009','Electrical',       '{ev-charging,parking,offline,firmware,circuit}',                0.8300, '{"business_impact":"Low","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Medium","is_recurring":false}'),
    ('CX-MA010','Access Control',   '{badge,cloning,security,access,incident}',                      0.9700, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-AP001','Access Control',   '{turnstile,jammed,lobby,peak,access}',                          0.9500, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-AP002','Software',         '{payroll,export,timeout,month-end,batch}',                      0.9600, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-AP003','Civil',            '{roof,drainage,standing-water,blocked,rain}',                   0.8700, '{"business_impact":"Medium","safety_concern":true,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
    ('CX-AP004','Software',         '{asset-register,laptops,audit,it,missing}',                     0.8800, '{"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
    ('CX-AP005','Software',         '{lease-renewal,reminder,automated,email,batch}',                0.8900, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
    ('CX-AP006','Cleaning',         '{chemical,ghs-label,hse,audit,compliance}',                     0.9200, '{"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"Critical","is_recurring":false}'),
    ('CX-AP007','Civil',            '{maintenance,backlog,work-order,staffing,eid}',                  0.7500, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Medium","is_recurring":true}'),
    ('CX-AP008','Documentation',    '{contract,clause,dispute,legal,non-compete}',                   0.7900, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Medium","is_recurring":false}')
) AS fv(tc, asset_cat, topics, conf, raw)
JOIN model_execution_log mel
  ON mel.ticket_id = (SELECT id FROM tickets WHERE ticket_code = fv.tc LIMIT 1)
 AND mel.agent_name = 'feature'
 AND mel.status     = 'success'
WHERE NOT EXISTS (
    SELECT 1 FROM feature_outputs fo
    WHERE fo.ticket_id = mel.ticket_id AND fo.is_current = TRUE
)
ORDER BY mel.ticket_id, mel.started_at;

-- backfill is_recurring from feature_outputs
UPDATE tickets t
SET is_recurring = TRUE
FROM feature_outputs fo
WHERE fo.ticket_id  = t.id
  AND fo.is_current = TRUE
  AND (fo.raw_features->>'is_recurring')::boolean = TRUE
  AND t.is_recurring = FALSE;

-- SECTION 15: suggested_resolution_usage for March + April tickets
-- ~83% accepted, ~17% declined_custom — consistent with existing data
INSERT INTO suggested_resolution_usage (
    ticket_id, employee_user_id, decision, actor_role, department,
    suggested_text, final_text, used
)
SELECT t.id, u.id, fb.decision, 'employee', d.name,
       fb.suggested, fb.final, (fb.decision = 'accepted')
FROM (VALUES
    ('CX-MA001','yousef@innovacx.net','accepted',
     'Shut down suppression zone; call certified engineer; log in fire register.',
     NULL, 'Suppression zone isolated. Engineer on site within 90 minutes. System certified safe.'),
    ('CX-MA002','ahmed@innovacx.net','accepted',
     'Failover to backup ISP; log fault with primary provider; monitor for 4 hours.',
     NULL, 'Failover activated. Primary ISP fault logged. Connectivity restored within 2 hours.'),
    ('CX-MA003','talya@innovacx.net','declined_custom',
     'Retrieve full document; obtain missing signature; re-upload complete copy.',
     'Signature obtained via DocuSign to meet same-day deadline.',
     'DocuSign request sent and completed within 1 hour. Full document re-uploaded.'),
    ('CX-MA004','sarah@innovacx.net','accepted',
     'Clear blocked condensate drain; check refrigerant charge; dry affected surfaces.',
     NULL, 'Drain cleared. Refrigerant charge OK. Affected surfaces dried and disinfected.'),
    ('CX-MA005','lena@innovacx.net','accepted',
     'Restart SMTP relay service; test email delivery; update SPF record if needed.',
     NULL, 'SMTP relay restarted. All queued password reset emails delivered successfully.'),
    ('CX-MA006','yousef@innovacx.net','accepted',
     'Evacuate ground level; cordon area; call structural engineer immediately.',
     NULL, 'Area evacuated and cordoned. Structural engineer confirmed scaffolding safe after inspection.'),
    ('CX-MA007','sameer@innovacx.net','accepted',
     'Replace resin bed; reset controller; run full regeneration cycle.',
     NULL, 'Resin bed replaced. Full regeneration cycle completed. Water quality confirmed normal.'),
    ('CX-MA008','bilal@innovacx.net','declined_custom',
     'Review current template against latest regulatory requirements; update and re-publish.',
     'Required external legal counsel sign-off before re-publishing.',
     'External counsel reviewed and approved updated template. Published to intranet.'),
    ('CX-MA009','sarah@innovacx.net','accepted',
     'Reset charge point controller; check circuit breaker; update firmware.',
     NULL, 'Controller reset. Firmware updated to v3.2.1. Both charge points operational.'),
    ('CX-MA010','yousef@innovacx.net','accepted',
     'Revoke compromised badge; audit L3 access logs; file security incident report.',
     NULL, 'Badge revoked. Access log audit complete — no confirmed intrusion. Incident report filed.'),
    ('CX-AP001','yousef@innovacx.net','accepted',
     'Clear jam; run diagnostics; replace worn drive gear if needed.',
     NULL, 'Jam cleared. Drive gear replaced. Turnstile operating normally within 30 minutes.'),
    ('CX-AP002','lena@innovacx.net','accepted',
     'Increase export timeout; split batch; re-run and confirm all records transmitted.',
     NULL, 'Timeout increased to 300s. Batch split into 2 runs. All 280 records transmitted successfully.'),
    ('CX-AP003','sarah@innovacx.net','accepted',
     'Clear drain debris; inspect waterproofing membrane; schedule follow-up after next rain.',
     NULL, 'Drain cleared. Membrane inspected — minor crack sealed. Follow-up scheduled.'),
    ('CX-AP004','ahmed@innovacx.net','declined_custom',
     'Cross-reference DHCP logs with asset register; locate devices; update register.',
     'Physical audit required alongside DHCP check to confirm locations.',
     'Physical audit and DHCP cross-reference completed. 44 of 47 laptops located and registered.'),
    ('CX-AP005','talya@innovacx.net','accepted',
     'Fix scheduled job config; trigger manual send; confirm delivery receipts.',
     NULL, 'Job config fixed. Manual send triggered. All 32 tenants confirmed delivery.'),
    ('CX-AP006','yousef@innovacx.net','accepted',
     'Print and apply GHS labels; update chemical inventory; brief storage staff.',
     NULL, 'All 12 containers relabelled. Inventory updated. Staff briefed. Ready for HSE audit.'),
    ('CX-AP007','sameer@innovacx.net','accepted',
     'Triage open items by severity; engage temporary contractor for peak period.',
     NULL, 'Items triaged: 8 critical, 18 high, 12 medium. Contractor engaged for 2-week cover.'),
    ('CX-AP008','bilal@innovacx.net','accepted',
     'Review clause against current template; advise HR and employee within 5 business days.',
     NULL, 'Clause reviewed. Wording found ambiguous — amendment letter drafted and issued.')
) AS fb(tc, emp, decision, suggested, custom, final)
JOIN tickets t ON t.ticket_code = fb.tc
JOIN users u ON u.email = fb.emp
LEFT JOIN departments d ON d.id = t.department_id
WHERE NOT EXISTS (
    SELECT 1 FROM suggested_resolution_usage sru
    WHERE sru.ticket_id        = t.id
      AND sru.employee_user_id = u.id
);

-- SECTION 16: approval_requests for March + April tickets
-- Provides data for QC B Rescoring + Rerouting KPIs
INSERT INTO approval_requests (
    request_code, ticket_id, request_type, current_value, requested_value,
    request_reason, submitted_by_user_id, submitted_at, status,
    decided_by_user_id, decided_at, decision_notes
)
SELECT r.code, t.id, r.rtype::approval_request_type,
    r.cur, r.req, r.reason,
    (SELECT id FROM users WHERE email = r.sub_email),
    r.sub_at::timestamptz, r.status::approval_status,
    CASE WHEN r.dec_email IS NOT NULL THEN (SELECT id FROM users WHERE email = r.dec_email) ELSE NULL END,
    r.dec_at::timestamptz, r.dec_notes
FROM (VALUES
    ('REQ-6001','CX-MA006','Rescoring','Priority: Critical','Priority: Critical',
     'Scaffolding collapse risk warrants Critical — confirming escalation.',
     'yousef@innovacx.net','2026-03-14 07:30:00+00','Approved',
     'ali@innovacx.net','2026-03-14 08:00:00+00',
     'Confirmed Critical — immediate structural safety risk.'),
    ('REQ-6002','CX-MA002','Rerouting','Dept: IT','Dept: Facilities Management',
     'Broadband outage may be physical line fault — Facilities should assess cabling.',
     'ahmed@innovacx.net','2026-03-05 09:00:00+00','Rejected',
     'hamad@innovacx.net','2026-03-05 09:30:00+00',
     'ISP-side fault confirmed — IT retains ownership.'),
    ('REQ-6003','CX-MA010','Rescoring','Priority: Critical','Priority: Critical',
     'Badge cloning confirmed — Critical security incident.',
     'yousef@innovacx.net','2026-03-27 07:00:00+00','Approved',
     'ali@innovacx.net','2026-03-27 07:30:00+00',
     'Agreed — confirmed security breach attempt warrants Critical.'),
    ('REQ-6004','CX-AP002','Rescoring','Priority: Critical','Priority: Critical',
     'Payroll failure affecting 280 staff — Critical is correct.',
     'lena@innovacx.net','2026-04-02 08:30:00+00','Approved',
     'leen@innovacx.net','2026-04-02 09:00:00+00',
     'Confirmed — financial and legal exposure at month-end.'),
    ('REQ-6005','CX-AP003','Rerouting','Dept: Facilities Management','Dept: Maintenance',
     'Roof drainage blockage is a Maintenance scope item not Facilities.',
     'sarah@innovacx.net','2026-04-03 10:30:00+00','Pending',
     NULL, NULL, NULL),
    ('REQ-6006','CX-AP004','Rerouting','Dept: IT','Dept: Safety & Security',
     'Missing laptops may be a security/theft issue — Security should be involved.',
     'ahmed@innovacx.net','2026-04-04 11:30:00+00','Rejected',
     'hamad@innovacx.net','2026-04-04 12:00:00+00',
     'Asset management is IT responsibility. Security notified separately.'),
    ('REQ-6007','CX-AP006','Rescoring','Priority: High','Priority: Critical',
     'HSE audit in 5 days — non-compliance could result in enforcement notice.',
     'yousef@innovacx.net','2026-04-06 09:30:00+00','Approved',
     'ali@innovacx.net','2026-04-06 10:00:00+00',
     'Agreed — regulatory deadline makes this Critical.')
) AS r(code, tc, rtype, cur, req, reason, sub_email, sub_at, status, dec_email, dec_at, dec_notes)
JOIN tickets t ON t.ticket_code = r.tc
ON CONFLICT (request_code) DO NOTHING;

-- SECTION 17: reroute_reference + rescore_reference for March + April
INSERT INTO reroute_reference (
    ticket_id, department, original_dept, corrected_dept, actor_role, source_type
)
SELECT t.id, v.dept, v.orig, v.corr, v.actor_role, v.src
FROM (VALUES
    ('CX-MA002','IT','IT','Facilities Management','employee','approval_rerouting'),
    ('CX-AP003','Facilities Management','Facilities Management','Maintenance','employee','approval_rerouting'),
    ('CX-AP004','IT','IT','Safety & Security','employee','approval_rerouting')
) AS v(tc, dept, orig, corr, actor_role, src)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
    SELECT 1 FROM reroute_reference rr
    WHERE rr.ticket_id = t.id AND rr.original_dept = v.orig AND rr.corrected_dept = v.corr
);

INSERT INTO rescore_reference (
    ticket_id, department, original_priority, corrected_priority, actor_role, source_type
)
SELECT t.id, v.dept, v.orig_p, v.corr_p, v.actor_role, v.src
FROM (VALUES
    ('CX-MA006','Safety & Security','Critical','Critical','manager','approval_rescoring'),
    ('CX-MA010','Safety & Security','Critical','Critical','manager','approval_rescoring'),
    ('CX-AP002','HR','Critical','Critical','manager','approval_rescoring'),
    ('CX-AP006','Safety & Security','High','Critical','manager','approval_rescoring')
) AS v(tc, dept, orig_p, corr_p, actor_role, src)
JOIN tickets t ON t.ticket_code = v.tc
WHERE NOT EXISTS (
    SELECT 1 FROM rescore_reference rsc
    WHERE rsc.ticket_id = t.id AND rsc.original_priority = v.orig_p AND rsc.corrected_priority = v.corr_p
);

-- SECTION 18: sessions + user_chat_logs for March + April
-- Adds chatbot sessions spread across both months
INSERT INTO sessions (
    user_id, current_state, context, history,
    created_at, updated_at,
    bot_model_version, escalated_to_human, escalated_at, linked_ticket_id
)
SELECT
    (SELECT id FROM users WHERE email = v.email),
    'resolved', v.ctx::jsonb, v.hist::jsonb,
    v.ts::timestamptz, (v.ts::timestamptz + interval '20 minutes'),
    'chatbot-v2.1',
    v.escalated::boolean,
    CASE WHEN v.escalated::boolean THEN v.ts::timestamptz + interval '4 minutes' ELSE NULL END,
    CASE WHEN v.tc IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code = v.tc) ELSE NULL END
FROM (VALUES
    -- March escalated
    ('customer1@innovacx.net',
     '{"last_intent":"report_issue","asset":"Fire Safety","type":"suppression_fault"}',
     '[{"role":"user","msg":"Fire suppression fault LED on in server room"},{"role":"bot","msg":"Critical -- escalating"}]',
     '2026-03-03 07:30:00+00', 'true', 'CX-MA001'),
    ('customer3@innovacx.net',
     '{"last_intent":"report_issue","asset":"Access Control","type":"badge_cloning"}',
     '[{"role":"user","msg":"Repeated failed badge attempts on L3"},{"role":"bot","msg":"Security incident -- escalating"}]',
     '2026-03-27 06:30:00+00', 'true', 'CX-MA010'),
    -- March contained
    ('customer2@innovacx.net',
     '{"last_intent":"inquiry","topic":"lease_renewal"}',
     '[{"role":"user","msg":"How do I renew a lease early?"},{"role":"bot","msg":"Explained process"}]',
     '2026-03-15 11:00:00+00', 'false', NULL),
    ('customer1@innovacx.net',
     '{"last_intent":"inquiry","topic":"ev_charging"}',
     '[{"role":"user","msg":"Are EV charging points bookable?"},{"role":"bot","msg":"No booking needed -- first come first served"}]',
     '2026-03-22 14:00:00+00', 'false', NULL),
    -- April escalated
    ('customer2@innovacx.net',
     '{"last_intent":"report_issue","asset":"Access Control","type":"turnstile_jam"}',
     '[{"role":"user","msg":"Turnstile 2 jammed open -- hundreds queuing"},{"role":"bot","msg":"Critical -- escalating"}]',
     '2026-04-01 07:00:00+00', 'true', 'CX-AP001'),
    ('customer3@innovacx.net',
     '{"last_intent":"report_issue","asset":"Software","type":"payroll_failure"}',
     '[{"role":"user","msg":"Payroll export timing out -- 280 staff affected"},{"role":"bot","msg":"Critical -- escalating immediately"}]',
     '2026-04-02 08:00:00+00', 'true', 'CX-AP002'),
    ('customer1@innovacx.net',
     '{"last_intent":"report_issue","asset":"Cleaning","type":"hse_labels"}',
     '[{"role":"user","msg":"Chemical storage labels missing before HSE audit"},{"role":"bot","msg":"High priority -- escalating"}]',
     '2026-04-06 08:00:00+00', 'true', 'CX-AP006'),
    -- April contained
    ('customer2@innovacx.net',
     '{"last_intent":"inquiry","topic":"maintenance_schedule"}',
     '[{"role":"user","msg":"When is the next planned HVAC maintenance?"},{"role":"bot","msg":"Quarterly -- next due June"}]',
     '2026-04-07 10:00:00+00', 'false', NULL),
    ('customer3@innovacx.net',
     '{"last_intent":"inquiry","topic":"visitor_parking"}',
     '[{"role":"user","msg":"How do visitors register for parking?"},{"role":"bot","msg":"Online pre-registration link sent"}]',
     '2026-04-08 15:00:00+00', 'false', NULL)
) AS v(email, ctx, hist, ts, escalated, tc)
WHERE NOT EXISTS (
    SELECT 1 FROM sessions s2
    WHERE s2.user_id    = (SELECT id FROM users WHERE email = v.email)
      AND s2.created_at = v.ts::timestamptz
);

INSERT INTO user_chat_logs (
    user_id, session_id, message,
    intent_detected, aggression_flag, aggression_score,
    created_at, sentiment_score, category, response_time_ms, ticket_id
)
SELECT
    (SELECT id FROM users WHERE email = v.email),
    s.session_id,
    v.msg, v.intent,
    FALSE, 0.003,
    v.ts::timestamptz,
    v.sent, v.cat, v.resp_ms,
    CASE WHEN v.tc IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code = v.tc) ELSE NULL END
FROM (VALUES
    ('customer1@innovacx.net','2026-03-03 07:30:30+00',
     'Fire suppression fault LED is showing in the server room.',
     'report_issue',-0.74,'Fire Safety',NULL,'CX-MA001'),
    ('customer3@innovacx.net','2026-03-27 06:30:30+00',
     'Repeated failed badge entry attempts detected on L3 access point.',
     'report_issue',-0.79,'Access Control',NULL,'CX-MA010'),
    ('customer2@innovacx.net','2026-03-15 11:00:30+00',
     'How can a tenant initiate an early lease renewal process?',
     'inquiry',0.15,'General',620,NULL),
    ('customer1@innovacx.net','2026-03-22 14:00:30+00',
     'Are the EV charging points on P1 available to book in advance?',
     'inquiry',0.20,'Parking',600,NULL),
    ('customer2@innovacx.net','2026-04-01 07:00:30+00',
     'Turnstile 2 in main lobby is jammed open during morning peak.',
     'report_issue',-0.68,'Access Control',NULL,'CX-AP001'),
    ('customer3@innovacx.net','2026-04-02 08:00:30+00',
     'Monthly payroll export is timing out -- 280 staff payments at risk.',
     'report_issue',-0.76,'Software',NULL,'CX-AP002'),
    ('customer1@innovacx.net','2026-04-06 08:00:30+00',
     'Chemical storage containers missing GHS labels before HSE audit in 5 days.',
     'report_issue',-0.62,'Cleaning',NULL,'CX-AP006'),
    ('customer2@innovacx.net','2026-04-07 10:00:30+00',
     'When is the next scheduled HVAC maintenance for the building?',
     'inquiry',0.18,'HVAC',610,NULL),
    ('customer3@innovacx.net','2026-04-08 15:00:30+00',
     'How do visitors register their vehicle for the building parking?',
     'inquiry',0.25,'Parking',590,NULL)
) AS v(email, ts, msg, intent, sent, cat, resp_ms, tc)
JOIN sessions s
  ON s.user_id    = (SELECT id FROM users WHERE email = v.email)
 AND s.created_at = (
     SELECT created_at FROM sessions
     WHERE user_id = (SELECT id FROM users WHERE email = v.email)
     ORDER BY ABS(EXTRACT(EPOCH FROM (created_at - v.ts::timestamptz)))
     LIMIT 1
 )
WHERE NOT EXISTS (
    SELECT 1 FROM user_chat_logs ucl
    WHERE ucl.user_id = (SELECT id FROM users WHERE email = v.email)
      AND ucl.message  = v.msg
);

-- Correct sentiment scores for March/April escalated sessions
-- so they land in esc_negative / esc_neutral / esc_positive buckets:
-- Fire suppression + badge cloning + turnstile → Negative (-0.5 to -0.1)
-- Payroll + HSE labels → Negative (-0.5 to -0.1)
-- Roof drainage → Neutral (-0.1 to +0.1)
UPDATE user_chat_logs
SET sentiment_score = -0.38
WHERE message IN (
    'Fire suppression fault LED is showing in the server room.',
    'Repeated failed badge entry attempts detected on L3 access point.',
    'Turnstile 2 in main lobby is jammed open during morning peak.',
    'Chemical storage containers missing GHS labels before HSE audit in 5 days.'
)
AND sentiment_score < -0.5;

UPDATE user_chat_logs
SET sentiment_score = -0.28
WHERE message IN (
    'Monthly payroll export is timing out -- 280 staff payments at risk.'
)
AND sentiment_score < -0.5;

UPDATE user_chat_logs
SET sentiment_score = 0.02
WHERE message IN (
    'How can a tenant initiate an early lease renewal process.',
    'Are the EV charging points on P1 available to book in advance?'
)
AND sentiment_score < -0.1;

-- Final MV refresh — picks up all new March + April data
SELECT refresh_analytics_mvs() AS presentation_refresh_result;

COMMIT;

-- POST-RUN VERIFICATION QUERIES
-- Run these after applying to confirm data is populated correctly.

-- 1. MV row counts (all should be > 0)
SELECT
    'mv_chatbot_daily'      AS mv, COUNT(*) AS rows FROM mv_chatbot_daily
UNION ALL SELECT 'mv_sentiment_daily',   COUNT(*) FROM mv_sentiment_daily
UNION ALL SELECT 'mv_feature_daily',     COUNT(*) FROM mv_feature_daily
UNION ALL SELECT 'mv_acceptance_daily',  COUNT(*) FROM mv_acceptance_daily
UNION ALL SELECT 'mv_operator_qc_daily', COUNT(*) FROM mv_operator_qc_daily
UNION ALL SELECT 'mv_ticket_base',       COUNT(*) FROM mv_ticket_base
UNION ALL SELECT 'mv_daily_volume',      COUNT(*) FROM mv_daily_volume
UNION ALL SELECT 'mv_employee_daily',    COUNT(*) FROM mv_employee_daily
ORDER BY mv;

-- 2. Learning tab tables
SELECT 'reroute_reference'          AS tbl, COUNT(*) AS rows FROM reroute_reference
UNION ALL SELECT 'rescore_reference',           COUNT(*) FROM rescore_reference
UNION ALL SELECT 'suggested_resolution_usage',  COUNT(*) FROM suggested_resolution_usage;

-- 3. Chatbot KPIs
SELECT
    SUM(total_sessions)     AS total_sessions,
    SUM(escalated_sessions) AS escalated,
    SUM(contained_sessions) AS contained,
    ROUND(SUM(escalated_sessions)::numeric
          / NULLIF(SUM(total_sessions),0) * 100, 1) AS escalation_pct
FROM mv_chatbot_daily;

-- 4. Sentiment distribution
SELECT
    SUM(positive_count)      AS positive,
    SUM(neutral_count)       AS neutral,
    SUM(negative_count)      AS negative,
    SUM(very_negative_count) AS very_negative,
    ROUND(AVG(avg_sentiment_score), 3) AS avg_score
FROM mv_sentiment_daily;

-- 5. Feature agent summary
SELECT
    SUM(total_processed)   AS total,
    SUM(safety_flag_count) AS safety_flags,
    SUM(impact_high)       AS impact_high,
    SUM(impact_medium)     AS impact_medium,
    SUM(impact_low)        AS impact_low
FROM mv_feature_daily;

-- 6. Acceptance (QC tab A)
SELECT
    SUM(total)    AS total_resolutions,
    SUM(accepted) AS accepted,
    SUM(declined) AS declined,
    ROUND(SUM(accepted)::numeric / NULLIF(SUM(total),0) * 100, 1) AS acceptance_rate
FROM mv_acceptance_daily;

-- 7. Agent coverage
SELECT COUNT(DISTINCT ticket_id) AS routing_agent_tickets
FROM model_execution_log WHERE agent_name = 'routing' AND status = 'success';

SELECT COUNT(DISTINCT ticket_id) AS priority_agent_tickets
FROM model_execution_log WHERE agent_name = 'priority' AND status = 'success';
