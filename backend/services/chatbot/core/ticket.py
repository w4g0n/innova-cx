import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"inquiry", "complaint"}


def create_ticket(
    user_id: str,
    session_id: str,
    category: str,
    description: str,
    title: str = "",
) -> dict:
    _ = session_id
    category = (category or "").strip().lower()

    if category not in VALID_CATEGORIES:
        return {"success": False, "ticket_id": None, "error": f"Invalid category: {category}"}

    description = (description or "").strip()
    if not description:
        return {"success": False, "ticket_id": None, "error": "Description cannot be empty"}

    if not title:
        if len(description) <= 80:
            title = description
        else:
            truncated = description[:80]
            last_space = truncated.rfind(" ")
            title = truncated[:last_space] if last_space > 0 else truncated
    else:
        title = str(title).strip()

    api_base = os.environ.get("BACKEND_API_URL", "http://backend:8000")
    local_fallback = os.environ.get("BACKEND_API_URL_LOCAL", "http://localhost:8000")

    payload = {
        "created_by_user_id": user_id,
        "ticket_type": category,  # backend maps inquiry/complaint
        "subject": title,
        "details": description,
        "ticket_source": "chatbot",
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    last_error = None
    for base in (api_base, local_fallback):
        req = urllib.request.Request(
            f"{base}/api/internal/tickets/create",
            data=payload_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
                parsed = json.loads(raw) if raw else {}
                ticket_code = parsed.get("ticket_id")
                if ticket_code:
                    logger.info("chatbot_ticket_create | ok ticket=%s via=%s", ticket_code, base)
                    return {"success": True, "ticket_id": ticket_code, "error": None, "is_recurring": False}
                last_error = "Ticket gate returned no ticket_id"
                logger.warning("chatbot_ticket_create | missing ticket_id via=%s body=%s", base, raw)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = str(e)
            last_error = f"{e.code}: {body}"
            logger.warning("chatbot_ticket_create | http_error via=%s err=%s", base, last_error)
        except Exception as e:
            last_error = str(e)
            logger.warning("chatbot_ticket_create | error via=%s err=%s", base, last_error)

    logger.error("chatbot_ticket_create | gate_unavailable err=%s", last_error)
    return {
        "success": False,
        "ticket_id": None,
        "error": f"Ticket creation gate unavailable: {last_error}",
    }
