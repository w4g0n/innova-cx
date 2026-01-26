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