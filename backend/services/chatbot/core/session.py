import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from .db import engine

MAX_HISTORY = 10


def _to_json_obj(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def load_session(session_id: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT current_state, context, history FROM sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()
    if row is None:
        raise ValueError(f"Session {session_id} not found")

    return {
        "session_id": session_id,
        "current_state": row.current_state,
        "context": _to_json_obj(row.context, {}),
        "history": _to_json_obj(row.history, []),
    }


def session_belongs_to_user(session_id: str, user_id: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM sessions WHERE session_id = :sid AND user_id = :uid"),
            {"sid": session_id, "uid": user_id},
        ).fetchone()
    return row is not None


def create_session(user_id: str) -> str:
    session_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO sessions (session_id, user_id, current_state, context, history, created_at, updated_at) "
                "VALUES (:sid, :uid, 'greeting', :ctx, :hist, :now, :now)"
            ),
            {
                "sid": session_id,
                "uid": user_id,
                "ctx": json.dumps({}),
                "hist": json.dumps([]),
                "now": datetime.now(timezone.utc),
            },
        )
    return session_id


def save_session(session: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE sessions SET current_state=:state, context=:ctx, history=:hist, "
                "updated_at=:now WHERE session_id=:sid"
            ),
            {
                "state": session["current_state"],
                "ctx": json.dumps(session["context"]),
                "hist": json.dumps(session["history"][-MAX_HISTORY:]),
                "now": datetime.now(timezone.utc),
                "sid": session["session_id"],
            },
        )


def append_history(session: dict, role: str, content: str) -> None:
    session["history"].append({"role": role, "content": content})


def transition(session: dict, new_state: str) -> None:
    session["current_state"] = new_state
