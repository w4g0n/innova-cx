-- =============================================================================
-- InnovaCX — Employee Report Sub-tables Migration
-- File: database/scripts/001_employee_report_subtables.sql
--
-- Creates the three sub-tables that back the Employee Monthly Report screen:
--   - employee_report_rating_components
--   - employee_report_weekly
--   - employee_report_notes
--
-- SAFE TO RE-RUN: all statements use IF NOT EXISTS guards.
--
-- RUN ORDER (apply after init.sql and 000_analytics_prerequisites.sql):
--   docker exec -i innovacx-db psql -U innovacx_app -d complaints_db \
--     < database/scripts/001_employee_report_subtables.sql
--
-- These tables are populated by _generate_employee_report() in main.py,
-- which reads exclusively from mv_employee_daily and mv_acceptance_daily.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- employee_report_rating_components
-- One row per rating dimension per report.
-- Columns:
--   name  — dimension label (e.g. "Closure Rate")
--   score — raw metric value (0-100 scale) used for the progress bar width
--   pct   — same value used to sort components by contribution
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.employee_report_rating_components (
    id        BIGSERIAL     PRIMARY KEY,
    report_id UUID          NOT NULL
                            REFERENCES public.employee_reports(id)
                            ON DELETE CASCADE,
    name      TEXT          NOT NULL,
    score     NUMERIC(6,2)  NOT NULL DEFAULT 0,
    pct       NUMERIC(6,2)  NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_errc_report_id
    ON public.employee_report_rating_components (report_id);


-- ---------------------------------------------------------------------------
-- employee_report_weekly
-- One row per ISO week that falls within the report's month.
-- Columns:
--   week_label   — human label, e.g. "Week 1 (Mar 3)"
--   assigned     — total tickets assigned that week
--   resolved     — tickets resolved that week
--   sla          — SLA compliance % for that week, e.g. "92.5%"
--   avg_response — weighted avg first-response time, e.g. "45 min"
--   delta_type   — "positive" | "neutral" (drives CSS class in frontend)
--   delta_text   — delta description vs prior week, e.g. "+2 resolved"
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.employee_report_weekly (
    id           BIGSERIAL  PRIMARY KEY,
    report_id    UUID       NOT NULL
                            REFERENCES public.employee_reports(id)
                            ON DELETE CASCADE,
    week_label   TEXT       NOT NULL,
    assigned     INTEGER    NOT NULL DEFAULT 0,
    resolved     INTEGER    NOT NULL DEFAULT 0,
    sla          TEXT,
    avg_response TEXT,
    delta_type   TEXT,
    delta_text   TEXT
);

CREATE INDEX IF NOT EXISTS idx_erw_report_id
    ON public.employee_report_weekly (report_id);


-- ---------------------------------------------------------------------------
-- employee_report_notes
-- Auto-generated insight bullets for the report.
-- Ordered by insertion order (id ASC) which matches generation priority.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.employee_report_notes (
    id        BIGSERIAL  PRIMARY KEY,
    report_id UUID       NOT NULL
                         REFERENCES public.employee_reports(id)
                         ON DELETE CASCADE,
    note      TEXT       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ern_report_id
    ON public.employee_report_notes (report_id);


-- ---------------------------------------------------------------------------
-- Verification query — uncomment to confirm after applying:
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
--   AND table_name IN (
--       'employee_report_rating_components',
--       'employee_report_weekly',
--       'employee_report_notes'
--   );
-- ---------------------------------------------------------------------------

COMMIT;
