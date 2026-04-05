-- Add explicit actor_role to learning tables so rows clearly record whether
-- the learning signal came from a manager, operator, or employee.

BEGIN;

ALTER TABLE reroute_reference
    ADD COLUMN IF NOT EXISTS actor_role TEXT;

UPDATE reroute_reference
SET actor_role = CASE
    WHEN source_type = 'operator_correction' THEN 'operator'
    ELSE 'manager'
END
WHERE actor_role IS NULL OR btrim(actor_role) = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'reroute_reference_actor_role_check'
    ) THEN
        ALTER TABLE reroute_reference
        ADD CONSTRAINT reroute_reference_actor_role_check
        CHECK (actor_role IN ('manager', 'operator', 'employee'));
    END IF;
END$$;

ALTER TABLE reroute_reference ALTER COLUMN actor_role SET NOT NULL;

ALTER TABLE rescore_reference
    ADD COLUMN IF NOT EXISTS actor_role TEXT;

UPDATE rescore_reference
SET actor_role = CASE
    WHEN source_type = 'operator_correction' THEN 'operator'
    ELSE 'manager'
END
WHERE actor_role IS NULL OR btrim(actor_role) = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'rescore_reference_actor_role_check'
    ) THEN
        ALTER TABLE rescore_reference
        ADD CONSTRAINT rescore_reference_actor_role_check
        CHECK (actor_role IN ('manager', 'operator', 'employee'));
    END IF;
END$$;

ALTER TABLE rescore_reference ALTER COLUMN actor_role SET NOT NULL;

ALTER TABLE suggested_resolution_usage
    ADD COLUMN IF NOT EXISTS actor_role TEXT;

UPDATE suggested_resolution_usage
SET actor_role = 'employee'
WHERE actor_role IS NULL OR btrim(actor_role) = '';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'suggested_resolution_usage_actor_role_check'
    ) THEN
        ALTER TABLE suggested_resolution_usage
        ADD CONSTRAINT suggested_resolution_usage_actor_role_check
        CHECK (actor_role IN ('manager', 'operator', 'employee'));
    END IF;
END$$;

ALTER TABLE suggested_resolution_usage ALTER COLUMN actor_role SET DEFAULT 'employee';
ALTER TABLE suggested_resolution_usage ALTER COLUMN actor_role SET NOT NULL;

COMMIT;
