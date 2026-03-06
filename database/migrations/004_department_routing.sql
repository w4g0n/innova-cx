-- ============================================================
-- Migration 004: department_routing
-- Logs every routing decision (confident and non-confident)
-- ============================================================

CREATE TABLE IF NOT EXISTS department_routing (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  suggested_department TEXT NOT NULL,
  confidence_score     NUMERIC(5,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
  is_confident         BOOLEAN NOT NULL,
  final_department     TEXT,
  routed_by            TEXT CHECK (routed_by IN ('model', 'manager')),
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
