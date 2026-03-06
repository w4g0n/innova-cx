from typing import Optional


def _select_balanced_employee_user_id(cur, department_id, incoming_priority: Optional[str]) -> Optional[str]:
    """
    Pick an employee in a department by balanced weighted queue:
      1) lowest weighted active load (Critical 8, High 5, Medium 3, Low 1)
      2) lowest same-priority active load
      3) lowest active ticket count
      4) oldest last assignment
    """
    priority = str(incoming_priority or "Medium").strip().title()
    if priority not in {"Low", "Medium", "High", "Critical"}:
        priority = "Medium"

    cur.execute(
        """
        SELECT
          u.id::text AS user_id,
          COALESCE(
            SUM(
              CASE t.priority
                WHEN 'Critical' THEN 8
                WHEN 'High' THEN 5
                WHEN 'Medium' THEN 3
                ELSE 1
              END
            ) FILTER (WHERE t.status <> 'Resolved'),
            0
          ) AS weighted_active_load,
          COUNT(*) FILTER (
            WHERE t.status <> 'Resolved'
              AND t.priority = %s::ticket_priority
          ) AS same_priority_active,
          COUNT(*) FILTER (WHERE t.status <> 'Resolved') AS active_total,
          MAX(t.assigned_at) FILTER (WHERE t.status <> 'Resolved') AS last_assigned_at
        FROM users u
        JOIN user_profiles up
          ON up.user_id = u.id
        LEFT JOIN tickets t
          ON t.assigned_to_user_id = u.id
        WHERE u.role = 'employee'
          AND u.is_active = TRUE
          AND up.department_id = %s::uuid
        GROUP BY u.id
        ORDER BY
          weighted_active_load ASC,
          same_priority_active ASC,
          active_total ASC,
          last_assigned_at ASC NULLS FIRST,
          u.id ASC
        LIMIT 1;
        """,
        (priority, str(department_id)),
    )
    row = cur.fetchone()
    if row and row[0]:
        return str(row[0])

    # Fallback: if no active employee exists in the routed department,
    # still assign to the globally least-loaded active employee.
    cur.execute(
        """
        SELECT
          u.id::text AS user_id,
          COALESCE(
            SUM(
              CASE t.priority
                WHEN 'Critical' THEN 8
                WHEN 'High' THEN 5
                WHEN 'Medium' THEN 3
                ELSE 1
              END
            ) FILTER (WHERE t.status <> 'Resolved'),
            0
          ) AS weighted_active_load,
          COUNT(*) FILTER (
            WHERE t.status <> 'Resolved'
              AND t.priority = %s::ticket_priority
          ) AS same_priority_active,
          COUNT(*) FILTER (WHERE t.status <> 'Resolved') AS active_total,
          MAX(t.assigned_at) FILTER (WHERE t.status <> 'Resolved') AS last_assigned_at
        FROM users u
        JOIN user_profiles up
          ON up.user_id = u.id
        LEFT JOIN tickets t
          ON t.assigned_to_user_id = u.id
        WHERE u.role = 'employee'
          AND u.is_active = TRUE
        GROUP BY u.id
        ORDER BY
          weighted_active_load ASC,
          same_priority_active ASC,
          active_total ASC,
          last_assigned_at ASC NULLS FIRST,
          u.id ASC
        LIMIT 1;
        """,
        (priority,),
    )
    row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def auto_assign_ticket_if_needed(
    cur,
    *,
    ticket_code: str,
    status: Optional[str],
    department_id,
    priority: Optional[str],
) -> Optional[str]:
    """
    Auto-assign only when ticket is in Assigned status and currently unassigned.
    Returns assigned employee user_id (if newly assigned), else None.
    """
    if str(status or "").strip() != "Assigned" or not department_id or not ticket_code:
        return None

    assignee_user_id = _select_balanced_employee_user_id(cur, department_id, priority)
    if not assignee_user_id:
        return None

    cur.execute(
        """
        UPDATE tickets
        SET
          assigned_to_user_id = %s,
          assigned_at = COALESCE(assigned_at, now()),
          updated_at = now()
        WHERE ticket_code = %s
          AND assigned_to_user_id IS NULL
        RETURNING assigned_to_user_id::text;
        """,
        (assignee_user_id, ticket_code),
    )
    updated = cur.fetchone()
    return str(updated[0]) if updated and updated[0] else None
