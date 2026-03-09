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

-- Insert manager users
WITH required_departments AS (
  SELECT id, name
  FROM departments
  WHERE name IN (
    'Facilities Management',
    'Legal & Compliance',
    'Safety & Security',
    'HR',
    'Leasing',
    'Maintenance',
    'IT'
  )
),
dept_meta AS (
  SELECT
    id AS department_id,
    name AS department_name,
    lower(regexp_replace(name, '[^a-z0-9]+', '', 'g')) AS slug
  FROM required_departments
),
manager_seed AS (
  SELECT
    department_id,
    department_name,
    slug,
    format('manager.%s@innova.cx', slug) AS email,
    format('%s Manager', replace(department_name, '&', 'and')) AS full_name,
    format('MGR-%s', upper(substr(md5('mgr-' || slug), 1, 8))) AS employee_code
  FROM dept_meta
)
INSERT INTO users (email, password_hash, role, is_active)
SELECT DISTINCT ON (ms.email)
  ms.email,
  crypt('Innova@2025', gen_salt('bf')),
  'manager'::user_role,
  TRUE
FROM manager_seed ms
ORDER BY ms.email
ON CONFLICT (email) DO NOTHING;

-- Insert/update manager profiles
WITH required_departments AS (
  SELECT id, name
  FROM departments
  WHERE name IN (
    'Facilities Management',
    'Legal & Compliance',
    'Safety & Security',
    'HR',
    'Leasing',
    'Maintenance',
    'IT'
  )
),
dept_meta AS (
  SELECT
    id AS department_id,
    name AS department_name,
    lower(regexp_replace(name, '[^a-z0-9]+', '', 'g')) AS slug
  FROM required_departments
),
manager_seed AS (
  SELECT
    department_id,
    department_name,
    slug,
    format('manager.%s@innova.cx', slug) AS email,
    format('%s Manager', replace(department_name, '&', 'and')) AS full_name,
    format('MGR-%s', upper(substr(md5('mgr-' || slug), 1, 8))) AS employee_code
  FROM dept_meta
)
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT DISTINCT ON (u.id)
  u.id,
  ms.full_name,
  ms.department_id,
  ms.employee_code,
  'Department Manager'
FROM manager_seed ms
JOIN users u ON u.email = ms.email
ORDER BY u.id, ms.department_id
ON CONFLICT (user_id) DO UPDATE
SET
  full_name = EXCLUDED.full_name,
  department_id = EXCLUDED.department_id,
  employee_code = EXCLUDED.employee_code,
  job_title = EXCLUDED.job_title;

-- Insert employee users
WITH required_departments AS (
  SELECT id, name
  FROM departments
  WHERE name IN (
    'Facilities Management',
    'Legal & Compliance',
    'Safety & Security',
    'HR',
    'Leasing',
    'Maintenance',
    'IT'
  )
),
dept_meta AS (
  SELECT
    id AS department_id,
    name AS department_name,
    lower(regexp_replace(name, '[^a-z0-9]+', '', 'g')) AS slug
  FROM required_departments
),
employee_seed AS (
  SELECT
    dm.department_id,
    dm.department_name,
    dm.slug,
    gs.n AS seq,
    format('employee.%s.%s@innova.cx', dm.slug, gs.n) AS email,
    format('%s Employee %s', replace(dm.department_name, '&', 'and'), gs.n) AS full_name,
    format('EMP-%s', upper(substr(md5(dm.slug || '-emp-' || gs.n), 1, 8))) AS employee_code
  FROM dept_meta dm
  CROSS JOIN generate_series(1, 10) AS gs(n)
)
INSERT INTO users (email, password_hash, role, is_active)
SELECT DISTINCT ON (es.email)
  es.email,
  crypt('Innova@2025', gen_salt('bf')),
  'employee'::user_role,
  TRUE
FROM employee_seed es
ORDER BY es.email
ON CONFLICT (email) DO NOTHING;

-- Insert/update employee profiles
WITH required_departments AS (
  SELECT id, name
  FROM departments
  WHERE name IN (
    'Facilities Management',
    'Legal & Compliance',
    'Safety & Security',
    'HR',
    'Leasing',
    'Maintenance',
    'IT'
  )
),
dept_meta AS (
  SELECT
    id AS department_id,
    name AS department_name,
    lower(regexp_replace(name, '[^a-z0-9]+', '', 'g')) AS slug
  FROM required_departments
),
employee_seed AS (
  SELECT
    dm.department_id,
    dm.department_name,
    dm.slug,
    gs.n AS seq,
    format('employee.%s.%s@innova.cx', dm.slug, gs.n) AS email,
    format('%s Employee %s', replace(dm.department_name, '&', 'and'), gs.n) AS full_name,
    format('EMP-%s', upper(substr(md5(dm.slug || '-emp-' || gs.n), 1, 8))) AS employee_code
  FROM dept_meta dm
  CROSS JOIN generate_series(1, 10) AS gs(n)
)
INSERT INTO user_profiles (user_id, full_name, department_id, employee_code, job_title)
SELECT DISTINCT ON (u.id)
  u.id,
  es.full_name,
  es.department_id,
  es.employee_code,
  'Support Specialist'
FROM employee_seed es
JOIN users u ON u.email = es.email
ORDER BY u.id, es.department_id
ON CONFLICT (user_id) DO UPDATE
SET
  full_name = EXCLUDED.full_name,
  department_id = EXCLUDED.department_id,
  employee_code = EXCLUDED.employee_code,
  job_title = EXCLUDED.job_title;

-- Verification output.
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