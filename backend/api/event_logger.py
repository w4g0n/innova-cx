import json
import os
import uuid
from typing import Any, Optional

import psycopg2


def _build_dsn() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_app")
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError("DB_PASSWORD env var must be set")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def _coerce_uuid_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


def _safe_payload(payload: Any) -> dict:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        candidate = payload
    else:
        candidate = {"value": payload}
    try:
        return json.loads(json.dumps(candidate, default=str))
    except (TypeError, ValueError):
        return {"_serialization_error": str(payload)[:500]}


def log_application_event(
    *,
    service: str,
    event_key: str,
    level: str = "INFO",
    ticket_id: Any = None,
    ticket_code: Optional[str] = None,
    execution_id: Any = None,
    payload: Optional[dict] = None,
    cur=None,
) -> None:
    ticket_uuid = _coerce_uuid_or_none(ticket_id)
    execution_uuid = _coerce_uuid_or_none(execution_id)
    payload_json = _safe_payload(payload)
    sql = """
        INSERT INTO application_event_log
            (service, event_key, ticket_id, ticket_code, execution_id, level, payload)
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
    """
    params = (
        service,
        event_key,
        ticket_uuid,
        ticket_code,
        execution_uuid,
        level,
        json.dumps(payload_json),
    )
    try:
        if cur is not None:
            cur.execute(sql, params)
            return
        with psycopg2.connect(_build_dsn()) as conn:
            with conn.cursor() as db_cur:
                db_cur.execute(sql, params)
    except Exception:
        # Never break request flow because event logging failed.
        return