/* ============================================================
   AI Complaint Management System - PostgreSQL Schema (DDL)
   ============================================================ */

-- -------------------------------
-- Create dedicated schema
-- -------------------------------
CREATE SCHEMA IF NOT EXISTS cms;
SET search_path TO cms;

-- -------------------------------
-- 1) ENUM TYPES
-- -------------------------------
DO $$ BEGIN
  CREATE TYPE role_type AS ENUM ('user', 'employee', 'manager', 'operator');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE ticket_channel AS ENUM ('text', 'audio', 'chatbot');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE ticket_status AS ENUM (
    'unassigned', 'assigned', 'in_progress', 'resolved', 'overdue', 'escalated', 'submitted'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE approval_type AS ENUM ('rescore', 'reroute', 'other');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE issue_report_status AS ENUM ('received', 'in_review', 'resolved', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'whatsapp', 'push');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE notification_status AS ENUM ('queued', 'sent', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- -------------------------------
-- 2) MASTER DATA TABLES
-- -------------------------------
CREATE TABLE IF NOT EXISTS department (
  department_id   VARCHAR PRIMARY KEY,
  name            VARCHAR NOT NULL UNIQUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------
-- 3) USERS / EMPLOYEES / AUTH
-- -------------------------------
CREATE TABLE IF NOT EXISTS "user" (
  user_id     VARCHAR PRIMARY KEY,
  full_name   VARCHAR NOT NULL,
  phone_e164  VARCHAR NOT NULL,
  company     VARCHAR NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_phone ON "user"(phone_e164);
CREATE INDEX IF NOT EXISTS idx_user_company ON "user"(company);

CREATE TABLE IF NOT EXISTS employee (
  employee_id    VARCHAR PRIMARY KEY,
  department_id  VARCHAR NOT NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  full_name      VARCHAR NOT NULL,
  email          VARCHAR NOT NULL UNIQUE,
  role           VARCHAR NOT NULL,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_department ON employee(department_id);

CREATE TABLE IF NOT EXISTS app_account (
  account_id          VARCHAR PRIMARY KEY,
  linked_user_id      VARCHAR NULL REFERENCES "user"(user_id) ON UPDATE CASCADE,
  linked_employee_id  VARCHAR NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  email               VARCHAR NOT NULL UNIQUE,
  password_hash       VARCHAR NOT NULL,
  role                role_type NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at       TIMESTAMPTZ NULL,
  CONSTRAINT chk_account_single_link
    CHECK (
      (linked_user_id IS NOT NULL AND linked_employee_id IS NULL)
      OR (linked_user_id IS NULL AND linked_employee_id IS NOT NULL)
      OR (linked_user_id IS NULL AND linked_employee_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_account_role ON app_account(role);

CREATE TABLE IF NOT EXISTS password_reset_token (
  reset_id      VARCHAR PRIMARY KEY,
  account_id    VARCHAR NOT NULL REFERENCES app_account(account_id) ON DELETE CASCADE,
  token_hash    VARCHAR NOT NULL,
  requested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ NOT NULL,
  used_at       TIMESTAMPTZ NULL,
  resent_at     TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_reset_account ON password_reset_token(account_id);
CREATE INDEX IF NOT EXISTS idx_reset_expires ON password_reset_token(expires_at);

-- -------------------------------
-- 4) TICKETS
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket (
  ticket_id        VARCHAR PRIMARY KEY,
  user_id          VARCHAR NULL REFERENCES "user"(user_id) ON UPDATE CASCADE,
  employee_id      VARCHAR NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  subject          VARCHAR NOT NULL,
  title            VARCHAR NOT NULL,
  description      TEXT NULL,
  channel          ticket_channel NOT NULL,
  department       VARCHAR NOT NULL REFERENCES department(name) ON UPDATE CASCADE,
  priority         VARCHAR NOT NULL,
  status           ticket_status NOT NULL,
  submitted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at      TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_ticket_user ON ticket(user_id);
CREATE INDEX IF NOT EXISTS idx_ticket_employee ON ticket(employee_id);
CREATE INDEX IF NOT EXISTS idx_ticket_department ON ticket(department);
CREATE INDEX IF NOT EXISTS idx_ticket_status_priority ON ticket(status, priority);
CREATE INDEX IF NOT EXISTS idx_ticket_submitted ON ticket(submitted_at);
CREATE INDEX IF NOT EXISTS idx_ticket_updated ON ticket(last_updated_at);

-- -------------------------------
-- 5) SLA TABLE
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_sla (
  ticket_id            VARCHAR PRIMARY KEY REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  respond_due_at       TIMESTAMPTZ NOT NULL,
  resolve_due_at       TIMESTAMPTZ NOT NULL,
  respond_breached_at  TIMESTAMPTZ NULL,
  resolve_breached_at  TIMESTAMPTZ NULL,
  CONSTRAINT chk_sla_due_order CHECK (respond_due_at <= resolve_due_at)
);

CREATE INDEX IF NOT EXISTS idx_sla_respond_due ON ticket_sla(respond_due_at);
CREATE INDEX IF NOT EXISTS idx_sla_resolve_due ON ticket_sla(resolve_due_at);

-- -------------------------------
-- 6) STATUS + ASSIGNMENT HISTORY
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_status_history (
  history_id  VARCHAR PRIMARY KEY,
  ticket_id   VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  status      ticket_status NOT NULL,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_statushist_ticket_time ON ticket_status_history(ticket_id, changed_at);

CREATE TABLE IF NOT EXISTS ticket_assignment_history (
  assignment_id  VARCHAR PRIMARY KEY,
  ticket_id      VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  employee_id    VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  assigned_by    VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  assigned_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  note           TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_assign_ticket_time ON ticket_assignment_history(ticket_id, assigned_at);
CREATE INDEX IF NOT EXISTS idx_assign_employee ON ticket_assignment_history(employee_id);

-- -------------------------------
-- 7) WORKLOG
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_work_log (
  worklog_id    VARCHAR PRIMARY KEY,
  ticket_id     VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  employee_id   VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  step_no       INT NOT NULL,
  note          TEXT NOT NULL,
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_worklog_step UNIQUE(ticket_id, step_no),
  CONSTRAINT chk_step_positive CHECK (step_no > 0)
);

CREATE INDEX IF NOT EXISTS idx_worklog_ticket ON ticket_work_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_worklog_employee ON ticket_work_log(employee_id);

-- -------------------------------
-- 8) ATTACHMENTS
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_attachment (
  attachment_id     VARCHAR PRIMARY KEY,
  ticket_id         VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  file_name         VARCHAR NOT NULL,
  content_type      VARCHAR NOT NULL,
  size_bytes        BIGINT NULL,
  duration_seconds  INT NULL,
  storage_key       VARCHAR NULL,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_size_nonnegative CHECK (size_bytes IS NULL OR size_bytes >= 0),
  CONSTRAINT chk_duration_nonnegative CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS idx_attach_ticket ON ticket_attachment(ticket_id);
CREATE INDEX IF NOT EXISTS idx_attach_type ON ticket_attachment(content_type);

-- -------------------------------
-- 9) NOTIFICATIONS LOG
-- -------------------------------
CREATE TABLE IF NOT EXISTS notification_log (
  notification_id  VARCHAR PRIMARY KEY,
  ticket_id        VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  channel          notification_channel NOT NULL,
  status           notification_status NOT NULL,
  queued_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent_at          TIMESTAMPTZ NULL,
  error_message    TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_notify_ticket ON notification_log(ticket_id);
CREATE INDEX IF NOT EXISTS idx_notify_status ON notification_log(status);
CREATE INDEX IF NOT EXISTS idx_notify_queued ON notification_log(queued_at);

-- -------------------------------
-- 10) AI OUTPUT STORAGE
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_ai_result (
  ai_ticket_id            VARCHAR PRIMARY KEY,
  ticket_id               VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  predicted_department_id  VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  model_version            VARCHAR NULL,
  predicted_priority       VARCHAR NULL,
  confidence_score         NUMERIC NULL,
  priority_to_respond      INT NULL,
  priority_to_resolve      INT NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT chk_confidence_range CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),
  CONSTRAINT chk_priority_respond_range CHECK (priority_to_respond IS NULL OR (priority_to_respond BETWEEN 1 AND 5)),
  CONSTRAINT chk_priority_resolve_range CHECK (priority_to_resolve IS NULL OR (priority_to_resolve BETWEEN 1 AND 5))
);

CREATE INDEX IF NOT EXISTS idx_ai_ticket ON ticket_ai_result(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ai_created ON ticket_ai_result(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_dept ON ticket_ai_result(predicted_department_id);

-- -------------------------------
-- 11) MANAGER APPROVAL REQUESTS
-- -------------------------------
CREATE TABLE IF NOT EXISTS approval_request (
  request_id               VARCHAR PRIMARY KEY,
  ticket_id                VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  request_type             approval_type NOT NULL,
  current_value            VARCHAR NULL,
  requested_value          VARCHAR NULL,
  submitted_by_employee_id VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  submitted_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status                   approval_status NOT NULL DEFAULT 'pending',
  decided_at               TIMESTAMPTZ NULL,
  decision_note            TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_ticket ON approval_request(ticket_id);
CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_request(status);
CREATE INDEX IF NOT EXISTS idx_approval_submitter ON approval_request(submitted_by_employee_id);

-- -------------------------------
-- 12) ISSUE REPORTS
-- -------------------------------
CREATE TABLE IF NOT EXISTS issue_report (
  report_id     VARCHAR PRIMARY KEY,
  ticket_id     VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  submitted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status        issue_report_status NOT NULL DEFAULT 'received',
  details       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issuereport_ticket ON issue_report(ticket_id);
CREATE INDEX IF NOT EXISTS idx_issuereport_status ON issue_report(status);

CREATE TABLE IF NOT EXISTS ticket_issue_report (
  report_id               VARCHAR PRIMARY KEY,
  ticket_id               VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  submitted_by_user_id     VARCHAR NOT NULL REFERENCES "user"(user_id) ON UPDATE CASCADE,
  resolved_by_employee_id  VARCHAR NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  issue_text              TEXT NOT NULL,
  status                  issue_report_status NOT NULL DEFAULT 'received',
  submitted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at             TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_ticketissuereport_ticket ON ticket_issue_report(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticketissuereport_user ON ticket_issue_report(submitted_by_user_id);
CREATE INDEX IF NOT EXISTS idx_ticketissuereport_status ON ticket_issue_report(status);

-- -------------------------------
-- 13) AI REVIEW / OVERRIDES
-- -------------------------------
CREATE TABLE IF NOT EXISTS ticket_review (
  review_id                    VARCHAR PRIMARY KEY,
  ticket_id                    VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  model_routing_department_id   VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  final_routing_department_id   VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  customer_type                VARCHAR NULL,
  model_priority               VARCHAR NULL,
  final_priority               VARCHAR NULL,
  reason                       TEXT NULL,
  reviewed_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_ticket ON ticket_review(ticket_id);
CREATE INDEX IF NOT EXISTS idx_review_time ON ticket_review(reviewed_at);

-- -------------------------------
-- 14) CHATBOT TABLES
-- -------------------------------
CREATE TABLE IF NOT EXISTS chat_conversation (
  conversation_id  VARCHAR PRIMARY KEY,
  user_id          VARCHAR NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
  status           VARCHAR NOT NULL DEFAULT 'active',
  context          JSONB NULL,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON chat_conversation(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_created ON chat_conversation(created_at);

CREATE TABLE IF NOT EXISTS chat_message (
  message_id       VARCHAR PRIMARY KEY,
  conversation_id  VARCHAR NOT NULL REFERENCES chat_conversation(conversation_id) ON DELETE CASCADE,
  role             VARCHAR NOT NULL,
  text             TEXT NOT NULL,
  "timestamp"      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata         JSONB NULL
);

CREATE INDEX IF NOT EXISTS idx_msg_conv_time ON chat_message(conversation_id, "timestamp");

-- -------------------------------
-- 15) PERFORMANCE REPORTS
-- -------------------------------
CREATE TABLE IF NOT EXISTS employee_performance_report (
  report_id      VARCHAR PRIMARY KEY,
  employee_id    VARCHAR NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
  report_month   DATE NOT NULL,                        -- ✅ FIXED
  overall_rating INT NOT NULL CHECK (overall_rating BETWEEN 0 AND 100),
  generated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (employee_id, report_month)
);

CREATE INDEX IF NOT EXISTS idx_emp_report_employee ON employee_performance_report(employee_id);
CREATE INDEX IF NOT EXISTS idx_emp_report_month ON employee_performance_report(report_month);

CREATE TABLE IF NOT EXISTS performance_note (
  note_id      VARCHAR PRIMARY KEY,
  report_id    VARCHAR NOT NULL REFERENCES employee_performance_report(report_id) ON DELETE CASCADE,
  note_text    TEXT NOT NULL,
  created_by   VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_note_report ON performance_note(report_id);

-- -------------------------------
-- 16) SLA VIEW
-- -------------------------------
CREATE OR REPLACE VIEW v_ticket_sla_status AS
SELECT
  s.ticket_id,
  s.respond_due_at,
  s.resolve_due_at,
  s.respond_breached_at,
  s.resolve_breached_at,
  (s.respond_breached_at IS NOT NULL OR now() > s.respond_due_at) AS respond_breached_now,
  (s.resolve_breached_at IS NOT NULL OR now() > s.resolve_due_at) AS resolve_breached_now,
  ((s.respond_breached_at IS NOT NULL OR now() > s.respond_due_at)
    OR (s.resolve_breached_at IS NOT NULL OR now() > s.resolve_due_at)
  ) AS sla_breached_now
FROM ticket_sla s;

-- -------------------------------
-- 17) KPI & ANALYTICS VIEWS
-- -------------------------------
-- Ticket KPIs
CREATE OR REPLACE VIEW v_ticket_kpis AS
SELECT
  t.ticket_id,
  t.department,
  t.priority,
  t.status,
  t.submitted_at,
  t.resolved_at,
  CASE WHEN t.resolved_at IS NOT NULL THEN EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at))/3600 ELSE NULL END AS resolution_hours,
  (s.respond_breached_at IS NOT NULL) AS respond_sla_breached,
  (s.resolve_breached_at IS NOT NULL) AS resolve_sla_breached,
  ((s.respond_breached_at IS NOT NULL) OR (s.resolve_breached_at IS NOT NULL)) AS sla_breached
FROM ticket t
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id;

-- Employee KPIs
CREATE OR REPLACE VIEW v_employee_kpis AS
SELECT
  e.employee_id,
  e.full_name,
  e.department_id,
  COUNT(t.ticket_id) AS tickets_handled,
  COUNT(t.ticket_id) FILTER (WHERE t.status = 'resolved') AS tickets_resolved,
  AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at))/3600) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,
  COUNT(s.ticket_id) FILTER (WHERE s.respond_breached_at IS NOT NULL OR s.resolve_breached_at IS NOT NULL) AS sla_breaches,
  COUNT(h.ticket_id) FILTER (WHERE h.status = 'escalated') AS escalations
FROM employee e
LEFT JOIN ticket t ON t.employee_id = e.employee_id
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id
LEFT JOIN ticket_status_history h ON h.ticket_id = t.ticket_id
GROUP BY e.employee_id, e.full_name, e.department_id;

-- Department KPIs
CREATE OR REPLACE VIEW v_department_kpis AS
SELECT
  t.department,
  COUNT(*) AS total_tickets,
  COUNT(*) FILTER (WHERE t.status = 'resolved') AS resolved_tickets,
  ROUND(COUNT(*) FILTER (WHERE t.status = 'resolved')::NUMERIC / NULLIF(COUNT(*),0)*100, 2) AS resolution_rate_percent,
  AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at))/3600) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,
  COUNT(s.ticket_id) FILTER (WHERE s.respond_breached_at IS NOT NULL OR s.resolve_breached_at IS NOT NULL) AS sla_breaches
FROM ticket t
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id
GROUP BY t.department;

-- Monthly Employee KPIs (for reporting)
CREATE OR REPLACE VIEW v_employee_monthly_kpis AS
SELECT
  e.employee_id,
  date_trunc('month', t.submitted_at)::date AS report_month,  -- ✅ Fixed type
  COUNT(t.ticket_id) AS tickets_handled,
  COUNT(t.ticket_id) FILTER (WHERE t.status = 'resolved') AS tickets_resolved,
  AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at))/3600) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,
  COUNT(s.ticket_id) FILTER (WHERE s.respond_breached_at IS NOT NULL OR s.resolve_breached_at IS NOT NULL) AS sla_breaches
FROM employee e
LEFT JOIN ticket t ON t.employee_id = e.employee_id
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id
GROUP BY e.employee_id, report_month;

-- ============================================================
-- 1) DEPARTMENTS
-- ============================================================
INSERT INTO department (department_id, name)
VALUES
('D001', 'Customer Service'),
('D002', 'Technical Support'),
('D003', 'Billing'),
('D004', 'IT'),
('D005', 'Logistics'),
('D006', 'HR'),
('D007', 'Operations'),
('D008', 'Sales'),
('D009', 'Marketing'),
('D010', 'Quality Assurance');

-- ============================================================
-- 2) USERS
-- ============================================================
INSERT INTO "user" (user_id, full_name, phone_e164, company)
VALUES
('U001', 'Alice Johnson', '+971501234001', 'InnovaCorp'),
('U002', 'Bob Smith', '+971501234002', 'InnovaCorp'),
('U003', 'Carol Lee', '+971501234003', 'InnovaCorp'),
('U004', 'David Kim', '+971501234004', 'InnovaCorp'),
('U005', 'Eva Wong', '+971501234005', 'InnovaCorp'),
('U006', 'Frank Miller', '+971501234006', 'InnovaCorp'),
('U007', 'Grace Tan', '+971501234007', 'InnovaCorp'),
('U008', 'Henry Ford', '+971501234008', 'InnovaCorp'),
('U009', 'Isla Moore', '+971501234009', 'InnovaCorp'),
('U010', 'Jack White', '+971501234010', 'InnovaCorp');

-- ============================================================
-- 3) EMPLOYEES
-- ============================================================
INSERT INTO employee (employee_id, department_id, full_name, email, role)
VALUES
('E001', 'D001', 'Sam Parker', 'sam.parker@innovacx.com', 'operator'),
('E002', 'D002', 'Lily Evans', 'lily.evans@innovacx.com', 'operator'),
('E003', 'D003', 'Tom Hardy', 'tom.hardy@innovacx.com', 'manager'),
('E004', 'D004', 'Nina Brown', 'nina.brown@innovacx.com', 'employee'),
('E005', 'D005', 'Oscar Grant', 'oscar.grant@innovacx.com', 'employee'),
('E006', 'D006', 'Pamela Lee', 'pamela.lee@innovacx.com', 'manager'),
('E007', 'D007', 'Quinn Davis', 'quinn.davis@innovacx.com', 'operator'),
('E008', 'D008', 'Rachel Green', 'rachel.green@innovacx.com', 'employee'),
('E009', 'D009', 'Steve Jobs', 'steve.jobs@innovacx.com', 'manager'),
('E010', 'D010', 'Tracy Morgan', 'tracy.morgan@innovacx.com', 'operator');

-- ============================================================
-- 4) APP ACCOUNTS
-- ============================================================
INSERT INTO app_account (account_id, linked_user_id, linked_employee_id, email, password_hash, role)
VALUES
('A001', 'U001', NULL, 'alice.johnson@innova.com', 'hash1', 'user'),
('A002', 'U002', NULL, 'bob.smith@innova.com', 'hash2', 'user'),
('A003', NULL, 'E001', 'sam.parker@innovacx.com', 'hash3', 'operator'),
('A004', NULL, 'E002', 'lily.evans@innovacx.com', 'hash4', 'operator'),
('A005', NULL, 'E003', 'tom.hardy@innovacx.com', 'hash5', 'manager'),
('A006', 'U003', NULL, 'carol.lee@innova.com', 'hash6', 'user'),
('A007', NULL, 'E004', 'nina.brown@innovacx.com', 'hash7', 'employee'),
('A008', 'U004', NULL, 'david.kim@innova.com', 'hash8', 'user'),
('A009', NULL, 'E005', 'oscar.grant@innovacx.com', 'hash9', 'employee'),
('A010', NULL, 'E006', 'pamela.lee@innovacx.com', 'hash10', 'manager');

-- ============================================================
-- 5) TICKETS
-- ============================================================
INSERT INTO ticket (ticket_id, user_id, employee_id, subject, title, description, channel, department, priority, status, submitted_at)
VALUES
('T001', 'U001', 'E001', 'Login Issue', 'Cannot login', 'User cannot login to account', 'text', 'Customer Service', 'High', 'submitted', NOW()),
('T002', 'U002', 'E002', 'Payment Failure', 'Payment did not go through', 'Transaction failed multiple times', 'chatbot', 'Billing', 'High', 'submitted', NOW()),
('T003', 'U003', 'E003', 'Software Bug', 'App crashes', 'App crashes on opening', 'text', 'IT', 'Medium', 'submitted', NOW()),
('T004', 'U004', 'E004', 'Late Delivery', 'Package delayed', 'Delivery expected 3 days ago', 'audio', 'Logistics', 'High', 'submitted', NOW()),
('T005', 'U005', 'E005', 'Refund Request', 'Requesting refund', 'Refund not processed', 'text', 'Billing', 'Medium', 'submitted', NOW()),
('T006', 'U006', 'E006', 'Account Update', 'Update profile info', 'User wants to update info', 'chatbot', 'Customer Service', 'Low', 'submitted', NOW()),
('T007', 'U007', 'E007', 'Technical Query', 'Issue with device', 'Device not working properly', 'text', 'Technical Support', 'High', 'submitted', NOW()),
('T008', 'U008', 'E008', 'Complaint', 'Service not satisfactory', 'User complains about service', 'audio', 'Customer Service', 'Medium', 'submitted', NOW()),
('T009', 'U009', 'E009', 'Password Reset', 'Reset password issue', 'Cannot reset password', 'chatbot', 'IT', 'High', 'submitted', NOW()),
('T010', 'U010', 'E010', 'Order Error', 'Wrong product delivered', 'User received wrong item', 'text', 'Logistics', 'High', 'submitted', NOW());

-- ============================================================
-- 6) TICKET SLA
-- ============================================================
INSERT INTO ticket_sla (ticket_id, respond_due_at, resolve_due_at)
VALUES
('T001', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '24 hours'),
('T002', NOW() + INTERVAL '1 hour', NOW() + INTERVAL '12 hours'),
('T003', NOW() + INTERVAL '3 hours', NOW() + INTERVAL '36 hours'),
('T004', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '24 hours'),
('T005', NOW() + INTERVAL '1 hour', NOW() + INTERVAL '24 hours'),
('T006', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '48 hours'),
('T007', NOW() + INTERVAL '1 hour', NOW() + INTERVAL '12 hours'),
('T008', NOW() + INTERVAL '3 hours', NOW() + INTERVAL '24 hours'),
('T009', NOW() + INTERVAL '2 hours', NOW() + INTERVAL '24 hours'),
('T010', NOW() + INTERVAL '1 hour', NOW() + INTERVAL '12 hours');

-- ============================================================
-- 7) TICKET STATUS HISTORY
-- ============================================================
INSERT INTO ticket_status_history (history_id, ticket_id, status, changed_at)
VALUES
('TSH001', 'T001', 'submitted', NOW()),
('TSH002', 'T002', 'submitted', NOW()),
('TSH003', 'T003', 'submitted', NOW()),
('TSH004', 'T004', 'submitted', NOW()),
('TSH005', 'T005', 'submitted', NOW()),
('TSH006', 'T006', 'submitted', NOW()),
('TSH007', 'T007', 'submitted', NOW()),
('TSH008', 'T008', 'submitted', NOW()),
('TSH009', 'T009', 'submitted', NOW()),
('TSH010', 'T010', 'submitted', NOW());

-- ============================================================
-- 8) TICKET ASSIGNMENT HISTORY
-- ============================================================
INSERT INTO ticket_assignment_history (assignment_id, ticket_id, employee_id, assigned_by, assigned_at)
VALUES
('TAH001', 'T001', 'E001', 'E003', NOW()),
('TAH002', 'T002', 'E002', 'E003', NOW()),
('TAH003', 'T003', 'E004', 'E006', NOW()),
('TAH004', 'T004', 'E005', 'E006', NOW()),
('TAH005', 'T005', 'E005', 'E003', NOW()),
('TAH006', 'T006', 'E006', 'E006', NOW()),
('TAH007', 'T007', 'E007', 'E003', NOW()),
('TAH008', 'T008', 'E008', 'E006', NOW()),
('TAH009', 'T009', 'E009', 'E009', NOW()),
('TAH010', 'T010', 'E010', 'E009', NOW());

-- ============================================================
-- 9) TICKET WORK LOG
-- ============================================================
INSERT INTO ticket_work_log (worklog_id, ticket_id, employee_id, step_no, note, occurred_at)
VALUES
('TW001', 'T001', 'E001', 1, 'Initial investigation', NOW()),
('TW002', 'T002', 'E002', 1, 'Checked payment logs', NOW()),
('TW003', 'T003', 'E004', 1, 'Reproduced crash', NOW()),
('TW004', 'T004', 'E005', 1, 'Contacted delivery partner', NOW()),
('TW005', 'T005', 'E005', 1, 'Verified refund request', NOW()),
('TW006', 'T006', 'E006', 1, 'Updated profile info', NOW()),
('TW007', 'T007', 'E007', 1, 'Checked device', NOW()),
('TW008', 'T008', 'E008', 1, 'Reviewed complaint', NOW()),
('TW009', 'T009', 'E009', 1, 'Reset password', NOW()),
('TW010', 'T010', 'E010', 1, 'Reported wrong item', NOW());

-- ============================================================
-- 10) TICKET ATTACHMENTS
-- ============================================================
INSERT INTO ticket_attachment (attachment_id, ticket_id, file_name, content_type, size_bytes, storage_key)
VALUES
('ATT001', 'T001', 'screenshot1.png', 'image/png', 120000, 's3://ticket/T001/screenshot1.png'),
('ATT002', 'T002', 'payment_log.pdf', 'application/pdf', 500000, 's3://ticket/T002/payment_log.pdf'),
('ATT003', 'T003', 'crash_video.mp4', 'video/mp4', 2000000, 's3://ticket/T003/crash_video.mp4'),
('ATT004', 'T004', 'delivery_photo.jpg', 'image/jpeg', 150000, 's3://ticket/T004/delivery_photo.jpg'),
('ATT005', 'T005', 'refund_request.pdf', 'application/pdf', 400000, 's3://ticket/T005/refund_request.pdf'),
('ATT006', 'T006', 'profile_update.png', 'image/png', 100000, 's3://ticket/T006/profile_update.png'),
('ATT007', 'T007', 'device_error.jpg', 'image/jpeg', 180000, 's3://ticket/T007/device_error.jpg'),
('ATT008', 'T008', 'complaint_audio.mp3', 'audio/mpeg', 300000, 's3://ticket/T008/complaint_audio.mp3'),
('ATT009', 'T009', 'password_reset.png', 'image/png', 90000, 's3://ticket/T009/password_reset.png'),
('ATT010', 'T010', 'wrong_item.jpg', 'image/jpeg', 200000, 's3://ticket/T010/wrong_item.jpg');

-- ============================================================
-- Additional 30 tickets for employee E001 (for testing analytics)
-- ============================================================
INSERT INTO ticket (ticket_id, user_id, employee_id, subject, title, description, channel, department, priority, status, submitted_at)
VALUES
('T011', 'U001', 'E001', 'Password Reset', 'Cannot reset password', 'User cannot reset password via portal', 'text', 'Customer Service', 'High', 'resolved', NOW() - INTERVAL '30 days'),
('T012', 'U002', 'E001', 'Login Issue', 'Login fails', 'User login fails intermittently', 'chatbot', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '29 days'),
('T013', 'U003', 'E001', 'Payment Issue', 'Payment declined', 'Payment declined at checkout', 'text', 'Billing', 'High', 'resolved', NOW() - INTERVAL '28 days'),
('T014', 'U004', 'E001', 'Late Response', 'Support delayed', 'User waited too long for support', 'audio', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '27 days'),
('T015', 'U005', 'E001', 'Refund Issue', 'Refund not processed', 'Refund request pending for 3 days', 'text', 'Billing', 'High', 'resolved', NOW() - INTERVAL '26 days'),
('T016', 'U006', 'E001', 'App Crash', 'App crashes on launch', 'App crashes when opening', 'chatbot', 'IT', 'High', 'resolved', NOW() - INTERVAL '25 days'),
('T017', 'U007', 'E001', 'Incorrect Bill', 'Billing error', 'User received wrong bill', 'text', 'Billing', 'Medium', 'resolved', NOW() - INTERVAL '24 days'),
('T018', 'U008', 'E001', 'Delivery Issue', 'Package delayed', 'Delivery delayed by 5 days', 'audio', 'Logistics', 'High', 'resolved', NOW() - INTERVAL '23 days'),
('T019', 'U009', 'E001', 'Account Locked', 'Account locked out', 'User cannot access account', 'text', 'Customer Service', 'High', 'resolved', NOW() - INTERVAL '22 days'),
('T020', 'U010', 'E001', 'Feature Request', 'Request new feature', 'User requested dark mode', 'chatbot', 'IT', 'Low', 'resolved', NOW() - INTERVAL '21 days'),
('T021', 'U001', 'E001', 'Incorrect Info', 'Wrong details shown', 'User sees incorrect account info', 'text', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '20 days'),
('T022', 'U002', 'E001', 'Login Timeout', 'Session timeout', 'User gets logged out too quickly', 'chatbot', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '19 days'),
('T023', 'U003', 'E001', 'Refund Delay', 'Refund delayed', 'Refund has not been processed', 'text', 'Billing', 'High', 'resolved', NOW() - INTERVAL '18 days'),
('T024', 'U004', 'E001', 'App Update Error', 'Cannot update app', 'Update fails with error', 'chatbot', 'IT', 'High', 'resolved', NOW() - INTERVAL '17 days'),
('T025', 'U005', 'E001', 'Ticket Lost', 'Ticket missing', 'User ticket disappeared from portal', 'text', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '16 days'),
('T026', 'U006', 'E001', 'Wrong Delivery', 'Package sent to wrong address', 'User received wrong item', 'audio', 'Logistics', 'High', 'resolved', NOW() - INTERVAL '15 days'),
('T027', 'U007', 'E001', 'Password Reset', 'Cannot reset password', 'Reset link invalid', 'text', 'Customer Service', 'High', 'resolved', NOW() - INTERVAL '14 days'),
('T028', 'U008', 'E001', 'Slow Response', 'Support too slow', 'Customer service response slow', 'chatbot', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '13 days'),
('T029', 'U009', 'E001', 'App Bug', 'UI glitch', 'App UI not showing correctly', 'text', 'IT', 'Medium', 'resolved', NOW() - INTERVAL '12 days'),
('T030', 'U010', 'E001', 'Billing Error', 'Extra charges', 'User billed twice', 'text', 'Billing', 'High', 'resolved', NOW() - INTERVAL '11 days'),
('T031', 'U001', 'E001', 'Late Refund', 'Refund overdue', 'Refund request overdue by 2 days', 'text', 'Billing', 'Medium', 'resolved', NOW() - INTERVAL '10 days'),
('T032', 'U002', 'E001', 'App Crash', 'App freezes', 'App freezes on checkout', 'chatbot', 'IT', 'High', 'resolved', NOW() - INTERVAL '9 days'),
('T033', 'U003', 'E001', 'Login Issue', 'Cannot login', 'User login fails multiple attempts', 'text', 'Customer Service', 'High', 'resolved', NOW() - INTERVAL '8 days'),
('T034', 'U004', 'E001', 'Delivery Delay', 'Late package', 'Delivery delayed by 4 days', 'audio', 'Logistics', 'Medium', 'resolved', NOW() - INTERVAL '7 days'),
('T035', 'U005', 'E001', 'Refund Request', 'Request not processed', 'Refund request still pending', 'text', 'Billing', 'High', 'resolved', NOW() - INTERVAL '6 days'),
('T036', 'U006', 'E001', 'App Error', 'App crashes', 'App crashes when logging in', 'chatbot', 'IT', 'High', 'resolved', NOW() - INTERVAL '5 days'),
('T037', 'U007', 'E001', 'Wrong Info', 'Incorrect account info', 'Account shows wrong info', 'text', 'Customer Service', 'Medium', 'resolved', NOW() - INTERVAL '4 days'),
('T038', 'U008', 'E001', 'Delivery Issue', 'Package missing', 'User did not receive package', 'audio', 'Logistics', 'High', 'resolved', NOW() - INTERVAL '3 days'),
('T039', 'U009', 'E001', 'Account Locked', 'Cannot login', 'Account locked unexpectedly', 'text', 'Customer Service', 'High', 'resolved', NOW() - INTERVAL '2 days'),
('T040', 'U010', 'E001', 'Feature Request', 'Request new feature', 'User requested additional report', 'chatbot', 'IT', 'Low', 'resolved', NOW() - INTERVAL '1 day');

-- ============================================================
-- Additional SLA for E001 tickets
-- ============================================================
INSERT INTO ticket_sla (ticket_id, respond_due_at, resolve_due_at)
SELECT ticket_id, submitted_at + INTERVAL '2 hours', submitted_at + INTERVAL '24 hours'
FROM ticket
WHERE employee_id = 'E001' AND ticket_id BETWEEN 'T011' AND 'T040';

-- ============================================================
-- Additional Status History for E001 tickets
-- ============================================================
INSERT INTO ticket_status_history (history_id, ticket_id, status, changed_at)
SELECT 'TSH' || LPAD(ROW_NUMBER() OVER (), 3, '0') + 10, ticket_id, 'submitted', submitted_at
FROM ticket
WHERE employee_id = 'E001' AND ticket_id BETWEEN 'T011' AND 'T040';

-- ============================================================
-- Additional Work Logs for E001 tickets
-- ============================================================
INSERT INTO ticket_work_log (worklog_id, ticket_id, employee_id, step_no, note, occurred_at)
SELECT 'TW' || LPAD(ROW_NUMBER() OVER (), 3, '0') + 10, ticket_id, 'E001', 1, 'Initial investigation', submitted_at
FROM ticket
WHERE employee_id = 'E001' AND ticket_id BETWEEN 'T011' AND 'T040';
