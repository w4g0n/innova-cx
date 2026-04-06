BEGIN;

-- Normalize deprecated status values before shrinking enum.
UPDATE tickets
SET status = 'Open'
WHERE status::text IN ('Unassigned', 'Reopened');

UPDATE ticket_updates
SET from_status = 'Open'
WHERE from_status::text IN ('Unassigned', 'Reopened');

UPDATE ticket_updates
SET to_status = 'Open'
WHERE to_status::text IN ('Unassigned', 'Reopened');

-- Do not physically shrink the enum here. Fresh-volume initialization has
-- already attached triggers/functions that depend on tickets.status, and
-- replacing the enum after that causes PostgreSQL to abort the migration.
-- Keeping the enum as a superset is safe; the deprecated data values were
-- normalized above.

COMMIT;
