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

-- Temporarily cast status columns to text so old enum can be replaced.
ALTER TABLE tickets
  ALTER COLUMN status TYPE TEXT USING status::text;

ALTER TABLE ticket_updates
  ALTER COLUMN from_status TYPE TEXT USING from_status::text;

ALTER TABLE ticket_updates
  ALTER COLUMN to_status TYPE TEXT USING to_status::text;

DROP TYPE IF EXISTS ticket_status;

CREATE TYPE ticket_status AS ENUM (
  'Open',
  'In Progress',
  'Assigned',
  'Overdue',
  'Escalated',
  'Resolved'
);

ALTER TABLE tickets
  ALTER COLUMN status TYPE ticket_status USING status::ticket_status,
  ALTER COLUMN status SET DEFAULT 'Open';

ALTER TABLE ticket_updates
  ALTER COLUMN from_status TYPE ticket_status USING from_status::ticket_status,
  ALTER COLUMN to_status TYPE ticket_status USING
    CASE WHEN to_status IS NULL THEN NULL ELSE to_status::ticket_status END;

COMMIT;
