-- =============================================================================
-- Department Staffing Seed
-- EXACT users: 7 departments x 1 manager + 1 employee each = 14 dept users
-- No generated/bulk users. All emails use @innovacx.net domain.
-- Password for all: Innova@2025
-- =============================================================================

-- Ensure all required departments exist.
INSERT INTO departments (name)
VALUES
  ('Facilities Management'),
  ('Legal & Compliance'),
  ('Safety & Security'),
  ('HR'),
  ('Leasing'),
  ('Maintenance'),
  ('IT')
ON CONFLICT (name) DO NOTHING;

-- =============================================================================
-- MANAGERS (1 per department)
-- =============================================================================
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
  SET role = 'manager', is_active = TRUE, mfa_enabled = FALSE, totp_secret = NULL;

-- =============================================================================
-- EMPLOYEES (1 per department)
-- =============================================================================
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
  SET role = 'employee', is_active = TRUE, mfa_enabled = FALSE, totp_secret = NULL;

-- =============================================================================
-- MANAGER PROFILES
-- =============================================================================
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT u.id,
       m.full_name,
       (SELECT id FROM departments WHERE name = m.dept_name),
       m.emp_code,
       'Department Manager'
FROM (VALUES
  ('hamad@innovacx.net', 'Hamad Alaa',      'IT',                   'MGR-IT01'),
  ('leen@innovacx.net',  'Leen Naser',       'HR',                   'MGR-HR01'),
  ('rami@innovacx.net',  'Rami Alassi',      'Legal & Compliance',   'MGR-LC01'),
  ('majid@innovacx.net', 'Majid Sharaf',     'Maintenance',          'MGR-MN01'),
  ('ali@innovacx.net',   'Ali Al Maharif',   'Safety & Security',    'MGR-SS01'),
  ('yara@innovacx.net',  'Yara Saab',        'Leasing',              'MGR-LS01'),
  ('hana@innovacx.net',  'Hana Ayad',        'Facilities Management','MGR-FM01')
) AS m(email, full_name, dept_name, emp_code)
JOIN users u ON u.email = m.email
ON CONFLICT (user_id) DO UPDATE
  SET full_name     = EXCLUDED.full_name,
      department_id = EXCLUDED.department_id,
      employee_code = EXCLUDED.employee_code,
      job_title     = EXCLUDED.job_title;

-- =============================================================================
-- EMPLOYEE PROFILES
-- =============================================================================
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT u.id,
       e.full_name,
       (SELECT id FROM departments WHERE name = e.dept_name),
       e.emp_code,
       'Support Specialist'
FROM (VALUES
  ('ahmed@innovacx.net',  'Ahmed Hassan',    'IT',                   'EMP-IT01'),
  ('lena@innovacx.net',   'Lena Musa',       'HR',                   'EMP-HR01'),
  ('bilal@innovacx.net',  'Bilal Khan',      'Legal & Compliance',   'EMP-LC01'),
  ('sameer@innovacx.net', 'Sameer Ahmed',    'Maintenance',          'EMP-MN01'),
  ('yousef@innovacx.net', 'Yousef Madi',     'Safety & Security',    'EMP-SS01'),
  ('talya@innovacx.net',  'Talya Mohammad',  'Leasing',              'EMP-LS01'),
  ('sarah@innovacx.net',  'Sarah Muneer',    'Facilities Management','EMP-FM01')
) AS e(email, full_name, dept_name, emp_code)
JOIN users u ON u.email = e.email
ON CONFLICT (user_id) DO UPDATE
  SET full_name     = EXCLUDED.full_name,
      department_id = EXCLUDED.department_id,
      employee_code = EXCLUDED.employee_code,
      job_title     = EXCLUDED.job_title;

-- =============================================================================
-- VERIFICATION
-- =============================================================================
SELECT
  d.name AS department,
  COUNT(*) FILTER (WHERE u.role = 'manager') AS managers,
  COUNT(*) FILTER (WHERE u.role = 'employee') AS employees
FROM departments d
LEFT JOIN user_profiles up ON up.department_id = d.id
LEFT JOIN users u ON u.id = up.user_id AND u.is_active = TRUE
WHERE d.name IN (
  'Facilities Management',
  'Legal & Compliance',
  'Safety & Security',
  'HR',
  'Leasing',
  'Maintenance',
  'IT'
)
GROUP BY d.name
ORDER BY d.name;
