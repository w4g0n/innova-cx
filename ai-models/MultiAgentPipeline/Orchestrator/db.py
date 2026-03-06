"""
Orchestrator DB helper — write-only access for execution logging.
"""

import os
import logging

import psycopg2

logger = logging.getLogger(__name__)


def _build_dsn() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_admin")
    password = os.getenv("DB_PASSWORD", "changeme123")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def db_connect():
    """Return a new psycopg2 connection (auto-commit context manager)."""
    return psycopg2.connect(_build_dsn())


def ensure_log_tables() -> None:
    """Idempotent DDL — creates logging tables if they don't exist. Safe on every startup."""
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS model_execution_log (
                        id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                        execution_id      UUID        NOT NULL,
                        ticket_id         UUID,
                        agent_name        VARCHAR(80) NOT NULL,
                        model_version     VARCHAR(50),
                        inference_time_ms INTEGER     NOT NULL DEFAULT 0,
                        confidence_score  NUMERIC(5,4),
                        error_flag        BOOLEAN     NOT NULL DEFAULT FALSE,
                        error_message     TEXT,
                        created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                """)
                # Backward/forward compatibility with older/newer schemas.
                cur.execute("ALTER TABLE model_execution_log ADD COLUMN IF NOT EXISTS agent_name_old VARCHAR(120);")
                cur.execute("ALTER TABLE model_execution_log ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;")
                cur.execute("ALTER TABLE model_execution_log ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;")
                cur.execute("ALTER TABLE model_execution_log ADD COLUMN IF NOT EXISTS status VARCHAR(30);")
                cur.execute(
                    "ALTER TABLE model_execution_log ADD COLUMN IF NOT EXISTS infra_metadata JSONB DEFAULT '{}'::jsonb;"
                )
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS agent_output_log (
                        id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                        execution_id      UUID        NOT NULL,
                        ticket_id         UUID,
                        agent_name        VARCHAR(80) NOT NULL,
                        step_order        INTEGER     NOT NULL,
                        input_state       JSONB       NOT NULL DEFAULT '{}'::jsonb,
                        output_state      JSONB       NOT NULL DEFAULT '{}'::jsonb,
                        state_diff        JSONB       NOT NULL DEFAULT '{}'::jsonb,
                        inference_time_ms INTEGER     NOT NULL DEFAULT 0,
                        error_flag        BOOLEAN     NOT NULL DEFAULT FALSE,
                        error_message     TEXT,
                        created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_mel_execution_id ON model_execution_log(execution_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_mel_ticket_id    ON model_execution_log(ticket_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_mel_agent_name   ON model_execution_log(agent_name);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_mel_created_at   ON model_execution_log(created_at);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_aol_execution_id ON agent_output_log(execution_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_aol_ticket_id    ON agent_output_log(ticket_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_aol_agent_name   ON agent_output_log(agent_name);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_aol_created_at   ON agent_output_log(created_at);")
        logger.info("execution_log | tables ensured")
    except Exception as exc:
        logger.warning("execution_log | DDL failed (non-fatal): %s", exc)
