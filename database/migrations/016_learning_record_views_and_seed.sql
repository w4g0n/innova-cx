-- Add learning record views and seed demo rows for reroute/rescore references.

CREATE OR REPLACE VIEW vw_reroute_reference_records AS
SELECT
    rr.id,
    rr.ticket_id,
    t.ticket_code,
    rr.department,
    rr.original_dept,
    rr.corrected_dept,
    rr.actor_role,
    rr.source_type,
    rr.source_id,
    rr.decided_by,
    u.email AS decided_by_email,
    rr.created_at
FROM reroute_reference rr
LEFT JOIN tickets t ON t.id = rr.ticket_id
LEFT JOIN users u ON u.id = rr.decided_by;

CREATE OR REPLACE VIEW vw_rescore_reference_records AS
SELECT
    rs.id,
    rs.ticket_id,
    t.ticket_code,
    rs.department,
    rs.original_priority,
    rs.corrected_priority,
    rs.actor_role,
    rs.source_type,
    rs.source_id,
    rs.decided_by,
    u.email AS decided_by_email,
    rs.created_at
FROM rescore_reference rs
LEFT JOIN tickets t ON t.id = rs.ticket_id
LEFT JOIN users u ON u.id = rs.decided_by;

INSERT INTO reroute_reference (
    ticket_id,
    department,
    original_dept,
    corrected_dept,
    actor_role,
    source_type,
    decided_by,
    created_at
)
SELECT
    t.id,
    s.department,
    s.original_dept,
    s.corrected_dept,
    s.actor_role,
    s.source_type,
    u.id,
    s.created_at
FROM (
    VALUES
        ('CX-M53', 'Facilities Management', 'Maintenance', 'Facilities Management', 'manager',  'manager_review',    now() - interval '5 days'),
        ('CX-3862', 'Legal & Compliance',   'HR',          'Legal & Compliance',   'manager',  'employee_request',  now() - interval '3 days'),
        ('CX-M54', 'Safety & Security',     'Facilities Management', 'Safety & Security', 'operator', 'operator_override', now() - interval '36 hours'),
        ('CX-4725', 'IT',                   'Maintenance', 'IT',                    'operator', 'operator_override', now() - interval '20 hours')
) AS s(ticket_code, department, original_dept, corrected_dept, actor_role, source_type, created_at)
JOIN tickets t ON t.ticket_code = s.ticket_code
LEFT JOIN users u
  ON u.role = s.actor_role::user_role
 AND u.is_active = TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM reroute_reference rr
    WHERE rr.ticket_id = t.id
      AND rr.original_dept IS NOT DISTINCT FROM s.original_dept
      AND rr.corrected_dept = s.corrected_dept
      AND rr.source_type = s.source_type
);

INSERT INTO rescore_reference (
    ticket_id,
    department,
    original_priority,
    corrected_priority,
    actor_role,
    source_type,
    decided_by,
    created_at
)
SELECT
    t.id,
    s.department,
    s.original_priority,
    s.corrected_priority,
    s.actor_role,
    s.source_type,
    u.id,
    s.created_at
FROM (
    VALUES
        ('CX-M52', 'Safety & Security',     'Medium', 'High',     'manager',  'approval_rescoring',  now() - interval '4 days'),
        ('CX-4780', 'IT',                   'High',   'Critical', 'manager',  'approval_rescoring',  now() - interval '2 days'),
        ('CX-A009', 'Legal & Compliance',   'Low',    'Medium',   'operator', 'operator_correction', now() - interval '30 hours'),
        ('CX-H015', 'Facilities Management','Medium', 'High',     'operator', 'operator_correction', now() - interval '16 hours')
) AS s(ticket_code, department, original_priority, corrected_priority, actor_role, source_type, created_at)
JOIN tickets t ON t.ticket_code = s.ticket_code
LEFT JOIN users u
  ON u.role = s.actor_role::user_role
 AND u.is_active = TRUE
WHERE NOT EXISTS (
    SELECT 1
    FROM rescore_reference rs
    WHERE rs.ticket_id = t.id
      AND rs.original_priority IS NOT DISTINCT FROM s.original_priority
      AND rs.corrected_priority = s.corrected_priority
      AND rs.source_type = s.source_type
);
