-- =============================================================================
-- seed_extra.sql  — 5-10 extra rows per table
-- Run AFTER init.sql (alphabetically between init.sql and zzz_analytics_mvs.sh).
-- Only inserts into tables created by init.sql. ML pipeline seed data (sections
-- 28-35: model_execution_log, *_outputs, agent_output_log) is in
-- zzz_seed_analytics.sql, which runs after zzz_analytics_mvs.sh creates those tables.
-- Idempotent: uses DO blocks + ON CONFLICT DO NOTHING where possible.
-- =============================================================================

BEGIN;

-- =============================================================================
-- 1. DEPARTMENTS  (reference table — 7 rows already in init.sql seed;
--    we add extra to give routing_outputs & tickets more variety)
-- =============================================================================
INSERT INTO departments (name) VALUES
  ('Facilities Management'),
  ('Legal and Compliance'),
  ('Safety & Security'),
  ('HR'),
  ('Leasing'),
  ('Maintenance'),
  ('IT')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- 2. USERS  (11 seed users: 1 customer, 1 manager, 1 operator, 8 employees)
-- =============================================================================
INSERT INTO users (email, password_hash, role, is_active, mfa_enabled, totp_secret) VALUES
  ('customer1@innova.cx',  crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  TRUE, FALSE, NULL),
  ('customer2@innova.cx',  crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  TRUE, FALSE, NULL),
  ('customer3@innova.cx',  crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  TRUE, FALSE, NULL),
  ('manager@innova.cx',    crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   TRUE, FALSE, NULL),
  ('operator@innova.cx',   crypt('Innova@2025', gen_salt('bf', 12)), 'operator',  TRUE, FALSE, NULL),
  ('ahmed@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('maria@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('omar@innova.cx',       crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('sara@innova.cx',       crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('bilal@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('fatima@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('yousef@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('khalid@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('rania@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('tariq@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, FALSE, NULL),
  ('lena@innova.cx',       crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('hassan@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('noura@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('ziad@innova.cx',       crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL),
  ('dina@innova.cx',       crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  TRUE, FALSE, NULL)
ON CONFLICT (email) DO UPDATE SET mfa_enabled = FALSE, totp_secret = NULL;

-- =============================================================================
-- 3. USER_PROFILES
-- =============================================================================
INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Dr. Farhad Al-Rashidi', '+97155000001', 'Dubai',
       (SELECT id FROM departments WHERE name='Facilities Management'), NULL, 'Department Manager'
FROM users u WHERE u.email='manager@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Sarah Operator', '+97155000002', 'Dubai',
       NULL, NULL, 'System Operator'
FROM users u WHERE u.email='operator@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Ahmed Hassan', '+97155001001', 'Dubai',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1023', 'Senior Technician'
FROM users u WHERE u.email='ahmed@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Maria Lopez', '+97155001002', 'Dubai',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1078', 'Technician'
FROM users u WHERE u.email='maria@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Omar Ali', '+97155001003', 'Sharjah',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1150', 'Assistant Technician'
FROM users u WHERE u.email='omar@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Sara Ahmed', '+97155001004', 'Dubai',
       (SELECT id FROM departments WHERE name='Facilities Management'), 'EMP-1192', 'Technician'
FROM users u WHERE u.email='sara@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Bilal Khan', '+97155001005', 'Abu Dhabi',
       (SELECT id FROM departments WHERE name='Safety & Security'), 'EMP-1244', 'HVAC Specialist'
FROM users u WHERE u.email='bilal@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Fatima Noor', '+97155001006', 'Dubai',
       (SELECT id FROM departments WHERE name='IT'), 'EMP-1290', 'IT Coordinator'
FROM users u WHERE u.email='fatima@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Yousef Karim', '+97155001007', 'Sharjah',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1331', 'Maintenance Supervisor'
FROM users u WHERE u.email='yousef@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Khalid Musa', '+97155001008', 'Dubai',
       (SELECT id FROM departments WHERE name='Facilities Management'), 'EMP-1378', 'Electrician'
FROM users u WHERE u.email='khalid@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Rania Saeed', '+97155001009', 'Dubai',
       (SELECT id FROM departments WHERE name='HR'), 'EMP-1401', 'HR Coordinator'
FROM users u WHERE u.email='rania@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Tariq Mansour', '+97155001010', 'Ajman',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1412', 'Junior Technician'
FROM users u WHERE u.email='tariq@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Lena Haddad', '+97155001011', 'Dubai',
       (SELECT id FROM departments WHERE name='IT'), 'EMP-1435', 'Network Engineer'
FROM users u WHERE u.email='lena@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Hassan Zuberi', '+97155001012', 'Dubai',
       (SELECT id FROM departments WHERE name='Safety & Security'), 'EMP-1460', 'Security Officer'
FROM users u WHERE u.email='hassan@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Noura Al-Farsi', '+97155001013', 'Dubai',
       (SELECT id FROM departments WHERE name='Leasing'), 'EMP-1482', 'Leasing Executive'
FROM users u WHERE u.email='noura@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Ziad Khalil', '+97155001014', 'Dubai',
       (SELECT id FROM departments WHERE name='Maintenance'), 'EMP-1499', 'Plumber'
FROM users u WHERE u.email='ziad@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location, department_id, employee_code, job_title)
SELECT u.id, 'Dina Rashid', '+97155001015', 'Sharjah',
       (SELECT id FROM departments WHERE name='Facilities Management'), 'EMP-1510', 'Facilities Coordinator'
FROM users u WHERE u.email='dina@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

-- Customer profiles
INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer One', '+971500000001', 'Dubai'
FROM users u WHERE u.email='customer1@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer Two', '+971500000002', 'Abu Dhabi'
FROM users u WHERE u.email='customer2@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer Three', '+971500000003', 'Sharjah'
FROM users u WHERE u.email='customer3@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

-- =============================================================================
-- 4. USER_PREFERENCES
-- =============================================================================
INSERT INTO user_preferences (user_id, language, dark_mode, default_complaint_type, email_notifications, in_app_notifications, status_alerts)
SELECT u.id, 'English', FALSE, 'General', TRUE, TRUE, TRUE
FROM users u
WHERE NOT EXISTS (SELECT 1 FROM user_preferences p WHERE p.user_id = u.id);

-- Customise a few users
UPDATE user_preferences SET dark_mode = TRUE, language = 'Arabic'
WHERE user_id = (SELECT id FROM users WHERE email = 'manager@innova.cx');

UPDATE user_preferences SET dark_mode = TRUE
WHERE user_id = (SELECT id FROM users WHERE email = 'fatima@innova.cx');

UPDATE user_preferences SET email_notifications = FALSE
WHERE user_id = (SELECT id FROM users WHERE email = 'omar@innova.cx');

-- =============================================================================
-- 5. PASSWORD_RESET_TOKENS
-- =============================================================================
INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
SELECT (SELECT id FROM users WHERE email='customer1@innova.cx'),
       crypt('reset-token-cust1-abc123', gen_salt('bf', 10)),
       now() + interval '2 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM password_reset_tokens WHERE user_id=(SELECT id FROM users WHERE email='customer1@innova.cx') AND used_at IS NULL
);

INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innova.cx'),
       crypt('reset-token-ahmed-xyz789', gen_salt('bf', 10)),
       now() - interval '12 hours',
       now() - interval '10 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM password_reset_tokens WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innova.cx')
);

INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
SELECT (SELECT id FROM users WHERE email='maria@innova.cx'),
       crypt('reset-token-maria-mno456', gen_salt('bf', 10)),
       now() + interval '1 hour'
WHERE NOT EXISTS (
  SELECT 1 FROM password_reset_tokens WHERE user_id=(SELECT id FROM users WHERE email='maria@innova.cx') AND used_at IS NULL
);

-- =============================================================================
-- 6. TICKETS  (20+ rows spanning all statuses, priorities, departments)
-- =============================================================================
-- All tickets inserted with ON CONFLICT (ticket_code) DO NOTHING so safe to re-run.

-- ── Active / open tickets (current month, March 2026) ──────────────────────
INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, status, priority,
  asset_type, department_id, created_by_user_id, assigned_to_user_id,
  created_at, assigned_at, first_response_at,
  respond_due_at, resolve_due_at,
  respond_breached, resolve_breached,
  priority_assigned_at,
  sentiment_score, sentiment_label,
  model_priority, model_department_id, model_confidence, model_suggestion,
  human_overridden, is_recurring
)
VALUES

-- 1
('CX-A001', 'HVAC completely offline – Server Room B',
 'Cooling unit in Server Room B has stopped. Ambient temperature above 32°C and rising. All servers at risk.',
 'Complaint', 'In Progress', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2026-03-01 06:00:00+00', '2026-03-01 06:08:00+00', '2026-03-01 06:25:00+00',
 '2026-03-01 06:30:00+00', '2026-03-01 12:00:00+00',
 FALSE, FALSE, '2026-03-01 06:00:00+00',
 -0.78, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 96.50,
 'Activate backup cooling and dispatch HVAC technician immediately.',
 FALSE, FALSE),

-- 2
('CX-A002', 'Access badge readers down – Gate 2',
 'All RFID readers at main Gate 2 refusing valid credentials. 30+ staff unable to enter.',
 'Complaint', 'In Progress', 'Critical',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='omar@innova.cx'),
 '2026-03-01 07:30:00+00', '2026-03-01 07:35:00+00', '2026-03-01 07:52:00+00',
 '2026-03-01 08:00:00+00', '2026-03-01 13:30:00+00',
 FALSE, FALSE, '2026-03-01 07:30:00+00',
 -0.65, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 94.00,
 'Restart access control server and force-sync badge database.',
 FALSE, FALSE),

-- 3
('CX-A003', 'Elevator B stuck between floors',
 'Elevator B in Tower 2 has stalled between floors 4 and 5. Alarm sounding intermittently.',
 'Complaint', 'Assigned', 'High',
 'Elevator', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='khalid@innova.cx'),
 '2026-03-01 08:00:00+00', '2026-03-01 08:10:00+00', '2026-03-01 08:32:00+00',
 '2026-03-01 09:00:00+00', '2026-03-02 08:00:00+00',
 FALSE, FALSE, '2026-03-01 08:00:00+00',
 -0.50, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 89.00,
 'Run elevator diagnostics and inspect door sensors and control panel.',
 FALSE, FALSE),

-- 4
('CX-A004', 'Network outage – Floor 5 workstations',
 '20 workstations on Floor 5 lost connectivity. Identified as potential switch failure.',
 'Complaint', 'In Progress', 'Critical',
 'Network', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='fatima@innova.cx'),
 '2026-03-01 08:15:00+00', '2026-03-01 08:20:00+00', '2026-03-01 08:42:00+00',
 '2026-03-01 08:45:00+00', '2026-03-01 14:15:00+00',
 FALSE, FALSE, '2026-03-01 08:15:00+00',
 -0.60, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 95.00,
 'Replace failed switch and verify all 20 workstation connections.',
 FALSE, FALSE),

-- 5
('CX-A005', 'Water leak – Pantry ceiling pipe',
 'Water dripping from ceiling joint in 3rd floor pantry area. Puddle forming near electrical sockets.',
 'Complaint', 'Assigned', 'High',
 'Plumbing', (SELECT id FROM departments WHERE name='Maintenance'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='ziad@innova.cx'),
 '2026-03-01 09:00:00+00', '2026-03-01 09:15:00+00', '2026-03-01 09:48:00+00',
 '2026-03-01 10:00:00+00', '2026-03-02 09:00:00+00',
 FALSE, FALSE, '2026-03-01 09:00:00+00',
 -0.45, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Maintenance'), 86.00,
 'Isolate water supply at floor valve and repair pipe joint; dry area thoroughly.',
 FALSE, FALSE),

-- 6
('CX-A006', 'Cleaning team missed 2-day schedule – Block D',
 'Block D restrooms and corridors have not been cleaned for two consecutive days. Multiple complaints received.',
 'Complaint', 'Assigned', 'Medium',
 'Cleaning', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='sara@innova.cx'),
 '2026-03-01 09:30:00+00', '2026-03-01 09:45:00+00', '2026-03-01 10:05:00+00',
 '2026-03-01 12:30:00+00', '2026-03-03 09:30:00+00',
 FALSE, FALSE, '2026-03-01 09:30:00+00',
 -0.30, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='Facilities Management'), 80.00,
 'Dispatch cleaning crew immediately and update schedule rotation.',
 FALSE, FALSE),

-- 7
('CX-A007', 'Perimeter fence section damaged',
 'A 3-metre section of the western perimeter fence has collapsed, creating an unsecured gap.',
 'Complaint', 'Assigned', 'High',
 'Infrastructure', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='hassan@innova.cx'),
 '2026-03-01 10:00:00+00', '2026-03-01 10:12:00+00', '2026-03-01 10:35:00+00',
 '2026-03-01 11:00:00+00', '2026-03-02 10:00:00+00',
 FALSE, FALSE, '2026-03-01 10:00:00+00',
 -0.40, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Safety & Security'), 88.00,
 'Deploy temporary security barrier and arrange permanent fence repair.',
 FALSE, FALSE),

-- 8
('CX-A008', 'VoIP system dropping calls – Finance dept',
 'VoIP phones on the Finance floor dropping all calls after 2 minutes. Business operations impacted.',
 'Inquiry', 'Assigned', 'Medium',
 'Telephony', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='lena@innova.cx'),
 '2026-03-01 10:30:00+00', '2026-03-01 10:45:00+00', '2026-03-01 11:00+00',
 '2026-03-01 13:30:00+00', '2026-03-02 10:30:00+00',
 FALSE, FALSE, '2026-03-01 10:30:00+00',
 -0.20, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='IT'), 81.00,
 'Update QoS rules and SIP trunk configuration; test call stability.',
 FALSE, FALSE),

-- 9
('CX-A009', 'Roof membrane leak – Executive floor',
 'Rainwater seeping through roof membrane into executive office area. Documents at risk.',
 'Complaint', 'Unassigned', 'High',
 'Roof', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 NULL,
 '2026-03-01 11:00:00+00', NULL, NULL,
 '2026-03-01 12:00:00+00', '2026-03-02 11:00:00+00',
 FALSE, FALSE, '2026-03-01 11:00:00+00',
 -0.55, 'Negative', 'High',
 (SELECT id FROM departments WHERE name='Facilities Management'), 85.00,
 'Apply temporary waterproofing patch and schedule full membrane inspection.',
 FALSE, FALSE),

-- 10
('CX-A010', 'Parking bay repeatedly occupied by unknown vehicle',
 'Reserved emergency access bay at entrance C occupied by an unknown vehicle for 3 consecutive days.',
 'Complaint', 'Unassigned', 'Low',
 'Parking', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 NULL,
 '2026-03-01 11:30:00+00', NULL, NULL,
 '2026-03-01 17:30:00+00', '2026-03-04 11:30:00+00',
 FALSE, FALSE, '2026-03-01 11:30:00+00',
 -0.18, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Safety & Security'), 70.00,
 'Review CCTV footage and issue formal removal notice; increase patrol frequency.',
 FALSE, FALSE),

-- ── Historical resolved tickets (past 12 months for analytics) ────────────
-- 11
('CX-H001', 'Gas leak alarm – Main kitchen',
 'Gas sensor triggered in building kitchen. Evacuated area as precaution.',
 'Complaint', 'Resolved', 'Critical',
 'Gas', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-03-05 06:00:00+00', '2025-03-05 06:04:00+00', '2025-03-05 06:24:00+00',
 '2025-03-05 06:30:00+00', '2025-03-05 12:00:00+00',
 FALSE, FALSE, '2025-03-05 06:00:00+00',
 -0.82, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 98.00,
 'Isolate gas supply; replace faulty valve; confirm safe re-entry.',
 FALSE, FALSE),

-- 12
('CX-H002', 'Power outage – Finance floor',
 'Complete power failure affecting Finance department. UPS not kicking in.',
 'Complaint', 'Resolved', 'Critical',
 'Electrical', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='khalid@innova.cx'),
 '2025-04-10 13:00:00+00', '2025-04-10 13:05:00+00', '2025-04-10 13:26:00+00',
 '2025-04-10 13:30:00+00', '2025-04-10 19:00:00+00',
 FALSE, FALSE, '2025-04-10 13:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 96.00,
 'Reset tripped MCB; activate UPS bypass for continuity.',
 FALSE, FALSE),

-- 13
('CX-H003', 'CCTV system completely offline',
 'All 48 cameras showing signal lost on monitoring console. Security breach risk.',
 'Complaint', 'Resolved', 'Critical',
 'CCTV', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='bilal@innova.cx'),
 '2025-05-15 07:00:00+00', '2025-05-15 07:07:00+00', '2025-05-15 07:28:00+00',
 '2025-05-15 07:30:00+00', '2025-05-15 13:00:00+00',
 FALSE, FALSE, '2025-05-15 07:00:00+00',
 -0.75, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Replace NVR hard drive and restore all camera feeds.',
 FALSE, FALSE),

-- 14
('CX-H004', 'Server room overheating',
 'Server room temperature crossed 28°C threshold. Backup cooling unit fault.',
 'Complaint', 'Resolved', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-06-20 14:00:00+00', '2025-06-20 14:04:00+00', '2025-06-20 14:27:00+00',
 '2025-06-20 14:30:00+00', '2025-06-20 20:00:00+00',
 FALSE, FALSE, '2025-06-20 14:00:00+00',
 -0.68, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 95.00,
 'Activate redundant cooling; repair primary unit compressor.',
 FALSE, FALSE),

-- 15
('CX-H005', 'Water ingress – basement carpark flooding',
 'Heavy rain caused flooding in basement carpark. Vehicles and equipment at risk.',
 'Complaint', 'Resolved', 'Critical',
 'Civil', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-07-08 06:00:00+00', '2025-07-08 06:06:00+00', '2025-07-08 06:28:00+00',
 '2025-07-08 06:30:00+00', '2025-07-08 12:00:00+00',
 FALSE, FALSE, '2025-07-08 06:00:00+00',
 -0.80, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 94.00,
 'Deploy pumping crew; clear drainage channels immediately.',
 FALSE, FALSE),

-- 16
('CX-H006', 'Intruder detected – rooftop after hours',
 'Motion sensors triggered on restricted rooftop area at 23:15. Unclear if threat.',
 'Complaint', 'Resolved', 'Critical',
 'Security', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='omar@innova.cx'),
 '2025-08-22 23:00:00+00', '2025-08-22 23:04:00+00', '2025-08-22 23:27:00+00',
 '2025-08-22 23:30:00+00', '2025-08-23 05:00:00+00',
 FALSE, FALSE, '2025-08-22 23:00:00+00',
 -0.60, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 97.00,
 'Secure rooftop; review access logs; replace door lock.',
 FALSE, FALSE),

-- 17
('CX-H007', 'Chiller plant failure – building-wide cooling',
 'Main chiller breakdown caused complete loss of cooling across all floors.',
 'Complaint', 'Resolved', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-09-12 08:00:00+00', '2025-09-12 08:04:00+00', '2025-09-12 08:28:00+00',
 '2025-09-12 08:30:00+00', '2025-09-12 20:00:00+00',
 FALSE, FALSE, '2025-09-12 08:00:00+00',
 -0.72, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 97.00,
 'Replace compressor and recharge refrigerant; restore chiller operation.',
 FALSE, FALSE),

-- 18
('CX-H008', 'Wi-Fi dead zone – Conference rooms 3A-3D',
 'No wireless connectivity across 4 conference rooms during back-to-back client meetings.',
 'Inquiry', 'Resolved', 'Medium',
 'Network', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='fatima@innova.cx'),
 '2025-10-14 10:00:00+00', '2025-10-14 10:25:00+00', '2025-10-14 13:00:00+00',
 '2025-10-14 13:00:00+00', '2025-10-15 10:00:00+00',
 FALSE, FALSE, '2025-10-14 10:00:00+00',
 -0.15, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='IT'), 82.00,
 'Install additional access point and verify full conference room coverage.',
 FALSE, FALSE),

-- 19
('CX-H009', 'Fire suppression system test failure – server room',
 'Annual suppression test failed. System will not trigger on test activation.',
 'Complaint', 'Resolved', 'Critical',
 'Fire Safety', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-11-04 08:00:00+00', '2025-11-04 08:04:00+00', '2025-11-04 08:28:00+00',
 '2025-11-04 08:30:00+00', '2025-11-04 18:00:00+00',
 FALSE, FALSE, '2025-11-04 08:00:00+00',
 -0.55, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Safety & Security'), 98.00,
 'Replace suppression head; retest system and obtain compliance certificate.',
 FALSE, FALSE),

-- 20
('CX-H010', 'UPS batteries below minimum capacity',
 'Data centre UPS batteries flagged at 18% capacity. Emergency runtime insufficient.',
 'Complaint', 'Resolved', 'Critical',
 'Electrical', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2025-12-10 09:00:00+00', '2025-12-10 09:04:00+00', '2025-12-10 09:27:00+00',
 '2025-12-10 09:30:00+00', '2025-12-10 21:00:00+00',
 FALSE, FALSE, '2025-12-10 09:00:00+00',
 -0.48, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='IT'), 97.00,
 'Replace all UPS battery modules; run runtime certification test.',
 FALSE, FALSE),

-- 21
('CX-H011', 'Boiler failure – Building A heating',
 'Entire Building A without heating during winter. Heat exchanger fault.',
 'Complaint', 'Resolved', 'Critical',
 'HVAC', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='ahmed@innova.cx'),
 '2026-01-08 07:00:00+00', '2026-01-08 07:05:00+00', '2026-01-08 07:28:00+00',
 '2026-01-08 07:30:00+00', '2026-01-08 19:00:00+00',
 FALSE, FALSE, '2026-01-08 07:00:00+00',
 -0.70, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 96.00,
 'Replace heat exchanger and restore building pressure.',
 FALSE, FALSE),

-- 22
('CX-H012', 'VPN access failure – all remote staff',
 'Remote employees unable to connect to internal VPN since certificate expiry.',
 'Inquiry', 'Resolved', 'High',
 'Network', (SELECT id FROM departments WHERE name='IT'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='fatima@innova.cx'),
 '2026-01-20 09:00:00+00', '2026-01-20 09:18:00+00', '2026-01-20 10:00:00+00',
 '2026-01-20 10:00:00+00', '2026-01-21 09:00:00+00',
 FALSE, FALSE, '2026-01-20 09:00:00+00',
 -0.25, 'Neutral', 'High',
 (SELECT id FROM departments WHERE name='IT'), 78.00,
 'Renew VPN gateway certificate and update routing tables.',
 FALSE, FALSE),

-- 23
('CX-H013', 'Electrical main distribution board tripped',
 'Main DB tripped cutting power to floors 3 and 4. Faulty MCB identified.',
 'Complaint', 'Resolved', 'Critical',
 'Electrical', (SELECT id FROM departments WHERE name='Facilities Management'),
 (SELECT id FROM users WHERE email='customer3@innova.cx'),
 (SELECT id FROM users WHERE email='khalid@innova.cx'),
 '2026-02-05 07:00:00+00', '2026-02-05 07:05:00+00', '2026-02-05 07:27:00+00',
 '2026-02-05 07:30:00+00', '2026-02-05 15:00:00+00',
 FALSE, FALSE, '2026-02-05 07:00:00+00',
 -0.65, 'Negative', 'Critical',
 (SELECT id FROM departments WHERE name='Facilities Management'), 96.00,
 'Replace faulty MCB and redistribute electrical load across circuits.',
 FALSE, FALSE),

-- 24
('CX-H014', 'Smoke detector false alarms – laboratory',
 'Lab smoke detector triggering false alarms every morning causing unnecessary evacuations.',
 'Complaint', 'Resolved', 'Medium',
 'Fire Safety', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer2@innova.cx'),
 (SELECT id FROM users WHERE email='bilal@innova.cx'),
 '2026-02-15 10:00:00+00', '2026-02-15 10:18:00+00', '2026-02-15 11:00:00+00',
 '2026-02-15 13:00:00+00', '2026-02-16 10:00:00+00',
 FALSE, FALSE, '2026-02-15 10:00:00+00',
 -0.30, 'Negative', 'Medium',
 (SELECT id FROM departments WHERE name='Safety & Security'), 81.00,
 'Replace detector head and recalibrate sensitivity threshold.',
 FALSE, FALSE),

-- 25 (Escalated, SLA breached)
('CX-H015', 'Parking access card system – repeated failures',
 'Customer parking access cards failing at gate reader. Issue recurring for third time this month.',
 'Inquiry', 'Overdue', 'Medium',
 'Access Control', (SELECT id FROM departments WHERE name='Safety & Security'),
 (SELECT id FROM users WHERE email='customer1@innova.cx'),
 (SELECT id FROM users WHERE email='omar@innova.cx'),
 '2026-02-20 08:00:00+00', '2026-02-20 08:30:00+00', '2026-02-20 11:30:00+00',
 '2026-02-20 11:00:00+00', '2026-02-22 08:00:00+00',
 TRUE, FALSE, '2026-02-20 08:00:00+00',
 -0.10, 'Neutral', 'Medium',
 (SELECT id FROM departments WHERE name='Safety & Security'), 75.00,
 'Re-encode access card and test all gate readers; confirm system-side permissions.',
 FALSE, TRUE)

ON CONFLICT (ticket_code) DO NOTHING;

-- Set resolved_at and resolved_by for historical resolved tickets
UPDATE tickets SET
  resolved_at = created_at + interval '8 hours',
  resolved_by_user_id = assigned_to_user_id
WHERE ticket_code IN ('CX-H001','CX-H002','CX-H003','CX-H004','CX-H005',
                      'CX-H006','CX-H007','CX-H008','CX-H009','CX-H010',
                      'CX-H011','CX-H012','CX-H013','CX-H014')
  AND resolved_at IS NULL;

-- =============================================================================
-- 7. TICKET_ATTACHMENTS
-- =============================================================================
INSERT INTO ticket_attachments (ticket_id, file_name, file_url, uploaded_by, uploaded_at)
SELECT t.id, v.fname, v.furl,
  (SELECT id FROM users WHERE email = v.email),
  v.ts::timestamptz
FROM (VALUES
  ('CX-A001', 'server_room_temp_log_2026-03-01.csv',
   'https://storage.innovacx.com/attachments/CX-A001/temp_log.csv',
   'ahmed@innova.cx', '2026-03-01 07:00:00+00'),
  ('CX-A001', 'hvac_unit_photo.jpg',
   'https://storage.innovacx.com/attachments/CX-A001/hvac_photo.jpg',
   'ahmed@innova.cx', '2026-03-01 07:15:00+00'),
  ('CX-A002', 'gate2_reader_error_screenshot.png',
   'https://storage.innovacx.com/attachments/CX-A002/reader_error.png',
   'omar@innova.cx', '2026-03-01 07:55:00+00'),
  ('CX-A004', 'network_topology_floor5.pdf',
   'https://storage.innovacx.com/attachments/CX-A004/network_topology.pdf',
   'fatima@innova.cx', '2026-03-01 08:50:00+00'),
  ('CX-A005', 'leak_damage_photo.jpg',
   'https://storage.innovacx.com/attachments/CX-A005/leak_photo.jpg',
   'ziad@innova.cx', '2026-03-01 09:20:00+00'),
  ('CX-H009', 'suppression_test_report_2025.pdf',
   'https://storage.innovacx.com/attachments/CX-H009/test_report.pdf',
   'ahmed@innova.cx', '2025-11-04 09:00:00+00'),
  ('CX-H010', 'ups_capacity_report_Q4_2025.pdf',
   'https://storage.innovacx.com/attachments/CX-H010/ups_report.pdf',
   'ahmed@innova.cx', '2025-12-10 10:00:00+00'),
  ('CX-H003', 'nvr_error_log_2025-05-15.txt',
   'https://storage.innovacx.com/attachments/CX-H003/nvr_error.txt',
   'bilal@innova.cx', '2025-05-15 08:00:00+00'),
  ('CX-H013', 'electrical_inspection_report.pdf',
   'https://storage.innovacx.com/attachments/CX-H013/inspection.pdf',
   'khalid@innova.cx', '2026-02-05 08:00:00+00'),
  ('CX-H015', 'access_card_system_logs.csv',
   'https://storage.innovacx.com/attachments/CX-H015/card_logs.csv',
   'omar@innova.cx', '2026-02-20 09:00:00+00'),
  ('CX-A007', 'fence_damage_photos.zip',
   'https://storage.innovacx.com/attachments/CX-A007/fence_photos.zip',
   'hassan@innova.cx', '2026-03-01 10:40:00+00'),
  ('CX-H001', 'gas_sensor_alert_log.csv',
   'https://storage.innovacx.com/attachments/CX-H001/gas_log.csv',
   'ahmed@innova.cx', '2025-03-05 07:00:00+00'),
  ('CX-H005', 'carpark_flooding_video.mp4',
   'https://storage.innovacx.com/attachments/CX-H005/flooding.mp4',
   'ahmed@innova.cx', '2025-07-08 07:00:00+00'),
  ('CX-H007', 'chiller_diagnostic_report.pdf',
   'https://storage.innovacx.com/attachments/CX-H007/chiller_diag.pdf',
   'ahmed@innova.cx', '2025-09-12 09:00:00+00'),
  ('CX-H011', 'boiler_replacement_invoice.pdf',
   'https://storage.innovacx.com/attachments/CX-H011/boiler_invoice.pdf',
   'ahmed@innova.cx', '2026-01-08 14:00:00+00'),
  ('CX-H002', 'electrical_panel_photo.jpg',
   'https://storage.innovacx.com/attachments/CX-H002/panel_photo.jpg',
   'khalid@innova.cx', '2025-04-10 14:00:00+00'),
  ('CX-H012', 'vpn_certificate_renewal_log.txt',
   'https://storage.innovacx.com/attachments/CX-H012/vpn_cert.txt',
   'fatima@innova.cx', '2026-01-20 11:00:00+00'),
  ('CX-H006', 'cctv_rooftop_capture.jpg',
   'https://storage.innovacx.com/attachments/CX-H006/rooftop.jpg',
   'omar@innova.cx', '2025-08-23 00:30:00+00'),
  ('CX-H014', 'smoke_detector_calibration_report.pdf',
   'https://storage.innovacx.com/attachments/CX-H014/detector_calib.pdf',
   'bilal@innova.cx', '2026-02-15 12:00:00+00'),
  ('CX-A009', 'roof_leak_damage_assessment.pdf',
   'https://storage.innovacx.com/attachments/CX-A009/roof_assessment.pdf',
   'manager@innova.cx', '2026-03-01 12:00:00+00')
) AS v(ticket_code, fname, furl, email, ts)
JOIN tickets t ON t.ticket_code = v.ticket_code
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_attachments ta WHERE ta.ticket_id = t.id AND ta.file_name = v.fname
);

-- =============================================================================
-- 8. TICKET_UPDATES  (status transitions, notes, escalations)
-- =============================================================================
INSERT INTO ticket_updates (ticket_id, author_user_id, update_type, message, from_status, to_status, meta, created_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code = v.tc),
  (SELECT id FROM users WHERE email = v.email),
  v.utype, v.msg,
  v.from_s::ticket_status,
  v.to_s::ticket_status,
  v.meta::jsonb,
  v.ts::timestamptz
FROM (VALUES
  ('CX-A001','operator@innova.cx','status_change',
   'Critical ticket created via chat escalation. Assigned to Ahmed Hassan.',
   'Unassigned','Assigned',
   '{"source":"chat","escalation_level":1}',
   '2026-03-01 06:08:00+00'),
  ('CX-A001','ahmed@innova.cx','internal_note',
   'On-site. Backup cooling activated. Primary compressor inspection underway.',
   'Assigned','In Progress',
   '{"temp_reading":32.5,"backup_cooling":"active"}',
   '2026-03-01 07:00:00+00'),
  ('CX-A002','operator@innova.cx','status_change',
   'Gate 2 access failure. Omar Ali dispatched. Temporary manual entry authorised.',
   'Unassigned','In Progress',
   '{"affected_staff":32,"manual_entry":"authorised"}',
   '2026-03-01 07:35:00+00'),
  ('CX-A004','fatima@innova.cx','internal_note',
   'Switch identified as failed. Replacement sourced from spares. ETA 1 hour.',
   'Assigned','In Progress',
   '{"floor":5,"affected_workstations":20}',
   '2026-03-01 09:00:00+00'),
  ('CX-H001','ahmed@innova.cx','status_change',
   'Gas leak resolved. Faulty valve replaced. Area cleared for re-entry.',
   'In Progress','Resolved',
   '{"parts_replaced":["valve"],"downtime_minutes":360}',
   '2025-03-05 12:00:00+00'),
  ('CX-H002','khalid@innova.cx','status_change',
   'MCB replaced. Power restored to Finance floor. UPS tested and operational.',
   'In Progress','Resolved',
   '{"parts_replaced":["MCB-3A"],"downtime_minutes":360}',
   '2025-04-10 19:00:00+00'),
  ('CX-H003','bilal@innova.cx','status_change',
   'NVR hard drive replaced. All 48 cameras restored. System tested for 1 hour.',
   'In Progress','Resolved',
   '{"nvr_drives_replaced":1,"cameras_restored":48}',
   '2025-05-15 13:00:00+00'),
  ('CX-H007','ahmed@innova.cx','status_change',
   'Chiller compressor replaced. Refrigerant recharged. Cooling restored to all floors.',
   'In Progress','Resolved',
   '{"parts_replaced":["compressor"],"floors_affected":8}',
   '2025-09-12 20:00:00+00'),
  ('CX-H009','ahmed@innova.cx','status_change',
   'Suppression head replaced. System re-tested with full pass. Certificate issued.',
   'In Progress','Resolved',
   '{"certificate_issued":true,"test_result":"pass"}',
   '2025-11-04 18:00:00+00'),
  ('CX-H010','ahmed@innova.cx','status_change',
   'All UPS battery modules replaced. Runtime certified at 45 minutes.',
   'In Progress','Resolved',
   '{"batteries_replaced":12,"certified_runtime_mins":45}',
   '2025-12-10 21:00:00+00'),
  ('CX-H011','ahmed@innova.cx','status_change',
   'Heat exchanger replaced. Boiler pressure normalised. Heating restored.',
   'In Progress','Resolved',
   '{"parts_replaced":["heat_exchanger"],"downtime_hours":12}',
   '2026-01-08 19:00:00+00'),
  ('CX-H013','khalid@innova.cx','status_change',
   'Faulty MCB replaced. Load redistributed across circuits. Power fully restored.',
   'In Progress','Resolved',
   '{"floors_affected":2,"mcb_replaced":"MCB-Phase-2"}',
   '2026-02-05 15:00:00+00'),
  ('CX-H015','manager@innova.cx','escalation',
   'SLA breached — response time exceeded by 30 minutes. Escalating to manager review.',
   'Assigned','Overdue',
   '{"breach_minutes":30,"escalated_by":"system"}',
   '2026-02-20 11:31:00+00'),
  ('CX-A009','manager@innova.cx','internal_note',
   'Unassigned — awaiting Facilities team availability. Temporary bucket placement authorised.',
   'Unassigned','Unassigned',
   '{"temporary_measure":"bucket_placement"}',
   '2026-03-01 11:30:00+00'),
  ('CX-H014','bilal@innova.cx','status_change',
   'Detector head replaced and recalibrated. No false alarms in 48-hour test period.',
   'In Progress','Resolved',
   '{"test_period_hours":48,"false_alarms_since_fix":0}',
   '2026-02-16 10:00:00+00'),
  ('CX-H012','fatima@innova.cx','status_change',
   'VPN certificate renewed. All remote users confirmed back online.',
   'In Progress','Resolved',
   '{"users_affected":45,"certificate_expiry":"2027-01-20"}',
   '2026-01-21 09:00:00+00'),
  ('CX-H015','omar@innova.cx','internal_note',
   'Re-encoded 5 cards and tested all readers. Issue may be intermittent server-side.',
   'Overdue','Overdue',
   '{"cards_re-encoded":5,"readers_tested":3}',
   '2026-02-21 10:00:00+00'),
  ('CX-A003','khalid@innova.cx','internal_note',
   'Elevator diagnostics complete. Door sensor fault confirmed. Parts on order.',
   'Assigned','Assigned',
   '{"fault":"door_sensor","parts_eta":"2 hours"}',
   '2026-03-01 09:30:00+00'),
  ('CX-A006','sara@innova.cx','internal_note',
   'Cleaning crew deployed to Block D. Deep-clean in progress. ETA completion 14:00.',
   'Assigned','Assigned',
   '{"crew_size":4,"eta_completion":"14:00"}',
   '2026-03-01 10:00:00+00'),
  ('CX-H004','ahmed@innova.cx','status_change',
   'Backup cooling restored server room to 22°C. Primary unit compressor replaced.',
   'In Progress','Resolved',
   '{"final_temp_c":22,"primary_unit_repaired":true}',
   '2025-06-20 20:00:00+00')
) AS v(tc, email, utype, msg, from_s, to_s, meta, ts)
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_updates tu
  WHERE tu.ticket_id = (SELECT id FROM tickets WHERE ticket_code = v.tc)
    AND tu.created_at = v.ts::timestamptz
);

-- =============================================================================
-- 9. TICKET_WORK_STEPS
-- =============================================================================
INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes, occurred_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code = v.tc),
  v.step_no,
  (SELECT id FROM users WHERE email = v.email),
  v.notes, v.ts::timestamptz
FROM (VALUES
  ('CX-A001', 1, 'ahmed@innova.cx',
   'Arrived server room. Temperature at 32.5°C. Backup cooling unit powered on.',
   '2026-03-01 06:55:00+00'),
  ('CX-A001', 2, 'ahmed@innova.cx',
   'Primary AC compressor inspected. Refrigerant leak identified. Parts ordered.',
   '2026-03-01 08:00:00+00'),
  ('CX-A001', 3, 'ahmed@innova.cx',
   'Parts arrived. Compressor replacement in progress.',
   '2026-03-01 10:00:00+00'),
  ('CX-A002', 1, 'omar@innova.cx',
   'Access control server rebooted. Badge DB re-sync initiated.',
   '2026-03-01 07:55:00+00'),
  ('CX-A002', 2, 'omar@innova.cx',
   'Sync completed. 28 of 30 readers online. 2 readers require firmware update.',
   '2026-03-01 09:00:00+00'),
  ('CX-A003', 1, 'khalid@innova.cx',
   'Elevator diagnostics run. Door sensor fault confirmed.',
   '2026-03-01 08:35:00+00'),
  ('CX-A004', 1, 'fatima@innova.cx',
   'Network switch confirmed failed. Replacement sourced from IT spares room.',
   '2026-03-01 08:50:00+00'),
  ('CX-A004', 2, 'fatima@innova.cx',
   'Replacement switch installed. All 20 workstations back online.',
   '2026-03-01 10:00:00+00'),
  ('CX-A005', 1, 'ziad@innova.cx',
   'Water supply isolated at floor valve. Leak source identified as compression joint.',
   '2026-03-01 09:30:00+00'),
  ('CX-A007', 1, 'hassan@innova.cx',
   'Temporary barrier deployed along collapsed fence section. Area cordoned off.',
   '2026-03-01 10:45:00+00'),
  ('CX-H001', 1, 'ahmed@innova.cx',
   'Gas supply isolated at main valve. Evacuated kitchen area.',
   '2025-03-05 06:30:00+00'),
  ('CX-H001', 2, 'ahmed@innova.cx',
   'Faulty gas valve replaced. Leak test passed. Area cleared for re-entry.',
   '2025-03-05 10:00:00+00'),
  ('CX-H002', 1, 'khalid@innova.cx',
   'Faulty MCB-3A identified in main distribution board.',
   '2025-04-10 13:30:00+00'),
  ('CX-H002', 2, 'khalid@innova.cx',
   'MCB replaced. Power restored to Finance floor. UPS bypass disengaged.',
   '2025-04-10 17:00:00+00'),
  ('CX-H009', 1, 'ahmed@innova.cx',
   'Test activation failed — suppression head confirmed defective.',
   '2025-11-04 09:00:00+00'),
  ('CX-H009', 2, 'ahmed@innova.cx',
   'New suppression head installed. System retested — full pass.',
   '2025-11-04 14:00:00+00'),
  ('CX-H010', 1, 'ahmed@innova.cx',
   'UPS capacity confirmed at 18% across all 12 modules.',
   '2025-12-10 09:30:00+00'),
  ('CX-H010', 2, 'ahmed@innova.cx',
   'All 12 battery modules replaced. Runtime test: 47 minutes certified.',
   '2025-12-10 16:00:00+00'),
  ('CX-H011', 1, 'ahmed@innova.cx',
   'Heat exchanger identified as failed. Emergency parts ordered.',
   '2026-01-08 08:00:00+00'),
  ('CX-H011', 2, 'ahmed@innova.cx',
   'Heat exchanger replaced. Boiler restarted. Heating restored to all zones.',
   '2026-01-08 15:00:00+00'),
  ('CX-H013', 1, 'khalid@innova.cx',
   'Faulty MCB identified in Phase 2 of main DB.',
   '2026-02-05 07:30:00+00'),
  ('CX-H013', 2, 'khalid@innova.cx',
   'MCB replaced. Load redistributed. Full power restored floors 3-4.',
   '2026-02-05 12:00:00+00')
) AS v(tc, step_no, email, notes, ts)
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_work_steps tws
  WHERE tws.ticket_id = (SELECT id FROM tickets WHERE ticket_code = v.tc)
    AND tws.step_no = v.step_no
);

-- =============================================================================
-- 10. TICKET_RESOLUTION_FEEDBACK
-- =============================================================================
INSERT INTO ticket_resolution_feedback (ticket_id, employee_user_id, decision, suggested_resolution, employee_resolution, final_resolution)
SELECT t.id, u.id, fb.decision, fb.suggested, fb.custom, fb.final
FROM (VALUES
  ('CX-H001','ahmed@innova.cx','accepted',
   'Isolate gas supply and replace faulty valve.',
   NULL, 'Gas supply isolated; faulty valve replaced and area cleared for re-entry.'),
  ('CX-H002','khalid@innova.cx','accepted',
   'Reset tripped MCB and test UPS bypass.',
   NULL, 'Faulty MCB replaced; power restored. UPS tested operational.'),
  ('CX-H003','bilal@innova.cx','accepted',
   'Replace NVR hard drive and restore camera feeds.',
   NULL, 'NVR hard drive replaced; all 48 camera feeds restored.'),
  ('CX-H004','ahmed@innova.cx','accepted',
   'Activate backup cooling; repair primary unit.',
   NULL, 'Backup cooling activated; primary compressor replaced.'),
  ('CX-H005','ahmed@innova.cx','accepted',
   'Deploy pumping crew and clear drainage channels.',
   NULL, 'Pumping crew deployed; drainage channel cleared.'),
  ('CX-H006','omar@innova.cx','accepted',
   'Secure rooftop area and review access logs.',
   NULL, 'Area secured; access logs reviewed; door lock replaced.'),
  ('CX-H007','ahmed@innova.cx','accepted',
   'Replace compressor and recharge refrigerant.',
   NULL, 'Compressor replaced and refrigerant recharged. Cooling restored.'),
  ('CX-H008','fatima@innova.cx','declined_custom',
   'Restart AP controller.',
   'Restart alone insufficient — new access point required for coverage.',
   'New AP installed. Signal verified across all 4 conference rooms.'),
  ('CX-H009','ahmed@innova.cx','accepted',
   'Replace suppression head and retest.',
   NULL, 'Suppression head replaced; system retested — full pass. Certificate issued.'),
  ('CX-H010','ahmed@innova.cx','declined_custom',
   'Recharge UPS batteries.',
   'Batteries degraded beyond recharge — full module replacement required.',
   'All 12 UPS battery modules replaced; 47-minute runtime certified.'),
  ('CX-H011','ahmed@innova.cx','accepted',
   'Replace heat exchanger and restore pressure.',
   NULL, 'Heat exchanger replaced; boiler pressure normalised. Heating restored.'),
  ('CX-H012','fatima@innova.cx','accepted',
   'Renew VPN gateway certificate and update routing.',
   NULL, 'VPN certificate renewed; all remote users confirmed online.'),
  ('CX-H013','khalid@innova.cx','accepted',
   'Replace faulty MCB and redistribute load.',
   NULL, 'Faulty MCB replaced; load redistributed. Full power restored.'),
  ('CX-H014','bilal@innova.cx','declined_custom',
   'Replace detector head.',
   'Root cause was accumulated dust — cleaning needed before replacement test.',
   'Detector cleaned and head replaced. No false alarms in 48-hour test.'),
  ('CX-H015','omar@innova.cx','declined_custom',
   'Re-encode access card.',
   'Card re-encode insufficient — server-side permission sync required.',
   'Cards re-encoded; permission sync completed. Readers all operational.')
) AS fb(tc, emp, decision, suggested, custom, final)
JOIN tickets t ON t.ticket_code = fb.tc
JOIN users u ON u.email = fb.emp
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_resolution_feedback trf WHERE trf.ticket_id = t.id AND trf.employee_user_id = u.id
);

-- =============================================================================
-- 11. APPROVAL_REQUESTS
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
  ('REQ-4001','CX-A001','Rescoring','Priority: High','Priority: Critical',
   'Server room temperature escalating beyond thresholds. Critical impact on all IT operations.',
   'ahmed@innova.cx','2026-03-01 06:10:00+00','Approved',
   'manager@innova.cx','2026-03-01 06:20:00+00','Safety-critical — approved immediately.'),
  ('REQ-4002','CX-A002','Rerouting','Dept: Maintenance','Dept: Safety & Security',
   'Badge reader failure is an access control issue — Security team must own this.',
   'omar@innova.cx','2026-03-01 07:40:00+00','Approved',
   'manager@innova.cx','2026-03-01 07:50:00+00','Correct routing — Security confirmed as owner.'),
  ('REQ-4003','CX-A009','Rescoring','Priority: Medium','Priority: High',
   'Executive floor leak now affecting documents and IT equipment. Higher priority justified.',
   'yousef@innova.cx','2026-03-01 11:10:00+00','Pending',
   NULL, NULL, NULL),
  ('REQ-4004','CX-H015','Rescoring','Priority: Medium','Priority: High',
   'Third recurrence of same issue this month. Pattern suggests systemic fault.',
   'omar@innova.cx','2026-02-21 09:00:00+00','Pending',
   NULL, NULL, NULL),
  ('REQ-4005','CX-A003','Rerouting','Dept: Maintenance','Dept: Facilities Management',
   'Elevator is mechanical Facilities asset — should not be logged under Maintenance.',
   'khalid@innova.cx','2026-03-01 09:00:00+00','Rejected',
   'manager@innova.cx','2026-03-01 09:30:00+00','Maintenance is correct for mechanical elevators. Keep as is.'),
  ('REQ-4006','CX-A010','Rescoring','Priority: Low','Priority: Medium',
   'Repeated occupancy of emergency access bay is a safety compliance risk.',
   'hassan@innova.cx','2026-03-01 12:00:00+00','Pending',
   NULL, NULL, NULL),
  ('REQ-4007','CX-H008','Rerouting','Dept: IT','Dept: Facilities Management',
   'VoIP crackling caused by HVAC vibration near server rack — not a pure IT issue.',
   'lena@innova.cx','2025-10-15 11:00:00+00','Rejected',
   'manager@innova.cx','2025-10-15 14:00:00+00','IT confirmed root cause is QoS configuration. Remains in IT.'),
  ('REQ-4008','CX-H014','Rescoring','Priority: Medium','Priority: High',
   'False alarms causing daily evacuations — productivity and safety impact is High not Medium.',
   'bilal@innova.cx','2026-02-15 10:30:00+00','Approved',
   'manager@innova.cx','2026-02-15 11:00:00+00','Agreed — daily disruption warrants High priority.'),
  ('REQ-4009','CX-A005','Rescoring','Priority: High','Priority: Critical',
   'Water near live electrical sockets. Immediate electrocution risk.',
   'ziad@innova.cx','2026-03-01 09:20:00+00','Approved',
   'manager@innova.cx','2026-03-01 09:35:00+00','Electric hazard confirmed — Critical approved.'),
  ('REQ-4010','CX-A006','Rerouting','Dept: Facilities Management','Dept: Maintenance',
   'Cleaning scheduling is owned by Maintenance operations team, not Facilities.',
   'sara@innova.cx','2026-03-01 10:00:00+00','Pending',
   NULL, NULL, NULL)
) AS r(code, tc, rtype, cur, req, reason, sub_email, sub_at, status, dec_email, dec_at, dec_notes)
JOIN tickets t ON t.ticket_code = r.tc
ON CONFLICT (request_code) DO NOTHING;

-- =============================================================================
-- 12. CHAT_CONVERSATIONS
-- =============================================================================
INSERT INTO chat_conversations (id, customer_user_id, channel, created_at, ended_at, status)
VALUES
  ('aaaaaaaa-0001-0001-0001-000000000001'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2026-03-01 06:15:00+00','2026-03-01 06:35:00+00','closed'),
  ('aaaaaaaa-0002-0002-0002-000000000002'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2026-03-01 07:25:00+00','2026-03-01 07:45:00+00','closed'),
  ('aaaaaaaa-0003-0003-0003-000000000003'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'mobile','2026-03-01 08:05:00+00','2026-03-01 08:20:00+00','closed'),
  ('aaaaaaaa-0004-0004-0004-000000000004'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2026-03-01 09:00:00+00',NULL,'open'),
  ('aaaaaaaa-0005-0005-0005-000000000005'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2026-02-28 14:00:00+00','2026-02-28 14:12:00+00','closed'),
  ('aaaaaaaa-0006-0006-0006-000000000006'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'web','2026-02-27 10:00:00+00','2026-02-27 10:20:00+00','closed'),
  ('aaaaaaaa-0007-0007-0007-000000000007'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'mobile','2026-02-25 11:00:00+00','2026-02-25 11:25:00+00','closed'),
  ('aaaaaaaa-0008-0008-0008-000000000008'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2026-02-20 09:00:00+00','2026-02-20 09:10:00+00','closed'),
  ('aaaaaaaa-0009-0009-0009-000000000009'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2026-02-15 16:00:00+00','2026-02-15 16:30:00+00','closed'),
  ('aaaaaaaa-0010-0010-0010-000000000010'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'mobile','2026-02-10 08:00:00+00','2026-02-10 08:18:00+00','closed'),
  ('aaaaaaaa-0011-0011-0011-000000000011'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2026-01-22 13:00:00+00','2026-01-22 13:15:00+00','closed'),
  ('aaaaaaaa-0012-0012-0012-000000000012'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2026-01-10 09:30:00+00','2026-01-10 09:45:00+00','closed'),
  ('aaaaaaaa-0013-0013-0013-000000000013'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'mobile','2025-12-05 10:00:00+00','2025-12-05 10:22:00+00','closed'),
  ('aaaaaaaa-0014-0014-0014-000000000014'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2025-11-18 14:30:00+00','2025-11-18 14:50:00+00','closed'),
  ('aaaaaaaa-0015-0015-0015-000000000015'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2025-10-12 08:45:00+00','2025-10-12 09:00:00+00','closed'),
  ('aaaaaaaa-0016-0016-0016-000000000016'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'web','2025-09-08 11:00:00+00','2025-09-08 11:20:00+00','closed'),
  ('aaaaaaaa-0017-0017-0017-000000000017'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'mobile','2025-08-20 07:30:00+00','2025-08-20 07:50:00+00','closed'),
  ('aaaaaaaa-0018-0018-0018-000000000018'::uuid,
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'web','2025-07-14 15:00:00+00','2025-07-14 15:18:00+00','closed'),
  ('aaaaaaaa-0019-0019-0019-000000000019'::uuid,
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'web','2025-06-10 09:00:00+00','2025-06-10 09:12:00+00','closed'),
  ('aaaaaaaa-0020-0020-0020-000000000020'::uuid,
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'web','2025-05-22 10:00:00+00','2025-05-22 10:30:00+00','closed')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- 13. CHAT_MESSAGES
-- =============================================================================
INSERT INTO chat_messages (conversation_id, sender_type, sender_user_id, message_text, created_at, intent, category, sentiment_score, escalation_flag, linked_ticket_id)
VALUES
  -- Conv 1: CX-A001 escalation
  ('aaaaaaaa-0001-0001-0001-000000000001'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'The server room AC is completely down! Temperature is at 32 degrees and rising!',
   '2026-03-01 06:15:30+00','report_issue','HVAC',-0.85,FALSE,NULL),
  ('aaaaaaaa-0001-0001-0001-000000000001'::uuid, 'bot', NULL,
   'This sounds critical. I am escalating to an operator immediately.',
   '2026-03-01 06:15:45+00','escalate','HVAC',0.05,TRUE,NULL),
  ('aaaaaaaa-0001-0001-0001-000000000001'::uuid, 'operator',
   (SELECT id FROM users WHERE email='operator@innova.cx'),
   'Critical ticket CX-A001 raised. Ahmed Hassan assigned and en route.',
   '2026-03-01 06:20:00+00','resolution','HVAC',0.30,FALSE,
   (SELECT id FROM tickets WHERE ticket_code='CX-A001')),

  -- Conv 2: CX-A002 escalation
  ('aaaaaaaa-0002-0002-0002-000000000002'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'All badge readers at Gate 2 are refusing our cards. 30 people stuck outside!',
   '2026-03-01 07:25:30+00','report_issue','Access Control',-0.80,FALSE,NULL),
  ('aaaaaaaa-0002-0002-0002-000000000002'::uuid, 'bot', NULL,
   'I understand — this is urgent. Escalating to our security team immediately.',
   '2026-03-01 07:25:45+00','escalate','Access Control',0.05,TRUE,NULL),
  ('aaaaaaaa-0002-0002-0002-000000000002'::uuid, 'operator',
   (SELECT id FROM users WHERE email='operator@innova.cx'),
   'Ticket CX-A002 created as Critical. Omar Ali dispatched. Manual entry authorised.',
   '2026-03-01 07:30:00+00','resolution','Access Control',0.20,FALSE,
   (SELECT id FROM tickets WHERE ticket_code='CX-A002')),

  -- Conv 3: elevator inquiry
  ('aaaaaaaa-0003-0003-0003-000000000003'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'The elevator in Tower 2 is stuck between floors and the alarm keeps going off.',
   '2026-03-01 08:05:30+00','report_issue','Elevator',-0.60,FALSE,NULL),
  ('aaaaaaaa-0003-0003-0003-000000000003'::uuid, 'bot', NULL,
   'Understood. I am raising a High priority ticket for our Facilities team.',
   '2026-03-01 08:05:50+00','create_ticket','Elevator',0.10,FALSE,
   (SELECT id FROM tickets WHERE ticket_code='CX-A003')),
  ('aaaaaaaa-0003-0003-0003-000000000003'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'Thank you. Please make sure someone comes quickly.',
   '2026-03-01 08:06:30+00','close','Elevator',0.20,FALSE,NULL),

  -- Conv 4: open chat (ongoing)
  ('aaaaaaaa-0004-0004-0004-000000000004'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'What is the expected resolution time for ticket CX-A001?',
   '2026-03-01 09:00:30+00','inquiry','HVAC',0.00,FALSE,NULL),
  ('aaaaaaaa-0004-0004-0004-000000000004'::uuid, 'bot', NULL,
   'Ticket CX-A001 is In Progress. Ahmed Hassan is on-site and the target resolve time is 12:00 today.',
   '2026-03-01 09:00:45+00','status_update','HVAC',0.40,FALSE,
   (SELECT id FROM tickets WHERE ticket_code='CX-A001')),

  -- Conv 5: FAQ, no escalation
  ('aaaaaaaa-0005-0005-0005-000000000005'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'What are the SLA times for critical tickets?',
   '2026-02-28 14:00:30+00','inquiry','General',0.10,FALSE,NULL),
  ('aaaaaaaa-0005-0005-0005-000000000005'::uuid, 'bot', NULL,
   'Critical tickets have a 30-minute response SLA and 6-hour resolution SLA.',
   '2026-02-28 14:00:45+00','answer','General',0.50,FALSE,NULL),
  ('aaaaaaaa-0005-0005-0005-000000000005'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'Perfect, thank you.',
   '2026-02-28 14:01:10+00','close','General',0.80,FALSE,NULL),

  -- Conv 6: complaint
  ('aaaaaaaa-0006-0006-0006-000000000006'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'Nobody has cleaned the restrooms in Block D for two days. This is unacceptable!',
   '2026-02-27 10:00:30+00','complaint','Cleaning',-0.70,FALSE,NULL),
  ('aaaaaaaa-0006-0006-0006-000000000006'::uuid, 'bot', NULL,
   'I apologise for this. I have raised a Medium priority ticket for the Facilities team.',
   '2026-02-27 10:00:50+00','create_ticket','Cleaning',0.10,FALSE,NULL),

  -- Conv 7: aggressive user (flagged)
  ('aaaaaaaa-0007-0007-0007-000000000007'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'I have called 3 times and nobody has fixed the AC yet! This is absolutely disgraceful!',
   '2026-02-25 11:00:30+00','complaint','HVAC',-0.95,FALSE,NULL),
  ('aaaaaaaa-0007-0007-0007-000000000007'::uuid, 'bot', NULL,
   'I completely understand your frustration. Connecting you to a senior operator now.',
   '2026-02-25 11:00:50+00','escalate','HVAC',0.05,TRUE,NULL),
  ('aaaaaaaa-0007-0007-0007-000000000007'::uuid, 'operator',
   (SELECT id FROM users WHERE email='operator@innova.cx'),
   'I sincerely apologise. I am personally escalating your case to the department manager.',
   '2026-02-25 11:05:00+00','resolution','HVAC',0.30,FALSE,NULL),

  -- Conv 8–20: brief interactions for volume/analytics
  ('aaaaaaaa-0008-0008-0008-000000000008'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer2@innova.cx'),
   'Can I track the status of my ticket CX-H015?',
   '2026-02-20 09:00:30+00','inquiry','General',0.00,FALSE,NULL),
  ('aaaaaaaa-0008-0008-0008-000000000008'::uuid, 'bot', NULL,
   'Ticket CX-H015 is currently Overdue. Our team has been notified.',
   '2026-02-20 09:00:45+00','status_update','General',0.20,FALSE,
   (SELECT id FROM tickets WHERE ticket_code='CX-H015')),

  ('aaaaaaaa-0009-0009-0009-000000000009'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer1@innova.cx'),
   'How do I submit a maintenance request for a broken window?',
   '2026-02-15 16:00:30+00','inquiry','General',0.10,FALSE,NULL),
  ('aaaaaaaa-0009-0009-0009-000000000009'::uuid, 'bot', NULL,
   'You can raise a ticket using the Complaints section. Select Inquiry and choose Facilities as the department.',
   '2026-02-15 16:00:48+00','answer','General',0.50,FALSE,NULL),

  ('aaaaaaaa-0010-0010-0010-000000000010'::uuid, 'customer',
   (SELECT id FROM users WHERE email='customer3@innova.cx'),
   'The perimeter fence near the west entrance has collapsed.',
   '2026-02-10 08:00:30+00','report_issue','Security',-0.50,FALSE,NULL),
  ('aaaaaaaa-0010-0010-0010-000000000010'::uuid, 'bot', NULL,
   'Thank you for reporting this. I have raised a High priority security ticket.',
   '2026-02-10 08:00:48+00','create_ticket','Security',0.20,FALSE,NULL)

ON CONFLICT DO NOTHING;

-- =============================================================================
-- 14. SESSIONS
-- =============================================================================
INSERT INTO sessions (user_id, current_state, context, history, created_at, updated_at, bot_model_version, escalated_to_human, escalated_at, linked_ticket_id)
VALUES
  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"HVAC","building":"A","floor":"Ground"}',
   '[{"role":"user","msg":"AC down in server room"},{"role":"bot","msg":"Escalating"},{"role":"operator","msg":"Ticket raised"}]',
   '2026-03-01 06:15:00+00','2026-03-01 06:35:00+00','chatbot-v2.1',
   TRUE,'2026-03-01 06:18:00+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A001')),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Access Control","building":"Main","gate":"Gate2"}',
   '[{"role":"user","msg":"Badge readers down"},{"role":"bot","msg":"Escalating"},{"role":"operator","msg":"Omar dispatched"}]',
   '2026-03-01 07:25:00+00','2026-03-01 07:45:00+00','chatbot-v2.1',
   TRUE,'2026-03-01 07:27:00+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A002')),

  ((SELECT id FROM users WHERE email='customer3@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Elevator","building":"Tower2","floors":"4-5"}',
   '[{"role":"user","msg":"Elevator stuck"},{"role":"bot","msg":"Ticket raised"}]',
   '2026-03-01 08:05:00+00','2026-03-01 08:20:00+00','chatbot-v2.1',
   FALSE, NULL,
   (SELECT id FROM tickets WHERE ticket_code='CX-A003')),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'collecting_info',
   '{"last_intent":"inquiry","topic":"ticket_status"}',
   '[{"role":"user","msg":"Status of CX-A001?"}]',
   '2026-03-01 09:00:00+00','2026-03-01 09:01:00+00','chatbot-v2.1',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"sla_times"}',
   '[{"role":"user","msg":"SLA for critical?"},{"role":"bot","msg":"30 min response, 6 hour resolve"}]',
   '2026-02-28 14:00:00+00','2026-02-28 14:12:00+00','chatbot-v2.1',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"complaint","topic":"cleaning","block":"D"}',
   '[{"role":"user","msg":"Restrooms not cleaned"},{"role":"bot","msg":"Ticket raised"}]',
   '2026-02-27 10:00:00+00','2026-02-27 10:20:00+00','chatbot-v2.1',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"complaint","topic":"HVAC","escalation_reason":"repeated_failure"}',
   '[{"role":"user","msg":"AC still not fixed"},{"role":"bot","msg":"Connecting to operator"},{"role":"operator","msg":"Escalated to manager"}]',
   '2026-02-25 11:00:00+00','2026-02-25 11:25:00+00','chatbot-v2.1',
   TRUE,'2026-02-25 11:03:00+00', NULL),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"ticket_status","ticket":"CX-H015"}',
   '[{"role":"user","msg":"Status of CX-H015?"},{"role":"bot","msg":"Overdue"}]',
   '2026-02-20 09:00:00+00','2026-02-20 09:10:00+00','chatbot-v2.1',
   FALSE, NULL,
   (SELECT id FROM tickets WHERE ticket_code='CX-H015')),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"how_to_submit"}',
   '[{"role":"user","msg":"How to raise a ticket?"},{"role":"bot","msg":"Use Complaints section"}]',
   '2026-02-15 16:00:00+00','2026-02-15 16:30:00+00','chatbot-v2.1',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer3@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Security","location":"west_fence"}',
   '[{"role":"user","msg":"Fence collapsed"},{"role":"bot","msg":"High ticket raised"}]',
   '2026-02-10 08:00:00+00','2026-02-10 08:18:00+00','chatbot-v2.1',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"support_hours"}',
   '[{"role":"user","msg":"Support hours?"},{"role":"bot","msg":"24/7 for critical"}]',
   '2026-01-22 13:00:00+00','2026-01-22 13:15:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Network","building":"Tower1","floor":5}',
   '[{"role":"user","msg":"No network on floor 5"},{"role":"bot","msg":"Ticket raised"}]',
   '2026-01-10 09:30:00+00','2026-01-10 09:45:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer3@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"HVAC","building":"B","floor":2}',
   '[{"role":"user","msg":"No heating on floor 2"},{"role":"bot","msg":"Ticket raised"}]',
   '2025-12-05 10:00:00+00','2025-12-05 10:22:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"complaint","topic":"cleaning","floor":3}',
   '[{"role":"user","msg":"Floor 3 not cleaned"},{"role":"bot","msg":"Ticket raised"}]',
   '2025-11-18 14:30:00+00','2025-11-18 14:50:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"wifi","building":"C","rooms":"conference"}',
   '[{"role":"user","msg":"No WiFi in conference rooms"},{"role":"bot","msg":"Medium ticket raised"}]',
   '2025-10-12 08:45:00+00','2025-10-12 09:00:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer3@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Security","type":"intruder_alert"}',
   '[{"role":"user","msg":"Intruder on roof"},{"role":"bot","msg":"Critical ticket — escalating to operator"}]',
   '2025-09-08 11:00:00+00','2025-09-08 11:20:00+00','chatbot-v2.0',
   TRUE,'2025-09-08 11:02:00+00', NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"Security","type":"intruder"}',
   '[{"role":"user","msg":"Motion on rooftop"},{"role":"bot","msg":"Critical ticket raised"}]',
   '2025-08-20 07:30:00+00','2025-08-20 07:50:00+00','chatbot-v2.0',
   TRUE,'2025-08-20 07:32:00+00', NULL),

  ((SELECT id FROM users WHERE email='customer2@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"HVAC","building":"Main","floor":"Basement"}',
   '[{"role":"user","msg":"Basement flooding"},{"role":"bot","msg":"Critical ticket raised"}]',
   '2025-07-14 15:00:00+00','2025-07-14 15:18:00+00','chatbot-v2.0',
   TRUE,'2025-07-14 15:03:00+00', NULL),

  ((SELECT id FROM users WHERE email='customer3@innova.cx'),
   'resolved',
   '{"last_intent":"inquiry","topic":"fire_safety"}',
   '[{"role":"user","msg":"What do I do in a fire?"},{"role":"bot","msg":"Answered with evacuation procedure"}]',
   '2025-06-10 09:00:00+00','2025-06-10 09:12:00+00','chatbot-v2.0',
   FALSE, NULL, NULL),

  ((SELECT id FROM users WHERE email='customer1@innova.cx'),
   'resolved',
   '{"last_intent":"report_issue","asset":"CCTV","type":"system_down"}',
   '[{"role":"user","msg":"All CCTV down"},{"role":"bot","msg":"Critical ticket raised — escalating"}]',
   '2025-05-22 10:00:00+00','2025-05-22 10:30:00+00','chatbot-v2.0',
   TRUE,'2025-05-22 10:05:00+00', NULL)

ON CONFLICT DO NOTHING;

-- =============================================================================
-- 15. USER_CHAT_LOGS
-- =============================================================================
INSERT INTO user_chat_logs (user_id, session_id, message, intent_detected, aggression_flag, aggression_score, created_at, sentiment_score, category, response_time_ms, ticket_id)
SELECT
  (SELECT id FROM users WHERE email = v.email),
  s.session_id,
  v.msg, v.intent, v.agg, v.agg_score, v.ts::timestamptz,
  v.sent, v.cat, v.resp_ms,
  CASE WHEN v.tc IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code = v.tc) ELSE NULL END
FROM (VALUES
  ('customer1@innova.cx','2026-03-01 06:15:30+00',
   'The server room AC is completely down. Temperature is at 32 degrees!',
   'report_issue',FALSE,0.0180,-0.85,'HVAC',NULL,'CX-A001'),
  ('customer2@innova.cx','2026-03-01 07:25:30+00',
   'Badge readers at Gate 2 are refusing all cards. 30 people stuck outside!',
   'report_issue',FALSE,0.0250,-0.80,'Access Control',NULL,'CX-A002'),
  ('customer3@innova.cx','2026-03-01 08:05:30+00',
   'The elevator in Tower 2 is stuck and alarm keeps going off.',
   'report_issue',FALSE,0.0150,-0.60,'Elevator',1100,'CX-A003'),
  ('customer1@innova.cx','2026-03-01 09:00:30+00',
   'What is the expected resolution time for ticket CX-A001?',
   'inquiry',FALSE,0.0080,0.00,'HVAC',800,NULL),
  ('customer2@innova.cx','2026-02-28 14:00:30+00',
   'What are the SLA times for critical tickets?',
   'inquiry',FALSE,0.0060,0.10,'General',650,NULL),
  ('customer1@innova.cx','2026-02-27 10:00:30+00',
   'Nobody has cleaned the restrooms in Block D for two days. Unacceptable!',
   'complaint',FALSE,0.3200,-0.70,'Cleaning',950,NULL),
  ('customer1@innova.cx','2026-02-25 11:00:30+00',
   'I have called 3 times and nobody fixed the AC yet. Absolutely disgraceful!',
   'complaint',TRUE,0.8100,-0.95,'HVAC',NULL,NULL),
  ('customer2@innova.cx','2026-02-20 09:00:30+00',
   'Can I track the status of my ticket CX-H015?',
   'inquiry',FALSE,0.0050,0.00,'General',700,'CX-H015'),
  ('customer1@innova.cx','2026-02-15 16:00:30+00',
   'How do I submit a maintenance request for a broken window?',
   'inquiry',FALSE,0.0040,0.10,'General',580,NULL),
  ('customer3@innova.cx','2026-02-10 08:00:30+00',
   'The perimeter fence near the west entrance has completely collapsed.',
   'report_issue',FALSE,0.0200,-0.50,'Security',920,NULL),
  ('customer1@innova.cx','2026-01-22 13:00:30+00',
   'What are your support hours for facilities management?',
   'inquiry',FALSE,0.0030,0.10,'General',610,NULL),
  ('customer2@innova.cx','2026-01-10 09:30:30+00',
   'All workstations on Floor 5 have no network access since this morning.',
   'report_issue',FALSE,0.0120,-0.40,'Network',NULL,NULL),
  ('customer3@innova.cx','2025-12-05 10:00:30+00',
   'There is no heating on the second floor of Building B.',
   'report_issue',FALSE,0.0100,-0.35,'HVAC',1000,NULL),
  ('customer1@innova.cx','2025-11-18 14:30:30+00',
   'The third floor has not been cleaned today and it is very messy.',
   'complaint',FALSE,0.1800,-0.45,'Cleaning',870,NULL),
  ('customer2@innova.cx','2025-10-12 08:45:30+00',
   'Wi-Fi in all conference rooms on Floor 3 is completely down.',
   'report_issue',FALSE,0.0140,-0.30,'IT',940,NULL),
  ('customer3@innova.cx','2025-09-08 11:00:30+00',
   'Motion sensors went off on the rooftop at 3 AM — possible intruder.',
   'report_issue',FALSE,0.0500,-0.55,'Security',1150,NULL),
  ('customer1@innova.cx','2025-08-20 07:30:30+00',
   'Security camera system is completely offline — all cameras showing no signal.',
   'report_issue',FALSE,0.0220,-0.65,'Security',NULL,NULL),
  ('customer2@innova.cx','2025-07-14 15:00:30+00',
   'The basement carpark is flooding from the heavy rain.',
   'report_issue',FALSE,0.0380,-0.78,'Civil',NULL,NULL),
  ('customer1@innova.cx','2025-06-10 09:00:30+00',
   'What should I do if I smell gas in the building?',
   'inquiry',FALSE,0.0050,0.05,'Safety',620,NULL),
  ('customer3@innova.cx','2025-05-22 10:00:30+00',
   'All cameras on the security monitoring system are showing no signal.',
   'report_issue',FALSE,0.0280,-0.72,'Security',NULL,NULL)
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
-- 16. BOT_RESPONSE_LOGS
-- =============================================================================
INSERT INTO bot_response_logs (response, response_type, state_at_time, sql_query_used, kb_match_score, created_at, ticket_id)
VALUES
  ('This sounds critical. I am escalating to an operator immediately.',
   'escalation', 'escalate', NULL, NULL, '2026-03-01 06:15:45+00', NULL),
  ('Critical ticket CX-A001 raised. Ahmed Hassan assigned and en route.',
   'resolution', 'resolved', NULL, NULL, '2026-03-01 06:20:00+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A001')),
  ('I understand — this is urgent. Escalating to our security team immediately.',
   'escalation', 'escalate', NULL, NULL, '2026-03-01 07:25:45+00', NULL),
  ('Ticket CX-A002 created as Critical. Omar Ali dispatched. Manual entry authorised.',
   'resolution', 'resolved', NULL, NULL, '2026-03-01 07:30:00+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A002')),
  ('Understood. I am raising a High priority ticket for our Facilities team.',
   'create_ticket', 'ticket_creation', NULL, NULL, '2026-03-01 08:05:50+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A003')),
  ('Ticket CX-A001 is In Progress. Ahmed Hassan is on-site and the target resolve time is 12:00 today.',
   'status_update', 'answer',
   'SELECT * FROM tickets WHERE ticket_code=''CX-A001''', 0.96000,
   '2026-03-01 09:00:45+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-A001')),
  ('Critical tickets have a 30-minute response SLA and 6-hour resolution SLA.',
   'faq_answer', 'answer',
   'SELECT * FROM kb WHERE topic=''sla_times''', 0.94200,
   '2026-02-28 14:00:45+00', NULL),
  ('I apologise for this. I have raised a Medium priority ticket for the Facilities team.',
   'create_ticket', 'ticket_creation', NULL, NULL,
   '2026-02-27 10:00:50+00', NULL),
  ('I completely understand your frustration. Connecting you to a senior operator now.',
   'escalation', 'escalate', NULL, NULL,
   '2026-02-25 11:00:50+00', NULL),
  ('Ticket CX-H015 is currently Overdue. Our team has been notified.',
   'status_update', 'answer',
   'SELECT * FROM tickets WHERE ticket_code=''CX-H015''', 0.97100,
   '2026-02-20 09:00:45+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-H015')),
  ('You can raise a ticket using the Complaints section. Select Inquiry and choose Facilities as the department.',
   'faq_answer', 'answer',
   'SELECT * FROM kb WHERE topic=''ticket_submission''', 0.91800,
   '2026-02-15 16:00:48+00', NULL),
  ('Facilities Management is available 24/7 for critical issues and 7 AM to 10 PM for standard requests.',
   'faq_answer', 'answer',
   'SELECT * FROM kb WHERE topic=''support_hours''', 0.93500,
   '2026-01-22 13:00:45+00', NULL),
  ('If you smell gas, leave the area immediately, do not use electrical switches, and call the emergency line.',
   'safety_response', 'answer',
   'SELECT * FROM kb WHERE topic=''gas_safety''', 0.98700,
   '2025-06-10 09:00:45+00', NULL),
  ('I have raised a Critical security ticket and an operator is being notified immediately.',
   'escalation', 'escalate', NULL, NULL,
   '2025-09-08 11:00:45+00', NULL),
  ('In the event of fire: activate the nearest fire alarm, evacuate via marked exits, and call 999.',
   'safety_response', 'answer',
   'SELECT * FROM kb WHERE topic=''fire_evacuation''', 0.99100,
   '2025-06-10 09:05:00+00', NULL),
  ('The parking management team has been notified. A security officer will attend your bay within 30 minutes.',
   'create_ticket', 'ticket_creation', NULL, NULL,
   '2026-02-10 08:00:48+00', NULL),
  ('Your feedback has been noted. A cleaning supervisor will conduct an inspection today.',
   'acknowledgement', 'resolved',
   NULL, NULL, '2025-11-18 14:35:00+00', NULL),
  ('Wi-Fi issues in conference rooms have been logged as a Medium priority IT ticket.',
   'create_ticket', 'ticket_creation', NULL, NULL,
   '2025-10-12 08:48:00+00', NULL),
  ('I can see your ticket is currently assigned to Fatima Noor. Expected resolution is within 24 hours.',
   'status_update', 'answer',
   'SELECT * FROM tickets WHERE ticket_code=''CX-H012''', 0.95400,
   '2026-01-22 13:05:00+00', NULL),
  ('A high priority network ticket has been raised for Floor 5. Our IT team will respond within 1 hour.',
   'create_ticket', 'ticket_creation', NULL, NULL,
   '2026-01-10 09:33:00+00', NULL)

ON CONFLICT DO NOTHING;

-- =============================================================================
-- 17. NOTIFICATIONS
-- =============================================================================
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = v.email),
  v.ntype::notification_type,
  v.title, v.msg,
  CASE WHEN v.prio IS NOT NULL THEN v.prio::ticket_priority ELSE NULL END,
  CASE WHEN v.tc IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code = v.tc) ELSE NULL END,
  v.read_flag, v.ts::timestamptz
FROM (VALUES
  -- Manager notifications
  ('manager@innova.cx','sla_warning','SLA Warning — CX-A001',
   'Critical ticket CX-A001 (HVAC Server Room) is approaching resolve SLA. 2 hours remaining.',
   'Critical','CX-A001',FALSE,'2026-03-01 10:00:00+00'),
  ('manager@innova.cx','status_change','Ticket Escalated — CX-A002',
   'CX-A002 (Gate 2 badge readers down) — 32 staff affected. Operator assigned.',
   'Critical','CX-A002',FALSE,'2026-03-01 07:40:00+00'),
  ('manager@innova.cx','ticket_assignment','Approval Requested — REQ-4003',
   'Yousef Karim requested priority upgrade for CX-A009 (Roof leak – Executive floor).',
   'High','CX-A009',FALSE,'2026-03-01 11:10:00+00'),
  ('manager@innova.cx','sla_warning','SLA Breached — CX-H015',
   'CX-H015 (Parking card failures) has exceeded response SLA. Immediate action required.',
   'Medium','CX-H015',TRUE,'2026-02-20 11:31:00+00'),
  ('manager@innova.cx','ticket_assignment','Approval Requested — REQ-4004',
   'Omar Ali submitted a rescoring request for CX-H015 — third recurrence of same issue.',
   'Medium','CX-H015',FALSE,'2026-02-21 09:00:00+00'),
  ('manager@innova.cx','status_change','Approval Approved — REQ-4008',
   'You approved the rescoring of CX-H014 from Medium to High. Bilal Khan notified.',
   'High','CX-H014',TRUE,'2026-02-15 11:00:00+00'),
  ('manager@innova.cx','ticket_assignment','Approval Requested — REQ-4006',
   'Hassan Zuberi requested priority change for CX-A010 (Parking bay dispute) to Medium.',
   'Low','CX-A010',FALSE,'2026-03-01 12:00:00+00'),
  ('manager@innova.cx','report_ready','March 2026 Analytics Ready',
   'The monthly analytics report for March 2026 has been generated and is available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),

  -- Ahmed notifications
  ('ahmed@innova.cx','ticket_assignment','New Ticket Assigned: CX-A001',
   'You have been assigned CX-A001 — HVAC offline in Server Room B. Critical priority.',
   'Critical','CX-A001',FALSE,'2026-03-01 06:08:00+00'),
  ('ahmed@innova.cx','sla_warning','SLA Warning: CX-A001',
   'CX-A001 resolve deadline is in 2 hours. Ensure completion before 12:00.',
   'Critical','CX-A001',FALSE,'2026-03-01 10:00:00+00'),
  ('ahmed@innova.cx','customer_reply','Customer replied on CX-H010',
   'Customer confirmed UPS replacement resolved issue. Awaiting formal ticket closure.',
   'Critical','CX-H010',TRUE,'2025-12-10 22:00:00+00'),
  ('ahmed@innova.cx','report_ready','February 2026 Report Ready',
   'Your performance report for February 2026 is now available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),
  ('ahmed@innova.cx','status_change','Ticket Resolved: CX-H011',
   'Ticket CX-H011 (Boiler failure – Building A) has been marked Resolved.',
   'Critical','CX-H011',TRUE,'2026-01-08 19:00:00+00'),

  -- Maria notifications
  ('maria@innova.cx','ticket_assignment','New Ticket Assigned: CX-A008',
   'You have been assigned CX-A008 — VoIP dropping calls – Finance. Medium priority.',
   'Medium','CX-A008',FALSE,'2026-03-01 10:45:00+00'),
  ('maria@innova.cx','report_ready','February 2026 Report Ready',
   'Your performance report for February 2026 is now available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),
  ('maria@innova.cx','sla_warning','SLA Warning: CX-A008',
   'CX-A008 response deadline is in 30 minutes.',
   'Medium','CX-A008',FALSE,'2026-03-01 13:00:00+00'),

  -- Omar notifications
  ('omar@innova.cx','ticket_assignment','New Ticket Assigned: CX-A002',
   'You have been assigned CX-A002 — Gate 2 access failure. Critical priority.',
   'Critical','CX-A002',FALSE,'2026-03-01 07:35:00+00'),
  ('omar@innova.cx','sla_warning','SLA Warning: CX-A002',
   'CX-A002 resolve deadline is in 5 hours. Multiple staff still blocked.',
   'Critical','CX-A002',FALSE,'2026-03-01 08:30:00+00'),
  ('omar@innova.cx','status_change','Approval Decision: REQ-4004',
   'Your rescoring request REQ-4004 for CX-H015 is pending manager review.',
   'Medium','CX-H015',FALSE,'2026-02-21 09:15:00+00'),
  ('omar@innova.cx','system','Scheduled Maintenance Tonight',
   'System maintenance window: tonight 11 PM – 2 AM. No ticket disruption expected.',
   NULL, NULL, TRUE,'2026-02-28 16:00:00+00'),

  -- Sara notifications
  ('sara@innova.cx','ticket_assignment','New Ticket Assigned: CX-A006',
   'You have been assigned CX-A006 — Cleaning missed Block D. Medium priority.',
   'Medium','CX-A006',FALSE,'2026-03-01 09:45:00+00'),
  ('sara@innova.cx','customer_reply','Customer replied on CX-H015',
   'Customer noted recurring issue with parking access card. Third time this month.',
   'Medium','CX-H015',TRUE,'2026-02-21 10:00:00+00'),
  ('sara@innova.cx','report_ready','February 2026 Report Ready',
   'Your performance report for February 2026 is now available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),

  -- Bilal notifications
  ('bilal@innova.cx','ticket_assignment','New Ticket Assigned: CX-A007',
   'You have been assigned CX-A007 — Perimeter fence collapsed. High priority.',
   'High','CX-A007',FALSE,'2026-03-01 10:12:00+00'),
  ('bilal@innova.cx','status_change','Approval Decision: REQ-4008',
   'Your rescoring request REQ-4008 for CX-H014 was approved. Priority changed to High.',
   'High','CX-H014',FALSE,'2026-02-15 11:05:00+00'),
  ('bilal@innova.cx','system','Password Policy Update',
   'Your system password expires in 14 days. Please update via Settings.',
   NULL, NULL, FALSE,'2026-02-26 09:00:00+00'),

  -- Fatima notifications
  ('fatima@innova.cx','ticket_assignment','New Ticket Assigned: CX-A004',
   'You have been assigned CX-A004 — Network outage Floor 5. Critical priority.',
   'Critical','CX-A004',FALSE,'2026-03-01 08:20:00+00'),
  ('fatima@innova.cx','sla_warning','SLA Warning: CX-A004',
   'CX-A004 resolve SLA is in 3 hours. 20 workstations still offline.',
   'Critical','CX-A004',FALSE,'2026-03-01 11:15:00+00'),
  ('fatima@innova.cx','customer_reply','Customer replied on CX-H012',
   'Customer confirmed VPN access restored for all remote staff.',
   'High','CX-H012',TRUE,'2026-01-21 10:00:00+00'),
  ('fatima@innova.cx','report_ready','February 2026 Report Ready',
   'Your performance report for February 2026 is now available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),

  -- Yousef notifications
  ('yousef@innova.cx','ticket_assignment','New Ticket Assigned: CX-A009',
   'You have been assigned CX-A009 — Roof membrane leak – Executive floor. High priority.',
   'High','CX-A009',FALSE,'2026-03-01 11:20:00+00'),
  ('yousef@innova.cx','status_change','Approval Decision: REQ-4003',
   'Your rescoring request REQ-4003 for CX-A009 is pending manager review.',
   'High','CX-A009',FALSE,'2026-03-01 11:15:00+00'),
  ('yousef@innova.cx','report_ready','February 2026 Report Ready',
   'Your performance report for February 2026 is now available.',
   NULL, NULL, FALSE,'2026-03-01 06:00:00+00'),

  -- Khalid notifications
  ('khalid@innova.cx','ticket_assignment','New Ticket Assigned: CX-A003',
   'You have been assigned CX-A003 — Elevator B stuck. High priority.',
   'High','CX-A003',FALSE,'2026-03-01 08:10:00+00'),
  ('khalid@innova.cx','sla_warning','SLA Warning: CX-A003',
   'CX-A003 response deadline is in 30 minutes. Elevator still stuck.',
   'High','CX-A003',FALSE,'2026-03-01 08:30:00+00'),
  ('khalid@innova.cx','status_change','Ticket Resolved: CX-H013',
   'Ticket CX-H013 (Main distribution board tripped) marked Resolved.',
   'Critical','CX-H013',TRUE,'2026-02-05 15:00:00+00'),
  ('khalid@innova.cx','system','System Update Completed',
   'InnovaCX updated to v2.4.2. New analytics dashboard features available.',
   NULL, NULL, TRUE,'2026-02-28 06:00:00+00')
) AS v(email, ntype, title, msg, prio, tc, read_flag, ts)
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = v.email)
    AND n.title = v.title
);

-- =============================================================================
-- 18-22. EMPLOYEE REPORTS (for Ahmed, Maria, Bilal, Yousef, Khalid, Sara, Omar, Fatima)
-- =============================================================================
INSERT INTO employee_reports (report_code, employee_user_id, month_label, subtitle, kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response, model_version, generated_by, period_start, period_end)
SELECT code, emp_id, label, sub, rating, resolved, sla, avg_resp, 'report-gen-v1.0', 'system', ps::date, pe::date
FROM (
  SELECT
    (SELECT id FROM users WHERE email='ahmed@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-ahmed-mar26','rpt-ahmed-feb26','rpt-ahmed-jan26',
                 'rpt-ahmed-dec25','rpt-ahmed-nov25','rpt-ahmed-oct25']) AS code,
    unnest(ARRAY['March 2026','February 2026','January 2026',
                 'December 2025','November 2025','October 2025']) AS label,
    unnest(ARRAY[
      'Strong start to March — 3 critical tickets resolved within SLA.',
      'Excellent month — highest resolution rate in team.',
      'Solid performance. All critical jobs resolved on time.',
      'Good month with no SLA breaches on critical tickets.',
      'Strong performance with high SLA compliance.',
      'Consistent resolution rate across all priorities.'
    ]) AS sub,
    unnest(ARRAY['4.8 / 5','4.9 / 5','4.7 / 5','4.7 / 5','4.7 / 5','4.5 / 5']) AS rating,
    unnest(ARRAY[5, 12, 10, 9, 12, 10]) AS resolved,
    unnest(ARRAY['95%','96%','93%','91%','92%','88%']) AS sla,
    unnest(ARRAY['14 Mins','16 Mins','18 Mins','19 Mins','18 Mins','22 Mins']) AS avg_resp,
    unnest(ARRAY['2026-03-01','2026-02-01','2026-01-01',
                 '2025-12-01','2025-11-01','2025-10-01']) AS ps,
    unnest(ARRAY['2026-03-31','2026-02-28','2026-01-31',
                 '2025-12-31','2025-11-30','2025-10-31']) AS pe

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='bilal@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-bilal-mar26','rpt-bilal-feb26','rpt-bilal-jan26',
                 'rpt-bilal-dec25','rpt-bilal-nov25','rpt-bilal-oct25']),
    unnest(ARRAY['March 2026','February 2026','January 2026',
                 'December 2025','November 2025','October 2025']),
    unnest(ARRAY[
      'High SLA compliance on security tickets.',
      'Zero SLA breaches — best in team for February.',
      'Strong security team performance.',
      'All CCTV and access control tickets resolved within SLA.',
      'High SLA compliance across security tickets.',
      'Above-average month — strong resolve rate.'
    ]),
    unnest(ARRAY['4.7 / 5','4.8 / 5','4.6 / 5','4.7 / 5','4.6 / 5','4.5 / 5']),
    unnest(ARRAY[3, 9, 8, 7, 10, 9]),
    unnest(ARRAY['96%','97%','94%','93%','93%','90%']),
    unnest(ARRAY['15 Mins','16 Mins','18 Mins','17 Mins','17 Mins','19 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2026-01-01',
                 '2025-12-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2026-01-31',
                 '2025-12-31','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='khalid@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-khalid-mar26','rpt-khalid-feb26','rpt-khalid-jan26',
                 'rpt-khalid-dec25','rpt-khalid-nov25','rpt-khalid-oct25']),
    unnest(ARRAY['March 2026','February 2026','January 2026',
                 'December 2025','November 2025','October 2025']),
    unnest(ARRAY[
      'Critical electrical jobs handled with exceptional response times.',
      'All critical electrical faults resolved within SLA.',
      'Strong month — 30-minute response on all critical electrical jobs.',
      'Reliable performance across all electrical ticket types.',
      'All critical tickets resolved within 30-minute response SLA.',
      'Handled complex electrical faults efficiently.'
    ]),
    unnest(ARRAY['4.9 / 5','4.8 / 5','4.8 / 5','4.7 / 5','4.8 / 5','4.7 / 5']),
    unnest(ARRAY[4, 8, 7, 7, 11, 10]),
    unnest(ARRAY['98%','96%','95%','94%','95%','92%']),
    unnest(ARRAY['13 Mins','15 Mins','16 Mins','18 Mins','16 Mins','18 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2026-01-01',
                 '2025-12-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2026-01-31',
                 '2025-12-31','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='fatima@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-fatima-mar26','rpt-fatima-feb26','rpt-fatima-jan26',
                 'rpt-fatima-dec25','rpt-fatima-nov25','rpt-fatima-oct25']),
    unnest(ARRAY['March 2026','February 2026','January 2026',
                 'December 2025','November 2025','October 2025']),
    unnest(ARRAY[
      'Solid IT performance. Critical network issue resolved quickly.',
      'Good consistency — two complex VPN and network issues resolved.',
      'Strong month — VPN and network faults resolved within SLA.',
      'Consistent performance across IT ticket types.',
      'Good month — exceeded SLA targets on IT tickets.',
      'Consistent IT resolve rate with room for improvement.'
    ]),
    unnest(ARRAY['4.5 / 5','4.6 / 5','4.5 / 5','4.4 / 5','4.4 / 5','4.2 / 5']),
    unnest(ARRAY[3, 7, 6, 6, 8, 7]),
    unnest(ARRAY['92%','93%','91%','89%','90%','85%']),
    unnest(ARRAY['20 Mins','19 Mins','21 Mins','22 Mins','20 Mins','24 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2026-01-01',
                 '2025-12-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2026-01-31',
                 '2025-12-31','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='maria@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-maria-mar26','rpt-maria-feb26','rpt-maria-nov25','rpt-maria-oct25']),
    unnest(ARRAY['March 2026','February 2026','November 2025','October 2025']),
    unnest(ARRAY[
      'Good start to month — Wi-Fi issue resolved within SLA.',
      'Solid month with high resolution rate.',
      'Solid month with consistent resolution rate.',
      'Steady performance — slight SLA dip in week 3.'
    ]),
    unnest(ARRAY['4.3 / 5','4.4 / 5','4.4 / 5','4.2 / 5']),
    unnest(ARRAY[2, 8, 8, 7]),
    unnest(ARRAY['91%','89%','89%','85%']),
    unnest(ARRAY['21 Mins','21 Mins','21 Mins','24 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='omar@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-omar-mar26','rpt-omar-feb26','rpt-omar-nov25','rpt-omar-oct25']),
    unnest(ARRAY['March 2026','February 2026','November 2025','October 2025']),
    unnest(ARRAY[
      'Critical access control ticket handled with fast response time.',
      'Moderate month — one SLA breach on overdue ticket.',
      'Good security performance across all ticket types.',
      'Consistent month with room for improvement on response times.'
    ]),
    unnest(ARRAY['4.4 / 5','4.1 / 5','4.3 / 5','4.1 / 5']),
    unnest(ARRAY[2, 6, 7, 6]),
    unnest(ARRAY['93%','84%','88%','82%']),
    unnest(ARRAY['18 Mins','25 Mins','23 Mins','27 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='sara@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-sara-mar26','rpt-sara-feb26','rpt-sara-nov25','rpt-sara-oct25']),
    unnest(ARRAY['March 2026','February 2026','November 2025','October 2025']),
    unnest(ARRAY[
      'Cleaning operations back on track after staffing adjustment.',
      'Steady month — cleaning SLA maintained across all zones.',
      'Good cleaning compliance with minor schedule deviations.',
      'Adequate performance with two SLA breaches due to staffing gaps.'
    ]),
    unnest(ARRAY['4.2 / 5','4.3 / 5','4.2 / 5','4.0 / 5']),
    unnest(ARRAY[2, 7, 7, 6]),
    unnest(ARRAY['88%','90%','86%','82%']),
    unnest(ARRAY['24 Mins','22 Mins','25 Mins','28 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='yousef@innova.cx') AS emp_id,
    unnest(ARRAY['rpt-yousef-mar26','rpt-yousef-feb26','rpt-yousef-nov25','rpt-yousef-oct25']),
    unnest(ARRAY['March 2026','February 2026','November 2025','October 2025']),
    unnest(ARRAY[
      'Good resolve rate — roof and elevator issues handled professionally.',
      'Steady performance — lift maintenance handled on time.',
      'Good resolve rate with room to improve response time.',
      'Steady performance — no SLA breaches on critical tickets.'
    ]),
    unnest(ARRAY['4.4 / 5','4.3 / 5','4.3 / 5','4.4 / 5']),
    unnest(ARRAY[3, 6, 7, 8]),
    unnest(ARRAY['90%','88%','87%','91%']),
    unnest(ARRAY['20 Mins','22 Mins','23 Mins','20 Mins']),
    unnest(ARRAY['2026-03-01','2026-02-01','2025-11-01','2025-10-01']),
    unnest(ARRAY['2026-03-31','2026-02-28','2025-11-30','2025-10-31'])
) sub
ON CONFLICT (report_code) DO NOTHING;

-- ── 19. Summary items ─────────────────────────────────────────────────────
INSERT INTO employee_report_summary_items (report_id, label, value_text)
SELECT er.id, d.label, d.val
FROM employee_reports er
JOIN (VALUES
  ('rpt-ahmed-feb26','Total Assigned','13'),  ('rpt-ahmed-feb26','Resolved','12'),
  ('rpt-ahmed-feb26','Escalated','1'),         ('rpt-ahmed-feb26','Pending','0'),
  ('rpt-ahmed-feb26','Avg Priority','Critical'),('rpt-ahmed-feb26','SLA Breaches','0'),

  ('rpt-bilal-feb26','Total Assigned','10'),  ('rpt-bilal-feb26','Resolved','9'),
  ('rpt-bilal-feb26','Escalated','0'),         ('rpt-bilal-feb26','Pending','1'),
  ('rpt-bilal-feb26','Avg Priority','High'),   ('rpt-bilal-feb26','SLA Breaches','0'),

  ('rpt-khalid-feb26','Total Assigned','9'),  ('rpt-khalid-feb26','Resolved','8'),
  ('rpt-khalid-feb26','Escalated','0'),        ('rpt-khalid-feb26','Pending','1'),
  ('rpt-khalid-feb26','Avg Priority','Critical'),('rpt-khalid-feb26','SLA Breaches','0'),

  ('rpt-fatima-feb26','Total Assigned','8'),  ('rpt-fatima-feb26','Resolved','7'),
  ('rpt-fatima-feb26','Escalated','0'),        ('rpt-fatima-feb26','Pending','1'),
  ('rpt-fatima-feb26','Avg Priority','High'),  ('rpt-fatima-feb26','SLA Breaches','1'),

  ('rpt-omar-feb26','Total Assigned','7'),    ('rpt-omar-feb26','Resolved','6'),
  ('rpt-omar-feb26','Escalated','1'),          ('rpt-omar-feb26','Pending','0'),
  ('rpt-omar-feb26','Avg Priority','Medium'),  ('rpt-omar-feb26','SLA Breaches','1'),

  ('rpt-sara-feb26','Total Assigned','8'),    ('rpt-sara-feb26','Resolved','7'),
  ('rpt-sara-feb26','Escalated','0'),          ('rpt-sara-feb26','Pending','1'),
  ('rpt-sara-feb26','Avg Priority','Medium'),  ('rpt-sara-feb26','SLA Breaches','0'),

  ('rpt-yousef-feb26','Total Assigned','7'),  ('rpt-yousef-feb26','Resolved','6'),
  ('rpt-yousef-feb26','Escalated','0'),        ('rpt-yousef-feb26','Pending','1'),
  ('rpt-yousef-feb26','Avg Priority','High'),  ('rpt-yousef-feb26','SLA Breaches','1'),

  ('rpt-maria-feb26','Total Assigned','9'),   ('rpt-maria-feb26','Resolved','8'),
  ('rpt-maria-feb26','Escalated','1'),         ('rpt-maria-feb26','Pending','0'),
  ('rpt-maria-feb26','Avg Priority','Medium'), ('rpt-maria-feb26','SLA Breaches','1')
) AS d(report_code, label, val) ON d.report_code = er.report_code
WHERE NOT EXISTS (SELECT 1 FROM employee_report_summary_items si WHERE si.report_id = er.id);

-- ── 20. Rating components ──────────────────────────────────────────────────
INSERT INTO employee_report_rating_components (report_id, name, score, pct)
SELECT er.id, d.name, d.score, d.pct
FROM employee_reports er
JOIN (VALUES
  ('rpt-ahmed-feb26','Resolution Rate',4.9,98),
  ('rpt-ahmed-feb26','SLA Compliance',4.8,96),
  ('rpt-ahmed-feb26','Response Speed',4.9,98),
  ('rpt-ahmed-feb26','Customer Satisfaction',4.8,96),

  ('rpt-bilal-feb26','Resolution Rate',4.8,96),
  ('rpt-bilal-feb26','SLA Compliance',4.9,98),
  ('rpt-bilal-feb26','Response Speed',4.8,96),
  ('rpt-bilal-feb26','Customer Satisfaction',4.6,92),

  ('rpt-khalid-feb26','Resolution Rate',4.8,96),
  ('rpt-khalid-feb26','SLA Compliance',4.9,98),
  ('rpt-khalid-feb26','Response Speed',4.9,98),
  ('rpt-khalid-feb26','Customer Satisfaction',4.7,94),

  ('rpt-fatima-feb26','Resolution Rate',4.6,92),
  ('rpt-fatima-feb26','SLA Compliance',4.5,90),
  ('rpt-fatima-feb26','Response Speed',4.6,92),
  ('rpt-fatima-feb26','Customer Satisfaction',4.4,88),

  ('rpt-omar-feb26','Resolution Rate',4.2,84),
  ('rpt-omar-feb26','SLA Compliance',4.0,80),
  ('rpt-omar-feb26','Response Speed',4.1,82),
  ('rpt-omar-feb26','Customer Satisfaction',4.0,80),

  ('rpt-sara-feb26','Resolution Rate',4.4,88),
  ('rpt-sara-feb26','SLA Compliance',4.3,86),
  ('rpt-sara-feb26','Response Speed',4.2,84),
  ('rpt-sara-feb26','Customer Satisfaction',4.3,86),

  ('rpt-yousef-feb26','Resolution Rate',4.4,88),
  ('rpt-yousef-feb26','SLA Compliance',4.2,84),
  ('rpt-yousef-feb26','Response Speed',4.3,86),
  ('rpt-yousef-feb26','Customer Satisfaction',4.2,84),

  ('rpt-maria-feb26','Resolution Rate',4.5,90),
  ('rpt-maria-feb26','SLA Compliance',4.4,88),
  ('rpt-maria-feb26','Response Speed',4.3,86),
  ('rpt-maria-feb26','Customer Satisfaction',4.4,88)
) AS d(report_code, name, score, pct) ON d.report_code = er.report_code
WHERE NOT EXISTS (SELECT 1 FROM employee_report_rating_components rc WHERE rc.report_id = er.id);

-- ── 21. Weekly breakdowns ──────────────────────────────────────────────────
INSERT INTO employee_report_weekly (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text)
SELECT er.id, d.wk, d.asgn, d.res, d.s, d.avg_r, d.dt, d.dtxt
FROM employee_reports er
JOIN (VALUES
  ('rpt-ahmed-feb26','Week 1',4,4,'100%','14 Mins','positive','+100%'),
  ('rpt-ahmed-feb26','Week 2',3,3,'100%','16 Mins','positive','+0%'),
  ('rpt-ahmed-feb26','Week 3',4,3,'75%', '17 Mins','negative','-25%'),
  ('rpt-ahmed-feb26','Week 4',2,2,'100%','17 Mins','positive','+25%'),

  ('rpt-bilal-feb26','Week 1',3,3,'100%','15 Mins','positive','+100%'),
  ('rpt-bilal-feb26','Week 2',2,2,'100%','16 Mins','positive','+0%'),
  ('rpt-bilal-feb26','Week 3',3,2,'67%', '17 Mins','negative','-33%'),
  ('rpt-bilal-feb26','Week 4',2,2,'100%','18 Mins','positive','+33%'),

  ('rpt-khalid-feb26','Week 1',2,2,'100%','13 Mins','positive','+100%'),
  ('rpt-khalid-feb26','Week 2',3,3,'100%','15 Mins','positive','+0%'),
  ('rpt-khalid-feb26','Week 3',2,2,'100%','14 Mins','positive','+0%'),
  ('rpt-khalid-feb26','Week 4',2,1,'50%', '19 Mins','negative','-50%'),

  ('rpt-fatima-feb26','Week 1',2,2,'100%','19 Mins','positive','+100%'),
  ('rpt-fatima-feb26','Week 2',2,1,'50%', '22 Mins','negative','-50%'),
  ('rpt-fatima-feb26','Week 3',2,2,'100%','18 Mins','positive','+50%'),
  ('rpt-fatima-feb26','Week 4',2,2,'100%','18 Mins','positive','+0%')
) AS d(report_code, wk, asgn, res, s, avg_r, dt, dtxt) ON d.report_code = er.report_code
WHERE NOT EXISTS (SELECT 1 FROM employee_report_weekly ew WHERE ew.report_id = er.id);

-- ── 22. Notes ──────────────────────────────────────────────────────────────
INSERT INTO employee_report_notes (report_id, note)
SELECT er.id, d.note
FROM employee_reports er
JOIN (VALUES
  ('rpt-ahmed-feb26','Excellent February — 12 tickets resolved with zero SLA breaches.'),
  ('rpt-ahmed-feb26','Nominated for Employee of the Month for consecutive top performance.'),
  ('rpt-bilal-feb26','Zero SLA breaches in February — best security team record.'),
  ('rpt-bilal-feb26','CCTV restoration handled with exceptional speed and accuracy.'),
  ('rpt-khalid-feb26','Critical electrical response times consistently under 15 minutes.'),
  ('rpt-khalid-feb26','One SLA breach in week 4 — parts delay documented and excused.'),
  ('rpt-fatima-feb26','VPN and network resolutions handled with expertise.'),
  ('rpt-fatima-feb26','Week 2 SLA breach due to third-party vendor delay — noted.'),
  ('rpt-omar-feb26','SLA breach on CX-H015 — recurring issue caused delays. Escalation logged.'),
  ('rpt-omar-feb26','Response speed must improve. Recommend workload redistribution in March.'),
  ('rpt-sara-feb26','Cleaning schedule maintained well. No hygiene complaints received.'),
  ('rpt-yousef-feb26','Lift maintenance backlog cleared effectively in February.')
) AS d(report_code, note) ON d.report_code = er.report_code
WHERE NOT EXISTS (SELECT 1 FROM employee_report_notes en WHERE en.report_id = er.id);

-- =============================================================================
-- 23. SYSTEM_SERVICE_STATUS
-- =============================================================================
INSERT INTO system_service_status (name, status, severity, note, checked_at)
VALUES
  ('API Gateway',         'Healthy',   'ok',       'Normal latency — p99 under 120ms',          now()),
  ('Chatbot Service',     'Healthy',   'ok',       'No errors detected — uptime 99.97%',         now()),
  ('Database',            'Healthy',   'ok',       'Primary reachable — replica lag under 50ms', now()),
  ('Analytics Engine',    'Healthy',   'ok',       'MV refresh completed — all 8 views current', now()),
  ('Auth Service',        'Healthy',   'ok',       'JWT validation normal',                      now()),
  ('File Storage (S3)',   'Healthy',   'ok',       'Upload throughput normal',                   now()),
  ('Email Service (SES)', 'Warning',   'warning',  'Occasional delivery delay — monitoring',     now()),
  ('Notification Worker', 'Healthy',   'ok',       'Queue depth zero — processing in real-time', now()),
  ('Scheduler',           'Healthy',   'ok',       'All cron jobs executed on schedule',         now()),
  ('Model Inference API', 'Healthy',   'ok',       'All 6 agents responding within 10s',         now()),
  ('Cache (Redis)',        'Warning',   'warning',  'Memory at 78% — nearing threshold',          now()),
  ('Load Balancer',        'Healthy',   'ok',       'Active connections: 142 — nominal',          now()),
  ('Backup Service',       'Healthy',   'ok',       'Daily backup completed at 02:00 AM',         now()),
  ('Audit Log Service',    'Healthy',   'ok',       'All events being captured and indexed',      now()),
  ('CDN',                  'Healthy',   'ok',       'Edge nodes all responsive — global coverage',now()),
  ('Search Service',       'Degraded',  'critical', 'Ticket search returning incomplete results — investigating', now()),
  ('SMS Gateway',          'Healthy',   'ok',       'Message delivery rate 99.8%',                now()),
  ('WebSocket Server',     'Healthy',   'ok',       'Active connections: 38 — stable',            now()),
  ('Monitoring Agent',     'Healthy',   'ok',       'Metrics ingestion at normal rate',           now()),
  ('Report Generator',     'Healthy',   'ok',       'Last run completed in 3.2s',                 now())
ON CONFLICT (name) DO UPDATE
  SET status=EXCLUDED.status, severity=EXCLUDED.severity, note=EXCLUDED.note, checked_at=now();

-- =============================================================================
-- 24. SYSTEM_INTEGRATION_STATUS
-- =============================================================================
INSERT INTO system_integration_status (name, status, severity, note, checked_at)
VALUES
  ('Email (SES)',          'Healthy',   'ok',      'Delivery normal — bounce rate under 0.1%',    now()),
  ('Storage (S3)',         'Healthy',   'ok',      'Upload / download speeds normal',             now()),
  ('Twilio SMS',           'Healthy',   'ok',      'Message throughput 300/min',                  now()),
  ('Google Maps API',      'Healthy',   'ok',      'Geocoding requests normal',                   now()),
  ('OpenAI API',           'Warning',   'warning', 'Elevated latency on GPT-4 endpoint — monitoring', now()),
  ('JIRA Integration',     'Healthy',   'ok',      'Ticket sync active — last run 5 min ago',     now()),
  ('LDAP / AD',            'Healthy',   'ok',      'User authentication syncing normally',        now()),
  ('SAP ERP',              'Degraded',  'critical','Asset sync failing — SOAP endpoint timeout',  now()),
  ('Slack Notifications',  'Healthy',   'ok',      'Alert webhooks active — no failures',         now()),
  ('Power BI Connector',   'Healthy',   'ok',      'Analytics data refreshed every 15 minutes',  now()),
  ('Stripe Payments',      'Healthy',   'ok',      'No failed transactions in last 24 hours',     now()),
  ('DocuSign',             'Healthy',   'ok',      'Document signing API operational',            now()),
  ('Salesforce CRM',       'Warning',   'warning', 'Rate limit warnings — queuing requests',      now()),
  ('AWS CloudWatch',       'Healthy',   'ok',      'Log ingestion and alerting normal',           now()),
  ('Zoom API',             'Healthy',   'ok',      'Meeting link generation working',             now()),
  ('PagerDuty',            'Healthy',   'ok',      'Incident routing active',                     now()),
  ('GitHub Actions',       'Healthy',   'ok',      'CI/CD pipelines running normally',            now()),
  ('DataDog APM',          'Healthy',   'ok',      'Trace ingestion normal — no anomalies',      now()),
  ('SendGrid',             'Healthy',   'ok',      'Transactional email delivery normal',         now()),
  ('Zendesk',              'Healthy',   'ok',      'Help centre sync operational',                now())
ON CONFLICT (name) DO UPDATE
  SET status=EXCLUDED.status, severity=EXCLUDED.severity, note=EXCLUDED.note, checked_at=now();

-- =============================================================================
-- 25. SYSTEM_QUEUE_METRICS
-- =============================================================================
INSERT INTO system_queue_metrics (name, value, severity, note, measured_at)
VALUES
  ('Ticket Queue',            '18',  'ok',      'Normal throughput — processing at 22 tickets/hour',  now()),
  ('Escalation Queue',        '4',   'warning', 'Slight backlog — 4 tickets awaiting manager review', now()),
  ('Notification Queue',      '0',   'ok',      'No backlog — all notifications delivered in real-time', now()),
  ('Model Inference Queue',   '2',   'ok',      '2 tickets queued for AI processing — normal',        now()),
  ('Email Queue',             '12',  'warning', 'Minor delay — 12 emails pending delivery',           now()),
  ('Chatbot Session Queue',   '3',   'ok',      '3 active sessions — within capacity',                now()),
  ('Report Generation Queue', '1',   'ok',      '1 report queued — will complete in 30 seconds',      now()),
  ('Attachment Upload Queue', '0',   'ok',      'All uploads processed',                              now()),
  ('Audit Log Queue',         '5',   'ok',      'Flushing to storage — normal batch size',            now()),
  ('SLA Check Queue',         '0',   'ok',      'SLA cron job idle — last run 10 minutes ago',        now()),
  ('Approval Queue',          '5',   'warning', '5 approval requests awaiting manager decision',      now()),
  ('Analytics Refresh Queue', '0',   'ok',      'All 8 MVs current — last refresh 15 min ago',        now()),
  ('SMS Queue',               '0',   'ok',      'All SMS dispatched',                                 now()),
  ('WebSocket Event Queue',   '8',   'ok',      '8 events pending broadcast — real-time',             now()),
  ('Dead Letter Queue',        '1',   'warning', '1 failed task awaiting manual review',              now()),
  ('Password Reset Queue',    '2',   'ok',      '2 reset email requests queued',                      now()),
  ('Data Export Queue',       '0',   'ok',      'No pending export jobs',                             now()),
  ('Backup Queue',            '0',   'ok',      'Next backup scheduled for 02:00 tomorrow',           now()),
  ('Retraining Queue',        '1',   'ok',      '1 model retraining job scheduled for tonight',       now()),
  ('Search Index Queue',      '3',   'warning', '3 tickets pending re-indexing after search issue',   now())
ON CONFLICT (name) DO UPDATE
  SET value=EXCLUDED.value, severity=EXCLUDED.severity, note=EXCLUDED.note, measured_at=now();

-- =============================================================================
-- 26. SYSTEM_EVENT_FEED
-- =============================================================================
INSERT INTO system_event_feed (severity, title, description, event_time)
VALUES
  ('critical', 'Search service degraded',
   'Ticket search returning incomplete results on Floor 5 queries. Engineering team investigating.',
   '2026-03-01 10:45:00+00'),
  ('critical', 'SAP ERP integration timeout',
   'Asset synchronisation with SAP failing — SOAP endpoint returning 503. ERP team alerted.',
   '2026-03-01 09:00:00+00'),
  ('warning', 'Escalation queue backlog',
   'Escalation queue reached 4 items — above normal baseline of 2.',
   '2026-03-01 10:30:00+00'),
  ('warning', 'Redis cache nearing capacity',
   'Cache memory usage at 78%. Monitoring for further growth. Flush scheduled tonight.',
   '2026-03-01 08:00:00+00'),
  ('warning', 'Email delivery delay',
   'SES experiencing minor delivery delays. Monitoring; no action needed yet.',
   '2026-03-01 07:00:00+00'),
  ('info', 'Analytics MVs refreshed successfully',
   'All 8 materialized views refreshed in 3.2s. Data current as of 06:00 AM.',
   '2026-03-01 06:00:00+00'),
  ('info', 'Deployment completed — v2.4.2',
   'InnovaCX platform updated to v2.4.2. New analytics features and bug fixes deployed.',
   '2026-02-28 06:00:00+00'),
  ('info', 'Model retraining completed',
   'Resolution agent v2.0 retrained on 47 new feedback samples. Accuracy improved by 2.1%.',
   '2026-02-27 02:00:00+00'),
  ('warning', 'Approval queue spike',
   '5 approval requests pending — above average for this time period.',
   '2026-02-25 14:00:00+00'),
  ('critical', 'Critical ticket surge — March 1',
   'Ticket volume 45% above baseline in first 4 hours of March 1. CX-A001, A002, A004 all Critical.',
   '2026-03-01 10:00:00+00'),
  ('info', 'Daily backup completed successfully',
   'Full database backup completed at 02:00 AM. Backup size: 4.2 GB. Duration: 8 minutes.',
   '2026-03-01 02:08:00+00'),
  ('info', 'SSL certificate auto-renewed',
   'TLS certificate for api.innovacx.com auto-renewed. Valid for 90 days.',
   '2026-02-28 00:00:00+00'),
  ('warning', 'OpenAI API elevated latency',
   'GPT-4 inference endpoint experiencing 2-3x normal latency. Resolution agent impacted.',
   '2026-02-26 16:00:00+00'),
  ('info', 'Salesforce CRM sync completed',
   'CRM data synchronised — 342 customer records updated.',
   '2026-02-25 08:00:00+00'),
  ('info', 'SLA cron job executed',
   'SLA heartbeat updated 78 active tickets. 2 escalated, 1 marked overdue.',
   '2026-03-01 10:15:00+00'),
  ('critical', 'Power outage – Finance floor',
   'Main distribution board tripped on February 5 — 2 floors without power for 8 hours.',
   '2026-02-05 07:00:00+00'),
  ('info', 'New employee accounts activated',
   '3 new employee accounts (lena, hassan, noura) activated and onboarding emails sent.',
   '2026-02-01 09:00:00+00'),
  ('warning', 'Failed model execution — resolution agent',
   'Resolution agent failed on first attempt for a ticket. Retry succeeded after 15 minutes.',
   '2026-02-22 09:06:00+00'),
  ('info', 'Chat bot model updated',
   'Chatbot upgraded from v2.0 to v2.1. Escalation accuracy improved by 8%.',
   '2026-01-15 06:00:00+00'),
  ('info', 'Quarterly security audit completed',
   'No critical vulnerabilities found. 3 medium findings resolved. Certificate issued.',
   '2026-01-10 12:00:00+00')
ON CONFLICT DO NOTHING;

-- =============================================================================
-- 27. SYSTEM_VERSIONS
-- =============================================================================
INSERT INTO system_versions (component, version, deployed_at)
VALUES
  ('API',                 'v2.4.2',  '2026-02-28'),
  ('Chatbot',             'v2.1',    '2026-01-15'),
  ('Sentiment Agent',     'v3.1',    '2026-01-15'),
  ('Priority Agent',      'v2.4',    '2026-01-15'),
  ('Routing Agent',       'v1.8',    '2025-12-01'),
  ('SLA Agent',           'v1.2',    '2025-11-01'),
  ('Resolution Agent',    'v2.0',    '2026-02-01'),
  ('Feature Agent',       'v1.5',    '2025-12-01'),
  ('Model',               'v2.1',    '2026-01-15'),
  ('Analytics Engine',    'v1.3',    '2026-02-01'),
  ('Report Generator',    'v1.1',    '2025-12-15'),
  ('Auth Service',        'v3.0',    '2025-11-01'),
  ('Notification Worker', 'v1.4',    '2026-01-20'),
  ('File Storage Client', 'v1.2',    '2025-10-01'),
  ('Database',            'v15.4',   '2025-09-01'),
  ('Frontend',            'v3.2.1',  '2026-02-28'),
  ('Mobile App iOS',      'v2.1.0',  '2026-02-15'),
  ('Mobile App Android',  'v2.1.1',  '2026-02-15'),
  ('Admin Dashboard',     'v1.5.0',  '2026-02-01'),
  ('SDK Node.js',         'v1.3.2',  '2026-01-10')
ON CONFLICT (component) DO UPDATE
  SET version=EXCLUDED.version, deployed_at=EXCLUDED.deployed_at;

-- =============================================================================
-- 28. SYSTEM_CONFIG_KV
-- =============================================================================
INSERT INTO system_config_kv (key, value)
VALUES
  ('maintenance_mode',             'false'),
  ('rate_limit',                   'enabled'),
  ('ai_agent_timeout_ms',          '30000'),
  ('sla_escalation_threshold',     '0.90'),
  ('chat_bot_model',               'chatbot-v2.1'),
  ('max_tickets_per_page',         '25'),
  ('sentiment_threshold_neg',      '-0.50'),
  ('sentiment_threshold_pos',      '0.50'),
  ('max_upload_size_mb',           '50'),
  ('session_timeout_minutes',      '60'),
  ('mfa_enforcement',              'optional'),
  ('max_login_attempts',           '5'),
  ('password_expiry_days',         '90'),
  ('default_sla_tier',             'standard'),
  ('escalation_notify_email',      'facilities@innova.cx'),
  ('critical_notify_sms',          'true'),
  ('report_retention_months',      '24'),
  ('analytics_refresh_interval',   '900'),
  ('ticket_auto_close_days',       '30'),
  ('chatbot_escalation_threshold', '0.75'),
  ('model_confidence_min',         '0.65'),
  ('max_attachments_per_ticket',   '10'),
  ('currency',                     'AED'),
  ('timezone',                     'Asia/Dubai'),
  ('locale',                       'en-AE'),
  ('feature_flag_ai_routing',      'true'),
  ('feature_flag_dark_mode',       'true'),
  ('feature_flag_mobile_push',     'true'),
  ('log_level',                    'info'),
  ('support_email',                'support@innova.cx')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
COMMIT;

-- NOTE: ML pipeline seed data (sections 28-35) moved to zzz_seed_analytics.sql,
-- which runs after zzz_analytics_mvs.sh creates those tables.

-- =============================================================================
-- PASSWORD RESET TOKENS (a few for testing)
-- =============================================================================
BEGIN;
INSERT INTO password_reset_tokens (user_id, token_hash, expires_at, used_at) VALUES
  ('b1000000-0000-0000-0000-000000000001', 'abc123tokenhashalice',  now()+interval'1 hour',  NULL),
  ('b1000000-0000-0000-0000-000000000007', 'def456tokenhashgrace',  now()-interval'2 hours', now()-interval'1 hour')
ON CONFLICT DO NOTHING;
COMMIT;
