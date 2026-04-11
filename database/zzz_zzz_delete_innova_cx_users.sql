-- zzz_zzz_delete_innova_cx_users.sql
--
-- PURPOSE: Hard-delete ALL @innova.cx users after all other seed files have run.
--          This file sorts alphabetically AFTER every other zzz_* file so it
--          runs LAST, regardless of what seeds created innova.cx users earlier.
--
-- SAFE:    Fully idempotent. If no innova.cx users exist, it's a no-op.
--          Reassigns FK references before deleting to avoid constraint violations.

BEGIN;

-- Step 1: Reassign tickets created by innova.cx customers → customer1@innovacx.net
UPDATE tickets
SET created_by_user_id = (SELECT id FROM users WHERE email = 'customer1@innovacx.net')
WHERE created_by_user_id IN (
    SELECT id FROM users WHERE email LIKE '%@innova.cx'
      AND role = 'customer'
)
AND (SELECT id FROM users WHERE email = 'customer1@innovacx.net') IS NOT NULL;

-- Step 2: Reassign tickets assigned to innova.cx employees → matching innovacx.net employee
-- Uses email prefix to find the matching new user (ahmed@innova.cx → ahmed@innovacx.net)
-- Falls back to first active innovacx.net employee if no match found.
UPDATE tickets
SET assigned_to_user_id = COALESCE(
    (SELECT new_u.id FROM users new_u
     JOIN users old_u ON split_part(old_u.email, '@', 1) = split_part(new_u.email, '@', 1)
     WHERE old_u.id = tickets.assigned_to_user_id
       AND new_u.email LIKE '%@innovacx.net'
       AND new_u.role = 'employee'
       AND new_u.is_active = TRUE
     LIMIT 1),
    (SELECT id FROM users WHERE email LIKE '%@innovacx.net'
       AND role = 'employee' AND is_active = TRUE
     ORDER BY email LIMIT 1)
)
WHERE assigned_to_user_id IN (
    SELECT id FROM users WHERE email LIKE '%@innova.cx' AND role = 'employee'
);

-- Step 3: Reassign approval_requests submitted by innova.cx users
UPDATE approval_requests
SET submitted_by_user_id = COALESCE(
    (SELECT new_u.id FROM users new_u
     JOIN users old_u ON split_part(old_u.email, '@', 1) = split_part(new_u.email, '@', 1)
     WHERE old_u.id = approval_requests.submitted_by_user_id
       AND new_u.email LIKE '%@innovacx.net'
       AND new_u.is_active = TRUE
     LIMIT 1),
    (SELECT id FROM users WHERE email LIKE '%@innovacx.net'
       AND role = 'employee' AND is_active = TRUE
     ORDER BY email LIMIT 1)
)
WHERE submitted_by_user_id IN (
    SELECT id FROM users WHERE email LIKE '%@innova.cx'
);

-- Step 4: Reassign employee_reports owned by innova.cx employees
UPDATE employee_reports
SET employee_user_id = COALESCE(
    (SELECT new_u.id FROM users new_u
     JOIN users old_u ON split_part(old_u.email, '@', 1) = split_part(new_u.email, '@', 1)
     WHERE old_u.id = employee_reports.employee_user_id
       AND new_u.email LIKE '%@innovacx.net'
       AND new_u.role = 'employee'
       AND new_u.is_active = TRUE
     LIMIT 1),
    (SELECT id FROM users WHERE email LIKE '%@innovacx.net'
       AND role = 'employee' AND is_active = TRUE
     ORDER BY email LIMIT 1)
)
WHERE employee_user_id IN (
    SELECT id FROM users WHERE email LIKE '%@innova.cx' AND role = 'employee'
);

-- Step 5: Reassign sessions linked to innova.cx users
UPDATE sessions
SET user_id = (SELECT id FROM users WHERE email = 'customer1@innovacx.net')
WHERE user_id IN (
    SELECT id FROM users WHERE email LIKE '%@innova.cx'
);

-- Step 6: Reassign notifications for innova.cx users
DELETE FROM notifications
WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@innova.cx');

-- Step 7: Reassign password_reset_tokens
DELETE FROM password_reset_tokens
WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@innova.cx');

-- Step 8: Hard-delete innova.cx users (profiles, preferences, then users)
DELETE FROM user_profiles
WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@innova.cx');

DELETE FROM user_preferences
WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@innova.cx');

DELETE FROM sessions
WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@innova.cx');

-- Final delete — should succeed now that all FK refs are reassigned/removed
DO $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM users WHERE email LIKE '%@innova.cx';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'zzz_zzz_cleanup: deleted % innova.cx user(s)', deleted_count;
END;
$$;

-- Step 9: Verification
DO $$
DECLARE
    remaining INT;
    op_count  INT;
BEGIN
    SELECT COUNT(*) INTO remaining FROM users
    WHERE email LIKE '%@innova.cx' AND is_active = TRUE;

    SELECT COUNT(*) INTO op_count FROM users
    WHERE role = 'operator' AND is_active = TRUE;

    RAISE NOTICE 'Active innova.cx users remaining : % (expected 0)', remaining;
    RAISE NOTICE 'Active operator users            : % (expected 1)', op_count;

    IF remaining > 0 THEN
        RAISE WARNING 'innova.cx users still active — check FK constraints above';
    END IF;
END;
$$;

COMMIT;
