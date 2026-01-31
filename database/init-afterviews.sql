/* ============================================================
   AI Complaint Management System - PostgreSQL Schema (DDL)
   ============================================================ */

-- -------------------------------
-- Create dedicated schema
-- -------------------------------
CREATE SCHEMA IF NOT EXISTS cms;
SET search_path TO cms;

-- -------------------------------
-- 1) ENUM TYPES (prevents bad values)
-- -------------------------------

-- System login roles used by AppAccount
DO $$ BEGIN
  CREATE TYPE role_type AS ENUM ('user', 'employee', 'manager', 'operator');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Ticket channel
DO $$ BEGIN
  CREATE TYPE ticket_channel AS ENUM ('text', 'audio', 'chatbot');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Ticket lifecycle statuses 
DO $$ BEGIN
  CREATE TYPE ticket_status AS ENUM (
    'unassigned',
    'assigned',
    'in_progress',
    'resolved',
    'overdue',
    'escalated',
    'submitted'
  );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Approval workflow
DO $$ BEGIN
  CREATE TYPE approval_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE approval_type AS ENUM ('rescore', 'reroute', 'other');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Issue report workflow
DO $$ BEGIN
  CREATE TYPE issue_report_status AS ENUM ('received', 'in_review', 'resolved', 'rejected');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Notifications
DO $$ BEGIN
  CREATE TYPE notification_channel AS ENUM ('email', 'sms', 'whatsapp', 'push');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE notification_status AS ENUM ('queued', 'sent', 'failed');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- -------------------------------
-- 2) MASTER DATA TABLES
-- -------------------------------

/* Department: used for employee organization and AI routing/reviews */
CREATE TABLE IF NOT EXISTS department (
  department_id   VARCHAR PRIMARY KEY,        -- e.g. "DPT-01"
  name            VARCHAR NOT NULL UNIQUE,     -- unique so it can be referenced safely
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------
-- 3) USERS / EMPLOYEES / AUTH
-- -------------------------------

/* End users raising complaints */
CREATE TABLE IF NOT EXISTS "user" (
  user_id     VARCHAR PRIMARY KEY,            -- e.g. "USR-501"
  full_name   VARCHAR NOT NULL,
  phone_e164  VARCHAR NOT NULL,               -- e.g. +971501234567
  company     VARCHAR NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_phone ON "user"(phone_e164);
CREATE INDEX IF NOT EXISTS idx_user_company ON "user"(company);

/* Internal employees (technicians, supervisors, managers, etc.) */
CREATE TABLE IF NOT EXISTS employee (
  employee_id    VARCHAR PRIMARY KEY,         -- e.g. "EMP-1023"
  department_id  VARCHAR NOT NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  full_name      VARCHAR NOT NULL,
  email          VARCHAR NOT NULL UNIQUE,
  role           VARCHAR NOT NULL,             -- job title e.g. Technician, Supervisor
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_employee_department ON employee(department_id);

/* Authentication account (login + role-based access)
   - links to either a user or an employee based on role
   - password is stored as a hash (never plain text)
*/
CREATE TABLE IF NOT EXISTS app_account (
  account_id          VARCHAR PRIMARY KEY,    -- e.g. "ACC-1001"
  linked_user_id      VARCHAR NULL REFERENCES "user"(user_id) ON UPDATE CASCADE,
  linked_employee_id  VARCHAR NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  email               VARCHAR NOT NULL UNIQUE,
  password_hash       VARCHAR NOT NULL,
  role                role_type NOT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at       TIMESTAMPTZ NULL,

  -- Ensure an account links to at most one identity row
  CONSTRAINT chk_account_single_link
    CHECK (
      (linked_user_id IS NOT NULL AND linked_employee_id IS NULL)
      OR
      (linked_user_id IS NULL AND linked_employee_id IS NOT NULL)
      OR
      (linked_user_id IS NULL AND linked_employee_id IS NULL) -- allow for operator accounts if you want no link
    )
);

CREATE INDEX IF NOT EXISTS idx_account_role ON app_account(role);

/* Password reset tokens for forgot-password and resend-reset */
CREATE TABLE IF NOT EXISTS password_reset_token (
  reset_id      VARCHAR PRIMARY KEY,          -- e.g. "RST-9001"
  account_id    VARCHAR NOT NULL REFERENCES app_account(account_id) ON DELETE CASCADE,
  token_hash    VARCHAR NOT NULL,             -- store hashed token
  requested_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at    TIMESTAMPTZ NOT NULL,
  used_at       TIMESTAMPTZ NULL,
  resent_at     TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_reset_account ON password_reset_token(account_id);
CREATE INDEX IF NOT EXISTS idx_reset_expires ON password_reset_token(expires_at);

-- -------------------------------
-- 4) TICKETS (COMPLAINTS)
-- -------------------------------

/* Ticket = complaint record */
CREATE TABLE IF NOT EXISTS ticket (
  ticket_id        VARCHAR PRIMARY KEY,       -- e.g. "CX-1122"
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
-- 5) SLA TABLE (timestamps are STORED; booleans are derived in queries)
-- -------------------------------

/* TicketSLA stores SLA deadlines + breach timestamps */
CREATE TABLE IF NOT EXISTS ticket_sla (
  ticket_id            VARCHAR PRIMARY KEY REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  respond_due_at       TIMESTAMPTZ NOT NULL,
  resolve_due_at       TIMESTAMPTZ NOT NULL,
  respond_breached_at  TIMESTAMPTZ NULL,
  resolve_breached_at  TIMESTAMPTZ NULL,

  -- note: response due should not be after resolve due (usually)
  CONSTRAINT chk_sla_due_order CHECK (respond_due_at <= resolve_due_at)
);

CREATE INDEX IF NOT EXISTS idx_sla_respond_due ON ticket_sla(respond_due_at);
CREATE INDEX IF NOT EXISTS idx_sla_resolve_due ON ticket_sla(resolve_due_at);

-- -------------------------------
-- 6) STATUS + ASSIGNMENT HISTORY
-- -------------------------------

/* TicketStatusHistory: timeline for status changes */
CREATE TABLE IF NOT EXISTS ticket_status_history (
  history_id  VARCHAR PRIMARY KEY,            -- e.g. "HIS-8001"
  ticket_id   VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  status      ticket_status NOT NULL,
  changed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_statushist_ticket_time ON ticket_status_history(ticket_id, changed_at);

/* TicketAssignmentHistory: manager assign/reassign tracking */
CREATE TABLE IF NOT EXISTS ticket_assignment_history (
  assignment_id  VARCHAR PRIMARY KEY,         -- e.g. "ASN-5001"
  ticket_id      VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  employee_id    VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,  -- assigned to
  assigned_by    VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,  -- assigned by (manager/supervisor)
  assigned_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  note           TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_assign_ticket_time ON ticket_assignment_history(ticket_id, assigned_at);
CREATE INDEX IF NOT EXISTS idx_assign_employee ON ticket_assignment_history(employee_id);

-- -------------------------------
-- 7) WORKLOG (steps taken)
-- -------------------------------

/* TicketWorkLog: steps/notes added by employees while working the ticket */
CREATE TABLE IF NOT EXISTS ticket_work_log (
  worklog_id    VARCHAR PRIMARY KEY,          -- e.g. "WLG-6001"
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
-- 8) ATTACHMENTS (audio/images/files)
-- -------------------------------

/* TicketAttachment: store any file attached to a ticket */
CREATE TABLE IF NOT EXISTS ticket_attachment (
  attachment_id     VARCHAR PRIMARY KEY,      -- e.g. "ATT-9101"
  ticket_id         VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  file_name         VARCHAR NOT NULL,
  content_type      VARCHAR NOT NULL,          -- e.g. audio/webm, image/jpeg
  size_bytes        BIGINT NULL,
  duration_seconds  INT NULL,                  -- for audio/video only
  storage_key       VARCHAR NULL,              -- where file is stored (S3 key/path)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_size_nonnegative CHECK (size_bytes IS NULL OR size_bytes >= 0),
  CONSTRAINT chk_duration_nonnegative CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
);

CREATE INDEX IF NOT EXISTS idx_attach_ticket ON ticket_attachment(ticket_id);
CREATE INDEX IF NOT EXISTS idx_attach_type ON ticket_attachment(content_type);

-- -------------------------------
-- 9) NOTIFICATIONS LOG
-- -------------------------------

/* NotificationLog: tracks email/SMS/etc queue + delivery outcomes */
CREATE TABLE IF NOT EXISTS notification_log (
  notification_id  VARCHAR PRIMARY KEY,       -- e.g. "NTF-4001"
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
-- 10) AI OUTPUT STORAGE (for analytics + rescore/reroute)
-- -------------------------------

/* TicketAIResult: persists model predictions + confidence for each ticket */
CREATE TABLE IF NOT EXISTS ticket_ai_result (
  ai_ticket_id            VARCHAR PRIMARY KEY,  -- e.g. "AIR-3001"
  ticket_id               VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  predicted_department_id  VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  model_version            VARCHAR NULL,
  predicted_priority       VARCHAR NULL,          
  confidence_score         NUMERIC NULL,         
  priority_to_respond      INT NULL,
  priority_to_resolve      INT NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_confidence_range
    CHECK (confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)),

  CONSTRAINT chk_priority_respond_range
    CHECK (priority_to_respond IS NULL OR (priority_to_respond BETWEEN 1 AND 5)),

  CONSTRAINT chk_priority_resolve_range
    CHECK (priority_to_resolve IS NULL OR (priority_to_resolve BETWEEN 1 AND 5))
);

CREATE INDEX IF NOT EXISTS idx_ai_ticket ON ticket_ai_result(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ai_created ON ticket_ai_result(created_at);
CREATE INDEX IF NOT EXISTS idx_ai_dept ON ticket_ai_result(predicted_department_id);

-- -------------------------------
-- 11) MANAGER APPROVAL REQUESTS
-- -------------------------------

/* ApprovalRequest: employee submits; manager approves/rejects */
CREATE TABLE IF NOT EXISTS approval_request (
  request_id               VARCHAR PRIMARY KEY,      -- e.g. "REQ-3101"
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

/* IssueReport: generic report table */
CREATE TABLE IF NOT EXISTS issue_report (
  report_id     VARCHAR PRIMARY KEY,              -- e.g. "RPT-7001"
  ticket_id     VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  submitted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status        issue_report_status NOT NULL DEFAULT 'received',
  details       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_issuereport_ticket ON issue_report(ticket_id);
CREATE INDEX IF NOT EXISTS idx_issuereport_status ON issue_report(status);

/* TicketIssueReport: more detailed issue reports (user submitted + resolver) */
CREATE TABLE IF NOT EXISTS ticket_issue_report (
  report_id               VARCHAR PRIMARY KEY,   -- e.g. "RPT-7100"
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
-- 13) AI REVIEW / OVERRIDES (operator analytics)
-- -------------------------------

/* TicketReview: stores model vs final decisions (audit + analytics) */
CREATE TABLE IF NOT EXISTS ticket_review (
  review_id                    VARCHAR PRIMARY KEY,   -- e.g. "REV-8801"
  ticket_id                    VARCHAR NOT NULL REFERENCES ticket(ticket_id) ON DELETE CASCADE,
  model_routing_department_id   VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  final_routing_department_id   VARCHAR NULL REFERENCES department(department_id) ON UPDATE CASCADE,
  customer_type                VARCHAR NULL,          -- Tenant, Vendor, etc.
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

/* ChatConversation: one chat thread per user session */
CREATE TABLE IF NOT EXISTS chat_conversation (
  conversation_id  VARCHAR PRIMARY KEY,        -- e.g. "CONV-1001"
  user_id          VARCHAR NOT NULL REFERENCES "user"(user_id) ON DELETE CASCADE,
  status           VARCHAR NOT NULL DEFAULT 'active', -- active/closed
  context          JSONB NULL,                 -- stores collected fields (e.g. location)
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conv_user ON chat_conversation(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_created ON chat_conversation(created_at);

/* ChatMessage: stores the messages in each conversation */
CREATE TABLE IF NOT EXISTS chat_message (
  message_id       VARCHAR PRIMARY KEY,        -- e.g. "MSG-2001"
  conversation_id  VARCHAR NOT NULL REFERENCES chat_conversation(conversation_id) ON DELETE CASCADE,
  role             VARCHAR NOT NULL,           -- "user" or "bot"
  text             TEXT NOT NULL,
  "timestamp"      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  metadata         JSONB NULL                  -- suggestedReplies, nextAction, intent, etc.
);

CREATE INDEX IF NOT EXISTS idx_msg_conv_time ON chat_message(conversation_id, "timestamp");

-- -------------------------------
-- 15) PERFORMANCE REPORTS
-- -------------------------------

/* EmployeePerformanceReport: monthly snapshot report used by employee/manager dashboards */
CREATE TABLE IF NOT EXISTS employee_performance_report (
  report_id        VARCHAR PRIMARY KEY,        -- e.g. "RPT-EMP-2025-10-EMP-1023"
  employee_id      VARCHAR NOT NULL REFERENCES employee(employee_id) ON DELETE CASCADE,
  report_month     VARCHAR NOT NULL,           -- "YYYY-MM"
  overall_rating   INT NOT NULL,
  generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  report_payload   JSONB NULL,

  CONSTRAINT uq_employee_month UNIQUE(employee_id, report_month),
  CONSTRAINT chk_overall_rating CHECK (overall_rating BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS idx_emp_report_employee ON employee_performance_report(employee_id);
CREATE INDEX IF NOT EXISTS idx_emp_report_month ON employee_performance_report(report_month);

/* PerformanceNote: manager notes on performance reports */
CREATE TABLE IF NOT EXISTS performance_note (
  note_id      VARCHAR PRIMARY KEY,
  report_id    VARCHAR NOT NULL REFERENCES employee_performance_report(report_id) ON DELETE CASCADE,
  note_text    TEXT NOT NULL,
  created_by   VARCHAR NOT NULL REFERENCES employee(employee_id) ON UPDATE CASCADE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_perf_note_report ON performance_note(report_id);

-- ============================================================
-- 16) OPTIONAL: Helpful VIEW for SLA booleans (derived at query time)
-- ============================================================

/* This view returns SLA status flags without storing them in the table */
CREATE OR REPLACE VIEW v_ticket_sla_status AS
SELECT
  s.ticket_id,
  s.respond_due_at,
  s.resolve_due_at,
  s.respond_breached_at,
  s.resolve_breached_at,

  /* derived flags */
  (s.respond_breached_at IS NOT NULL OR now() > s.respond_due_at) AS respond_breached_now,
  (s.resolve_breached_at IS NOT NULL OR now() > s.resolve_due_at) AS resolve_breached_now,
  ( (s.respond_breached_at IS NOT NULL OR now() > s.respond_due_at)
    OR
    (s.resolve_breached_at IS NOT NULL OR now() > s.resolve_due_at)
  ) AS sla_breached_now
FROM ticket_sla s;

-- ============================================================
-- End of schema
-- ============================================================

-- ============================================================
-- 17) KPI & ANALYTICS VIEWS
-- (Read-only views for dashboards, reports, and analytics)
-- ============================================================

-- ------------------------------------------------------------
-- 1) Ticket-level KPI view
-- Purpose:
-- - Per-ticket analytics
-- - SLA tracking
-- - Resolution time calculations
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_ticket_kpis AS
SELECT
  t.ticket_id,
  t.department,
  t.priority,
  t.status,

  t.submitted_at,
  t.resolved_at,

  -- Resolution time in hours
  CASE
    WHEN t.resolved_at IS NOT NULL
    THEN EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at)) / 3600
    ELSE NULL
  END AS resolution_hours,

  -- SLA flags
  (s.respond_breached_at IS NOT NULL) AS respond_sla_breached,
  (s.resolve_breached_at IS NOT NULL) AS resolve_sla_breached,

  -- Overall SLA breach flag
  (
    s.respond_breached_at IS NOT NULL
    OR s.resolve_breached_at IS NOT NULL
  ) AS sla_breached

FROM ticket t
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id;


-- ------------------------------------------------------------
-- 2) Employee KPI view
-- Purpose:
-- - Employee performance dashboards
-- - SLA + escalation tracking
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_employee_kpis AS
SELECT
  e.employee_id,
  e.full_name,
  e.department_id,

  COUNT(t.ticket_id) AS tickets_handled,

  COUNT(t.ticket_id)
    FILTER (WHERE t.status = 'resolved') AS tickets_resolved,

  -- Average resolution time (hours)
  AVG(
    EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at)) / 3600
  ) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,

  -- SLA breaches count
  COUNT(s.ticket_id)
    FILTER (
      WHERE s.respond_breached_at IS NOT NULL
         OR s.resolve_breached_at IS NOT NULL
    ) AS sla_breaches,

  -- Escalation count
  COUNT(h.ticket_id)
    FILTER (WHERE h.status = 'escalated') AS escalations

FROM employee e
LEFT JOIN ticket t ON t.employee_id = e.employee_id
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id
LEFT JOIN ticket_status_history h ON h.ticket_id = t.ticket_id

GROUP BY e.employee_id, e.full_name, e.department_id;


-- ------------------------------------------------------------
-- 3) Department KPI view
-- Purpose:
-- - Department-level dashboards
-- - Management overview
-- ------------------------------------------------------------
CREATE OR REPLACE VIEW v_department_kpis AS
SELECT
  t.department,

  COUNT(*) AS total_tickets,

  COUNT(*)
    FILTER (WHERE t.status = 'resolved') AS resolved_tickets,

  -- Resolution rate (%)
  ROUND(
    COUNT(*) FILTER (WHERE t.status = 'resolved')::NUMERIC
    / NULLIF(COUNT(*), 0) * 100,
    2
  ) AS resolution_rate_percent,

  -- Average resolution time (hours)
  AVG(
    EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at)) / 3600
  ) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,

  -- SLA breaches
  COUNT(s.ticket_id)
    FILTER (
      WHERE s.respond_breached_at IS NOT NULL
         OR s.resolve_breached_at IS NOT NULL
    ) AS sla_breaches

FROM ticket t
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id

GROUP BY t.department;

-- ------------------------------------------------------------
-- 4) Monthly employee KPI view
-- Purpose:
-- - Feeds employee_performance_report table
-- - Used for monthly snapshots
-- ------------------------------------------------------------

CREATE OR REPLACE VIEW v_employee_monthly_kpis AS
SELECT
  e.employee_id,
  TO_CHAR(t.submitted_at, 'YYYY-MM') AS report_month,

  COUNT(t.ticket_id) AS tickets_handled,

  COUNT(t.ticket_id)
    FILTER (WHERE t.status = 'resolved') AS tickets_resolved,

  AVG(
    EXTRACT(EPOCH FROM (t.resolved_at - t.submitted_at)) / 3600
  ) FILTER (WHERE t.resolved_at IS NOT NULL) AS avg_resolution_hours,

  COUNT(s.ticket_id)
    FILTER (
      WHERE s.respond_breached_at IS NOT NULL
         OR s.resolve_breached_at IS NOT NULL
    ) AS sla_breaches

FROM employee e
LEFT JOIN ticket t ON t.employee_id = e.employee_id
LEFT JOIN ticket_sla s ON s.ticket_id = t.ticket_id

GROUP BY e.employee_id, report_month;

-- ============================================================
-- End of KPI Views
-- ============================================================

-- INSERTING PART

SET search_path TO cms;

-- ============================================================
-- 1) DEPARTMENTS
-- ============================================================
INSERT INTO department (department_id, name) VALUES
('DPT-IT', 'IT Support'),
('DPT-NET', 'Network'),
('DPT-BILL', 'Billing'),
('DPT-CS', 'Customer Service'),
('DPT-OPS', 'Operations')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 2) USERS
-- ============================================================
INSERT INTO "user" (user_id, full_name, phone_e164, company) VALUES
('USR-001', 'Ahmed Al Mansoori', '+971501111111', 'Emirates Tech'),
('USR-002', 'Sara Khaled', '+971502222222', 'Dubai Holdings'),
('USR-003', 'Omar Hassan', '+971503333333', 'Etisalat'),
('USR-004', 'Laila Noor', '+971504444444', 'Careem')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 3) EMPLOYEES
-- ============================================================
INSERT INTO employee (employee_id, department_id, full_name, email, role) VALUES
('EMP-101', 'DPT-IT', 'Yousef Ali', 'yousef@company.com', 'Technician'),
('EMP-102', 'DPT-NET', 'Mona Farouk', 'mona@company.com', 'Engineer'),
('EMP-103', 'DPT-BILL', 'Khalid Saeed', 'khalid@company.com', 'Billing Officer'),
('EMP-104', 'DPT-CS', 'Lina Saleh', 'lina@company.com', 'Supervisor'),
('EMP-200', 'DPT-CS', 'Hassan Nabil', 'hassan@company.com', 'Manager')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 4) APP ACCOUNTS
-- ============================================================
INSERT INTO app_account (
  account_id, linked_user_id, linked_employee_id,
  email, password_hash, role
) VALUES
('ACC-U1', 'USR-001', NULL, 'ahmed@gmail.com', 'hash123', 'user'),
('ACC-U2', 'USR-002', NULL, 'sara@gmail.com', 'hash123', 'user'),
('ACC-U3', 'USR-003', NULL, 'omar@gmail.com', 'hash123', 'user'),

('ACC-E1', NULL, 'EMP-101', 'yousef@company.com', 'hash123', 'employee'),
('ACC-E2', NULL, 'EMP-102', 'mona@company.com', 'hash123', 'employee'),
('ACC-M1', NULL, 'EMP-200', 'hassan@company.com', 'hash123', 'manager')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 5) PASSWORD RESET TOKENS
-- ============================================================
INSERT INTO password_reset_token (
  reset_id, account_id, token_hash, expires_at
) VALUES
(
  'RST-001', 'ACC-U1', 'resettokenhash',
  NOW() + INTERVAL '30 minutes'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 6) TICKETS
-- ============================================================
INSERT INTO ticket (
  ticket_id, user_id, employee_id,
  subject, title, description,
  channel, department, priority, status,
  submitted_at, last_updated_at, resolved_at
) VALUES
(
  'CX-1001', 'USR-001', 'EMP-101',
  'Internet Issue', 'No Internet Access',
  'Internet disconnected since morning.',
  'chatbot', 'IT Support', 'High', 'resolved',
  NOW() - INTERVAL '3 days',
  NOW() - INTERVAL '1 day',
  NOW() - INTERVAL '1 day'
),
(
  'CX-1002', 'USR-002', 'EMP-103',
  'Billing Error', 'Wrong Invoice Amount',
  'Extra charge on last invoice.',
  'text', 'Billing', 'Medium', 'in_progress',
  NOW() - INTERVAL '2 days',
  NOW() - INTERVAL '6 hours',
  NULL
),
(
  'CX-1003', 'USR-003', NULL,
  'Network Speed', 'Slow Internet Speed',
  'Connection speed is very slow.',
  'audio', 'Network', 'Low', 'submitted',
  NOW() - INTERVAL '5 hours',
  NOW() - INTERVAL '5 hours',
  NULL
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 7) SLA
-- ============================================================
INSERT INTO ticket_sla (
  ticket_id, respond_due_at, resolve_due_at,
  respond_breached_at, resolve_breached_at
) VALUES
(
  'CX-1001',
  NOW() - INTERVAL '2 days',
  NOW() - INTERVAL '1 day',
  NULL,
  NULL
),
(
  'CX-1002',
  NOW() - INTERVAL '12 hours',
  NOW() + INTERVAL '1 day',
  NOW() - INTERVAL '2 hours',
  NULL
),
(
  'CX-1003',
  NOW() + INTERVAL '4 hours',
  NOW() + INTERVAL '2 days',
  NULL,
  NULL
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 8) STATUS HISTORY
-- ============================================================
INSERT INTO ticket_status_history (history_id, ticket_id, status) VALUES
('HIS-001', 'CX-1001', 'submitted'),
('HIS-002', 'CX-1001', 'assigned'),
('HIS-003', 'CX-1001', 'resolved'),

('HIS-004', 'CX-1002', 'submitted'),
('HIS-005', 'CX-1002', 'in_progress'),

('HIS-006', 'CX-1003', 'submitted')
ON CONFLICT DO NOTHING;


-- ============================================================
-- 9) ASSIGNMENT HISTORY
-- ============================================================
INSERT INTO ticket_assignment_history (
  assignment_id, ticket_id, employee_id, assigned_by, note
) VALUES
(
  'ASN-001', 'CX-1001', 'EMP-101', 'EMP-200',
  'Auto-assigned by AI routing'
),
(
  'ASN-002', 'CX-1002', 'EMP-103', 'EMP-200',
  'Manual assignment by manager'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 10) WORK LOGS
-- ============================================================
INSERT INTO ticket_work_log (
  worklog_id, ticket_id, employee_id, step_no, note
) VALUES
(
  'WLG-001', 'CX-1001', 'EMP-101', 1,
  'Checked router and network configuration'
),
(
  'WLG-002', 'CX-1001', 'EMP-101', 2,
  'Restarted modem and confirmed connectivity'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 11) ATTACHMENTS
-- ============================================================
INSERT INTO ticket_attachment (
  attachment_id, ticket_id, file_name, content_type,
  size_bytes, duration_seconds, storage_key
) VALUES
(
  'ATT-001', 'CX-1003', 'voice_complaint.webm',
  'audio/webm', 204800, 45, 'tickets/CX-1003/audio1.webm'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 12) NOTIFICATIONS
-- ============================================================
INSERT INTO notification_log (
  notification_id, ticket_id, channel, status, sent_at
) VALUES
(
  'NTF-001', 'CX-1001', 'email', 'sent', NOW() - INTERVAL '2 days'
),
(
  'NTF-002', 'CX-1002', 'sms', 'failed', NULL
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 13) AI RESULTS
-- ============================================================
INSERT INTO ticket_ai_result (
  ai_ticket_id, ticket_id, predicted_department_id,
  model_version, predicted_priority,
  confidence_score, priority_to_respond, priority_to_resolve
) VALUES
(
  'AIR-001', 'CX-1001', 'DPT-IT',
  'v1.2.0', 'High', 0.94, 1, 2
),
(
  'AIR-002', 'CX-1003', 'DPT-NET',
  'v1.2.0', 'Low', 0.78, 3, 4
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 14) APPROVAL REQUESTS
-- ============================================================
INSERT INTO approval_request (
  request_id, ticket_id, request_type,
  current_value, requested_value,
  submitted_by_employee_id, status
) VALUES
(
  'REQ-001', 'CX-1002', 'rescore',
  'Medium', 'High',
  'EMP-103', 'pending'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 15) ISSUE REPORTS
-- ============================================================
INSERT INTO issue_report (
  report_id, ticket_id, details
) VALUES
(
  'RPT-001', 'CX-1002',
  'Customer dissatisfied with invoice explanation'
)
ON CONFLICT DO NOTHING;

INSERT INTO ticket_issue_report (
  report_id, ticket_id, submitted_by_user_id,
  issue_text
) VALUES
(
  'RPT-002', 'CX-1003', 'USR-003',
  'Internet speed unacceptable during work hours'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 16) CHATBOT DATA
-- ============================================================
INSERT INTO chat_conversation (
  conversation_id, user_id, context
) VALUES
(
  'CONV-001', 'USR-001',
  '{"intent":"internet_issue","location":"Dubai"}'
)
ON CONFLICT DO NOTHING;

INSERT INTO chat_message (
  message_id, conversation_id, role, text
) VALUES
(
  'MSG-001', 'CONV-001', 'user',
  'My internet is not working'
),
(
  'MSG-002', 'CONV-001', 'bot',
  'I have created a ticket for you.'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- 17) PERFORMANCE REPORTS (from KPI view)
-- ============================================================
INSERT INTO employee_performance_report (
  report_id, employee_id, report_month, overall_rating
)
SELECT
  'RPT-EMP-2026-01-EMP-101',
  employee_id,
  report_month,
  88
FROM v_employee_monthly_kpis
WHERE employee_id = 'EMP-101'
ON CONFLICT DO NOTHING;


-- ============================================================
-- 18) PERFORMANCE NOTES
-- ============================================================
INSERT INTO performance_note (
  note_id, report_id, note_text, created_by
) VALUES
(
  'NOTE-001',
  'RPT-EMP-2026-01-EMP-101',
  'Excellent SLA adherence and customer communication.',
  'EMP-200'
)
ON CONFLICT DO NOTHING;

