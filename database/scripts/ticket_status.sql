BEGIN;

CREATE OR REPLACE FUNCTION sync_ticket_status_timestamps()
RETURNS TRIGGER AS $$
BEGIN
  -- Default lifecycle entry state.
  IF NEW.status IS NULL THEN
    NEW.status := 'Open';
  END IF;

  -- Preserve assignment timestamp when ticket first becomes assigned/in-progress.
  IF NEW.status IN ('Assigned', 'In Progress')
     AND NEW.assigned_at IS NULL
     AND (TG_OP = 'INSERT' OR OLD.assigned_at IS NULL) THEN
    NEW.assigned_at := now();
  END IF;

  -- Resolution timestamp must exist when resolved.
  IF NEW.status = 'Resolved' THEN
    NEW.resolved_at := COALESCE(NEW.resolved_at, now());
    IF TG_OP = 'UPDATE' THEN
      NEW.resolved_by_user_id := COALESCE(NEW.resolved_by_user_id, NEW.assigned_to_user_id, OLD.resolved_by_user_id);
    ELSE
      NEW.resolved_by_user_id := COALESCE(NEW.resolved_by_user_id, NEW.assigned_to_user_id);
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tickets_status_timestamps ON tickets;
CREATE TRIGGER trg_tickets_status_timestamps
BEFORE INSERT OR UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION sync_ticket_status_timestamps();

COMMIT;
