-- =============================================================================
-- InnovaCX — Analytics MV Seed Data Extension
-- Appends to seedV2.sql output — run AFTER seedV2.sql and analytics_mvs.sql
--
-- PURPOSE: Ensure every materialized view has rich, realistic data to display.
--   mv_ticket_base          → sourced from tickets (already seeded in seedV2)
--   mv_daily_volume         → sourced from mv_ticket_base
--   mv_employee_daily       → sourced from mv_ticket_base
--   mv_acceptance_daily     → sourced from suggested_resolution_usage
--   mv_operator_qc_daily    → sourced from tickets + approval_requests
--   mv_chatbot_daily        → sourced from sessions + user_chat_logs
--   mv_sentiment_daily      → sourced from sentiment_outputs
--   mv_feature_daily        → sourced from feature_outputs
--
-- All inserts use ON CONFLICT … DO NOTHING so safe to re-run.
-- =============================================================================

BEGIN;

-- =============================================================================
-- EXTEND TICKETS: Add more tickets across more dates/departments/employees
-- so the trend charts in ComplaintTrends and ModelHealth have volume to show.
-- These span the last 12 months and cover all departments.
-- =============================================================================

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

-- ── February 2026 (dense month for QC data) ──────────────────────────────────
('CX-F001', 'Lift motor overheating – Tower 1',
 'Lift motor in Tower 1 reaching dangerous temperatures. Passengers reporting smell of burning.',
 'Complaint', 'Resolved', 'Critical',
 'Elevator', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-02-03 07:00:00+00', '2026-02-03 07:08:00+00', '2026-02-03 07:22:00+00', '2026-02-03 15:00:00+00',
 '2026-02-03 07:30:00+00', '2026-02-03 19:00:00+00',
 FALSE, FALSE, '2026-02-03 07:00:00+00',
 -0.82, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 96.00,
 'Shut down lift immediately; inspect motor cooling and replace thermal relay.',
 FALSE, FALSE),

('CX-F002', 'Biometric entry system failure – HR floor',
 'Biometric readers on HR floor rejecting all fingerprints since morning system update.',
 'Complaint', 'Resolved', 'High',
 'Access Control', (SELECT id FROM departments WHERE name='HR'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='lena@innovacx.net'),
 '2026-02-05 08:30:00+00', '2026-02-05 08:45:00+00', '2026-02-05 09:05:00+00', '2026-02-05 17:00:00+00',
 '2026-02-05 09:30:00+00', '2026-02-06 08:30:00+00',
 FALSE, FALSE, '2026-02-05 08:30:00+00',
 -0.55, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='HR'), 88.00,
 'Roll back firmware update and re-enrol user fingerprints.',
 FALSE, FALSE),

('CX-F003', 'Cold water supply disrupted – Floor 3',
 'Cold water taps on Floor 3 producing no flow. Overhead tank valve may be stuck.',
 'Complaint', 'Resolved', 'High',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2026-02-07 09:00:00+00', '2026-02-07 09:20:00+00', '2026-02-07 09:48:00+00', '2026-02-07 18:00:00+00',
 '2026-02-07 10:00:00+00', '2026-02-08 09:00:00+00',
 FALSE, FALSE, '2026-02-07 09:00:00+00',
 -0.42, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Maintenance'), 85.00,
 'Open stuck valve at rooftop tank; flush pipes and restore flow.',
 FALSE, FALSE),

('CX-F004', 'Printer room exhaust fan broken – Admin',
 'Exhaust fan in admin printer room seized. Toner fumes accumulating.',
 'Inquiry', 'Resolved', 'Medium',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-02-10 10:00:00+00', '2026-02-10 10:25:00+00', '2026-02-10 11:00:00+00', '2026-02-11 14:00:00+00',
 '2026-02-10 13:00:00+00', '2026-02-12 10:00:00+00',
 FALSE, FALSE, '2026-02-10 10:00:00+00',
 -0.22, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Facilities Management'), 78.00,
 'Replace exhaust fan motor and verify adequate ventilation.',
 FALSE, FALSE),

('CX-F005', 'Recurring: CCTV dead zone – parking level B1',
 'Camera 14 on B1 parking level has a persistent blind spot. Third report this quarter.',
 'Complaint', 'Resolved', 'Medium',
 'CCTV', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-02-12 11:00:00+00', '2026-02-12 11:18:00+00', '2026-02-12 12:00:00+00', '2026-02-13 16:00:00+00',
 '2026-02-12 14:00:00+00', '2026-02-14 11:00:00+00',
 FALSE, FALSE, '2026-02-12 11:00:00+00',
 -0.35, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='Safety & Security'), 80.00,
 'Reposition camera bracket 15° left; verify coverage with monitoring room.',
 FALSE, TRUE),

('CX-F006', 'UPS bypass switch stuck – data closet L2',
 'UPS bypass switch on L2 data closet jammed. Cannot perform scheduled maintenance.',
 'Complaint', 'Resolved', 'High',
 'Electrical', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2026-02-17 08:00:00+00', '2026-02-17 08:15:00+00', '2026-02-17 08:50:00+00', '2026-02-17 16:00:00+00',
 '2026-02-17 09:00:00+00', '2026-02-18 08:00:00+00',
 FALSE, FALSE, '2026-02-17 08:00:00+00',
 -0.48, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='IT'), 87.00,
 'Manually disengage bypass; replace actuator mechanism.',
 FALSE, FALSE),

('CX-F007', 'Mould visible – Meeting Room 5B ceiling',
 'Moisture and mould on ceiling tiles in 5B. Staff reporting allergic symptoms.',
 'Complaint', 'Resolved', 'High',
 'Civil', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-02-19 09:00:00+00', '2026-02-19 09:20:00+00', '2026-02-19 10:00:00+00', '2026-02-21 12:00:00+00',
 '2026-02-19 10:00:00+00', '2026-02-21 09:00:00+00',
 FALSE, FALSE, '2026-02-19 09:00:00+00',
 -0.52, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 84.00,
 'Replace ceiling tiles; seal water ingress point; apply anti-mould treatment.',
 FALSE, FALSE),

('CX-F008', 'Intercom failure – all visitor entry points',
 'Building intercom panels at all 3 visitor entry points producing no audio.',
 'Complaint', 'Resolved', 'Critical',
 'Communications', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-02-22 07:00:00+00', '2026-02-22 07:10:00+00', '2026-02-22 07:28:00+00', '2026-02-22 15:00:00+00',
 '2026-02-22 07:30:00+00', '2026-02-22 19:00:00+00',
 FALSE, FALSE, '2026-02-22 07:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 95.00,
 'Replace intercom central controller unit; test all entry panels.',
 FALSE, FALSE),

('CX-F009', 'AHU filter blocked – Wing C ventilation',
 'Air handling unit in Wing C has a blocked filter. CO2 levels elevated.',
 'Complaint', 'Resolved', 'High',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-02-24 08:00:00+00', '2026-02-24 08:12:00+00', '2026-02-24 08:45:00+00', '2026-02-24 17:00:00+00',
 '2026-02-24 09:00:00+00', '2026-02-25 08:00:00+00',
 FALSE, FALSE, '2026-02-24 08:00:00+00',
 -0.45, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 91.00,
 'Replace AHU filter immediately; schedule quarterly maintenance.',
 FALSE, FALSE),

('CX-F010', 'Leasing portal login broken – external users',
 'External users unable to log into leasing portal. SSL certificate issue suspected.',
 'Complaint', 'Resolved', 'Critical',
 'Software', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2026-02-26 09:00:00+00', '2026-02-26 09:08:00+00', '2026-02-26 09:25:00+00', '2026-02-26 14:00:00+00',
 '2026-02-26 09:30:00+00', '2026-02-26 21:00:00+00',
 FALSE, FALSE, '2026-02-26 09:00:00+00',
 -0.60, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Leasing'), 93.00,
 'Renew expired SSL certificate; flush CDN cache and verify portal access.',
 FALSE, FALSE),

-- ── January 2026 ──────────────────────────────────────────────────────────────
('CX-J001', 'Fluorescent lights flickering – corridor B2',
 'Flickering lights in B2 corridor causing migraines for staff. Ballast fault suspected.',
 'Complaint', 'Resolved', 'Medium',
 'Electrical', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-01-05 09:00:00+00', '2026-01-05 09:30:00+00', '2026-01-05 10:15:00+00', '2026-01-06 14:00:00+00',
 '2026-01-05 12:00:00+00', '2026-01-07 09:00:00+00',
 FALSE, FALSE, '2026-01-05 09:00:00+00',
 -0.28, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Facilities Management'), 79.00,
 'Replace faulty ballasts and upgrade to LED drivers.',
 FALSE, FALSE),

('CX-J002', 'Server backup failure – weekly job',
 'Weekly backup job failing with disk write error since Jan 3. Two jobs missed.',
 'Complaint', 'Resolved', 'Critical',
 'Software', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2026-01-06 07:00:00+00', '2026-01-06 07:05:00+00', '2026-01-06 07:22:00+00', '2026-01-06 18:00:00+00',
 '2026-01-06 07:30:00+00', '2026-01-06 19:00:00+00',
 FALSE, FALSE, '2026-01-06 07:00:00+00',
 -0.65, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 94.00,
 'Expand backup disk volume; run manual backup; schedule RAID health check.',
 FALSE, FALSE),

('CX-J003', 'Roof access door stuck – emergency exit',
 'Emergency roof access door will not open from inside. Fire safety risk.',
 'Complaint', 'Resolved', 'Critical',
 'Civil', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-01-12 10:00:00+00', '2026-01-12 10:06:00+00', '2026-01-12 10:28:00+00', '2026-01-12 18:00:00+00',
 '2026-01-12 10:30:00+00', '2026-01-12 22:00:00+00',
 FALSE, FALSE, '2026-01-12 10:00:00+00',
 -0.72, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Repair door latch mechanism; test emergency release; log in fire safety register.',
 FALSE, FALSE),

('CX-J004', 'Heating system uneven – south wing',
 'South wing offices 15°C while north wing 26°C. Balancing valve likely failed.',
 'Complaint', 'Resolved', 'High',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2026-01-15 08:00:00+00', '2026-01-15 08:20:00+00', '2026-01-15 09:00:00+00', '2026-01-16 16:00:00+00',
 '2026-01-15 09:00:00+00', '2026-01-16 08:00:00+00',
 FALSE, FALSE, '2026-01-15 08:00:00+00',
 -0.40, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 88.00,
 'Replace failed balancing valve; recalibrate HVAC zone controls.',
 FALSE, FALSE),

('CX-J005', 'Photocopier fire alarm trigger – false positive',
 'High-volume photocopier on L2 triggered smoke alarm twice this week. Dust accumulation.',
 'Inquiry', 'Resolved', 'Medium',
 'Fire Safety', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-01-18 11:00:00+00', '2026-01-18 11:30:00+00', '2026-01-18 12:15:00+00', '2026-01-19 14:00:00+00',
 '2026-01-18 14:00:00+00', '2026-01-20 11:00:00+00',
 FALSE, FALSE, '2026-01-18 11:00:00+00',
 -0.20, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Safety & Security'), 76.00,
 'Service photocopier and relocate smoke detector away from exhaust path.',
 FALSE, FALSE),

('CX-J006', 'Parking barrier stuck open – level P2',
 'P2 entry barrier stuck open since weekend. Unauthorised vehicles entering.',
 'Complaint', 'Resolved', 'High',
 'Parking', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2026-01-25 08:00:00+00', '2026-01-25 08:18:00+00', '2026-01-25 09:00:00+00', '2026-01-25 17:00:00+00',
 '2026-01-25 09:00:00+00', '2026-01-26 08:00:00+00',
 FALSE, FALSE, '2026-01-25 08:00:00+00',
 -0.50, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Safety & Security'), 86.00,
 'Replace barrier motor arm; update access control whitelist.',
 FALSE, FALSE),

-- ── December 2025 ─────────────────────────────────────────────────────────────
('CX-D001', 'Main gate CCTV offline – Christmas period',
 'Main entrance CCTV camera cluster offline during peak visitor period.',
 'Complaint', 'Resolved', 'Critical',
 'CCTV', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2025-12-03 07:00:00+00', '2025-12-03 07:06:00+00', '2025-12-03 07:27:00+00', '2025-12-03 16:00:00+00',
 '2025-12-03 07:30:00+00', '2025-12-03 19:00:00+00',
 FALSE, FALSE, '2025-12-03 07:00:00+00',
 -0.75, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Replace PoE switch feeding CCTV cluster; verify all feeds.',
 FALSE, FALSE),

('CX-D002', 'Heating boiler pressure drop – Block B',
 'Block B heating boiler showing 0.5 bar — well below minimum. Risk of shutdown.',
 'Complaint', 'Resolved', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-12-08 06:30:00+00', '2025-12-08 06:36:00+00', '2025-12-08 06:58:00+00', '2025-12-08 18:00:00+00',
 '2025-12-08 07:00:00+00', '2025-12-08 18:30:00+00',
 FALSE, FALSE, '2025-12-08 06:30:00+00',
 -0.68, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 95.00,
 'Repressurise boiler to 1.5 bar; inspect for micro-leak in expansion vessel.',
 FALSE, FALSE),

('CX-D003', 'Network printer offline – Leasing team',
 'Shared network printer for Leasing team showing offline. Contracts queued for print.',
 'Inquiry', 'Resolved', 'Medium',
 'Network', (SELECT id FROM departments WHERE name='Leasing'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='talya@innovacx.net'),
 '2025-12-15 10:00:00+00', '2025-12-15 10:35:00+00', '2025-12-15 11:20:00+00', '2025-12-15 15:00:00+00',
 '2025-12-15 13:00:00+00', '2025-12-16 10:00:00+00',
 FALSE, FALSE, '2025-12-15 10:00:00+00',
 -0.18, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Leasing'), 77.00,
 'Reassign static IP and restart print spooler; update driver on all clients.',
 FALSE, FALSE),

('CX-D004', 'Recurring water hammer – riser pipe shaft',
 'Banging noise from riser pipe shaft 3rd occurrence this month. Pressure surges causing damage.',
 'Complaint', 'Resolved', 'High',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2025-12-20 09:00:00+00', '2025-12-20 09:22:00+00', '2025-12-20 10:00:00+00', '2025-12-22 12:00:00+00',
 '2025-12-20 10:00:00+00', '2025-12-21 09:00:00+00',
 FALSE, FALSE, '2025-12-20 09:00:00+00',
 -0.44, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Maintenance'), 83.00,
 'Install pressure-reducing valve and water hammer arrestors on riser.',
 FALSE, TRUE),

-- ── November 2025 ────────────────────────────────────────────────────────────
('CX-N001', 'Emergency lighting failure – basement',
 'Emergency lighting in basement carpark not illuminating during drill. Battery packs degraded.',
 'Complaint', 'Resolved', 'Critical',
 'Electrical', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2025-11-06 09:00:00+00', '2025-11-06 09:06:00+00', '2025-11-06 09:27:00+00', '2025-11-06 18:00:00+00',
 '2025-11-06 09:30:00+00', '2025-11-06 21:00:00+00',
 FALSE, FALSE, '2025-11-06 09:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Replace all degraded emergency light battery packs; conduct full test cycle.',
 FALSE, FALSE),

('CX-N002', 'VoIP PBX failed – all desk phones down',
 'PBX controller crashed. All desk phones show no dial tone across building.',
 'Complaint', 'Resolved', 'Critical',
 'Telephony', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2025-11-12 08:00:00+00', '2025-11-12 08:06:00+00', '2025-11-12 08:27:00+00', '2025-11-12 16:00:00+00',
 '2025-11-12 08:30:00+00', '2025-11-12 20:00:00+00',
 FALSE, FALSE, '2025-11-12 08:00:00+00',
 -0.72, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 96.00,
 'Restore PBX from snapshot backup; reconfigure SIP trunk parameters.',
 FALSE, FALSE),

('CX-N003', 'Cleaning chemical spill – ground floor lobby',
 'Cleaning staff spilled corrosive chemical near reception. Area cordoned; HSE incident.',
 'Complaint', 'Resolved', 'High',
 'Cleaning', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-11-18 10:00:00+00', '2025-11-18 10:14:00+00', '2025-11-18 10:45:00+00', '2025-11-18 15:00:00+00',
 '2025-11-18 11:00:00+00', '2025-11-19 10:00:00+00',
 FALSE, FALSE, '2025-11-18 10:00:00+00',
 -0.80, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 92.00,
 'Neutralise spill with baking soda solution; file HSE incident report.',
 FALSE, FALSE),

('CX-N004', 'Keypad PIN lock failure – comms room',
 'Communications room PIN entry pad accepting all codes. Security breach risk.',
 'Complaint', 'Resolved', 'Critical',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2025-11-25 07:00:00+00', '2025-11-25 07:07:00+00', '2025-11-25 07:28:00+00', '2025-11-25 14:00:00+00',
 '2025-11-25 07:30:00+00', '2025-11-25 19:00:00+00',
 FALSE, FALSE, '2025-11-25 07:00:00+00',
 -0.78, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 98.00,
 'Replace keypad module immediately; audit all room access attempts for last 48 hours.',
 FALSE, FALSE),

-- ── October 2025 ─────────────────────────────────────────────────────────────
('CX-O001', 'Carpet tiles lifting – open plan L4',
 'Multiple carpet tiles lifting on L4 — trip hazard reported by 3 staff.',
 'Complaint', 'Resolved', 'Medium',
 'Civil', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-10-05 09:00:00+00', '2025-10-05 09:40:00+00', '2025-10-05 10:30:00+00', '2025-10-07 12:00:00+00',
 '2025-10-05 12:00:00+00', '2025-10-07 09:00:00+00',
 FALSE, FALSE, '2025-10-05 09:00:00+00',
 -0.25, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Facilities Management'), 78.00,
 'Re-adhere lifting tiles; identify root cause (subfloor moisture).',
 FALSE, FALSE),

('CX-O002', 'UPS runtime alarm – server room',
 'Server room UPS runtime warning: 12 minutes under full load. Load shedding needed.',
 'Complaint', 'Resolved', 'High',
 'Electrical', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2025-10-12 08:00:00+00', '2025-10-12 08:18:00+00', '2025-10-12 09:00:00+00', '2025-10-13 16:00:00+00',
 '2025-10-12 09:00:00+00', '2025-10-13 08:00:00+00',
 FALSE, FALSE, '2025-10-12 08:00:00+00',
 -0.50, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='IT'), 89.00,
 'Identify and remove non-critical loads; order replacement battery modules.',
 FALSE, FALSE),

('CX-O003', 'Fire door self-closer broken – stairwell 3',
 'Self-closing mechanism on stairwell 3 fire door broken. Door stays open — fire risk.',
 'Complaint', 'Resolved', 'Critical',
 'Fire Safety', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2025-10-20 10:00:00+00', '2025-10-20 10:07:00+00', '2025-10-20 10:27:00+00', '2025-10-20 17:00:00+00',
 '2025-10-20 10:30:00+00', '2025-10-20 22:00:00+00',
 FALSE, FALSE, '2025-10-20 10:00:00+00',
 -0.62, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 96.00,
 'Replace door closer unit immediately; add to monthly fire door inspection list.',
 FALSE, FALSE),

-- ── September 2025 ────────────────────────────────────────────────────────────
('CX-S001', 'Pest infestation reported – kitchen area',
 'Staff reported mice in building kitchen. Droppings found near food storage area.',
 'Complaint', 'Resolved', 'High',
 'Cleaning', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-09-02 08:00:00+00', '2025-09-02 08:25:00+00', '2025-09-02 09:00:00+00', '2025-09-04 14:00:00+00',
 '2025-09-02 09:00:00+00', '2025-09-03 08:00:00+00',
 FALSE, FALSE, '2025-09-02 08:00:00+00',
 -0.75, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 91.00,
 'Deploy licensed pest control contractor; seal all entry points.',
 FALSE, FALSE),

('CX-S002', 'Diesel generator failed test run',
 'Monthly generator test run failed to start. Fuel filter blocked and battery flat.',
 'Complaint', 'Resolved', 'Critical',
 'Electrical', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-09-10 09:00:00+00', '2025-09-10 09:08:00+00', '2025-09-10 09:29:00+00', '2025-09-10 18:00:00+00',
 '2025-09-10 09:30:00+00', '2025-09-10 21:00:00+00',
 FALSE, FALSE, '2025-09-10 09:00:00+00',
 -0.65, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 94.00,
 'Replace fuel filter and battery; complete full load test to certify readiness.',
 FALSE, FALSE),

-- ── August 2025 ───────────────────────────────────────────────────────────────
('CX-G001', 'Chiller leak – level 3 plant room',
 'Refrigerant leak detected on chiller unit 2 in level 3 plant room. EPA reportable.',
 'Complaint', 'Resolved', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='sarah@innovacx.net'),
 '2025-08-05 07:00:00+00', '2025-08-05 07:05:00+00', '2025-08-05 07:26:00+00', '2025-08-05 20:00:00+00',
 '2025-08-05 07:30:00+00', '2025-08-05 19:00:00+00',
 FALSE, FALSE, '2025-08-05 07:00:00+00',
 -0.80, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 98.00,
 'Isolate chiller unit 2; call certified refrigerant technician; file EPA leak report.',
 FALSE, FALSE),

('CX-G002', 'Network fabric failure – core switch stack',
 'Core switch stack experienced split-brain — 30% of VLANs affected.',
 'Complaint', 'Resolved', 'Critical',
 'Network', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2025-08-18 06:00:00+00', '2025-08-18 06:06:00+00', '2025-08-18 06:28:00+00', '2025-08-18 18:00:00+00',
 '2025-08-18 06:30:00+00', '2025-08-18 18:00:00+00',
 FALSE, FALSE, '2025-08-18 06:00:00+00',
 -0.75, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 97.00,
 'Force stack re-election; upgrade IOS firmware; monitor for 4 hours post-fix.',
 FALSE, FALSE),

-- ── July 2025 ─────────────────────────────────────────────────────────────────
('CX-L001', 'Water mains pressure loss – entire site',
 'Site water pressure dropped below 1 bar. Building-wide cold water disruption.',
 'Complaint', 'Resolved', 'Critical',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2025-07-03 06:00:00+00', '2025-07-03 06:06:00+00', '2025-07-03 06:28:00+00', '2025-07-03 18:00:00+00',
 '2025-07-03 06:30:00+00', '2025-07-03 18:00:00+00',
 FALSE, FALSE, '2025-07-03 06:00:00+00',
 -0.85, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Maintenance'), 97.00,
 'Identify burst main; contact utility; deploy emergency water tanker.',
 FALSE, FALSE),

-- ── June 2025 ─────────────────────────────────────────────────────────────────
('CX-E001', 'Lightning strike – rooftop antennae array',
 'Lightning strike during storm damaged 4 rooftop antennae. Comms and GPS affected.',
 'Complaint', 'Resolved', 'Critical',
 'Communications', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer3@innovacx.net'),
 (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
 '2025-06-05 19:00:00+00', '2025-06-05 19:07:00+00', '2025-06-05 19:29:00+00', '2025-06-06 14:00:00+00',
 '2025-06-05 19:30:00+00', '2025-06-06 07:00:00+00',
 FALSE, FALSE, '2025-06-05 19:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 96.00,
 'Replace damaged antennae; install surge protectors; inspect lightning conductor.',
 FALSE, FALSE),

-- ── May 2025 ──────────────────────────────────────────────────────────────────
('CX-M001', 'Access control server hardware failure',
 'Main access control server disk array degraded. System falling back to offline mode.',
 'Complaint', 'Resolved', 'Critical',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innovacx.net'),
 (SELECT id FROM users WHERE email='yousef@innovacx.net'),
 '2025-05-08 07:00:00+00', '2025-05-08 07:06:00+00', '2025-05-08 07:27:00+00', '2025-05-08 18:00:00+00',
 '2025-05-08 07:30:00+00', '2025-05-08 19:00:00+00',
 FALSE, FALSE, '2025-05-08 07:00:00+00',
 -0.78, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Hot-swap failed disk; rebuild RAID array; failover to standby server.',
 FALSE, FALSE),

-- ── April 2025 ────────────────────────────────────────────────────────────────
('CX-P001', 'Hot water tank thermostat failure – ablutions',
 'Hot water in ablution facilities dangerously hot — thermostat stuck open.',
 'Complaint', 'Resolved', 'Critical',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer2@innovacx.net'),
 (SELECT id FROM users WHERE email='sameer@innovacx.net'),
 '2025-04-22 07:00:00+00', '2025-04-22 07:05:00+00', '2025-04-22 07:26:00+00', '2025-04-22 16:00:00+00',
 '2025-04-22 07:30:00+00', '2025-04-22 19:00:00+00',
 FALSE, FALSE, '2025-04-22 07:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Maintenance'), 95.00,
 'Replace thermostat and test water temperature at all outlets.',
 FALSE, FALSE)

ON CONFLICT (ticket_code) DO NOTHING;

-- =============================================================================
-- SET resolved_at for all new tickets that are Resolved
-- =============================================================================
UPDATE tickets
SET
  resolved_at         = created_at + interval '9 hours',
  resolved_by_user_id = assigned_to_user_id
WHERE ticket_code IN (
  'CX-F001','CX-F002','CX-F003','CX-F004','CX-F005','CX-F006','CX-F007',
  'CX-F008','CX-F009','CX-F010',
  'CX-J001','CX-J002','CX-J003','CX-J004','CX-J005','CX-J006',
  'CX-D001','CX-D002','CX-D003','CX-D004',
  'CX-N001','CX-N002','CX-N003','CX-N004',
  'CX-O001','CX-O002','CX-O003',
  'CX-S001','CX-S002',
  'CX-G001','CX-G002',
  'CX-L001','CX-E001','CX-M001','CX-P001'
)
AND resolved_at IS NULL;

-- =============================================================================
-- SUGGESTED_RESOLUTION_USAGE for new tickets
-- 80% accepted, 20% declined_custom — matches the QC dashboard display
-- =============================================================================
INSERT INTO suggested_resolution_usage (
  ticket_id, employee_user_id, decision, department,
  suggested_text, final_text, used
)
SELECT t.id, u.id, fb.decision, d.name, fb.suggested, fb.final, (fb.decision = 'accepted')
FROM (VALUES
  ('CX-F001','sarah@innovacx.net','accepted',
   'Shut down lift; inspect motor cooling; replace thermal relay.',
   NULL, 'Lift shut down. Thermal relay replaced. Motor cooling restored and tested.'),
  ('CX-F002','lena@innovacx.net','accepted',
   'Roll back firmware update and re-enrol user fingerprints.',
   NULL, 'Firmware rolled back. 42 users re-enrolled. System operational.'),
  ('CX-F003','sameer@innovacx.net','accepted',
   'Open stuck valve at rooftop tank; flush pipes.',
   NULL, 'Valve freed and lubricated. Pipes flushed. Full cold water flow restored.'),
  ('CX-F004','sarah@innovacx.net','declined_custom',
   'Lubricate and restart exhaust fan.',
   'Fan motor seized beyond lubrication — full motor replacement required.',
   'Motor replaced with energy-efficient unit. Ventilation verified adequate.'),
  ('CX-F005','yousef@innovacx.net','accepted',
   'Reposition camera bracket 15° left; verify coverage.',
   NULL, 'Camera repositioned. Blind spot eliminated. Monitoring room confirmed full coverage.'),
  ('CX-F006','ahmed@innovacx.net','accepted',
   'Manually disengage bypass; replace actuator mechanism.',
   NULL, 'Bypass disengaged manually. New actuator fitted and tested. UPS maintenance completed.'),
  ('CX-F007','sarah@innovacx.net','accepted',
   'Replace ceiling tiles; seal water ingress; apply anti-mould treatment.',
   NULL, 'Tiles replaced. Ingress sealed at roof level. Anti-mould treatment applied.'),
  ('CX-F008','yousef@innovacx.net','accepted',
   'Replace intercom central controller unit.',
   NULL, 'New controller installed. All 3 entry panel intercoms operational.'),
  ('CX-F009','sarah@innovacx.net','accepted',
   'Replace AHU filter immediately.',
   NULL, 'Filter replaced. CO2 levels normalised within 20 minutes of restart.'),
  ('CX-F010','talya@innovacx.net','declined_custom',
   'Renew expired SSL certificate.',
   'Certificate was valid — CDN was caching old cert. CDN purge was primary fix.',
   'CDN purged and cert renewed. All users accessing portal successfully.'),
  ('CX-J001','sarah@innovacx.net','accepted',
   'Replace faulty ballasts and upgrade to LED drivers.',
   NULL, 'All ballasts replaced with LED drivers. Flickering eliminated.'),
  ('CX-J002','ahmed@innovacx.net','accepted',
   'Expand backup disk volume; run manual backup.',
   NULL, 'Disk expanded to 8TB. Manual backup completed successfully. Monitoring in place.'),
  ('CX-J003','yousef@innovacx.net','accepted',
   'Repair door latch mechanism; test emergency release.',
   NULL, 'Latch repaired. Emergency release tested and certified. Logged in fire register.'),
  ('CX-J004','sarah@innovacx.net','accepted',
   'Replace failed balancing valve; recalibrate HVAC zone controls.',
   NULL, 'Valve replaced. Zones recalibrated. Temperature balanced across north and south wings.'),
  ('CX-J005','yousef@innovacx.net','declined_custom',
   'Service photocopier and relocate smoke detector.',
   'Detector sensitivity was set too high — recalibration was the primary fix.',
   'Detector recalibrated to correct sensitivity. Photocopier serviced. No further false alarms.'),
  ('CX-J006','yousef@innovacx.net','accepted',
   'Replace barrier motor arm; update access control whitelist.',
   NULL, 'Motor arm replaced. Whitelist updated. Barrier operating normally.'),
  ('CX-D001','yousef@innovacx.net','accepted',
   'Replace PoE switch feeding CCTV cluster; verify all feeds.',
   NULL, 'PoE switch replaced. All 12 cameras in cluster back online.'),
  ('CX-D002','sarah@innovacx.net','accepted',
   'Repressurise boiler to 1.5 bar; inspect expansion vessel.',
   NULL, 'Boiler repressurised. Micro-leak found and sealed in expansion vessel. System stable.'),
  ('CX-D003','talya@innovacx.net','accepted',
   'Reassign static IP and restart print spooler.',
   NULL, 'Static IP reassigned. Print spooler restarted. All clients printing normally.'),
  ('CX-D004','sameer@innovacx.net','accepted',
   'Install pressure-reducing valve and water hammer arrestors.',
   NULL, 'PRV and arrestors installed. Banging noise eliminated. Pressure stable at 3 bar.'),
  ('CX-N001','yousef@innovacx.net','accepted',
   'Replace all degraded emergency light battery packs; conduct full test cycle.',
   NULL, 'All 24 battery packs replaced. Full 3-hour test passed. Certificate issued.'),
  ('CX-N002','ahmed@innovacx.net','accepted',
   'Restore PBX from snapshot backup; reconfigure SIP trunk parameters.',
   NULL, 'PBX restored from yesterday snapshot. SIP trunk reconfigured. All phones operational.'),
  ('CX-N003','sarah@innovacx.net','accepted',
   'Neutralise spill with baking soda solution; file HSE incident report.',
   NULL, 'Spill neutralised and area deep-cleaned. HSE incident report filed.'),
  ('CX-N004','yousef@innovacx.net','accepted',
   'Replace keypad module immediately; audit access attempts.',
   NULL, 'Keypad module replaced. Access log audited — no unauthorised entries confirmed.'),
  ('CX-O001','sarah@innovacx.net','declined_custom',
   'Re-adhere lifting tiles.',
   'Subfloor moisture was the root cause — waterproofing membrane needed.',
   'Membrane replaced under affected area. Tiles re-adhered with waterproof adhesive.'),
  ('CX-O002','ahmed@innovacx.net','accepted',
   'Identify non-critical loads; order replacement battery modules.',
   NULL, 'Non-essential servers migrated to secondary circuit. New batteries ordered and fitted.'),
  ('CX-O003','yousef@innovacx.net','accepted',
   'Replace door closer unit immediately.',
   NULL, 'New door closer fitted and fire door tested for compliance.'),
  ('CX-S001','sarah@innovacx.net','accepted',
   'Deploy pest control contractor; seal all entry points.',
   NULL, 'Contractor deployed. 6 entry points sealed. Follow-up scheduled in 2 weeks.'),
  ('CX-S002','sarah@innovacx.net','accepted',
   'Replace fuel filter and battery; complete full load test.',
   NULL, 'Filter and battery replaced. Full 30-minute load test passed. Generator certified ready.'),
  ('CX-G001','sarah@innovacx.net','accepted',
   'Isolate chiller unit 2; call certified refrigerant technician; file EPA leak report.',
   NULL, 'Unit isolated. Refrigerant recovered. Leak sealed. EPA report filed. Unit recharged.'),
  ('CX-G002','ahmed@innovacx.net','accepted',
   'Force stack re-election; upgrade IOS firmware.',
   NULL, 'Stack re-election forced. IOS upgraded. 4-hour monitoring shows no further issues.'),
  ('CX-L001','sameer@innovacx.net','accepted',
   'Identify burst main; contact utility; deploy emergency water tanker.',
   NULL, 'Burst main located and utility notified. Tanker deployed within 2 hours. Mains restored.'),
  ('CX-E001','ahmed@innovacx.net','accepted',
   'Replace damaged antennae; install surge protectors.',
   NULL, 'All 4 antennae replaced. Surge protectors installed. Lightning conductor inspected — intact.'),
  ('CX-M001','yousef@innovacx.net','accepted',
   'Hot-swap failed disk; rebuild RAID array.',
   NULL, 'Disk hot-swapped. RAID rebuild completed in 4 hours. Failover server restored to standby.'),
  ('CX-P001','sameer@innovacx.net','accepted',
   'Replace thermostat and test water temperature at all outlets.',
   NULL, 'Thermostat replaced. Water temperature verified at 55°C across all outlets.')
) AS fb(tc, emp, decision, suggested, custom, final)
JOIN tickets t ON t.ticket_code = fb.tc
JOIN users u ON u.email = fb.emp
LEFT JOIN departments d ON d.id = t.department_id
WHERE NOT EXISTS (
  SELECT 1 FROM suggested_resolution_usage sru
  WHERE sru.ticket_id = t.id
    AND sru.employee_user_id = u.id
    AND sru.decision = fb.decision
    AND sru.final_text = fb.final
);

-- =============================================================================
-- APPROVAL_REQUESTS for new tickets (to populate mv_operator_qc_daily)
-- These create rerouting data visible in Quality Control → C — Rerouting
-- =============================================================================
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
  ('REQ-5001','CX-F002','Rerouting','Dept: HR','Dept: IT',
   'Biometric readers run on network infrastructure — IT team should handle firmware.',
   'lena@innovacx.net','2026-02-05 09:00:00+00','Rejected',
   'leen@innovacx.net','2026-02-05 10:00:00+00',
   'HR owns the biometric system for its floor. Firmware rollback is within HR scope.'),
  ('REQ-5002','CX-F005','Rescoring','Priority: Medium','Priority: High',
   'Third recurrence of same CCTV fault — persistent systemic issue justifies High.',
   'bilal@innovacx.net','2026-02-12 11:30:00+00','Approved',
   'ali@innovacx.net','2026-02-12 12:00:00+00',
   'Agreed — recurring issue warrants escalation.'),
  ('REQ-5003','CX-F008','Rerouting','Dept: Safety & Security','Dept: IT',
   'Intercom runs over IP network — IT infrastructure team should own this.',
   'yousef@innovacx.net','2026-02-22 07:15:00+00','Rejected',
   'ali@innovacx.net','2026-02-22 08:00:00+00',
   'Physical intercom hardware is a Security asset. Keep in Security.'),
  ('REQ-5004','CX-F010','Rescoring','Priority: Critical','Priority: High',
   'Issue resolved within 5 hours — may not meet Critical criteria retrospectively.',
   'talya@innovacx.net','2026-02-26 15:00:00+00','Pending',
   NULL, NULL, NULL),
  ('REQ-5005','CX-J003','Rerouting','Dept: Safety & Security','Dept: Facilities Management',
   'Roof door is a facilities civil asset — should be under Facilities Management.',
   'yousef@innovacx.net','2026-01-12 10:30:00+00','Approved',
   'ali@innovacx.net','2026-01-12 11:00:00+00',
   'Correct — structural door belongs to Facilities.'),
  ('REQ-5006','CX-D004','Rescoring','Priority: High','Priority: Critical',
   'Recurring water hammer causing pipe damage — third incident. Structural risk.',
   'sameer@innovacx.net','2025-12-20 09:30:00+00','Approved',
   'majid@innovacx.net','2025-12-20 10:00:00+00',
   'Agreed — third recurrence with structural risk meets Critical threshold.'),
  ('REQ-5007','CX-N003','Rerouting','Dept: Facilities Management','Dept: Safety & Security',
   'Chemical spill is an HSE/Safety matter — Safety & Security should lead response.',
   'sarah@innovacx.net','2025-11-18 10:20:00+00','Approved',
   'hana@innovacx.net','2025-11-18 11:00:00+00',
   'HSE incidents to be led by Safety & Security. Reassigned.'),
  ('REQ-5008','CX-O001','Rescoring','Priority: Medium','Priority: Low',
   'No safety risk — cosmetic issue only. Low priority is appropriate.',
   'sarah@innovacx.net','2025-10-05 10:00:00+00','Rejected',
   'hana@innovacx.net','2025-10-05 11:00:00+00',
   'Trip hazard confirmed by 3 staff — Medium priority is correct.'),
  ('REQ-5009','CX-S002','Rerouting','Dept: Facilities Management','Dept: Maintenance',
   'Generator maintenance is Maintenance team scope, not general Facilities.',
   'sarah@innovacx.net','2025-09-10 09:30:00+00','Pending',
   NULL, NULL, NULL),
  ('REQ-5010','CX-F009','Rescoring','Priority: High','Priority: Critical',
   'AHU filter blockage causing CO2 buildup — immediate health risk to occupants.',
   'ahmed@innovacx.net','2026-02-24 08:20:00+00','Approved',
   'hana@innovacx.net','2026-02-24 08:40:00+00',
   'Health safety risk confirmed — Critical appropriate.')
) AS r(code, tc, rtype, cur, req, reason, sub_email, sub_at, status, dec_email, dec_at, dec_notes)
JOIN tickets t ON t.ticket_code = r.tc
ON CONFLICT (request_code) DO NOTHING;

-- =============================================================================
-- MODEL_EXECUTION_LOG for new tickets
-- Covers sentiment + feature agents for all new tickets.
-- Other agents (priority/routing/sla/resolution) also added for key tickets.
-- =============================================================================
INSERT INTO public.model_execution_log (
  ticket_id, agent_name, model_version, triggered_by,
  started_at, completed_at, status,
  input_token_count, output_token_count,
  inference_time_ms, confidence_score, error_flag, error_message,
  infra_metadata
)
SELECT t.id,
  v.agent_name::agent_name_type,
  v.model_version,
  v.triggered_by::trigger_source,
  v.started_at::timestamptz,
  v.completed_at::timestamptz,
  v.status::execution_status,
  v.in_tok, v.out_tok, v.inf_ms,
  v.conf_score, FALSE, NULL,
  v.infra::jsonb
FROM (VALUES
  -- Feb 2026 tickets — sentiment + feature + priority for all
  ('CX-F001','sentiment','sentiment-v3.1','ingest','2026-02-03 07:01:00+00','2026-02-03 07:01:05+00','success',415,28,4300,0.9400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F001','feature',  'feature-v1.5','ingest','2026-02-03 07:01:06+00','2026-02-03 07:01:09+00','success',380,44,3200,0.9500,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-F001','priority', 'priority-v2.4','ingest','2026-02-03 07:01:10+00','2026-02-03 07:01:14+00','success',422,31,3900,0.9600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F001','routing',  'routing-v1.8','ingest','2026-02-03 07:01:15+00','2026-02-03 07:01:19+00','success',430,25,4000,0.9700,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F001','resolution','resolution-v2.0','ingest','2026-02-03 07:01:20+00','2026-02-03 07:01:29+00','success',615,143,9100,0.9600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),

  ('CX-F002','sentiment','sentiment-v3.1','ingest','2026-02-05 08:31:00+00','2026-02-05 08:31:04+00','success',390,27,4100,0.8800,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F002','feature',  'feature-v1.5','ingest','2026-02-05 08:31:05+00','2026-02-05 08:31:08+00','success',375,43,3100,0.9200,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-F002','priority', 'priority-v2.4','ingest','2026-02-05 08:31:09+00','2026-02-05 08:31:13+00','success',418,30,3800,0.8800,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),

  ('CX-F003','sentiment','sentiment-v3.1','ingest','2026-02-07 09:01:00+00','2026-02-07 09:01:04+00','success',382,26,4000,0.8600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F003','feature',  'feature-v1.5','ingest','2026-02-07 09:01:05+00','2026-02-07 09:01:08+00','success',370,42,3000,0.9100,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F004','sentiment','sentiment-v3.1','ingest','2026-02-10 10:01:00+00','2026-02-10 10:01:04+00','success',365,24,3800,0.7200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F004','feature',  'feature-v1.5','ingest','2026-02-10 10:01:05+00','2026-02-10 10:01:08+00','success',360,40,2900,0.8000,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F005','sentiment','sentiment-v3.1','ingest','2026-02-12 11:01:00+00','2026-02-12 11:01:04+00','success',375,25,3900,0.8400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F005','feature',  'feature-v1.5','ingest','2026-02-12 11:01:05+00','2026-02-12 11:01:08+00','success',370,41,3000,0.8700,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F006','sentiment','sentiment-v3.1','ingest','2026-02-17 08:01:00+00','2026-02-17 08:01:04+00','success',385,27,4000,0.8900,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F006','feature',  'feature-v1.5','ingest','2026-02-17 08:01:05+00','2026-02-17 08:01:08+00','success',375,43,3100,0.9100,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F007','sentiment','sentiment-v3.1','ingest','2026-02-19 09:01:00+00','2026-02-19 09:01:04+00','success',395,27,4100,0.9000,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F007','feature',  'feature-v1.5','ingest','2026-02-19 09:01:05+00','2026-02-19 09:01:08+00','success',380,44,3100,0.9100,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F008','sentiment','sentiment-v3.1','ingest','2026-02-22 07:01:00+00','2026-02-22 07:01:04+00','success',405,28,4200,0.9300,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F008','feature',  'feature-v1.5','ingest','2026-02-22 07:01:05+00','2026-02-22 07:01:08+00','success',390,45,3200,0.9400,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F009','sentiment','sentiment-v3.1','ingest','2026-02-24 08:01:00+00','2026-02-24 08:01:04+00','success',395,27,4100,0.8900,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F009','feature',  'feature-v1.5','ingest','2026-02-24 08:01:05+00','2026-02-24 08:01:08+00','success',380,44,3100,0.9200,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  ('CX-F010','sentiment','sentiment-v3.1','ingest','2026-02-26 09:01:00+00','2026-02-26 09:01:04+00','success',402,28,4200,0.9100,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-F010','feature',  'feature-v1.5','ingest','2026-02-26 09:01:05+00','2026-02-26 09:01:08+00','success',385,44,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Jan 2026
  ('CX-J001','sentiment','sentiment-v3.1','ingest','2026-01-05 09:01:00+00','2026-01-05 09:01:04+00','success',360,24,3800,0.7400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J001','feature',  'feature-v1.5','ingest','2026-01-05 09:01:05+00','2026-01-05 09:01:08+00','success',355,40,2900,0.7900,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-J002','sentiment','sentiment-v3.1','ingest','2026-01-06 07:01:00+00','2026-01-06 07:01:04+00','success',398,27,4100,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J002','feature',  'feature-v1.5','ingest','2026-01-06 07:01:05+00','2026-01-06 07:01:08+00','success',382,43,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-J003','sentiment','sentiment-v3.1','ingest','2026-01-12 10:01:00+00','2026-01-12 10:01:04+00','success',408,28,4200,0.9500,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J003','feature',  'feature-v1.5','ingest','2026-01-12 10:01:05+00','2026-01-12 10:01:08+00','success',390,45,3200,0.9600,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-J004','sentiment','sentiment-v3.1','ingest','2026-01-15 08:01:00+00','2026-01-15 08:01:04+00','success',388,26,4000,0.8700,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J004','feature',  'feature-v1.5','ingest','2026-01-15 08:01:05+00','2026-01-15 08:01:08+00','success',375,43,3000,0.9000,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-J005','sentiment','sentiment-v3.1','ingest','2026-01-18 11:01:00+00','2026-01-18 11:01:04+00','success',365,25,3800,0.7600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J005','feature',  'feature-v1.5','ingest','2026-01-18 11:01:05+00','2026-01-18 11:01:08+00','success',358,41,2900,0.8100,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-J006','sentiment','sentiment-v3.1','ingest','2026-01-25 08:01:00+00','2026-01-25 08:01:04+00','success',392,26,4100,0.8800,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-J006','feature',  'feature-v1.5','ingest','2026-01-25 08:01:05+00','2026-01-25 08:01:08+00','success',378,43,3100,0.9100,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Dec 2025
  ('CX-D001','sentiment','sentiment-v3.1','ingest','2025-12-03 07:01:00+00','2025-12-03 07:01:04+00','success',405,27,4200,0.9400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-D001','feature',  'feature-v1.5','ingest','2025-12-03 07:01:05+00','2025-12-03 07:01:08+00','success',390,44,3200,0.9500,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-D002','sentiment','sentiment-v3.1','ingest','2025-12-08 06:31:00+00','2025-12-08 06:31:04+00','success',398,27,4100,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-D002','feature',  'feature-v1.5','ingest','2025-12-08 06:31:05+00','2025-12-08 06:31:08+00','success',382,43,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-D003','sentiment','sentiment-v3.1','ingest','2025-12-15 10:01:00+00','2025-12-15 10:01:04+00','success',360,24,3800,0.7500,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-D003','feature',  'feature-v1.5','ingest','2025-12-15 10:01:05+00','2025-12-15 10:01:08+00','success',355,40,2900,0.8000,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-D004','sentiment','sentiment-v3.1','ingest','2025-12-20 09:01:00+00','2025-12-20 09:01:04+00','success',385,26,4000,0.8800,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-D004','feature',  'feature-v1.5','ingest','2025-12-20 09:01:05+00','2025-12-20 09:01:08+00','success',372,42,3000,0.9000,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Nov 2025
  ('CX-N001','sentiment','sentiment-v3.1','ingest','2025-11-06 09:01:00+00','2025-11-06 09:01:04+00','success',408,28,4200,0.9500,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-N001','feature',  'feature-v1.5','ingest','2025-11-06 09:01:05+00','2025-11-06 09:01:08+00','success',392,45,3200,0.9600,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-N002','sentiment','sentiment-v3.1','ingest','2025-11-12 08:01:00+00','2025-11-12 08:01:04+00','success',410,28,4300,0.9400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-N002','feature',  'feature-v1.5','ingest','2025-11-12 08:01:05+00','2025-11-12 08:01:08+00','success',390,44,3200,0.9400,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-N003','sentiment','sentiment-v3.1','ingest','2025-11-18 10:01:00+00','2025-11-18 10:01:04+00','success',400,27,4200,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-N003','feature',  'feature-v1.5','ingest','2025-11-18 10:01:05+00','2025-11-18 10:01:08+00','success',385,44,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-N004','sentiment','sentiment-v3.1','ingest','2025-11-25 07:01:00+00','2025-11-25 07:01:04+00','success',412,28,4300,0.9600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-N004','feature',  'feature-v1.5','ingest','2025-11-25 07:01:05+00','2025-11-25 07:01:08+00','success',395,45,3200,0.9600,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Oct 2025
  ('CX-O001','sentiment','sentiment-v3.1','ingest','2025-10-05 09:01:00+00','2025-10-05 09:01:04+00','success',355,24,3700,0.7100,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-O001','feature',  'feature-v1.5','ingest','2025-10-05 09:01:05+00','2025-10-05 09:01:08+00','success',348,39,2800,0.7700,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-O002','sentiment','sentiment-v3.1','ingest','2025-10-12 08:01:00+00','2025-10-12 08:01:04+00','success',392,27,4100,0.8900,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-O002','feature',  'feature-v1.5','ingest','2025-10-12 08:01:05+00','2025-10-12 08:01:08+00','success',378,43,3100,0.9100,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-O003','sentiment','sentiment-v3.1','ingest','2025-10-20 10:01:00+00','2025-10-20 10:01:04+00','success',400,27,4200,0.9100,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-O003','feature',  'feature-v1.5','ingest','2025-10-20 10:01:05+00','2025-10-20 10:01:08+00','success',385,44,3100,0.9200,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Sep 2025
  ('CX-S001','sentiment','sentiment-v3.1','ingest','2025-09-02 08:01:00+00','2025-09-02 08:01:04+00','success',400,27,4200,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-S001','feature',  'feature-v1.5','ingest','2025-09-02 08:01:05+00','2025-09-02 08:01:08+00','success',385,44,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-S002','sentiment','sentiment-v3.1','ingest','2025-09-10 09:01:00+00','2025-09-10 09:01:04+00','success',398,27,4100,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-S002','feature',  'feature-v1.5','ingest','2025-09-10 09:01:05+00','2025-09-10 09:01:08+00','success',382,43,3100,0.9200,'{"region":"me-south-1","instance":"ml-c5.large"}'),

  -- Aug-Jul-Jun-May-Apr 2025
  ('CX-G001','sentiment','sentiment-v3.1','ingest','2025-08-05 07:01:00+00','2025-08-05 07:01:04+00','success',410,28,4300,0.9500,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-G001','feature',  'feature-v1.5','ingest','2025-08-05 07:01:05+00','2025-08-05 07:01:08+00','success',395,45,3200,0.9600,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-G002','sentiment','sentiment-v3.1','ingest','2025-08-18 06:01:00+00','2025-08-18 06:01:04+00','success',408,28,4200,0.9400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-G002','feature',  'feature-v1.5','ingest','2025-08-18 06:01:05+00','2025-08-18 06:01:08+00','success',390,44,3200,0.9500,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-L001','sentiment','sentiment-v3.1','ingest','2025-07-03 06:01:00+00','2025-07-03 06:01:04+00','success',415,28,4300,0.9600,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-L001','feature',  'feature-v1.5','ingest','2025-07-03 06:01:05+00','2025-07-03 06:01:08+00','success',398,45,3200,0.9700,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-E001','sentiment','sentiment-v3.1','ingest','2025-06-05 19:01:00+00','2025-06-05 19:01:04+00','success',404,28,4200,0.9300,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-E001','feature',  'feature-v1.5','ingest','2025-06-05 19:01:05+00','2025-06-05 19:01:08+00','success',388,44,3200,0.9400,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-M001','sentiment','sentiment-v3.1','ingest','2025-05-08 07:01:00+00','2025-05-08 07:01:04+00','success',408,28,4200,0.9400,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-M001','feature',  'feature-v1.5','ingest','2025-05-08 07:01:05+00','2025-05-08 07:01:08+00','success',392,45,3200,0.9500,'{"region":"me-south-1","instance":"ml-c5.large"}'),
  ('CX-P001','sentiment','sentiment-v3.1','ingest','2025-04-22 07:01:00+00','2025-04-22 07:01:04+00','success',405,27,4200,0.9200,'{"region":"me-south-1","instance":"ml-g4dn.xlarge","gpu":"A10G"}'),
  ('CX-P001','feature',  'feature-v1.5','ingest','2025-04-22 07:01:05+00','2025-04-22 07:01:08+00','success',388,44,3100,0.9300,'{"region":"me-south-1","instance":"ml-c5.large"}')

) AS v(tc, agent_name, model_version, triggered_by, started_at, completed_at, status,
       in_tok, out_tok, inf_ms, conf_score, infra)
JOIN public.tickets t ON t.ticket_code = v.tc;

-- =============================================================================
-- SENTIMENT_OUTPUTS for all new tickets (powers mv_sentiment_daily)
-- =============================================================================
INSERT INTO public.sentiment_outputs (
  execution_id, ticket_id, model_version,
  sentiment_label, sentiment_score, confidence_score,
  emotion_tags, raw_scores, is_current
)
SELECT DISTINCT ON (mel.ticket_id)
  mel.id, mel.ticket_id, mel.model_version,
  sv.label, sv.score, sv.conf, sv.emotions::text[], sv.raw::jsonb, TRUE
FROM (VALUES
  ('CX-F001','Negative',    -0.8200, 0.9400, '{panicked,urgent,distressed}',          '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
  ('CX-F002','Negative',    -0.5500, 0.8800, '{frustrated,concerned}',                '{"negative":0.8800,"neutral":0.0850,"positive":0.0350}'),
  ('CX-F003','Negative',    -0.4200, 0.8600, '{inconvenienced,frustrated}',           '{"negative":0.8600,"neutral":0.1000,"positive":0.0400}'),
  ('CX-F004','Neutral',     -0.2200, 0.7200, '{neutral,inquiring}',                   '{"negative":0.5200,"neutral":0.3800,"positive":0.1000}'),
  ('CX-F005','Negative',    -0.3500, 0.8400, '{frustrated,recurring_annoyance}',      '{"negative":0.8400,"neutral":0.1100,"positive":0.0500}'),
  ('CX-F006','Negative',    -0.4800, 0.8900, '{concerned,urgent}',                   '{"negative":0.8900,"neutral":0.0750,"positive":0.0350}'),
  ('CX-F007','Negative',    -0.5200, 0.9000, '{alarmed,frustrated}',                 '{"negative":0.9000,"neutral":0.0700,"positive":0.0300}'),
  ('CX-F008','Negative',    -0.7000, 0.9300, '{urgent,distressed,angry}',             '{"negative":0.9300,"neutral":0.0500,"positive":0.0200}'),
  ('CX-F009','Negative',    -0.4500, 0.8900, '{concerned,urgent}',                   '{"negative":0.8900,"neutral":0.0750,"positive":0.0350}'),
  ('CX-F010','Negative',    -0.6000, 0.9100, '{frustrated,business_impacted}',        '{"negative":0.9100,"neutral":0.0600,"positive":0.0300}'),
  ('CX-J001','Neutral',     -0.2800, 0.7400, '{mildly_frustrated}',                  '{"negative":0.5800,"neutral":0.3200,"positive":0.1000}'),
  ('CX-J002','Negative',    -0.6500, 0.9200, '{alarmed,business_impacted}',           '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}'),
  ('CX-J003','Negative',    -0.7200, 0.9500, '{alarmed,safety_concerned}',            '{"negative":0.9500,"neutral":0.0350,"positive":0.0150}'),
  ('CX-J004','Negative',    -0.4000, 0.8700, '{uncomfortable,frustrated}',            '{"negative":0.8700,"neutral":0.0900,"positive":0.0400}'),
  ('CX-J005','Neutral',     -0.2000, 0.7600, '{curious,mildly_concerned}',            '{"negative":0.4800,"neutral":0.3900,"positive":0.1300}'),
  ('CX-J006','Negative',    -0.5000, 0.8800, '{concerned,urgent}',                   '{"negative":0.8800,"neutral":0.0850,"positive":0.0350}'),
  ('CX-D001','Negative',    -0.7500, 0.9400, '{alarmed,urgent}',                     '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
  ('CX-D002','Negative',    -0.6800, 0.9200, '{alarmed,urgent}',                     '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}'),
  ('CX-D003','Neutral',     -0.1800, 0.7500, '{neutral,business_impacted}',           '{"negative":0.4500,"neutral":0.4200,"positive":0.1300}'),
  ('CX-D004','Negative',    -0.4400, 0.8800, '{frustrated,recurring_annoyance}',      '{"negative":0.8800,"neutral":0.0850,"positive":0.0350}'),
  ('CX-N001','Negative',    -0.7000, 0.9500, '{alarmed,safety_concerned}',            '{"negative":0.9500,"neutral":0.0350,"positive":0.0150}'),
  ('CX-N002','Negative',    -0.7200, 0.9400, '{alarmed,business_impacted}',           '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
  ('CX-N003','Negative',    -0.8000, 0.9200, '{alarmed,safety_concerned,distressed}', '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}'),
  ('CX-N004','Negative',    -0.7800, 0.9600, '{alarmed,urgent,safety_concerned}',     '{"negative":0.9600,"neutral":0.0300,"positive":0.0100}'),
  ('CX-O001','Neutral',     -0.2500, 0.7100, '{mildly_concerned}',                   '{"negative":0.5400,"neutral":0.3500,"positive":0.1100}'),
  ('CX-O002','Negative',    -0.5000, 0.8900, '{concerned,business_impacted}',         '{"negative":0.8900,"neutral":0.0750,"positive":0.0350}'),
  ('CX-O003','Negative',    -0.6200, 0.9100, '{alarmed,safety_concerned}',            '{"negative":0.9100,"neutral":0.0600,"positive":0.0300}'),
  ('CX-S001','Negative',    -0.7500, 0.9200, '{alarmed,disgusted}',                  '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}'),
  ('CX-S002','Negative',    -0.6500, 0.9200, '{alarmed,safety_concerned}',            '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}'),
  ('CX-G001','Negative',    -0.8000, 0.9500, '{alarmed,urgent,distressed}',           '{"negative":0.9500,"neutral":0.0350,"positive":0.0150}'),
  ('CX-G002','Negative',    -0.7500, 0.9400, '{alarmed,business_impacted}',           '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
  ('CX-L001','Negative',    -0.8500, 0.9600, '{panicked,urgent,distressed}',          '{"negative":0.9600,"neutral":0.0300,"positive":0.0100}'),
  ('CX-E001','Negative',    -0.7000, 0.9300, '{alarmed,business_impacted}',           '{"negative":0.9300,"neutral":0.0500,"positive":0.0200}'),
  ('CX-M001','Negative',    -0.7800, 0.9400, '{alarmed,urgent}',                     '{"negative":0.9400,"neutral":0.0400,"positive":0.0200}'),
  ('CX-P001','Negative',    -0.7000, 0.9200, '{alarmed,safety_concerned}',            '{"negative":0.9200,"neutral":0.0550,"positive":0.0250}')
) AS sv(tc, label, score, conf, emotions, raw)
JOIN public.model_execution_log mel
  ON mel.ticket_id = (SELECT id FROM public.tickets WHERE ticket_code = sv.tc LIMIT 1)
 AND mel.agent_name = 'sentiment'
 AND mel.status     = 'success'
WHERE NOT EXISTS (
  SELECT 1 FROM public.sentiment_outputs so
  WHERE so.ticket_id = mel.ticket_id AND so.is_current = TRUE
)
ORDER BY mel.ticket_id, mel.started_at;

-- =============================================================================
-- FEATURE_OUTPUTS for all new tickets (powers mv_feature_daily)
-- raw_features JSON includes: business_impact, safety_concern,
-- issue_severity, issue_urgency (used by mv_feature_daily aggregation)
-- =============================================================================
INSERT INTO public.feature_outputs (
  execution_id, ticket_id, model_version,
  asset_category, topic_labels, confidence_score, raw_features, is_current
)
SELECT DISTINCT ON (mel.ticket_id)
  mel.id, mel.ticket_id, mel.model_version,
  fv.asset_cat, fv.topics::text[], fv.conf, fv.raw::jsonb, TRUE
FROM (VALUES
  ('CX-F001','Elevator',            '{elevator,motor,overheating,critical,mechanical}',    0.9500, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-F002','Access Control',      '{biometric,access,hr,firmware,update}',               0.9200, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-F003','Plumbing',            '{water,cold,supply,valve,rooftop}',                   0.9100, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-F004','HVAC',                '{exhaust,fan,ventilation,toner,fumes}',               0.8000, '{"business_impact":"Low","safety_concern":true,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
  ('CX-F005','CCTV',                '{cctv,camera,blind-spot,parking,recurring}',          0.8700, '{"business_impact":"Medium","safety_concern":true,"issue_severity":"Medium","issue_urgency":"Medium","is_recurring":true}'),
  ('CX-F006','Electrical',          '{ups,bypass,switch,data-closet,maintenance}',         0.9100, '{"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-F007','Civil',               '{mould,moisture,ceiling,meeting-room,health}',        0.9100, '{"business_impact":"Medium","safety_concern":true,"issue_severity":"High","issue_urgency":"Medium","is_recurring":false}'),
  ('CX-F008','Communications',      '{intercom,entry,audio,security,controller}',          0.9400, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-F009','HVAC',                '{ahu,filter,co2,ventilation,blocked}',                0.9200, '{"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-F010','Software',            '{ssl,certificate,cdn,leasing,portal}',                0.9300, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-J001','Electrical',          '{lighting,flickering,ballast,corridor,health}',       0.7900, '{"business_impact":"Low","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
  ('CX-J002','Software',            '{backup,disk,server,data-loss,critical}',             0.9300, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-J003','Civil',               '{door,emergency-exit,fire-safety,rooftop,latch}',     0.9600, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-J004','HVAC',                '{heating,balancing-valve,zones,temperature,hvac}',    0.9000, '{"business_impact":"Medium","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-J005','Fire Safety',         '{smoke-detector,false-alarm,photocopier,calibration}',0.8100, '{"business_impact":"Low","safety_concern":true,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
  ('CX-J006','Parking',             '{barrier,parking,motor,access,security}',             0.9100, '{"business_impact":"Medium","safety_concern":true,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-D001','CCTV',                '{cctv,poe-switch,camera-cluster,main-entrance}',      0.9500, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-D002','HVAC',                '{boiler,pressure,heating,expansion-vessel}',          0.9300, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-D003','Network',             '{printer,network,ip,spooler,leasing}',                0.8000, '{"business_impact":"Low","safety_concern":false,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
  ('CX-D004','Plumbing',            '{water-hammer,pressure,riser,recurring,damage}',      0.9000, '{"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"High","is_recurring":true}'),
  ('CX-N001','Electrical',          '{emergency-lighting,battery,basement,fire-safety}',   0.9600, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-N002','Telephony',           '{pbx,voip,phones,sip-trunk,building-wide}',           0.9400, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-N003','Cleaning',            '{chemical,spill,hse,lobby,safety}',                   0.9300, '{"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-N004','Access Control',      '{keypad,comms-room,security,access,breach}',          0.9600, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-O001','Civil',               '{carpet,trip-hazard,moisture,subfloor}',              0.7700, '{"business_impact":"Low","safety_concern":true,"issue_severity":"Medium","issue_urgency":"Low","is_recurring":false}'),
  ('CX-O002','Electrical',          '{ups,runtime,battery,server-room,load}',              0.9100, '{"business_impact":"High","safety_concern":false,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-O003','Fire Safety',         '{fire-door,self-closer,stairwell,compliance}',        0.9200, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"High","is_recurring":false}'),
  ('CX-S001','Cleaning',            '{pest,mice,kitchen,food-storage,hygiene}',            0.9300, '{"business_impact":"High","safety_concern":true,"issue_severity":"High","issue_urgency":"High","is_recurring":false}'),
  ('CX-S002','Electrical',          '{generator,diesel,fuel-filter,battery,power}',        0.9200, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-G001','HVAC',                '{chiller,refrigerant,leak,epa,plant-room}',           0.9600, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-G002','Network',             '{core-switch,vlan,split-brain,ios,fabric}',           0.9500, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-L001','Plumbing',            '{mains,water,pressure,burst,site-wide}',              0.9700, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-E001','Communications',      '{antenna,lightning,gps,comms,surge}',                 0.9400, '{"business_impact":"High","safety_concern":false,"issue_severity":"Critical","issue_urgency":"High","is_recurring":false}'),
  ('CX-M001','Access Control',      '{server,disk,raid,access-control,offline-mode}',      0.9500, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}'),
  ('CX-P001','Plumbing',            '{hot-water,thermostat,ablutions,safety,burn-risk}',   0.9300, '{"business_impact":"High","safety_concern":true,"issue_severity":"Critical","issue_urgency":"Critical","is_recurring":false}')
) AS fv(tc, asset_cat, topics, conf, raw)
JOIN public.model_execution_log mel
  ON mel.ticket_id = (SELECT id FROM public.tickets WHERE ticket_code = fv.tc LIMIT 1)
 AND mel.agent_name = 'feature'
 AND mel.status     = 'success'
WHERE NOT EXISTS (
  SELECT 1 FROM public.feature_outputs fo
  WHERE fo.ticket_id = mel.ticket_id AND fo.is_current = TRUE
)
ORDER BY mel.ticket_id, mel.started_at;

-- =============================================================================
-- BACKFILL is_recurring on tickets table from feature_outputs
-- (mv_feature_daily reads tickets.is_recurring, not raw_features)
-- =============================================================================
UPDATE tickets t
SET is_recurring = TRUE
FROM public.feature_outputs fo
WHERE fo.ticket_id = t.id
  AND fo.is_current = TRUE
  AND (fo.raw_features->>'is_recurring')::boolean = TRUE
  AND t.is_recurring = FALSE;

-- =============================================================================
-- ADDITIONAL SESSIONS for chatbot MV data
-- These sessions span multiple months to give mv_chatbot_daily trend data
-- =============================================================================
INSERT INTO sessions (user_id, current_state, context, history, created_at, updated_at, bot_model_version, escalated_to_human, escalated_at, linked_ticket_id)
VALUES
  -- Feb 2026 escalated sessions
  ((SELECT id FROM users WHERE email='customer1@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Elevator","building":"Tower1"}',
   '[{"role":"user","msg":"Lift motor overheating"},{"role":"bot","msg":"Critical — escalating"},{"role":"operator","msg":"Khalid assigned"}]',
   '2026-02-03 07:00:00+00','2026-02-03 07:30:00+00','chatbot-v2.1',
   TRUE,'2026-02-03 07:04:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-F001')),

  ((SELECT id FROM users WHERE email='customer2@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Access Control","floor":"HR"}',
   '[{"role":"user","msg":"Biometric readers broken"},{"role":"bot","msg":"High ticket raised"}]',
   '2026-02-05 08:30:00+00','2026-02-05 09:00:00+00','chatbot-v2.1',
   FALSE,NULL,(SELECT id FROM tickets WHERE ticket_code='CX-F002')),

  ((SELECT id FROM users WHERE email='customer3@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Intercom","type":"entry_failure"}',
   '[{"role":"user","msg":"All intercoms dead"},{"role":"bot","msg":"Critical — escalating"},{"role":"operator","msg":"Omar dispatched"}]',
   '2026-02-22 07:00:00+00','2026-02-22 07:30:00+00','chatbot-v2.1',
   TRUE,'2026-02-22 07:05:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-F008')),

  ((SELECT id FROM users WHERE email='customer1@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"HVAC","type":"ahu_filter"}',
   '[{"role":"user","msg":"CO2 levels high — AHU blocked"},{"role":"bot","msg":"Health risk — escalating"}]',
   '2026-02-24 08:00:00+00','2026-02-24 08:20:00+00','chatbot-v2.1',
   TRUE,'2026-02-24 08:03:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-F009')),

  ((SELECT id FROM users WHERE email='customer2@innovacx.net'),
   'resolved','{"last_intent":"inquiry","topic":"sla_policy"}',
   '[{"role":"user","msg":"What is the escalation process?"},{"role":"bot","msg":"Explained escalation tiers"}]',
   '2026-02-18 14:00:00+00','2026-02-18 14:12:00+00','chatbot-v2.1',
   FALSE,NULL,NULL),

  -- Jan 2026 sessions
  ((SELECT id FROM users WHERE email='customer3@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Civil","type":"emergency_door"}',
   '[{"role":"user","msg":"Roof exit door stuck"},{"role":"bot","msg":"Critical fire safety — escalating"}]',
   '2026-01-12 10:00:00+00','2026-01-12 10:20:00+00','chatbot-v2.1',
   TRUE,'2026-01-12 10:03:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-J003')),

  ((SELECT id FROM users WHERE email='customer1@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"IT","type":"backup_failure"}',
   '[{"role":"user","msg":"Server backups failing"},{"role":"bot","msg":"Critical ticket raised"}]',
   '2026-01-06 07:00:00+00','2026-01-06 07:15:00+00','chatbot-v2.1',
   FALSE,NULL,(SELECT id FROM tickets WHERE ticket_code='CX-J002')),

  ((SELECT id FROM users WHERE email='customer2@innovacx.net'),
   'resolved','{"last_intent":"inquiry","topic":"ticket_status"}',
   '[{"role":"user","msg":"Status of my last ticket?"},{"role":"bot","msg":"Resolved 3 days ago"}]',
   '2026-01-20 11:00:00+00','2026-01-20 11:08:00+00','chatbot-v2.1',
   FALSE,NULL,NULL),

  -- Dec 2025 sessions
  ((SELECT id FROM users WHERE email='customer3@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"CCTV","type":"cluster_offline"}',
   '[{"role":"user","msg":"Main gate cameras all offline"},{"role":"bot","msg":"Critical — escalating"}]',
   '2025-12-03 07:00:00+00','2025-12-03 07:20:00+00','chatbot-v2.1',
   TRUE,'2025-12-03 07:04:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-D001')),

  ((SELECT id FROM users WHERE email='customer1@innovacx.net'),
   'resolved','{"last_intent":"inquiry","topic":"hvac_policy"}',
   '[{"role":"user","msg":"How often are HVAC filters changed?"},{"role":"bot","msg":"Quarterly — answered"}]',
   '2025-12-18 14:00:00+00','2025-12-18 14:10:00+00','chatbot-v2.0',
   FALSE,NULL,NULL),

  -- Nov 2025 sessions
  ((SELECT id FROM users WHERE email='customer2@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Electrical","type":"emergency_lighting"}',
   '[{"role":"user","msg":"Emergency lights failed drill"},{"role":"bot","msg":"Critical safety — escalating"}]',
   '2025-11-06 09:00:00+00','2025-11-06 09:20:00+00','chatbot-v2.0',
   TRUE,'2025-11-06 09:03:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-N001')),

  ((SELECT id FROM users WHERE email='customer3@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Telephony","type":"pbx_down"}',
   '[{"role":"user","msg":"All desk phones dead"},{"role":"bot","msg":"Critical — escalating"}]',
   '2025-11-12 08:00:00+00','2025-11-12 08:20:00+00','chatbot-v2.0',
   TRUE,'2025-11-12 08:05:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-N002')),

  ((SELECT id FROM users WHERE email='customer1@innovacx.net'),
   'resolved','{"last_intent":"inquiry","topic":"general"}',
   '[{"role":"user","msg":"How do I book a meeting room?"},{"role":"bot","msg":"Explained booking process"}]',
   '2025-11-20 10:00:00+00','2025-11-20 10:08:00+00','chatbot-v2.0',
   FALSE,NULL,NULL),

  -- Oct 2025 sessions
  ((SELECT id FROM users WHERE email='customer2@innovacx.net'),
   'resolved','{"last_intent":"report_issue","asset":"Fire Safety","type":"door_closer"}',
   '[{"role":"user","msg":"Fire door stays open — safety risk"},{"role":"bot","msg":"Critical — escalating"}]',
   '2025-10-20 10:00:00+00','2025-10-20 10:15:00+00','chatbot-v2.0',
   TRUE,'2025-10-20 10:03:00+00',(SELECT id FROM tickets WHERE ticket_code='CX-O003')),

  ((SELECT id FROM users WHERE email='customer3@innovacx.net'),
   'resolved','{"last_intent":"inquiry","topic":"complaint_process"}',
   '[{"role":"user","msg":"How do I file a formal complaint?"},{"role":"bot","msg":"Directed to complaints form"}]',
   '2025-10-08 15:00:00+00','2025-10-08 15:10:00+00','chatbot-v2.0',
   FALSE,NULL,NULL)
;

-- =============================================================================
-- USER_CHAT_LOGS for new sessions — adds sentiment data to mv_chatbot_daily
-- =============================================================================
INSERT INTO user_chat_logs (user_id, session_id, message, intent_detected, aggression_flag, aggression_score, created_at, sentiment_score, category, response_time_ms, ticket_id)
SELECT
  (SELECT id FROM users WHERE email = v.email),
  s.session_id,
  v.msg, v.intent, v.agg::boolean, v.agg_score, v.ts::timestamptz,
  v.sent, v.cat, v.resp_ms,
  CASE WHEN v.tc IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code = v.tc) ELSE NULL END
FROM (VALUES
  ('customer1@innovacx.net','2026-02-03 07:00:30+00','Lift motor in Tower 1 is overheating — smell of burning!','report_issue','false',0.0350,-0.82,'Elevator',NULL,'CX-F001'),
  ('customer2@innovacx.net','2026-02-05 08:30:30+00','Biometric readers on HR floor rejecting all fingerprints.','report_issue','false',0.0200,-0.55,'Access Control',1050,'CX-F002'),
  ('customer3@innovacx.net','2026-02-22 07:00:30+00','All intercoms at entry points have no audio!','report_issue','false',0.0400,-0.70,'Communications',NULL,'CX-F008'),
  ('customer1@innovacx.net','2026-02-24 08:00:30+00','CO2 levels high in Wing C — AHU filter seems blocked.','report_issue','false',0.0280,-0.45,'HVAC',900,'CX-F009'),
  ('customer2@innovacx.net','2026-02-18 14:00:30+00','What is the escalation process for facilities issues?','inquiry','false',0.0050,0.10,'General',640,NULL),
  ('customer3@innovacx.net','2026-01-12 10:00:30+00','The roof emergency exit door will not open from inside!','report_issue','false',0.0450,-0.72,'Civil',NULL,'CX-J003'),
  ('customer1@innovacx.net','2026-01-06 07:00:30+00','Server backup jobs have been failing since January 3rd.','report_issue','false',0.0220,-0.65,'IT',NULL,'CX-J002'),
  ('customer2@innovacx.net','2026-01-20 11:00:30+00','What is the current status of my last submitted ticket?','inquiry','false',0.0050,0.00,'General',610,NULL),
  ('customer3@innovacx.net','2025-12-03 07:00:30+00','All cameras at the main gate are showing no signal.','report_issue','false',0.0320,-0.75,'CCTV',NULL,'CX-D001'),
  ('customer1@innovacx.net','2025-12-18 14:00:30+00','How often are the HVAC filters supposed to be replaced?','inquiry','false',0.0040,0.10,'HVAC',620,NULL),
  ('customer2@innovacx.net','2025-11-06 09:00:30+00','Emergency lights failed to come on during the fire drill.','report_issue','false',0.0400,-0.70,'Electrical',NULL,'CX-N001'),
  ('customer3@innovacx.net','2025-11-12 08:00:30+00','All desk phones are completely dead — no dial tone.','report_issue','false',0.0380,-0.72,'Telephony',NULL,'CX-N002'),
  ('customer1@innovacx.net','2025-11-20 10:00:30+00','Can I book the conference room through the chat?','inquiry','false',0.0040,0.20,'General',580,NULL),
  ('customer2@innovacx.net','2025-10-20 10:00:30+00','The stairwell 3 fire door stays wide open — it is a fire hazard.','report_issue','false',0.0380,-0.62,'Fire Safety',NULL,'CX-O003'),
  ('customer3@innovacx.net','2025-10-08 15:00:30+00','How do I submit a formal complaint about repeated issues?','inquiry','false',0.0060,0.05,'General',600,NULL)
) AS v(email, ts, msg, intent, agg, agg_score, sent, cat, resp_ms, tc)
LEFT JOIN sessions s ON s.user_id = (SELECT id FROM users WHERE email = v.email)
  AND s.created_at = (
    SELECT created_at FROM sessions
    WHERE user_id = (SELECT id FROM users WHERE email = v.email)
    ORDER BY ABS(EXTRACT(EPOCH FROM (created_at - v.ts::timestamptz)))
    LIMIT 1
  )
WHERE NOT EXISTS (
  SELECT 1 FROM user_chat_logs ucl
  WHERE ucl.user_id = (SELECT id FROM users WHERE email = v.email)
    AND ucl.message = v.msg
  LIMIT 1
);

-- =============================================================================
-- BACKFILL: Ensure all priority_assigned_at are set for new tickets
-- =============================================================================
UPDATE tickets
SET priority_assigned_at = created_at
WHERE priority_assigned_at IS NULL;

-- NOTE: refresh_analytics_mvs() is called by zzz_analytics_mvs.sh after
-- the materialized views are created. The backend also refreshes on startup.

COMMIT;
