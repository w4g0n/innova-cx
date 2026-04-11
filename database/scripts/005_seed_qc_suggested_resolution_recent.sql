-- Seed recent Suggested Resolution analytics records for the QC tab.
-- Safe to rerun: inserts only when the target ticket_code does not already exist.

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id,
        (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1) AS employee_id
),
seed_rows AS (
    SELECT *
    FROM (
        VALUES
            (
                'CX-QCSR-APR01',
                'Lobby light circuit tripping repeatedly',
                'The main lobby light circuit trips every evening after 8 PM and leaves the entrance dim.',
                'Complaint',
                'Medium',
                'Facilities Management',
                '2026-04-08 09:15:00+00'::timestamptz,
                'Inspect the lobby lighting circuit, isolate the faulty fixture or breaker, then restore the circuit and confirm stable operation during evening load.',
                'Inspect the lobby lighting circuit, isolate the faulty fixture or breaker, then restore the circuit and confirm stable operation during evening load.',
                'accepted',
                TRUE
            ),
            (
                'CX-QCSR-APR02',
                'Access card reader rejecting valid staff badges',
                'Staff badges are being rejected at the service corridor entrance during shift handover.',
                'Complaint',
                'High',
                'Safety & Security',
                '2026-04-08 13:40:00+00'::timestamptz,
                'Check the card reader logs, resync badge permissions, then test multiple active cards and confirm the entrance unlocks normally.',
                'Check the card reader logs, resync badge permissions, then test multiple active cards and confirm the entrance unlocks normally.',
                'accepted',
                TRUE
            ),
            (
                'CX-QCSR-APR03',
                'Wi-Fi keeps dropping in meeting room 3B',
                'Users lose connection every few minutes during video calls in meeting room 3B.',
                'Complaint',
                'Medium',
                'IT',
                '2026-04-09 07:55:00+00'::timestamptz,
                'Check the meeting room access point, rebalance the channel if congested, then run a live connection test during a video call.',
                'Check the meeting room access point, update the channel plan, then run a live video-call test and confirm the connection remains stable.',
                'declined_custom',
                FALSE
            ),
            (
                'CX-QCSR-APR04',
                'Water leaking under pantry sink',
                'There is a steady leak under the pantry sink and the cabinet floor is already wet.',
                'Complaint',
                'High',
                'Maintenance',
                '2026-04-09 12:20:00+00'::timestamptz,
                'Shut off the pantry sink supply, replace the failed seal or connector, then reopen the line and confirm there is no further leakage.',
                'Shut off the pantry sink supply, replace the failed seal or connector, then reopen the line and confirm there is no further leakage.',
                'accepted',
                TRUE
            ),
            (
                'CX-QCSR-APR05',
                'Lease copy missing signature page',
                'The tenant says the lease copy on file is missing the signed final page.',
                'Inquiry',
                'Low',
                'Legal & Compliance',
                '2026-04-10 10:05:00+00'::timestamptz,
                'Review the lease record, retrieve the signed final page from the archive, then resend the complete signed copy and confirm receipt.',
                'Review the lease archive, retrieve the signed execution set, then resend the complete document and confirm the tenant received every page.',
                'declined_custom',
                FALSE
            ),
            (
                'CX-QCSR-APR06',
                'Visitor parking gate arm not lifting',
                'The visitor parking gate arm stays down even after security approves entry.',
                'Complaint',
                'Medium',
                'Facilities Management',
                '2026-04-11 08:35:00+00'::timestamptz,
                'Check the gate control signal and safety loop, reset the controller if needed, then test approved entry and confirm the arm lifts correctly.',
                'Check the gate control signal and safety loop, reset the controller if needed, then test approved entry and confirm the arm lifts correctly.',
                'accepted',
                TRUE
            )
    ) AS v(
        ticket_code,
        subject,
        details,
        ticket_type,
        priority,
        department_name,
        created_at,
        suggested_resolution,
        final_resolution,
        decision,
        used
    )
)
INSERT INTO tickets (
        ticket_code,
        subject,
        details,
        ticket_type,
        status,
        priority,
        department_id,
        created_by_user_id,
        assigned_to_user_id,
        created_at,
        updated_at,
        assigned_at,
        first_response_at,
        resolved_at,
        ticket_source,
        final_resolution,
        resolved_by_user_id,
        suggested_resolution,
        suggested_resolution_model,
        suggested_resolution_generated_at,
        model_priority
    )
    SELECT
        sr.ticket_code,
        sr.subject,
        sr.details,
        sr.ticket_type::ticket_type,
        'Resolved'::ticket_status,
        sr.priority::ticket_priority,
        d.id,
        a.customer_id,
        a.employee_id,
        sr.created_at,
        sr.created_at + interval '6 hours',
        sr.created_at + interval '20 minutes',
        sr.created_at + interval '35 minutes',
        sr.created_at + interval '4 hours',
        'user',
        sr.final_resolution,
        a.employee_id,
        sr.suggested_resolution,
        'seed-qc',
        sr.created_at + interval '10 minutes',
        sr.priority::ticket_priority
FROM seed_rows sr
CROSS JOIN actors a
JOIN departments d ON d.name = sr.department_name
WHERE NOT EXISTS (
    SELECT 1
    FROM tickets t
    WHERE t.ticket_code = sr.ticket_code
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1) AS employee_id
),
seed_rows AS (
    SELECT *
    FROM (
        VALUES
            (
                'CX-QCSR-APR01',
                'Facilities Management',
                'Inspect the lobby lighting circuit, isolate the faulty fixture or breaker, then restore the circuit and confirm stable operation during evening load.',
                'Inspect the lobby lighting circuit, isolate the faulty fixture or breaker, then restore the circuit and confirm stable operation during evening load.',
                'accepted',
                TRUE,
                '2026-04-08 13:15:00+00'::timestamptz
            ),
            (
                'CX-QCSR-APR02',
                'Safety & Security',
                'Check the card reader logs, resync badge permissions, then test multiple active cards and confirm the entrance unlocks normally.',
                'Check the card reader logs, resync badge permissions, then test multiple active cards and confirm the entrance unlocks normally.',
                'accepted',
                TRUE,
                '2026-04-08 17:40:00+00'::timestamptz
            ),
            (
                'CX-QCSR-APR03',
                'IT',
                'Check the meeting room access point, rebalance the channel if congested, then run a live connection test during a video call.',
                'Check the meeting room access point, update the channel plan, then run a live video-call test and confirm the connection remains stable.',
                'declined_custom',
                FALSE,
                '2026-04-09 11:55:00+00'::timestamptz
            ),
            (
                'CX-QCSR-APR04',
                'Maintenance',
                'Shut off the pantry sink supply, replace the failed seal or connector, then reopen the line and confirm there is no further leakage.',
                'Shut off the pantry sink supply, replace the failed seal or connector, then reopen the line and confirm there is no further leakage.',
                'accepted',
                TRUE,
                '2026-04-09 16:20:00+00'::timestamptz
            ),
            (
                'CX-QCSR-APR05',
                'Legal & Compliance',
                'Review the lease record, retrieve the signed final page from the archive, then resend the complete signed copy and confirm receipt.',
                'Review the lease archive, retrieve the signed execution set, then resend the complete document and confirm the tenant received every page.',
                'declined_custom',
                FALSE,
                '2026-04-10 14:05:00+00'::timestamptz
            ),
            (
                'CX-QCSR-APR06',
                'Facilities Management',
                'Check the gate control signal and safety loop, reset the controller if needed, then test approved entry and confirm the arm lifts correctly.',
                'Check the gate control signal and safety loop, reset the controller if needed, then test approved entry and confirm the arm lifts correctly.',
                'accepted',
                TRUE,
                '2026-04-11 12:35:00+00'::timestamptz
            )
    ) AS v(
        ticket_code,
        department_name,
        suggested_resolution,
        final_resolution,
        decision,
        used,
        usage_created_at
    )
)
INSERT INTO suggested_resolution_usage (
    ticket_id,
    employee_user_id,
    decision,
    actor_role,
    department,
    suggested_text,
    final_text,
    used,
    created_at
)
SELECT
    t.id,
    a.employee_id,
    sr.decision,
    'employee',
    sr.department_name,
    sr.suggested_resolution,
    sr.final_resolution,
    sr.used,
    sr.usage_created_at
FROM seed_rows sr
CROSS JOIN actors a
JOIN tickets t ON t.ticket_code = sr.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM suggested_resolution_usage sru
    WHERE sru.ticket_id = t.id
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id,
        (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1) AS employee_id
),
generated_resolution_tickets AS (
    SELECT
        format('CX-QCSR-BULK%02s', gs)::text AS ticket_code,
        CASE gs % 6
            WHEN 0 THEN 'Maintenance follow-up for repeated plumbing complaint'
            WHEN 1 THEN 'Facilities request about access and entry issue'
            WHEN 2 THEN 'IT support request for unstable connection'
            WHEN 3 THEN 'Lease and documentation clarification request'
            WHEN 4 THEN 'Security concern requiring review'
            ELSE 'Operations complaint requiring guided resolution'
        END AS subject,
        CASE gs % 6
            WHEN 0 THEN format('Resident reported recurring plumbing issue number %s and requested a follow-up resolution.', gs)
            WHEN 1 THEN format('Customer raised an access issue affecting entry flow in case %s.', gs)
            WHEN 2 THEN format('Customer described connectivity problems affecting daily work in case %s.', gs)
            WHEN 3 THEN format('Customer needs help with lease-related documentation for case %s.', gs)
            WHEN 4 THEN format('Customer reported a security-related concern that needs confirmation for case %s.', gs)
            ELSE format('Customer needs operational guidance and a suggested next step for case %s.', gs)
        END AS details,
        CASE WHEN gs % 5 = 0 THEN 'Inquiry' ELSE 'Complaint' END AS ticket_type,
        CASE
            WHEN gs % 6 = 0 THEN 'Facilities Management'
            WHEN gs % 6 = 1 THEN 'Maintenance'
            WHEN gs % 6 = 2 THEN 'IT'
            WHEN gs % 6 = 3 THEN 'Legal & Compliance'
            WHEN gs % 6 = 4 THEN 'Safety & Security'
            ELSE 'Facilities Management'
        END AS department_name,
        CASE
            WHEN gs % 5 = 0 THEN 'Low'
            WHEN gs % 5 IN (1, 2) THEN 'Medium'
            ELSE 'High'
        END AS priority,
        ('2026-04-01 09:00:00+00'::timestamptz + ((gs - 1) * interval '6 hours')) AS created_at,
        CASE gs % 6
            WHEN 0 THEN 'Inspect the reported plumbing issue, confirm the failed component, carry out the repair, and verify that the area is dry and stable.'
            WHEN 1 THEN 'Review the access control path, confirm the blockage or control error, restore normal entry behavior, and verify successful access.'
            WHEN 2 THEN 'Check the affected network point, validate connectivity under load, apply the needed fix, and confirm the connection remains stable.'
            WHEN 3 THEN 'Review the documentation set, retrieve the missing record, provide the corrected copy, and confirm the customer received it.'
            WHEN 4 THEN 'Review the reported safety condition, validate the risk, take the required corrective action, and confirm the area is safe.'
            ELSE 'Review the operational complaint, apply the recommended service action, and confirm the issue is fully resolved for the customer.'
        END AS suggested_resolution,
        CASE
            WHEN gs % 4 = 0 THEN
                CASE gs % 6
                    WHEN 0 THEN 'Maintenance team inspected the plumbing issue, replaced the worn fitting, and confirmed there was no further leak.'
                    WHEN 1 THEN 'Facilities team restored access control behavior and confirmed normal entry after testing.'
                    WHEN 2 THEN 'IT adjusted the affected network configuration and confirmed the connection remained stable during testing.'
                    WHEN 3 THEN 'Legal team retrieved the missing record and sent the corrected document set to the customer.'
                    WHEN 4 THEN 'Security team reviewed the issue, removed the risk, and confirmed the area was safe to use.'
                    ELSE 'Operations team completed the follow-up steps and confirmed the complaint was resolved.'
                END
            ELSE
                CASE gs % 6
                    WHEN 0 THEN 'Inspect the reported plumbing issue, confirm the failed component, carry out the repair, and verify that the area is dry and stable.'
                    WHEN 1 THEN 'Review the access control path, confirm the blockage or control error, restore normal entry behavior, and verify successful access.'
                    WHEN 2 THEN 'Check the affected network point, validate connectivity under load, apply the needed fix, and confirm the connection remains stable.'
                    WHEN 3 THEN 'Review the documentation set, retrieve the missing record, provide the corrected copy, and confirm the customer received it.'
                    WHEN 4 THEN 'Review the reported safety condition, validate the risk, take the required corrective action, and confirm the area is safe.'
                    ELSE 'Review the operational complaint, apply the recommended service action, and confirm the issue is fully resolved for the customer.'
                END
        END AS final_resolution,
        CASE WHEN gs % 4 = 0 THEN 'declined_custom' ELSE 'accepted' END AS decision,
        CASE WHEN gs % 4 = 0 THEN FALSE ELSE TRUE END AS used
    FROM generate_series(1, 38) AS gs
)
INSERT INTO tickets (
    ticket_code,
    subject,
    details,
    ticket_type,
    status,
    priority,
    department_id,
    created_by_user_id,
    assigned_to_user_id,
    created_at,
    updated_at,
    assigned_at,
    first_response_at,
    resolved_at,
    ticket_source,
    final_resolution,
    resolved_by_user_id,
    suggested_resolution,
    suggested_resolution_model,
    suggested_resolution_generated_at,
    model_priority
)
SELECT
    grt.ticket_code,
    grt.subject,
    grt.details,
    grt.ticket_type::ticket_type,
    'Resolved'::ticket_status,
    grt.priority::ticket_priority,
    d.id,
    a.customer_id,
    a.employee_id,
    grt.created_at,
    grt.created_at + interval '5 hours',
    grt.created_at + interval '18 minutes',
    grt.created_at + interval '28 minutes',
    grt.created_at + interval '3 hours',
    'user',
    grt.final_resolution,
    a.employee_id,
    grt.suggested_resolution,
    'seed-qc-bulk',
    grt.created_at + interval '9 minutes',
    grt.priority::ticket_priority
FROM generated_resolution_tickets grt
CROSS JOIN actors a
JOIN departments d ON d.name = grt.department_name
WHERE NOT EXISTS (
    SELECT 1
    FROM tickets t
    WHERE t.ticket_code = grt.ticket_code
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1) AS employee_id
),
generated_resolution_tickets AS (
    SELECT
        format('CX-QCSR-BULK%02s', gs)::text AS ticket_code,
        CASE
            WHEN gs % 6 = 0 THEN 'Facilities Management'
            WHEN gs % 6 = 1 THEN 'Maintenance'
            WHEN gs % 6 = 2 THEN 'IT'
            WHEN gs % 6 = 3 THEN 'Legal & Compliance'
            WHEN gs % 6 = 4 THEN 'Safety & Security'
            ELSE 'Facilities Management'
        END AS department_name,
        CASE gs % 6
            WHEN 0 THEN 'Inspect the reported plumbing issue, confirm the failed component, carry out the repair, and verify that the area is dry and stable.'
            WHEN 1 THEN 'Review the access control path, confirm the blockage or control error, restore normal entry behavior, and verify successful access.'
            WHEN 2 THEN 'Check the affected network point, validate connectivity under load, apply the needed fix, and confirm the connection remains stable.'
            WHEN 3 THEN 'Review the documentation set, retrieve the missing record, provide the corrected copy, and confirm the customer received it.'
            WHEN 4 THEN 'Review the reported safety condition, validate the risk, take the required corrective action, and confirm the area is safe.'
            ELSE 'Review the operational complaint, apply the recommended service action, and confirm the issue is fully resolved for the customer.'
        END AS suggested_resolution,
        CASE
            WHEN gs % 4 = 0 THEN
                CASE gs % 6
                    WHEN 0 THEN 'Maintenance team inspected the plumbing issue, replaced the worn fitting, and confirmed there was no further leak.'
                    WHEN 1 THEN 'Facilities team restored access control behavior and confirmed normal entry after testing.'
                    WHEN 2 THEN 'IT adjusted the affected network configuration and confirmed the connection remained stable during testing.'
                    WHEN 3 THEN 'Legal team retrieved the missing record and sent the corrected document set to the customer.'
                    WHEN 4 THEN 'Security team reviewed the issue, removed the risk, and confirmed the area was safe to use.'
                    ELSE 'Operations team completed the follow-up steps and confirmed the complaint was resolved.'
                END
            ELSE
                CASE gs % 6
                    WHEN 0 THEN 'Inspect the reported plumbing issue, confirm the failed component, carry out the repair, and verify that the area is dry and stable.'
                    WHEN 1 THEN 'Review the access control path, confirm the blockage or control error, restore normal entry behavior, and verify successful access.'
                    WHEN 2 THEN 'Check the affected network point, validate connectivity under load, apply the needed fix, and confirm the connection remains stable.'
                    WHEN 3 THEN 'Review the documentation set, retrieve the missing record, provide the corrected copy, and confirm the customer received it.'
                    WHEN 4 THEN 'Review the reported safety condition, validate the risk, take the required corrective action, and confirm the area is safe.'
                    ELSE 'Review the operational complaint, apply the recommended service action, and confirm the issue is fully resolved for the customer.'
                END
        END AS final_resolution,
        CASE WHEN gs % 4 = 0 THEN 'declined_custom' ELSE 'accepted' END AS decision,
        CASE WHEN gs % 4 = 0 THEN FALSE ELSE TRUE END AS used,
        ('2026-04-01 12:00:00+00'::timestamptz + ((gs - 1) * interval '6 hours')) AS usage_created_at
    FROM generate_series(1, 38) AS gs
)
INSERT INTO suggested_resolution_usage (
    ticket_id,
    employee_user_id,
    decision,
    actor_role,
    department,
    suggested_text,
    final_text,
    used,
    created_at
)
SELECT
    t.id,
    a.employee_id,
    grt.decision,
    'employee',
    grt.department_name,
    grt.suggested_resolution,
    grt.final_resolution,
    grt.used,
    grt.usage_created_at
FROM generated_resolution_tickets grt
CROSS JOIN actors a
JOIN tickets t ON t.ticket_code = grt.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM suggested_resolution_usage sru
    WHERE sru.ticket_id = t.id
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1) AS employee_id,
        (SELECT id FROM users WHERE email = 'hamad@innovacx.net' LIMIT 1)  AS manager_id
),
seed_rows AS (
    SELECT *
    FROM (
        VALUES
            (
                'REQ-QCRR-APR01',
                'CX-QCSR-APR01',
                'Dept: Facilities Management',
                'Dept: Maintenance',
                'Lobby electrical issue needs direct maintenance handling.',
                'Approved',
                0.8120::numeric(5,4),
                'routing-qwen',
                '2026-04-08 10:10:00+00'::timestamptz,
                '2026-04-08 10:40:00+00'::timestamptz
            ),
            (
                'REQ-QCRR-APR02',
                'CX-QCSR-APR03',
                'Dept: IT',
                'Dept: Facilities Management',
                'Signal issue may be caused by meeting-room power interference, needs facilities check first.',
                'Rejected',
                0.6640::numeric(5,4),
                'routing-qwen',
                '2026-04-09 08:20:00+00'::timestamptz,
                '2026-04-09 09:00:00+00'::timestamptz
            ),
            (
                'REQ-QCRR-APR03',
                'CX-QCSR-APR05',
                'Dept: Legal & Compliance',
                'Dept: HR',
                'Tenant document request should stay with legal for records validation.',
                'Rejected',
                0.5930::numeric(5,4),
                'routing-qwen',
                '2026-04-10 10:40:00+00'::timestamptz,
                '2026-04-10 11:05:00+00'::timestamptz
            ),
            (
                'REQ-QCRR-APR04',
                'CX-QCSR-APR06',
                'Dept: Facilities Management',
                'Dept: Safety & Security',
                'Security approval workflow is part of visitor gate access handling.',
                'Approved',
                0.7780::numeric(5,4),
                'routing-qwen',
                '2026-04-11 09:10:00+00'::timestamptz,
                '2026-04-11 09:35:00+00'::timestamptz
            )
    ) AS v(
        request_code,
        ticket_code,
        current_value,
        requested_value,
        request_reason,
        status,
        model_confidence,
        model_name,
        submitted_at,
        decided_at
    )
)
INSERT INTO approval_requests (
    request_code,
    ticket_id,
    request_type,
    current_value,
    requested_value,
    request_reason,
    submitted_by_user_id,
    source,
    requested_to_user_id,
    model_name,
    model_confidence,
    submitted_at,
    status,
    decided_by_user_id,
    decided_at,
    decision_notes
)
SELECT
    sr.request_code,
    t.id,
    'Rerouting'::approval_request_type,
    sr.current_value,
    sr.requested_value,
    sr.request_reason,
    a.employee_id,
    'employee',
    a.manager_id,
    sr.model_name,
    sr.model_confidence,
    sr.submitted_at,
    sr.status::approval_status,
    a.manager_id,
    sr.decided_at,
    CASE
        WHEN sr.status = 'Approved' THEN 'Manager approved rerouting request for QC analytics seed.'
        ELSE 'Manager rejected rerouting request for QC analytics seed.'
    END
FROM seed_rows sr
CROSS JOIN actors a
JOIN tickets t ON t.ticket_code = sr.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM approval_requests ar
    WHERE ar.request_code = sr.request_code
);

WITH seed_rows AS (
    SELECT *
    FROM (
        VALUES
            ('CX-QCSR-APR01', '2026-04-08 09:18:00+00'::timestamptz, 0.8120::numeric(5,4)),
            ('CX-QCSR-APR02', '2026-04-08 13:45:00+00'::timestamptz, 0.7440::numeric(5,4)),
            ('CX-QCSR-APR03', '2026-04-09 08:00:00+00'::timestamptz, 0.6640::numeric(5,4)),
            ('CX-QCSR-APR04', '2026-04-09 12:28:00+00'::timestamptz, 0.8360::numeric(5,4)),
            ('CX-QCSR-APR05', '2026-04-10 10:12:00+00'::timestamptz, 0.5930::numeric(5,4)),
            ('CX-QCSR-APR06', '2026-04-11 08:42:00+00'::timestamptz, 0.7780::numeric(5,4))
    ) AS v(ticket_code, started_at, confidence_score)
)
INSERT INTO model_execution_log (
    ticket_id,
    agent_name,
    model_version,
    triggered_by,
    started_at,
    completed_at,
    status,
    input_token_count,
    output_token_count,
    inference_time_ms,
    confidence_score,
    error_flag
)
SELECT
    t.id,
    'routing'::agent_name_type,
    'routing-qwen',
    'ingest'::trigger_source,
    sr.started_at,
    sr.started_at + interval '8 seconds',
    'success'::execution_status,
    180,
    32,
    820,
    sr.confidence_score,
    FALSE
FROM seed_rows sr
JOIN tickets t ON t.ticket_code = sr.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM model_execution_log mel
    WHERE mel.ticket_id = t.id
      AND mel.agent_name = 'routing'::agent_name_type
      AND mel.model_version = 'routing-qwen'
      AND mel.started_at = sr.started_at
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id
),
seed_sessions AS (
    SELECT *
    FROM (
        VALUES
            (
                '11111111-1111-4111-8111-111111111111'::uuid,
                '2026-04-08 07:55:00+00'::timestamptz,
                FALSE,
                NULL::timestamptz,
                NULL::text,
                'contained',
                NULL::text
            ),
            (
                '22222222-2222-4222-8222-222222222222'::uuid,
                '2026-04-08 10:05:00+00'::timestamptz,
                TRUE,
                '2026-04-08 10:12:00+00'::timestamptz,
                'CX-QCSR-APR01',
                'escalated',
                'facilities issue'
            ),
            (
                '33333333-3333-4333-8333-333333333333'::uuid,
                '2026-04-09 08:10:00+00'::timestamptz,
                FALSE,
                NULL::timestamptz,
                NULL::text,
                'contained',
                NULL::text
            ),
            (
                '44444444-4444-4444-8444-444444444444'::uuid,
                '2026-04-09 11:20:00+00'::timestamptz,
                TRUE,
                '2026-04-09 11:28:00+00'::timestamptz,
                'CX-QCSR-APR03',
                'escalated',
                'wifi outage'
            ),
            (
                '55555555-5555-4555-8555-555555555555'::uuid,
                '2026-04-10 09:30:00+00'::timestamptz,
                FALSE,
                NULL::timestamptz,
                NULL::text,
                'contained',
                NULL::text
            ),
            (
                '66666666-6666-4666-8666-666666666666'::uuid,
                '2026-04-11 08:42:00+00'::timestamptz,
                TRUE,
                '2026-04-11 08:50:00+00'::timestamptz,
                'CX-QCSR-APR06',
                'escalated',
                'visitor gate issue'
            )
    ) AS v(
        session_id,
        created_at,
        escalated_to_human,
        escalated_at,
        linked_ticket_code,
        current_state,
        category
    )
)
INSERT INTO sessions (
    session_id,
    user_id,
    current_state,
    context,
    history,
    created_at,
    updated_at,
    bot_model_version,
    escalated_to_human,
    escalated_at,
    linked_ticket_id
)
SELECT
    ss.session_id,
    a.customer_id,
    ss.current_state,
    jsonb_build_object('seed', 'chatbot-model-health', 'category', ss.category),
    '[]'::jsonb,
    ss.created_at,
    ss.created_at + interval '12 minutes',
    'chatbot-v2.1',
    ss.escalated_to_human,
    ss.escalated_at,
    t.id
FROM seed_sessions ss
CROSS JOIN actors a
LEFT JOIN tickets t ON t.ticket_code = ss.linked_ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM sessions s
    WHERE s.session_id = ss.session_id
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id
),
generated_chatbot_sessions AS (
    SELECT
        (
            substr(md5('seed-chatbot-session-' || gs::text), 1, 8) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 9, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 13, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 17, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 21, 12)
        )::uuid AS session_id,
        ('2026-04-01 08:00:00+00'::timestamptz + ((gs - 1) * interval '4 hours')) AS created_at,
        (gs % 4 = 0) AS escalated_to_human,
        CASE
            WHEN gs % 4 = 0 THEN ('2026-04-01 08:00:00+00'::timestamptz + ((gs - 1) * interval '4 hours') + interval '9 minutes')
            ELSE NULL::timestamptz
        END AS escalated_at,
        CASE WHEN gs % 4 = 0 THEN 'escalated' ELSE 'contained' END AS current_state,
        CASE
            WHEN gs % 3 = 0 THEN 'account_help'
            WHEN gs % 3 = 1 THEN 'booking_help'
            ELSE 'general_support'
        END AS category
    FROM generate_series(1, 49) AS gs
)
INSERT INTO sessions (
    session_id,
    user_id,
    current_state,
    context,
    history,
    created_at,
    updated_at,
    bot_model_version,
    escalated_to_human,
    escalated_at,
    linked_ticket_id
)
SELECT
    gcs.session_id,
    a.customer_id,
    gcs.current_state,
    jsonb_build_object('seed', 'chatbot-model-health-bulk', 'category', gcs.category),
    '[]'::jsonb,
    gcs.created_at,
    gcs.created_at + interval '14 minutes',
    'chatbot-v2.1',
    gcs.escalated_to_human,
    gcs.escalated_at,
    NULL::uuid
FROM generated_chatbot_sessions gcs
CROSS JOIN actors a
WHERE NOT EXISTS (
    SELECT 1
    FROM sessions s
    WHERE s.session_id = gcs.session_id
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id
),
seed_messages AS (
    SELECT *
    FROM (
        VALUES
            ('aaaaaaa1-0000-4000-8000-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'The mobile app answered my parking question.',  'faq', FALSE,  0.120::numeric(4,3), 'general',       '2026-04-08 07:56:00+00'::timestamptz, 1400),
            ('aaaaaaa2-0000-4000-8000-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'I found the answer and do not need a ticket.', 'faq', FALSE,  0.180::numeric(4,3), 'general',       '2026-04-08 07:58:00+00'::timestamptz, 1200),
            ('aaaaaaa3-0000-4000-8000-000000000016'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'I also checked the visitor parking rules.', 'faq', FALSE, 0.110::numeric(4,3), 'general', '2026-04-08 07:59:00+00'::timestamptz, 1150),
            ('aaaaaaa4-0000-4000-8000-000000000017'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'The chatbot showed me where overnight parking is allowed.', 'faq', FALSE, 0.160::numeric(4,3), 'general', '2026-04-08 08:00:00+00'::timestamptz, 1180),
            ('aaaaaaa5-0000-4000-8000-000000000018'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'It clarified the timing for guest parking too.', 'faq', FALSE, 0.170::numeric(4,3), 'general', '2026-04-08 08:01:00+00'::timestamptz, 1100),
            ('aaaaaaa6-0000-4000-8000-000000000019'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'I asked whether I needed a permit.', 'faq', FALSE, 0.090::numeric(4,3), 'general', '2026-04-08 08:02:00+00'::timestamptz, 1175),
            ('aaaaaaa7-0000-4000-8000-000000000020'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'It said visitors can register at the kiosk.', 'faq', FALSE, 0.150::numeric(4,3), 'general', '2026-04-08 08:03:00+00'::timestamptz, 1090),
            ('aaaaaaa8-0000-4000-8000-000000000021'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'Everything is clear now, thanks for the help.', 'gratitude', FALSE, 0.240::numeric(4,3), 'general', '2026-04-08 08:04:00+00'::timestamptz, 980),

            ('bbbbbbb1-0000-4000-8000-000000000003'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'The lobby electrical issue keeps happening tonight.', 'report_issue', FALSE, -0.420::numeric(4,3), 'electrical', '2026-04-08 10:05:30+00'::timestamptz, 1800),
            ('bbbbbbb2-0000-4000-8000-000000000004'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'It is affecting visitors and I need someone now.',      'report_issue', TRUE,  -0.640::numeric(4,3), 'electrical', '2026-04-08 10:08:00+00'::timestamptz, 2100),
            ('bbbbbbb3-0000-4000-8000-000000000005'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Please create a ticket for maintenance.',              'escalate',     FALSE, -0.520::numeric(4,3), 'electrical', '2026-04-08 10:11:00+00'::timestamptz, 1600),
            ('bbbbbbb4-0000-4000-8000-000000000022'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'The breaker has tripped twice this week already.', 'report_issue', FALSE, -0.410::numeric(4,3), 'electrical', '2026-04-08 10:06:30+00'::timestamptz, 1850),
            ('bbbbbbb5-0000-4000-8000-000000000023'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Guests are walking through a dim entrance corridor.', 'report_issue', FALSE, -0.470::numeric(4,3), 'electrical', '2026-04-08 10:07:15+00'::timestamptz, 1900),
            ('bbbbbbb6-0000-4000-8000-000000000024'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'This could become a safety problem if it stays dark.', 'report_issue', TRUE, -0.590::numeric(4,3), 'electrical', '2026-04-08 10:08:40+00'::timestamptz, 2050),
            ('bbbbbbb7-0000-4000-8000-000000000025'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'I need confirmation that an engineer is coming tonight.', 'escalate', FALSE, -0.540::numeric(4,3), 'electrical', '2026-04-08 10:09:20+00'::timestamptz, 1750),
            ('bbbbbbb8-0000-4000-8000-000000000026'::uuid, '22222222-2222-4222-8222-222222222222'::uuid, 'Please attach all of this to the maintenance ticket.', 'escalate', FALSE, -0.360::numeric(4,3), 'electrical', '2026-04-08 10:10:10+00'::timestamptz, 1625),

            ('ccccccc1-0000-4000-8000-000000000006'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'How do I reset my visitor wifi voucher?',              'how_to',        FALSE,  0.050::numeric(4,3), 'wifi',       '2026-04-09 08:11:00+00'::timestamptz, 1000),
            ('ccccccc2-0000-4000-8000-000000000007'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'That solved it, thanks.',                               'gratitude',     FALSE,  0.220::numeric(4,3), 'wifi',       '2026-04-09 08:13:00+00'::timestamptz, 900),
            ('ccccccc3-0000-4000-8000-000000000027'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'I also needed to know how long the voucher lasts.', 'how_to', FALSE, 0.060::numeric(4,3), 'wifi', '2026-04-09 08:11:30+00'::timestamptz, 980),
            ('ccccccc4-0000-4000-8000-000000000028'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'The instructions for reconnecting after timeout were helpful.', 'how_to', FALSE, 0.120::numeric(4,3), 'wifi', '2026-04-09 08:12:00+00'::timestamptz, 920),
            ('ccccccc5-0000-4000-8000-000000000029'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'I checked the guest portal and it matched your answer.', 'faq', FALSE, 0.150::numeric(4,3), 'wifi', '2026-04-09 08:12:20+00'::timestamptz, 910),
            ('ccccccc6-0000-4000-8000-000000000030'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'I did not need a human after that.', 'gratitude', FALSE, 0.230::numeric(4,3), 'wifi', '2026-04-09 08:12:40+00'::timestamptz, 880),
            ('ccccccc7-0000-4000-8000-000000000031'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'The steps were easy to follow on mobile too.', 'gratitude', FALSE, 0.210::numeric(4,3), 'wifi', '2026-04-09 08:13:20+00'::timestamptz, 860),
            ('ccccccc8-0000-4000-8000-000000000032'::uuid, '33333333-3333-4333-8333-333333333333'::uuid, 'I am all set now.', 'gratitude', FALSE, 0.260::numeric(4,3), 'wifi', '2026-04-09 08:13:40+00'::timestamptz, 840),

            ('ddddddd1-0000-4000-8000-000000000008'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'Meeting room wifi keeps dropping during client calls.', 'report_issue',  FALSE, -0.350::numeric(4,3), 'wifi',       '2026-04-09 11:20:30+00'::timestamptz, 1700),
            ('ddddddd2-0000-4000-8000-000000000009'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'We already rebooted everything and it is still bad.',    'report_issue',  FALSE, -0.480::numeric(4,3), 'wifi',       '2026-04-09 11:23:00+00'::timestamptz, 2000),
            ('ddddddd3-0000-4000-8000-000000000010'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'Please escalate this to IT support now.',              'escalate',      TRUE,  -0.610::numeric(4,3), 'wifi',       '2026-04-09 11:27:30+00'::timestamptz, 1900),
            ('ddddddd4-0000-4000-8000-000000000033'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'The issue starts as soon as more than five people join.', 'report_issue', FALSE, -0.320::numeric(4,3), 'wifi', '2026-04-09 11:21:15+00'::timestamptz, 1760),
            ('ddddddd5-0000-4000-8000-000000000034'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'It disrupted two calls with clients this morning.', 'report_issue', FALSE, -0.430::numeric(4,3), 'wifi', '2026-04-09 11:22:10+00'::timestamptz, 1880),
            ('ddddddd6-0000-4000-8000-000000000035'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'No one can hold a stable video meeting in that room.', 'report_issue', FALSE, -0.500::numeric(4,3), 'wifi', '2026-04-09 11:24:10+00'::timestamptz, 1930),
            ('ddddddd7-0000-4000-8000-000000000036'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'I already tried forgetting and rejoining the network.', 'report_issue', FALSE, -0.290::numeric(4,3), 'wifi', '2026-04-09 11:25:20+00'::timestamptz, 1810),
            ('ddddddd8-0000-4000-8000-000000000037'::uuid, '44444444-4444-4444-8444-444444444444'::uuid, 'Please send this to the IT team with urgency.', 'escalate', TRUE, -0.580::numeric(4,3), 'wifi', '2026-04-09 11:26:30+00'::timestamptz, 1875),

            ('eeeeeee1-0000-4000-8000-000000000011'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'What documents are needed for a lease copy request?',    'faq',           FALSE,  0.040::numeric(4,3), 'leasing',    '2026-04-10 09:31:00+00'::timestamptz, 1100),
            ('eeeeeee2-0000-4000-8000-000000000012'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'Understood, I can send that today.',                   'acknowledge',   FALSE,  0.140::numeric(4,3), 'leasing',    '2026-04-10 09:33:00+00'::timestamptz, 950),
            ('eeeeeee3-0000-4000-8000-000000000038'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'I also wanted to confirm whether ID is required.', 'faq', FALSE, 0.030::numeric(4,3), 'leasing', '2026-04-10 09:31:30+00'::timestamptz, 1020),
            ('eeeeeee4-0000-4000-8000-000000000039'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'The checklist for lease copies was useful.', 'faq', FALSE, 0.100::numeric(4,3), 'leasing', '2026-04-10 09:32:00+00'::timestamptz, 980),
            ('eeeeeee5-0000-4000-8000-000000000040'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'I will send the tenant reference and email now.', 'acknowledge', FALSE, 0.130::numeric(4,3), 'leasing', '2026-04-10 09:32:20+00'::timestamptz, 920),
            ('eeeeeee6-0000-4000-8000-000000000041'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'It also answered how long retrieval normally takes.', 'faq', FALSE, 0.090::numeric(4,3), 'leasing', '2026-04-10 09:32:40+00'::timestamptz, 910),
            ('eeeeeee7-0000-4000-8000-000000000042'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'Thanks, I do not need to escalate this.', 'gratitude', FALSE, 0.210::numeric(4,3), 'leasing', '2026-04-10 09:33:20+00'::timestamptz, 870),
            ('eeeeeee8-0000-4000-8000-000000000043'::uuid, '55555555-5555-4555-8555-555555555555'::uuid, 'This saved me a call to the office.', 'gratitude', FALSE, 0.240::numeric(4,3), 'leasing', '2026-04-10 09:33:40+00'::timestamptz, 860),

            ('fffffff1-0000-4000-8000-000000000013'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'The visitor gate is not opening and cars are backed up.', 'report_issue', FALSE, -0.410::numeric(4,3), 'access',     '2026-04-11 08:42:30+00'::timestamptz, 1800),
            ('fffffff2-0000-4000-8000-000000000014'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'Security approved entry but the arm stays down.',         'report_issue', FALSE, -0.550::numeric(4,3), 'access',     '2026-04-11 08:45:00+00'::timestamptz, 2100),
            ('fffffff3-0000-4000-8000-000000000015'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'Please connect me to a human because this is urgent.',    'escalate',     TRUE,  -0.700::numeric(4,3), 'access',     '2026-04-11 08:49:00+00'::timestamptz, 2200),
            ('fffffff4-0000-4000-8000-000000000044'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'There are several cars waiting at the entrance now.', 'report_issue', FALSE, -0.460::numeric(4,3), 'access', '2026-04-11 08:43:15+00'::timestamptz, 1860),
            ('fffffff5-0000-4000-8000-000000000045'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'The queue is reaching the street outside the gate.', 'report_issue', TRUE, -0.620::numeric(4,3), 'access', '2026-04-11 08:44:20+00'::timestamptz, 2080),
            ('fffffff6-0000-4000-8000-000000000046'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'Security says the approval signal is being sent correctly.', 'report_issue', FALSE, -0.350::numeric(4,3), 'access', '2026-04-11 08:46:10+00'::timestamptz, 1940),
            ('fffffff7-0000-4000-8000-000000000047'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'We need facilities to check the gate controller immediately.', 'escalate', FALSE, -0.580::numeric(4,3), 'access', '2026-04-11 08:47:00+00'::timestamptz, 2010),
            ('fffffff8-0000-4000-8000-000000000048'::uuid, '66666666-6666-4666-8666-666666666666'::uuid, 'Please include that visitors cannot enter the parking area.', 'escalate', FALSE, -0.520::numeric(4,3), 'access', '2026-04-11 08:48:00+00'::timestamptz, 1980)
    ) AS v(
        id,
        session_id,
        message,
        intent_detected,
        aggression_flag,
        sentiment_score,
        category,
        created_at,
        response_time_ms
    )
)
INSERT INTO user_chat_logs (
    id,
    session_id,
    user_id,
    message,
    intent_detected,
    aggression_flag,
    created_at,
    sentiment_score,
    category,
    response_time_ms
)
SELECT
    sm.id,
    sm.session_id,
    a.customer_id,
    sm.message,
    sm.intent_detected,
    sm.aggression_flag,
    sm.created_at,
    sm.sentiment_score,
    sm.category,
    sm.response_time_ms
FROM seed_messages sm
CROSS JOIN actors a
WHERE NOT EXISTS (
    SELECT 1
    FROM user_chat_logs ucl
    WHERE ucl.id = sm.id
);

WITH actors AS (
    SELECT
        (SELECT id FROM users WHERE email = 'customer1@innovacx.net' LIMIT 1) AS customer_id
),
generated_chatbot_sessions AS (
    SELECT
        gs,
        (
            substr(md5('seed-chatbot-session-' || gs::text), 1, 8) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 9, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 13, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 17, 4) || '-' ||
            substr(md5('seed-chatbot-session-' || gs::text), 21, 12)
        )::uuid AS session_id,
        ('2026-04-01 08:00:00+00'::timestamptz + ((gs - 1) * interval '4 hours')) AS created_at,
        (gs % 4 = 0) AS escalated_to_human,
        CASE
            WHEN gs % 3 = 0 THEN 'account_help'
            WHEN gs % 3 = 1 THEN 'booking_help'
            ELSE 'general_support'
        END AS category
    FROM generate_series(1, 49) AS gs
),
generated_chatbot_messages AS (
    SELECT
        (
            substr(md5(format('seed-chatbot-message-%s-%s', gcs.gs, msg_no)), 1, 8) || '-' ||
            substr(md5(format('seed-chatbot-message-%s-%s', gcs.gs, msg_no)), 9, 4) || '-' ||
            substr(md5(format('seed-chatbot-message-%s-%s', gcs.gs, msg_no)), 13, 4) || '-' ||
            substr(md5(format('seed-chatbot-message-%s-%s', gcs.gs, msg_no)), 17, 4) || '-' ||
            substr(md5(format('seed-chatbot-message-%s-%s', gcs.gs, msg_no)), 21, 12)
        )::uuid AS id,
        gcs.session_id,
        CASE
            WHEN gcs.escalated_to_human AND msg_no = 8 THEN format('Please escalate session %s to a human agent now.', gcs.gs)
            WHEN gcs.escalated_to_human AND msg_no >= 5 THEN format('Session %s is still unresolved and affecting my work.', gcs.gs)
            WHEN msg_no = 1 THEN format('I need help with issue %s in the customer portal.', gcs.gs)
            WHEN msg_no = 2 THEN 'I checked the self-service steps already.'
            WHEN msg_no = 3 THEN 'The instructions were partly helpful but I still have questions.'
            WHEN msg_no = 4 THEN 'Can you walk me through the next step?'
            WHEN msg_no = 5 THEN 'I tried that and got a different result.'
            WHEN msg_no = 6 THEN 'Here is some more detail so the issue can be understood clearly.'
            WHEN msg_no = 7 THEN 'I want to make sure this gets resolved correctly.'
            ELSE 'Thanks, that gives me what I need for now.'
        END AS message,
        CASE
            WHEN gcs.escalated_to_human AND msg_no >= 7 THEN 'escalate'
            WHEN msg_no IN (1, 5, 6) THEN 'report_issue'
            WHEN msg_no IN (2, 3, 4) THEN 'how_to'
            ELSE 'acknowledge'
        END AS intent_detected,
        (gcs.escalated_to_human AND msg_no IN (6, 7, 8)) AS aggression_flag,
        CASE
            WHEN gcs.escalated_to_human AND msg_no >= 6 THEN -0.520::numeric(4,3)
            WHEN gcs.escalated_to_human THEN -0.280::numeric(4,3)
            WHEN msg_no <= 2 THEN 0.020::numeric(4,3)
            WHEN msg_no <= 5 THEN 0.090::numeric(4,3)
            ELSE 0.180::numeric(4,3)
        END AS sentiment_score,
        gcs.category,
        gcs.created_at + ((msg_no - 1) * interval '55 seconds') AS created_at,
        (900 + (msg_no * 70) + ((gcs.gs % 5) * 35))::int AS response_time_ms
    FROM generated_chatbot_sessions gcs
    CROSS JOIN generate_series(1, 8) AS msg_no
)
INSERT INTO user_chat_logs (
    id,
    session_id,
    user_id,
    message,
    intent_detected,
    aggression_flag,
    created_at,
    sentiment_score,
    category,
    response_time_ms
)
SELECT
    gcm.id,
    gcm.session_id,
    a.customer_id,
    gcm.message,
    gcm.intent_detected,
    gcm.aggression_flag,
    gcm.created_at,
    gcm.sentiment_score,
    gcm.category,
    gcm.response_time_ms
FROM generated_chatbot_messages gcm
CROSS JOIN actors a
WHERE NOT EXISTS (
    SELECT 1
    FROM user_chat_logs ucl
    WHERE ucl.id = gcm.id
);

WITH feature_exec_seed AS (
    SELECT *
    FROM (
        VALUES
            ('71111111-1111-4111-8111-111111111111'::uuid, 'CX-QCSR-APR01', '2026-04-08 09:17:00+00'::timestamptz, 0.9400::numeric(5,4)),
            ('72222222-2222-4222-8222-222222222222'::uuid, 'CX-QCSR-APR02', '2026-04-08 13:44:00+00'::timestamptz, 0.9100::numeric(5,4)),
            ('73333333-3333-4333-8333-333333333333'::uuid, 'CX-QCSR-APR03', '2026-04-09 07:59:00+00'::timestamptz, 0.5200::numeric(5,4)),
            ('74444444-4444-4444-8444-444444444444'::uuid, 'CX-QCSR-APR04', '2026-04-09 12:26:00+00'::timestamptz, 0.9300::numeric(5,4)),
            ('75555555-5555-4555-8555-555555555555'::uuid, 'CX-QCSR-APR05', '2026-04-10 10:11:00+00'::timestamptz, 0.5700::numeric(5,4)),
            ('76666666-6666-4666-8666-666666666666'::uuid, 'CX-QCSR-APR06', '2026-04-11 08:41:00+00'::timestamptz, 0.9600::numeric(5,4))
    ) AS v(execution_id, ticket_code, started_at, confidence_score)
)
INSERT INTO model_execution_log (
    id,
    execution_id,
    ticket_id,
    agent_name,
    model_version,
    triggered_by,
    started_at,
    completed_at,
    status,
    input_token_count,
    output_token_count,
    infra_metadata,
    inference_time_ms,
    confidence_score,
    error_flag,
    created_at
)
SELECT
    fes.execution_id,
    fes.execution_id,
    t.id,
    'feature'::agent_name_type,
    'feature-qwen',
    'ingest'::trigger_source,
    fes.started_at,
    fes.started_at + interval '9 seconds',
    'success'::execution_status,
    240,
    64,
    '{}'::jsonb,
    910,
    fes.confidence_score,
    FALSE,
    fes.started_at
FROM feature_exec_seed fes
JOIN tickets t ON t.ticket_code = fes.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM model_execution_log mel
    WHERE mel.id = fes.execution_id
);

WITH feature_seed AS (
    SELECT *
    FROM (
        VALUES
            (
                '81111111-1111-4111-8111-111111111111'::uuid,
                '71111111-1111-4111-8111-111111111111'::uuid,
                'CX-QCSR-APR01',
                'Electrical',
                ARRAY['lighting','breaker']::text[],
                0.9400::numeric(5,4),
                '{"business_impact":"High","issue_severity":"High","issue_urgency":"High","safety_concern":true}'::jsonb,
                '2026-04-08 09:17:10+00'::timestamptz
            ),
            (
                '82222222-2222-4222-8222-222222222222'::uuid,
                '72222222-2222-4222-8222-222222222222'::uuid,
                'CX-QCSR-APR02',
                'Access Control',
                ARRAY['badge','entry']::text[],
                0.9100::numeric(5,4),
                '{"business_impact":"Medium","issue_severity":"Medium","issue_urgency":"High","safety_concern":true}'::jsonb,
                '2026-04-08 13:44:10+00'::timestamptz
            ),
            (
                '83333333-3333-4333-8333-333333333333'::uuid,
                '73333333-3333-4333-8333-333333333333'::uuid,
                'CX-QCSR-APR03',
                'Network',
                ARRAY['wifi','meeting-room']::text[],
                0.5200::numeric(5,4),
                '{"business_impact":"High","issue_severity":"Critical","issue_urgency":"Critical","safety_concern":false}'::jsonb,
                '2026-04-09 07:59:10+00'::timestamptz
            ),
            (
                '84444444-4444-4444-8444-444444444444'::uuid,
                '74444444-4444-4444-8444-444444444444'::uuid,
                'CX-QCSR-APR04',
                'Plumbing',
                ARRAY['leak','sink']::text[],
                0.9300::numeric(5,4),
                '{"business_impact":"High","issue_severity":"High","issue_urgency":"High","safety_concern":true}'::jsonb,
                '2026-04-09 12:26:10+00'::timestamptz
            ),
            (
                '85555555-5555-4555-8555-555555555555'::uuid,
                '75555555-5555-4555-8555-555555555555'::uuid,
                'CX-QCSR-APR05',
                'Document Control',
                ARRAY['lease','signature']::text[],
                0.5700::numeric(5,4),
                '{"business_impact":"Low","issue_severity":"Low","issue_urgency":"Low","safety_concern":false}'::jsonb,
                '2026-04-10 10:11:10+00'::timestamptz
            ),
            (
                '86666666-6666-4666-8666-666666666666'::uuid,
                '76666666-6666-4666-8666-666666666666'::uuid,
                'CX-QCSR-APR06',
                'Gate Systems',
                ARRAY['visitor-gate','access']::text[],
                0.9600::numeric(5,4),
                '{"business_impact":"High","issue_severity":"Medium","issue_urgency":"Critical","safety_concern":true}'::jsonb,
                '2026-04-11 08:41:10+00'::timestamptz
            )
    ) AS v(id, execution_id, ticket_code, asset_category, topic_labels, confidence_score, raw_features, created_at)
)
INSERT INTO feature_outputs (
    id,
    execution_id,
    ticket_id,
    model_version,
    asset_category,
    topic_labels,
    confidence_score,
    raw_features,
    is_current,
    created_at
)
SELECT
    fs.id,
    fs.execution_id,
    t.id,
    'feature-qwen',
    fs.asset_category,
    fs.topic_labels,
    fs.confidence_score,
    fs.raw_features,
    TRUE,
    fs.created_at
FROM feature_seed fs
JOIN tickets t ON t.ticket_code = fs.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM feature_outputs fo
    WHERE fo.id = fs.id
);

WITH sentiment_exec_seed AS (
    SELECT *
    FROM (
        VALUES
            ('91111111-1111-4111-8111-111111111111'::uuid, 'CX-QCSR-APR01', '2026-04-08 09:16:00+00'::timestamptz, 0.9200::numeric(5,4)),
            ('92222222-2222-4222-8222-222222222222'::uuid, 'CX-QCSR-APR02', '2026-04-08 13:43:00+00'::timestamptz, 0.8800::numeric(5,4)),
            ('93333333-3333-4333-8333-333333333333'::uuid, 'CX-QCSR-APR03', '2026-04-09 07:58:00+00'::timestamptz, 0.9100::numeric(5,4)),
            ('94444444-4444-4444-8444-444444444444'::uuid, 'CX-QCSR-APR04', '2026-04-09 12:25:00+00'::timestamptz, 0.9300::numeric(5,4)),
            ('95555555-5555-4555-8555-555555555555'::uuid, 'CX-QCSR-APR05', '2026-04-10 10:10:00+00'::timestamptz, 0.8500::numeric(5,4)),
            ('96666666-6666-4666-8666-666666666666'::uuid, 'CX-QCSR-APR06', '2026-04-11 08:40:00+00'::timestamptz, 0.9400::numeric(5,4))
    ) AS v(execution_id, ticket_code, started_at, confidence_score)
)
INSERT INTO model_execution_log (
    id,
    execution_id,
    ticket_id,
    agent_name,
    model_version,
    triggered_by,
    started_at,
    completed_at,
    status,
    input_token_count,
    output_token_count,
    infra_metadata,
    inference_time_ms,
    confidence_score,
    error_flag,
    created_at
)
SELECT
    ses.execution_id,
    ses.execution_id,
    t.id,
    'sentiment'::agent_name_type,
    'sentiment-qwen',
    'ingest'::trigger_source,
    ses.started_at,
    ses.started_at + interval '6 seconds',
    'success'::execution_status,
    150,
    32,
    '{}'::jsonb,
    640,
    ses.confidence_score,
    FALSE,
    ses.started_at
FROM sentiment_exec_seed ses
JOIN tickets t ON t.ticket_code = ses.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM model_execution_log mel
    WHERE mel.id = ses.execution_id
);

WITH sentiment_seed AS (
    SELECT *
    FROM (
        VALUES
            ('a1111111-1111-4111-8111-111111111111'::uuid, '91111111-1111-4111-8111-111111111111'::uuid, 'CX-QCSR-APR01', 'Negative', -0.4200::numeric(6,4), 0.9200::numeric(5,4), ARRAY['frustration']::text[], '{"negative":0.71,"neutral":0.21,"positive":0.08}'::jsonb, '2026-04-08 09:16:10+00'::timestamptz),
            ('a2222222-2222-4222-8222-222222222222'::uuid, '92222222-2222-4222-8222-222222222222'::uuid, 'CX-QCSR-APR02', 'Negative', -0.3500::numeric(6,4), 0.8800::numeric(5,4), ARRAY['concern']::text[], '{"negative":0.62,"neutral":0.28,"positive":0.10}'::jsonb, '2026-04-08 13:43:10+00'::timestamptz),
            ('a3333333-3333-4333-8333-333333333333'::uuid, '93333333-3333-4333-8333-333333333333'::uuid, 'CX-QCSR-APR03', 'Very Negative', -0.7100::numeric(6,4), 0.9100::numeric(5,4), ARRAY['anger']::text[], '{"negative":0.88,"neutral":0.10,"positive":0.02}'::jsonb, '2026-04-09 07:58:10+00'::timestamptz),
            ('a4444444-4444-4444-8444-444444444444'::uuid, '94444444-4444-4444-8444-444444444444'::uuid, 'CX-QCSR-APR04', 'Negative', -0.4600::numeric(6,4), 0.9300::numeric(5,4), ARRAY['urgency']::text[], '{"negative":0.73,"neutral":0.20,"positive":0.07}'::jsonb, '2026-04-09 12:25:10+00'::timestamptz),
            ('a5555555-5555-4555-8555-555555555555'::uuid, '95555555-5555-4555-8555-555555555555'::uuid, 'CX-QCSR-APR05', 'Neutral', 0.0200::numeric(6,4), 0.8500::numeric(5,4), ARRAY['clarity']::text[], '{"negative":0.18,"neutral":0.68,"positive":0.14}'::jsonb, '2026-04-10 10:10:10+00'::timestamptz),
            ('a6666666-6666-4666-8666-666666666666'::uuid, '96666666-6666-4666-8666-666666666666'::uuid, 'CX-QCSR-APR06', 'Negative', -0.5200::numeric(6,4), 0.9400::numeric(5,4), ARRAY['urgency']::text[], '{"negative":0.77,"neutral":0.17,"positive":0.06}'::jsonb, '2026-04-11 08:40:10+00'::timestamptz)
    ) AS v(id, execution_id, ticket_code, sentiment_label, sentiment_score, confidence_score, emotion_tags, raw_scores, created_at)
)
INSERT INTO sentiment_outputs (
    id,
    execution_id,
    ticket_id,
    model_version,
    sentiment_label,
    sentiment_score,
    confidence_score,
    emotion_tags,
    raw_scores,
    is_current,
    created_at
)
SELECT
    ss.id,
    ss.execution_id,
    t.id,
    'sentiment-qwen',
    ss.sentiment_label,
    ss.sentiment_score,
    ss.confidence_score,
    ss.emotion_tags,
    ss.raw_scores,
    TRUE,
    ss.created_at
FROM sentiment_seed ss
JOIN tickets t ON t.ticket_code = ss.ticket_code
WHERE NOT EXISTS (
    SELECT 1
    FROM sentiment_outputs so
    WHERE so.id = ss.id
);
