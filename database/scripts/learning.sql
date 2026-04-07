-- =============================================================================
-- Learning Loop Schema
-- Canonical fresh-setup definitions for:
--   - reroute_reference
--   - rescore_reference
--   - suggested_resolution_usage
--
-- Existing databases should still apply migrations under database/migrations/.
-- =============================================================================

-- -------------------------------------------------------------------------
-- reroute_reference
-- Populated from:
--   1. Manager routing review decisions
--   2. Manager approval of rerouting requests
--   3. Operator pipeline-queue department corrections
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reroute_reference (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id       UUID REFERENCES tickets(id) ON DELETE CASCADE,
    department      TEXT NOT NULL,
    original_dept   TEXT,
    corrected_dept  TEXT NOT NULL,
    actor_role      TEXT NOT NULL CHECK (actor_role IN ('manager', 'operator', 'employee')),
    source_type     TEXT NOT NULL,
    source_id       UUID,
    decided_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reroute_ref_dept_created
    ON reroute_reference(department, created_at DESC);

-- -------------------------------------------------------------------------
-- rescore_reference
-- Populated from:
--   1. Manager approval of rescoring requests
--   2. Operator pipeline-queue priority corrections
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rescore_reference (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id           UUID REFERENCES tickets(id) ON DELETE CASCADE,
    department          TEXT NOT NULL,
    original_priority   TEXT,
    corrected_priority  TEXT NOT NULL,
    actor_role          TEXT NOT NULL CHECK (actor_role IN ('manager', 'operator', 'employee')),
    source_type         TEXT NOT NULL,
    source_id           UUID,
    decided_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rescore_ref_dept_created
    ON rescore_reference(department, created_at DESC);

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

-- -------------------------------------------------------------------------
-- suggested_resolution_usage
-- Populated from employee accept/decline usage of suggested resolutions.
-- Used by orchestrator and chatbot prompt-learning paths.
-- -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suggested_resolution_usage (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id        UUID REFERENCES tickets(id) ON DELETE CASCADE,
    employee_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    decision         TEXT CHECK (decision IN ('accepted', 'declined_custom')),
    actor_role       TEXT NOT NULL DEFAULT 'employee' CHECK (actor_role IN ('manager', 'operator', 'employee')),
    department       TEXT NOT NULL,
    suggested_text   TEXT,
    final_text       TEXT,
    used             BOOLEAN NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sru_dept_used_created
    ON suggested_resolution_usage(department, used, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sru_employee_created
    ON suggested_resolution_usage(employee_user_id, created_at DESC);

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

-- =========================================================================
-- Trigger 1: department_routing -> reroute_reference
-- =========================================================================
CREATE OR REPLACE FUNCTION trg_dept_routing_to_reroute_ref()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
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
            NEW.final_department,
            NEW.suggested_department,
            NEW.final_department,
            'manager',
            'manager_review',
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

-- =========================================================================
-- Trigger 2: approval_requests -> reroute_reference
-- =========================================================================
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
                'employee_request',
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

-- =========================================================================
-- Trigger 3: approval_requests -> rescore_reference
-- =========================================================================
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
