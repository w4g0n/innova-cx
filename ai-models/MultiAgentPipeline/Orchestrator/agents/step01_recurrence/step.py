"""
Step 1 — Recurrence Agent
==========================
First stage of the pipeline. Detects recurring submissions via transformer
semantic similarity, then applies one of four branches:

  A  Open ticket, SLA < 50% elapsed  → employee reminder notification
  B  Open ticket, SLA ≥ 50% elapsed  → reminder + priority bump +1 (skip if Critical)
  C  Resolved < 1 month ago          → reopen old ticket, assign back, archive prior resolution
  D  Resolved ≥ 1 month ago          → new ticket runs full pipeline; old ticket referenced only

For branches A/B/C the new ticket is set to Linked status and
`state["_recurrence_handled"] = True` stops the pipeline.
For branch D the pipeline continues with prior context injected into state.

In all 4 cases `is_recurring = True` and `linked_ticket_code` is written to DB.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher

from db import db_connect
from recurrence_encoder import find_similar_ticket, encoder_is_available

logger = logging.getLogger(__name__)

_UTC = timezone.utc
_PRIORITY_ORDER = ["Low", "Medium", "High", "Critical"]
_OPEN_STATUSES = {"Open", "Assigned", "In Progress", "Escalated", "Overdue", "Reopened"}

# Threshold used by the heuristic fallback (imported by recurrence_encoder)
SIMILARITY_RECURRENCE_THRESHOLD = 0.75


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(value or "").lower())).strip()


def _token_jaccard(a: str, b: str) -> float:
    a_tokens = {t for t in _normalize_text(a).split() if len(t) > 2}
    b_tokens = {t for t in _normalize_text(b).split() if len(t) > 2}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / float(len(a_tokens | b_tokens))


def _find_similar_ticket(
    text: str,
    current_ticket_code: str | None,
    created_by_user_id: str | None = None,
) -> tuple[str | None, str | None, float]:
    """
    Heuristic fallback used by recurrence_encoder when the transformer is unavailable.

    Mirrors the encoder candidate filter so only tickets that have already
    progressed beyond the initial Open intake state are considered.
    """
    query_text = str(text or "").strip().lower()
    if not query_text:
        return None, None, 0.0
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_code, subject, details
                    FROM tickets
                    WHERE (%s IS NULL OR ticket_code <> %s)
                      AND (%s IS NULL OR created_by_user_id = %s::uuid)
                      AND status NOT IN ('Open'::ticket_status, 'Linked'::ticket_status)
                      AND priority_assigned_at IS NOT NULL
                      AND EXISTS (
                          SELECT 1
                          FROM pipeline_stage_events pse
                          WHERE pse.ticket_code = tickets.ticket_code
                            AND pse.stage_name = 'ReviewAgent'
                            AND pse.step_order = 11
                            AND pse.event_type = 'output'
                            AND pse.status = 'success'
                      )
                    ORDER BY created_at DESC
                    LIMIT 120
                    """,
                    (current_ticket_code, current_ticket_code,
                     created_by_user_id, created_by_user_id),
                )
                rows = cur.fetchall() or []
    except Exception:
        return None, None, 0.0

    best_code = best_subject = None
    best_score = 0.0
    for row in rows:
        code = str(row[0] or "").strip()
        subject = str(row[1] or "").strip().lower()
        details = str(row[2] or "").strip().lower()
        if not code or (not details and not subject):
            continue
        score = max(
            SequenceMatcher(None, query_text, details).ratio() if details else 0.0,
            SequenceMatcher(None, query_text, subject).ratio() if subject else 0.0,
            _token_jaccard(query_text, details) if details else 0.0,
            _token_jaccard(query_text, subject) if subject else 0.0,
        )
        if score > best_score:
            best_score = score
            best_code = code
            best_subject = str(row[1] or "").strip()
    if best_score < 0.25:
        return None, None, best_score
    return best_code, best_subject, best_score


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _fetch_ticket(ticket_code: str) -> dict | None:
    """Return a dict of the matched ticket's key fields, or None."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, ticket_code, status, priority,
                           priority_assigned_at, respond_due_at, resolved_at,
                           assigned_to_user_id, final_resolution, details
                    FROM tickets
                    WHERE ticket_code = %s
                    LIMIT 1
                    """,
                    (ticket_code,),
                )
                row = cur.fetchone()
    except Exception as exc:
        logger.warning("recurrence | _fetch_ticket failed: %s", exc)
        return None
    if not row:
        return None
    return {
        "id":                   row[0],
        "ticket_code":          row[1],
        "status":               row[2],
        "priority":             row[3],
        "priority_assigned_at": row[4],
        "respond_due_at":       row[5],
        "resolved_at":          row[6],
        "assigned_to_user_id":  row[7],
        "final_resolution":     row[8],
        "details":              row[9],
    }


def _write_ticket_link(ticket_id: str, linked_code: str) -> None:
    """Set linked_ticket_code and is_recurring on the new ticket (Branch D only)."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET linked_ticket_code = %s,
                        is_recurring = TRUE
                    WHERE id = %s::uuid
                    """,
                    (linked_code, ticket_id),
                )
    except Exception as exc:
        logger.warning("recurrence | _write_ticket_link failed: %s", exc)


def _cancel_new_ticket(ticket_id: str, old_ticket_code: str) -> None:
    """Set the new ticket to Linked status, write the link, and record the merge — single transaction."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET status             = 'Linked'::ticket_status,
                        linked_ticket_code = %s,
                        is_recurring       = TRUE
                    WHERE id = %s::uuid
                    """,
                    (old_ticket_code, ticket_id),
                )
                rows_updated = cur.rowcount
                if rows_updated == 0:
                    logger.warning("recurrence | _cancel_new_ticket: no row updated for ticket_id=%s", ticket_id)
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message)
                    VALUES (%s::uuid, 'merged_into_existing',
                            'Recurring submission — linked to existing ticket ' || %s)
                    """,
                    (ticket_id, old_ticket_code),
                )
    except Exception as exc:
        logger.warning("recurrence | _cancel_new_ticket failed: %s", exc)


# ---------------------------------------------------------------------------
# Branch determination
# ---------------------------------------------------------------------------

def _sla_pct(priority_assigned_at, respond_due_at) -> float | None:
    if not priority_assigned_at or not respond_due_at:
        return None
    now = datetime.now(_UTC)
    if priority_assigned_at.tzinfo is None:
        priority_assigned_at = priority_assigned_at.replace(tzinfo=_UTC)
    if respond_due_at.tzinfo is None:
        respond_due_at = respond_due_at.replace(tzinfo=_UTC)
    total = (respond_due_at - priority_assigned_at).total_seconds()
    if total <= 0:
        return 1.0
    elapsed = (now - priority_assigned_at).total_seconds()
    return max(0.0, elapsed / total)


def _is_within_one_month(resolved_at: datetime) -> bool:
    now = datetime.now(_UTC)
    if resolved_at.tzinfo is None:
        resolved_at = resolved_at.replace(tzinfo=_UTC)
    return (now - resolved_at).days < 30


def _has_recurrence_escalation(ticket_id: str) -> bool:
    """Return True if this ticket has already been escalated via recurrence (Branch B)."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM ticket_updates
                    WHERE ticket_id = %s
                      AND update_type = 'recurrence_escalation'
                    LIMIT 1
                    """,
                    (ticket_id,),
                )
                return cur.fetchone() is not None
    except Exception as exc:
        logger.warning("recurrence | _has_recurrence_escalation check failed: %s", exc)
        return False


def _determine_branch(matched: dict) -> str:
    status = matched["status"]
    resolved_at = matched["resolved_at"]

    if status == "Resolved":
        if resolved_at and _is_within_one_month(resolved_at):
            return "C"
        return "D"

    if status in _OPEN_STATUSES:
        pct = _sla_pct(matched["priority_assigned_at"], matched["respond_due_at"])
        # SLA not started yet → treat as < 50% (branch A)
        if pct is None or pct < 0.50:
            return "A"
        # SLA ≥ 50% — only escalate once per ticket via recurrence
        if _has_recurrence_escalation(matched["id"]):
            logger.info(
                "recurrence | ticket %s already recurrence-escalated — downgrading B → A",
                matched["ticket_code"],
            )
            return "A"
        return "B"

    # Unknown status — fall through as new ticket
    return "D"


# ---------------------------------------------------------------------------
# Branch actions
# ---------------------------------------------------------------------------

def _send_reminder_notification(matched: dict, new_ticket_code: str, context_msg: str) -> None:
    """Write a recurrence_reminder notification and a ticket_update on the old ticket."""
    assigned_user_id = matched.get("assigned_to_user_id")
    old_ticket_id = matched["id"]
    old_ticket_code = matched["ticket_code"]
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                if assigned_user_id:
                    cur.execute(
                        """
                        INSERT INTO notifications (user_id, type, title, message, ticket_id)
                        VALUES (%s, 'recurrence_reminder'::notification_type,
                                'Recurring Ticket Submission',
                                %s,
                                %s)
                        """,
                        (
                            assigned_user_id,
                            f"A recurring submission was received for ticket {old_ticket_code}. "
                            f"New submission: {new_ticket_code}. {context_msg}",
                            old_ticket_id,
                        ),
                    )
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message)
                    VALUES (%s, 'recurrence_reminder', %s)
                    """,
                    (old_ticket_id, f"Recurring submission {new_ticket_code}. {context_msg}"),
                )
    except Exception as exc:
        logger.warning("recurrence | _send_reminder_notification failed: %s", exc)


def _branch_a(matched: dict, new_ticket_code: str) -> None:
    """Branch A: open + SLA < 50% → employee reminder only."""
    _send_reminder_notification(
        matched,
        new_ticket_code,
        context_msg="SLA < 50% elapsed — no priority change.",
    )
    logger.info("recurrence | branch A: reminder sent for ticket %s", matched["ticket_code"])


def _branch_b(matched: dict, new_ticket_code: str) -> None:
    """Branch B: open + SLA ≥ 50% → reminder + priority +1 (skip if Critical)."""
    current_priority = matched.get("priority") or "Medium"
    old_ticket_id = matched["id"]
    old_ticket_code = matched["ticket_code"]

    new_priority = current_priority
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                if current_priority != "Critical":
                    idx = _PRIORITY_ORDER.index(current_priority) if current_priority in _PRIORITY_ORDER else 1
                    new_priority = _PRIORITY_ORDER[min(idx + 1, len(_PRIORITY_ORDER) - 1)]
                    cur.execute(
                        """
                        UPDATE tickets
                        SET priority = %s::ticket_priority,
                            is_recurring = TRUE
                        WHERE id = %s
                        """,
                        (new_priority, old_ticket_id),
                    )
                escalation_msg = (
                    f"Priority escalated {current_priority} → {new_priority} "
                    f"(SLA ≥ 50%, recurring submission {new_ticket_code})."
                    if current_priority != "Critical"
                    else f"Already Critical — no priority change "
                    f"(SLA ≥ 50%, recurring submission {new_ticket_code})."
                )
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message)
                    VALUES (%s, 'recurrence_escalation', %s)
                    """,
                    (old_ticket_id, escalation_msg),
                )
    except Exception as exc:
        logger.warning("recurrence | _branch_b priority update failed: %s", exc)

    _send_reminder_notification(
        matched,
        new_ticket_code,
        context_msg=f"SLA ≥ 50% elapsed — priority escalated to {new_priority}.",
    )
    logger.info(
        "recurrence | branch B: escalated %s → %s for ticket %s",
        current_priority, new_priority, old_ticket_code,
    )


def _branch_c(matched: dict, new_submission_text: str) -> None:
    """Branch C: resolved < 1 month → reopen, assign back, attach last resolution."""
    old_ticket_id = matched["id"]
    old_ticket_code = matched["ticket_code"]
    assigned_user_id = matched.get("assigned_to_user_id")
    resolution_note = (matched.get("final_resolution") or "(no resolution recorded)")[:300]
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET status               = 'Reopened'::ticket_status,
                        first_response_at    = NULL,
                        priority_assigned_at = now(),
                        is_recurring         = TRUE
                    WHERE id = %s
                      AND status = 'Resolved'::ticket_status
                    """,
                    (old_ticket_id,),
                )
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message)
                    VALUES (%s, 'recurrence_reopen', %s)
                    """,
                    (
                        old_ticket_id,
                        f"Ticket reopened — recurring issue reported within 1 month of resolution. "
                        f"Last resolution: {resolution_note} | "
                        f"New submission: {new_submission_text[:300]}",
                    ),
                )
                # Archive the previous resolution cleanly for UI display
                prev_res_payload = json.dumps({
                    "resolved_at": matched.get("resolved_at").isoformat() if matched.get("resolved_at") else None,
                    "resolution": matched.get("final_resolution") or "(no resolution recorded)",
                })
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message)
                    VALUES (%s, 'previous_resolution', %s)
                    """,
                    (old_ticket_id, prev_res_payload),
                )
                if assigned_user_id:
                    cur.execute(
                        """
                        INSERT INTO notifications (user_id, type, title, message, ticket_id)
                        VALUES (%s, 'recurrence_reminder'::notification_type,
                                'Ticket Reopened — Recurring Issue',
                                %s,
                                %s)
                        """,
                        (
                            assigned_user_id,
                            f"Ticket {old_ticket_code} has been reopened due to a recurring submission "
                            f"within 1 month of resolution.",
                            old_ticket_id,
                        ),
                    )
    except Exception as exc:
        logger.warning("recurrence | _branch_c reopen failed: %s", exc)

    logger.info("recurrence | branch C: reopened ticket %s (status → Reopened)", old_ticket_code)


# ---------------------------------------------------------------------------
# Main step
# ---------------------------------------------------------------------------

async def check_recurrence(state: dict) -> dict:
    text = str(state.get("text") or "").strip()
    ticket_code = str(state.get("ticket_code") or "").strip() or None
    ticket_id = str(state.get("ticket_id") or "").strip() or None
    created_by_user_id = str(state.get("created_by_user_id") or "").strip() or None

    if not text:
        state["is_recurring"] = False
        state["recurrence_branch"] = "none"
        return state

    matched_code, matched_subject, score = find_similar_ticket(
        text, ticket_code, created_by_user_id
    )
    state["recurrence_mode"] = "transformer" if encoder_is_available() else "heuristic_fallback"

    if not matched_code:
        state["is_recurring"] = False
        state["recurrence_branch"] = "none"
        state["similarity_score"] = round(score, 3) if score else None
        logger.info("recurrence | no similar ticket found (best score=%.3f)", score or 0.0)
        return state

    matched = _fetch_ticket(matched_code)
    if not matched:
        state["is_recurring"] = False
        state["recurrence_branch"] = "none"
        return state

    state["is_recurring"] = True
    state["similar_ticket_code"] = matched_code
    state["similar_ticket_subject"] = matched_subject
    state["similarity_score"] = round(score, 3)

    branch = _determine_branch(matched)
    state["recurrence_branch"] = branch

    if branch == "A":
        _branch_a(matched, new_ticket_code=ticket_code or "")
        if ticket_id:
            _cancel_new_ticket(ticket_id, matched_code)
        state["_recurrence_handled"] = True
        state["recurrence_reason"] = (
            f"Open ticket {matched_code} (SLA < 50%) — reminder sent"
        )

    elif branch == "B":
        _branch_b(matched, new_ticket_code=ticket_code or "")
        if ticket_id:
            _cancel_new_ticket(ticket_id, matched_code)
        state["_recurrence_handled"] = True
        state["recurrence_reason"] = (
            f"Open ticket {matched_code} (SLA ≥ 50%) — priority escalated + reminder sent"
        )

    elif branch == "C":
        _branch_c(matched, new_submission_text=text)
        if ticket_id:
            _cancel_new_ticket(ticket_id, matched_code)
        state["_recurrence_handled"] = True
        state["recurrence_reason"] = (
            f"Ticket {matched_code} resolved < 1 month ago — reopened"
        )

    elif branch == "D":
        # New ticket runs through pipeline — write link without cancelling
        if ticket_id:
            _write_ticket_link(ticket_id=ticket_id, linked_code=matched_code)
        # Inject prior context
        state["prior_ticket_code"] = matched_code
        state["prior_ticket_resolution"] = matched.get("final_resolution")
        state["prior_ticket_details"] = (matched.get("details") or "")[:500]
        state["recurrence_reason"] = (
            f"Prior ticket {matched_code} resolved > 1 month ago — new ticket, old ticket referenced"
        )
        logger.info(
            "recurrence | branch D: new ticket linked to %s (fresh pipeline — old ticket referenced only)",
            matched_code,
        )

    logger.info(
        "recurrence | branch=%s ticket=%s similar=%s score=%.3f",
        branch, ticket_code, matched_code, score,
    )
    return state
