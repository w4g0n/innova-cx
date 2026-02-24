import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from .db import engine


def log_user_message(
    session_id: str,
    user_id: str,
    message: str,
    intent_detected: str = None,
    aggression_flag: bool = False,
    aggression_score: float = 0.0,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO user_chat_logs "
                "(id, session_id, user_id, message, intent_detected, aggression_flag, aggression_score, created_at) "
                "VALUES (:id, :sid, :uid, :msg, :intent, :agg, :score, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "sid": session_id,
                "uid": user_id,
                "msg": message,
                "intent": intent_detected,
                "agg": aggression_flag,
                "score": aggression_score,
                "now": datetime.now(timezone.utc),
            },
        )


def log_bot_response(
    session_id: str,
    response: str,
    response_type: str = None,
    state_at_time: str = None,
    sql_query: str = None,
    kb_score: float = None,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO bot_response_logs "
                "(id, session_id, response, response_type, state_at_time, sql_query_used, kb_match_score, created_at) "
                "VALUES (:id, :sid, :resp, :rtype, :state, :sql, :kb, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "sid": session_id,
                "resp": response,
                "rtype": response_type,
                "state": state_at_time,
                "sql": sql_query,
                "kb": kb_score,
                "now": datetime.now(timezone.utc),
            },
        )
