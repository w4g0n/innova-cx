-- =============================================================================
-- MANUAL CLEANUP SQL for EXISTING Docker volumes
--
-- FILE NAME: zzz_manual_cleanup_existing_volume.sql
--
-- PURPOSE: One-time cleanup to migrate old @innova.cx seed users to the new
--          @innovacx.net users on a database volume that already has data.
--
-- SAFE (when run AFTER init.sql): Uses ON CONFLICT DO UPDATE / DO NOTHING.
--   - All inserts are idempotent.
--   - Old @innova.cx user accounts (except operator) are deactivated.
--
-- HOW TO USE:
--   Option A (recommended for fresh volumes): The zzz_ prefix ensures this
--     runs AFTER init.sql when placed in docker-entrypoint-initdb.d/.
--     On a fresh volume it is a safe no-op (users don't exist yet, inserts
--     will skip the DELETE/UPDATE steps that reference old emails).
--
--   Option B (existing volumes with data): Run manually:
--     psql -h localhost -p 5433 -U innovacx_admin -d complaints_db \
--          -f database/zzz_manual_cleanup_existing_volume.sql
--
-- DO NOT keep this file named cleanup_existing_volume.sql — it would run
-- BEFORE init.sql alphabetically and fail on a fresh volume.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1: Insert all correct new users (idempotent)
-- ---------------------------------------------------------------------------

-- Customers
INSERT INTO users (email, password_hash, role, is_active, mfa_enabled, totp_secret)
VALUES
  ('customer1@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer', TRUE, FALSE, NULL),
  ('customer2@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer', TRUE, FALSE, NULL),
  ('customer3@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer', TRUE, FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET role='customer', is_active=TRUE, mfa_enabled=FALSE, totp_secret=NULL,
      password_hash=crypt('Innova@2025', gen_salt('bf', 12));

-- Operator
INSERT INTO users (email, password_hash, role, is_active, mfa_enabled, totp_secret)
VALUES ('operator@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'operator', TRUE, FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET role='operator', is_active=TRUE, mfa_enabled=FALSE, totp_secret=NULL,
      password_hash=crypt('Innova@2025', gen_salt('bf', 12));

-- Managers
INSERT INTO users (email, password_hash, role, is_active, mfa_enabled, totp_secret)
VALUES
  ('hamad@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('leen@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('rami@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('majid@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('ali@innovacx.net',   crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('yara@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL),
  ('hana@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'manager', TRUE, FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET role='manager', is_active=TRUE, mfa_enabled=FALSE, totp_secret=NULL,
      password_hash=crypt('Innova@2025', gen_salt('bf', 12));

-- Employees
INSERT INTO users (email, password_hash, role, is_active, mfa_enabled, totp_secret)
VALUES
  ('ahmed@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('lena@innovacx.net',   crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('bilal@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('sameer@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('yousef@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('talya@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL),
  ('sarah@innovacx.net',  crypt('Innova@2025', gen_salt('bf', 12)), 'employee', TRUE, FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET role='employee', is_active=TRUE, mfa_enabled=FALSE, totp_secret=NULL,
      password_hash=crypt('Innova@2025', gen_salt('bf', 12));

-- ---------------------------------------------------------------------------
-- STEP 2: Upsert user_profiles for all new users
-- ---------------------------------------------------------------------------

-- Operator
INSERT INTO user_profiles (user_id, full_name, job_title)
SELECT id, 'System Operator', 'System Operator' FROM users WHERE email='operator@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

-- Manager profiles
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT u.id, m.full_name, (SELECT id FROM departments WHERE name=m.dept), m.code, 'Department Manager'
FROM (VALUES
  ('hamad@innovacx.net','Hamad Alaa',     'IT',                   'MGR-IT01'),
  ('leen@innovacx.net', 'Leen Naser',     'HR',                   'MGR-HR01'),
  ('rami@innovacx.net', 'Rami Alassi',    'Legal & Compliance',   'MGR-LC01'),
  ('majid@innovacx.net','Majid Sharaf',   'Maintenance',          'MGR-MN01'),
  ('ali@innovacx.net',  'Ali Al Maharif', 'Safety & Security',    'MGR-SS01'),
  ('yara@innovacx.net', 'Yara Saab',      'Leasing',              'MGR-LS01'),
  ('hana@innovacx.net', 'Hana Ayad',      'Facilities Management','MGR-FM01')
) AS m(email, full_name, dept, code)
JOIN users u ON u.email = m.email
ON CONFLICT (user_id) DO UPDATE
  SET full_name=EXCLUDED.full_name, department_id=EXCLUDED.department_id,
      employee_code=EXCLUDED.employee_code, job_title=EXCLUDED.job_title;

-- Employee profiles
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT u.id, e.full_name, (SELECT id FROM departments WHERE name=e.dept), e.code, 'Support Specialist'
FROM (VALUES
  ('ahmed@innovacx.net',  'Ahmed Hassan',   'IT',                   'EMP-IT01'),
  ('lena@innovacx.net',   'Lena Musa',      'HR',                   'EMP-HR01'),
  ('bilal@innovacx.net',  'Bilal Khan',     'Legal & Compliance',   'EMP-LC01'),
  ('sameer@innovacx.net', 'Sameer Ahmed',   'Maintenance',          'EMP-MN01'),
  ('yousef@innovacx.net', 'Yousef Madi',    'Safety & Security',    'EMP-SS01'),
  ('talya@innovacx.net',  'Talya Mohammad', 'Leasing',              'EMP-LS01'),
  ('sarah@innovacx.net',  'Sarah Muneer',   'Facilities Management','EMP-FM01')
) AS e(email, full_name, dept, code)
JOIN users u ON u.email = e.email
ON CONFLICT (user_id) DO UPDATE
  SET full_name=EXCLUDED.full_name, department_id=EXCLUDED.department_id,
      employee_code=EXCLUDED.employee_code, job_title=EXCLUDED.job_title;

-- Customer profiles
INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, c.full_name, c.phone, c.loc
FROM (VALUES
  ('customer1@innovacx.net','Customer One',   '+971500000001','Dubai'),
  ('customer2@innovacx.net','Customer Two',   '+971500000002','Abu Dhabi'),
  ('customer3@innovacx.net','Customer Three', '+971500000003','Sharjah')
) AS c(email, full_name, phone, loc)
JOIN users u ON u.email = c.email
ON CONFLICT (user_id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- STEP 3: Reassign tickets from old customers to new customer accounts.
-- (tickets created by old customers are moved to the corresponding new customer)
-- ---------------------------------------------------------------------------
UPDATE tickets
SET created_by_user_id = (SELECT id FROM users WHERE email='customer1@innovacx.net')
WHERE created_by_user_id IN (
  SELECT id FROM users WHERE email IN ('customer1@innova.cx','customer2@innova.cx','customer3@innova.cx')
)
AND (SELECT id FROM users WHERE email='customer1@innovacx.net') IS NOT NULL;

-- ---------------------------------------------------------------------------
-- STEP 4: Reassign open tickets from old employees to new employees.
-- Only NULL-able FK (assigned_to_user_id) — safe to update.
-- Maps by closest department match.
-- ---------------------------------------------------------------------------
-- Old ahmed/fatima (IT/Maintenance) -> new ahmed (IT)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='ahmed@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('ahmed@innova.cx','fatima@innova.cx')
);

-- Old maria/sara/khalid/dina (Facilities/Maintenance) -> new sarah (Facilities)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='sarah@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('maria@innova.cx','sara@innova.cx','khalid@innova.cx','dina@innova.cx')
);

-- Old omar/hassan (Safety) -> new yousef (Safety)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='yousef@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('omar@innova.cx','hassan@innova.cx')
);

-- Old bilal (Legal/Safety) -> new bilal (Legal)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='bilal@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('bilal@innova.cx')
);

-- Old yousef/ziad/tariq (Maintenance) -> new sameer (Maintenance)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='sameer@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('yousef@innova.cx','ziad@innova.cx','tariq@innova.cx')
);

-- Old lena/rania (HR/IT) -> new lena (HR)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='lena@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('lena@innova.cx','rania@innova.cx')
);

-- Old noura (Leasing) -> new talya (Leasing)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email='talya@innovacx.net')
WHERE assigned_to_user_id IN (
  SELECT id FROM users WHERE email IN ('noura@innova.cx')
);

-- ---------------------------------------------------------------------------
-- STEP 5: Reassign resolution_feedback from old employees to new employees.
-- employee_user_id has ON DELETE RESTRICT so we must update it first.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
  IF to_regclass('public.ticket_resolution_feedback') IS NOT NULL THEN
    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='ahmed@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('ahmed@innova.cx','fatima@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='sarah@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('maria@innova.cx','sara@innova.cx','khalid@innova.cx','dina@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='yousef@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('omar@innova.cx','hassan@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='bilal@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('bilal@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='sameer@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('yousef@innova.cx','ziad@innova.cx','tariq@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='lena@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('lena@innova.cx','rania@innova.cx')
    );

    UPDATE ticket_resolution_feedback
    SET employee_user_id = (SELECT id FROM users WHERE email='talya@innovacx.net')
    WHERE employee_user_id IN (
      SELECT id FROM users WHERE email IN ('noura@innova.cx')
    );
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- STEP 6: Reassign employee_reports from old employees to new employees.
-- ---------------------------------------------------------------------------
UPDATE employee_reports
SET employee_user_id = (SELECT id FROM users WHERE email='ahmed@innovacx.net')
WHERE employee_user_id IN (
  SELECT id FROM users WHERE email IN ('ahmed@innova.cx','fatima@innova.cx')
);

UPDATE employee_reports
SET employee_user_id = (SELECT id FROM users WHERE email='sarah@innovacx.net')
WHERE employee_user_id IN (
  SELECT id FROM users WHERE email IN ('maria@innova.cx','sara@innova.cx','khalid@innova.cx')
);

UPDATE employee_reports
SET employee_user_id = (SELECT id FROM users WHERE email='yousef@innovacx.net')
WHERE employee_user_id IN (
  SELECT id FROM users WHERE email IN ('omar@innova.cx','yousef@innova.cx')
);

UPDATE employee_reports
SET employee_user_id = (SELECT id FROM users WHERE email='bilal@innovacx.net')
WHERE employee_user_id IN (
  SELECT id FROM users WHERE email IN ('bilal@innova.cx')
);

UPDATE employee_reports
SET employee_user_id = (SELECT id FROM users WHERE email='lena@innovacx.net')
WHERE employee_user_id IN (
  SELECT id FROM users WHERE email IN ('lena@innova.cx','rania@innova.cx')
);

-- ---------------------------------------------------------------------------
-- STEP 7: Handle the old manager user — reassign approval_requests references
-- submitted_by_user_id has ON DELETE RESTRICT
-- ---------------------------------------------------------------------------
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='hamad@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email = 'manager@innova.cx'
);

-- ---------------------------------------------------------------------------
-- STEP 8: Reassign approval_requests submitted by old employees
-- ---------------------------------------------------------------------------
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='ahmed@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email IN ('ahmed@innova.cx','fatima@innova.cx')
);
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='yousef@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email IN ('omar@innova.cx','yousef@innova.cx','hassan@innova.cx')
);
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='bilal@innovacx.net')
WHERE submitted_by_user_id IN (SELECT id FROM users WHERE email='bilal@innova.cx');
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='sameer@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email IN ('khalid@innova.cx','ziad@innova.cx','tariq@innova.cx')
);
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='sarah@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email IN ('sara@innova.cx','maria@innova.cx','dina@innova.cx')
);
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='lena@innovacx.net')
WHERE submitted_by_user_id IN (
  SELECT id FROM users WHERE email IN ('lena@innova.cx','rania@innova.cx')
);
UPDATE approval_requests
SET submitted_by_user_id = (SELECT id FROM users WHERE email='talya@innovacx.net')
WHERE submitted_by_user_id IN (SELECT id FROM users WHERE email='noura@innova.cx');

-- ---------------------------------------------------------------------------
-- STEP 9: Safely handle old customer RESTRICT FKs — reassign to new customer1
-- ---------------------------------------------------------------------------
UPDATE tickets
SET created_by_user_id = (SELECT id FROM users WHERE email='customer1@innovacx.net')
WHERE created_by_user_id IN (
  SELECT id FROM users
  WHERE email IN ('customer1@innova.cx','customer2@innova.cx','customer3@innova.cx')
);

-- ---------------------------------------------------------------------------
-- STEP 10: Delete generated department employees (employee.*.N@innova.cx pattern)
-- These were created by seed_department_staffing.sql's generate_series loop.
-- They have no ticket data (FK constraints would prevent deletion otherwise).
-- ---------------------------------------------------------------------------
DELETE FROM user_profiles
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'employee.%.%@innova.cx'
);
DELETE FROM user_preferences
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'employee.%.%@innova.cx'
);
DELETE FROM sessions
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'employee.%.%@innova.cx'
);
DELETE FROM users WHERE email LIKE 'employee.%.%@innova.cx';

-- Delete generated department managers (manager.*.@innova.cx pattern)
DELETE FROM user_profiles
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'manager.%@innova.cx'
);
DELETE FROM user_preferences
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'manager.%@innova.cx'
);
DELETE FROM sessions
WHERE user_id IN (
  SELECT id FROM users WHERE email LIKE 'manager.%@innova.cx'
);
DELETE FROM users WHERE email LIKE 'manager.%@innova.cx';

-- ---------------------------------------------------------------------------
-- STEP 11: Delete old @innova.cx seed users that are now fully dereferenced.
-- (Only deletes if no remaining FK RESTRICT constraints block it.)
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  old_emails TEXT[] := ARRAY[
    'customer1@innova.cx','customer2@innova.cx','customer3@innova.cx',
    'manager@innova.cx',
    'ahmed@innova.cx','maria@innova.cx','omar@innova.cx','sara@innova.cx',
    'bilal@innova.cx','fatima@innova.cx','yousef@innova.cx','khalid@innova.cx',
    'rania@innova.cx','tariq@innova.cx','lena@innova.cx','hassan@innova.cx',
    'noura@innova.cx','ziad@innova.cx','dina@innova.cx'
  ];
  email_val TEXT;
  uid UUID;
BEGIN
  FOREACH email_val IN ARRAY old_emails LOOP
    SELECT id INTO uid FROM users WHERE email = email_val;
    IF uid IS NOT NULL THEN
      -- Attempt deletion; if blocked by RESTRICT, deactivate instead
      BEGIN
        DELETE FROM user_profiles WHERE user_id = uid;
        DELETE FROM user_preferences WHERE user_id = uid;
        DELETE FROM sessions WHERE user_id = uid;
        DELETE FROM notifications WHERE user_id = uid;
        DELETE FROM password_reset_tokens WHERE user_id = uid;
        DELETE FROM users WHERE id = uid;
        RAISE NOTICE 'Deleted user: %', email_val;
      EXCEPTION
        WHEN foreign_key_violation THEN
          UPDATE users SET is_active = FALSE WHERE id = uid;
          RAISE NOTICE 'Could not delete % (FK constraint) — deactivated instead', email_val;
      END;
    END IF;
  END LOOP;
END;
$$;

-- ---------------------------------------------------------------------------
-- STEP 12: Verification — confirm final counts
-- ---------------------------------------------------------------------------
SELECT role, COUNT(*) AS total
FROM users
WHERE is_active = TRUE
GROUP BY role
ORDER BY role;

SELECT
  d.name AS department,
  COUNT(*) FILTER (WHERE u.role = 'manager') AS managers,
  COUNT(*) FILTER (WHERE u.role = 'employee') AS employees
FROM departments d
LEFT JOIN user_profiles up ON up.department_id = d.id
LEFT JOIN users u ON u.id = up.user_id AND u.is_active = TRUE
WHERE d.name IN (
  'Facilities Management','Legal & Compliance','Safety & Security',
  'HR','Leasing','Maintenance','IT'
)
GROUP BY d.name
ORDER BY d.name;

COMMIT;
