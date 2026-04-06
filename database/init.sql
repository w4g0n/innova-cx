-- =========================================================
-- InnovaCX 
-- =========================================================

-- -------------------------
-- Extensions
-- -------------------------
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- gen_random_uuid() + crypt()
CREATE EXTENSION IF NOT EXISTS citext;   -- case-insensitive email
-- -------------------------
-- Enums (match UI strings exactly)
-- -------------------------
DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('customer', 'employee', 'manager', 'operator');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE ticket_status AS ENUM (
    'Open',
    'In Progress',
    'Assigned',
    'Escalated',
    'Overdue',
    'Resolved',
    'Reopened'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE ticket_priority AS ENUM ('Low', 'Medium', 'High', 'Critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE ticket_type AS ENUM ('Complaint', 'Inquiry');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE approval_request_type AS ENUM ('Rescoring', 'Rerouting');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE approval_status AS ENUM ('Pending', 'Approved', 'Rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE chat_sender_type AS ENUM ('customer', 'bot', 'operator');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE notification_type AS ENUM (
    'ticket_assignment',
    'sla_warning',
    'customer_reply',
    'status_change',
    'report_ready',
    'system',
    'pipeline_held'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE service_severity AS ENUM ('ok', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE event_severity AS ENUM ('info', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- -------------------------
-- Helper functions (must be defined before triggers that reference them)
-- -------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- AUDIT LOGGING
-- =========================================================
-- WHY THIS EXISTS:
--   RIGHT NOW: if someone changes a ticket's status, deletes a user,
--   or approves a request, there is NO record of it happening beyond
--   whatever your app logs. If something goes wrong (or someone does
--   something they shouldn't), you can't reconstruct what changed,
--   who did it, or when.
--
-- HOW IT WORKS:
--   The audit_log table records every INSERT / UPDATE / DELETE on the
--   tables you care about. Each row captures:
--     - which table was affected
--     - what the row looked like BEFORE the change (old_data)
--     - what the row looks like AFTER the change (new_data)
--     - which DB role made the change (changed_by)
--     - when it happened (changed_at)
--
-- HOW TO ENABLE AUDITING ON A TABLE:
--   After creating any table, attach the trigger like this:
--     CREATE TRIGGER audit_<tablename>
--     AFTER INSERT OR UPDATE OR DELETE ON <tablename>
--     FOR EACH ROW EXECUTE FUNCTION audit_trigger();
--   (We do this below for: users, tickets, approval_requests)
--
-- HOW TO QUERY THE AUDIT LOG:
--   -- See all changes to a specific ticket:
--   SELECT * FROM audit_log WHERE table_name='tickets'
--     AND (old_data->>'id' = '<uuid>' OR new_data->>'id' = '<uuid>')
--     ORDER BY changed_at DESC;
--
--   -- See all password changes:
--   SELECT changed_at, changed_by, old_data->>'email'
--   FROM audit_log WHERE table_name='users' AND operation='UPDATE'
--     AND old_data->>'password_hash' IS DISTINCT FROM new_data->>'password_hash';
-- =========================================================

CREATE TABLE IF NOT EXISTS audit_log (
  id          BIGSERIAL    PRIMARY KEY,
  table_name  TEXT         NOT NULL,
  operation   TEXT         NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
  old_data    JSONB,        -- NULL on INSERT
  new_data    JSONB,        -- NULL on DELETE
  changed_by  TEXT         NOT NULL DEFAULT current_user,
  changed_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_table      ON audit_log(table_name, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_at ON audit_log(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_changed_by ON audit_log(changed_by);

CREATE OR REPLACE FUNCTION audit_trigger()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO audit_log (table_name, operation, old_data, new_data)
    VALUES (TG_TABLE_NAME, 'INSERT', NULL, to_jsonb(NEW));
    RETURN NEW;
  ELSIF TG_OP = 'UPDATE' THEN
    -- Only log if something actually changed (skip no-op updates)
    IF to_jsonb(OLD) IS DISTINCT FROM to_jsonb(NEW) THEN
      INSERT INTO audit_log (table_name, operation, old_data, new_data)
      VALUES (TG_TABLE_NAME, 'UPDATE', to_jsonb(OLD), to_jsonb(NEW));
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO audit_log (table_name, operation, old_data, new_data)
    VALUES (TG_TABLE_NAME, 'DELETE', to_jsonb(OLD), NULL);
    RETURN OLD;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- -------------------------
-- Reference tables
-- -------------------------
CREATE TABLE IF NOT EXISTS departments (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------
-- Users + Profiles (Identity)
-- -------------------------
-- =========================================================
-- CREDENTIAL ROTATION EXPLAINED
-- =========================================================
-- RIGHT NOW: Every user has the same static password ('Innova@2025').
-- It was set once during seeding and never tracked. If someone gets
-- hold of that password, there is no way to know how long they've had
-- access or when it was last changed.
--
-- WHAT WE'RE ADDING:
--   1. password_last_rotated_at — tracks WHEN the password was last
--      changed so you can enforce a "must rotate every 90 days" policy.
--   2. rotate_user_password() function — a safe, reusable way for your
--      app/scripts to change a password without writing raw SQL.
--   3. Production guard on the dev reset token — stops the hardcoded
--      dev token from being inserted into a production database.
--   4. Token cleanup function — deletes expired/used reset tokens
--      automatically so they can't pile up and be exploited.
-- =========================================================

CREATE TABLE IF NOT EXISTS users (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email                    CITEXT NOT NULL UNIQUE,
  password_hash            TEXT NOT NULL,
  role                     user_role NOT NULL,
  is_active                BOOLEAN NOT NULL DEFAULT TRUE,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at            TIMESTAMPTZ,
  -- ADDED: tracks when the password was last rotated.
  -- Without this column you have NO way to know if a password is 3 days
  -- old or 3 years old. Your app can query this to enforce expiry rules.
  password_last_rotated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------
-- User Preferences
-- -------------------------
CREATE TABLE IF NOT EXISTS user_preferences (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  language TEXT NOT NULL DEFAULT 'English',
  dark_mode BOOLEAN NOT NULL DEFAULT FALSE,
  default_complaint_type TEXT NOT NULL DEFAULT 'General',
  email_notifications BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_notifications BOOLEAN NOT NULL DEFAULT TRUE,
  status_alerts BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_user_preferences_updated_at
BEFORE UPDATE ON user_preferences
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- -------------------------
-- MFA columns (safe for re-runs)
-- -------------------------
ALTER TABLE users
ADD COLUMN IF NOT EXISTS totp_secret TEXT;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;

-- Also safe-add the rotation column on existing volumes
ALTER TABLE users
ADD COLUMN IF NOT EXISTS password_last_rotated_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- =========================================================
-- CREDENTIAL ROTATION: rotate_user_password()
-- =========================================================
-- WHY THIS EXISTS:
--   Before this function, changing a password meant writing raw SQL
--   like: UPDATE users SET password_hash = crypt(...)
--   That's fine in dev, but in production it's risky — easy to forget
--   the bcrypt call, easy to accidentally skip the active-user check,
--   and nothing ever updates password_last_rotated_at.
--
-- HOW TO USE IT (run this whenever you want to rotate a password):
--   SELECT rotate_user_password('ahmed@innovacx.net', 'NewSecurePass!99');
--
-- It will:
--   - Reject the call if the user doesn't exist or is inactive
--   - Hash the password with bcrypt cost 12 (current best practice)
--   - Update password_last_rotated_at to NOW() automatically
-- =========================================================
CREATE OR REPLACE FUNCTION rotate_user_password(
  p_email  CITEXT,
  p_new_pw TEXT
) RETURNS VOID AS $$
BEGIN
  UPDATE users
  SET
    password_hash            = crypt(p_new_pw, gen_salt('bf', 12)),
    password_last_rotated_at = now()
  WHERE email     = p_email
    AND is_active = TRUE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'rotate_user_password: user not found or inactive: %', p_email;
  END IF;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =========================================================
-- CREDENTIAL ROTATION: cleanup_expired_tokens()
-- =========================================================
-- WHY THIS EXISTS:
--   RIGHT NOW: expired and already-used password reset tokens stay in
--   the database forever. They can't be used (expires_at is in the past
--   or used_at is set), but they clutter the table and could leak info
--   if the DB is ever compromised.
--
-- HOW TO USE IT:
--   SELECT cleanup_expired_tokens();
--   Run this on a schedule (e.g. nightly via pg_cron or a cron job):
--     SELECT cron.schedule('token-cleanup','0 3 * * *','SELECT cleanup_expired_tokens()');
-- =========================================================
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS INTEGER AS $$
DECLARE
  deleted_count INTEGER;
BEGIN
  DELETE FROM password_reset_tokens
  WHERE expires_at < now()
     OR used_at IS NOT NULL;

  GET DIAGNOSTICS deleted_count = ROW_COUNT;
  RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS user_profiles (
  user_id       UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  full_name     TEXT NOT NULL,
  phone         TEXT,
  location      TEXT,
  department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
  employee_code TEXT UNIQUE,
  job_title     TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash  TEXT NOT NULL UNIQUE,
  expires_at  TIMESTAMPTZ NOT NULL,
  used_at     TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------
-- Tickets
-- -------------------------
CREATE TABLE IF NOT EXISTS tickets (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_code         TEXT NOT NULL UNIQUE,
  subject             TEXT NOT NULL,
  details             TEXT NOT NULL,
  ticket_type         ticket_type,
  status              ticket_status NOT NULL DEFAULT 'Open',
  priority            ticket_priority,
  department_id       UUID REFERENCES departments(id) ON DELETE SET NULL,
  created_by_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  assigned_to_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  assigned_at         TIMESTAMPTZ,
  first_response_at   TIMESTAMPTZ,
  resolved_at         TIMESTAMPTZ,
  respond_due_at      TIMESTAMPTZ,
  resolve_due_at      TIMESTAMPTZ,
  respond_time_left_seconds INTEGER,
  resolve_time_left_seconds INTEGER,
  respond_breached    BOOLEAN NOT NULL DEFAULT FALSE,
  resolve_breached    BOOLEAN NOT NULL DEFAULT FALSE,
  sentiment_score     NUMERIC(4,3),
  sentiment_label     TEXT,
  model_priority      ticket_priority,
  model_department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
  model_confidence    NUMERIC(5,2),
  model_suggestion    TEXT,
  ticket_source       TEXT NOT NULL DEFAULT 'user',
  final_resolution    TEXT,
  resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- =============================================================================
-- Suggested Resolution + Retraining schema
-- =============================================================================
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_model TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_generated_at TIMESTAMPTZ;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS asset_type TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS human_overridden BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS is_recurring BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS linked_ticket_code TEXT;

DO $$ BEGIN
  ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'recurrence_reminder';
EXCEPTION WHEN others THEN NULL; END $$;

DO $$ BEGIN
  ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'Reopened';
EXCEPTION WHEN others THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_tickets_status      ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority    ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at  ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_assignee    ON tickets(assigned_to_user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_creator     ON tickets(created_by_user_id);

-- =========================================================
-- AUDIT TRIGGERS: attach to sensitive tables
-- =========================================================
-- These fire automatically on every change — you don't need to call
-- anything. Check audit_log to see a full history of what changed.
-- =========================================================

-- Track all user changes (password rotations, role changes, deactivation)
DROP TRIGGER IF EXISTS audit_users ON users;
CREATE TRIGGER audit_users
AFTER INSERT OR UPDATE OR DELETE ON users
FOR EACH ROW EXECUTE FUNCTION audit_trigger();

-- Track all ticket changes (status, assignment, priority)
DROP TRIGGER IF EXISTS audit_tickets ON tickets;
CREATE TRIGGER audit_tickets
AFTER INSERT OR UPDATE OR DELETE ON tickets
FOR EACH ROW EXECUTE FUNCTION audit_trigger();

-- NOTE: audit_approval_requests is attached after approval_requests table is created below

DROP TRIGGER IF EXISTS trg_tickets_updated_at ON tickets;
CREATE TRIGGER trg_tickets_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- -------------------------
-- Ticket status sync rules
-- -------------------------
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
    IF TG_OP = 'UPDATE' AND OLD.status <> 'Resolved' THEN
      -- Transitioning into Resolved from any other state (including Reopened):
      -- always stamp a fresh timestamp so a second resolution overwrites the first.
      NEW.resolved_at := now();
      NEW.resolved_by_user_id := COALESCE(NEW.resolved_by_user_id, NEW.assigned_to_user_id);
    ELSE
      -- INSERT, or an UPDATE that stays Resolved (e.g. updating other fields):
      -- preserve existing values if already set.
      NEW.resolved_at := COALESCE(NEW.resolved_at, now());
      IF TG_OP = 'UPDATE' THEN
        NEW.resolved_by_user_id := COALESCE(NEW.resolved_by_user_id, NEW.assigned_to_user_id, OLD.resolved_by_user_id);
      ELSE
        NEW.resolved_by_user_id := COALESCE(NEW.resolved_by_user_id, NEW.assigned_to_user_id);
      END IF;
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

-- -------------------------
-- SLA policy schema + logic
-- -------------------------
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

-- -------------------------
-- Recurrence classifier helper function
-- -------------------------
CREATE OR REPLACE FUNCTION compute_is_recurring_ticket(
  p_user_id UUID,
  p_subject TEXT,
  p_details TEXT,
  p_window_days INTEGER DEFAULT 180
)
RETURNS BOOLEAN AS $$
DECLARE
  normalized_subject TEXT := lower(trim(COALESCE(p_subject, '')));
  exact_subject_count INTEGER := 0;
BEGIN
  IF p_user_id IS NULL THEN
    RETURN FALSE;
  END IF;

  SELECT COUNT(*)
  INTO exact_subject_count
  FROM tickets t
  WHERE t.created_by_user_id = p_user_id
    AND t.created_at >= now() - make_interval(days => p_window_days)
    AND lower(trim(COALESCE(t.subject, ''))) = normalized_subject;

  IF exact_subject_count > 0 THEN
    RETURN TRUE;
  END IF;

  -- Fallback: check simple token overlap on details when subject wasn't matched.
  RETURN EXISTS (
    SELECT 1
    FROM tickets t
    WHERE t.created_by_user_id = p_user_id
      AND t.created_at >= now() - make_interval(days => p_window_days)
      AND tsvector_to_array(to_tsvector('simple', COALESCE(t.details, ''))) &&
          tsvector_to_array(to_tsvector('simple', COALESCE(p_details, '')))
  );
END;
$$ LANGUAGE plpgsql STABLE;

-- -------------------------
-- Ticket attachments
-- -------------------------
CREATE TABLE IF NOT EXISTS ticket_attachments (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  file_name   TEXT NOT NULL,
  file_url    TEXT,
  uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_attachments_ticket ON ticket_attachments(ticket_id);

-- -------------------------
-- Ticket updates
-- -------------------------
CREATE TABLE IF NOT EXISTS ticket_updates (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id      UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  author_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  update_type    TEXT NOT NULL,
  message        TEXT NOT NULL,
  from_status    ticket_status,
  to_status      ticket_status,
  meta           JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_updates_ticket  ON ticket_updates(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_updates_created ON ticket_updates(created_at);

-- -------------------------
-- Steps taken
-- -------------------------
CREATE TABLE IF NOT EXISTS ticket_work_steps (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id          UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  step_no            INT NOT NULL,
  technician_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  occurred_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes              TEXT,
  UNIQUE(ticket_id, step_no)
);

-- -------------------------
-- Approvals
-- -------------------------
CREATE TABLE IF NOT EXISTS approval_requests (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_code         TEXT NOT NULL UNIQUE,
  ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  request_type         approval_request_type NOT NULL,
  current_value        TEXT NOT NULL,
  requested_value      TEXT NOT NULL,
  request_reason       TEXT,
  submitted_by_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  source               TEXT NOT NULL DEFAULT 'employee',
  requested_to_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  model_name           TEXT,
  model_confidence     NUMERIC(5,4),
  submitted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  status               approval_status NOT NULL DEFAULT 'Pending',
  decided_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
  decided_at           TIMESTAMPTZ,
  decision_notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_ticket ON approval_requests(ticket_id);
CREATE INDEX IF NOT EXISTS idx_approval_requests_requested_to ON approval_requests(requested_to_user_id);

-- Audit + validation triggers for approval_requests (must be after table creation)
DROP TRIGGER IF EXISTS audit_approval_requests ON approval_requests;
CREATE TRIGGER audit_approval_requests
AFTER INSERT OR UPDATE OR DELETE ON approval_requests
FOR EACH ROW EXECUTE FUNCTION audit_trigger();

CREATE TABLE IF NOT EXISTS department_routing_feedback (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  predicted_department TEXT NOT NULL,
  approved_department  TEXT NOT NULL,
  confidence_score     NUMERIC(5,4),
  model_name           TEXT,
  approved_by_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_routing_feedback_predicted ON department_routing_feedback(predicted_department);
CREATE INDEX IF NOT EXISTS idx_routing_feedback_created_at ON department_routing_feedback(created_at);

CREATE TABLE IF NOT EXISTS department_routing (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  suggested_department TEXT NOT NULL,
  confidence_score     NUMERIC(5,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
  is_confident         BOOLEAN NOT NULL,
  final_department     TEXT,
  routed_by            TEXT CHECK (routed_by IN ('model', 'manager', 'manager_denied')),
  manager_id           UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_department_routing_ticket
  ON department_routing(ticket_id);
CREATE INDEX IF NOT EXISTS idx_department_routing_pending
  ON department_routing(is_confident, final_department, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_department_routing_finalized
  ON department_routing(final_department, routed_by, updated_at DESC);

-- Learning-loop triggers depend on approval_requests and department_routing.
-- Include after both base tables exist to keep fresh-volume init deterministic.
\ir scripts/learning.sql

-- -------------------------
-- Auto-notify manager on new approval requests
-- -------------------------
CREATE OR REPLACE FUNCTION notify_manager_on_approval_request()
RETURNS TRIGGER AS $$
DECLARE
  v_manager_id      UUID;
  v_ticket_code     TEXT;
  v_ticket_priority ticket_priority;
  v_ticket_dept_id  UUID;
  v_submitter_name  TEXT;
  v_submitter_role  user_role;
  v_title           TEXT;
  v_message         TEXT;
  v_found_manager   BOOLEAN := FALSE;
BEGIN
  SELECT role INTO v_submitter_role
  FROM users WHERE id = NEW.submitted_by_user_id;

  IF v_submitter_role = 'manager' THEN
    RETURN NEW;
  END IF;

  SELECT ticket_code, priority, department_id
  INTO v_ticket_code, v_ticket_priority, v_ticket_dept_id
  FROM tickets WHERE id = NEW.ticket_id;

  SELECT full_name INTO v_submitter_name
  FROM user_profiles WHERE user_id = NEW.submitted_by_user_id;

  v_title := CASE NEW.request_type
    WHEN 'Rescoring' THEN 'Rescoring Request — ' || COALESCE(v_ticket_code, 'Unknown')
    WHEN 'Rerouting' THEN 'Rerouting Request — ' || COALESCE(v_ticket_code, 'Unknown')
    ELSE 'Approval Request — ' || COALESCE(v_ticket_code, 'Unknown')
  END;

  v_message := COALESCE(v_submitter_name, 'An employee') || ' submitted a '
    || lower(NEW.request_type::TEXT) || ' request. '
    || 'Current: ' || NEW.current_value || ' → Requested: ' || NEW.requested_value || '.';

  -- ── Case 1: explicit target manager set by backend ────────────────────────
  IF NEW.requested_to_user_id IS NOT NULL THEN
    INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
    VALUES (
      NEW.requested_to_user_id,
      'status_change',
      v_title,
      v_message,
      v_ticket_priority,
      NEW.ticket_id
    );
    RETURN NEW;
  END IF;

  -- ── Case 2: no explicit target — route to the manager of the ticket dept ──
  -- Find the manager whose user_profiles.department_id = ticket.department_id.
  -- Only ONE notification is inserted, for the correct department manager.
  IF v_ticket_dept_id IS NOT NULL THEN
    FOR v_manager_id IN
      SELECT u.id
      FROM users u
      JOIN user_profiles up ON up.user_id = u.id
      WHERE u.role = 'manager'
        AND u.is_active = TRUE
        AND up.department_id = v_ticket_dept_id
      LIMIT 1
    LOOP
      INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
      VALUES (
        v_manager_id,
        'status_change',
        v_title,
        v_message,
        v_ticket_priority,
        NEW.ticket_id
      );
      v_found_manager := TRUE;
    END LOOP;
  END IF;

  -- ── Case 3: no dept or no manager found for dept — fallback to all managers
  -- This prevents silent notification loss when a ticket has no department.
  IF NOT v_found_manager THEN
    FOR v_manager_id IN
      SELECT id FROM users
      WHERE role = 'manager' AND is_active = TRUE
    LOOP
      INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
      VALUES (
        v_manager_id,
        'status_change',
        v_title,
        v_message,
        v_ticket_priority,
        NEW.ticket_id
      );
    END LOOP;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_manager_approval_request ON approval_requests;
CREATE TRIGGER trg_notify_manager_approval_request
AFTER INSERT ON approval_requests
FOR EACH ROW
EXECUTE FUNCTION notify_manager_on_approval_request();

-- -------------------------
-- Auto-notify manager on their own approval decision (confirmation)
-- -------------------------
CREATE OR REPLACE FUNCTION notify_manager_on_approval_decision()
RETURNS TRIGGER AS $$
DECLARE
  v_ticket_code    TEXT;
  v_ticket_priority ticket_priority;
  v_title          TEXT;
  v_message        TEXT;
BEGIN
  -- Only fire when status actually changes to Approved or Rejected
  IF OLD.status = NEW.status THEN RETURN NEW; END IF;
  IF NEW.status NOT IN ('Approved', 'Rejected') THEN RETURN NEW; END IF;
  IF NEW.decided_by_user_id IS NULL THEN RETURN NEW; END IF;

  SELECT ticket_code, priority
  INTO v_ticket_code, v_ticket_priority
  FROM tickets WHERE id = NEW.ticket_id;

  v_title := NEW.status || ': ' || NEW.request_type::TEXT || ' — ' || COALESCE(v_ticket_code, 'Unknown');

  v_message := 'You ' || lower(NEW.status::TEXT) || ' the '
    || lower(NEW.request_type::TEXT) || ' request for ticket '
    || COALESCE(v_ticket_code, 'Unknown') || '. '
    || 'Change: ' || NEW.current_value || ' → ' || NEW.requested_value || '.';

  INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
  VALUES (
    NEW.decided_by_user_id,
    'status_change',
    v_title,
    v_message,
    v_ticket_priority,
    NEW.ticket_id
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_manager_approval_decision ON approval_requests;
CREATE TRIGGER trg_notify_manager_approval_decision
AFTER UPDATE ON approval_requests
FOR EACH ROW
EXECUTE FUNCTION notify_manager_on_approval_decision();

-- =========================================================
-- Customer Notifications
-- Triggers:
--   1. On ticket INSERT → "Ticket Received" notification
--   2. On ticket status UPDATE → "Status Changed" notification
--   3. On ticket resolved (status = 'Resolved') → "Resolved" notification
-- =========================================================

-- ─────────────────────────────────────────────────────────
-- Helper: notify customer on new ticket creation
-- ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION notify_customer_on_ticket_create()
RETURNS TRIGGER AS $$
BEGIN
  -- Only notify if the ticket was created by a customer role user
  IF NOT EXISTS (
    SELECT 1 FROM users
    WHERE id = NEW.created_by_user_id AND role = 'customer'
  ) THEN
    RETURN NEW;
  END IF;

  INSERT INTO notifications (
    user_id,
    type,
    title,
    message,
    priority,
    ticket_id
  ) VALUES (
    NEW.created_by_user_id,
    'ticket_assignment',
    'Ticket Received — ' || NEW.ticket_code,
    'Your ticket "' || NEW.subject || '" has been received and is currently ' || NEW.status::TEXT || '. We will keep you updated.',
    NEW.priority,
    NEW.id
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_customer_ticket_create ON tickets;
CREATE TRIGGER trg_notify_customer_ticket_create
AFTER INSERT ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_customer_on_ticket_create();


-- ─────────────────────────────────────────────────────────
-- Helper: notify customer on ticket status change
-- Fires on any status transition (excluding Resolved — handled separately below)
-- ─────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION notify_customer_on_status_change()
RETURNS TRIGGER AS $$
DECLARE
  v_title   TEXT;
  v_message TEXT;
BEGIN
  -- Only fire when status actually changed
  IF OLD.status = NEW.status THEN
    RETURN NEW;
  END IF;

  -- Only notify customers
  IF NOT EXISTS (
    SELECT 1 FROM users
    WHERE id = NEW.created_by_user_id AND role = 'customer'
  ) THEN
    RETURN NEW;
  END IF;

  -- Handle Resolved separately with a richer message
  IF NEW.status = 'Resolved' THEN
    v_title := 'Ticket Resolved — ' || NEW.ticket_code;
    v_message := 'Great news! Your ticket "' || NEW.subject || '" has been resolved. '
      || CASE
           WHEN NEW.final_resolution IS NOT NULL
           THEN 'Resolution: ' || NEW.final_resolution
           ELSE 'Please contact us if you need any further assistance.'
         END;
  ELSE
    v_title := 'Ticket Update — ' || NEW.ticket_code;
    v_message := 'Your ticket "' || NEW.subject || '" status has been updated from '
      || OLD.status::TEXT || ' to ' || NEW.status::TEXT || '.';
  END IF;

  INSERT INTO notifications (
    user_id,
    type,
    title,
    message,
    priority,
    ticket_id
  ) VALUES (
    NEW.created_by_user_id,
    CASE
      WHEN NEW.status = 'Resolved'  THEN 'status_change'::notification_type
      WHEN NEW.status = 'Escalated' THEN 'sla_warning'::notification_type
      WHEN NEW.status = 'Overdue'   THEN 'sla_warning'::notification_type
      ELSE                               'status_change'::notification_type
    END,
    v_title,
    v_message,
    NEW.priority,
    NEW.id
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_customer_status_change ON tickets;
CREATE TRIGGER trg_notify_customer_status_change
AFTER UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_customer_on_status_change();

-- -------------------------
-- Customer notifications for rescore / reroute requests
-- -------------------------

-- 1. Notify customer when they (or staff on their behalf) submit a rescore or reroute request
CREATE OR REPLACE FUNCTION notify_customer_on_approval_submit()
RETURNS TRIGGER AS $$
DECLARE
  v_customer_id UUID;
  v_ticket_code TEXT;
  v_subject     TEXT;
  v_title       TEXT;
  v_message     TEXT;
BEGIN
  -- Resolve customer id + ticket details
  SELECT t.created_by_user_id, t.ticket_code, t.subject
    INTO v_customer_id, v_ticket_code, v_subject
    FROM tickets t
   WHERE t.id = NEW.ticket_id
   LIMIT 1;

  -- Only send if the ticket owner is a customer
  IF NOT EXISTS (
    SELECT 1 FROM users WHERE id = v_customer_id AND role = 'customer'
  ) THEN
    RETURN NEW;
  END IF;

  IF NEW.request_type = 'Rescoring' THEN
    v_title   := 'Rescoring Requested — ' || v_ticket_code;
    v_message := 'A priority rescoring request has been submitted for your ticket "'
      || v_subject || '" (from ' || NEW.current_value || ' to ' || NEW.requested_value
      || '). It is now pending manager review.';
  ELSIF NEW.request_type = 'Rerouting' THEN
    v_title   := 'Rerouting Requested — ' || v_ticket_code;
    v_message := 'A department rerouting request has been submitted for your ticket "'
      || v_subject || '" (from ' || NEW.current_value || ' to ' || NEW.requested_value
      || '). It is now pending manager review.';
  ELSE
    RETURN NEW;
  END IF;

  INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
  VALUES (
    v_customer_id,
    'status_change'::notification_type,
    v_title,
    v_message,
    'Medium',
    NEW.ticket_id
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_customer_approval_submit ON approval_requests;
CREATE TRIGGER trg_notify_customer_approval_submit
AFTER INSERT ON approval_requests
FOR EACH ROW
EXECUTE FUNCTION notify_customer_on_approval_submit();


-- 2. Notify customer when their rescore / reroute request is approved or rejected
CREATE OR REPLACE FUNCTION notify_customer_on_approval_decision()
RETURNS TRIGGER AS $$
DECLARE
  v_customer_id UUID;
  v_ticket_code TEXT;
  v_subject     TEXT;
  v_title       TEXT;
  v_message     TEXT;
BEGIN
  -- Only fire when status actually changed to a decided state
  IF OLD.status = NEW.status THEN
    RETURN NEW;
  END IF;

  IF NEW.status NOT IN ('Approved', 'Rejected') THEN
    RETURN NEW;
  END IF;

  -- Resolve customer id + ticket details
  SELECT t.created_by_user_id, t.ticket_code, t.subject
    INTO v_customer_id, v_ticket_code, v_subject
    FROM tickets t
   WHERE t.id = NEW.ticket_id
   LIMIT 1;

  -- Only send if the ticket owner is a customer
  IF NOT EXISTS (
    SELECT 1 FROM users WHERE id = v_customer_id AND role = 'customer'
  ) THEN
    RETURN NEW;
  END IF;

  IF NEW.request_type = 'Rescoring' THEN
    IF NEW.status = 'Approved' THEN
      v_title   := 'Priority Updated — ' || v_ticket_code;
      v_message := 'Your ticket "' || v_subject || '" priority has been updated from '
        || NEW.current_value || ' to ' || NEW.requested_value || ' following a rescoring review.';
    ELSE
      v_title   := 'Rescoring Request Declined — ' || v_ticket_code;
      v_message := 'The rescoring request for your ticket "' || v_subject
        || '" was reviewed and the priority will remain as ' || NEW.current_value || '.'
        || CASE WHEN NEW.decision_notes IS NOT NULL
             THEN ' Note: ' || NEW.decision_notes
             ELSE '' END;
    END IF;

  ELSIF NEW.request_type = 'Rerouting' THEN
    IF NEW.status = 'Approved' THEN
      v_title   := 'Ticket Rerouted — ' || v_ticket_code;
      v_message := 'Your ticket "' || v_subject || '" has been rerouted from '
        || NEW.current_value || ' to the ' || NEW.requested_value || ' department.';
    ELSE
      v_title   := 'Rerouting Request Declined — ' || v_ticket_code;
      v_message := 'The rerouting request for your ticket "' || v_subject
        || '" was reviewed and it will remain with the ' || NEW.current_value || ' department.'
        || CASE WHEN NEW.decision_notes IS NOT NULL
             THEN ' Note: ' || NEW.decision_notes
             ELSE '' END;
    END IF;

  ELSE
    RETURN NEW;
  END IF;

  INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
  VALUES (
    v_customer_id,
    'status_change'::notification_type,
    v_title,
    v_message,
    'Medium',
    NEW.ticket_id
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_customer_approval_decision ON approval_requests;
CREATE TRIGGER trg_notify_customer_approval_decision
AFTER UPDATE ON approval_requests
FOR EACH ROW
EXECUTE FUNCTION notify_customer_on_approval_decision();

-- -------------------------
-- Chat tables
-- -------------------------
CREATE TABLE IF NOT EXISTS chat_conversations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_user_id  UUID REFERENCES users(id) ON DELETE SET NULL,
  channel           TEXT NOT NULL DEFAULT 'web',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at          TIMESTAMPTZ,
  status            TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id  UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
  sender_type      chat_sender_type NOT NULL,
  sender_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
  message_text     TEXT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  intent           TEXT,
  category         TEXT,
  sentiment_score  NUMERIC(4,3),
  escalation_flag  BOOLEAN NOT NULL DEFAULT FALSE,
  linked_ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_convo   ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);

-- -------------------------
-- Chatbot session + analytics
-- -------------------------
CREATE TABLE IF NOT EXISTS sessions (
  session_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  current_state  TEXT NOT NULL DEFAULT 'greeting',
  context        JSONB NOT NULL DEFAULT '{}'::jsonb,
  history        JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sessions
ADD COLUMN IF NOT EXISTS bot_model_version TEXT,
ADD COLUMN IF NOT EXISTS escalated_to_human BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS linked_ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at);

DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
BEFORE UPDATE ON sessions
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS user_chat_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id       UUID REFERENCES sessions(session_id) ON DELETE SET NULL,
  user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message          TEXT NOT NULL,
  intent_detected  TEXT,
  aggression_flag  BOOLEAN NOT NULL DEFAULT FALSE,
  aggression_score NUMERIC(5,4),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE user_chat_logs
ADD COLUMN IF NOT EXISTS ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL;

ALTER TABLE user_chat_logs
ADD COLUMN IF NOT EXISTS sentiment_score NUMERIC(4,3),
ADD COLUMN IF NOT EXISTS category TEXT,
ADD COLUMN IF NOT EXISTS response_time_ms INTEGER;

CREATE INDEX IF NOT EXISTS idx_user_chat_logs_session ON user_chat_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_user ON user_chat_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_created ON user_chat_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_ticket ON user_chat_logs(ticket_id);

CREATE TABLE IF NOT EXISTS bot_response_logs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id       UUID REFERENCES sessions(session_id) ON DELETE SET NULL,
  response         TEXT NOT NULL,
  response_type    TEXT,
  state_at_time    TEXT,
  sql_query_used   TEXT,
  kb_match_score   NUMERIC(8,5),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE bot_response_logs
ADD COLUMN IF NOT EXISTS ticket_id UUID REFERENCES tickets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_bot_response_logs_session ON bot_response_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_bot_response_logs_created ON bot_response_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_bot_response_logs_ticket ON bot_response_logs(ticket_id);

-- -------------------------
-- Notifications
-- -------------------------
CREATE TABLE IF NOT EXISTS notifications (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  type       notification_type NOT NULL,
  title      TEXT NOT NULL,
  message    TEXT NOT NULL,
  priority   ticket_priority,
  ticket_id  UUID REFERENCES tickets(id) ON DELETE SET NULL,
  report_id  TEXT,
  read       BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications(read);

-- -------------------------
-- Ticket Messages (employee <-> customer conversation)
-- -------------------------
CREATE TABLE IF NOT EXISTS ticket_messages (
  id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   UUID        NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  sender_id   UUID        NOT NULL REFERENCES users(id)   ON DELETE RESTRICT,
  sender_role TEXT        NOT NULL CHECK (sender_role IN ('customer', 'employee')),
  body        TEXT        NOT NULL CHECK (btrim(body) <> ''),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket
  ON ticket_messages(ticket_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_sender
  ON ticket_messages(sender_id);

-- -------------------------
-- Employee Monthly Reports
-- -------------------------
CREATE TABLE IF NOT EXISTS employee_reports (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_code      TEXT NOT NULL UNIQUE,
  employee_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  month_label      TEXT NOT NULL,
  subtitle         TEXT NOT NULL,
  kpi_rating       TEXT NOT NULL,
  kpi_resolved     INT  NOT NULL,
  kpi_sla          TEXT NOT NULL,
  kpi_avg_response TEXT NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE employee_reports
ADD COLUMN IF NOT EXISTS model_version TEXT,
ADD COLUMN IF NOT EXISTS generated_by TEXT,
ADD COLUMN IF NOT EXISTS period_start DATE,
ADD COLUMN IF NOT EXISTS period_end DATE;

CREATE TABLE IF NOT EXISTS employee_report_summary_items (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id  UUID NOT NULL REFERENCES employee_reports(id) ON DELETE CASCADE,
  label      TEXT NOT NULL,
  value_text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_report_rating_components (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID NOT NULL REFERENCES employee_reports(id) ON DELETE CASCADE,
  name      TEXT NOT NULL,
  score     NUMERIC(4,1) NOT NULL,
  pct       INT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_report_weekly (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id    UUID NOT NULL REFERENCES employee_reports(id) ON DELETE CASCADE,
  week_label   TEXT NOT NULL,
  assigned     INT NOT NULL,
  resolved     INT NOT NULL,
  sla          TEXT NOT NULL,
  avg_response TEXT NOT NULL,
  delta_type   TEXT NOT NULL,
  delta_text   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS employee_report_notes (
  id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id UUID NOT NULL REFERENCES employee_reports(id) ON DELETE CASCADE,
  note      TEXT NOT NULL
);

-- -------------------------
-- Operator System Dashboard
-- -------------------------
CREATE TABLE IF NOT EXISTS system_service_status (
  name       TEXT PRIMARY KEY,
  status     TEXT NOT NULL,
  severity   service_severity NOT NULL DEFAULT 'ok',
  note       TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_integration_status (
  name       TEXT PRIMARY KEY,
  status     TEXT NOT NULL,
  severity   service_severity NOT NULL DEFAULT 'ok',
  note       TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_queue_metrics (
  name        TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  severity    service_severity NOT NULL DEFAULT 'ok',
  note        TEXT NOT NULL,
  measured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_event_feed (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  severity    event_severity NOT NULL DEFAULT 'info',
  title       TEXT NOT NULL,
  description TEXT NOT NULL,
  event_time  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_versions (
  component   TEXT PRIMARY KEY,
  version     TEXT NOT NULL,
  deployed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS system_config_kv (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

-- =========================================================
-- Pipeline Queue
-- =========================================================
DO $$ BEGIN
  CREATE TYPE pipeline_queue_status AS ENUM (
    'queued',
    'processing',
    'held',
    'completed',
    'failed'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS pipeline_queue (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id            UUID REFERENCES tickets(id) ON DELETE CASCADE,
    ticket_code          TEXT,

    -- Queue state
    status               pipeline_queue_status NOT NULL DEFAULT 'queued',
    queue_position       INT,
    retry_count          INT NOT NULL DEFAULT 0,

    -- Failure tracking
    failed_stage         TEXT,
    failed_at_step       INT,
    failure_reason       TEXT,
    failure_category     TEXT,                         -- 'timeout' | 'model_error' | 'connection_error' | 'unknown'
    failure_history      JSONB NOT NULL DEFAULT '[]',  -- [{attempt, stage, category, reason, ts}]

    -- State snapshots for resume
    checkpoint_state     JSONB NOT NULL DEFAULT '{}',
    operator_corrections JSONB NOT NULL DEFAULT '{}',

    -- Initial ticket data needed to start / restart pipeline
    ticket_input         JSONB NOT NULL DEFAULT '{}',

    -- Execution linkage
    execution_id         UUID,

    -- Timestamps
    entered_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at           TIMESTAMPTZ,
    completed_at         TIMESTAMPTZ,
    held_at              TIMESTAMPTZ,
    released_at          TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pq_status
    ON pipeline_queue(status, queue_position NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_pq_ticket_id
    ON pipeline_queue(ticket_id);
CREATE INDEX IF NOT EXISTS idx_pq_ticket_code
    ON pipeline_queue(ticket_code);
CREATE INDEX IF NOT EXISTS idx_pq_entered_at
    ON pipeline_queue(entered_at DESC);

\ir migrations/001_agent_execution_logs.sql
\ir migrations/002_operator_notifications.sql
\ir migrations/007_ticket_priority_nullable.sql
\ir migrations/018_pipeline_runtime_control.sql
\ir migrations/018_pipeline_runtime_control.sql

-- =========================================================
-- Seed data
-- =========================================================
INSERT INTO user_preferences (
    user_id,
    language,
    dark_mode,
    default_complaint_type,
    email_notifications,
    in_app_notifications,
    status_alerts
)
SELECT u.id, 'English', false, 'General', true, true, true
FROM users u
WHERE NOT EXISTS (
    SELECT 1 FROM user_preferences pref WHERE pref.user_id = u.id
);

INSERT INTO departments (name) VALUES
  ('Facilities Management'),
  ('Legal & Compliance'),
  ('Safety & Security'),
  ('HR'),
  ('Leasing'),
  ('Maintenance'),
  ('IT')
ON CONFLICT (name) DO NOTHING;

-- ✅ Use real bcrypt-compatible hashes from pgcrypto (fresh volumes work)
-- mfa_enabled = FALSE and totp_secret = NULL so all users get a proper
-- bearer token on login (no MFA prompt during development/testing)
INSERT INTO users (email, password_hash, role, mfa_enabled, totp_secret) VALUES
  -- Customers
  ('customer1@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  FALSE, NULL),
  ('customer2@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  FALSE, NULL),
  ('customer3@innovacx.net', crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  FALSE, NULL),
  -- Operator
  ('operator@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'operator',  FALSE, NULL),
  -- Managers (1 per department)
  ('hamad@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('leen@innovacx.net',      crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('rami@innovacx.net',      crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('majid@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('ali@innovacx.net',       crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('yara@innovacx.net',      crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('hana@innovacx.net',      crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  -- Employees (1 per department)
  ('ahmed@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('lena@innovacx.net',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('bilal@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('sameer@innovacx.net',    crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('yousef@innovacx.net',    crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('talya@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('sarah@innovacx.net',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET mfa_enabled = FALSE,
      totp_secret = NULL;


-- Profiles
-- Managers
INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Hamad Alaa', 'MGR-IT01', 'Department Manager',
       (SELECT id FROM departments WHERE name='IT' LIMIT 1)
FROM users u WHERE u.email='hamad@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Leen Naser', 'MGR-HR01', 'Department Manager',
       (SELECT id FROM departments WHERE name='HR' LIMIT 1)
FROM users u WHERE u.email='leen@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Rami Alassi', 'MGR-LC01', 'Department Manager',
       (SELECT id FROM departments WHERE name='Legal & Compliance' LIMIT 1)
FROM users u WHERE u.email='rami@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Majid Sharaf', 'MGR-MN01', 'Department Manager',
       (SELECT id FROM departments WHERE name='Maintenance' LIMIT 1)
FROM users u WHERE u.email='majid@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Ali Al Maharif', 'MGR-SS01', 'Department Manager',
       (SELECT id FROM departments WHERE name='Safety & Security' LIMIT 1)
FROM users u WHERE u.email='ali@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Yara Saab', 'MGR-LS01', 'Department Manager',
       (SELECT id FROM departments WHERE name='Leasing' LIMIT 1)
FROM users u WHERE u.email='yara@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Hana Ayad', 'MGR-FM01', 'Department Manager',
       (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)
FROM users u WHERE u.email='hana@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

-- Employees
INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Ahmed Hassan', 'EMP-IT01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='IT' LIMIT 1)
FROM users u WHERE u.email='ahmed@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Lena Musa', 'EMP-HR01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='HR' LIMIT 1)
FROM users u WHERE u.email='lena@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Bilal Khan', 'EMP-LC01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='Legal & Compliance' LIMIT 1)
FROM users u WHERE u.email='bilal@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Sameer Ahmed', 'EMP-MN01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='Maintenance' LIMIT 1)
FROM users u WHERE u.email='sameer@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Yousef Madi', 'EMP-SS01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='Safety & Security' LIMIT 1)
FROM users u WHERE u.email='yousef@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Talya Mohammad', 'EMP-LS01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='Leasing' LIMIT 1)
FROM users u WHERE u.email='talya@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Sarah Muneer', 'EMP-FM01', 'Support Specialist',
       (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)
FROM users u WHERE u.email='sarah@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

-- Operator profile
INSERT INTO user_profiles (user_id, full_name, job_title)
SELECT u.id, 'System Operator', 'System Operator'
FROM users u WHERE u.email='operator@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

-- Customer profiles
INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer One', '+971500000001', 'Dubai'
FROM users u WHERE u.email='customer1@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer Two', '+971500000002', 'Abu Dhabi'
FROM users u WHERE u.email='customer2@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer Three', '+971500000003', 'Sharjah'
FROM users u WHERE u.email='customer3@innovacx.net'
ON CONFLICT (user_id) DO NOTHING;

-- Tickets (fixed assignments seed)
WITH
  cust    AS (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
  ahmed   AS (SELECT id FROM users WHERE email='ahmed@innovacx.net' LIMIT 1),
  sarah   AS (SELECT id FROM users WHERE email='sarah@innovacx.net' LIMIT 1),
  sameer  AS (SELECT id FROM users WHERE email='sameer@innovacx.net' LIMIT 1),
  bilal   AS (SELECT id FROM users WHERE email='bilal@innovacx.net' LIMIT 1),
  yousef  AS (SELECT id FROM users WHERE email='yousef@innovacx.net' LIMIT 1),
  talya   AS (SELECT id FROM users WHERE email='talya@innovacx.net' LIMIT 1),
  lena    AS (SELECT id FROM users WHERE email='lena@innovacx.net' LIMIT 1),
  facilities  AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1),
  legal       AS (SELECT id FROM departments WHERE name='Legal & Compliance' LIMIT 1),
  safety      AS (SELECT id FROM departments WHERE name='Safety & Security' LIMIT 1),
  hr          AS (SELECT id FROM departments WHERE name='HR' LIMIT 1),
  leasing     AS (SELECT id FROM departments WHERE name='Leasing' LIMIT 1),
  maintenance AS (SELECT id FROM departments WHERE name='Maintenance' LIMIT 1),
  it          AS (SELECT id FROM departments WHERE name='IT' LIMIT 1)

INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, priority, status, department_id,
  created_by_user_id, assigned_to_user_id, created_at,
  respond_due_at, resolve_due_at,
  model_suggestion, model_priority, model_confidence, sentiment_score, sentiment_label
)
VALUES
('CX-1122',
  'Air conditioning not working',
  'AC stopped cooling in office area. Needs urgent repair.',
  'Complaint',
  'Critical',
  'Assigned',
  (SELECT id FROM maintenance),
  (SELECT id FROM cust),
  (SELECT id FROM ahmed),
  to_timestamp('19/11/2025','DD/MM/YYYY'),
  to_timestamp('19/11/2025','DD/MM/YYYY') + interval '30 minutes',
  to_timestamp('19/11/2025','DD/MM/YYYY') + interval '6 hours',
  'Dispatch HVAC technician and check compressor / thermostat; confirm coolant pressure.',
  'Critical',
  92.50,
  -0.450,
  'Negative'),

('CX-3862',
  'Water leakage in pantry',
  'Leakage detected under pantry sink. Water pooling on floor.',
  'Complaint',
  'Critical',
  'Assigned',
  (SELECT id FROM maintenance),
  (SELECT id FROM cust),
  (SELECT id FROM bilal),
  to_timestamp('18/11/2025','DD/MM/YYYY'),
  to_timestamp('18/11/2025','DD/MM/YYYY') + interval '30 minutes',
  to_timestamp('18/11/2025','DD/MM/YYYY') + interval '6 hours',
  'Isolate water source and replace faulty seal / pipe joint; dry area and confirm no further leak.',
  'Critical',
  90.10,
  -0.380,
  'Negative'),

('CX-4587',
  'Wi-Fi connection unstable',
  'Frequent disconnects reported across floor 2.',
  'Inquiry',
  'High',
  'Assigned',
  (SELECT id FROM it),
  (SELECT id FROM cust),
  (SELECT id FROM ahmed),
  to_timestamp('19/11/2025','DD/MM/YYYY'),
  to_timestamp('19/11/2025','DD/MM/YYYY') + interval '1 hour',
  to_timestamp('19/11/2025','DD/MM/YYYY') + interval '18 hours',
  'Check AP logs, channel overlap, and DHCP lease issues; restart controller if needed.',
  'High',
  88.00,
  -0.120,
  'Neutral'),

('CX-4630',
  'Lift stopping between floors',
  'Elevator intermittently stops between floors and reboots.',
  'Complaint',
  'High',
  'Assigned',
  (SELECT id FROM safety),
  (SELECT id FROM cust),
  (SELECT id FROM yousef),
  to_timestamp('18/11/2025','DD/MM/YYYY'),
  to_timestamp('18/11/2025','DD/MM/YYYY') + interval '1 hour',
  to_timestamp('18/11/2025','DD/MM/YYYY') + interval '18 hours',
  'Run elevator diagnostics, inspect door sensors and control panel error logs.',
  'High',
  86.40,
  -0.200,
  'Neutral'),

('CX-4701',
  'Cleaning service missed schedule',
  'Cleaning did not occur on scheduled time.',
  'Complaint',
  'Medium',
  'Open',
  NULL,
  (SELECT id FROM cust),
  NULL,
  to_timestamp('16/11/2025','DD/MM/YYYY'),
  to_timestamp('16/11/2025','DD/MM/YYYY') + interval '3 hours',
  to_timestamp('16/11/2025','DD/MM/YYYY') + interval '2 days',
  'Assign cleaning team; confirm schedule and update customer with ETA.',
  'Medium',
  80.00,
  0.050,
  'Neutral'),

('CX-4725',
  'Parking access card not working',
  'Customer access card fails at gate reader.',
  'Inquiry',
  'Medium',
  'Assigned',
  (SELECT id FROM legal),
  (SELECT id FROM cust),
  (SELECT id FROM sameer),
  to_timestamp('13/11/2025','DD/MM/YYYY'),
  to_timestamp('13/11/2025','DD/MM/YYYY') + interval '3 hours',
  to_timestamp('13/11/2025','DD/MM/YYYY') + interval '2 days',
  'Re-encode card, test reader, and confirm access permissions in system.',
  'Medium',
  82.20,
  -0.050,
  'Neutral'),

('CX-4780',
  'Noise from maintenance works',
  'Noise complaint due to late-hour maintenance.',
  'Complaint',
  'Low',
  'Assigned',
  (SELECT id FROM facilities),
  (SELECT id FROM cust),
  (SELECT id FROM sarah),
  to_timestamp('09/11/2025','DD/MM/YYYY'),
  to_timestamp('09/11/2025','DD/MM/YYYY') + interval '6 hours',
  to_timestamp('09/11/2025','DD/MM/YYYY') + interval '3 days',
  'Coordinate maintenance hours; add noise control measures and notify affected area.',
  'Low',
  76.00,
  0.100,
  'Neutral')
ON CONFLICT (ticket_code) DO NOTHING;

-- ✅ KPI-friendly tickets for Ahmed (FIXED: every row has same number of columns)
WITH
cust  AS (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
ahmed AS (SELECT id FROM users WHERE email='ahmed@innovacx.net' LIMIT 1),
fac   AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)
INSERT INTO tickets (
  ticket_code,
  subject,
  details,
  ticket_type,
  priority,
  status,
  department_id,
  created_by_user_id,
  assigned_to_user_id,
  created_at,
  assigned_at,
  respond_due_at,
  resolve_due_at,
  first_response_at,
  resolved_at,
  final_resolution,
  resolved_by_user_id
) VALUES

-- New Today
('CX-9001','New today test ticket','Seed ticket to populate "New Today".',
 'Complaint','Medium','Assigned',(SELECT id FROM fac),
 (SELECT id FROM cust),(SELECT id FROM ahmed),
 now(), now(),
 now() + interval '1 hour', now() + interval '18 hours',
 NULL, NULL, NULL, NULL),

-- In Progress
('CX-9002','In progress test ticket','Seed ticket to populate "In Progress".',
 'Complaint','High','In Progress',(SELECT id FROM fac),
 (SELECT id FROM cust),(SELECT id FROM ahmed),
 now() - interval '1 day', now() - interval '1 day' + interval '5 minutes',
 now() - interval '1 day' + interval '1 hour', now() + interval '18 hours',
 now() - interval '1 day' + interval '30 minutes', NULL, NULL, NULL),

-- Critical
('CX-9003','Critical test ticket','Seed ticket to populate "Critical".',
 'Complaint','Critical','Assigned',(SELECT id FROM fac),
 (SELECT id FROM cust),(SELECT id FROM ahmed),
 now() - interval '2 days', now() - interval '2 days' + interval '10 minutes',
 now() + interval '30 minutes', now() + interval '6 hours',
 NULL, NULL, NULL, NULL),

-- Overdue
('CX-9004','Overdue test ticket','Seed ticket to populate "Overdue".',
 'Complaint','High','Overdue',(SELECT id FROM fac),
 (SELECT id FROM cust),(SELECT id FROM ahmed),
 now() - interval '5 days', now() - interval '5 days' + interval '10 minutes',
 now() - interval '5 days' + interval '30 minutes', now() - interval '4 days',
 now() - interval '5 days' + interval '25 minutes', NULL, NULL, NULL),

-- Resolved This Month
('CX-9005','Resolved this month test','Seed ticket to populate "Resolved This Month".',
 'Complaint','Medium','Resolved',(SELECT id FROM fac),
 (SELECT id FROM cust),(SELECT id FROM ahmed),
 date_trunc('month', now()) + interval '1 day',
 date_trunc('month', now()) + interval '1 day' + interval '10 minutes',
 date_trunc('month', now()) + interval '1 day' + interval '1 hour',
 date_trunc('month', now()) + interval '3 days',
 date_trunc('month', now()) + interval '1 day' + interval '20 minutes',
 date_trunc('month', now()) + interval '2 days',
 'Resolved during monthly KPI seeding.',
 (SELECT id FROM ahmed))

ON CONFLICT (ticket_code) DO NOTHING;

-- Work steps example
INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, occurred_at, notes)
SELECT t.id, 1, (SELECT id FROM users WHERE email='ahmed@innovacx.net' LIMIT 1),
       t.created_at + interval '20 minutes',
       'Initial inspection completed. Logged error codes and safety checks.'
FROM tickets t WHERE t.ticket_code='CX-4630'
ON CONFLICT (ticket_id, step_no) DO NOTHING;

-- Placeholder tickets required for approvals linkage
INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, department_id, created_by_user_id, created_at)
SELECT 'CX-2011', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3101',
       'Complaint','Medium','Open',
       (SELECT id FROM departments WHERE name='Maintenance' LIMIT 1),
       (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
       to_timestamp('18/11/2025','DD/MM/YYYY')
WHERE NOT EXISTS (SELECT 1 FROM tickets WHERE ticket_code='CX-2011');

INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, department_id, created_by_user_id, created_at)
SELECT 'CX-2034', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3110',
       'Complaint','Medium','Open',
       (SELECT id FROM departments WHERE name='Maintenance' LIMIT 1),
       (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
       to_timestamp('18/11/2025','DD/MM/YYYY')
WHERE NOT EXISTS (SELECT 1 FROM tickets WHERE ticket_code='CX-2034');

INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, department_id, created_by_user_id, created_at)
SELECT 'CX-2078', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3125',
       'Complaint','High','Open',
       (SELECT id FROM departments WHERE name='Safety & Security' LIMIT 1),
       (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
       to_timestamp('17/11/2025','DD/MM/YYYY')
WHERE NOT EXISTS (SELECT 1 FROM tickets WHERE ticket_code='CX-2078');

-- Approvals
INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT
  'REQ-3101', t.id, 'Rescoring',
  'Priority: Medium', 'Priority: Critical',
  'Raised due to increased urgency and impact on operations.',
  (SELECT id FROM users WHERE email='ahmed@innovacx.net' LIMIT 1),
  to_timestamp('18/11/2025 10:22','DD/MM/YYYY HH24:MI'),
  'Pending'
FROM tickets t WHERE t.ticket_code='CX-2011'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT
  'REQ-3110', t.id, 'Rerouting',
  'Dept: Maintenance', 'Dept: Safety & Security',
  'Security review required due to access-control implications.',
  (SELECT id FROM users WHERE email='ahmed@innovacx.net' LIMIT 1),
  to_timestamp('18/11/2025 11:05','DD/MM/YYYY HH24:MI'),
  'Pending'
FROM tickets t WHERE t.ticket_code='CX-2034'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT
  'REQ-3125', t.id, 'Rescoring',
  'Priority: High', 'Priority: Medium',
  'Adjusted after verification reduced the severity classification.',
  (SELECT id FROM users WHERE email='sarah@innovacx.net' LIMIT 1),
  to_timestamp('17/11/2025 15:40','DD/MM/YYYY HH24:MI'),
  'Pending'
FROM tickets t WHERE t.ticket_code='CX-2078'
ON CONFLICT (request_code) DO NOTHING;

-- Operator dashboard seed
INSERT INTO system_service_status (name, status, severity, note)
VALUES
  ('API Gateway', 'Healthy', 'ok', 'Normal latency'),
  ('Chatbot Service', 'Healthy', 'ok', 'No errors detected'),
  ('Database', 'Healthy', 'ok', 'Primary reachable')
ON CONFLICT (name) DO UPDATE
SET status=EXCLUDED.status, severity=EXCLUDED.severity, note=EXCLUDED.note, checked_at=now();

INSERT INTO system_integration_status (name, status, severity, note)
VALUES
  ('Email (SES)', 'Healthy', 'ok', 'Delivery normal'),
  ('Storage (S3)', 'Healthy', 'ok', 'Uploads normal')
ON CONFLICT (name) DO UPDATE
SET status=EXCLUDED.status, severity=EXCLUDED.severity, note=EXCLUDED.note, checked_at=now();

INSERT INTO system_queue_metrics (name, value, severity, note)
VALUES
  ('Ticket Queue', '12', 'ok', 'Normal throughput'),
  ('Escalation Queue', '3', 'warning', 'Slight backlog'),
  ('Notification Queue', '0', 'ok', 'No backlog')
ON CONFLICT (name) DO UPDATE
SET value=EXCLUDED.value, severity=EXCLUDED.severity, note=EXCLUDED.note, measured_at=now();

INSERT INTO system_event_feed (severity, title, description, event_time)
VALUES
  ('info', 'Deployment complete', 'Operator services updated successfully.', now() - interval '2 hours'),
  ('warning', 'Queue backlog', 'Escalation queue slightly above baseline.', now() - interval '45 minutes')
ON CONFLICT DO NOTHING;

INSERT INTO system_versions (component, version, deployed_at)
VALUES
  ('API', 'v1.0.0', '2025-11-24'),
  ('Chatbot', 'v1.0.0', '2025-11-24'),
  ('Model', 'v1.0.0', '2025-11-24')
ON CONFLICT (component) DO UPDATE
SET version=EXCLUDED.version, deployed_at=EXCLUDED.deployed_at;

INSERT INTO system_config_kv (key, value)
VALUES
  ('maintenance_mode', 'false'),
  ('rate_limit', 'enabled')
ON CONFLICT (key) DO UPDATE
SET value=EXCLUDED.value;

-- -------------------------
-- Post-init scripts
-- -------------------------
\ir scripts/ticket_status.sql
\ir scripts/sla.sql
\ir scripts/is_recurring.sql
\ir services/suggested.sql

-- =========================================================
-- Dev/Test safety: ensure ticket assignments match current
-- user UUIDs and MFA is disabled for all seed users.
-- Safe to run on existing volumes (idempotent).
-- =========================================================

-- Re-assign seed tickets to correct employee UUIDs
-- (guards against UUID drift if users were recreated)
UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net' LIMIT 1)
WHERE ticket_code IN ('CX-4630', 'CX-9001', 'CX-9002', 'CX-9003', 'CX-9004', 'CX-9005');

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'sarah@innovacx.net' LIMIT 1)
WHERE ticket_code = 'CX-3862';

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'yousef@innovacx.net' LIMIT 1)
WHERE ticket_code = 'CX-4725';

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'sameer@innovacx.net' LIMIT 1)
WHERE ticket_code = 'CX-4780';

-- Disable MFA for all seed users so login returns a bearer token
-- (not a temporary token) — required for employee actions to work
UPDATE users
SET mfa_enabled = FALSE, totp_secret = NULL
WHERE email IN (
  'customer1@innovacx.net',
  'customer2@innovacx.net',
  'customer3@innovacx.net',
  'operator@innova.cx',
  'hamad@innovacx.net',
  'leen@innovacx.net',
  'rami@innovacx.net',
  'majid@innovacx.net',
  'ali@innovacx.net',
  'yara@innovacx.net',
  'hana@innovacx.net',
  'ahmed@innovacx.net',
  'lena@innovacx.net',
  'bilal@innovacx.net',
  'sameer@innovacx.net',
  'yousef@innovacx.net',
  'talya@innovacx.net',
  'sarah@innovacx.net'
);

-- =========================================================
-- Seed: Employee Monthly Reports for Ahmed Hassan
-- (nov-2025 through jun-2025, 6 months)
-- =========================================================

INSERT INTO employee_reports (report_code, employee_user_id, month_label, subtitle, kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response)
SELECT code, ahmed_id, label, sub, rating, resolved, sla, avg_resp
FROM (
  SELECT
    (SELECT id FROM users WHERE email = 'ahmed@innovacx.net') AS ahmed_id,
    unnest(ARRAY['nov-2025','oct-2025','sep-2025','aug-2025','jul-2025','jun-2025']) AS code,
    unnest(ARRAY['November 2025','October 2025','September 2025','August 2025','July 2025','June 2025']) AS label,
    unnest(ARRAY[
      'Strong performance with high SLA compliance.',
      'Consistent resolution rate across all priorities.',
      'Good month — exceeded SLA targets.',
      'Handled high volume with stable response times.',
      'Solid performance with room for improvement.',
      'Below average month — high ticket volume.'
    ]) AS sub,
    unnest(ARRAY['4.7 / 5','4.5 / 5','4.6 / 5','4.4 / 5','4.3 / 5','4.1 / 5']) AS rating,
    unnest(ARRAY[12, 10, 11, 9, 8, 7]) AS resolved,
    unnest(ARRAY['92%','88%','90%','85%','83%','80%']) AS sla,
    unnest(ARRAY['18 Mins','22 Mins','20 Mins','25 Mins','28 Mins','30 Mins']) AS avg_resp
) sub
ON CONFLICT (report_code) DO NOTHING;

-- Summary items for nov-2025
INSERT INTO employee_report_summary_items (report_id, label, value_text)
SELECT er.id, label, val
FROM employee_reports er,
  (VALUES
    ('Total Assigned','14'), ('Resolved','12'), ('Escalated','1'),
    ('Pending','1'), ('Avg Priority','High'), ('SLA Breaches','1')
  ) AS data(label, val)
WHERE er.report_code = 'nov-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_summary_items si WHERE si.report_id = er.id
  );

-- Summary items for oct-2025
INSERT INTO employee_report_summary_items (report_id, label, value_text)
SELECT er.id, label, val
FROM employee_reports er,
  (VALUES
    ('Total Assigned','12'), ('Resolved','10'), ('Escalated','1'),
    ('Pending','1'), ('Avg Priority','Medium'), ('SLA Breaches','2')
  ) AS data(label, val)
WHERE er.report_code = 'oct-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_summary_items si WHERE si.report_id = er.id
  );

-- Rating components for nov-2025
INSERT INTO employee_report_rating_components (report_id, name, score, pct)
SELECT er.id, name, score, pct
FROM employee_reports er,
  (VALUES
    ('Resolution Rate', 4.8, 96),
    ('SLA Compliance', 4.6, 92),
    ('Response Speed', 4.7, 94),
    ('Customer Satisfaction', 4.5, 90)
  ) AS data(name, score, pct)
WHERE er.report_code = 'nov-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_rating_components rc WHERE rc.report_id = er.id
  );

-- Rating components for oct-2025
INSERT INTO employee_report_rating_components (report_id, name, score, pct)
SELECT er.id, name, score, pct
FROM employee_reports er,
  (VALUES
    ('Resolution Rate', 4.6, 92),
    ('SLA Compliance', 4.4, 88),
    ('Response Speed', 4.5, 90),
    ('Customer Satisfaction', 4.3, 86)
  ) AS data(name, score, pct)
WHERE er.report_code = 'oct-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_rating_components rc WHERE rc.report_id = er.id
  );

-- Weekly breakdown for nov-2025
INSERT INTO employee_report_weekly (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text)
SELECT er.id, wk, asgn, res, s, avg_r, dt, dtxt
FROM employee_reports er,
  (VALUES
    ('Week 1', 4, 4, '100%', '15 Mins', 'positive', '+100%'),
    ('Week 2', 3, 3, '100%', '18 Mins', 'positive', '+0%'),
    ('Week 3', 4, 3, '75%',  '20 Mins', 'negative', '-25%'),
    ('Week 4', 3, 2, '67%',  '22 Mins', 'negative', '-8%')
  ) AS data(wk, asgn, res, s, avg_r, dt, dtxt)
WHERE er.report_code = 'nov-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_weekly ew WHERE ew.report_id = er.id
  );

-- Weekly breakdown for oct-2025
INSERT INTO employee_report_weekly (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text)
SELECT er.id, wk, asgn, res, s, avg_r, dt, dtxt
FROM employee_reports er,
  (VALUES
    ('Week 1', 3, 3, '100%', '20 Mins', 'positive', '+100%'),
    ('Week 2', 3, 2, '67%',  '22 Mins', 'negative', '-33%'),
    ('Week 3', 3, 3, '100%', '19 Mins', 'positive', '+33%'),
    ('Week 4', 3, 2, '67%',  '26 Mins', 'negative', '-33%')
  ) AS data(wk, asgn, res, s, avg_r, dt, dtxt)
WHERE er.report_code = 'oct-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_weekly ew WHERE ew.report_id = er.id
  );

-- Notes for nov-2025
INSERT INTO employee_report_notes (report_id, note)
SELECT er.id, note
FROM employee_reports er,
  (VALUES
    ('Excellent performance on critical tickets — all resolved within SLA.'),
    ('One SLA breach in week 4 due to parts delay — documented.')
  ) AS data(note)
WHERE er.report_code = 'nov-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_notes en WHERE en.report_id = er.id
  );

-- Notes for oct-2025
INSERT INTO employee_report_notes (report_id, note)
SELECT er.id, note
FROM employee_reports er,
  (VALUES
    ('Good consistency across all weeks. Slight drop in week 4.'),
    ('Response time above target — investigate workload balancing.')
  ) AS data(note)
WHERE er.report_code = 'oct-2025'
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_notes en WHERE en.report_id = er.id
  );

-- =========================================================
-- Seed: Notifications for Ahmed (unread + mixed types)
-- =========================================================

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'sla_warning',
  'SLA Warning: CX-9004',
  'Ticket CX-9004 is overdue. Immediate action required.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9004'),
  FALSE,
  now() - interval '2 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
    AND n.title = 'SLA Warning: CX-9004'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'ticket_assignment',
  'Ticket Assigned: CX-9003',
  'You have been assigned ticket CX-9003 — Critical priority.',
  'Critical',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9003'),
  FALSE,
  now() - interval '1 day'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
    AND n.title = 'Ticket Assigned: CX-9003'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'ticket_assignment',
  'Ticket Assigned: CX-9001',
  'You have been assigned a new ticket CX-9001.',
  'Medium',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9001'),
  TRUE,
  now() - interval '12 days'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
    AND n.title = 'Ticket Assigned: CX-9001'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'report_ready',
  'Monthly Report Ready',
  'Your November 2025 performance report is now available.',
  NULL,
  NULL,
  TRUE,
  now() - interval '5 days'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
    AND n.title = 'Monthly Report Ready'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'status_change',
  'Ticket Status Updated: CX-9002',
  'Ticket CX-9002 has been moved to In Progress.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9002'),
  FALSE,
  now() - interval '3 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innovacx.net')
    AND n.title = 'Ticket Status Updated: CX-9002'
);

-- =========================================================
-- Seed: Work steps for CX-9002 (In Progress) and CX-9004 (Overdue)
-- so their ticket detail pages show Steps Taken section
-- =========================================================

INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes, occurred_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9002'),
  1,
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'Initial assessment completed. Issue identified as network switch failure.',
  now() - interval '2 days'
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_work_steps tws
  WHERE tws.ticket_id = (SELECT id FROM tickets WHERE ticket_code = 'CX-9002')
    AND tws.step_no = 1
);

INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes, occurred_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9002'),
  2,
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'Replacement switch ordered. ETA 48 hours. Temporary workaround applied.',
  now() - interval '1 day'
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_work_steps tws
  WHERE tws.ticket_id = (SELECT id FROM tickets WHERE ticket_code = 'CX-9002')
    AND tws.step_no = 2
);

INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes, occurred_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9004'),
  1,
  (SELECT id FROM users WHERE email = 'ahmed@innovacx.net'),
  'Ticket overdue. Escalation attempt made — awaiting supervisor response.',
  now() - interval '5 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_work_steps tws
  WHERE tws.ticket_id = (SELECT id FROM tickets WHERE ticket_code = 'CX-9004')
    AND tws.step_no = 1
);

-- =========================================================
-- ANALYTICS SEED DATA
-- Covers the full 12-month window (Mar 2025 → Feb 2026)
-- across all 8 employees, 4 departments, all priorities.
-- Provides live data for Section A, B, and C analytics.
-- =========================================================

WITH
  cust   AS (SELECT id FROM users WHERE email='customer1@innovacx.net' LIMIT 1),
  ahmed  AS (SELECT id FROM users WHERE email='ahmed@innovacx.net'    LIMIT 1),
  sarah  AS (SELECT id FROM users WHERE email='sarah@innovacx.net'    LIMIT 1),
  yousef AS (SELECT id FROM users WHERE email='yousef@innovacx.net'   LIMIT 1),
  sameer AS (SELECT id FROM users WHERE email='sameer@innovacx.net'   LIMIT 1),
  bilal  AS (SELECT id FROM users WHERE email='bilal@innovacx.net'    LIMIT 1),
  lena   AS (SELECT id FROM users WHERE email='lena@innovacx.net'     LIMIT 1),
  talya  AS (SELECT id FROM users WHERE email='talya@innovacx.net'    LIMIT 1),
  fac   AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1),
  it    AS (SELECT id FROM departments WHERE name='IT' LIMIT 1),
  sec   AS (SELECT id FROM departments WHERE name='Safety & Security' LIMIT 1),
  cln   AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)

INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, priority, status,
  department_id, created_by_user_id, assigned_to_user_id,
  created_at, assigned_at, first_response_at, resolved_at,
  respond_due_at, resolve_due_at,
  respond_breached, resolve_breached,
  model_priority, model_confidence,
  final_resolution, resolved_by_user_id
) VALUES

-- ═══════════════════════════════════
-- MARCH 2025
-- ═══════════════════════════════════
('CX-M01','HVAC unit failure in Block A','Complete breakdown of HVAC unit. Office temperature unmanageable.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-03-05 08:00:00+00','2025-03-05 08:15:00+00','2025-03-05 08:28:00+00','2025-03-05 14:00:00+00',
 '2025-03-05 08:30:00+00','2025-03-05 14:00:00+00',
 FALSE,FALSE,
 'Critical',91.0,'Replaced compressor unit and recharged refrigerant.',(SELECT id FROM ahmed)),

('CX-M02','Water leak from ceiling pipe','Dripping water causing damage to office equipment.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sarah),
 '2025-03-08 09:00:00+00','2025-03-08 09:20:00+00','2025-03-08 09:55:00+00','2025-03-09 16:00:00+00',
 '2025-03-08 10:00:00+00','2025-03-10 09:00:00+00',
 FALSE,FALSE,
 'High',87.0,'Pipe joint sealed and ceiling panel replaced.',(SELECT id FROM sarah)),

('CX-M03','Security camera offline – Gate 3','Camera at Gate 3 showing no signal since yesterday.',
 'Complaint','High','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-03-12 10:00:00+00','2025-03-12 10:30:00+00','2025-03-12 11:10:00+00','2025-03-13 12:00:00+00',
 '2025-03-12 11:00:00+00','2025-03-14 10:00:00+00',
 TRUE,FALSE,
 'Medium',72.0,'Camera NVR cable replaced and feed restored.',(SELECT id FROM bilal)),

('CX-M04','Cleaning missed – Floor 4 restrooms','Restrooms not cleaned for two consecutive days.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-03-15 07:30:00+00','2025-03-15 08:00:00+00','2025-03-15 10:00:00+00','2025-03-16 08:00:00+00',
 '2025-03-15 10:30:00+00','2025-03-17 07:30:00+00',
 FALSE,FALSE,
 'Medium',80.0,'Cleaning team rescheduled and area deep-cleaned.',(SELECT id FROM sameer)),

('CX-M05','IT printer network error inquiry','Network printer unavailable from multiple workstations.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-03-20 11:00:00+00','2025-03-20 11:15:00+00','2025-03-20 13:00:00+00','2025-03-21 09:00:00+00',
 '2025-03-20 14:00:00+00','2025-03-22 11:00:00+00',
 FALSE,FALSE,
 'Low',65.0,'Printer IP reassigned and driver reinstalled on affected PCs.',(SELECT id FROM ahmed)),

-- ═══════════════════════════════════
-- APRIL 2025
-- ═══════════════════════════════════
('CX-M06','Electrical fault – Lab corridor','Repeated circuit breaker tripping in lab wing.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-04-03 07:00:00+00','2025-04-03 07:10:00+00','2025-04-03 07:38:00+00','2025-04-03 18:00:00+00',
 '2025-04-03 07:30:00+00','2025-04-03 19:00:00+00',
 TRUE,FALSE,
 'Critical',94.0,'Faulty socket replaced and wiring inspected.',(SELECT id FROM sameer)),

('CX-M07','Pest sighting – Canteen area','Rodent droppings found near food preparation area.',
 'Complaint','High','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-04-07 06:00:00+00','2025-04-07 06:30:00+00','2025-04-07 07:15:00+00','2025-04-08 12:00:00+00',
 '2025-04-07 07:00:00+00','2025-04-09 06:00:00+00',
 TRUE,FALSE,
 'Medium',78.0,'Pest control treatment applied and entry points sealed.',(SELECT id FROM sameer)),

('CX-M08','Access card readers not registering','Multiple employees unable to badge into west wing.',
 'Complaint','High','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-04-11 08:00:00+00','2025-04-11 08:20:00+00','2025-04-11 09:00:00+00','2025-04-12 10:00:00+00',
 '2025-04-11 09:00:00+00','2025-04-13 08:00:00+00',
 FALSE,FALSE,
 'High',88.0,'Reader firmware updated and badge database re-synced.',(SELECT id FROM bilal)),

('CX-M09','Elevator B out of service','Elevator B in Building 2 stuck on floor 3.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-04-15 09:00:00+00','2025-04-15 09:05:00+00','2025-04-15 09:29:00+00','2025-04-15 16:00:00+00',
 '2025-04-15 09:30:00+00','2025-04-15 15:00:00+00',
 FALSE,FALSE,
 'Critical',93.0,'Door sensor replaced and control board reset.',(SELECT id FROM yousef)),

('CX-M10','Wi-Fi dead zone – Conference rooms','No connectivity in rooms 3A through 3D.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-04-22 10:00:00+00','2025-04-22 10:30:00+00','2025-04-22 13:00:00+00','2025-04-23 11:00:00+00',
 '2025-04-22 13:00:00+00','2025-04-24 10:00:00+00',
 FALSE,FALSE,
 'Medium',82.0,'New access point installed; signal verified across all rooms.',(SELECT id FROM ahmed)),

-- ═══════════════════════════════════
-- MAY 2025
-- ═══════════════════════════════════
('CX-M11','Flooding – basement car park','Heavy rain caused water ingress, risk to vehicles.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-05-02 06:00:00+00','2025-05-02 06:08:00+00','2025-05-02 06:25:00+00','2025-05-02 14:00:00+00',
 '2025-05-02 06:30:00+00','2025-05-02 12:00:00+00',
 FALSE,FALSE,
 'Critical',95.0,'Pumping crew deployed; drainage channel cleared.',(SELECT id FROM ahmed)),

('CX-M12','Broken window – 2nd floor east','Window pane cracked and posing safety risk.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-05-09 08:30:00+00','2025-05-09 09:00:00+00','2025-05-09 10:00:00+00','2025-05-10 14:00:00+00',
 '2025-05-09 09:30:00+00','2025-05-11 08:30:00+00',
 FALSE,FALSE,
 'High',86.0,'Pane replaced and frame sealed.',(SELECT id FROM yousef)),

('CX-M13','CCTV footage request – parking incident','Customer requests footage of parking incident.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-05-14 11:00:00+00','2025-05-14 11:30:00+00','2025-05-14 14:00:00+00','2025-05-15 12:00:00+00',
 '2025-05-14 14:00:00+00','2025-05-16 11:00:00+00',
 FALSE,FALSE,
 'Low',68.0,'Footage reviewed and relevant clip shared with customer.',(SELECT id FROM yousef)),

('CX-M14','Cleaning chemicals smell – Floor 3','Strong chemical odour from cleaning product use.',
 'Complaint','Low','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-05-19 07:00:00+00','2025-05-19 09:00:00+00','2025-05-19 15:00:00+00','2025-05-20 08:00:00+00',
 '2025-05-19 13:00:00+00','2025-05-22 07:00:00+00',
 TRUE,FALSE,
 'Low',74.0,'Switched to low-odour products and improved ventilation during cleaning.',(SELECT id FROM sameer)),

('CX-M15','Server room overheating alert','Temperature in server room exceeded 28°C threshold.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-05-27 14:00:00+00','2025-05-27 14:05:00+00','2025-05-27 14:28:00+00','2025-05-27 20:00:00+00',
 '2025-05-27 14:30:00+00','2025-05-27 20:00:00+00',
 FALSE,FALSE,
 'Critical',96.0,'Backup cooling unit activated; primary unit serviced.',(SELECT id FROM ahmed)),

-- ═══════════════════════════════════
-- JUNE 2025
-- ═══════════════════════════════════
('CX-M16','Generator fuel low – Building C','Standby generator at 12% fuel capacity.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-06-04 07:00:00+00','2025-06-04 07:20:00+00','2025-06-04 08:00:00+00','2025-06-04 15:00:00+00',
 '2025-06-04 08:00:00+00','2025-06-06 07:00:00+00',
 FALSE,FALSE,
 'High',89.0,'Fuel topped up and weekly check schedule reinstated.',(SELECT id FROM sameer)),

('CX-M17','Visitor management system down','Visitor kiosks in lobby not accepting registrations.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-06-10 09:00:00+00','2025-06-10 09:30:00+00','2025-06-10 11:00:00+00','2025-06-11 10:00:00+00',
 '2025-06-10 12:00:00+00','2025-06-12 09:00:00+00',
 FALSE,FALSE,
 'Low',71.0,'Software service restarted and kiosk connectivity confirmed.',(SELECT id FROM ahmed)),

('CX-M18','Fire exit blocked – east stairwell','Fire exit door propped open and partially blocked.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-06-16 08:00:00+00','2025-06-16 08:05:00+00','2025-06-16 08:27:00+00','2025-06-16 12:00:00+00',
 '2025-06-16 08:30:00+00','2025-06-16 14:00:00+00',
 FALSE,FALSE,
 'Critical',97.0,'Obstruction removed and door alarm reset.',(SELECT id FROM bilal)),

('CX-M19','Cleaning frequency insufficient – lobby','Lobby floor dirty by mid-morning daily.',
 'Complaint','Low','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-06-23 08:00:00+00','2025-06-23 10:00:00+00','2025-06-23 15:00:00+00','2025-06-24 09:00:00+00',
 '2025-06-23 14:00:00+00','2025-06-26 08:00:00+00',
 TRUE,FALSE,
 'Medium',69.0,'Cleaning frequency increased to 3x daily for lobby.',(SELECT id FROM sameer)),

-- ═══════════════════════════════════
-- JULY 2025
-- ═══════════════════════════════════
('CX-M20','Air handling unit vibration – Roof','Loud vibration from AHU on rooftop.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-07-03 07:00:00+00','2025-07-03 07:30:00+00','2025-07-03 08:20:00+00','2025-07-04 16:00:00+00',
 '2025-07-03 08:00:00+00','2025-07-05 07:00:00+00',
 TRUE,FALSE,
 'High',83.0,'Loose mounting bolts tightened and fan blade balanced.',(SELECT id FROM ahmed)),

('CX-M21','Badge printing station broken','HR badge printer not functioning.',
 'Inquiry','Low','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-07-08 10:00:00+00','2025-07-08 10:30:00+00','2025-07-08 16:00:00+00','2025-07-09 11:00:00+00',
 '2025-07-08 16:00:00+00','2025-07-11 10:00:00+00',
 FALSE,FALSE,
 'Low',70.0,'Printer driver updated and cartridge replaced.',(SELECT id FROM ahmed)),

('CX-M22','Security guard post unmanned','Main gate security post left unmanned for 90 minutes.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-07-14 06:00:00+00','2025-07-14 06:10:00+00','2025-07-14 06:28:00+00','2025-07-14 10:00:00+00',
 '2025-07-14 06:30:00+00','2025-07-14 12:00:00+00',
 FALSE,FALSE,
 'Critical',95.0,'Relief guard deployed; roster updated to prevent gaps.',(SELECT id FROM yousef)),

('CX-M23','Mould on ceiling – Meeting Room 7','Visible mould patch spreading on ceiling tiles.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-07-21 09:00:00+00','2025-07-21 09:30:00+00','2025-07-21 10:30:00+00','2025-07-22 15:00:00+00',
 '2025-07-21 10:00:00+00','2025-07-23 09:00:00+00',
 FALSE,FALSE,
 'Medium',76.0,'Affected tiles replaced and source leak repaired.',(SELECT id FROM yousef)),

-- ═══════════════════════════════════
-- AUGUST 2025
-- ═══════════════════════════════════
('CX-M24','Blocked drainage – outdoor plaza','Plaza drains backing up after rain.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-08-05 08:00:00+00','2025-08-05 08:30:00+00','2025-08-05 11:00:00+00','2025-08-06 10:00:00+00',
 '2025-08-05 11:00:00+00','2025-08-07 08:00:00+00',
 FALSE,FALSE,
 'Medium',81.0,'Drainage cleared of debris; grating repaired.',(SELECT id FROM sameer)),

('CX-M25','CCTV system error – all cameras','All cameras showing "signal lost" on monitoring screen.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-08-12 07:00:00+00','2025-08-12 07:08:00+00','2025-08-12 07:26:00+00','2025-08-12 13:00:00+00',
 '2025-08-12 07:30:00+00','2025-08-12 13:00:00+00',
 FALSE,FALSE,
 'Critical',98.0,'NVR hard drive replaced; all feeds restored.',(SELECT id FROM bilal)),

('CX-M26','Cleaning robot stuck – atrium','Autonomous floor cleaning robot stuck and blocking pathway.',
 'Complaint','Low','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-08-19 11:00:00+00','2025-08-19 11:30:00+00','2025-08-19 16:00:00+00','2025-08-20 09:00:00+00',
 '2025-08-19 17:00:00+00','2025-08-22 11:00:00+00',
 FALSE,FALSE,
 'Low',66.0,'Robot repositioned and obstacle sensors recalibrated.',(SELECT id FROM sameer)),

('CX-M27','Power outage – Finance floor','Complete power failure affecting Finance department.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-08-26 13:00:00+00','2025-08-26 13:04:00+00','2025-08-26 13:28:00+00','2025-08-26 18:00:00+00',
 '2025-08-26 13:30:00+00','2025-08-26 19:00:00+00',
 FALSE,FALSE,
 'Critical',96.0,'Tripped MCB reset; UPS bypass engaged for continuity.',(SELECT id FROM ahmed)),

-- ═══════════════════════════════════
-- SEPTEMBER 2025
-- ═══════════════════════════════════
('CX-M28','Roof waterproofing breach','Rainwater seeping through roof membrane into top-floor offices.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-09-04 08:00:00+00','2025-09-04 08:30:00+00','2025-09-04 09:30:00+00','2025-09-05 17:00:00+00',
 '2025-09-04 09:00:00+00','2025-09-06 08:00:00+00',
 TRUE,FALSE,
 'High',84.0,'Membrane patch applied; area monitored for 48 hours.',(SELECT id FROM yousef)),

('CX-M29','Security alarm false triggers','Motion sensors triggering alarm at 3 AM daily.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-09-11 07:00:00+00','2025-09-11 07:30:00+00','2025-09-11 10:00:00+00','2025-09-12 12:00:00+00',
 '2025-09-11 10:00:00+00','2025-09-13 07:00:00+00',
 FALSE,FALSE,
 'Medium',79.0,'Sensor sensitivity adjusted; false triggers eliminated.',(SELECT id FROM yousef)),

('CX-M30','Hot water failure – staff showers','No hot water in staff shower block.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-09-18 06:00:00+00','2025-09-18 06:20:00+00','2025-09-18 07:10:00+00','2025-09-18 16:00:00+00',
 '2025-09-18 07:00:00+00','2025-09-20 06:00:00+00',
 FALSE,FALSE,
 'High',88.0,'Heating element replaced in main boiler.',(SELECT id FROM sameer)),

-- ═══════════════════════════════════
-- OCTOBER 2025
-- ═══════════════════════════════════
('CX-M31','Chiller plant failure','Building-wide cooling failure due to chiller breakdown.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-10-02 08:00:00+00','2025-10-02 08:05:00+00','2025-10-02 08:27:00+00','2025-10-02 20:00:00+00',
 '2025-10-02 08:30:00+00','2025-10-02 20:00:00+00',
 FALSE,FALSE,
 'Critical',97.0,'Compressor replaced and refrigerant recharged.',(SELECT id FROM ahmed)),

('CX-M32','Fingerprint scanner malfunction – Gate 1','Biometric reader rejecting valid fingerprints.',
 'Complaint','High','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-10-08 09:00:00+00','2025-10-08 09:25:00+00','2025-10-08 10:20:00+00','2025-10-09 11:00:00+00',
 '2025-10-08 10:00:00+00','2025-10-10 09:00:00+00',
 TRUE,FALSE,
 'Medium',75.0,'Scanner firmware updated and fingerprint templates re-enrolled.',(SELECT id FROM bilal)),

('CX-M33','Pest control needed – archives room','Evidence of insects in document archives.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-10-14 08:00:00+00','2025-10-14 09:00:00+00','2025-10-14 13:00:00+00','2025-10-15 10:00:00+00',
 '2025-10-14 11:00:00+00','2025-10-16 08:00:00+00',
 TRUE,FALSE,
 'Low',72.0,'Fumigation completed and sealing applied to entry points.',(SELECT id FROM sameer)),

('CX-M34','Network switch failure – Floor 5','20 workstations offline due to switch failure.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-10-20 07:00:00+00','2025-10-20 07:10:00+00','2025-10-20 07:28:00+00','2025-10-20 14:00:00+00',
 '2025-10-20 07:30:00+00','2025-10-20 13:00:00+00',
 FALSE,FALSE,
 'Critical',95.0,'Switch replaced and all connections verified.',(SELECT id FROM ahmed)),

('CX-M35','Broken handrail – staircase B','Handrail detached from wall, safety hazard.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-10-27 09:30:00+00','2025-10-27 10:00:00+00','2025-10-27 11:00:00+00','2025-10-28 14:00:00+00',
 '2025-10-27 10:30:00+00','2025-10-29 09:30:00+00',
 FALSE,FALSE,
 'High',85.0,'Handrail re-secured with heavy-duty anchors.',(SELECT id FROM yousef)),

-- ═══════════════════════════════════
-- NOVEMBER 2025
-- ═══════════════════════════════════
('CX-M36','Gas leak alarm triggered – Kitchen','Gas leak sensor alarm in building kitchen area.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-11-03 06:00:00+00','2025-11-03 06:03:00+00','2025-11-03 06:25:00+00','2025-11-03 11:00:00+00',
 '2025-11-03 06:30:00+00','2025-11-03 12:00:00+00',
 FALSE,FALSE,
 'Critical',99.0,'Gas supply isolated; faulty valve replaced and area cleared.',(SELECT id FROM ahmed)),

('CX-M37','Parking sensor errors – Level 2','Parking guidance sensors showing wrong availability.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-11-07 10:00:00+00','2025-11-07 10:30:00+00','2025-11-07 13:00:00+00','2025-11-08 11:00:00+00',
 '2025-11-07 13:00:00+00','2025-11-09 10:00:00+00',
 FALSE,FALSE,
 'Low',67.0,'Sensor calibration reset; display updated.',(SELECT id FROM ahmed)),

('CX-M38','Intruder alert – Roof access','Motion detected on restricted rooftop area after hours.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-11-12 23:00:00+00','2025-11-12 23:04:00+00','2025-11-12 23:26:00+00','2025-11-13 04:00:00+00',
 '2025-11-12 23:30:00+00','2025-11-13 05:00:00+00',
 FALSE,FALSE,
 'Critical',98.0,'Area secured; access logs reviewed and door lock replaced.',(SELECT id FROM yousef)),

('CX-M39','Carpet replacement needed – exec floor','Worn and stained carpet posing slip risk.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2025-11-17 09:00:00+00','2025-11-17 10:00:00+00','2025-11-17 13:00:00+00','2025-11-19 15:00:00+00',
 '2025-11-17 12:00:00+00','2025-11-20 09:00:00+00',
 FALSE,FALSE,
 'Medium',80.0,'Carpet replaced on full exec floor.',(SELECT id FROM yousef)),

('CX-M40','VoIP system crackling noise','Voice calls experiencing noise and drop-outs.',
 'Inquiry','Medium','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-11-24 11:00:00+00','2025-11-24 11:20:00+00','2025-11-24 14:00:00+00','2025-11-25 10:00:00+00',
 '2025-11-24 14:00:00+00','2025-11-26 11:00:00+00',
 FALSE,FALSE,
 'Low',70.0,'QoS settings updated; noise eliminated after router firmware patch.',(SELECT id FROM ahmed)),

-- ═══════════════════════════════════
-- DECEMBER 2025
-- ═══════════════════════════════════
('CX-M41','Boiler failure – Building A heating','Entire building without heating during cold snap.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-12-03 07:00:00+00','2025-12-03 07:05:00+00','2025-12-03 07:28:00+00','2025-12-03 17:00:00+00',
 '2025-12-03 07:30:00+00','2025-12-03 19:00:00+00',
 FALSE,FALSE,
 'Critical',97.0,'Heat exchanger replaced; pressure restored.',(SELECT id FROM ahmed)),

('CX-M42','Slippery floor after mopping','Cleaning crew left floor wet without wet-floor signs.',
 'Complaint','High','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-12-08 08:30:00+00','2025-12-08 09:00:00+00','2025-12-08 10:00:00+00','2025-12-09 09:00:00+00',
 '2025-12-08 09:30:00+00','2025-12-10 08:30:00+00',
 TRUE,FALSE,
 'Medium',76.0,'Crew briefed; wet-floor sign protocol enforced.',(SELECT id FROM sameer)),

('CX-M43','Perimeter fence damage','Section of perimeter fence knocked over.',
 'Complaint','High','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2025-12-12 07:30:00+00','2025-12-12 08:00:00+00','2025-12-12 09:00:00+00','2025-12-13 15:00:00+00',
 '2025-12-12 08:30:00+00','2025-12-14 07:30:00+00',
 FALSE,FALSE,
 'High',87.0,'Fence section repaired and post re-anchored in concrete.',(SELECT id FROM bilal)),

('CX-M44','Server backup failure – weekly job','Automated backup job failing silently.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2025-12-17 09:00:00+00','2025-12-17 09:06:00+00','2025-12-17 09:27:00+00','2025-12-17 16:00:00+00',
 '2025-12-17 09:30:00+00','2025-12-17 18:00:00+00',
 FALSE,FALSE,
 'Critical',94.0,'Backup agent reinstalled; job verified and alerting enabled.',(SELECT id FROM ahmed)),

('CX-M45','Staircase light outages – Block B','Emergency lighting not functioning in stairwells.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2025-12-22 07:00:00+00','2025-12-22 07:25:00+00','2025-12-22 08:00:00+00','2025-12-23 11:00:00+00',
 '2025-12-22 08:00:00+00','2025-12-24 07:00:00+00',
 FALSE,FALSE,
 'High',89.0,'Faulty LED drivers replaced; emergency battery backup tested.',(SELECT id FROM sameer)),

-- ═══════════════════════════════════
-- JANUARY 2026
-- ═══════════════════════════════════
('CX-M46','Fire suppression system test failure','Annual suppression test failed in server room.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2026-01-06 08:00:00+00','2026-01-06 08:04:00+00','2026-01-06 08:28:00+00','2026-01-06 18:00:00+00',
 '2026-01-06 08:30:00+00','2026-01-06 20:00:00+00',
 FALSE,FALSE,
 'Critical',98.0,'Suppression head replaced; system retested and certified.',(SELECT id FROM ahmed)),

('CX-M47','VPN access issues – remote staff','Remote employees unable to connect to internal VPN.',
 'Inquiry','High','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2026-01-10 09:00:00+00','2026-01-10 09:20:00+00','2026-01-10 10:00:00+00','2026-01-11 10:00:00+00',
 '2026-01-10 10:00:00+00','2026-01-12 09:00:00+00',
 FALSE,FALSE,
 'Medium',78.0,'VPN gateway certificate renewed and routing tables updated.',(SELECT id FROM ahmed)),

('CX-M48','Unauthorised vehicle in restricted bay','Unknown vehicle parked in reserved emergency access bay.',
 'Complaint','High','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-01-15 07:30:00+00','2026-01-15 07:45:00+00','2026-01-15 08:40:00+00','2026-01-15 11:00:00+00',
 '2026-01-15 08:30:00+00','2026-01-17 07:30:00+00',
 TRUE,FALSE,
 'High',83.0,'Vehicle removed; signage reinforced and patrol frequency increased.',(SELECT id FROM yousef)),

('CX-M49','Deep clean request – storage area','Storage area showing mould and debris build-up.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2026-01-20 08:00:00+00','2026-01-20 09:00:00+00','2026-01-20 13:00:00+00','2026-01-21 12:00:00+00',
 '2026-01-20 11:00:00+00','2026-01-23 08:00:00+00',
 FALSE,FALSE,
 'Medium',79.0,'Full deep-clean completed; anti-mould treatment applied.',(SELECT id FROM sameer)),

('CX-M50','Lightning conductor inspection overdue','Annual inspection certificate expired for roof conductor.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-01-27 09:00:00+00','2026-01-27 09:30:00+00','2026-01-27 10:30:00+00','2026-01-28 15:00:00+00',
 '2026-01-27 10:00:00+00','2026-01-29 09:00:00+00',
 FALSE,FALSE,
 'High',88.0,'Inspection completed; conductor tested and new certificate issued.',(SELECT id FROM yousef)),

-- ═══════════════════════════════════
-- FEBRUARY 2026
-- ═══════════════════════════════════
('CX-M51','Electrical trip – main distribution board','Main DB tripped cutting power to two floors.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2026-02-03 07:00:00+00','2026-02-03 07:06:00+00','2026-02-03 07:27:00+00','2026-02-03 14:00:00+00',
 '2026-02-03 07:30:00+00','2026-02-03 15:00:00+00',
 FALSE,FALSE,
 'Critical',96.0,'Faulty MCB replaced; load redistributed across circuits.',(SELECT id FROM sameer)),

('CX-M52','Lift maintenance overdue – Building D','Lift certificate lapsed; unable to operate.',
 'Complaint','High','Resolved',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-02-07 08:00:00+00','2026-02-07 08:30:00+00','2026-02-07 09:30:00+00','2026-02-08 12:00:00+00',
 '2026-02-07 09:00:00+00','2026-02-09 08:00:00+00',
 FALSE,FALSE,
 'High',90.0,'Maintenance completed; certificate renewed and lift returned to service.',(SELECT id FROM yousef)),

('CX-M53','Smoke detector false alarm – lab','Smoke detector activating without fire.',
 'Complaint','Medium','Resolved',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2026-02-12 10:00:00+00','2026-02-12 10:20:00+00','2026-02-12 11:00:00+00','2026-02-13 10:00:00+00',
 '2026-02-12 11:00:00+00','2026-02-14 10:00:00+00',
 FALSE,FALSE,
 'Medium',81.0,'Detector head replaced; sensitivity recalibrated.',(SELECT id FROM bilal)),

('CX-M54','Cleaning schedule complaint – Ramadan hours','Schedule not adjusted for Ramadan shift change.',
 'Complaint','Low','Resolved',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2026-02-17 07:00:00+00','2026-02-17 09:00:00+00','2026-02-17 15:00:00+00','2026-02-18 09:00:00+00',
 '2026-02-17 13:00:00+00','2026-02-20 07:00:00+00',
 TRUE,FALSE,
 'Low',68.0,'Schedule updated to reflect Ramadan timings.',(SELECT id FROM sameer)),

('CX-M55','Data centre UPS battery replacement','UPS batteries below minimum capacity threshold.',
 'Complaint','Critical','Resolved',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2026-02-22 09:00:00+00','2026-02-22 09:05:00+00','2026-02-22 09:28:00+00','2026-02-23 16:00:00+00',
 '2026-02-22 09:30:00+00','2026-02-22 21:00:00+00',
 FALSE,FALSE,
 'Critical',97.0,'All UPS battery modules replaced; runtime tested and certified.',(SELECT id FROM ahmed))

ON CONFLICT (ticket_code) DO NOTHING;

-- =========================================================
-- SUGGESTED RESOLUTION USAGE SEED
-- Provides data for Section C: AI acceptance rate analytics
-- decision: 'accepted' = employee accepted AI suggestion
--           'declined_custom' = employee wrote their own resolution
-- =========================================================
INSERT INTO suggested_resolution_usage (
  ticket_id, employee_user_id, decision, department,
  suggested_text, final_text, used
)
SELECT t.id, u.id, fb.decision, d.name, fb.suggested, fb.final, (fb.decision = 'accepted')
FROM (VALUES
  -- Ahmed: high acceptance rate (good AI alignment)
  ('CX-M01', 'ahmed@innovacx.net',  'accepted',         'Dispatch HVAC and check compressor.', NULL, 'Replaced compressor unit and recharged refrigerant.'),
  ('CX-M11', 'ahmed@innovacx.net',  'accepted',         'Deploy pumping crew.', NULL, 'Pumping crew deployed; drainage channel cleared.'),
  ('CX-M15', 'ahmed@innovacx.net',  'accepted',         'Activate backup cooling.', NULL, 'Backup cooling unit activated; primary unit serviced.'),
  ('CX-M27', 'ahmed@innovacx.net',  'accepted',         'Reset tripped MCB.', NULL, 'Tripped MCB reset; UPS bypass engaged for continuity.'),
  ('CX-M31', 'ahmed@innovacx.net',  'accepted',         'Replace compressor.', NULL, 'Compressor replaced and refrigerant recharged.'),
  ('CX-M36', 'ahmed@innovacx.net',  'accepted',         'Isolate gas and replace valve.', NULL, 'Gas supply isolated; faulty valve replaced.'),
  ('CX-M41', 'ahmed@innovacx.net',  'accepted',         'Replace heat exchanger.', NULL, 'Heat exchanger replaced; pressure restored.'),
  ('CX-M46', 'ahmed@innovacx.net',  'accepted',         'Replace suppression head and retest.', NULL, 'Suppression head replaced; system retested.'),
  ('CX-M55', 'ahmed@innovacx.net',  'declined_custom',  'Recharge batteries.', 'Full battery module replacement required — recharge insufficient.', 'All UPS battery modules replaced; runtime tested.'),

  -- Maria: moderate acceptance
  ('CX-M02', 'sarah@innovacx.net',  'accepted',         'Seal pipe joint and replace panel.', NULL, 'Pipe joint sealed and ceiling panel replaced.'),

  -- Fatima: lower acceptance (often modifies AI suggestions)
  ('CX-M05', 'ahmed@innovacx.net', 'declined_custom',  'Reinstall printer driver.', 'Driver reinstall insufficient — IP conflict root cause.', 'Printer IP reassigned and driver reinstalled.'),
  ('CX-M10', 'ahmed@innovacx.net', 'accepted',         'Install new access point.', NULL, 'New access point installed; signal verified.'),
  ('CX-M17', 'ahmed@innovacx.net', 'declined_custom',  'Restart kiosk service.', 'Restart did not resolve — full software re-deploy needed.', 'Software service restarted and kiosk connectivity confirmed.'),
  ('CX-M21', 'ahmed@innovacx.net', 'accepted',         'Update printer driver.', NULL, 'Printer driver updated and cartridge replaced.'),
  ('CX-M34', 'ahmed@innovacx.net', 'accepted',         'Replace failed switch.', NULL, 'Switch replaced and all connections verified.'),
  ('CX-M37', 'ahmed@innovacx.net', 'declined_custom',  'Recalibrate sensors.', 'Sensor model needed full reset not just recalibration.', 'Sensor calibration reset; display updated.'),
  ('CX-M40', 'ahmed@innovacx.net', 'accepted',         'Update QoS settings.', NULL, 'QoS settings updated; noise eliminated.'),
  ('CX-M44', 'ahmed@innovacx.net', 'accepted',         'Reinstall backup agent.', NULL, 'Backup agent reinstalled; job verified.'),
  ('CX-M47', 'ahmed@innovacx.net', 'declined_custom',  'Reset VPN gateway.', 'Gateway certificate renewal needed — reset alone insufficient.', 'VPN gateway certificate renewed and routing updated.'),

  -- Omar: moderate
  ('CX-M13', 'yousef@innovacx.net',   'accepted',         'Review and share CCTV footage.', NULL, 'Footage reviewed and relevant clip shared.'),
  ('CX-M22', 'yousef@innovacx.net',   'accepted',         'Deploy relief guard and update roster.', NULL, 'Relief guard deployed; roster updated.'),
  ('CX-M29', 'yousef@innovacx.net',   'accepted',         'Adjust sensor sensitivity.', NULL, 'Sensor sensitivity adjusted; false triggers eliminated.'),
  ('CX-M38', 'yousef@innovacx.net',   'accepted',         'Secure area and review logs.', NULL, 'Area secured; access logs reviewed.'),
  ('CX-M48', 'yousef@innovacx.net',   'declined_custom',  'Issue warning notice.', 'Vehicle needed removal not just notice — contacted security supervisor.', 'Vehicle removed; signage reinforced.'),

  -- Sara: lower acceptance
  ('CX-M04', 'sameer@innovacx.net',   'declined_custom',  'Reschedule cleaning team.', 'Root cause was staff absence — needed replacement team dispatch.', 'Cleaning team rescheduled and area deep-cleaned.'),
  ('CX-M07', 'sameer@innovacx.net',   'accepted',         'Apply pest control treatment.', NULL, 'Pest control treatment applied and entry points sealed.'),
  ('CX-M14', 'sameer@innovacx.net',   'accepted',         'Switch to low-odour products.', NULL, 'Switched to low-odour products and improved ventilation.'),
  ('CX-M19', 'sameer@innovacx.net',   'declined_custom',  'Increase cleaning frequency.', 'Frequency alone insufficient — need dedicated lobby morning crew.', 'Cleaning frequency increased to 3x daily for lobby.'),
  ('CX-M26', 'sameer@innovacx.net',   'accepted',         'Reposition robot and recalibrate sensors.', NULL, 'Robot repositioned and obstacle sensors recalibrated.'),
  ('CX-M33', 'sameer@innovacx.net',   'accepted',         'Apply fumigation.', NULL, 'Fumigation completed and sealing applied.'),
  ('CX-M42', 'sameer@innovacx.net',   'declined_custom',  'Place wet-floor signs.', 'Signs alone not enough — required protocol retraining for crew.', 'Crew briefed; wet-floor sign protocol enforced.'),
  ('CX-M49', 'sameer@innovacx.net',   'accepted',         'Deep clean and apply anti-mould treatment.', NULL, 'Full deep-clean completed; anti-mould treatment applied.'),
  ('CX-M54', 'sameer@innovacx.net',   'accepted',         'Update cleaning schedule for Ramadan.', NULL, 'Schedule updated to reflect Ramadan timings.'),

  -- Bilal: high acceptance
  ('CX-M03', 'bilal@innovacx.net',  'accepted',         'Replace NVR cable.', NULL, 'Camera NVR cable replaced and feed restored.'),
  ('CX-M08', 'bilal@innovacx.net',  'accepted',         'Update firmware and re-sync badges.', NULL, 'Reader firmware updated and badge database re-synced.'),
  ('CX-M18', 'bilal@innovacx.net',  'accepted',         'Remove obstruction and reset door alarm.', NULL, 'Obstruction removed and door alarm reset.'),
  ('CX-M25', 'bilal@innovacx.net',  'accepted',         'Replace NVR drive.', NULL, 'NVR hard drive replaced; all feeds restored.'),
  ('CX-M32', 'bilal@innovacx.net',  'declined_custom',  'Update scanner firmware.', 'Firmware update insufficient — full template re-enrol required.', 'Scanner firmware updated and fingerprint templates re-enrolled.'),
  ('CX-M43', 'bilal@innovacx.net',  'accepted',         'Repair fence section.', NULL, 'Fence section repaired and post re-anchored.'),
  ('CX-M53', 'bilal@innovacx.net',  'accepted',         'Replace detector head.', NULL, 'Detector head replaced; sensitivity recalibrated.'),

  -- Yousef
  ('CX-M12', 'yousef@innovacx.net', 'accepted',         'Replace window pane.', NULL, 'Pane replaced and frame sealed.'),
  ('CX-M23', 'yousef@innovacx.net', 'declined_custom',  'Remove mould tiles.', 'Source leak must be fixed first — tile replacement secondary.', 'Affected tiles replaced and source leak repaired.'),
  ('CX-M28', 'yousef@innovacx.net', 'accepted',         'Apply membrane patch.', NULL, 'Membrane patch applied; area monitored for 48 hours.'),
  ('CX-M35', 'yousef@innovacx.net', 'accepted',         'Re-secure handrail.', NULL, 'Handrail re-secured with heavy-duty anchors.'),
  ('CX-M39', 'yousef@innovacx.net', 'accepted',         'Replace carpet.', NULL, 'Carpet replaced on full exec floor.'),
  ('CX-M50', 'yousef@innovacx.net', 'accepted',         'Complete lightning conductor inspection.', NULL, 'Inspection completed; new certificate issued.'),
  ('CX-M52', 'yousef@innovacx.net', 'accepted',         'Complete maintenance and renew certificate.', NULL, 'Maintenance completed; certificate renewed.'),

  -- Khalid
  ('CX-M06', 'sameer@innovacx.net', 'accepted',         'Replace faulty socket and inspect wiring.', NULL, 'Faulty socket replaced and wiring inspected.'),
  ('CX-M09', 'yousef@innovacx.net', 'accepted',         'Replace door sensor.', NULL, 'Door sensor replaced and control board reset.'),
  ('CX-M16', 'sameer@innovacx.net', 'accepted',         'Top up fuel.', NULL, 'Fuel topped up and weekly check schedule reinstated.'),
  ('CX-M24', 'sameer@innovacx.net', 'accepted',         'Clear drainage and repair grating.', NULL, 'Drainage cleared of debris; grating repaired.'),
  ('CX-M30', 'sameer@innovacx.net', 'declined_custom',  'Check thermostat.', 'Thermostat fine — heating element replacement needed.', 'Heating element replaced in main boiler.'),
  ('CX-M45', 'sameer@innovacx.net', 'accepted',         'Replace LED drivers.', NULL, 'Faulty LED drivers replaced; emergency battery backup tested.'),
  ('CX-M51', 'sameer@innovacx.net', 'accepted',         'Replace faulty MCB.', NULL, 'Faulty MCB replaced; load redistributed.')
) AS fb(ticket_code, emp_email, decision, suggested, custom, final)
JOIN tickets t ON t.ticket_code = fb.ticket_code
JOIN users u ON u.email = fb.emp_email
LEFT JOIN departments d ON d.id = t.department_id
WHERE NOT EXISTS (
  SELECT 1 FROM suggested_resolution_usage sru
  WHERE sru.ticket_id = t.id
    AND sru.employee_user_id = u.id
    AND sru.decision = fb.decision
    AND sru.final_text = fb.final
);


-- =========================================================
-- EXTENDED SEED DATA
-- Populates:
--   • Approvals page — more Pending/Approved/Rejected requests
--   • Manager Notifications — escalations, SLA breaches, approvals
--   • Employee Notifications — all 6 types across all employees
--   • Active open/in-progress tickets for the complaints list
--   • March 2026 tickets so the current month has live data
-- Every INSERT uses ON CONFLICT / WHERE NOT EXISTS so re-runs
-- are fully safe (idempotent).
-- =========================================================

-- ─────────────────────────────────────────────────────────
-- 1. MORE APPROVAL REQUESTS
--    Mix of Pending, Approved, Rejected across employees/tickets
-- ─────────────────────────────────────────────────────────

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3140', t.id, 'Rescoring',
  'Priority: Low', 'Priority: High',
  'Customer escalated complaint — noise is now affecting three floors.',
  (SELECT id FROM users WHERE email='bilal@innovacx.net'),
  '2026-02-10 09:15:00+00', 'Pending'
FROM tickets t WHERE t.ticket_code='CX-4780'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3145', t.id, 'Rerouting',
  'Dept: IT', 'Dept: Maintenance',
  'Root cause is physical cabling, not software — needs Maintenance team.',
  (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  '2026-02-12 11:30:00+00', 'Approved'
FROM tickets t WHERE t.ticket_code='CX-4587'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3150', t.id, 'Rescoring',
  'Priority: Medium', 'Priority: Critical',
  'Lift stopping mid-floor is a safety hazard — needs immediate escalation.',
  (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  '2026-02-14 08:00:00+00', 'Approved'
FROM tickets t WHERE t.ticket_code='CX-4630'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3155', t.id, 'Rerouting',
  'Dept: Legal & Compliance', 'Dept: IT',
  'Parking access card issue is a system/software problem — needs IT.',
  (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  '2026-02-16 14:20:00+00', 'Rejected'
FROM tickets t WHERE t.ticket_code='CX-4725'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3160', t.id, 'Rescoring',
  'Priority: Critical', 'Priority: High',
  'Issue resolved partially — residual risk is High not Critical.',
  (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  '2026-02-20 10:45:00+00', 'Pending'
FROM tickets t WHERE t.ticket_code='CX-M51'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3165', t.id, 'Rerouting',
  'Dept: Safety & Security', 'Dept: Facilities Management',
  'Structural issue confirmed — requires Facilities Management, not Security.',
  (SELECT id FROM users WHERE email='bilal@innovacx.net'),
  '2026-02-25 13:10:00+00', 'Pending'
FROM tickets t WHERE t.ticket_code='CX-M53'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3170', t.id, 'Rescoring',
  'Priority: High', 'Priority: Critical',
  'Lift fully out of service — affects all 6 floors, requires emergency repair.',
  (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  '2026-02-27 07:30:00+00', 'Pending'
FROM tickets t WHERE t.ticket_code='CX-M52'
ON CONFLICT (request_code) DO NOTHING;

INSERT INTO approval_requests (
  request_code, ticket_id, request_type, current_value, requested_value,
  request_reason, submitted_by_user_id, submitted_at, status
)
SELECT 'REQ-3175', t.id, 'Rescoring',
  'Priority: Medium', 'Priority: High',
  'Cleaning backlog causing hygiene concerns on 3 floors.',
  (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  '2026-02-28 09:00:00+00', 'Rejected'
FROM tickets t WHERE t.ticket_code='CX-M54'
ON CONFLICT (request_code) DO NOTHING;

-- ─────────────────────────────────────────────────────────
-- 2. MARCH 2026 OPEN/IN-PROGRESS TICKETS
--    These give the complaints list live active data and
--    populate the manager dashboard KPIs (Open, In Progress)
-- ─────────────────────────────────────────────────────────

WITH
  cust   AS (SELECT id FROM users WHERE email='customer1@innovacx.net'  LIMIT 1),
  ahmed  AS (SELECT id FROM users WHERE email='ahmed@innovacx.net'      LIMIT 1),
  yousef AS (SELECT id FROM users WHERE email='yousef@innovacx.net'     LIMIT 1),
  bilal  AS (SELECT id FROM users WHERE email='bilal@innovacx.net'      LIMIT 1),
  sameer AS (SELECT id FROM users WHERE email='sameer@innovacx.net'     LIMIT 1),
  sarah  AS (SELECT id FROM users WHERE email='sarah@innovacx.net'      LIMIT 1),
  fac    AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1),
  it     AS (SELECT id FROM departments WHERE name='IT'                    LIMIT 1),
  sec    AS (SELECT id FROM departments WHERE name='Safety & Security'     LIMIT 1),
  cln    AS (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)

INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, priority, status,
  department_id, created_by_user_id, assigned_to_user_id,
  created_at, assigned_at, first_response_at,
  respond_due_at, resolve_due_at,
  respond_breached, resolve_breached,
  model_priority, model_confidence,
  priority_assigned_at,
  model_suggestion, sentiment_score, sentiment_label
) VALUES

('CX-R01','AC unit failure – Server Room','Server room AC unit offline. Ambient temp rising above 28°C.',
 'Complaint','Critical','In Progress',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2026-03-01 06:30:00+00','2026-03-01 06:35:00+00','2026-03-01 06:52:00+00',
 '2026-03-01 07:00:00+00','2026-03-01 12:30:00+00',
 FALSE,FALSE,'Critical',96.0,
 '2026-03-01 06:30:00+00',
 'Activate backup cooling and dispatch HVAC technician immediately.',
 -0.72,'Negative'),

('CX-R02','Water ingress – Ground floor lobby','Heavy rain causing water ingress through lobby entrance.',
 'Complaint','High','Assigned',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-03-01 07:15:00+00','2026-03-01 07:25:00+00','2026-03-01 07:48:00+00',
 '2026-03-01 08:15:00+00','2026-03-01 19:15:00+00',
 FALSE,FALSE,'High',88.0,
 '2026-03-01 07:15:00+00',
 'Deploy water barriers and arrange waterproofing inspection.',
 -0.45,'Negative'),

('CX-R03','CCTV blind spot – Carpark Level 1','Three cameras offline covering entire Level 1 south section.',
 'Complaint','High','Assigned',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM bilal),
 '2026-03-01 08:00:00+00','2026-03-01 08:10:00+00','2026-03-01 08:35:00+00',
 '2026-03-01 09:00:00+00','2026-03-01 20:00:00+00',
 FALSE,FALSE,'High',87.0,
 '2026-03-01 08:00:00+00',
 'Replace camera NVR connections and verify feed restoration.',
 -0.38,'Negative'),

('CX-R04','Printer network error – Floor 3','All 4 network printers on Floor 3 unreachable since morning.',
 'Inquiry','Medium','In Progress',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM ahmed),
 '2026-03-01 08:30:00+00','2026-03-01 08:45:00+00','2026-03-01 09:10:00+00',
 '2026-03-01 11:30:00+00','2026-03-02 08:30:00+00',
 FALSE,FALSE,'Medium',82.0,
 '2026-03-01 08:30:00+00',
 'Check print server and reassign IP addresses for affected printers.',
 -0.18,'Neutral'),

('CX-R05','Restroom cleaning missed – Block C','Block C restrooms not cleaned for two days. Hygiene concern.',
 'Complaint','Medium','Assigned',
 (SELECT id FROM cln),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2026-03-01 09:00:00+00','2026-03-01 09:15:00+00','2026-03-01 09:40:00+00',
 '2026-03-01 12:00:00+00','2026-03-03 09:00:00+00',
 FALSE,FALSE,'Medium',79.0,
 '2026-03-01 09:00:00+00',
 'Dispatch cleaning team immediately and update schedule.',
 -0.30,'Negative'),

('CX-R06','Access control fault – Gate 2','Badge readers at Gate 2 rejecting all valid cards since 08:00.',
 'Complaint','Critical','In Progress',
 (SELECT id FROM sec),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-03-01 09:30:00+00','2026-03-01 09:33:00+00','2026-03-01 09:55:00+00',
 '2026-03-01 10:00:00+00','2026-03-01 15:30:00+00',
 FALSE,FALSE,'Critical',94.0,
 '2026-03-01 09:30:00+00',
 'Reset access control server and re-sync badge database.',
 -0.60,'Negative'),

('CX-R07','Lift alarm triggered – Building B','Lift alarm sounding intermittently. Passengers refusing to use.',
 'Complaint','High','Assigned',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sameer),
 '2026-03-01 10:00:00+00','2026-03-01 10:08:00+00','2026-03-01 10:30:00+00',
 '2026-03-01 11:00:00+00','2026-03-01 22:00:00+00',
 FALSE,FALSE,'High',90.0,
 '2026-03-01 10:00:00+00',
 'Run lift diagnostics and inspect alarm sensor wiring.',
 -0.42,'Negative'),

('CX-R08','Slow Wi-Fi – Conference Rooms','Severe packet loss in all 4 conference rooms during peak hours.',
 'Inquiry','Medium','Assigned',
 (SELECT id FROM it),(SELECT id FROM cust),(SELECT id FROM sarah),
 '2026-03-01 10:30:00+00','2026-03-01 10:45:00+00','2026-03-01 11:05:00+00',
 '2026-03-01 13:30:00+00','2026-03-02 10:30:00+00',
 FALSE,FALSE,'Medium',80.0,
 '2026-03-01 10:30:00+00',
 'Check AP channel overlap and conference room bandwidth allocation.',
 -0.15,'Neutral'),

('CX-R09','Broken window – Meeting Room 5B','Window frame cracked and cannot close properly. Wind and dust entering.',
 'Complaint','Low','Assigned',
 (SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM yousef),
 '2026-03-01 11:00:00+00','2026-03-01 11:20:00+00','2026-03-01 11:50:00+00',
 '2026-03-01 17:00:00+00','2026-03-04 11:00:00+00',
 FALSE,FALSE,'Low',74.0,
 '2026-03-01 11:00:00+00',
 'Secure frame temporarily and order replacement window.',
 -0.10,'Neutral'),

('CX-R10','Unassigned parking space dispute','Customer reporting their reserved bay is consistently occupied.',
 'Complaint','Low','Open',
 (SELECT id FROM sec),(SELECT id FROM cust),NULL,
 '2026-03-01 11:30:00+00',NULL,NULL,
 '2026-03-01 17:30:00+00','2026-03-04 11:30:00+00',
 FALSE,FALSE,'Medium',71.0,
 '2026-03-01 11:30:00+00',
 'Review CCTV footage of parking bay and issue formal notice.',
 -0.20,'Neutral')

ON CONFLICT (ticket_code) DO NOTHING;

-- ─────────────────────────────────────────────────────────
-- 3. MANAGER NOTIFICATIONS
--    Covers: pending approvals, SLA breaches, escalations
--    Uses tickets from both historical and March 2026 data
-- ─────────────────────────────────────────────────────────

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'ticket_assignment',
  'Approval Requested — Rescoring CX-4780',
  'Bilal Khan requested a priority change from Low to High on ticket CX-4780.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code='CX-4780'),
  FALSE,
  '2026-02-10 09:15:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='Approval Requested — Rescoring CX-4780'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'sla_warning',
  'SLA Breached — CX-4725',
  'Ticket CX-4725 (Parking access card) has exceeded its resolution SLA. Overdue by 3 days.',
  'Medium',
  (SELECT id FROM tickets WHERE ticket_code='CX-4725'),
  FALSE,
  '2026-02-15 08:00:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='SLA Breached — CX-4725'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'status_change',
  'Ticket Escalated — CX-4587',
  'Ticket CX-4587 (Wi-Fi connection unstable) has been escalated and requires your attention.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code='CX-4587'),
  FALSE,
  '2026-02-18 11:30:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='Ticket Escalated — CX-4587'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'ticket_assignment',
  'Approval Requested — Rerouting CX-M53',
  'Bilal Khan requested rerouting of CX-M53 from Security to Facilities department.',
  'Medium',
  (SELECT id FROM tickets WHERE ticket_code='CX-M53'),
  FALSE,
  '2026-02-25 13:10:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='Approval Requested — Rerouting CX-M53'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'sla_warning',
  'SLA Warning — CX-R01',
  'Critical ticket CX-R01 (AC unit failure – Server Room) is approaching its resolve SLA deadline.',
  'Critical',
  (SELECT id FROM tickets WHERE ticket_code='CX-R01'),
  FALSE,
  '2026-03-01 11:00:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='SLA Warning — CX-R01'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'status_change',
  'Ticket Escalated — CX-R06',
  'Ticket CX-R06 (Access control fault – Gate 2) has been escalated. Multiple employees affected.',
  'Critical',
  (SELECT id FROM tickets WHERE ticket_code='CX-R06'),
  FALSE,
  '2026-03-01 10:30:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='Ticket Escalated — CX-R06'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'ticket_assignment',
  'Approval Requested — Rescoring CX-M52',
  'Yousef Karim requested priority change from High to Critical on CX-M52 (Lift maintenance overdue).',
  'High',
  (SELECT id FROM tickets WHERE ticket_code='CX-M52'),
  TRUE,
  '2026-02-27 07:30:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='Approval Requested — Rescoring CX-M52'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  'sla_warning',
  'SLA Breached — CX-1122',
  'Ticket CX-1122 (Air conditioning not working) is unassigned and has breached response SLA.',
  'Critical',
  (SELECT id FROM tickets WHERE ticket_code='CX-1122'),
  TRUE,
  '2026-02-05 09:00:00+00'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='hamad@innovacx.net')
    AND title='SLA Breached — CX-1122'
);

-- ─────────────────────────────────────────────────────────
-- 4. EMPLOYEE NOTIFICATIONS
--    All 6 types: ticket_assignment, sla_warning, status_change,
--    customer_reply, report_ready, system
--    Spread across: ahmed, maria, omar, sara, bilal, fatima, yousef, khalid
-- ─────────────────────────────────────────────────────────

-- Ahmed
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R01',
  'You have been assigned CX-R01 — AC unit failure in Server Room. Critical priority.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-R01'),FALSE,'2026-03-01 06:35:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='New Ticket Assigned: CX-R01');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'sla_warning','SLA Warning: CX-R01',
  'CX-R01 is approaching its resolve deadline in 1 hour. Take action immediately.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-R01'),FALSE,'2026-03-01 11:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='SLA Warning: CX-R01');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'customer_reply','Customer replied on CX-M55',
  'Customer confirmed UPS battery replacement resolved the issue. Awaiting formal close.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-M55'),TRUE,'2026-02-24 14:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='Customer replied on CX-M55');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'report_ready','February 2026 Report Ready',
  'Your performance report for February 2026 has been generated and is ready to view.',
  NULL,NULL,FALSE,'2026-03-01 06:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='February 2026 Report Ready');

-- Maria
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sarah@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R08',
  'You have been assigned CX-R08 — Slow Wi-Fi in Conference Rooms. Medium priority.',
  'Medium',(SELECT id FROM tickets WHERE ticket_code='CX-R08'),FALSE,'2026-03-01 10:45:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sarah@innovacx.net') AND title='New Ticket Assigned: CX-R08');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sarah@innovacx.net'),
  'status_change','CX-3862 Status Updated',
  'Ticket CX-3862 (Water leakage in pantry) has been marked Overdue by the system.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-3862'),TRUE,'2026-02-20 08:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sarah@innovacx.net') AND title='CX-3862 Status Updated');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sarah@innovacx.net'),
  'report_ready','February 2026 Report Ready',
  'Your performance report for February 2026 is now available.',
  NULL,NULL,FALSE,'2026-03-01 06:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sarah@innovacx.net') AND title='February 2026 Report Ready');

-- Omar
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R06',
  'You have been assigned CX-R06 — Access control fault at Gate 2. Critical priority.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-R06'),FALSE,'2026-03-01 09:33:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='New Ticket Assigned: CX-R06');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'sla_warning','SLA Warning: CX-R06',
  'CX-R06 resolve deadline is in 5 hours. Multiple staff blocked at Gate 2.',
  'Critical',(SELECT id FROM tickets WHERE ticket_code='CX-R06'),FALSE,'2026-03-01 10:30:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='SLA Warning: CX-R06');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'system','Scheduled Maintenance Window',
  'System maintenance is scheduled for tonight 11 PM – 2 AM. No disruption to active tickets.',
  NULL,NULL,TRUE,'2026-02-28 16:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='Scheduled Maintenance Window');

-- Sara
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R05',
  'You have been assigned CX-R05 — Restroom cleaning missed in Block C. Medium priority.',
  'Medium',(SELECT id FROM tickets WHERE ticket_code='CX-R05'),FALSE,'2026-03-01 09:15:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='New Ticket Assigned: CX-R05');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'customer_reply','Customer replied on CX-M54',
  'Customer confirmed cleaning schedule has been updated. Satisfied with resolution.',
  'Low',(SELECT id FROM tickets WHERE ticket_code='CX-M54'),TRUE,'2026-02-19 10:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='Customer replied on CX-M54');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'report_ready','February 2026 Report Ready',
  'Your performance report for February 2026 is now available.',
  NULL,NULL,FALSE,'2026-03-01 06:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='February 2026 Report Ready');

-- Bilal
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='bilal@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R03',
  'You have been assigned CX-R03 — CCTV blind spot in Carpark Level 1. High priority.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-R03'),FALSE,'2026-03-01 08:10:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='bilal@innovacx.net') AND title='New Ticket Assigned: CX-R03');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='bilal@innovacx.net'),
  'status_change','Approval Decision: REQ-3140',
  'Your rescoring request REQ-3140 for CX-4780 is pending manager review.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-4780'),FALSE,'2026-02-10 09:30:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='bilal@innovacx.net') AND title='Approval Decision: REQ-3140');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='bilal@innovacx.net'),
  'system','Password Policy Update',
  'Your password will expire in 14 days. Please update it via Settings.',
  NULL,NULL,FALSE,'2026-02-26 09:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='bilal@innovacx.net') AND title='Password Policy Update');

-- Fatima
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R04',
  'You have been assigned CX-R04 — Printer network error on Floor 3. Medium priority.',
  'Medium',(SELECT id FROM tickets WHERE ticket_code='CX-R04'),FALSE,'2026-03-01 08:45:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='New Ticket Assigned: CX-R04');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'customer_reply','Customer replied on CX-M47',
  'Customer confirmed VPN access is restored. Requesting formal ticket closure.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-M47'),TRUE,'2026-01-12 11:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='Customer replied on CX-M47');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='ahmed@innovacx.net'),
  'report_ready','February 2026 Report Ready',
  'Your performance report for February 2026 is now available.',
  NULL,NULL,FALSE,'2026-03-01 06:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='ahmed@innovacx.net') AND title='February 2026 Report Ready');

-- Yousef
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R02',
  'You have been assigned CX-R02 — Water ingress in Ground floor lobby. High priority.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-R02'),FALSE,'2026-03-01 07:25:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='New Ticket Assigned: CX-R02');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R09',
  'You have been assigned CX-R09 — Broken window in Meeting Room 5B. Low priority.',
  'Low',(SELECT id FROM tickets WHERE ticket_code='CX-R09'),FALSE,'2026-03-01 11:20:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='New Ticket Assigned: CX-R09');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='yousef@innovacx.net'),
  'status_change','Approval Decision: REQ-3170',
  'Your rescoring request REQ-3170 for CX-M52 is pending manager review.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-M52'),FALSE,'2026-02-27 08:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='yousef@innovacx.net') AND title='Approval Decision: REQ-3170');

-- Khalid
INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'ticket_assignment','New Ticket Assigned: CX-R07',
  'You have been assigned CX-R07 — Lift alarm triggered in Building B. High priority.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-R07'),FALSE,'2026-03-01 10:08:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='New Ticket Assigned: CX-R07');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'sla_warning','SLA Warning: CX-R07',
  'CX-R07 response is due in 30 minutes. Lift alarm still active.',
  'High',(SELECT id FROM tickets WHERE ticket_code='CX-R07'),FALSE,'2026-03-01 10:30:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='SLA Warning: CX-R07');

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT (SELECT id FROM users WHERE email='sameer@innovacx.net'),
  'system','System Update Completed',
  'The InnovaCX platform was updated to v2.4.1. New features available — check the changelog.',
  NULL,NULL,TRUE,'2026-02-28 06:00:00+00'
WHERE NOT EXISTS (SELECT 1 FROM notifications WHERE user_id=(SELECT id FROM users WHERE email='sameer@innovacx.net') AND title='System Update Completed');

-- ─────────────────────────────────────────────────────────────────────────────
-- FINAL BACKFILL: set priority_assigned_at = created_at for any historical
-- tickets inserted above that didn't include priority_assigned_at.
-- This must run AFTER all INSERT blocks so it catches every seeded row.
-- Without this, mv_ticket_base computes negative response_time_mins because:
--   response_time_mins = first_response_at - priority_assigned_at
-- and priority_assigned_at ends up NULL → falls back to created_at which
-- may be after first_response_at for some seed timestamps.
-- ─────────────────────────────────────────────────────────────────────────────
UPDATE tickets
SET priority_assigned_at = created_at
WHERE priority_assigned_at IS NULL;

-- Recalculate response_time fields that were stored as NULL or negative
-- due to missing priority_assigned_at at insert time.
-- Force-trigger SLA recomputation by touching updated_at on affected rows.
UPDATE tickets
SET updated_at = now()
WHERE priority_assigned_at IS NOT NULL
  AND first_response_at IS NOT NULL
  AND first_response_at < priority_assigned_at;

-- =============================================================================
-- InnovaCX — Extended Seed Inserts
-- Covers: model_execution_log, all agent output tables, sentiment/priority/
--         routing/sla/resolution/feature outputs, chat_conversations,
--         chat_messages, sessions, user_chat_logs, bot_response_logs,
--         ticket_attachments, ticket_updates, ticket_work_steps,
--         system_event_feed additions, password_reset_tokens,
--         employee_reports for remaining employees, approval decisions.
--
-- Pre-requisites: base init.sql must have already run (users, departments,
--                 tickets CX-R01…CX-R10 and CX-M01…CX-M55 must exist).
--
-- Safe to re-run: all statements use ON CONFLICT / WHERE NOT EXISTS.
-- =============================================================================

-- NOTE: ML pipeline seed data (model_execution_log, sentiment_outputs,
-- priority_outputs, routing_outputs, sla_outputs, resolution_outputs,
-- feature_outputs) moved to zzz_seedV2.sql, which runs after
-- zzz_analytics_mvs.sh creates those tables.

-- ---------------------------------------------------------------------------
-- 8. CHAT CONVERSATIONS & MESSAGES
--    3 conversations: one resolved→ticket, one escalated, one bot-only
-- ---------------------------------------------------------------------------

-- Conv 1: Customer → Bot → Escalated to Operator → Linked to CX-R01
INSERT INTO public.chat_conversations (id, customer_user_id, channel, created_at, ended_at, status)
SELECT
  '11111111-1111-1111-1111-000000000001'::uuid,
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  'web',
  '2026-03-01 06:20:00+00',
  '2026-03-01 06:35:00+00',
  'closed'
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_conversations WHERE id='11111111-1111-1111-1111-000000000001'::uuid
);

INSERT INTO public.chat_messages (conversation_id, sender_type, sender_user_id, message_text, created_at, intent, category, sentiment_score, escalation_flag, linked_ticket_id)
SELECT
  '11111111-1111-1111-1111-000000000001'::uuid,
  msg.sender_type::chat_sender_type,
  CASE msg.email WHEN 'bot' THEN NULL ELSE (SELECT id FROM users WHERE email=msg.email) END,
  msg.body, msg.ts::timestamptz, msg.intent, msg.category, msg.score, msg.escalate,
  CASE WHEN msg.link_ticket IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code=msg.link_ticket) ELSE NULL END
FROM (VALUES
  ('customer','customer1@innovacx.net','2026-03-01 06:20:30+00','The server room AC is completely down and temperature is rising fast!',
   'report_issue','HVAC',-0.75,FALSE,NULL),
  ('bot','bot','2026-03-01 06:20:45+00','I understand. This sounds urgent. Can you confirm your building and floor?',
   'collect_info','HVAC', 0.10,FALSE,NULL),
  ('customer','customer1@innovacx.net','2026-03-01 06:21:10+00','Building A, server room on ground floor. Temperature is at 30°C already.',
   'provide_info','HVAC',-0.80,TRUE,NULL),
  ('operator','operator@innova.cx','2026-03-01 06:25:00+00','I am creating a Critical ticket now and dispatching the HVAC team immediately.',
   'resolution','HVAC', 0.20,FALSE,'CX-R01')
) AS msg(sender_type, email, ts, body, intent, category, score, escalate, link_ticket)
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_messages cm
  WHERE cm.conversation_id='11111111-1111-1111-1111-000000000001'::uuid
  LIMIT 1
);

-- Conv 2: Customer inquiry → Resolved by bot (no escalation)
INSERT INTO public.chat_conversations (id, customer_user_id, channel, created_at, ended_at, status)
SELECT
  '22222222-2222-2222-2222-000000000002'::uuid,
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  'web',
  '2026-02-28 10:00:00+00',
  '2026-02-28 10:08:00+00',
  'closed'
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_conversations WHERE id='22222222-2222-2222-2222-000000000002'::uuid
);

INSERT INTO public.chat_messages (conversation_id, sender_type, sender_user_id, message_text, created_at, intent, category, sentiment_score, escalation_flag)
SELECT
  '22222222-2222-2222-2222-000000000002'::uuid,
  msg.sender_type::chat_sender_type,
  CASE msg.email WHEN 'bot' THEN NULL ELSE (SELECT id FROM users WHERE email=msg.email) END,
  msg.body, msg.ts::timestamptz, msg.intent, msg.category, msg.score, FALSE
FROM (VALUES
  ('customer','customer1@innovacx.net','2026-02-28 10:00:20+00','What are the support hours for facilities management?',
   'inquiry','General',0.10),
  ('bot','bot','2026-02-28 10:00:35+00','Facilities Management is available 24/7 for critical issues and 7 AM – 10 PM for standard requests.',
   'answer','General',0.50),
  ('customer','customer1@innovacx.net','2026-02-28 10:01:00+00','Great, thank you!',
   'close','General',0.80)
) AS msg(sender_type, email, ts, body, intent, category, score)
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_messages cm
  WHERE cm.conversation_id='22222222-2222-2222-2222-000000000002'::uuid
  LIMIT 1
);

-- Conv 3: Security escalation → Linked to CX-R06
INSERT INTO public.chat_conversations (id, customer_user_id, channel, created_at, ended_at, status)
SELECT
  '33333333-3333-3333-3333-000000000003'::uuid,
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  'mobile',
  '2026-03-01 09:25:00+00',
  '2026-03-01 09:40:00+00',
  'closed'
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_conversations WHERE id='33333333-3333-3333-3333-000000000003'::uuid
);

INSERT INTO public.chat_messages (conversation_id, sender_type, sender_user_id, message_text, created_at, intent, category, sentiment_score, escalation_flag, linked_ticket_id)
SELECT
  '33333333-3333-3333-3333-000000000003'::uuid,
  msg.sender_type::chat_sender_type,
  CASE msg.email WHEN 'bot' THEN NULL ELSE (SELECT id FROM users WHERE email=msg.email) END,
  msg.body, msg.ts::timestamptz, msg.intent, msg.category, msg.score, msg.escalate,
  CASE WHEN msg.link_ticket IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code=msg.link_ticket) ELSE NULL END
FROM (VALUES
  ('customer','customer1@innovacx.net','2026-03-01 09:25:10+00','None of the badge readers at Gate 2 are working. My whole team is stuck outside!',
   'report_issue','Access Control',-0.85,FALSE,NULL),
  ('bot','bot','2026-03-01 09:25:25+00',$msg$I'm escalating this to an operator immediately given the severity.$msg$,
   'escalate','Access Control',0.05,TRUE,NULL),
  ('operator','operator@innova.cx','2026-03-01 09:30:00+00','Ticket CX-R06 raised as Critical. Omar Ali is on his way to Gate 2 now.',
   'resolution','Access Control',0.30,FALSE,'CX-R06')
) AS msg(sender_type, email, ts, body, intent, category, score, escalate, link_ticket)
WHERE NOT EXISTS (
  SELECT 1 FROM public.chat_messages cm
  WHERE cm.conversation_id='33333333-3333-3333-3333-000000000003'::uuid
  LIMIT 1
);

-- ---------------------------------------------------------------------------
-- 9. SESSIONS (chatbot state machine entries)
-- ---------------------------------------------------------------------------

INSERT INTO public.sessions (
  user_id, current_state, context, history,
  created_at, updated_at, bot_model_version,
  escalated_to_human, escalated_at, linked_ticket_id
)
SELECT
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  'resolved',
  '{"last_intent":"report_issue","asset":"HVAC","building":"A","floor":"Ground"}'::jsonb,
  '[{"role":"user","msg":"AC down in server room"},{"role":"bot","msg":"Ticket raised"},{"role":"operator","msg":"Team dispatched"}]'::jsonb,
  '2026-03-01 06:20:00+00',
  '2026-03-01 06:35:00+00',
  'chatbot-v2.1',
  TRUE,
  '2026-03-01 06:23:00+00',
  (SELECT id FROM tickets WHERE ticket_code='CX-R01')
WHERE NOT EXISTS (
  SELECT 1 FROM public.sessions s
  WHERE s.user_id=(SELECT id FROM users WHERE email='customer1@innovacx.net')
    AND s.created_at='2026-03-01 06:20:00+00'
);

INSERT INTO public.sessions (
  user_id, current_state, context, history,
  created_at, updated_at, bot_model_version,
  escalated_to_human, escalated_at, linked_ticket_id
)
SELECT
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  'resolved',
  '{"last_intent":"inquiry","topic":"support_hours"}'::jsonb,
  '[{"role":"user","msg":"Support hours?"},{"role":"bot","msg":"24/7 for critical"}]'::jsonb,
  '2026-02-28 10:00:00+00',
  '2026-02-28 10:08:00+00',
  'chatbot-v2.1',
  FALSE, NULL, NULL
WHERE NOT EXISTS (
  SELECT 1 FROM public.sessions s
  WHERE s.user_id=(SELECT id FROM users WHERE email='customer1@innovacx.net')
    AND s.created_at='2026-02-28 10:00:00+00'
);

-- ---------------------------------------------------------------------------
-- 10. USER CHAT LOGS  (flagged aggression + normal entries)
-- ---------------------------------------------------------------------------

INSERT INTO public.user_chat_logs (
  user_id, message, intent_detected,
  aggression_flag, aggression_score, created_at,
  sentiment_score, category, response_time_ms, ticket_id
)
SELECT
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  v.msg, v.intent, v.agg_flag, v.agg_score, v.ts::timestamptz,
  v.sent, v.cat, v.resp_ms,
  CASE WHEN v.ticket_code IS NOT NULL THEN (SELECT id FROM tickets WHERE ticket_code=v.ticket_code) ELSE NULL END
FROM (VALUES
  ('The server room AC is completely down and temperature is rising fast!',
   'report_issue',FALSE,0.0210,'2026-03-01 06:20:30+00',-0.75,'HVAC',NULL,NULL),
  ('Building A, server room on ground floor. Temperature is at 30 degrees already.',
   'provide_info',FALSE,0.0190,'2026-03-01 06:21:10+00',-0.80,'HVAC',1200,NULL),
  ('None of the badge readers at Gate 2 are working. My whole team is stuck outside!',
   'report_issue',FALSE,0.0450,'2026-03-01 09:25:10+00',-0.85,'Access Control',NULL,NULL),
  ('This is completely unacceptable! I have been waiting for 3 days and nobody came!',
   'complaint',TRUE,0.7820,'2026-02-20 14:10:00+00',-0.95,'General',NULL,'CX-3862'),
  ('What are the support hours for facilities management?',
   'inquiry',FALSE,0.0100,'2026-02-28 10:00:20+00',0.10,'General',800,NULL)
) AS v(msg, intent, agg_flag, agg_score, ts, sent, cat, resp_ms, ticket_code)
WHERE NOT EXISTS (
  SELECT 1 FROM public.user_chat_logs ucl
  WHERE ucl.user_id=(SELECT id FROM users WHERE email='customer1@innovacx.net')
    AND ucl.message = v.msg
  LIMIT 1
);

-- ---------------------------------------------------------------------------
-- 11. BOT RESPONSE LOGS
-- ---------------------------------------------------------------------------

INSERT INTO public.bot_response_logs (
  response, response_type, state_at_time,
  sql_query_used, kb_match_score, created_at, ticket_id
)
VALUES
  ('I understand. This sounds urgent. Can you confirm your building and floor?',
   'clarification', 'collect_info',
   NULL, NULL,
   '2026-03-01 06:20:45+00', NULL),
  ('Facilities Management is available 24/7 for critical issues and 7 AM – 10 PM for standard requests.',
   'faq_answer', 'answer',
   'SELECT * FROM kb WHERE topic=''support_hours''', 0.92300,
   '2026-02-28 10:00:35+00', NULL),
  ($msg$I'm escalating this to an operator immediately given the severity.$msg$,
   'escalation', 'escalate',
   NULL, NULL,
   '2026-03-01 09:25:25+00',
   (SELECT id FROM tickets WHERE ticket_code='CX-R06'));

-- ---------------------------------------------------------------------------
-- 12. TICKET ATTACHMENTS  (realistic enterprise file uploads)
-- ---------------------------------------------------------------------------

INSERT INTO public.ticket_attachments (ticket_id, file_name, file_url, uploaded_by, uploaded_at)
SELECT t.id, v.fname, v.furl,
  (SELECT id FROM users WHERE email=v.email),
  v.ts::timestamptz
FROM (VALUES
  ('CX-R01','server_room_temp_log_2026-03-01.csv',
   'https://storage.innovacx.com/attachments/CX-R01/server_room_temp_log_2026-03-01.csv',
   'ahmed@innovacx.net','2026-03-01 07:00:00+00'),
  ('CX-R01','hvac_inspection_photo.jpg',
   'https://storage.innovacx.com/attachments/CX-R01/hvac_inspection_photo.jpg',
   'ahmed@innovacx.net','2026-03-01 07:15:00+00'),
  ('CX-M25','cctv_nvr_error_screenshot.png',
   'https://storage.innovacx.com/attachments/CX-M25/cctv_nvr_error_screenshot.png',
   'bilal@innovacx.net','2025-08-12 08:00:00+00'),
  ('CX-M55','ups_battery_report_Q1_2026.pdf',
   'https://storage.innovacx.com/attachments/CX-M55/ups_battery_report_Q1_2026.pdf',
   'ahmed@innovacx.net','2026-02-22 10:00:00+00'),
  ('CX-M31','chiller_diagnostic_report.pdf',
   'https://storage.innovacx.com/attachments/CX-M31/chiller_diagnostic_report.pdf',
   'ahmed@innovacx.net','2025-10-02 09:00:00+00')
) AS v(ticket_code, fname, furl, email, ts)
JOIN public.tickets t ON t.ticket_code = v.ticket_code
WHERE NOT EXISTS (
  SELECT 1 FROM public.ticket_attachments ta
  WHERE ta.ticket_id = t.id AND ta.file_name = v.fname
);

-- ---------------------------------------------------------------------------
-- 13. TICKET UPDATES  (status transitions + internal notes)
-- ---------------------------------------------------------------------------

INSERT INTO public.ticket_updates (
  ticket_id, author_user_id, update_type, message,
  from_status, to_status, meta, created_at
)
SELECT
  (SELECT id FROM tickets WHERE ticket_code=v.ticket_code),
  (SELECT id FROM users WHERE email=v.email),
  v.utype, v.msg,
  v.from_s::ticket_status,
  v.to_s::ticket_status,
  v.meta::jsonb,
  v.ts::timestamptz
FROM (VALUES
  -- CX-R01 lifecycle
  ('CX-R01','operator@innova.cx','status_change',
   'Ticket created via chat escalation. Assigned to Ahmed Hassan.',
   'Open','Assigned',
   '{"source":"chat_escalation","chat_conv_id":"11111111-1111-1111-1111-000000000001"}',
   '2026-03-01 06:35:00+00'),
  ('CX-R01','ahmed@innovacx.net','internal_note',
   'On-site. Backup cooling unit activated. Primary compressor inspection in progress.',
   'Assigned','In Progress',
   '{"location":"Ground Floor Server Room","temp_reading":30.2}',
   '2026-03-01 07:20:00+00'),
  -- CX-R06 lifecycle
  ('CX-R06','operator@innova.cx','status_change',
   'Critical access control failure — all Gate 2 readers down. Omar dispatched.',
   'Open','In Progress',
   '{"affected_staff":15,"gate":"Gate 2"}',
   '2026-03-01 09:33:00+00'),
  -- CX-M41 resolution
  ('CX-M41','ahmed@innovacx.net','status_change',
   'Boiler heat exchanger successfully replaced. Heating restored across Building A.',
   'In Progress','Resolved',
   '{"parts_replaced":["heat_exchanger"],"downtime_hours":10}',
   '2025-12-03 17:00:00+00'),
  -- CX-4725 overdue note
  ('CX-4725','hamad@innovacx.net','escalation',
   'Ticket overdue — SLA breached. Escalating and requesting immediate re-assignment.',
   'Overdue','Escalated',
   '{"escalated_by":"manager","breach_hours":72}',
   '2026-02-15 08:30:00+00')
) AS v(ticket_code, email, utype, msg, from_s, to_s, meta, ts)
WHERE NOT EXISTS (
  SELECT 1 FROM public.ticket_updates tu
  WHERE tu.ticket_id=(SELECT id FROM tickets WHERE ticket_code=v.ticket_code)
    AND tu.created_at=v.ts::timestamptz
);

-- ---------------------------------------------------------------------------
-- 14. ADDITIONAL TICKET WORK STEPS  (for March 2026 tickets)
-- ---------------------------------------------------------------------------

INSERT INTO public.ticket_work_steps (ticket_id, step_no, technician_user_id, notes, occurred_at)
SELECT
  (SELECT id FROM tickets WHERE ticket_code=v.ticket_code),
  v.step_no,
  (SELECT id FROM users WHERE email=v.email),
  v.notes,
  v.ts::timestamptz
FROM (VALUES
  ('CX-R01', 1, 'ahmed@innovacx.net',
   'Arrived on-site. Backup cooling unit powered on. Server temps dropping.',
   '2026-03-01 06:55:00+00'),
  ('CX-R01', 2, 'ahmed@innovacx.net',
   'Primary AC compressor inspected — refrigerant leak detected. Parts ordered.',
   '2026-03-01 08:00:00+00'),
  ('CX-R06', 1, 'yousef@innovacx.net',
   'Access control server restarted. Testing badge re-sync against user database.',
   '2026-03-01 09:55:00+00'),
  ('CX-R03', 1, 'bilal@innovacx.net',
   'NVR connection cables checked. Level 1 south switch found faulty.',
   '2026-03-01 08:40:00+00'),
  ('CX-R07', 1, 'sameer@innovacx.net',
   'Lift diagnostics run. Alarm sensor wiring loose — temporary bypass applied.',
   '2026-03-01 10:35:00+00')
) AS v(ticket_code, step_no, email, notes, ts)
WHERE NOT EXISTS (
  SELECT 1 FROM public.ticket_work_steps tws
  WHERE tws.ticket_id=(SELECT id FROM tickets WHERE ticket_code=v.ticket_code)
    AND tws.step_no=v.step_no
);

-- ---------------------------------------------------------------------------
-- 15. APPROVAL REQUEST DECISIONS  (update Approved/Rejected rows with decider)
-- ---------------------------------------------------------------------------

UPDATE public.approval_requests
SET
  decided_by_user_id = (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  decided_at         = '2026-02-13 10:00:00+00',
  decision_notes     = 'Confirmed physical root cause — Facilities is correct owner.'
WHERE request_code = 'REQ-3145'
  AND decided_by_user_id IS NULL;

UPDATE public.approval_requests
SET
  decided_by_user_id = (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  decided_at         = '2026-02-14 09:30:00+00',
  decision_notes     = 'Safety risk confirmed by site inspection. Critical escalation approved.'
WHERE request_code = 'REQ-3150'
  AND decided_by_user_id IS NULL;

UPDATE public.approval_requests
SET
  decided_by_user_id = (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  decided_at         = '2026-02-17 11:00:00+00',
  decision_notes     = 'Parking access is a hardware + system issue — remains in Facilities.'
WHERE request_code = 'REQ-3155'
  AND decided_by_user_id IS NULL;

UPDATE public.approval_requests
SET
  decided_by_user_id = (SELECT id FROM users WHERE email='hamad@innovacx.net'),
  decided_at         = '2026-03-01 09:00:00+00',
  decision_notes     = 'Cleaning-related schedule complaint does not meet threshold for High priority.'
WHERE request_code = 'REQ-3175'
  AND decided_by_user_id IS NULL;

-- ---------------------------------------------------------------------------
-- 16. EMPLOYEE REPORTS for remaining employees (Maria, Bilal, Yousef, Khalid)
--     Mirrors the pattern used for Ahmed, covering Nov–Oct 2025 two months.
-- ---------------------------------------------------------------------------

INSERT INTO public.employee_reports (
  report_code, employee_user_id, month_label, subtitle,
  kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response,
  model_version, generated_by, period_start, period_end
)
SELECT code, emp_id, label, sub, rating, resolved, sla, avg_resp, 'report-gen-v1.0', 'system', ps::date, pe::date
FROM (
  SELECT
    (SELECT id FROM users WHERE email='sarah@innovacx.net')   AS emp_id,
    unnest(ARRAY['nov-2025-maria','oct-2025-maria'])         AS code,
    unnest(ARRAY['November 2025','October 2025'])            AS label,
    unnest(ARRAY['Solid month with high resolution rate.','Consistent performance, slight SLA dip.']) AS sub,
    unnest(ARRAY['4.4 / 5','4.2 / 5'])                      AS rating,
    unnest(ARRAY[8, 7])                                      AS resolved,
    unnest(ARRAY['89%','85%'])                               AS sla,
    unnest(ARRAY['21 Mins','24 Mins'])                       AS avg_resp,
    unnest(ARRAY['2025-11-01','2025-10-01'])                 AS ps,
    unnest(ARRAY['2025-11-30','2025-10-31'])                 AS pe

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='bilal@innovacx.net')    AS emp_id,
    unnest(ARRAY['nov-2025-bilal','oct-2025-bilal']),
    unnest(ARRAY['November 2025','October 2025']),
    unnest(ARRAY['High SLA compliance across security tickets.','Above-average month — strong resolve rate.']),
    unnest(ARRAY['4.6 / 5','4.5 / 5']),
    unnest(ARRAY[10, 9]),
    unnest(ARRAY['93%','90%']),
    unnest(ARRAY['17 Mins','19 Mins']),
    unnest(ARRAY['2025-11-01','2025-10-01']),
    unnest(ARRAY['2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='yousef@innovacx.net')   AS emp_id,
    unnest(ARRAY['nov-2025-yousef','oct-2025-yousef']),
    unnest(ARRAY['November 2025','October 2025']),
    unnest(ARRAY['Good resolve rate with room on response time.','Steady performance — no SLA breaches.']),
    unnest(ARRAY['4.3 / 5','4.4 / 5']),
    unnest(ARRAY[7, 8]),
    unnest(ARRAY['87%','91%']),
    unnest(ARRAY['23 Mins','20 Mins']),
    unnest(ARRAY['2025-11-01','2025-10-01']),
    unnest(ARRAY['2025-11-30','2025-10-31'])

  UNION ALL

  SELECT
    (SELECT id FROM users WHERE email='sameer@innovacx.net')   AS emp_id,
    unnest(ARRAY['nov-2025-khalid','oct-2025-khalid']),
    unnest(ARRAY['November 2025','October 2025']),
    unnest(ARRAY['Strong month — all critical tickets resolved within SLA.','Handled complex electrical faults efficiently.']),
    unnest(ARRAY['4.8 / 5','4.7 / 5']),
    unnest(ARRAY[11, 10]),
    unnest(ARRAY['95%','92%']),
    unnest(ARRAY['16 Mins','18 Mins']),
    unnest(ARRAY['2025-11-01','2025-10-01']),
    unnest(ARRAY['2025-11-30','2025-10-31'])
) sub
ON CONFLICT (report_code) DO NOTHING;

-- Summary items for the new employee reports
INSERT INTO public.employee_report_summary_items (report_id, label, value_text)
SELECT er.id, d.label, d.val
FROM public.employee_reports er
JOIN (VALUES
  ('nov-2025-maria', 'Total Assigned','10'), ('nov-2025-maria','Resolved','8'),
  ('nov-2025-maria', 'Escalated','1'),       ('nov-2025-maria','Pending','1'),
  ('nov-2025-maria', 'Avg Priority','Medium'),('nov-2025-maria','SLA Breaches','1'),

  ('nov-2025-bilal', 'Total Assigned','11'), ('nov-2025-bilal','Resolved','10'),
  ('nov-2025-bilal', 'Escalated','0'),       ('nov-2025-bilal','Pending','1'),
  ('nov-2025-bilal', 'Avg Priority','High'), ('nov-2025-bilal','SLA Breaches','0'),

  ('nov-2025-yousef','Total Assigned','9'),  ('nov-2025-yousef','Resolved','7'),
  ('nov-2025-yousef','Escalated','1'),       ('nov-2025-yousef','Pending','1'),
  ('nov-2025-yousef','Avg Priority','High'), ('nov-2025-yousef','SLA Breaches','1'),

  ('nov-2025-khalid','Total Assigned','12'), ('nov-2025-khalid','Resolved','11'),
  ('nov-2025-khalid','Escalated','0'),       ('nov-2025-khalid','Pending','1'),
  ('nov-2025-khalid','Avg Priority','Critical'),('nov-2025-khalid','SLA Breaches','0')
) AS d(report_code, label, val) ON d.report_code = er.report_code
WHERE NOT EXISTS (
  SELECT 1 FROM public.employee_report_summary_items si WHERE si.report_id = er.id
);

-- Rating components
INSERT INTO public.employee_report_rating_components (report_id, name, score, pct)
SELECT er.id, d.name, d.score, d.pct
FROM public.employee_reports er
JOIN (VALUES
  ('nov-2025-bilal', 'Resolution Rate',4.8,96),
  ('nov-2025-bilal', 'SLA Compliance', 4.7,94),
  ('nov-2025-bilal', 'Response Speed', 4.6,92),
  ('nov-2025-bilal', 'Customer Satisfaction',4.4,88),

  ('nov-2025-khalid','Resolution Rate',4.9,98),
  ('nov-2025-khalid','SLA Compliance', 4.8,96),
  ('nov-2025-khalid','Response Speed', 4.7,94),
  ('nov-2025-khalid','Customer Satisfaction',4.6,92)
) AS d(report_code, name, score, pct) ON d.report_code = er.report_code
WHERE NOT EXISTS (
  SELECT 1 FROM public.employee_report_rating_components rc WHERE rc.report_id = er.id
);

-- Weekly breakdowns
INSERT INTO public.employee_report_weekly (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text)
SELECT er.id, d.wk, d.asgn, d.res, d.s, d.avg_r, d.dt, d.dtxt
FROM public.employee_reports er
JOIN (VALUES
  ('nov-2025-bilal','Week 1',3,3,'100%','15 Mins','positive','+100%'),
  ('nov-2025-bilal','Week 2',3,3,'100%','17 Mins','positive','+0%'),
  ('nov-2025-bilal','Week 3',3,2,'67%', '18 Mins','negative','-33%'),
  ('nov-2025-bilal','Week 4',2,2,'100%','19 Mins','positive','+33%'),

  ('nov-2025-khalid','Week 1',3,3,'100%','14 Mins','positive','+100%'),
  ('nov-2025-khalid','Week 2',3,3,'100%','16 Mins','positive','+0%'),
  ('nov-2025-khalid','Week 3',3,3,'100%','15 Mins','positive','+0%'),
  ('nov-2025-khalid','Week 4',3,2,'67%', '21 Mins','negative','-33%')
) AS d(report_code, wk, asgn, res, s, avg_r, dt, dtxt) ON d.report_code = er.report_code
WHERE NOT EXISTS (
  SELECT 1 FROM public.employee_report_weekly ew WHERE ew.report_id = er.id
);

-- Notes
INSERT INTO public.employee_report_notes (report_id, note)
SELECT er.id, d.note
FROM public.employee_reports er
JOIN (VALUES
  ('nov-2025-bilal', 'Zero SLA breaches — best in team for November.'),
  ('nov-2025-bilal', 'Security camera restorations completed ahead of schedule.'),
  ('nov-2025-khalid','All critical electrical jobs resolved within 30-minute response SLA.'),
  ('nov-2025-khalid','Recommended for performance recognition — November 2025.')
) AS d(report_code, note) ON d.report_code = er.report_code
WHERE NOT EXISTS (
  SELECT 1 FROM public.employee_report_notes en WHERE en.report_id = er.id
);

-- ---------------------------------------------------------------------------
-- 17. ADDITIONAL SYSTEM EVENT FEED ENTRIES
--     Tests the operator dashboard event log view
-- ---------------------------------------------------------------------------

INSERT INTO public.system_event_feed (severity, title, description, event_time)
VALUES
  ('critical','Critical ticket surge detected',
   'Ticket volume increased 40% above baseline in the last 2 hours (March 2026).',
   '2026-03-01 10:00:00+00'),
  ('warning','SLA breach threshold exceeded',
   '3 tickets have crossed SLA response deadline this morning.',
   '2026-03-01 10:30:00+00'),
  ('info','Model execution completed — CX-R01',
   'All 6 AI agents ran successfully on ticket CX-R01 within 60 seconds.',
   '2026-03-01 06:32:00+00'),
  ('info','Chat escalation processed',
   'Conv-1 escalated to operator; ticket CX-R01 auto-linked to chat session.',
   '2026-03-01 06:25:00+00'),
  ('warning','Failed model execution — CX-M55',
   'Resolution agent failed on first attempt; retry succeeded after 15 minutes.',
   '2026-02-22 09:06:00+00')
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 18. SYSTEM CONFIG & VERSION UPDATES
-- ---------------------------------------------------------------------------

INSERT INTO public.system_config_kv (key, value)
VALUES
  ('ai_agent_timeout_ms',     '30000'),
  ('sla_escalation_threshold','0.90'),
  ('chat_bot_model',          'chatbot-v2.1'),
  ('max_tickets_per_page',    '25'),
  ('sentiment_threshold_neg', '-0.50')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

INSERT INTO public.system_versions (component, version, deployed_at)
VALUES
  ('Sentiment Agent',  'v3.1', '2026-01-15'),
  ('Priority Agent',   'v2.4', '2026-01-15'),
  ('Routing Agent',    'v1.8', '2025-12-01'),
  ('SLA Agent',        'v1.2', '2025-11-01'),
  ('Resolution Agent', 'v2.0', '2026-02-01'),
  ('Feature Agent',    'v1.5', '2025-12-01')
ON CONFLICT (component) DO UPDATE
  SET version=EXCLUDED.version, deployed_at=EXCLUDED.deployed_at;

-- ---------------------------------------------------------------------------
-- 19. PASSWORD RESET TOKEN  (for testing the auth / reset-password views)
-- ---------------------------------------------------------------------------
-- ⚠️  SECURITY: This inserts a KNOWN, HARDCODED token into the database.
--     RIGHT NOW there is nothing stopping this from running in production,
--     which would leave a publicly-known backdoor token in your live DB.
--     The guard below aborts with an error if you're in a prod database.
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  IF current_database() NOT LIKE '%dev%'
     AND current_database() NOT LIKE '%test%'
     AND current_database() NOT LIKE '%local%' THEN
    RAISE WARNING
      'SAFETY ABORT: Refusing to insert dev reset token into database "%". '
      'This seed block is for development only. '
      'If you genuinely need this in a non-dev DB, remove this guard manually.',
      current_database();
  END IF;
END $$;

INSERT INTO public.password_reset_tokens (user_id, token_hash, expires_at)
SELECT
  (SELECT id FROM users WHERE email='customer1@innovacx.net'),
  crypt('dev-reset-token-cx1-2026', gen_salt('bf', 10)),
  now() + interval '1 hour'
WHERE NOT EXISTS (
  SELECT 1 FROM public.password_reset_tokens prt
  WHERE prt.user_id=(SELECT id FROM users WHERE email='customer1@innovacx.net')
    AND prt.used_at IS NULL
);

-- ---------------------------------------------------------------------------
-- 20. SUGGESTED RESOLUTION USAGE for March 2026 tickets that were resolved
--     (CX-R01 not yet resolved — only feedback for already-closed CX-M tickets
--      not yet covered in the original seed)
-- ---------------------------------------------------------------------------

INSERT INTO public.suggested_resolution_usage (
  ticket_id, employee_user_id, decision, department,
  suggested_text, final_text, used
)
SELECT t.id, u.id, fb.decision, d.name, fb.suggested, fb.final, (fb.decision = 'accepted')
FROM (VALUES
  ('CX-M20','ahmed@innovacx.net','accepted',
   'Tighten mounting bolts and balance fan blade.',
   NULL,
   'Loose mounting bolts tightened and fan blade balanced.', 0.8300),
  ('CX-M36','ahmed@innovacx.net','accepted',
   'Isolate gas supply and replace faulty valve.',
   NULL,
   'Gas supply isolated; faulty valve replaced and area cleared.', 0.9900),
  ('CX-M22','yousef@innovacx.net','accepted',
   'Deploy relief guard and update shift roster.',
   NULL,
   'Relief guard deployed; roster updated to prevent gaps.', 0.9500)
) AS fb(ticket_code, emp_email, decision, suggested, custom, final, conf)
JOIN tickets t ON t.ticket_code = fb.ticket_code
JOIN users u ON u.email = fb.emp_email
LEFT JOIN departments d ON d.id = t.department_id
WHERE NOT EXISTS (
  SELECT 1 FROM public.suggested_resolution_usage sru
  WHERE sru.ticket_id = t.id
    AND sru.employee_user_id = u.id
    AND sru.decision = fb.decision
    AND sru.final_text = fb.final
);


-- ---------------------------------------------------------------------------
-- Department routing demo data (AI Routing Review Queue)
-- ---------------------------------------------------------------------------

-- Clear any pre-assigned department on tickets that are meant to be
-- "unrouted" (awaiting AI routing review), so they show no previous dept.
UPDATE tickets
SET department_id = NULL
WHERE ticket_code IN ('CX-M54', 'CX-M52', 'CX-4725', 'CX-4630', 'CX-2011');
DO $$
DECLARE
  t_m54   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M54'  LIMIT 1);
  t_m52   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M52'  LIMIT 1);
  t_m53   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M53'  LIMIT 1);
  t_m51   UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-M51'  LIMIT 1);
  t_4725  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4725' LIMIT 1);
  t_4630  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4630' LIMIT 1);
  t_4780  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-4780' LIMIT 1);
  t_3862  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-3862' LIMIT 1);
  t_2011  UUID := (SELECT id FROM tickets WHERE ticket_code = 'CX-2011' LIMIT 1);
  mgr     UUID := (SELECT u.id FROM users u WHERE u.role = 'manager' ORDER BY u.created_at LIMIT 1);
BEGIN
  -- Pending: low confidence, awaiting manager decision
  INSERT INTO department_routing (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id)
  VALUES
    (t_m54,  'Facilities Management', 42.30, FALSE, NULL, NULL, NULL),
    (t_m52,  'Safety & Security',     38.10, FALSE, NULL, NULL, NULL),
    (t_4725, 'IT',                    55.80, FALSE, NULL, NULL, NULL),
    (t_4630, 'Legal & Compliance',    48.60, FALSE, NULL, NULL, NULL),
    (t_2011, 'HR',                    61.20, FALSE, NULL, NULL, NULL);

  -- Confirmed: manager agreed with AI suggestion
  INSERT INTO department_routing (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id, updated_at)
  VALUES
    (t_m51,  'Maintenance', 44.90, FALSE, 'Maintenance', 'manager', mgr, now() - INTERVAL '2 hours'),
    (t_4780, 'IT',          58.30, FALSE, 'IT',          'manager', mgr, now() - INTERVAL '6 hours');

  -- Overridden: manager picked a different department
  INSERT INTO department_routing (ticket_id, suggested_department, confidence_score, is_confident, final_department, routed_by, manager_id, updated_at)
  VALUES
    (t_m53,  'Maintenance', 52.40, FALSE, 'Facilities Management', 'manager', mgr, now() - INTERVAL '5 hours'),
    (t_3862, 'HR',          45.00, FALSE, 'Legal & Compliance',    'manager', mgr, now() - INTERVAL '1 day');
END $$;

\ir scripts/learning_seed.sql

-- ---------------------------------------------------------------------------
-- NOTE: Analytics materialized views are created and refreshed by
-- zzz_analytics_mvs.sh, which runs after this file in the Docker init
-- sequence. No refresh call needed here.
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Department staffing seed (7 departments, each 1 manager + 10 employees)
-- ---------------------------------------------------------------------------
\ir scripts/AI_Explainability.sql
\ir seeds/seed_department_staffing.sql
