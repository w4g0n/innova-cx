import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from .db import engine

VALID_ASSET_TYPES = {"office", "warehouse", "retail"}
VALID_CATEGORIES = {"inquiry", "complaint"}


def create_ticket(
    user_id: str,
    session_id: str,
    category: str,
    asset_type: str,
    description: str,
    title: str = "",
) -> dict:
    category = category.strip().lower()
    asset_type = asset_type.strip().lower()

    if category not in VALID_CATEGORIES:
        return {"success": False, "ticket_id": None, "error": f"Invalid category: {category}"}
    if asset_type not in VALID_ASSET_TYPES:
        return {"success": False, "ticket_id": None, "error": f"Invalid asset_type: {asset_type}"}
    if not description.strip():
        return {"success": False, "ticket_id": None, "error": "Description cannot be empty"}

    ticket_id = str(uuid.uuid4())
    if not title:
        title = description[:80]

    ticket_code = f"CX-{uuid.uuid4().hex[:10].upper()}"
    ticket_type = "Inquiry" if category == "inquiry" else "Complaint"
    status = "Open"
    normalized_asset = asset_type.title()

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO tickets "
                    "(id, ticket_code, subject, details, ticket_type, status, asset_type, created_by_user_id, created_at, updated_at) "
                    "VALUES (:tid, :code, :subject, :details, :type, :status, :asset, :uid, :now, :now)"
                ),
                {
                    "tid": ticket_id,
                    "code": ticket_code,
                    "subject": title,
                    "details": description,
                    "type": ticket_type,
                    "status": status,
                    "asset": normalized_asset,
                    "uid": user_id,
                    "now": datetime.now(timezone.utc),
                },
            )
    except Exception as e:
        return {"success": False, "ticket_id": None, "error": str(e)}

    return {"success": True, "ticket_id": ticket_code, "error": None}
