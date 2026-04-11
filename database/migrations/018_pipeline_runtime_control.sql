-- Migration 018: pipeline_runtime_control table
--
-- PURPOSE:
--   Creates the pipeline_runtime_control table and grants the runtime role
--   (innovacx_app) exactly the privileges it needs — SELECT, INSERT, UPDATE.
--   No CREATE TABLE privilege is needed or granted to innovacx_app.
--
--   Previously pipeline_queue_api.py issued CREATE TABLE IF NOT EXISTS at
--   runtime, which requires CREATE on the public schema. That privilege was
--   removed from innovacx_app as part of least-privilege hardening. This
--   migration creates the table as innovacx_admin (schema owner) during DB
--   initialization so the runtime role never needs to create it.
--
-- IDEMPOTENT: uses IF NOT EXISTS / ON CONFLICT DO NOTHING throughout.
--
-- RUN MANUALLY (existing volume):
--   docker exec -i innovacx-db psql -U innovacx_admin -d complaints_db \
--     < database/migrations/018_pipeline_runtime_control.sql


CREATE TABLE IF NOT EXISTS public.pipeline_runtime_control (
    singleton  BOOLEAN      PRIMARY KEY DEFAULT TRUE CHECK (singleton = TRUE),
    is_paused  BOOLEAN      NOT NULL DEFAULT FALSE,
    paused_at  TIMESTAMPTZ  NULL,
    resumed_at TIMESTAMPTZ  NULL,
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Seed the single control row (idempotent)
INSERT INTO public.pipeline_runtime_control (singleton, is_paused)
VALUES (TRUE, FALSE)
ON CONFLICT (singleton) DO NOTHING;

-- Grant runtime role the minimum privileges it needs.
-- innovacx_app can read, insert the seed row, and update pause/resume state,
-- but cannot CREATE or DROP the table.
GRANT SELECT, INSERT, UPDATE ON public.pipeline_runtime_control
    TO innovacx_app;
