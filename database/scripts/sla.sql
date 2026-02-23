BEGIN;

ALTER TABLE tickets
ADD COLUMN IF NOT EXISTS priority_assigned_at TIMESTAMPTZ;

ALTER TABLE tickets
ADD COLUMN IF NOT EXISTS respond_time_left_seconds INTEGER;

ALTER TABLE tickets
ADD COLUMN IF NOT EXISTS resolve_time_left_seconds INTEGER;

CREATE INDEX IF NOT EXISTS idx_tickets_priority_assigned_at
  ON tickets(priority_assigned_at);

CREATE OR REPLACE FUNCTION sync_ticket_priority_sla()
RETURNS TRIGGER AS $$
DECLARE
  base_ts TIMESTAMPTZ;
  respond_iv INTERVAL;
  resolve_iv INTERVAL;
  should_recompute BOOLEAN := FALSE;
BEGIN
  -- SLA clocks only start once priority assignment timestamp exists.
  IF TG_OP = 'UPDATE' THEN
    IF NEW.priority IS DISTINCT FROM OLD.priority THEN
      NEW.priority_assigned_at := COALESCE(NEW.priority_assigned_at, now());
      should_recompute := TRUE;
    ELSIF NEW.priority_assigned_at IS DISTINCT FROM OLD.priority_assigned_at THEN
      should_recompute := NEW.priority_assigned_at IS NOT NULL;
    ELSIF NEW.respond_due_at IS NULL OR NEW.resolve_due_at IS NULL THEN
      should_recompute := NEW.priority_assigned_at IS NOT NULL;
    END IF;
  ELSE
    should_recompute := NEW.priority_assigned_at IS NOT NULL;
  END IF;

  IF should_recompute THEN
    base_ts := NEW.priority_assigned_at;
    CASE NEW.priority
      WHEN 'Critical' THEN
        respond_iv := interval '30 minutes';
        resolve_iv := interval '6 hours';
      WHEN 'High' THEN
        respond_iv := interval '1 hour';
        resolve_iv := interval '18 hours';
      WHEN 'Medium' THEN
        respond_iv := interval '3 hours';
        resolve_iv := interval '2 days';
      ELSE
        respond_iv := interval '6 hours';
        resolve_iv := interval '3 days';
    END CASE;

    NEW.respond_due_at := base_ts + respond_iv;
    NEW.resolve_due_at := base_ts + resolve_iv;
    NEW.respond_time_left_seconds := GREATEST(EXTRACT(EPOCH FROM (NEW.respond_due_at - now()))::INTEGER, 0);
    NEW.resolve_time_left_seconds := GREATEST(EXTRACT(EPOCH FROM (NEW.resolve_due_at - now()))::INTEGER, 0);
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tickets_priority_sla ON tickets;
CREATE TRIGGER trg_tickets_priority_sla
BEFORE INSERT OR UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION sync_ticket_priority_sla();

CREATE OR REPLACE FUNCTION apply_ticket_sla_policies()
RETURNS JSONB AS $$
DECLARE
  now_ts TIMESTAMPTZ := now();
  escalated_count INTEGER := 0;
  overdue_count INTEGER := 0;
  heartbeat_count INTEGER := 0;
BEGIN
  -- Heartbeat: refresh remaining SLA time columns.
  UPDATE tickets t
  SET
    respond_time_left_seconds = CASE
      WHEN t.status = 'Resolved'::ticket_status OR t.priority_assigned_at IS NULL OR t.respond_due_at IS NULL THEN NULL
      ELSE GREATEST(EXTRACT(EPOCH FROM (t.respond_due_at - now_ts))::INTEGER, 0)
    END,
    resolve_time_left_seconds = CASE
      WHEN t.status = 'Resolved'::ticket_status OR t.priority_assigned_at IS NULL OR t.resolve_due_at IS NULL THEN NULL
      ELSE GREATEST(EXTRACT(EPOCH FROM (t.resolve_due_at - now_ts))::INTEGER, 0)
    END;

  GET DIAGNOSTICS heartbeat_count = ROW_COUNT;

  -- Auto-escalate when 90% of response SLA has elapsed and no first response yet.
  UPDATE tickets t
  SET
    priority = CASE t.priority
      WHEN 'Low'::ticket_priority THEN 'Medium'::ticket_priority
      WHEN 'Medium'::ticket_priority THEN 'High'::ticket_priority
      WHEN 'High'::ticket_priority THEN 'Critical'::ticket_priority
      ELSE 'Critical'::ticket_priority
    END,
    status = CASE WHEN t.status = 'Resolved'::ticket_status THEN t.status ELSE 'Escalated'::ticket_status END,
    priority_assigned_at = now()
  WHERE t.status <> 'Resolved'::ticket_status
    AND t.priority_assigned_at IS NOT NULL
    AND t.respond_due_at IS NOT NULL
    AND t.first_response_at IS NULL
    AND t.priority <> 'Critical'::ticket_priority
    AND now_ts >= t.priority_assigned_at + ((t.respond_due_at - t.priority_assigned_at) * 0.9);

  GET DIAGNOSTICS escalated_count = ROW_COUNT;

  -- Mark overdue if response or resolve SLA has passed and unresolved conditions remain.
  UPDATE tickets t
  SET status = 'Overdue'::ticket_status
  WHERE t.status <> 'Resolved'::ticket_status
    AND (
      (t.first_response_at IS NULL AND t.respond_due_at IS NOT NULL AND now_ts > t.respond_due_at)
      OR
      (t.resolved_at IS NULL AND t.resolve_due_at IS NOT NULL AND now_ts > t.resolve_due_at)
    );

  GET DIAGNOSTICS overdue_count = ROW_COUNT;

  RETURN jsonb_build_object(
    'heartbeat_updated', heartbeat_count,
    'escalated', escalated_count,
    'overdue', overdue_count
  );
END;
$$ LANGUAGE plpgsql;

-- Backfill rows that already had SLA set before this migration.
UPDATE tickets
SET priority_assigned_at = COALESCE(priority_assigned_at, created_at)
WHERE priority_assigned_at IS NULL
  AND (respond_due_at IS NOT NULL OR resolve_due_at IS NOT NULL);

COMMIT;
