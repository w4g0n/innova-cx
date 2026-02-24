-- =============================================================================
-- Chatbot service database objects
-- PostgreSQL 14+   |   Safe to run multiple times (idempotent)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- Automatic updated_at trigger (shared by any table that needs it)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- -----------------------------------------------------------------------------
-- sessions
-- One row per conversation. Tracks state machine position and turn history.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    current_state TEXT        NOT NULL DEFAULT 'greeting',
    context       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    history       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id   ON sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions (updated_at);

-- Keep updated_at current automatically
DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions;
CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- user_chat_logs
-- One row per user message. Source for sentiment analysis feed.
--
-- intent_detected  : one of follow_up | create_ticket | inquiry | complaint | unknown
-- aggression_score : 0.000–1.000  (flagged when >= 0.750)
-- ticket_id        : populated once a ticket is created for this session,
--                    allows direct join without going through sessions
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_chat_logs (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id       UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    user_id          UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticket_id        UUID        REFERENCES tickets(id) ON DELETE SET NULL,
    message          TEXT        NOT NULL,
    intent_detected  TEXT,
    aggression_flag  BOOLEAN     NOT NULL DEFAULT FALSE,
    aggression_score REAL        CHECK (aggression_score BETWEEN 0 AND 1),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_chat_logs_session    ON user_chat_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_user       ON user_chat_logs (user_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_ticket     ON user_chat_logs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_user_chat_logs_created_at ON user_chat_logs (created_at);

-- -----------------------------------------------------------------------------
-- bot_response_logs
-- One row per bot response. Source for chatbot analytics.
--
-- response_type  : greeting | prompt_ticket_id | ticket_status | open_tickets_list |
--                  prompt_ticket_type | inquiry_kb_answer | inquiry_falcon_fallback |
--                  inquiry_escalate_to_ticket | inquiry_resolved | complaint_deescalate |
--                  collected_asset_type | ticket_created | ticket_create_error |
--                  escalation | clarify | fallback
-- state_at_time  : value of sessions.current_state when this response was generated
-- kb_match_score : cosine similarity score from knowledge base lookup (0–1)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bot_response_logs (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    ticket_id      UUID        REFERENCES tickets(id) ON DELETE SET NULL,
    response       TEXT        NOT NULL,
    response_type  TEXT,
    state_at_time  TEXT,
    sql_query_used TEXT,
    kb_match_score REAL        CHECK (kb_match_score BETWEEN 0 AND 1),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_response_logs_session    ON bot_response_logs (session_id);
CREATE INDEX IF NOT EXISTS idx_bot_response_logs_ticket     ON bot_response_logs (ticket_id);
CREATE INDEX IF NOT EXISTS idx_bot_response_logs_created_at ON bot_response_logs (created_at);

-- -----------------------------------------------------------------------------
-- Read-only role for chatbot ticket lookup (Text-to-SQL agent)
-- Uncomment and set a strong password before running in production.
-- -----------------------------------------------------------------------------
-- CREATE ROLE chatbot_ro LOGIN PASSWORD 'change-me';
-- GRANT CONNECT ON DATABASE complaints_db TO chatbot_ro;
-- GRANT USAGE ON SCHEMA public TO chatbot_ro;
-- GRANT SELECT ON tickets, users TO chatbot_ro;
