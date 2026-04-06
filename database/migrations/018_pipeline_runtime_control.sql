-- =============================================================================
-- Migration 018: pipeline_runtime_control table
--
-- PURPOSE:
--   Creates the pipeline_runtime_control table that the orchestrator's
--   queue_manager.py requires at startup (ensure_pipeline_control_table()).
--
--   Previously this table was created by the orchestrator itself at runtime
--   via CREATE TABLE IF NOT EXISTS. That required innovacx_app to have CREATE
--   on the public schema. As part of the role separation security work
--   (zzz_least_privilege.sql), CREATE was removed from innovacx_app because
--   application code should not create schema objects.
--
--   This migration creates the table as innovacx_admin (the schema owner)
--   during database initialization, before the orchestrator starts.
--   The orchestrator's CREATE TABLE IF NOT EXISTS call will then find the
--   table already present and proceed without needing CREATE privilege.
--
-- IDEMPOTENT: uses IF NOT EXISTS throughout.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.pipeline_runtime_control (
    singleton  BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton = TRUE),
    is_paused  BOOLEAN     NOT NULL DEFAULT FALSE,
    paused_at  TIMESTAMPTZ NULL,
    resumed_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed the single control row. The orchestrator does the same insert with
-- ON CONFLICT DO NOTHING, so this is safe to run before or alongside it.
INSERT INTO public.pipeline_runtime_control (singleton, is_paused)
VALUES (TRUE, FALSE)
ON CONFLICT (singleton) DO NOTHING;
