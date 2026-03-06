from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException
from psycopg2.extras import RealDictCursor


def build_routing_meta(
    requested_department: Optional[str],
    classification_confidence: Optional[float],
    threshold: float,
) -> Dict[str, Any]:
    has_routing_decision = bool(requested_department) and classification_confidence is not None
    routing_confidence_pct = (
        max(0.0, min(100.0, float(classification_confidence) * 100.0))
        if classification_confidence is not None
        else None
    )
    routing_is_confident = bool(
        has_routing_decision and float(classification_confidence) >= threshold
    )
    return {
        "has_routing_decision": has_routing_decision,
        "routing_confidence_raw": classification_confidence,
        "routing_confidence_pct": routing_confidence_pct,
        "routing_is_confident": routing_is_confident,
    }


def manager_targets_for_department(cur, department_id: Optional[str]) -> List[Dict[str, Any]]:
    def _rows_as_dicts(rows: List[Any]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        if isinstance(rows[0], dict):
            return rows
        cols = [d[0] for d in (cur.description or [])]
        return [dict(zip(cols, row)) for row in rows]

    if department_id:
        cur.execute(
            """
            SELECT u.id, up.full_name
            FROM users u
            JOIN user_profiles up ON up.user_id = u.id
            WHERE u.role = 'manager' AND up.department_id = %s
            ORDER BY up.full_name;
            """,
            (department_id,),
        )
        rows = _rows_as_dicts(cur.fetchall() or [])
        if rows:
            return rows

    cur.execute(
        """
        SELECT u.id, up.full_name
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.role = 'manager'
        ORDER BY up.full_name NULLS LAST, u.id;
        """
    )
    return _rows_as_dicts(cur.fetchall() or [])


def record_department_routing_decision(
    cur,
    *,
    ticket_uuid: str,
    ticket_code: str,
    suggested_department: str,
    routing_confidence_pct: float,
    routing_is_confident: bool,
    department_id: Optional[str],
    priority: Optional[str],
    insert_notification: Callable[..., None],
    logger,
) -> bool:
    final_department = suggested_department if routing_is_confident else None
    routed_by = "model" if routing_is_confident else None
    cur.execute(
        """
        INSERT INTO department_routing (
          ticket_id,
          suggested_department,
          confidence_score,
          is_confident,
          final_department,
          routed_by,
          manager_id
        )
        VALUES (%s::uuid, %s, %s, %s, %s, %s, NULL);
        """,
        (
            ticket_uuid,
            suggested_department,
            routing_confidence_pct,
            routing_is_confident,
            final_department,
            routed_by,
        ),
    )

    if routing_is_confident:
        return False

    managers = manager_targets_for_department(cur, department_id)
    for manager in managers:
        insert_notification(
            cur,
            user_id=str(manager["id"]),
            notif_type="system",
            title=f"Routing Approval Needed: {ticket_code}",
            message=(
                f"AI routing confidence is {routing_confidence_pct:.2f}% for "
                f"{ticket_code} (suggested: {suggested_department}). Please confirm department."
            ),
            ticket_id=ticket_uuid,
            priority=priority,
        )
    logger.info(
        "department_routing | ticket=%s suggested=%s confidence_pct=%.2f is_confident=%s queued=True",
        ticket_code,
        suggested_department,
        routing_confidence_pct,
        routing_is_confident,
    )
    return True


def get_routing_review_payload(
    fetch_all: Callable[..., List[Dict[str, Any]]],
    status_filter: str,
) -> Dict[str, Any]:
    valid = {"Pending", "Resolved", "All", "Approved", "Overridden"}
    if status_filter not in valid:
        status_filter = "Pending"
    if status_filter in {"Approved", "Overridden"}:
        status_filter = "Resolved"

    where = "WHERE dr.is_confident = FALSE"
    params: List[Any] = []
    if status_filter == "Pending":
        where += " AND dr.final_department IS NULL"
    elif status_filter == "Resolved":
        where += " AND dr.final_department IS NOT NULL"

    rows = fetch_all(
        f"""
        SELECT
          dr.id::text                          AS "reviewId",
          CASE
            WHEN dr.final_department IS NULL THEN 'Pending'
            WHEN dr.routed_by = 'manager' THEN 'Overridden'
            ELSE 'Approved'
          END                                  AS "status",
          dr.suggested_department              AS "predictedDepartment",
          ROUND(dr.confidence_score, 2)        AS "confidencePct",
          dr.final_department                  AS "approvedDepartment",
          NULL::text                           AS "decisionNotes",
          dr.updated_at                        AS "decidedAt",
          dr.created_at                        AS "createdAt",
          t.ticket_code                        AS "ticketCode",
          t.subject                            AS "subject",
          t.priority::text                     AS "priority",
          t.status::text                       AS "ticketStatus",
          d.name                               AS "currentDepartment",
          up.full_name                         AS "decidedBy",
          ro.reasoning                         AS "modelReasoning"
        FROM department_routing dr
        JOIN tickets t ON t.id = dr.ticket_id
        LEFT JOIN departments d ON d.id = t.department_id
        LEFT JOIN user_profiles up ON up.user_id = dr.manager_id
        LEFT JOIN routing_outputs ro ON ro.ticket_id = t.id AND ro.is_current = TRUE
        {where}
        ORDER BY dr.created_at DESC
        LIMIT 500;
        """,
        params,
    )

    result = []
    for r in rows:
        result.append(
            {
                **{k: v for k, v in r.items() if k not in ("decidedAt", "createdAt", "confidencePct")},
                "confidencePct": float(r.get("confidencePct") or 0),
                "decidedAt": r["decidedAt"].isoformat() if r.get("decidedAt") else None,
                "createdAt": r["createdAt"].isoformat() if r.get("createdAt") else None,
            }
        )

    pending_count = sum(1 for r in result if r.get("status") == "Pending")
    return {"items": result, "pendingCount": pending_count}


def decide_routing_review(
    *,
    review_id: str,
    decision: Optional[str],
    approved_department: Optional[str],
    user: Dict[str, Any],
    fetch_one: Callable[..., Optional[Dict[str, Any]]],
    db_connect: Callable[[], Any],
    auto_assign_ticket_if_needed: Callable[..., Any],
    insert_notification: Callable[..., None],
    logger,
) -> Dict[str, Any]:
    effective_decision = (decision or "").strip() or "Overridden"
    if effective_decision not in ("Approved", "Overridden"):
        raise HTTPException(status_code=422, detail="decision must be 'Approved' or 'Overridden'")

    rrq = fetch_one(
        """
        SELECT id, ticket_id, suggested_department, final_department
        FROM department_routing
        WHERE id::text = %s AND is_confident = FALSE
        LIMIT 1
        """,
        (review_id,),
    )
    if not rrq:
        raise HTTPException(status_code=404, detail="Review item not found")
    if rrq.get("final_department"):
        raise HTTPException(status_code=409, detail="This item has already been decided")

    final_dept = approved_department.strip() if effective_decision == "Overridden" and approved_department else rrq["suggested_department"]
    if not final_dept:
        raise HTTPException(status_code=422, detail="approved_department is required when overriding")

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                UPDATE department_routing
                SET final_department = %s,
                    routed_by        = 'manager',
                    manager_id       = %s,
                    updated_at       = now()
                WHERE id::text = %s;
                """,
                (final_dept, user["id"], review_id),
            )

            cur.execute("SELECT id FROM departments WHERE LOWER(name) = LOWER(%s) LIMIT 1", (final_dept,))
            dept_row = cur.fetchone()
            if dept_row:
                cur.execute(
                    """
                    UPDATE tickets
                    SET
                      department_id = %s,
                      status = CASE WHEN status = 'Open' THEN 'Assigned' ELSE status END,
                      updated_at = now()
                    WHERE id = %s
                    RETURNING ticket_code, status, priority;
                    """,
                    (dept_row["id"], rrq["ticket_id"]),
                )
                ticket_row = cur.fetchone()
                if ticket_row:
                    with conn.cursor() as assign_cur:
                        auto_assign_ticket_if_needed(
                            assign_cur,
                            ticket_code=ticket_row["ticket_code"],
                            status=ticket_row["status"],
                            department_id=dept_row["id"],
                            priority=ticket_row["priority"],
                        )

            cur.execute(
                """
                INSERT INTO department_routing_feedback
                  (ticket_id, predicted_department, approved_department,
                   confidence_score, model_name, approved_by_user_id)
                SELECT
                  %s, %s, %s,
                  dr.confidence_score / 100.0, 'orchestrator', %s
                FROM department_routing dr
                WHERE dr.id::text = %s;
                """,
                (rrq["ticket_id"], rrq["suggested_department"], final_dept, user["id"], review_id),
            )

            ticket_info = fetch_one(
                "SELECT ticket_code, priority FROM tickets WHERE id = %s",
                (rrq["ticket_id"],),
            ) or {}
            insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=(
                    f"Routing {'Confirmed' if effective_decision == 'Approved' else 'Overridden'}: "
                    f"{ticket_info.get('ticket_code', '')}"
                ),
                message=(
                    f"You {'confirmed' if effective_decision == 'Approved' else 'overrode'} the AI routing for "
                    f"{ticket_info.get('ticket_code', '')} -> {final_dept}."
                ),
                ticket_id=str(rrq["ticket_id"]),
                priority=ticket_info.get("priority"),
            )

    logger.info(
        "routing_review_decision | review=%s decision=%s dept=%s by=%s",
        review_id,
        effective_decision,
        final_dept,
        user["id"],
    )
    return {"ok": True, "reviewId": review_id, "decision": effective_decision, "finalDepartment": final_dept}
