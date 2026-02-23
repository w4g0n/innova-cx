BEGIN;

CREATE OR REPLACE FUNCTION compute_is_recurring_ticket(
  p_user_id UUID,
  p_subject TEXT,
  p_details TEXT,
  p_window_days INTEGER DEFAULT 180
)
RETURNS BOOLEAN AS $$
DECLARE
  normalized_subject TEXT := lower(trim(COALESCE(p_subject, '')));
  exact_subject_count INTEGER := 0;
BEGIN
  IF p_user_id IS NULL THEN
    RETURN FALSE;
  END IF;

  SELECT COUNT(*)
  INTO exact_subject_count
  FROM tickets t
  WHERE t.created_by_user_id = p_user_id
    AND t.created_at >= now() - make_interval(days => p_window_days)
    AND lower(trim(COALESCE(t.subject, ''))) = normalized_subject;

  IF exact_subject_count > 0 THEN
    RETURN TRUE;
  END IF;

  -- Fallback: check simple token overlap on details when subject wasn't matched.
  RETURN EXISTS (
    SELECT 1
    FROM tickets t
    WHERE t.created_by_user_id = p_user_id
      AND t.created_at >= now() - make_interval(days => p_window_days)
      AND tsvector_to_array(to_tsvector('simple', COALESCE(t.details, ''))) &&
          tsvector_to_array(to_tsvector('simple', COALESCE(p_details, '')))
  );
END;
$$ LANGUAGE plpgsql STABLE;

COMMIT;
