-- Canonicalize suggested resolution learning on suggested_resolution_usage.
-- Adds employee/decision fields so the table can back acceptance analytics
-- and ticket-level resolution feedback without relying on the legacy table.

ALTER TABLE suggested_resolution_usage
    ADD COLUMN IF NOT EXISTS employee_user_id UUID REFERENCES users(id) ON DELETE SET NULL;

ALTER TABLE suggested_resolution_usage
    ADD COLUMN IF NOT EXISTS decision TEXT;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'suggested_resolution_usage_decision_check'
    ) THEN
        ALTER TABLE suggested_resolution_usage
        ADD CONSTRAINT suggested_resolution_usage_decision_check
        CHECK (decision IN ('accepted', 'declined_custom') OR decision IS NULL);
    END IF;
END$$;

CREATE INDEX IF NOT EXISTS idx_sru_employee_created
    ON suggested_resolution_usage(employee_user_id, created_at DESC);
