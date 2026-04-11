-- Operator Notifications — SQL Triggers & Functions
-- Categories: Model & AI Health, Ticket Pipeline,
--             System & Infrastructure, User & Security,
--             Reports & Operations


BEGIN;

-- HELPER: insert a notification for every active operator
CREATE OR REPLACE FUNCTION notify_all_operators(
  p_type      notification_type,
  p_title     TEXT,
  p_message   TEXT,
  p_priority  ticket_priority DEFAULT NULL,
  p_ticket_id UUID            DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
  v_op_id UUID;
BEGIN
  FOR v_op_id IN
    SELECT id FROM users
    WHERE role = 'operator' AND is_active = TRUE
  LOOP
    INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
    VALUES (v_op_id, p_type, p_title, p_message, p_priority, p_ticket_id);
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- 1. MODEL & AI HEALTH

-- 1a. Acceptance rate drops below 70%
--     Fires on INSERT into ticket_resolution_feedback.
--     Looks at the last 20 decisions to get a rolling rate.
CREATE OR REPLACE FUNCTION notify_operator_acceptance_rate()
RETURNS TRIGGER AS $$
DECLARE
  v_total      INTEGER;
  v_accepted   INTEGER;
  v_rate       NUMERIC(5,2);
BEGIN
  SELECT COUNT(*), COUNT(*) FILTER (WHERE decision = 'accepted')
  INTO v_total, v_accepted
  FROM (
    SELECT decision
    FROM ticket_resolution_feedback
    ORDER BY created_at DESC
    LIMIT 20
  ) recent;

  IF v_total < 5 THEN
    RETURN NEW; -- not enough data yet
  END IF;

  v_rate := ROUND((v_accepted::NUMERIC / v_total) * 100, 2);

  IF v_rate < 70 THEN
    PERFORM notify_all_operators(
      'system',
      'AI Acceptance Rate Below Threshold',
      'The AI suggestion acceptance rate has dropped to ' || v_rate || '% '
        || '(threshold: 70%). Employees are frequently overriding AI resolutions. '
        || 'Consider reviewing model performance.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF to_regclass('public.ticket_resolution_feedback') IS NOT NULL THEN
    DROP TRIGGER IF EXISTS trg_notify_operator_acceptance_rate ON ticket_resolution_feedback;
    CREATE TRIGGER trg_notify_operator_acceptance_rate
    AFTER INSERT ON ticket_resolution_feedback
    FOR EACH ROW
    EXECUTE FUNCTION notify_operator_acceptance_rate();
  END IF;
END $$;

-- 1b. Chatbot escalation rate spikes
--     Fires on INSERT into sessions.
--     If >50% of the last 10 sessions were escalated, alert.
CREATE OR REPLACE FUNCTION notify_operator_escalation_spike()
RETURNS TRIGGER AS $$
DECLARE
  v_total     INTEGER;
  v_escalated INTEGER;
  v_rate      NUMERIC(5,2);
BEGIN
  SELECT COUNT(*), COUNT(*) FILTER (WHERE escalated_to_human = TRUE)
  INTO v_total, v_escalated
  FROM (
    SELECT escalated_to_human
    FROM sessions
    ORDER BY created_at DESC
    LIMIT 10
  ) recent;

  IF v_total < 5 THEN
    RETURN NEW;
  END IF;

  v_rate := ROUND((v_escalated::NUMERIC / v_total) * 100, 2);

  IF v_rate > 50 THEN
    PERFORM notify_all_operators(
      'system',
      'Chatbot Escalation Rate Spike',
      'Over 50% of recent chatbot sessions (' || v_escalated || ' of ' || v_total
        || ') were escalated to a human operator. '
        || 'The chatbot may be struggling with current ticket types.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_escalation_spike ON sessions;
CREATE TRIGGER trg_notify_operator_escalation_spike
AFTER INSERT ON sessions
FOR EACH ROW
EXECUTE FUNCTION notify_operator_escalation_spike();

-- 1c. Model confidence drops significantly
--     Fires on INSERT/UPDATE of tickets when model_confidence
--     is set. Alerts if the rolling average of the last 10
--     tickets drops below 65%.
CREATE OR REPLACE FUNCTION notify_operator_model_confidence()
RETURNS TRIGGER AS $$
DECLARE
  v_avg NUMERIC(5,2);
BEGIN
  IF NEW.model_confidence IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT ROUND(AVG(model_confidence), 2)
  INTO v_avg
  FROM (
    SELECT model_confidence
    FROM tickets
    WHERE model_confidence IS NOT NULL
    ORDER BY created_at DESC
    LIMIT 10
  ) recent;

  IF v_avg < 65 THEN
    PERFORM notify_all_operators(
      'system',
      'Model Confidence Score Low',
      'The rolling average model confidence across the last 10 tickets is '
        || v_avg || '%. This may indicate the model is uncertain about '
        || 'recent ticket classifications. Review model health.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_model_confidence ON tickets;
CREATE TRIGGER trg_notify_operator_model_confidence
AFTER INSERT OR UPDATE OF model_confidence ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_operator_model_confidence();

-- 2. TICKET PIPELINE

-- 2a. Open backlog exceeds 10 tickets
--     Fires on INSERT or when status changes to Open.
CREATE OR REPLACE FUNCTION notify_operator_unassigned_backlog()
RETURNS TRIGGER AS $$
DECLARE
  v_count INTEGER;
BEGIN
  -- Only relevant when the ticket is or becomes Open
  IF NEW.status <> 'Open' THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*)
  INTO v_count
  FROM tickets
  WHERE status = 'Open';

  IF v_count >= 10 THEN
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

DROP TRIGGER IF EXISTS trg_notify_operator_unassigned_backlog ON tickets;
CREATE TRIGGER trg_notify_operator_unassigned_backlog
AFTER INSERT OR UPDATE OF status ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_operator_unassigned_backlog();

-- 2b. Critical open ticket for too long
--     Fires on UPDATE — if a Critical ticket remains
--     Open for more than 15 minutes after creation.
--     Checked on any ticket update as a lightweight poll.
CREATE OR REPLACE FUNCTION notify_operator_critical_unassigned()
RETURNS TRIGGER AS $$
DECLARE
  v_ticket RECORD;
BEGIN
  -- Scan for any critical+open ticket older than 15 minutes
  FOR v_ticket IN
    SELECT id, ticket_code, subject
    FROM tickets
    WHERE status = 'Open'
      AND priority = 'Critical'
      AND created_at <= now() - interval '15 minutes'
  LOOP
    -- Avoid duplicate notifications: skip if one was sent in the last hour
    IF NOT EXISTS (
      SELECT 1 FROM notifications
      WHERE ticket_id = v_ticket.id
        AND title LIKE 'Critical Ticket Open%'
        AND created_at >= now() - interval '1 hour'
    ) THEN
      PERFORM notify_all_operators(
        'system',
        'Critical Ticket Open — ' || v_ticket.ticket_code,
        'Ticket "' || v_ticket.subject || '" (' || v_ticket.ticket_code || ') '
          || 'is Critical priority and has been open for over 15 minutes.',
        'Critical',
        v_ticket.id
      );
    END IF;
  END LOOP;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_critical_unassigned ON tickets;
CREATE TRIGGER trg_notify_operator_critical_unassigned
AFTER UPDATE ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_operator_critical_unassigned();

-- 2c. SLA breach rate spikes
--     Fires on ticket UPDATE when respond_breached or
--     resolve_breached flips to TRUE.
--     Alerts if >30% of tickets in the last 24 hours breached.
CREATE OR REPLACE FUNCTION notify_operator_sla_breach_rate()
RETURNS TRIGGER AS $$
DECLARE
  v_total    INTEGER;
  v_breached INTEGER;
  v_rate     NUMERIC(5,2);
BEGIN
  -- Only fire when a breach flag is newly set
  IF (NEW.respond_breached = OLD.respond_breached)
     AND (NEW.resolve_breached = OLD.resolve_breached) THEN
    RETURN NEW;
  END IF;

  SELECT COUNT(*),
         COUNT(*) FILTER (WHERE respond_breached = TRUE OR resolve_breached = TRUE)
  INTO v_total, v_breached
  FROM tickets
  WHERE created_at >= now() - interval '24 hours';

  IF v_total = 0 THEN RETURN NEW; END IF;

  v_rate := ROUND((v_breached::NUMERIC / v_total) * 100, 2);

  IF v_rate > 30 THEN
    PERFORM notify_all_operators(
      'sla_warning',
      'SLA Breach Rate High',
      v_breached || ' of ' || v_total || ' tickets in the last 24 hours have '
        || 'breached SLA (' || v_rate || '%). Immediate review recommended.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_sla_breach_rate ON tickets;
CREATE TRIGGER trg_notify_operator_sla_breach_rate
AFTER UPDATE OF respond_breached, resolve_breached ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_operator_sla_breach_rate();

-- 2d. Ticket volume surge
--     Fires on INSERT. If more than 10 tickets are created
--     in the last 2 hours, alert once per hour.
CREATE OR REPLACE FUNCTION notify_operator_ticket_volume_surge()
RETURNS TRIGGER AS $$
DECLARE
  v_count INTEGER;
BEGIN
  SELECT COUNT(*)
  INTO v_count
  FROM tickets
  WHERE created_at >= now() - interval '2 hours';

  IF v_count > 10 THEN
    -- Deduplicate: only once per hour
    IF NOT EXISTS (
      SELECT 1 FROM notifications
      WHERE title = 'Ticket Volume Surge'
        AND created_at >= now() - interval '1 hour'
    ) THEN
      PERFORM notify_all_operators(
        'system',
        'Ticket Volume Surge',
        v_count || ' tickets have been created in the last 2 hours, '
          || 'which is above the normal baseline. '
          || 'Consider increasing staffing or reviewing automation rules.'
      );
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_ticket_volume_surge ON tickets;
CREATE TRIGGER trg_notify_operator_ticket_volume_surge
AFTER INSERT ON tickets
FOR EACH ROW
EXECUTE FUNCTION notify_operator_ticket_volume_surge();

-- 3. SYSTEM & INFRASTRUCTURE

-- 3a. Core service flips to warning or critical
--     Fires on INSERT OR UPDATE of system_service_status.
CREATE OR REPLACE FUNCTION notify_operator_service_status()
RETURNS TRIGGER AS $$
BEGIN
  -- On UPDATE only alert if severity actually changed
  IF TG_OP = 'UPDATE' AND NEW.severity = OLD.severity THEN
    RETURN NEW;
  END IF;

  IF NEW.severity IN ('warning', 'critical') THEN
    PERFORM notify_all_operators(
      'system',
      'Service ' || INITCAP(NEW.severity::TEXT) || ': ' || NEW.name,
      'Service "' || NEW.name || '" status changed to ' || NEW.status
        || '. Note: ' || COALESCE(NEW.note, 'No additional details.')
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_service_status ON system_service_status;
CREATE TRIGGER trg_notify_operator_service_status
AFTER INSERT OR UPDATE ON system_service_status
FOR EACH ROW
EXECUTE FUNCTION notify_operator_service_status();

-- 3b. Integration goes down
--     Fires on INSERT OR UPDATE of system_integration_status.
CREATE OR REPLACE FUNCTION notify_operator_integration_status()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.severity = OLD.severity THEN
    RETURN NEW;
  END IF;

  IF NEW.severity IN ('warning', 'critical') THEN
    PERFORM notify_all_operators(
      'system',
      'Integration ' || INITCAP(NEW.severity::TEXT) || ': ' || NEW.name,
      'Integration "' || NEW.name || '" is reporting status: ' || NEW.status
        || '. Note: ' || COALESCE(NEW.note, 'No additional details.')
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_integration_status ON system_integration_status;
CREATE TRIGGER trg_notify_operator_integration_status
AFTER INSERT OR UPDATE ON system_integration_status
FOR EACH ROW
EXECUTE FUNCTION notify_operator_integration_status();

-- 3c. Queue backlog grows beyond threshold
--     Fires on INSERT OR UPDATE of system_queue_metrics.
CREATE OR REPLACE FUNCTION notify_operator_queue_backlog()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.severity = OLD.severity THEN
    RETURN NEW;
  END IF;

  IF NEW.severity IN ('warning', 'critical') THEN
    PERFORM notify_all_operators(
      'system',
      'Queue Backlog ' || INITCAP(NEW.severity::TEXT) || ': ' || NEW.name,
      '"' || NEW.name || '" has a backlog of ' || NEW.value || '. '
        || COALESCE(NEW.note, 'Review pipeline throughput.')
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_queue_backlog ON system_queue_metrics;
CREATE TRIGGER trg_notify_operator_queue_backlog
AFTER INSERT OR UPDATE ON system_queue_metrics
FOR EACH ROW
EXECUTE FUNCTION notify_operator_queue_backlog();

-- 4. USER & SECURITY

-- 4a. New user created
--     Fires on INSERT into users.
CREATE OR REPLACE FUNCTION notify_operator_user_created()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM notify_all_operators(
    'system',
    'New User Created',
    'A new ' || NEW.role::TEXT || ' account was created for '
      || NEW.email || '.'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_user_created ON users;
CREATE TRIGGER trg_notify_operator_user_created
AFTER INSERT ON users
FOR EACH ROW
EXECUTE FUNCTION notify_operator_user_created();

-- 4b. User deactivated
--     Fires on UPDATE when is_active flips from TRUE to FALSE.
CREATE OR REPLACE FUNCTION notify_operator_user_deactivated()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.is_active = TRUE AND NEW.is_active = FALSE THEN
    PERFORM notify_all_operators(
      'system',
      'User Account Deactivated',
      'The account for ' || NEW.email || ' (' || NEW.role::TEXT
        || ') has been deactivated.'
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_user_deactivated ON users;
CREATE TRIGGER trg_notify_operator_user_deactivated
AFTER UPDATE OF is_active ON users
FOR EACH ROW
EXECUTE FUNCTION notify_operator_user_deactivated();

-- 4c. Password reset requested
--     Fires on INSERT into password_reset_tokens.
CREATE OR REPLACE FUNCTION notify_operator_password_reset()
RETURNS TRIGGER AS $$
DECLARE
  v_email TEXT;
  v_role  user_role;
BEGIN
  SELECT email, role INTO v_email, v_role
  FROM users WHERE id = NEW.user_id;

  -- Only alert operators when the reset is for a privileged account
  IF v_role IN ('operator', 'manager', 'employee') THEN
    PERFORM notify_all_operators(
      'system',
      'Password Reset Requested',
      'A password reset was requested for ' || v_email
        || ' (' || v_role::TEXT || '). '
        || 'If this was not expected, investigate immediately.'
    );
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_password_reset ON password_reset_tokens;
CREATE TRIGGER trg_notify_operator_password_reset
AFTER INSERT ON password_reset_tokens
FOR EACH ROW
EXECUTE FUNCTION notify_operator_password_reset();

-- 5. REPORTS & OPERATIONS

-- 5a. Monthly performance report generated
--     Fires on INSERT into employee_reports.
CREATE OR REPLACE FUNCTION notify_operator_report_ready()
RETURNS TRIGGER AS $$
DECLARE
  v_name TEXT;
BEGIN
  SELECT full_name INTO v_name
  FROM user_profiles WHERE user_id = NEW.employee_user_id;

  PERFORM notify_all_operators(
    'report_ready',
    'Monthly Report Ready — ' || NEW.month_label,
    'Performance report for ' || COALESCE(v_name, 'an employee')
      || ' (' || NEW.month_label || ') has been generated. '
      || 'Report code: ' || NEW.report_code || '.'
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_report_ready ON employee_reports;
CREATE TRIGGER trg_notify_operator_report_ready
AFTER INSERT ON employee_reports
FOR EACH ROW
EXECUTE FUNCTION notify_operator_report_ready();

-- 5b. Approval request pending too long (> 24 hours)
--     Fires on UPDATE of approval_requests.
--     If still Pending after 24h, alert once.
CREATE OR REPLACE FUNCTION notify_operator_approval_overdue()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.status <> 'Pending' THEN
    RETURN NEW;
  END IF;

  IF NEW.submitted_at <= now() - interval '24 hours' THEN
    IF NOT EXISTS (
      SELECT 1 FROM notifications
      WHERE title LIKE '%Approval Request Overdue%' || NEW.request_code || '%'
        AND created_at >= now() - interval '24 hours'
    ) THEN
      PERFORM notify_all_operators(
        'system',
        'Approval Request Overdue — ' || NEW.request_code,
        'Approval request ' || NEW.request_code
          || ' has been pending for over 24 hours with no manager decision. '
          || 'Type: ' || NEW.request_type::TEXT
          || '. Current → Requested: ' || NEW.current_value
          || ' → ' || NEW.requested_value || '.'
      );
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_operator_approval_overdue ON approval_requests;
CREATE TRIGGER trg_notify_operator_approval_overdue
AFTER UPDATE ON approval_requests
FOR EACH ROW
EXECUTE FUNCTION notify_operator_approval_overdue();

COMMIT;
