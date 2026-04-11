-- Migration 010: Pipeline Queue — failure detail columns

ALTER TABLE pipeline_queue
    ADD COLUMN IF NOT EXISTS failure_category TEXT,
    ADD COLUMN IF NOT EXISTS failure_history  JSONB NOT NULL DEFAULT '[]';
