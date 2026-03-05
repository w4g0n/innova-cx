import logging
import os
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

from sqlalchemy import text

from .db import engine

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"inquiry", "complaint"}

ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:8004")
ORCHESTRATOR_URL_LOCAL = os.environ.get("ORCHESTRATOR_URL_LOCAL", "http://localhost:8004")


# ── Orchestrator dispatch (fire-and-forget) ──────────────────────────────────

def _dispatch_to_orchestrator(ticket_id: str, description: str, category: str) -> None:
    """Send ticket to ML pipeline for analysis. Runs in a daemon thread."""
    payload = urlencode({
        "text": description,
        "ticket_id": ticket_id,
        "ticket_type": category,
    }).encode("utf-8")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    for base in (ORCHESTRATOR_URL, ORCHESTRATOR_URL_LOCAL):
        try:
            req = urllib.request.Request(
                f"{base}/process/text",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                logger.info(
                    "orchestrator_dispatch | ticket_id=%s status=%s via %s",
                    ticket_id, resp.status, base,
                )
                return
        except Exception as e:
            logger.warning("orchestrator_dispatch | base=%s err=%s", base, e)
            continue

    logger.error(
        "orchestrator_dispatch | all endpoints failed for ticket=%s", ticket_id
    )


# ── Ticket creation (direct DB insert) ──────────────────────────────────────

def create_ticket(
    user_id: str,
    session_id: str,
    category: str,
    description: str,
    title: str = "",
) -> dict:
    _ = session_id
    category = category.strip().lower()

    if category not in VALID_CATEGORIES:
        return {"success": False, "ticket_id": None, "error": f"Invalid category: {category}"}

    # DB enum uses capitalized values: Complaint, Inquiry
    db_ticket_type = category.capitalize()
    if not description.strip():
        return {"success": False, "ticket_id": None, "error": "Description cannot be empty"}

    if not title:
        title = description[:80]

    ticket_code = f"CX-{int(time.time() * 1000)}-{os.urandom(2).hex().upper()}"

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO tickets (
                        ticket_code, ticket_type, subject, details,
                        priority, status, created_by_user_id,
                        created_at
                    ) VALUES (
                        :ticket_code, :ticket_type, :subject, :details,
                        :priority, :status, :user_id,
                        NOW()
                    )
                """),
                {
                    "ticket_code": ticket_code,
                    "ticket_type": db_ticket_type,
                    "subject": title,
                    "details": description,
                    "priority": "Low",
                    "status": "Open",
                    "user_id": user_id,
                },
            )

        # Fire-and-forget: dispatch to ML orchestrator pipeline
        thread = threading.Thread(
            target=_dispatch_to_orchestrator,
            args=(ticket_code, description, category),
            daemon=True,
        )
        thread.start()
        logger.info("create_ticket | ticket=%s dispatched to orchestrator", ticket_code)

        return {"success": True, "ticket_id": ticket_code, "error": None, "is_recurring": False}

    except Exception as e:
        logger.error("create_ticket | DB insert failed: %s", e)
        return {
            "success": False,
            "ticket_id": None,
            "error": f"Database error: {e}",
        }
