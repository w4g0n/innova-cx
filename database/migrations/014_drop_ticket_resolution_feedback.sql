-- Retire legacy ticket_resolution_feedback in favor of suggested_resolution_usage.
-- Backfill any legacy rows first, then remove the obsolete trigger/table.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'ticket_resolution_feedback'
    ) THEN
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
            trf.ticket_id,
            trf.employee_user_id,
            trf.decision,
            'employee',
            COALESCE(d.name, 'Unknown'),
            trf.suggested_resolution,
            trf.final_resolution,
            (trf.decision = 'accepted'),
            trf.created_at
        FROM ticket_resolution_feedback trf
        LEFT JOIN tickets t ON t.id = trf.ticket_id
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM suggested_resolution_usage sru
            WHERE sru.ticket_id IS NOT DISTINCT FROM trf.ticket_id
              AND sru.employee_user_id IS NOT DISTINCT FROM trf.employee_user_id
              AND sru.decision IS NOT DISTINCT FROM trf.decision
              AND sru.suggested_text IS NOT DISTINCT FROM trf.suggested_resolution
              AND sru.final_text IS NOT DISTINCT FROM trf.final_resolution
              AND sru.created_at IS NOT DISTINCT FROM trf.created_at
        );

        DROP TRIGGER IF EXISTS trg_notify_operator_acceptance_rate ON ticket_resolution_feedback;
        DROP TABLE IF EXISTS ticket_resolution_feedback;
    END IF;
END $$;

DROP FUNCTION IF EXISTS notify_operator_acceptance_rate();

COMMIT;
