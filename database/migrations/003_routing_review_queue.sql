
-- Migration 003: routing_review_queue
-- Stores tickets where the AI routing confidence is below
-- the threshold, pending manual department assignment.


DO $$ BEGIN
  CREATE TYPE routing_review_status AS ENUM ('Pending', 'Approved', 'Overridden');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS routing_review_queue (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
  predicted_department TEXT NOT NULL,
  confidence_score     NUMERIC(5,4) NOT NULL,
  status               routing_review_status NOT NULL DEFAULT 'Pending',
  approved_department  TEXT,
  decided_by_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
  decided_at           TIMESTAMPTZ,
  decision_notes       TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rrq_ticket    ON routing_review_queue(ticket_id);
CREATE INDEX IF NOT EXISTS idx_rrq_status    ON routing_review_queue(status);
CREATE INDEX IF NOT EXISTS idx_rrq_created   ON routing_review_queue(created_at DESC);