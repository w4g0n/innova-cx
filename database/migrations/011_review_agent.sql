-- Migration 011: Review Agent
-- Adds 'Review' ticket status and review_agent_decisions audit table.

-- Add 'Review' to ticket_status enum.
-- Used when the Review Agent holds a ticket for operator intervention.
ALTER TYPE ticket_status ADD VALUE IF NOT EXISTS 'Review';

-- Review Agent audit / decision table
CREATE TABLE IF NOT EXISTS review_agent_decisions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id               UUID REFERENCES tickets(id) ON DELETE CASCADE,
    ticket_code             TEXT,
    execution_id            UUID,

    -- Final verdict
    -- approved                : routing correct, all checks pass, ticket released
    -- approved_routing_review : ticket released but department needs manager confirmation
    -- held_operator_review    : critical mock + errors, or uncorrectable issues
    verdict                 TEXT NOT NULL,
    verdict_reason          TEXT,

    -- Consistency check results
    consistency_passed      BOOLEAN NOT NULL DEFAULT TRUE,
    consistency_issues      JSONB   NOT NULL DEFAULT '[]',

    -- Priority re-run (triggered when feature fields were auto-corrected)
    priority_rerun          BOOLEAN NOT NULL DEFAULT FALSE,
    priority_before         TEXT,
    priority_after          TEXT,
    priority_score_before   INT,
    priority_score_after    INT,

    -- Routing review
    routing_confidence      NUMERIC(6,4),
    routing_threshold       NUMERIC(6,4),
    routing_above_threshold BOOLEAN,
    original_department     TEXT,
    final_department        TEXT,
    routing_overridden      BOOLEAN NOT NULL DEFAULT FALSE,
    routing_sent_to_review  BOOLEAN NOT NULL DEFAULT FALSE,

    -- Mock fallback handling
    mock_stages_detected    JSONB NOT NULL DEFAULT '[]',
    mock_overrideable       BOOLEAN,

    -- LLM metadata
    llm_model               TEXT,
    llm_inference_time_ms   INT,

    -- Full pipeline state snapshot at review time
    pipeline_state_snapshot JSONB NOT NULL DEFAULT '{}',

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_rad_ticket_id   ON review_agent_decisions(ticket_id);
CREATE INDEX IF NOT EXISTS idx_rad_ticket_code ON review_agent_decisions(ticket_code);
CREATE INDEX IF NOT EXISTS idx_rad_verdict     ON review_agent_decisions(verdict, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rad_created_at  ON review_agent_decisions(created_at DESC);

-- Notification type for operator-required review holds
ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'review_agent_held';
