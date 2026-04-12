-- Prevent duplicate operator backlog alerts once the queue is already above threshold.
-- We only notify when the open queue crosses from below 10 to 10 or more,
-- with a one-hour dedupe window as an extra safety net.

BEGIN;

CREATE OR REPLACE FUNCTION notify_operator_unassigned_backlog()
RETURNS TRIGGER AS $$
DECLARE
  v_count INTEGER;
  v_prev_count INTEGER;
BEGIN
  IF NEW.status <> 'Open' THEN
    RETURN NEW;
  END IF;

  IF TG_OP = 'UPDATE' AND OLD.status = 'Open' THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*)
  INTO v_count
  FROM tickets
  WHERE status = 'Open';

  v_prev_count := GREATEST(v_count - 1, 0);

  IF v_prev_count < 10 AND v_count >= 10 AND NOT EXISTS (
    SELECT 1
    FROM notifications
    WHERE title = 'Open Ticket Backlog Alert'
      AND created_at >= now() - interval '1 hour'
  ) THEN
    PERFORM notify_all_operators(
      'system',
      'Open Ticket Backlog Alert',
      'There are currently ' || v_count || ' open tickets in the queue. '
        || 'Immediate assignment is recommended to avoid SLA breaches.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMIT;
