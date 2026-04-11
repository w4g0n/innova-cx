-- Migration 012: Training Loop
-- Canonical fresh-setup definitions now live in database/scripts/learning.sql.
-- Two separate reference tables for the Review Agent's learning signals.
--
-- reroute_reference  — department routing corrections from manager decisions
--                      and operator pipeline-queue corrections
-- rescore_reference  — priority rescoring corrections from manager approvals
--                      and operator pipeline-queue corrections
--
-- Records older than 3 months are excluded at query time (no hard delete).


-- reroute_reference
-- Populated when:
--   1. A manager manually routes or overrides a routing review
--      (department_routing: routed_by set to 'manager')
--   2. A manager approves a Rerouting approval request
--      (approval_requests: request_type='Rerouting', status → 'Approved')
--   3. An operator manually corrects department via pipeline queue
--      (written directly by backend code in pipeline_queue_api.py)

CREATE TABLE IF NOT EXISTS reroute_reference (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID REFERENCES tickets(id) ON DELETE CASCADE,
    department      TEXT NOT NULL,      -- the department this record is indexed under
    original_dept   TEXT,               -- what the model predicted
    corrected_dept  TEXT NOT NULL,      -- the final department chosen by manager/operator
    actor_role      TEXT NOT NULL CHECK (actor_role IN ('manager', 'operator', 'employee')),
    source_type     TEXT NOT NULL,      -- 'manager_routing_review' | 'approval_rerouting' | 'operator_correction'
    source_id       UUID,               -- department_routing.id, approval_requests.id, or NULL for operator
    decided_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reroute_ref_dept_created
    ON reroute_reference(department, created_at DESC);


-- rescore_reference
-- Populated when:
--   1. A manager approves a Rescoring approval request
--      (approval_requests: request_type='Rescoring', status → 'Approved')
--   2. An operator manually overwrites priority via pipeline queue dashboard
--      (written directly by backend code in pipeline_queue_api.py)

CREATE TABLE IF NOT EXISTS rescore_reference (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID REFERENCES tickets(id) ON DELETE CASCADE,
    department      TEXT NOT NULL,      -- department context for filtering
    original_priority   TEXT,
    corrected_priority  TEXT NOT NULL,
    actor_role      TEXT NOT NULL CHECK (actor_role IN ('manager', 'operator', 'employee')),
    source_type     TEXT NOT NULL,      -- 'approval_rescoring' | 'operator_correction'
    source_id       UUID,               -- approval_requests.id or NULL for operator
    decided_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rescore_ref_dept_created
    ON rescore_reference(department, created_at DESC);


-- suggested_resolution_usage
-- Tracks copy/use of suggested resolutions by employees.
-- Per-department JSON files are rebuilt from this table by retrain_resolution_examples_from_db().

CREATE TABLE IF NOT EXISTS suggested_resolution_usage (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID REFERENCES tickets(id) ON DELETE CASCADE,
    actor_role      TEXT NOT NULL DEFAULT 'employee' CHECK (actor_role IN ('manager', 'operator', 'employee')),
    department      TEXT NOT NULL,
    suggested_text  TEXT,
    final_text      TEXT,
    used            BOOLEAN NOT NULL DEFAULT TRUE,  -- TRUE = copied, FALSE = ignored
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sru_dept_used_created
    ON suggested_resolution_usage(department, used, created_at DESC);


-- Trigger 1: department_routing → reroute_reference
-- Fires when a manager finalises a routing review decision.
-- Captures both Approved (manager confirms suggested dept) and
-- Overridden (manager picks a different dept) — both are learning signals.

CREATE OR REPLACE FUNCTION trg_dept_routing_to_reroute_ref()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    -- Only capture when routed_by transitions to 'manager'
    IF NEW.routed_by = 'manager'
       AND (OLD.routed_by IS DISTINCT FROM 'manager')
       AND NEW.final_department IS NOT NULL
    THEN
        INSERT INTO reroute_reference (
            id, ticket_id, department,
            original_dept, corrected_dept,
            actor_role, source_type, source_id, decided_by
        ) VALUES (
            gen_random_uuid(),
            NEW.ticket_id,
            NEW.final_department,           -- index under the chosen department
            NEW.suggested_department,       -- what the model predicted
            NEW.final_department,           -- what the manager confirmed/chose
            'manager',
            'manager_routing_review',
            NEW.id,
            NEW.manager_id
        );
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_dept_routing_reroute_ref ON department_routing;
CREATE TRIGGER trg_dept_routing_reroute_ref
    AFTER UPDATE OF routed_by ON department_routing
    FOR EACH ROW
    EXECUTE FUNCTION trg_dept_routing_to_reroute_ref();


-- Trigger 2: approval_requests → reroute_reference  (Rerouting type)
-- Fires when a manager approves a Rerouting request submitted by an employee.

CREATE OR REPLACE FUNCTION trg_approval_rerouting_to_reroute_ref()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_original TEXT;
    v_corrected TEXT;
BEGIN
    IF NEW.request_type = 'Rerouting'
       AND NEW.status = 'Approved'
       AND OLD.status IS DISTINCT FROM 'Approved'
    THEN
        v_original  := REPLACE(COALESCE(NEW.current_value, ''), 'Dept:', '');
        v_corrected := REPLACE(COALESCE(NEW.requested_value, ''), 'Dept:', '');
        v_original  := BTRIM(v_original);
        v_corrected := BTRIM(v_corrected);

        IF v_corrected <> '' THEN
            INSERT INTO reroute_reference (
                id, ticket_id, department,
                original_dept, corrected_dept,
                actor_role, source_type, source_id, decided_by
            ) VALUES (
                gen_random_uuid(),
                NEW.ticket_id,
                v_corrected,
                NULLIF(v_original, ''),
                v_corrected,
                'manager',
                'approval_rerouting',
                NEW.id,
                NEW.decided_by_user_id
            );
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_approval_rerouting_ref ON approval_requests;
CREATE TRIGGER trg_approval_rerouting_ref
    AFTER UPDATE OF status ON approval_requests
    FOR EACH ROW
    EXECUTE FUNCTION trg_approval_rerouting_to_reroute_ref();


-- Trigger 3: approval_requests → rescore_reference  (Rescoring type)
-- Fires when a manager approves a Rescoring request submitted by an employee.

CREATE OR REPLACE FUNCTION trg_approval_rescoring_to_rescore_ref()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_original  TEXT;
    v_corrected TEXT;
    v_dept      TEXT;
BEGIN
    IF NEW.request_type = 'Rescoring'
       AND NEW.status = 'Approved'
       AND OLD.status IS DISTINCT FROM 'Approved'
    THEN
        v_original  := REPLACE(COALESCE(NEW.current_value, ''), 'Priority:', '');
        v_corrected := REPLACE(COALESCE(NEW.requested_value, ''), 'Priority:', '');
        v_original  := BTRIM(v_original);
        v_corrected := BTRIM(v_corrected);

        -- Fetch the ticket's current department name for indexing
        SELECT COALESCE(d.name, 'Unknown')
          INTO v_dept
          FROM tickets t
          LEFT JOIN departments d ON d.id = t.department_id
         WHERE t.id = NEW.ticket_id
         LIMIT 1;

        IF v_corrected <> '' THEN
            INSERT INTO rescore_reference (
                id, ticket_id, department,
                original_priority, corrected_priority,
                actor_role, source_type, source_id, decided_by
            ) VALUES (
                gen_random_uuid(),
                NEW.ticket_id,
                COALESCE(v_dept, 'Unknown'),
                NULLIF(v_original, ''),
                v_corrected,
                'manager',
                'approval_rescoring',
                NEW.id,
                NEW.decided_by_user_id
            );
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_approval_rescoring_ref ON approval_requests;
CREATE TRIGGER trg_approval_rescoring_ref
    AFTER UPDATE OF status ON approval_requests
    FOR EACH ROW
    EXECUTE FUNCTION trg_approval_rescoring_to_rescore_ref();
