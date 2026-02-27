-- =========================================================
-- InnovaCX 
-- =========================================================

BEGIN;

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
    'Unassigned',
    'Assigned',
    'Escalated',
    'Overdue',
    'Reopened',
    'Resolved'
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
    'system'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE service_severity AS ENUM ('ok', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE event_severity AS ENUM ('info', 'warning', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

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
CREATE TABLE IF NOT EXISTS users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         CITEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          user_role NOT NULL,
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);

-- -------------------------
-- MFA columns (safe for re-runs)
-- -------------------------
ALTER TABLE users
ADD COLUMN IF NOT EXISTS totp_secret TEXT;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;

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
  ticket_type         ticket_type NOT NULL DEFAULT 'Complaint',
  status              ticket_status NOT NULL DEFAULT 'Unassigned',
  priority            ticket_priority NOT NULL DEFAULT 'Medium',
  asset_type          TEXT NOT NULL DEFAULT 'General',
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
  final_resolution    TEXT,
  resolved_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

-- =============================================================================
-- Suggested Resolution + Retraining schema
-- =============================================================================
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_model TEXT;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_generated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS ticket_resolution_feedback (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id            UUID        NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    employee_user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    decision             TEXT        NOT NULL CHECK (decision IN ('accepted', 'declined_custom')),
    suggested_resolution TEXT,
    employee_resolution  TEXT,
    final_resolution     TEXT        NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ticket_resolution_feedback_ticket
    ON ticket_resolution_feedback (ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_resolution_feedback_employee
    ON ticket_resolution_feedback (employee_user_id);

CREATE INDEX IF NOT EXISTS idx_tickets_status      ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority    ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_asset_type  ON tickets(asset_type);
CREATE INDEX IF NOT EXISTS idx_tickets_created_at  ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_assignee    ON tickets(assigned_to_user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_creator     ON tickets(created_by_user_id);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

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
  submitted_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  status               approval_status NOT NULL DEFAULT 'Pending',
  decided_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
  decided_at           TIMESTAMPTZ,
  decision_notes       TEXT
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_ticket ON approval_requests(ticket_id);

-- -------------------------
-- Auto-notify manager on new approval requests
-- -------------------------
CREATE OR REPLACE FUNCTION notify_manager_on_approval_request()
RETURNS TRIGGER AS $$
DECLARE
  v_manager_id     UUID;
  v_ticket_code    TEXT;
  v_ticket_priority ticket_priority;
  v_submitter_name TEXT;
  v_title          TEXT;
  v_message        TEXT;
BEGIN
  -- Get the ticket info
  SELECT ticket_code, priority
  INTO v_ticket_code, v_ticket_priority
  FROM tickets WHERE id = NEW.ticket_id;

  -- Get the submitter's name
  SELECT full_name INTO v_submitter_name
  FROM user_profiles WHERE user_id = NEW.submitted_by_user_id;

  -- Find any active manager(s) — notifies all managers
  FOR v_manager_id IN
    SELECT id FROM users WHERE role = 'manager' AND is_active = TRUE
  LOOP
    v_title := CASE NEW.request_type
      WHEN 'Rescoring' THEN 'Rescoring Request — ' || COALESCE(v_ticket_code, 'Unknown')
      WHEN 'Rerouting' THEN 'Rerouting Request — ' || COALESCE(v_ticket_code, 'Unknown')
      ELSE 'Approval Request — ' || COALESCE(v_ticket_code, 'Unknown')
    END;

    v_message := COALESCE(v_submitter_name, 'An employee') || ' submitted a '
      || lower(NEW.request_type::TEXT) || ' request. '
      || 'Current: ' || NEW.current_value || ' → Requested: ' || NEW.requested_value || '.';

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
-- Seed data
-- =========================================================

INSERT INTO departments (name) VALUES
  ('IT'),
  ('Facilities'),
  ('Security'),
  ('HR'),
  ('Admin'),
  ('Facilities Management'),
  ('IT Support'),
  ('Cleaning'),
  ('Maintenance')
ON CONFLICT (name) DO NOTHING;

-- ✅ Use real bcrypt-compatible hashes from pgcrypto (fresh volumes work)
-- mfa_enabled = FALSE and totp_secret = NULL so all users get a proper
-- bearer token on login (no MFA prompt during development/testing)
INSERT INTO users (email, password_hash, role, mfa_enabled, totp_secret) VALUES
  ('customer1@innova.cx', crypt('Innova@2025', gen_salt('bf', 12)), 'customer',  FALSE, NULL),
  ('manager@innova.cx',   crypt('Innova@2025', gen_salt('bf', 12)), 'manager',   FALSE, NULL),
  ('operator@innova.cx',  crypt('Innova@2025', gen_salt('bf', 12)), 'operator',  FALSE, NULL),
  ('ahmed@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('maria@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('omar@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('sara@innova.cx',      crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('bilal@innova.cx',     crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('fatima@innova.cx',    crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('yousef@innova.cx',    crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL),
  ('khalid@innova.cx',    crypt('Innova@2025', gen_salt('bf', 12)), 'employee',  FALSE, NULL)
ON CONFLICT (email) DO UPDATE
  SET mfa_enabled = FALSE,
      totp_secret = NULL;


-- Profiles
INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Dr. Farhad', NULL, 'Department Manager',
       (SELECT id FROM departments WHERE name='Facilities Management' LIMIT 1)
FROM users u WHERE u.email='manager@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Ahmed Hassan', 'EMP-1023', 'Senior Technician',
       (SELECT id FROM departments WHERE name='Facilities' LIMIT 1)
FROM users u WHERE u.email='ahmed@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Maria Lopez', 'EMP-1078', 'Technician',
       (SELECT id FROM departments WHERE name='Facilities' LIMIT 1)
FROM users u WHERE u.email='maria@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Omar Ali', 'EMP-1150', 'Assistant Technician',
       (SELECT id FROM departments WHERE name='Facilities' LIMIT 1)
FROM users u WHERE u.email='omar@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title, department_id)
SELECT u.id, 'Sara Ahmed', 'EMP-1192', 'Technician',
       (SELECT id FROM departments WHERE name='Cleaning' LIMIT 1)
FROM users u WHERE u.email='sara@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title)
SELECT u.id, 'Bilal Khan', 'EMP-1244', 'HVAC Specialist'
FROM users u WHERE u.email='bilal@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title)
SELECT u.id, 'Fatima Noor', 'EMP-1290', 'Coordinator'
FROM users u WHERE u.email='fatima@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title)
SELECT u.id, 'Yousef Karim', 'EMP-1331', 'Maintenance Supervisor'
FROM users u WHERE u.email='yousef@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, employee_code, job_title)
SELECT u.id, 'Khalid Musa', 'EMP-1378', 'Electrician'
FROM users u WHERE u.email='khalid@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO user_profiles (user_id, full_name, phone, location)
SELECT u.id, 'Customer One', '+971500000000', 'Dubai'
FROM users u WHERE u.email='customer1@innova.cx'
ON CONFLICT (user_id) DO NOTHING;

-- Tickets (original sample seed)
WITH
cust  AS (SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1),
ahmed AS (SELECT id FROM users WHERE email='ahmed@innova.cx' LIMIT 1),
maria AS (SELECT id FROM users WHERE email='maria@innova.cx' LIMIT 1),
omar  AS (SELECT id FROM users WHERE email='omar@innova.cx' LIMIT 1),
sara  AS (SELECT id FROM users WHERE email='sara@innova.cx' LIMIT 1),
fac   AS (SELECT id FROM departments WHERE name='Facilities' LIMIT 1),
it    AS (SELECT id FROM departments WHERE name='IT' LIMIT 1)
INSERT INTO tickets (
  ticket_code, subject, details, ticket_type, priority, status, department_id,
  created_by_user_id, assigned_to_user_id, created_at,
  respond_due_at, resolve_due_at,
  model_suggestion, model_priority, model_confidence,
  sentiment_score, sentiment_label
) VALUES
('CX-1122','Air conditioning not working','AC stopped cooling in office area. Needs urgent repair.',
 'Complaint','Critical','Unassigned',(SELECT id FROM fac),(SELECT id FROM cust),NULL,
 to_timestamp('19/11/2025','DD/MM/YYYY'),
 to_timestamp('19/11/2025','DD/MM/YYYY') + interval '30 minutes',
 to_timestamp('19/11/2025','DD/MM/YYYY') + interval '6 hours',
 'Dispatch HVAC technician and check compressor / thermostat; confirm coolant pressure.',
 'Critical',92.50, -0.450,'Negative'),

('CX-3862','Water leakage in pantry','Leakage detected under pantry sink. Water pooling on floor.',
 'Complaint','Critical','Overdue',(SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM maria),
 to_timestamp('18/11/2025','DD/MM/YYYY'),
 to_timestamp('18/11/2025','DD/MM/YYYY') + interval '30 minutes',
 to_timestamp('18/11/2025','DD/MM/YYYY') + interval '6 hours',
 'Isolate water source and replace faulty seal / pipe joint; dry area and confirm no further leak.',
 'Critical',90.10,-0.380,'Negative'),

('CX-4587','Wi-Fi connection unstable','Frequent disconnects reported across floor 2.',
 'Inquiry','High','Escalated',(SELECT id FROM it),(SELECT id FROM cust),NULL,
 to_timestamp('19/11/2025','DD/MM/YYYY'),
 to_timestamp('19/11/2025','DD/MM/YYYY') + interval '1 hour',
 to_timestamp('19/11/2025','DD/MM/YYYY') + interval '18 hours',
 'Check AP logs, channel overlap, and DHCP lease issues; restart controller if needed.',
 'High',88.00,-0.120,'Neutral'),

('CX-4630','Lift stopping between floors','Elevator intermittently stops between floors and reboots.',
 'Complaint','High','Assigned',(SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM ahmed),
 to_timestamp('18/11/2025','DD/MM/YYYY'),
 to_timestamp('18/11/2025','DD/MM/YYYY') + interval '1 hour',
 to_timestamp('18/11/2025','DD/MM/YYYY') + interval '18 hours',
 'Run elevator diagnostics, inspect door sensors and control panel error logs.',
 'High',86.40,-0.200,'Neutral'),

('CX-4701','Cleaning service missed schedule','Cleaning did not occur on scheduled time.',
 'Complaint','Medium','Unassigned',(SELECT id FROM fac),(SELECT id FROM cust),NULL,
 to_timestamp('16/11/2025','DD/MM/YYYY'),
 to_timestamp('16/11/2025','DD/MM/YYYY') + interval '3 hours',
 to_timestamp('16/11/2025','DD/MM/YYYY') + interval '2 days',
 'Assign cleaning team; confirm schedule and update customer with ETA.',
 'Medium',80.00,0.050,'Neutral'),

('CX-4725','Parking access card not working','Customer access card fails at gate reader.',
 'Inquiry','Medium','Overdue',(SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM omar),
 to_timestamp('13/11/2025','DD/MM/YYYY'),
 to_timestamp('13/11/2025','DD/MM/YYYY') + interval '3 hours',
 to_timestamp('13/11/2025','DD/MM/YYYY') + interval '2 days',
 'Re-encode card, test reader, and confirm access permissions in system.',
 'Medium',82.20,-0.050,'Neutral'),

('CX-4780','Noise from maintenance works','Noise complaint due to late-hour maintenance.',
 'Complaint','Low','Escalated',(SELECT id FROM fac),(SELECT id FROM cust),(SELECT id FROM sara),
 to_timestamp('09/11/2025','DD/MM/YYYY'),
 to_timestamp('09/11/2025','DD/MM/YYYY') + interval '6 hours',
 to_timestamp('09/11/2025','DD/MM/YYYY') + interval '3 days',
 'Coordinate maintenance hours; add noise control measures and notify affected area.',
 'Low',76.00,0.100,'Neutral')
ON CONFLICT (ticket_code) DO NOTHING;

-- ✅ KPI-friendly tickets for Ahmed (FIXED: every row has same number of columns)
WITH
cust  AS (SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1),
ahmed AS (SELECT id FROM users WHERE email='ahmed@innova.cx' LIMIT 1),
fac   AS (SELECT id FROM departments WHERE name='Facilities' LIMIT 1)
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
SELECT t.id, 1, (SELECT id FROM users WHERE email='ahmed@innova.cx' LIMIT 1),
       t.created_at + interval '20 minutes',
       'Initial inspection completed. Logged error codes and safety checks.'
FROM tickets t WHERE t.ticket_code='CX-4630'
ON CONFLICT (ticket_id, step_no) DO NOTHING;

-- Placeholder tickets required for approvals linkage
INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, created_by_user_id, created_at)
SELECT 'CX-2011', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3101',
       'Complaint','Medium','Unassigned',(SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1),
       to_timestamp('18/11/2025','DD/MM/YYYY')
WHERE NOT EXISTS (SELECT 1 FROM tickets WHERE ticket_code='CX-2011');

INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, created_by_user_id, created_at)
SELECT 'CX-2034', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3110',
       'Complaint','Medium','Unassigned',(SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1),
       to_timestamp('18/11/2025','DD/MM/YYYY')
WHERE NOT EXISTS (SELECT 1 FROM tickets WHERE ticket_code='CX-2034');

INSERT INTO tickets (ticket_code, subject, details, ticket_type, priority, status, created_by_user_id, created_at)
SELECT 'CX-2078', 'Placeholder ticket for approval linkage', 'Created to support approval request REQ-3125',
       'Complaint','High','Unassigned',(SELECT id FROM users WHERE email='customer1@innova.cx' LIMIT 1),
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
  (SELECT id FROM users WHERE email='ahmed@innova.cx' LIMIT 1),
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
  'Dept: Facilities', 'Dept: Security',
  'Security review required due to access-control implications.',
  (SELECT id FROM users WHERE email='ahmed@innova.cx' LIMIT 1),
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
  (SELECT id FROM users WHERE email='maria@innova.cx' LIMIT 1),
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
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx' LIMIT 1)
WHERE ticket_code IN ('CX-4630', 'CX-9001', 'CX-9002', 'CX-9003', 'CX-9004', 'CX-9005');

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'maria@innova.cx' LIMIT 1)
WHERE ticket_code = 'CX-3862';

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'omar@innova.cx' LIMIT 1)
WHERE ticket_code = 'CX-4725';

UPDATE tickets
SET assigned_to_user_id = (SELECT id FROM users WHERE email = 'sara@innova.cx' LIMIT 1)
WHERE ticket_code = 'CX-4780';

-- Disable MFA for all seed users so login returns a bearer token
-- (not a temporary token) — required for employee actions to work
UPDATE users
SET mfa_enabled = FALSE, totp_secret = NULL
WHERE email IN (
  'customer1@innova.cx',
  'manager@innova.cx',
  'operator@innova.cx',
  'ahmed@innova.cx',
  'maria@innova.cx',
  'omar@innova.cx',
  'sara@innova.cx',
  'bilal@innova.cx',
  'fatima@innova.cx',
  'yousef@innova.cx',
  'khalid@innova.cx'
);

-- =========================================================
-- Seed: Employee Monthly Reports for Ahmed Hassan
-- (nov-2025 through jun-2025, 6 months)
-- =========================================================

INSERT INTO employee_reports (report_code, employee_user_id, month_label, subtitle, kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response)
SELECT code, ahmed_id, label, sub, rating, resolved, sla, avg_resp
FROM (
  SELECT
    (SELECT id FROM users WHERE email = 'ahmed@innova.cx') AS ahmed_id,
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  AND er.employee_user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
  AND NOT EXISTS (
    SELECT 1 FROM employee_report_notes en WHERE en.report_id = er.id
  );

-- =========================================================
-- Seed: Notifications for Ahmed (unread + mixed types)
-- =========================================================

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'sla_warning',
  'SLA Warning: CX-9004',
  'Ticket CX-9004 is overdue. Immediate action required.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9004'),
  FALSE,
  now() - interval '2 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
    AND n.title = 'SLA Warning: CX-9004'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'ticket_assignment',
  'Ticket Assigned: CX-9003',
  'You have been assigned ticket CX-9003 — Critical priority.',
  'Critical',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9003'),
  FALSE,
  now() - interval '1 day'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
    AND n.title = 'Ticket Assigned: CX-9003'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'ticket_assignment',
  'Ticket Assigned: CX-9001',
  'You have been assigned a new ticket CX-9001.',
  'Medium',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9001'),
  TRUE,
  now() - interval '12 days'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
    AND n.title = 'Ticket Assigned: CX-9001'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'report_ready',
  'Monthly Report Ready',
  'Your November 2025 performance report is now available.',
  NULL,
  NULL,
  TRUE,
  now() - interval '5 days'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
    AND n.title = 'Monthly Report Ready'
);

INSERT INTO notifications (user_id, type, title, message, priority, ticket_id, read, created_at)
SELECT
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'status_change',
  'Ticket Status Updated: CX-9002',
  'Ticket CX-9002 has been moved to In Progress.',
  'High',
  (SELECT id FROM tickets WHERE ticket_code = 'CX-9002'),
  FALSE,
  now() - interval '3 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM notifications n
  WHERE n.user_id = (SELECT id FROM users WHERE email = 'ahmed@innova.cx')
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
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
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
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
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
  (SELECT id FROM users WHERE email = 'ahmed@innova.cx'),
  'Ticket overdue. Escalation attempt made — awaiting supervisor response.',
  now() - interval '5 hours'
WHERE NOT EXISTS (
  SELECT 1 FROM ticket_work_steps tws
  WHERE tws.ticket_id = (SELECT id FROM tickets WHERE ticket_code = 'CX-9004')
    AND tws.step_no = 1
);

COMMIT;