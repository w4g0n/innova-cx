-- =============================================================================
-- seed_extra.sql  — 5-10 extra rows per table
-- Run AFTER init.sql + zzz_analytics_mvs.sh have completed.
-- Idempotent: uses DO blocks + ON CONFLICT DO NOTHING where possible.
-- =============================================================================



\echo "--- Section 1: DEPARTMENTS ---"
-- =============================================================================
-- 1. DEPARTMENTS
-- =============================================================================
BEGIN;

INSERT INTO departments (id, name) VALUES
  ('a1000000-0000-0000-0000-000000000001', 'Network Operations'),
  ('a1000000-0000-0000-0000-000000000002', 'Customer Experience'),
  ('a1000000-0000-0000-0000-000000000003', 'Billing & Finance'),
  ('a1000000-0000-0000-0000-000000000004', 'Field Services'),
  ('a1000000-0000-0000-0000-000000000005', 'Enterprise Support'),
  ('a1000000-0000-0000-0000-000000000006', 'Security Operations'),
  ('a1000000-0000-0000-0000-000000000007', 'Product Development')
ON CONFLICT (name) DO NOTHING;
COMMIT;

\echo "--- Section 2: USERS  (password_hash = bcrypt of "Password1!") ---"
-- =============================================================================
-- 2. USERS  (password_hash = bcrypt of "Password1!")
-- =============================================================================
BEGIN;

INSERT INTO users (id, email, password_hash, role, is_active) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'alice.morgan@example.com',   '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'customer',  TRUE),
  ('b1000000-0000-0000-0000-000000000002', 'bob.chen@example.com',       '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'customer',  TRUE),
  ('b1000000-0000-0000-0000-000000000003', 'carol.smith@example.com',    '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'employee',  TRUE),
  ('b1000000-0000-0000-0000-000000000004', 'dan.kowalski@example.com',   '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'employee',  TRUE),
  ('b1000000-0000-0000-0000-000000000005', 'eve.jackson@example.com',    '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'manager',   TRUE),
  ('b1000000-0000-0000-0000-000000000006', 'frank.ali@example.com',      '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'operator',  TRUE),
  ('b1000000-0000-0000-0000-000000000007', 'grace.osei@example.com',     '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'customer',  TRUE),
  ('b1000000-0000-0000-0000-000000000008', 'henry.ross@example.com',     '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'employee',  TRUE),
  ('b1000000-0000-0000-0000-000000000009', 'iris.khan@example.com',      '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'customer',  FALSE),
  ('b1000000-0000-0000-0000-000000000010', 'james.wu@example.com',       '$2b$12$KIX/EtHFGKtHfTqDpKpnYuGJOtLz5BQ1PmHJqZ0bQKw3LqX1gQ2Ry', 'employee',  TRUE)
ON CONFLICT (email) DO NOTHING;
COMMIT;

\echo "--- Section 3: USER PROFILES ---"
-- =============================================================================
-- 3. USER PROFILES
-- =============================================================================
BEGIN;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'Alice Morgan',   '+971501111001', 'Dubai, UAE',      NULL,                                         NULL,       NULL),
  ('b1000000-0000-0000-0000-000000000002', 'Bob Chen',       '+971501111002', 'Abu Dhabi, UAE',  NULL,                                         NULL,       NULL),
  ('b1000000-0000-0000-0000-000000000003', 'Carol Smith',    '+971501111003', 'Sharjah, UAE',    'a1000000-0000-0000-0000-000000000002', 'EMP-1003', 'Support Analyst'),
  ('b1000000-0000-0000-0000-000000000004', 'Dan Kowalski',   '+971501111004', 'Dubai, UAE',      'a1000000-0000-0000-0000-000000000001', 'EMP-1004', 'Network Engineer'),
  ('b1000000-0000-0000-0000-000000000005', 'Eve Jackson',    '+971501111005', 'Dubai, UAE',      'a1000000-0000-0000-0000-000000000002', 'MGR-1005', 'Support Manager'),
  ('b1000000-0000-0000-0000-000000000006', 'Frank Ali',      '+971501111006', 'Dubai, UAE',      'a1000000-0000-0000-0000-000000000006', 'OPR-1006', 'System Operator'),
  ('b1000000-0000-0000-0000-000000000007', 'Grace Osei',     '+971501111007', 'Ajman, UAE',      NULL,                                         NULL,       NULL),
  ('b1000000-0000-0000-0000-000000000008', 'Henry Ross',     '+971501111008', 'Dubai, UAE',      'a1000000-0000-0000-0000-000000000004', 'EMP-1008', 'Field Technician'),
  ('b1000000-0000-0000-0000-000000000009', 'Iris Khan',      '+971501111009', 'Fujairah, UAE',   NULL,                                         NULL,       NULL),
  ('b1000000-0000-0000-0000-000000000010', 'James Wu',       '+971501111010', 'Dubai, UAE',      'a1000000-0000-0000-0000-000000000003', 'EMP-1010', 'Billing Specialist')
ON CONFLICT (user_id) DO NOTHING;
COMMIT;

\echo "--- Section 4: USER PREFERENCES ---"
-- =============================================================================
-- 4. USER PREFERENCES
-- =============================================================================
BEGIN;

INSERT INTO user_preferences (user_id, language, dark_mode, default_complaint_type, email_notifications, in_app_notifications, status_alerts) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'English', FALSE, 'Network',  TRUE,  TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000002', 'Arabic',  TRUE,  'Billing',  TRUE,  FALSE, TRUE),
  ('b1000000-0000-0000-0000-000000000003', 'English', FALSE, 'General',  TRUE,  TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000004', 'English', TRUE,  'General',  FALSE, TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000005', 'English', FALSE, 'General',  TRUE,  TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000006', 'English', TRUE,  'General',  TRUE,  TRUE,  FALSE),
  ('b1000000-0000-0000-0000-000000000007', 'French',  FALSE, 'Service',  TRUE,  TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000008', 'English', FALSE, 'General',  TRUE,  TRUE,  TRUE),
  ('b1000000-0000-0000-0000-000000000009', 'Urdu',    FALSE, 'Network',  FALSE, FALSE, FALSE),
  ('b1000000-0000-0000-0000-000000000010', 'English', TRUE,  'Billing',  TRUE,  TRUE,  TRUE)
ON CONFLICT (user_id) DO NOTHING;
COMMIT;

\echo "--- Section 5: TICKETS ---"
-- =============================================================================
-- 5. TICKETS
-- =============================================================================
BEGIN;

INSERT INTO tickets (
  id, ticket_code, subject, details, ticket_type, status, priority,
  asset_type, department_id, created_by_user_id, assigned_to_user_id,
  created_at, updated_at, assigned_at, sentiment_score, sentiment_label,
  model_priority, model_confidence
) VALUES
  ('c1000000-0000-0000-0000-000000000001', 'TKT-X001', 'Slow internet at home',           'My broadband has been very slow for 3 days.',            'Complaint', 'Open',         'High',     'Broadband',  'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000004', now()-'5 days'::interval,  now()-'4 days'::interval,  now()-'4 days'::interval,  -0.720, 'Negative',  'High',     82.50),
  ('c1000000-0000-0000-0000-000000000002', 'TKT-X002', 'Billing overcharge',               'I was charged twice for my monthly plan.',                'Complaint', 'In Progress',  'Medium',   'Billing',    'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000010', now()-'4 days'::interval,  now()-'2 days'::interval,  now()-'3 days'::interval,  -0.550, 'Negative',  'Medium',   77.00),
  ('c1000000-0000-0000-0000-000000000003', 'TKT-X003', 'No signal in Fujairah area',       'Complete network outage since yesterday evening.',        'Complaint', 'Unassigned',   'Critical', 'Mobile',     'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000009', NULL,                                   now()-'1 day'::interval,   now()-'1 day'::interval,   NULL,                      -0.880, 'Negative',  'Critical', 91.00),
  ('c1000000-0000-0000-0000-000000000004', 'TKT-X004', 'Router replacement request',       'The router provided 2 years ago is faulty.',             'Inquiry',   'Open',         'Low',      'Hardware',   'a1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000008', now()-'7 days'::interval,  now()-'6 days'::interval,  now()-'6 days'::interval,   0.100, 'Neutral',   'Low',      65.00),
  ('c1000000-0000-0000-0000-000000000005', 'TKT-X005', 'Plan upgrade inquiry',             'Interested in upgrading from 100Mbps to 1Gbps.',          'Inquiry',   'Resolved',     'Low',      'Plan',       'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000003', now()-'10 days'::interval, now()-'8 days'::interval,  now()-'9 days'::interval,   0.420, 'Positive',  'Low',      88.00),
  ('c1000000-0000-0000-0000-000000000006', 'TKT-X006', 'Email service not working',       'Corporate email has been down since this morning.',       'Complaint', 'In Progress',  'High',     'Email',      'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000003', now()-'2 days'::interval,  now()-'1 day'::interval,   now()-'2 days'::interval,  -0.630, 'Negative',  'High',     85.00),
  ('c1000000-0000-0000-0000-000000000007', 'TKT-X007', 'Request for static IP',           'Need a dedicated static IP for our office VPN.',          'Inquiry',   'Open',         'Medium',   'Network',    'a1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000004', now()-'3 days'::interval,  now()-'3 days'::interval,  now()-'3 days'::interval,   0.200, 'Neutral',   'Medium',   72.00),
  ('c1000000-0000-0000-0000-000000000008', 'TKT-X008', 'Intermittent disconnections',     'Connection drops every few hours, very frustrating.',     'Complaint', 'Open',         'High',     'Broadband',  'a1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000004', now()-'6 days'::interval,  now()-'5 days'::interval,  now()-'5 days'::interval,  -0.700, 'Negative',  'High',     80.00),
  ('c1000000-0000-0000-0000-000000000009', 'TKT-X009', 'TV streaming buffering issue',    'IPTV keeps buffering during peak hours.',                 'Complaint', 'Resolved',     'Medium',   'IPTV',       'a1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000003', now()-'15 days'::interval, now()-'12 days'::interval, now()-'14 days'::interval, -0.400, 'Negative',  'Medium',   76.00),
  ('c1000000-0000-0000-0000-000000000010', 'TKT-X010', 'Contract termination request',    'Moving abroad, need to cancel my subscription.',          'Inquiry',   'Resolved',       'Low',      'Account',    'a1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000010', now()-'20 days'::interval, now()-'18 days'::interval, now()-'19 days'::interval,  0.050, 'Neutral',   'Low',      69.00)
ON CONFLICT (ticket_code) DO NOTHING;
COMMIT;

\echo "--- Section 6: TICKET RESOLUTION FEEDBACK ---"
-- =============================================================================
-- 6. TICKET RESOLUTION FEEDBACK
-- =============================================================================
BEGIN;

INSERT INTO ticket_resolution_feedback (ticket_id, employee_user_id, decision, suggested_resolution, employee_resolution, final_resolution) VALUES
  ('c1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000003', 'accepted',        'Upgrade plan to 1Gbps fiber.',                 NULL,                                        'Upgrade plan to 1Gbps fiber.'),
  ('c1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000003', 'accepted',        'Optimise IPTV multicast routing.',             NULL,                                        'Optimise IPTV multicast routing.'),
  ('c1000000-0000-0000-0000-000000000010', 'b1000000-0000-0000-0000-000000000010', 'declined_custom', 'Initiate standard contract termination flow.', 'Waived early termination fee as courtesy.', 'Waived early termination fee as courtesy.'),
  ('c1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000004', 'accepted',        'Replace CPE modem and re-provision line.',      NULL,                                        'Replace CPE modem and re-provision line.'),
  ('c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000004', 'declined_custom', 'Swap CPE device.',                             'Re-provisioned line from exchange side.',    'Re-provisioned line from exchange side.')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 7: TICKET ATTACHMENTS ---"
-- =============================================================================
-- 7. TICKET ATTACHMENTS
-- =============================================================================
BEGIN;

INSERT INTO ticket_attachments (ticket_id, file_name, file_url, uploaded_by) VALUES
  ('c1000000-0000-0000-0000-000000000001', 'speedtest_screenshot.png',  'https://storage.example.com/att/speedtest_screenshot.png',  'b1000000-0000-0000-0000-000000000001'),
  ('c1000000-0000-0000-0000-000000000002', 'invoice_june.pdf',          'https://storage.example.com/att/invoice_june.pdf',          'b1000000-0000-0000-0000-000000000002'),
  ('c1000000-0000-0000-0000-000000000003', 'signal_map.png',            'https://storage.example.com/att/signal_map.png',            'b1000000-0000-0000-0000-000000000009'),
  ('c1000000-0000-0000-0000-000000000006', 'email_error_log.txt',       'https://storage.example.com/att/email_error_log.txt',       'b1000000-0000-0000-0000-000000000002'),
  ('c1000000-0000-0000-0000-000000000008', 'router_logs.zip',           'https://storage.example.com/att/router_logs.zip',           'b1000000-0000-0000-0000-000000000001'),
  ('c1000000-0000-0000-0000-000000000004', 'router_model_photo.jpg',    'https://storage.example.com/att/router_model_photo.jpg',    'b1000000-0000-0000-0000-000000000001')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 8: TICKET UPDATES ---"
-- =============================================================================
-- 8. TICKET UPDATES
-- =============================================================================
BEGIN;

INSERT INTO ticket_updates (ticket_id, author_user_id, update_type, message, from_status, to_status) VALUES
  ('c1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000004', 'status_change',  'Assigned to field team for CPE inspection.',       'Unassigned',   'Open'),
  ('c1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000010', 'status_change',  'Billing team investigating duplicate charge.',      'Open',         'In Progress'),
  ('c1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000003', 'status_change',  'Plan upgrade completed successfully.',              'In Progress',  'Resolved'),
  ('c1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000003', 'comment',        'MX records checked — issue traced to DNS config.', NULL,           NULL),
  ('c1000000-0000-0000-0000-000000000009', 'b1000000-0000-0000-0000-000000000003', 'status_change',  'IPTV routing optimised; customer confirmed fix.',   'In Progress',  'Resolved'),
  ('c1000000-0000-0000-0000-000000000010', 'b1000000-0000-0000-0000-000000000010', 'status_change',  'Contract terminated; final invoice sent.',          'Open',         'Resolved'),
  ('c1000000-0000-0000-0000-000000000008', 'b1000000-0000-0000-0000-000000000004', 'comment',        'Line re-provisioned. Monitoring for 24 hours.',     NULL,           NULL),
  ('c1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000004', 'comment',        'Static IP pool availability confirmed.',            NULL,           NULL)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 9: TICKET WORK STEPS ---"
-- =============================================================================
-- 9. TICKET WORK STEPS
-- =============================================================================
BEGIN;

INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes) VALUES
  ('c1000000-0000-0000-0000-000000000001', 1, 'b1000000-0000-0000-0000-000000000004', 'Remote diagnostic run — CPE shows high error rate.'),
  ('c1000000-0000-0000-0000-000000000001', 2, 'b1000000-0000-0000-0000-000000000008', 'Field visit scheduled for modem swap.'),
  ('c1000000-0000-0000-0000-000000000006', 1, 'b1000000-0000-0000-0000-000000000004', 'MX record TTL issue identified.'),
  ('c1000000-0000-0000-0000-000000000006', 2, 'b1000000-0000-0000-0000-000000000003', 'DNS config corrected, email restored.'),
  ('c1000000-0000-0000-0000-000000000008', 1, 'b1000000-0000-0000-0000-000000000004', 'Exchange port reset performed.'),
  ('c1000000-0000-0000-0000-000000000008', 2, 'b1000000-0000-0000-0000-000000000008', 'Line re-provisioned at DSLAM level.'),
  ('c1000000-0000-0000-0000-000000000009', 1, 'b1000000-0000-0000-0000-000000000003', 'Multicast group config reviewed.'),
  ('c1000000-0000-0000-0000-000000000003', 1, 'b1000000-0000-0000-0000-000000000004', 'BTS site alarm detected — escalated to NOC.')
ON CONFLICT (ticket_id, step_no) DO NOTHING;
COMMIT;

\echo "--- Section 10: APPROVAL REQUESTS ---"
-- =============================================================================
-- 10. APPROVAL REQUESTS
-- =============================================================================
BEGIN;

INSERT INTO approval_requests (
  id, request_code, ticket_id, request_type, current_value,
  requested_value, request_reason, submitted_by_user_id, status,
  decided_by_user_id, decided_at, decision_notes
) VALUES
  ('d1000000-0000-0000-0000-000000000001', 'APR-X001', 'c1000000-0000-0000-0000-000000000002', 'Rescoring', 'Medium', 'High',    'Customer charged twice — financial impact warrants High.', 'b1000000-0000-0000-0000-000000000010', 'Approved',  'b1000000-0000-0000-0000-000000000005', now()-'2 days'::interval,  'Agreed, rescoring to High.'),
  ('d1000000-0000-0000-0000-000000000002', 'APR-X002', 'c1000000-0000-0000-0000-000000000007', 'Rerouting', 'Customer Experience', 'Network Operations', 'Static IP is a network-level task.', 'b1000000-0000-0000-0000-000000000003', 'Approved',  'b1000000-0000-0000-0000-000000000005', now()-'1 day'::interval,   'Correct — rerouting approved.'),
  ('d1000000-0000-0000-0000-000000000003', 'APR-X003', 'c1000000-0000-0000-0000-000000000004', 'Rescoring', 'Low',    'Medium',  'Router fault affecting business operations.',              'b1000000-0000-0000-0000-000000000008', 'Pending',   NULL,                                   NULL,                      NULL),
  ('d1000000-0000-0000-0000-000000000004', 'APR-X004', 'c1000000-0000-0000-0000-000000000008', 'Rescoring', 'High',   'Critical','Repeated disconnections SLA breach imminent.',             'b1000000-0000-0000-0000-000000000004', 'Rejected',  'b1000000-0000-0000-0000-000000000005', now()-'3 days'::interval,  'Current SLA not breached yet.'),
  ('d1000000-0000-0000-0000-000000000005', 'APR-X005', 'c1000000-0000-0000-0000-000000000006', 'Rerouting', 'Customer Experience', 'Enterprise Support', 'Ticket is corporate account.',  'b1000000-0000-0000-0000-000000000003', 'Approved',  'b1000000-0000-0000-0000-000000000005', now()-'1 day'::interval,   'Corporate tier — rerouting approved.')
ON CONFLICT (request_code) DO NOTHING;
COMMIT;

\echo "--- Section 11: CHAT CONVERSATIONS ---"
-- =============================================================================
-- 11. CHAT CONVERSATIONS
-- =============================================================================
BEGIN;

INSERT INTO chat_conversations (id, customer_user_id, channel, status) VALUES
  ('e1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'web',    'closed'),
  ('e1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000002', 'mobile', 'closed'),
  ('e1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000007', 'web',    'open'),
  ('e1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000009', 'mobile', 'closed'),
  ('e1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000001', 'web',    'open'),
  ('e1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000002', 'web',    'closed')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 12: CHAT MESSAGES ---"
-- =============================================================================
-- 12. CHAT MESSAGES
-- =============================================================================
BEGIN;

INSERT INTO chat_messages (conversation_id, sender_type, sender_user_id, message_text, intent, category, sentiment_score, escalation_flag) VALUES
  ('e1000000-0000-0000-0000-000000000001', 'customer', 'b1000000-0000-0000-0000-000000000001', 'My internet has been slow for 3 days!',           'complaint',     'network',  -0.72, FALSE),
  ('e1000000-0000-0000-0000-000000000001', 'bot',      NULL,                                   'I am sorry to hear that. Let me check your line.', 'response',      'network',   0.10, FALSE),
  ('e1000000-0000-0000-0000-000000000001', 'customer', 'b1000000-0000-0000-0000-000000000001', 'I need this fixed today, it is urgent!',           'escalation',    'network',  -0.88, TRUE),
  ('e1000000-0000-0000-0000-000000000002', 'customer', 'b1000000-0000-0000-0000-000000000002', 'I was charged twice this month.',                  'billing',       'billing',  -0.55, FALSE),
  ('e1000000-0000-0000-0000-000000000002', 'bot',      NULL,                                   'I can see your billing history. Let me review.',   'response',      'billing',   0.05, FALSE),
  ('e1000000-0000-0000-0000-000000000003', 'customer', 'b1000000-0000-0000-0000-000000000007', 'How do I upgrade my plan?',                        'inquiry',       'plan',      0.40, FALSE),
  ('e1000000-0000-0000-0000-000000000003', 'bot',      NULL,                                   'Great choice! Here are our available plans.',      'response',      'plan',      0.60, FALSE),
  ('e1000000-0000-0000-0000-000000000004', 'customer', 'b1000000-0000-0000-0000-000000000009', 'No signal at all in my area!',                     'complaint',     'mobile',   -0.85, TRUE),
  ('e1000000-0000-0000-0000-000000000005', 'customer', 'b1000000-0000-0000-0000-000000000001', 'Is there an outage in my area?',                   'inquiry',       'network',  -0.20, FALSE),
  ('e1000000-0000-0000-0000-000000000006', 'customer', 'b1000000-0000-0000-0000-000000000002', 'I want to cancel my contract.',                    'cancellation',  'account',  -0.10, FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 13: SESSIONS ---"
-- =============================================================================
-- 13. SESSIONS
-- =============================================================================
BEGIN;

INSERT INTO sessions (session_id, user_id, current_state, context, history, bot_model_version, escalated_to_human) VALUES
  ('f1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'resolved',   '{"intent":"complaint","category":"network"}'::jsonb,  '[]'::jsonb, 'v2.1.0', FALSE),
  ('f1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000002', 'resolved',   '{"intent":"billing","category":"billing"}'::jsonb,    '[]'::jsonb, 'v2.1.0', FALSE),
  ('f1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000007', 'greeting',   '{"intent":"inquiry","category":"plan"}'::jsonb,       '[]'::jsonb, 'v2.1.0', FALSE),
  ('f1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000009', 'escalated',  '{"intent":"complaint","category":"mobile"}'::jsonb,   '[]'::jsonb, 'v2.0.5', TRUE),
  ('f1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000001', 'awaiting',   '{"intent":"inquiry","category":"network"}'::jsonb,    '[]'::jsonb, 'v2.1.0', FALSE),
  ('f1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000002', 'resolved',   '{"intent":"cancellation","category":"account"}'::jsonb,'[]'::jsonb, 'v2.1.0', FALSE),
  ('f1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000003', 'resolved',   '{"intent":"inquiry","category":"general"}'::jsonb,    '[]'::jsonb, 'v2.1.0', FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 14: USER CHAT LOGS ---"
-- =============================================================================
-- 14. USER CHAT LOGS
-- =============================================================================
BEGIN;

INSERT INTO user_chat_logs (session_id, user_id, message, intent_detected, aggression_flag, aggression_score, sentiment_score, category) VALUES
  ('f1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'My internet is slow for 3 days!',           'complaint',     FALSE, 0.1200, -0.720, 'network'),
  ('f1000000-0000-0000-0000-000000000001', 'b1000000-0000-0000-0000-000000000001', 'I need this fixed today urgently!',         'escalation',    TRUE,  0.6800, -0.880, 'network'),
  ('f1000000-0000-0000-0000-000000000002', 'b1000000-0000-0000-0000-000000000002', 'I was charged double this month!',          'billing',       FALSE, 0.2100, -0.550, 'billing'),
  ('f1000000-0000-0000-0000-000000000003', 'b1000000-0000-0000-0000-000000000007', 'How do I upgrade my internet plan?',        'inquiry',       FALSE, 0.0000,  0.400, 'plan'),
  ('f1000000-0000-0000-0000-000000000004', 'b1000000-0000-0000-0000-000000000009', 'No signal at all in Fujairah!',             'complaint',     TRUE,  0.7500, -0.850, 'mobile'),
  ('f1000000-0000-0000-0000-000000000005', 'b1000000-0000-0000-0000-000000000001', 'Is there an outage in my area?',            'inquiry',       FALSE, 0.0000, -0.200, 'network'),
  ('f1000000-0000-0000-0000-000000000006', 'b1000000-0000-0000-0000-000000000002', 'I want to cancel my subscription.',         'cancellation',  FALSE, 0.0500, -0.100, 'account'),
  ('f1000000-0000-0000-0000-000000000007', 'b1000000-0000-0000-0000-000000000003', 'What are your business support hours?',     'inquiry',       FALSE, 0.0000,  0.300, 'general')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 15: BOT RESPONSE LOGS ---"
-- =============================================================================
-- 15. BOT RESPONSE LOGS
-- =============================================================================
BEGIN;

INSERT INTO bot_response_logs (session_id, response, response_type, state_at_time, kb_match_score) VALUES
  ('f1000000-0000-0000-0000-000000000001', 'I have logged a complaint and a technician will contact you within 4 hours.',  'resolution',  'complaint',    0.92300),
  ('f1000000-0000-0000-0000-000000000002', 'I can see a duplicate charge on your account. I will escalate this now.',       'escalation',  'billing',      0.88500),
  ('f1000000-0000-0000-0000-000000000003', 'Here are our available plans: 100Mbps, 500Mbps, and 1Gbps fibre options.',      'info',        'plan_inquiry', 0.95100),
  ('f1000000-0000-0000-0000-000000000004', 'There is a known outage in your area. Our team is working on it.',              'status',      'outage',       0.78200),
  ('f1000000-0000-0000-0000-000000000005', 'Let me check for outages in your area. One moment please.',                     'lookup',      'inquiry',      0.83000),
  ('f1000000-0000-0000-0000-000000000006', 'I have initiated the cancellation process. You will receive a confirmation.',   'action',      'cancellation', 0.89700),
  ('f1000000-0000-0000-0000-000000000007', 'Our business support is available Sunday to Thursday, 8AM to 8PM GST.',         'info',        'inquiry',      0.96000)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 16: NOTIFICATIONS ---"
-- =============================================================================
-- 16. NOTIFICATIONS
-- =============================================================================
BEGIN;

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'status_change',  'Ticket TKT-X001 Assigned',       'Your complaint has been assigned to a technician.',          'High',     'c1000000-0000-0000-0000-000000000001', TRUE),
  ('b1000000-0000-0000-0000-000000000002', 'status_change',  'Ticket TKT-X002 In Progress',    'The billing team is reviewing your overcharge complaint.',    'Medium',   'c1000000-0000-0000-0000-000000000002', FALSE),
  ('b1000000-0000-0000-0000-000000000007', 'status_change',  'Ticket TKT-X005 Resolved',       'Your plan upgrade has been completed.',                       'Low',      'c1000000-0000-0000-0000-000000000005', TRUE),
  ('b1000000-0000-0000-0000-000000000005', 'system',       'Rescoring Request — TKT-X002',   'Dan submitted a rescoring request for TKT-X002.',             'Medium',   'c1000000-0000-0000-0000-000000000002', TRUE),
  ('b1000000-0000-0000-0000-000000000004', 'ticket_assignment',     'New Ticket Assigned: TKT-X001',  'You have been assigned ticket TKT-X001.',                     'High',     'c1000000-0000-0000-0000-000000000001', FALSE),
  ('b1000000-0000-0000-0000-000000000009', 'sla_warning',     'SLA Warning: TKT-X003',          'Ticket TKT-X003 is approaching SLA breach.',                  'Critical', 'c1000000-0000-0000-0000-000000000003', FALSE),
  ('b1000000-0000-0000-0000-000000000003', 'ticket_assignment',     'New Ticket Assigned: TKT-X006',  'You have been assigned ticket TKT-X006.',                     'High',     'c1000000-0000-0000-0000-000000000006', TRUE),
  ('b1000000-0000-0000-0000-000000000010', 'status_change',  'Ticket TKT-X010 Closed',         'Contract termination for TKT-X010 has been completed.',       'Low',      'c1000000-0000-0000-0000-000000000010', TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 17: EMPLOYEE REPORTS ---"
-- =============================================================================
-- 17. EMPLOYEE REPORTS
-- =============================================================================
BEGIN;

INSERT INTO employee_reports (id, report_code, employee_user_id, month_label, subtitle, kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response) VALUES
  ('91000000-0000-0000-0000-000000000001', 'RPT-X001', 'b1000000-0000-0000-0000-000000000003', 'February 2026', 'Strong month with high resolution rate',   'A',  38, '94%', '1h 22m'),
  ('91000000-0000-0000-0000-000000000002', 'RPT-X002', 'b1000000-0000-0000-0000-000000000004', 'February 2026', 'Improved response times for network issues', 'B+', 29, '88%', '2h 05m'),
  ('91000000-0000-0000-0000-000000000003', 'RPT-X003', 'b1000000-0000-0000-0000-000000000008', 'February 2026', 'Field visits completed ahead of schedule',   'A-', 22, '91%', '3h 15m'),
  ('91000000-0000-0000-0000-000000000004', 'RPT-X004', 'b1000000-0000-0000-0000-000000000010', 'February 2026', 'Billing resolution accuracy at all-time high','A',  41, '96%', '0h 55m'),
  ('91000000-0000-0000-0000-000000000005', 'RPT-X005', 'b1000000-0000-0000-0000-000000000003', 'January 2026',  'Steady performance, some SLA near-misses',   'B',  34, '85%', '1h 45m')
ON CONFLICT (report_code) DO NOTHING;
COMMIT;

\echo "--- Section 18: EMPLOYEE REPORT SUMMARY ITEMS ---"
-- =============================================================================
-- 18. EMPLOYEE REPORT SUMMARY ITEMS
-- =============================================================================
BEGIN;

INSERT INTO employee_report_summary_items (report_id, label, value_text) VALUES
  ('91000000-0000-0000-0000-000000000001', 'Tickets Resolved',    '38'),
  ('91000000-0000-0000-0000-000000000001', 'SLA Compliance',      '94%'),
  ('91000000-0000-0000-0000-000000000001', 'CSAT Score',          '4.7 / 5'),
  ('91000000-0000-0000-0000-000000000002', 'Tickets Resolved',    '29'),
  ('91000000-0000-0000-0000-000000000002', 'SLA Compliance',      '88%'),
  ('91000000-0000-0000-0000-000000000003', 'Field Visits',        '15'),
  ('91000000-0000-0000-0000-000000000004', 'Tickets Resolved',    '41'),
  ('91000000-0000-0000-0000-000000000004', 'Billing Accuracy',    '99.2%'),
  ('91000000-0000-0000-0000-000000000005', 'Tickets Resolved',    '34'),
  ('91000000-0000-0000-0000-000000000005', 'SLA Near-Misses',     '4')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 19: EMPLOYEE REPORT RATING COMPONENTS ---"
-- =============================================================================
-- 19. EMPLOYEE REPORT RATING COMPONENTS
-- =============================================================================
BEGIN;

INSERT INTO employee_report_rating_components (report_id, name, score, pct) VALUES
  ('91000000-0000-0000-0000-000000000001', 'Resolution Speed',   4.8, 96),
  ('91000000-0000-0000-0000-000000000001', 'Customer Feedback',  4.7, 94),
  ('91000000-0000-0000-0000-000000000001', 'SLA Adherence',      4.5, 90),
  ('91000000-0000-0000-0000-000000000002', 'Resolution Speed',   4.0, 80),
  ('91000000-0000-0000-0000-000000000002', 'Technical Accuracy', 4.3, 86),
  ('91000000-0000-0000-0000-000000000003', 'Field Efficiency',   4.4, 88),
  ('91000000-0000-0000-0000-000000000004', 'Billing Accuracy',   4.9, 98),
  ('91000000-0000-0000-0000-000000000004', 'Customer Feedback',  4.6, 92)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 20: EMPLOYEE REPORT WEEKLY ---"
-- =============================================================================
-- 20. EMPLOYEE REPORT WEEKLY
-- =============================================================================
BEGIN;

INSERT INTO employee_report_weekly (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text) VALUES
  ('91000000-0000-0000-0000-000000000001', 'Week 1 Feb', 10, 10, '95%', '1h 18m', 'positive', '+2 vs prev'),
  ('91000000-0000-0000-0000-000000000001', 'Week 2 Feb', 11,  9, '91%', '1h 35m', 'neutral',  '=0 vs prev'),
  ('91000000-0000-0000-0000-000000000001', 'Week 3 Feb',  9, 10, '96%', '1h 10m', 'positive', '+1 vs prev'),
  ('91000000-0000-0000-0000-000000000001', 'Week 4 Feb',  8,  9, '94%', '1h 22m', 'neutral',  '=0 vs prev'),
  ('91000000-0000-0000-0000-000000000002', 'Week 1 Feb',  8,  7, '88%', '2h 10m', 'neutral',  '=0 vs prev'),
  ('91000000-0000-0000-0000-000000000002', 'Week 2 Feb',  7,  8, '89%', '1h 55m', 'positive', '+1 vs prev'),
  ('91000000-0000-0000-0000-000000000004', 'Week 1 Feb', 11, 11, '97%', '0h 50m', 'positive', '+3 vs prev'),
  ('91000000-0000-0000-0000-000000000004', 'Week 2 Feb', 10, 10, '95%', '0h 58m', 'neutral',  '=0 vs prev')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 21: EMPLOYEE REPORT NOTES ---"
-- =============================================================================
-- 21. EMPLOYEE REPORT NOTES
-- =============================================================================
BEGIN;

INSERT INTO employee_report_notes (report_id, note) VALUES
  ('91000000-0000-0000-0000-000000000001', 'Carol maintained the highest CSAT score on the team for February.'),
  ('91000000-0000-0000-0000-000000000001', 'Recommended for employee of the month nomination.'),
  ('91000000-0000-0000-0000-000000000002', 'Dan improved average response time by 18% vs January.'),
  ('91000000-0000-0000-0000-000000000003', 'All 15 field visits completed within scheduled windows.'),
  ('91000000-0000-0000-0000-000000000004', 'James achieved highest ticket resolution count this month.'),
  ('91000000-0000-0000-0000-000000000005', 'Carol had 4 SLA near-misses — coaching session scheduled.')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 22: SYSTEM SERVICE STATUS ---"
-- =============================================================================
-- 22. SYSTEM SERVICE STATUS
-- =============================================================================
BEGIN;

INSERT INTO system_service_status (name, status, severity, note) VALUES
  ('Core API',           'Operational',     'ok',       'All endpoints responding normally'),
  ('Database Cluster',   'Operational',     'ok',       'Primary + replica in sync'),
  ('Email Gateway',      'Degraded',        'warning',  'SMTP relay latency elevated — monitoring'),
  ('AI Pipeline',        'Operational',     'ok',       'All 6 agents running'),
  ('File Storage',       'Operational',     'ok',       'S3-compatible storage healthy'),
  ('Auth Service',       'Operational',     'ok',       'Token issuance normal'),
  ('Notification Queue', 'Operational',     'ok',       'Queue depth nominal')
ON CONFLICT (name) DO UPDATE
  SET status = EXCLUDED.status, severity = EXCLUDED.severity,
      note = EXCLUDED.note, checked_at = now();
COMMIT;

\echo "--- Section 23: SYSTEM INTEGRATION STATUS ---"
-- =============================================================================
-- 23. SYSTEM INTEGRATION STATUS
-- =============================================================================
BEGIN;

INSERT INTO system_integration_status (name, status, severity, note) VALUES
  ('CRM Connector',      'Connected',       'ok',       'Last sync 5 minutes ago'),
  ('Billing System',     'Connected',       'ok',       'Invoice API responding'),
  ('SMS Gateway',        'Degraded',        'warning',  'Delivery rate dropped to 87%'),
  ('ERP Integration',    'Connected',       'ok',       'Order feed active'),
  ('LDAP / AD',          'Connected',       'ok',       'Directory sync healthy'),
  ('Webhook Dispatcher', 'Operational',     'ok',       'All webhooks firing normally')
ON CONFLICT (name) DO UPDATE
  SET status = EXCLUDED.status, severity = EXCLUDED.severity,
      note = EXCLUDED.note, checked_at = now();
COMMIT;

\echo "--- Section 24: SYSTEM QUEUE METRICS ---"
-- =============================================================================
-- 24. SYSTEM QUEUE METRICS
-- =============================================================================
BEGIN;

INSERT INTO system_queue_metrics (name, value, severity, note) VALUES
  ('Unassigned Tickets',  '7',   'warning', '3 approaching SLA breach'),
  ('Pending Approvals',   '1',   'ok',      'Within normal range'),
  ('AI Queue Backlog',    '0',   'ok',      'No backlog'),
  ('Email Queue Depth',   '142', 'warning', 'Higher than usual — monitoring'),
  ('Notification Queue',  '23',  'ok',      'Processing normally')
ON CONFLICT (name) DO UPDATE
  SET value = EXCLUDED.value, severity = EXCLUDED.severity,
      note = EXCLUDED.note, measured_at = now();
COMMIT;

\echo "--- Section 25: SYSTEM EVENT FEED ---"
-- =============================================================================
-- 25. SYSTEM EVENT FEED
-- =============================================================================
BEGIN;

INSERT INTO system_event_feed (severity, title, description) VALUES
  ('info',     'Scheduled Maintenance Complete',  'Database cluster maintenance window completed successfully at 02:00 GST.'),
  ('warning',  'Email Gateway Latency Spike',     'SMTP relay latency exceeded 500ms threshold. Team notified.'),
  ('info',     'AI Pipeline Restarted',           'AI pipeline restarted after config update. All agents running.'),
  ('critical', 'Network Outage — Fujairah',       'BTS site alarm triggered. NOC dispatched field team.'),
  ('info',     'New Model Version Deployed',      'Sentiment agent updated to v2.1.0 with improved Arabic language support.'),
  ('warning',  'SMS Delivery Rate Drop',          'SMS gateway delivery rate dropped to 87%. Investigating provider issue.'),
  ('info',     'Backup Completed',                'Daily database backup completed. Stored to offsite S3 bucket.')
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 26: SYSTEM VERSIONS ---"
-- =============================================================================
-- 26. SYSTEM VERSIONS
-- =============================================================================
BEGIN;

INSERT INTO system_versions (component, version, deployed_at) VALUES
  ('Backend API',          'v3.4.2',  '2026-02-15'),
  ('Frontend Web',         'v2.8.1',  '2026-02-20'),
  ('AI Pipeline',          'v2.1.0',  '2026-03-01'),
  ('Database Schema',      'v1.9.0',  '2026-01-28'),
  ('Mobile App (iOS)',     'v4.1.3',  '2026-02-10'),
  ('Mobile App (Android)', 'v4.1.2',  '2026-02-12')
ON CONFLICT (component) DO UPDATE
  SET version = EXCLUDED.version, deployed_at = EXCLUDED.deployed_at;
COMMIT;

\echo "--- Section 27: SYSTEM CONFIG KV ---"
-- =============================================================================
-- 27. SYSTEM CONFIG KV
-- =============================================================================
BEGIN;

INSERT INTO system_config_kv (key, value) VALUES
  ('sla.respond.high_hours',     '4'),
  ('sla.respond.critical_hours', '1'),
  ('sla.resolve.high_hours',     '24'),
  ('sla.resolve.critical_hours', '8'),
  ('ai.sentiment.threshold',     '0.5'),
  ('ai.priority.auto_apply',     'true'),
  ('chat.escalation_score',      '0.75'),
  ('notifications.email.enabled','true')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
COMMIT;

\echo "--- Section 28: MODEL EXECUTION LOG ---"
-- =============================================================================
-- 28. MODEL EXECUTION LOG
-- =============================================================================
BEGIN;

INSERT INTO model_execution_log (
  id, execution_id, ticket_id, agent_name, model_version,
  triggered_by, started_at, completed_at, status,
  input_token_count, output_token_count, inference_time_ms, confidence_score, error_flag
) VALUES
  ('81000000-0000-0000-0000-000000000001', '82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'5 days'::interval,  now()-'5 days'::interval+interval'1.2s',  'success', 312, 48,  1200, 0.9120, FALSE),
  ('81000000-0000-0000-0000-000000000002', '82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'priority',    'priority-v1.8.0',    'ingest',    now()-'5 days'::interval,  now()-'5 days'::interval+interval'0.9s',  'success', 280, 36,   900, 0.8250, FALSE),
  ('81000000-0000-0000-0000-000000000003', '82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'4 days'::interval,  now()-'4 days'::interval+interval'1.1s',  'success', 295, 45,  1100, 0.8750, FALSE),
  ('81000000-0000-0000-0000-000000000004', '82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'routing',     'routing-v1.5.2',     'ingest',    now()-'4 days'::interval,  now()-'4 days'::interval+interval'0.8s',  'success', 260, 40,   800, 0.7700, FALSE),
  ('81000000-0000-0000-0000-000000000005', '82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'sentiment',   'sentiment-v2.1.0',   'ingest',    now()-'1 day'::interval,   now()-'1 day'::interval+interval'1.3s',   'success', 330, 52,  1300, 0.9400, FALSE),
  ('81000000-0000-0000-0000-000000000006', '82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'priority',    'priority-v1.8.0',    'ingest',    now()-'1 day'::interval,   now()-'1 day'::interval+interval'1.0s',   'success', 290, 42,  1000, 0.9100, FALSE),
  ('81000000-0000-0000-0000-000000000007', '82000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000006', 'feature',     'feature-v1.2.0',     'ingest',    now()-'2 days'::interval,  now()-'2 days'::interval+interval'2.1s',  'success', 410, 80,  2100, 0.8300, FALSE),
  ('81000000-0000-0000-0000-000000000008', '82000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000008', 'sla',         'sla-v1.3.1',         'ingest',    now()-'6 days'::interval,  now()-'6 days'::interval+interval'0.6s',  'success', 200, 30,   600, 0.8800, FALSE),
  ('81000000-0000-0000-0000-000000000009', '82000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000009', 'resolution',  'resolution-v1.6.0',  'ingest',    now()-'13 days'::interval, now()-'13 days'::interval+interval'1.8s', 'success', 380, 70,  1800, 0.8500, FALSE),
  ('81000000-0000-0000-0000-000000000010', '82000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000004', 'sentiment',   'sentiment-v2.0.5',   'reprocess', now()-'7 days'::interval,  now()-'7 days'::interval+interval'1.0s',  'success', 270, 40,  1000, 0.6500, FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 29: SENTIMENT OUTPUTS ---"
-- =============================================================================
-- 29. SENTIMENT OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO sentiment_outputs (execution_id, ticket_id, model_version, sentiment_label, sentiment_score, confidence_score, emotion_tags, raw_scores, is_current) VALUES
  ('81000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment-v2.1.0', 'Negative',  -0.7200, 0.9120, ARRAY['frustration','urgency'],   '{"negative":0.912,"neutral":0.071,"positive":0.017}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000002', 'sentiment-v2.1.0', 'Negative',  -0.5500, 0.8750, ARRAY['frustration'],              '{"negative":0.875,"neutral":0.100,"positive":0.025}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'sentiment-v2.1.0', 'Negative',  -0.8800, 0.9400, ARRAY['anger','urgency'],          '{"negative":0.940,"neutral":0.042,"positive":0.018}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'sentiment-v2.0.5', 'Neutral',    0.1000, 0.6500, ARRAY['neutral'],                  '{"negative":0.200,"neutral":0.650,"positive":0.150}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009', 'sentiment-v2.1.0', 'Negative',  -0.4000, 0.8500, ARRAY['frustration'],              '{"negative":0.850,"neutral":0.110,"positive":0.040}'::jsonb, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 30: PRIORITY OUTPUTS ---"
-- =============================================================================
-- 30. PRIORITY OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO priority_outputs (execution_id, ticket_id, model_version, suggested_priority, confidence_score, reasoning, is_current) VALUES
  ('81000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'priority-v1.8.0', 'High',     0.8250, 'Prolonged broadband outage with high negative sentiment.', TRUE),
  ('81000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000003', 'priority-v1.8.0', 'Critical', 0.9100, 'Complete mobile outage affecting entire area.',            TRUE),
  ('81000000-0000-0000-0000-000000000010', 'c1000000-0000-0000-0000-000000000004', 'priority-v1.8.0', 'Low',      0.6500, 'Hardware inquiry, no immediate service impact.',           TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 31: ROUTING OUTPUTS ---"
-- =============================================================================
-- 31. ROUTING OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO routing_outputs (execution_id, ticket_id, model_version, suggested_department_id, confidence_score, reasoning, is_current) VALUES
  ('81000000-0000-0000-0000-000000000004', 'c1000000-0000-0000-0000-000000000002', 'routing-v1.5.2', 'a1000000-0000-0000-0000-000000000003', 0.7700, 'Billing overcharge requires Billing & Finance team.',  TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 32: SLA OUTPUTS ---"
-- =============================================================================
-- 32. SLA OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO sla_outputs (execution_id, ticket_id, model_version, predicted_respond_mins, predicted_resolve_mins, breach_risk, confidence_score, is_current) VALUES
  ('81000000-0000-0000-0000-000000000008', 'c1000000-0000-0000-0000-000000000008', 'sla-v1.3.1', 240,  1080, 0.6200, 0.8800, TRUE),
  ('81000000-0000-0000-0000-000000000006', 'c1000000-0000-0000-0000-000000000003', 'sla-v1.3.1',  30,   480, 0.9500, 0.9100, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 33: RESOLUTION OUTPUTS ---"
-- =============================================================================
-- 33. RESOLUTION OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO resolution_outputs (execution_id, ticket_id, model_version, suggested_text, kb_references, confidence_score, is_current) VALUES
  ('81000000-0000-0000-0000-000000000009', 'c1000000-0000-0000-0000-000000000009', 'resolution-v1.6.0', 'Optimise IPTV multicast routing configuration at exchange level.', ARRAY['KB-0041','KB-0088'], 0.8500, TRUE),
  ('81000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000001', 'resolution-v1.6.0', 'Replace CPE modem and re-provision the DSL line.',                 ARRAY['KB-0012','KB-0034'], 0.8200, TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 34: FEATURE OUTPUTS ---"
-- =============================================================================
-- 34. FEATURE OUTPUTS
-- =============================================================================
BEGIN;

INSERT INTO feature_outputs (execution_id, ticket_id, model_version, asset_category, topic_labels, confidence_score, raw_features, is_current) VALUES
  ('81000000-0000-0000-0000-000000000007', 'c1000000-0000-0000-0000-000000000006', 'feature-v1.2.0', 'Email',   ARRAY['email','corporate','outage'],  0.8300, '{"is_recurring":false,"language":"en","word_count":12}'::jsonb, TRUE),
  ('81000000-0000-0000-0000-000000000005', 'c1000000-0000-0000-0000-000000000003', 'feature-v1.2.0', 'Mobile',  ARRAY['mobile','outage','area-wide'],  0.9200, '{"is_recurring":false,"language":"en","word_count":9}'::jsonb,  TRUE)
ON CONFLICT DO NOTHING;
COMMIT;

\echo "--- Section 35: AGENT OUTPUT LOG ---"
-- =============================================================================
-- 35. AGENT OUTPUT LOG
-- =============================================================================
BEGIN;

INSERT INTO agent_output_log (execution_id, ticket_id, agent_name, step_order, input_state, output_state, state_diff, inference_time_ms, error_flag) VALUES
  ('82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'sentiment',  1, '{"text":"My internet is slow for 3 days!"}'::jsonb,        '{"label":"Negative","score":-0.72}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1200, FALSE),
  ('82000000-0000-0000-0000-000000000001', 'c1000000-0000-0000-0000-000000000001', 'priority',   2, '{"sentiment":"Negative","category":"network"}'::jsonb,     '{"priority":"High","confidence":0.825}'::jsonb,       '{"priority":"High"}'::jsonb,                       900, FALSE),
  ('82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'sentiment',  1, '{"text":"I was charged double this month!"}'::jsonb,        '{"label":"Negative","score":-0.55}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1100, FALSE),
  ('82000000-0000-0000-0000-000000000002', 'c1000000-0000-0000-0000-000000000002', 'routing',    3, '{"category":"billing","department":"customer_exp"}'::jsonb, '{"department_id":"billing_dept","confidence":0.77}'::jsonb,'{"department":"Billing & Finance"}'::jsonb,     800, FALSE),
  ('82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'sentiment',  1, '{"text":"No signal at all in Fujairah!"}'::jsonb,           '{"label":"Negative","score":-0.88}'::jsonb,           '{"sentiment_label":"Negative"}'::jsonb,           1300, FALSE),
  ('82000000-0000-0000-0000-000000000003', 'c1000000-0000-0000-0000-000000000003', 'priority',   2, '{"sentiment":"Negative","category":"mobile"}'::jsonb,      '{"priority":"Critical","confidence":0.91}'::jsonb,    '{"priority":"Critical"}'::jsonb,                  1000, FALSE)
ON CONFLICT DO NOTHING;
COMMIT;

-- =============================================================================
-- PASSWORD RESET TOKENS (a few for testing)
-- =============================================================================
BEGIN;
INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used_at) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'abc123tokenhashalice',  now()+interval'1 hour',  NULL),
  ('b1000000-0000-0000-0000-000000000007', 'def456tokenhashgrace',  now()-interval'2 hours', now()-interval'1 hour')
ON CONFLICT DO NOTHING;
COMMIT;

-- =============================================================================
-- Refresh materialized views with the new data
-- =============================================================================
SELECT refresh_analytics_mvs();