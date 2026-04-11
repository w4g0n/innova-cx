-- InnovaCX — Legacy Employee Report Cleanup Migration
-- File: database/scripts/002_cleanup_legacy_employee_reports.sql
--
-- VERSION: 4 (final)
--
-- Removes ALL legacy employee_reports rows. Two conditions, either triggers
-- deletion:
--
--   (A) report_code does not match the canonical slug format
--           [a-z]{3}-[0-9]{4}-[a-z0-9]+
--       Catches: rpt-ahmed-feb26, rpt-bilal-jan26, nov-2025, nov-2025-maria
--
--   (B) month_label contains '2025'
--       Catches: nov-2025-ahmed, dec-2025-ahmed, dec-2025-sarah — correctly
--       formatted codes whose month is 2025 and have no MV backing data
--       (mv_employee_daily has no rows before 2026-01-01 in this dataset).
--
-- The ONLY rows that survive are canonical-format 2026+ reports:
--   mar-2026-ahmed, feb-2026-lena, jan-2026-sarah, apr-2026-ahmed, etc.
--
-- Child rows in all four sub-tables cascade automatically (ON DELETE CASCADE).
-- SAFE TO RE-RUN — DELETE WHERE is idempotent.
--
-- APPLY ORDER
-- -----------
-- After: init.sql, 000_analytics_prerequisites.sql, 001_employee_report_subtables.sql
--
-- Command:
--   docker exec -i innovacx-db psql -U innovacx_admin -d complaints_db \
--     < database/scripts/002_cleanup_legacy_employee_reports.sql


BEGIN;


-- PRE-FLIGHT (uncomment to preview without deleting):
-- SELECT id, report_code, month_label FROM employee_reports
-- WHERE month_label LIKE '%2025'
--    OR report_code NOT SIMILAR TO '[a-z]{3}-[0-9]{4}-[a-z0-9]+'
-- ORDER BY created_at;




-- STEP 1 — Delete all legacy rows

DELETE FROM employee_reports
WHERE month_label LIKE '%2025'
   OR report_code NOT SIMILAR TO '[a-z]{3}-[0-9]{4}-[a-z0-9]+';



-- STEP 2 — Verify. Raises EXCEPTION and rolls back if anything is wrong.

DO $$
DECLARE
    v_legacy_rows    INTEGER;
    v_rows_2025      INTEGER;
    v_orphan_summary INTEGER;
    v_orphan_rating  INTEGER;
    v_orphan_weekly  INTEGER;
    v_orphan_notes   INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_legacy_rows
    FROM employee_reports
    WHERE report_code NOT SIMILAR TO '[a-z]{3}-[0-9]{4}-[a-z0-9]+';

    SELECT COUNT(*) INTO v_rows_2025
    FROM employee_reports
    WHERE month_label LIKE '%2025';

    SELECT COUNT(*) INTO v_orphan_summary
    FROM employee_report_summary_items si
    LEFT JOIN employee_reports r ON r.id = si.report_id
    WHERE r.id IS NULL;

    SELECT COUNT(*) INTO v_orphan_rating
    FROM employee_report_rating_components rc
    LEFT JOIN employee_reports r ON r.id = rc.report_id
    WHERE r.id IS NULL;

    SELECT COUNT(*) INTO v_orphan_weekly
    FROM employee_report_weekly w
    LEFT JOIN employee_reports r ON r.id = w.report_id
    WHERE r.id IS NULL;

    SELECT COUNT(*) INTO v_orphan_notes
    FROM employee_report_notes n
    LEFT JOIN employee_reports r ON r.id = n.report_id
    WHERE r.id IS NULL;

    RAISE NOTICE '--- 002_cleanup_legacy_employee_reports verification ---';
    RAISE NOTICE 'Non-canonical format rows : %  (expected 0)', v_legacy_rows;
    RAISE NOTICE 'Remaining 2025 rows       : %  (expected 0)', v_rows_2025;
    RAISE NOTICE 'Orphan summary items      : %  (expected 0)', v_orphan_summary;
    RAISE NOTICE 'Orphan rating components  : %  (expected 0)', v_orphan_rating;
    RAISE NOTICE 'Orphan weekly rows        : %  (expected 0)', v_orphan_weekly;
    RAISE NOTICE 'Orphan notes              : %  (expected 0)', v_orphan_notes;

    IF v_legacy_rows > 0 OR v_rows_2025 > 0
       OR v_orphan_summary > 0 OR v_orphan_rating > 0
       OR v_orphan_weekly  > 0 OR v_orphan_notes  > 0
    THEN
        RAISE EXCEPTION
            'Verification FAILED — unexpected rows remain. Transaction rolled back.';
    END IF;

    RAISE NOTICE 'Verification PASSED — committing.';
END $$;


COMMIT;
