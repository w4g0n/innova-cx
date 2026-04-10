# backend/api/main.py

import os
import time
import json
import logging
import asyncio
import hmac
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from starlette.middleware.base import BaseHTTPMiddleware
import resend

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
import httpx

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Query, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator

import pyotp  # for RFC 6238 TOTP
import qrcode
import io
import re as _re
import secrets
import uuid as _uuid_mod
try:
    from api.ticket_creation_gate import create_ticket_via_gate, dispatch_ticket_to_orchestrator
except Exception:
    from ticket_creation_gate import create_ticket_via_gate, dispatch_ticket_to_orchestrator
try:
    from api.auto_assign_employee import auto_assign_ticket_if_needed
except Exception:
    from auto_assign_employee import auto_assign_ticket_if_needed
try:
    from api.department_routing_service import (
        build_routing_meta,
        decide_routing_review as decide_routing_review_service,
        get_routing_review_payload,
        record_department_routing_decision,
    )
except Exception:
    from department_routing_service import (
        build_routing_meta,
        decide_routing_review as decide_routing_review_service,
        get_routing_review_payload,
        record_department_routing_decision,
    )
try:
    from api.ai_explainability import router as ai_explainability_router
except Exception:
    from ai_explainability import router as ai_explainability_router
try:
    from api.pipeline_queue_api import router as pipeline_queue_router
except Exception:
    from pipeline_queue_api import router as pipeline_queue_router
try:
    from api.event_logger import log_application_event
except Exception:
    from event_logger import log_application_event
try:
    from api.security_hardening import (
        SecurityHeadersMiddleware,
        get_limiter,
        rate_limit_auth,
        SLOWAPI_AVAILABLE,
        validate_password_complexity,
        is_account_locked,
        check_and_record_failed_login,
        clear_failed_logins,
        log_auth_event,
        sanitize_email,
        validate_upload_file,
        _sanitize_filename,
        logout_user,
        is_token_revoked,
        generate_csrf_token,
        verify_csrf_token,
    )
except Exception:
    from security_hardening import (
        SecurityHeadersMiddleware,
        get_limiter,
        rate_limit_auth,
        SLOWAPI_AVAILABLE,
        validate_password_complexity,
        is_account_locked,
        check_and_record_failed_login,
        clear_failed_logins,
        log_auth_event,
        sanitize_email,
        validate_upload_file,
        _sanitize_filename,
        logout_user,
        is_token_revoked,
        generate_csrf_token,
        verify_csrf_token,
    )

# Analytics service (reads from materialized views)
try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from services import analytics_service as _analytics
    _ANALYTICS_READY = True
except Exception as _analytics_import_err:
    _analytics = None
    _ANALYTICS_READY = False
    import logging as _log
    _log.getLogger(__name__).warning(
        "analytics_service not loaded — manager trends will use raw SQL fallback. err=%s",
        _analytics_import_err
    )


logger = logging.getLogger(__name__)
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.WARNING), format="%(asctime)s | %(levelname)s | %(message)s")
SLA_HEARTBEAT_SECONDS = int(os.getenv("SLA_HEARTBEAT_SECONDS", "300"))
# Keep backward compatibility with ROUTING_CONFIDENCE_THRESHOLD while standardizing on
# DEPARTMENT_ROUTING_THRESHOLD used by orchestrator/.env.
ROUTING_CONFIDENCE_THRESHOLD = float(
    os.getenv(
        "DEPARTMENT_ROUTING_THRESHOLD",
        os.getenv("ROUTING_CONFIDENCE_THRESHOLD", "0.20"),
    )
)
CHATBOT_PROXY_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_PROXY_TIMEOUT_SECONDS", "30"))
MAX_CUSTOMER_TEXT_WORDS = 250
ANALYTICS_REFRESH_INTERVAL_SECONDS = int(os.getenv("ANALYTICS_REFRESH_INTERVAL_HOURS", "12")) * 3600
_sla_heartbeat_task: Optional[asyncio.Task] = None
_analytics_refresh_task: Optional[asyncio.Task] = None
_has_sla_policy_fn = False

resend.api_key = os.environ.get("RESEND_API_KEY")
# App
_EXPOSE_DOCS = os.getenv("EXPOSE_API_DOCS", "false").lower() == "true"
app = FastAPI(
    title="InnovaCX API",
    docs_url="/docs" if _EXPOSE_DOCS else None,
    redoc_url="/redoc" if _EXPOSE_DOCS else None,
    openapi_url="/openapi.json" if _EXPOSE_DOCS else None,
)

if SLOWAPI_AVAILABLE:
    try:
        app.state.limiter = get_limiter()
    except Exception as exc:
        logger.warning("rate_limit | limiter init failed: %s", exc)


def _parse_allowed_origins() -> List[str]:
    configured = os.getenv("ALLOWED_ORIGINS", "").strip()
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [
        "http://innovacx.net",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


ALLOWED_ORIGINS = _parse_allowed_origins()

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "X-Internal-Key", "X-Trust-Token"],
)


# CSP Middleware

class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(CSPMiddleware)


api = APIRouter(prefix="/api")


def _word_count(value: str) -> int:
    return len(str(value or "").split())


def _validate_customer_text_words(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return value
    if _word_count(value) > MAX_CUSTOMER_TEXT_WORDS:
        raise ValueError(f"{field_name} must be {MAX_CUSTOMER_TEXT_WORDS} words or fewer.")
    return value


def _ensure_uploads_root() -> str:
    # Use env var if provided, otherwise default
    root = os.getenv("UPLOADS_DIR", "/app/uploads")
    os.makedirs(root, exist_ok=True)
    return root


# Database helpers
def build_default_dsn() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_app")
    password = os.getenv("DB_PASSWORD", "changeme123")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def get_dsn() -> str:
    return os.getenv("DATABASE_URL") or build_default_dsn()


def db_connect():
    try:
        return psycopg2.connect(get_dsn())
    except OperationalError as e:
        logger.error("db_connect | connection failed: %s", e)
        raise HTTPException(status_code=500, detail="A server error occurred. Please try again later.")


def _ensure_runtime_schema_compatibility() -> None:
    """
    Keeps backend compatible with older DB volumes that skipped newer SQL scripts.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                # Runtime role is least-privilege (innovacx_app). Owner-level ALTERs
                # should only run when connected as the table owner.
                cur.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1
                      FROM pg_class c
                      JOIN pg_namespace n ON n.oid = c.relnamespace
                      WHERE n.nspname = 'public'
                        AND c.relname = 'tickets'
                        AND c.relkind = 'r'
                        AND pg_get_userbyid(c.relowner) = current_user
                    )
                    """
                )
                owns_tickets = bool((cur.fetchone() or [False])[0])
                if not owns_tickets:
                    logger.info("db_compat | skipping owner-only compatibility DDL for runtime DB role")
                    return

                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS asset_type TEXT;")
                cur.execute("UPDATE tickets SET asset_type = 'General' WHERE asset_type IS NULL OR btrim(asset_type) = '';")
                cur.execute("ALTER TABLE tickets ALTER COLUMN asset_type SET DEFAULT 'General';")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS priority_assigned_at TIMESTAMPTZ;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS respond_time_left_seconds INTEGER;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolve_time_left_seconds INTEGER;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS ticket_source TEXT;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution TEXT;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_model TEXT;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_generated_at TIMESTAMPTZ;")
                cur.execute("ALTER TABLE tickets ALTER COLUMN ticket_type DROP NOT NULL;")
                cur.execute("ALTER TABLE tickets ALTER COLUMN ticket_type DROP DEFAULT;")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS suggested_resolution_usage (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      ticket_id UUID REFERENCES tickets(id) ON DELETE CASCADE,
                      employee_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                      decision TEXT CHECK (decision IN ('accepted', 'declined_custom')),
                      actor_role TEXT NOT NULL DEFAULT 'employee' CHECK (actor_role IN ('manager', 'operator', 'employee')),
                      department TEXT NOT NULL,
                      suggested_text TEXT,
                      final_text TEXT,
                      used BOOLEAN NOT NULL DEFAULT TRUE,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                cur.execute("ALTER TABLE suggested_resolution_usage ADD COLUMN IF NOT EXISTS employee_user_id UUID REFERENCES users(id) ON DELETE SET NULL;")
                cur.execute("ALTER TABLE suggested_resolution_usage ADD COLUMN IF NOT EXISTS decision TEXT;")
                cur.execute("ALTER TABLE suggested_resolution_usage ADD COLUMN IF NOT EXISTS actor_role TEXT;")
                cur.execute("UPDATE suggested_resolution_usage SET actor_role = 'employee' WHERE actor_role IS NULL OR btrim(actor_role) = '';")
                cur.execute(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'suggested_resolution_usage_decision_check'
                      ) THEN
                        ALTER TABLE suggested_resolution_usage
                        ADD CONSTRAINT suggested_resolution_usage_decision_check
                        CHECK (decision IN ('accepted', 'declined_custom') OR decision IS NULL);
                      END IF;
                    END$$;
                    """
                )
                cur.execute(
                    """
                    DO $$
                    BEGIN
                      IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'suggested_resolution_usage_actor_role_check'
                      ) THEN
                        ALTER TABLE suggested_resolution_usage
                        ADD CONSTRAINT suggested_resolution_usage_actor_role_check
                        CHECK (actor_role IN ('manager', 'operator', 'employee'));
                      END IF;
                    END$$;
                    """
                )
                cur.execute("ALTER TABLE suggested_resolution_usage ALTER COLUMN actor_role SET DEFAULT 'employee';")
                cur.execute("ALTER TABLE suggested_resolution_usage ALTER COLUMN actor_role SET NOT NULL;")
                # Ensure MFA columns exist even on older volumes
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
                # password_changed_at: used by reset_password to stamp the moment
                # a password was changed via reset flow, enabling stale-session detection.
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ;")
                # FIX (Issue 3 — department_routing table missing):
                # The live DB volume may pre-date when department_routing was added to init.sql.
                # Create it here idempotently so the routing review feature works on all envs.
                # Note: routed_by includes manager_denied (used by the Deny routing action).
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS department_routing (
                      id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      ticket_id            UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                      suggested_department TEXT NOT NULL,
                      confidence_score     NUMERIC(5,2) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
                      is_confident         BOOLEAN NOT NULL,
                      final_department     TEXT,
                      routed_by            TEXT CHECK (routed_by IN ('model', 'manager', 'manager_denied')),
                      manager_id           UUID REFERENCES users(id) ON DELETE SET NULL,
                      created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
                      updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_department_routing_ticket ON department_routing(ticket_id);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_department_routing_pending ON department_routing(is_confident, final_department, created_at DESC);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_department_routing_finalized ON department_routing(final_department, routed_by, updated_at DESC);")
                # If the table already existed with the old constraint (no manager_denied),
                # widen it safely. PostgreSQL allows dropping and re-adding a CHECK constraint.
                cur.execute("""
                    DO $$
                    BEGIN
                        ALTER TABLE department_routing DROP CONSTRAINT IF EXISTS department_routing_routed_by_check;
                        ALTER TABLE department_routing ADD CONSTRAINT department_routing_routed_by_check
                            CHECK (routed_by IN ('model', 'manager', 'manager_denied'));
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END $$;
                """)
    except Exception as exc:
        logger.warning("db_compat | failed to apply compatibility DDL: %s", exc)


def _ensure_analytics_mvs() -> None:
    """
    Installs analytics materialized views if they don't exist yet.
    Delegates to analytics_service._ensure_analytics_mvs() which uses a
    Python DB connection — no psql binary required in the backend container.
    """
    if not _ANALYTICS_READY or _analytics is None:
        logger.info("_ensure_analytics_mvs | analytics_service not loaded — skipping")
        return
    try:
        _analytics._ensure_analytics_mvs()
    except Exception as _install_err:
        logger.error("_ensure_analytics_mvs | install failed: %s", _install_err)


def _detect_sla_policy_function() -> bool:
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT to_regprocedure('apply_ticket_sla_policies()') IS NOT NULL AS exists;")
                row = cur.fetchone() or {}
                return bool(row.get("exists"))
    except Exception:
        return False


def _clear_unassigned_sla_once() -> None:
    """
    App-level SLA gate:
    if department or assignee is missing, SLA must be unset and ticket cannot be Overdue.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tickets
                    SET
                      priority_assigned_at = NULL,
                      respond_due_at = NULL,
                      resolve_due_at = NULL,
                      respond_time_left_seconds = NULL,
                      resolve_time_left_seconds = NULL,
                      respond_breached = FALSE,
                      resolve_breached = FALSE,
                      status = CASE
                                 WHEN status = 'Overdue'::ticket_status THEN 'Open'::ticket_status
                                 ELSE status
                               END
                    WHERE status <> 'Resolved'::ticket_status
                      AND (department_id IS NULL OR assigned_to_user_id IS NULL)
                    """
                )
    except Exception:
        return


def _apply_sla_policies_once(log_result: bool = False, source: str = "request") -> None:
    """
    Applies time-based SLA policies (escalation/overdue) if migration is installed.
    Safe no-op when function is unavailable.
    """
    if not _has_sla_policy_fn:
        return
    try:
        _clear_unassigned_sla_once()
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT apply_ticket_sla_policies() AS result;")
                row = cur.fetchone() or {}
                if log_result:
                    logger.info(
                        "sla_heartbeat | source=%s interval_s=%s result=%s",
                        source,
                        SLA_HEARTBEAT_SECONDS,
                        row.get("result"),
                    )
    except Exception:
        return


async def _sla_heartbeat_loop() -> None:
    while True:
        await asyncio.to_thread(_apply_sla_policies_once, True, "timer")
        await asyncio.sleep(SLA_HEARTBEAT_SECONDS)


async def _analytics_refresh_loop() -> None:
    """Background task: refreshes all 4 materialized views on a repeating
    interval. Sleeps FIRST so the startup warm-up refresh isn't immediately
    duplicated. Interval is controlled by env var ANALYTICS_REFRESH_INTERVAL_HOURS
    (default 12 hours). Set to 0 to disable the loop entirely."""
    if ANALYTICS_REFRESH_INTERVAL_SECONDS <= 0:
        logger.info("analytics_refresh | loop disabled (ANALYTICS_REFRESH_INTERVAL_SECONDS=0)")
        return
    while True:
        await asyncio.sleep(ANALYTICS_REFRESH_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(_analytics.refresh_mvs)
            logger.info(
                "analytics_refresh | MVs refreshed (interval_s=%s)",
                ANALYTICS_REFRESH_INTERVAL_SECONDS,
            )
        except Exception as exc:
            logger.warning(
                "analytics_refresh | refresh failed — will retry next cycle. err=%s", exc
            )


def fetch_one(sql: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None


def fetch_all(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def execute(sql: str, params: Optional[tuple] = None) -> int:
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount


# Auth helpers (bcrypt + JWT)
_raw_jwt_secret = os.getenv("JWT_SECRET")
if not _raw_jwt_secret or len(_raw_jwt_secret) < 32:
    raise RuntimeError(
        "JWT_SECRET env var must be set to a random string of at least 32 characters. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
JWT_SECRET = _raw_jwt_secret
JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", "900"))  # 15 minutes
MFA_TEMP_TTL_SECONDS = int(os.getenv("MFA_TEMP_TTL_SECONDS", "900"))  # 15 minutes
DEV_LOG_RESET_TOKENS = os.getenv("DEV_LOG_RESET_TOKENS", "false").lower() == "true"
DISABLE_MFA = os.getenv("DISABLE_MFA", "false").lower() == "true"

DEV_SEED_USERS = os.getenv("DEV_SEED_USERS", "true").lower() == "true"
DEV_SEED_PASSWORD = os.getenv("DEV_SEED_PASSWORD", "Innova@2025")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64url_decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def create_jwt(payload: dict, ttl_seconds: int = JWT_TTL_SECONDS) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    if "jti" not in payload:
        payload = {**payload, "jti": os.urandom(16).hex()}
    payload = {**payload, "iat": now, "exp": now + ttl_seconds}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_jwt(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed token")
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(_b64url_encode(expected_sig), sig_b64):
            raise ValueError("Bad signature")

        payload = json.loads(_b64url_decode(payload_b64))
        if int(time.time()) > int(payload.get("exp", 0)):
            raise ValueError("Token expired")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _check_token_issued_after_password_change(payload: dict, user: dict) -> None:
    """
    Reject JWTs issued before the user's last password change.
    This invalidates all sessions that existed before a password reset.
    """
    password_changed_at = user.get("password_changed_at")
    if password_changed_at is None:
        return  # No password change recorded — token is fine

    iat = payload.get("iat")
    if iat is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Convert password_changed_at to a UTC Unix timestamp for comparison
    try:
        if hasattr(password_changed_at, "timestamp"):
            changed_ts = password_changed_at.timestamp()
        else:
            # Fallback: already a numeric value
            changed_ts = float(password_changed_at)
    except Exception:
        # If we cannot parse the timestamp, err on the side of caution
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Add a 2-second grace window to tolerate clock skew between
    # the token-issuance path and the password-change write path.
    if int(iat) < (changed_ts - 2):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


def _ensure_dev_seed_users() -> None:
    """
    Permanent fix: ensure demo users exist even when DB volume already exists.
    Idempotent: safe to run on every startup.
    """
    if not DEV_SEED_USERS:
        logger.info("dev_seed | disabled (DEV_SEED_USERS=false)")
        return

    demo_users = [
        ("customer1@innovacx.net", "customer"),
        ("customer2@innovacx.net", "customer"),
        ("customer3@innovacx.net", "customer"),
        ("operator@innovacx.net",  "operator"),
        ("hamad@innovacx.net",     "manager"),
        ("leen@innovacx.net",      "manager"),
        ("rami@innovacx.net",      "manager"),
        ("majid@innovacx.net",     "manager"),
        ("ali@innovacx.net",       "manager"),
        ("yara@innovacx.net",      "manager"),
        ("hana@innovacx.net",      "manager"),
        ("ahmed@innovacx.net",     "employee"),
        ("lena@innovacx.net",      "employee"),
        ("bilal@innovacx.net",     "employee"),
        ("sameer@innovacx.net",    "employee"),
        ("yousef@innovacx.net",    "employee"),
        ("talya@innovacx.net",     "employee"),
        ("sarah@innovacx.net",     "employee"),
    ]

    # Optional display names (won't break anything if missing)
    demo_names = {
        "customer1@innovacx.net": "Customer One",
        "customer2@innovacx.net": "Customer Two",
        "customer3@innovacx.net": "Customer Three",
        "operator@innovacx.net":  "System Operator",
        "hamad@innovacx.net":     "Hamad Alaa",
        "leen@innovacx.net":      "Leen Naser",
        "rami@innovacx.net":      "Rami Alassi",
        "majid@innovacx.net":     "Majid Sharaf",
        "ali@innovacx.net":       "Ali Al Maharif",
        "yara@innovacx.net":      "Yara Saab",
        "hana@innovacx.net":      "Hana Ayad",
        "ahmed@innovacx.net":     "Ahmed Hassan",
        "lena@innovacx.net":      "Lena Musa",
        "bilal@innovacx.net":     "Bilal Khan",
        "sameer@innovacx.net":    "Sameer Ahmed",
        "yousef@innovacx.net":    "Yousef Madi",
        "talya@innovacx.net":     "Talya Mohammad",
        "sarah@innovacx.net":     "Sarah Muneer",
    }

    try:
        pw_hash = hash_password(DEV_SEED_PASSWORD)

        with db_connect() as conn:
            with conn.cursor() as cur:
                for email, role in demo_users:
                    cur.execute(
                        """
                        INSERT INTO users (email, password_hash, role, is_active, mfa_enabled)
                        VALUES (%s, %s, %s, TRUE, FALSE)
                        ON CONFLICT (email) DO UPDATE
                        SET
                          password_hash = EXCLUDED.password_hash,
                          role = EXCLUDED.role,
                          is_active = TRUE,
                          mfa_enabled = FALSE;
                        """,
                        (email, pw_hash, role),
                    )

                # Ensure profiles exist (safe no-op if already there)
                for email, _role in demo_users:
                    full_name = demo_names.get(email, email)
                    cur.execute(
                        """
                        INSERT INTO user_profiles (user_id, full_name)
                        SELECT id, %s FROM users WHERE email = %s
                        ON CONFLICT (user_id) DO NOTHING;
                        """,
                        (full_name, email),
                    )

        logger.info("dev_seed | ensured demo users + profiles (password=%s)", DEV_SEED_PASSWORD)
    except Exception as exc:
        logger.warning("dev_seed | failed: %s", exc)


@app.on_event("startup")
async def _start_sla_heartbeat() -> None:
    global _sla_heartbeat_task, _has_sla_policy_fn

    # Retry db_compat and dev_seed until DB is reachable (handles startup race on first boot)
    for _boot_attempt in range(15):
        try:
            _ensure_runtime_schema_compatibility()
            break
        except Exception as _e:
            if _boot_attempt < 14:
                logger.info("db_compat | DB not ready yet (attempt %d/15), retrying in 2s...", _boot_attempt + 1)
                await asyncio.sleep(2)
            else:
                logger.warning("db_compat | gave up after 15 attempts: %s", _e)

    # permanent dev seed (works even with existing DB volume)
    for _seed_attempt in range(15):
        try:
            _ensure_dev_seed_users()
            break
        except Exception as _e:
            if _seed_attempt < 14:
                logger.info("dev_seed | DB not ready yet (attempt %d/15), retrying in 2s...", _seed_attempt + 1)
                await asyncio.sleep(2)
            else:
                logger.warning("dev_seed | gave up after 15 attempts: %s", _e)

    # ── One-time repair: fix any stale ISO week labels from pre-fix reports ────
    try:
        _repair_week_labels_once()
    except Exception as _e:
        logger.warning("week_label_repair | startup call failed: %s", _e)

    # ── Wire analytics service to DB helpers and warm-up refresh ─────────────
    if _ANALYTICS_READY:
        try:
            _analytics.init(fetch_one, fetch_all, db_connect)
            # Self-healing: install MVs if zzz_analytics_mvs.sh was skipped
            # Retry up to 10x (30s) in case DB is still finishing init.sql
            for _mv_attempt in range(10):
                try:
                    row = fetch_one(
                        "SELECT COUNT(*) AS cnt FROM pg_matviews WHERE matviewname = 'mv_ticket_base'", ()
                    )
                    if row and (row.get("cnt") or 0) > 0:
                        break  # MVs already exist
                    logger.info("_ensure_analytics_mvs | MVs missing — installing (attempt %d/10)...", _mv_attempt + 1)
                    _ensure_analytics_mvs()
                    break
                except Exception as _mv_err:
                    if _mv_attempt < 9:
                        await asyncio.sleep(3)
                    else:
                        logger.error("_ensure_analytics_mvs | gave up after 10 attempts: %s", _mv_err)
            _analytics.refresh_mvs()
            logger.info("analytics_service | MVs refreshed and ready")
        except Exception as _e:
            logger.warning("analytics_service | startup refresh failed — will still serve from MVs. err=%s", _e)

    # Retry detecting the SLA function — DB may still be running init.sql on first boot
    for _attempt in range(10):
        _has_sla_policy_fn = _detect_sla_policy_function()
        if _has_sla_policy_fn:
            break
        logger.info("sla_heartbeat | waiting for apply_ticket_sla_policies() (attempt %d/10)...", _attempt + 1)
        await asyncio.sleep(3)
    if not _has_sla_policy_fn:
        logger.warning("sla_heartbeat | disabled (apply_ticket_sla_policies() not found after retries)")
        return
    if SLA_HEARTBEAT_SECONDS <= 0:
        logger.info("sla_heartbeat | disabled (SLA_HEARTBEAT_SECONDS=%s)", SLA_HEARTBEAT_SECONDS)
        return
    if _sla_heartbeat_task is None or _sla_heartbeat_task.done():
        _sla_heartbeat_task = asyncio.create_task(_sla_heartbeat_loop())
        logger.info("sla_heartbeat | started interval_s=%s", SLA_HEARTBEAT_SECONDS)

    # Start background MV refresh loop
    global _analytics_refresh_task
    if _ANALYTICS_READY and ANALYTICS_REFRESH_INTERVAL_SECONDS > 0 and (
        _analytics_refresh_task is None or _analytics_refresh_task.done()
    ):
        _analytics_refresh_task = asyncio.create_task(_analytics_refresh_loop())
        logger.info(
            "analytics_refresh | background loop started (interval_s=%s)",
            ANALYTICS_REFRESH_INTERVAL_SECONDS,
        )


@app.on_event("shutdown")
async def _stop_sla_heartbeat() -> None:
    global _sla_heartbeat_task, _analytics_refresh_task
    if _sla_heartbeat_task and not _sla_heartbeat_task.done():
        _sla_heartbeat_task.cancel()
        try:
            await _sla_heartbeat_task
        except asyncio.CancelledError:
            pass
    _sla_heartbeat_task = None

    if _analytics_refresh_task and not _analytics_refresh_task.done():
        _analytics_refresh_task.cancel()
        try:
            await _analytics_refresh_task
        except asyncio.CancelledError:
            pass
    _analytics_refresh_task = None


# Auth dependencies
def _validate_token_and_fetch_user(token: str) -> Dict[str, Any]:
    """Validate a raw JWT string and return the user record."""
    payload = verify_jwt(token)
    jti = str(payload.get("jti") or "").strip()
    if jti and is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = fetch_one(
        """
        SELECT u.id, u.email, u.role, u.is_active, u.totp_secret, u.mfa_enabled,
               u.password_changed_at,
               up.full_name, up.department_id
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE u.id = %s
        """,
        (payload.get("sub"),),
    )
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    _check_token_issued_after_password_change(payload, user)
    return user


def _get_bearer_token(authorization: Optional[str]) -> str:
    """Extract and return the raw token from an Authorization: Bearer header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1].strip()


def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI dependency: resolves the current user from httpOnly cookie or Bearer header.
    Cookie is checked first (preferred — not accessible to JavaScript).
    Bearer header is accepted as fallback for backward compatibility.
    """
    token = request.cookies.get("access_token") if request else None
    if not token and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            token = parts[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _validate_token_and_fetch_user(token)


def _set_auth_cookie(response, token: str) -> None:
    """Set the access_token httpOnly cookie on a response object."""
    is_prod = os.getenv("ENVIRONMENT", "").lower() == "production"
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="strict" if is_prod else "lax",
        max_age=JWT_TTL_SECONDS,
        path="/",
    )


def _clear_auth_cookie(response) -> None:
    """Clear the access_token httpOnly cookie."""
    response.delete_cookie(key="access_token", path="/")


def require_employee(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def require_manager(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def require_customer(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user

def require_operator(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


api.include_router(ai_explainability_router, dependencies=[Depends(require_operator)])
api.include_router(
    pipeline_queue_router,
    prefix="/operator/pipeline-queue",
    dependencies=[Depends(require_operator)],
)

# Recurring complaint prediction
def predict_is_recurring(*, user_id: str, subject: str, details: str) -> bool:
    """
    Uses SQL function `compute_is_recurring_ticket(...)` when available.
    Falls back to False if the function is not installed or DB is unavailable.
    """
    if not user_id:
        return False
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT to_regprocedure('compute_is_recurring_ticket(uuid,text,text,integer)')
                           IS NOT NULL AS exists;
                    """
                )
                exists_row = cur.fetchone() or {}
                if not bool(exists_row.get("exists")):
                    return False

                cur.execute(
                    """
                    SELECT compute_is_recurring_ticket(%s::uuid, %s, %s) AS is_recurring;
                    """,
                    (user_id, subject or "", details or ""),
                )
                result = cur.fetchone() or {}
                return bool(result.get("is_recurring"))
    except Exception as exc:
        logger.warning("recurring_check | fallback_to_false err=%s", exc)
        return False


def _predict_department_from_details(details: str) -> tuple[str, float]:
    text = (details or "").lower()
    if any(k in text for k in ("wifi", "network", "internet", "server", "system", "software", "login")):
        return "IT", 0.86
    if any(k in text for k in ("leak", "pipe", "water", "ac", "air conditioning", "maintenance", "electrical", "power")):
        return "Maintenance", 0.86
    if any(k in text for k in ("fire", "unsafe", "hazard", "security", "alarm", "theft", "emergency")):
        return "Safety & Security", 0.88
    if any(k in text for k in ("contract", "legal", "policy", "compliance", "regulation", "law")):
        return "Legal & Compliance", 0.82
    if any(k in text for k in ("lease", "tenant", "rent", "handover", "move in")):
        return "Leasing", 0.82
    if any(k in text for k in ("hr", "salary", "leave", "employee", "staff")):
        return "HR", 0.82
    return "Facilities Management", 0.62


CHATBOT_URL = os.getenv("CHATBOT_URL", "http://chatbot:8000")
CHATBOT_URL_LOCAL = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004")
ORCHESTRATOR_URL_LOCAL = os.getenv("ORCHESTRATOR_URL_LOCAL", "http://innovacx-orchestrator:8004")

def _insert_notification(
    cur,
    user_id: str,
    notif_type: str,
    title: str,
    message: str,
    ticket_id: str,
    priority: Optional[str] = None,
) -> None:
    """
    Insert a single notification row inside an existing cursor/transaction.
    notif_type must match the notification_type enum:
      ticket_assignment | sla_warning | customer_reply |
      status_change | report_ready | system
    """
    cur.execute(
        """
        INSERT INTO notifications (user_id, type, title, message, priority, ticket_id)
        VALUES (%s, %s::notification_type, %s, %s, %s::ticket_priority, %s);
        """,
        (user_id, notif_type, title, message, priority, ticket_id),
    )


def _trigger_priority_relearning(ticket_id: str, approved_priority: str, retrain_now: bool = False) -> None:
    normalized_ticket_id = str(ticket_id).strip()
    # Relearning endpoint looks up orchestrator logs by pipeline ticket id
    # (typically the CX- ticket code). Approval flows often pass DB UUID.
    if normalized_ticket_id and not normalized_ticket_id.upper().startswith("CX-"):
        row = fetch_one(
            "SELECT ticket_code FROM tickets WHERE id::text = %s LIMIT 1;",
            (normalized_ticket_id,),
        ) or {}
        normalized_ticket_id = str(row.get("ticket_code") or normalized_ticket_id).strip()

    payload = {
        "ticket_id": normalized_ticket_id,
        "approved_priority": str(approved_priority).strip().lower(),
        "retrain_now": bool(retrain_now),
    }
    for base in [ORCHESTRATOR_URL, ORCHESTRATOR_URL_LOCAL]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{base}/priority/relearn/manager-approval",
                    json=payload,
                )
                resp.raise_for_status()
                logger.info(
                    "priority_relearn | triggered via %s ticket=%s label=%s",
                    base,
                    normalized_ticket_id,
                    approved_priority,
                )
                return
        except Exception:
            continue
    logger.warning(
        "priority_relearn | failed to trigger for ticket=%s label=%s",
        normalized_ticket_id,
        approved_priority,
    )


def _mock_department_from_text(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("wifi", "network", "internet", "server", "system", "software", "login")):
        return "IT"
    if any(k in t for k in ("leak", "pipe", "water", "ac", "air conditioning", "maintenance", "electrical", "power")):
        return "Maintenance"
    if any(k in t for k in ("fire", "unsafe", "hazard", "security", "alarm", "theft", "emergency")):
        return "Safety & Security"
    if any(k in t for k in ("contract", "legal", "policy", "compliance", "regulation", "law")):
        return "Legal & Compliance"
    if any(k in t for k in ("lease", "tenant", "rent", "handover", "move in")):
        return "Leasing"
    if any(k in t for k in ("hr", "salary", "leave", "employee", "staff")):
        return "HR"
    return "Facilities Management"


def _apply_mock_pipeline_outcome(ticket_code: str, details: str) -> None:
    """
    Local fallback when orchestrator dispatch is unavailable.
    Guarantees ticket has priority_assigned_at + SLA and a department.
    """
    dept_name = _mock_department_from_text(details)
    now_utc = datetime.now(timezone.utc)
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM departments WHERE LOWER(name)=LOWER(%s) LIMIT 1;",
                (dept_name,),
            )
            row = cur.fetchone()
            if row:
                dept_id = row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO departments (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                    RETURNING id;
                    """,
                    (dept_name,),
                )
                dept_id = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE tickets
                SET
                  priority = COALESCE(priority, 'Medium'),
                  model_priority = COALESCE(model_priority, 'Medium'),
                  status = CASE
                             WHEN status IN ('Resolved', 'Escalated') THEN status
                             ELSE 'Assigned'::ticket_status
                           END,
                  department_id = COALESCE(%s, department_id),
                  model_department_id = COALESCE(%s, model_department_id),
                  model_confidence = COALESCE(model_confidence, 0.35),
                  sentiment_score = COALESCE(sentiment_score, 0.0),
                  sentiment_label = COALESCE(sentiment_label, 'mock_orchestrator'),
                  priority_assigned_at = COALESCE(priority_assigned_at, %s),
                  updated_at = now()
                WHERE ticket_code = %s;
                """,
                (dept_id, dept_id, now_utc, ticket_code),
            )
            auto_assign_ticket_if_needed(
                cur,
                ticket_code=ticket_code,
                status="Assigned",
                department_id=dept_id,
                priority="Medium",
            )
# Helpers for response/resolution time
def minutes_to_label(total_minutes: Optional[int]) -> str:
    if not total_minutes or total_minutes <= 0:
        return ""
    if total_minutes < 60:
        return f"{total_minutes} Minutes" if total_minutes != 1 else "1 Minute"
    if total_minutes < 1440:
        hrs = round(total_minutes / 60)
        return f"{hrs} Hours" if hrs != 1 else "1 Hour"
    days = round(total_minutes / 1440)
    return f"{days} Days" if days != 1 else "1 Day"


def diff_minutes(later_dt, earlier_dt) -> Optional[int]:
    if not later_dt or not earlier_dt:
        return None
    return max(0, int((later_dt - earlier_dt).total_seconds() // 60))


# Models
class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyTOTPRequest(BaseModel):
    login_token: str
    otp_code: str
    trust_device: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# Routes: Health & Root
@api.get("/health")
def health():
    row = fetch_one("SELECT NOW() as db_time;")
    db_time = row["db_time"]
    return {"ok": True, "dbTime": db_time.isoformat()}


@api.get("/")
def api_root():
    return {"message": "InnovaCX API is running", "time": datetime.now(timezone.utc).isoformat()}


@api.get("/csrf-token", tags=["security"])
def get_csrf_token():
    """Issue a stateless HMAC-signed CSRF token for form submissions."""
    return {"csrf_token": generate_csrf_token()}


async def require_csrf(x_csrf_token: str = Header(None, alias="X-CSRF-Token")):
    """FastAPI dependency: validates X-CSRF-Token header on mutating form requests."""
    if not x_csrf_token or not verify_csrf_token(x_csrf_token):
        raise HTTPException(status_code=403, detail="Invalid or missing CSRF token.")


_INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

async def require_internal_key(x_internal_key: str = Header(None, alias="X-Internal-Key")):
    """FastAPI dependency: validates X-Internal-Key header on internal service endpoints."""
    if not _INTERNAL_API_KEY:
        raise HTTPException(status_code=503, detail="Internal API key not configured.")
    if not x_internal_key or not hmac.compare_digest(x_internal_key, _INTERNAL_API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing internal API key.")


# MFA / TOTP Setup & Verification
@api.get("/auth/totp-status")
def totp_status(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns whether MFA is enabled for the current user.
    """
    row = fetch_one(
        "SELECT mfa_enabled FROM users WHERE id = %s",
        (user["id"],),
    )
    needs_setup = not bool(row["mfa_enabled"]) if row else True
    return {"needsSetup": needs_setup}  # frontend expects needsSetup


@api.get("/auth/totp-setup")
def totp_setup(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns a QR code URL for the user to scan in their authenticator app.
    Only generates a new secret if the user does not have one.
    """
    # Generate secret if not exists
    if not user.get("totp_secret"):
        secret = pyotp.random_base32()  # 16-char base32 secret
        execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, user["id"]))
    else:
        secret = user["totp_secret"]

    # Build otpauth URI
    issuer = "InnovaCX"
    email = user["email"]
    otpauth_url = pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)

    # Generate QR code as base64 PNG
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(otpauth_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode()

    return {"qrCode": f"data:image/png;base64,{qr_base64}", "secret": secret}


@api.post("/auth/login")
@rate_limit_auth()
def login(request: Request, body: LoginRequest, _csrf: None = Depends(require_csrf)):
    """
    Login route returns a temporary token.
    If MFA is not yet enabled, frontend should show QR code.
    Trusted device token (X-Trust-Token header) bypasses MFA for 30 days.
    """
    email = sanitize_email(body.email)
    client_ip = request.client.host if request and request.client else None

    if is_account_locked(email):
        log_auth_event("login_blocked_locked", email=email, ip=client_ip)
        raise HTTPException(status_code=423, detail="Account temporarily locked. Please try again later.")

    user = fetch_one(
        "SELECT id, email, password_hash, role, is_active, totp_secret, mfa_enabled FROM users WHERE email = %s",
        (email,),
    )

    if not user or not user.get("is_active"):
        check_and_record_failed_login(email)
        log_auth_event("login_failed_unknown_email", email=email, ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user["password_hash"]):
        check_and_record_failed_login(email)
        log_auth_event("login_failed", user_id=str(user["id"]), email=email, ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    clear_failed_logins(email)
    execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))

    # ── Trusted-device bypass ─────────────────────────────────────────────────
    # If the client presents a valid, unexpired trusted-device token that belongs
    # to this user, skip MFA entirely and issue a full session token.
    raw_trust_token = (request.headers.get("X-Trust-Token") or "").strip()
    if raw_trust_token and len(raw_trust_token) >= 40:
        trust_hash = hashlib.sha256(raw_trust_token.encode()).hexdigest()
        trusted = fetch_one(
            """SELECT id FROM trusted_devices
               WHERE token_hash = %s
                 AND user_id    = %s
                 AND expires_at > NOW()""",
            (trust_hash, user["id"]),
        )
        if trusted:
            access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
            _profile = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
            log_auth_event("login_success", user_id=str(user["id"]), email=email, ip=client_ip, extra={"trusted_device": True})
            resp = JSONResponse(content={
                "access_token": access_token,
                "token_type": "bearer",
                "trusted_device_used": True,
                "user": {
                    "id": str(user["id"]),
                    "email": user["email"],
                    "role": user["role"],
                    "full_name": (_profile or {}).get("full_name") or user["email"],
                },
            })
            _set_auth_cookie(resp, access_token)
            return resp

    # Bypass TOTP when explicitly disabled (dev/demo only — set DISABLE_MFA=true in .env on VM)
    if DISABLE_MFA:
        access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
        profile = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
        log_auth_event("login_success", user_id=str(user["id"]), email=email, ip=client_ip, extra={"mfa_bypassed": True})
        resp = JSONResponse(content={
            "access_token": access_token,
            "token_type": "bearer",
            "requiresSetup": False,
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "role": user["role"],
                "full_name": (profile or {}).get("full_name") or user["email"],
            },
        })
        _set_auth_cookie(resp, access_token)
        return resp

    # Generate secret if missing
    if not user.get("totp_secret"):
        secret = pyotp.random_base32()
        execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, user["id"]))
        user["totp_secret"] = secret

    # Temporary token for MFA setup/verification. Kept separate from the full
    # dashboard session token so it can be longer than one OTP attempt but
    # still scoped to the verification flow.
    temp_token = create_jwt({"sub": str(user["id"]), "type": "mfa_temp"}, ttl_seconds=MFA_TEMP_TTL_SECONDS)

    # Flag to indicate MFA setup required
    requires_setup = not user.get("mfa_enabled", False)

    _profile = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
    log_auth_event("login_success", user_id=str(user["id"]), email=email, ip=client_ip, extra={"requires_setup": bool(requires_setup), "temporary_token": True})
    return {
        "access_token": temp_token,
        "token_type": "temporary",
        "requiresSetup": requires_setup,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
            "full_name": (_profile or {}).get("full_name") or user["email"],
        },
    }

@api.post("/auth/totp-setup-complete")
def totp_setup_complete(user: Dict[str, Any] = Depends(get_current_user), _csrf: None = Depends(require_csrf)):
    """
    Mark MFA as enabled after user has scanned QR and verified OTP.
    """
    # Update the database
    execute(
        "UPDATE users SET mfa_enabled = TRUE WHERE id = %s",
        (user["id"],)
    )
    return {"success": True}

@api.post("/auth/totp-verify")
@rate_limit_auth()
def totp_verify(request: Request, body: VerifyTOTPRequest, _csrf: None = Depends(require_csrf)):
    """
    Verifies the OTP code from user.
    If correct, marks MFA as enabled (first-time setup) and returns a full JWT.
    """
    payload = verify_jwt(body.login_token)
    client_ip = request.client.host if request and request.client else None
    user = fetch_one(
        "SELECT id, email, role, totp_secret, mfa_enabled FROM users WHERE id = %s",
        (payload.get("sub"),),
    )

    if not user or not user.get("totp_secret"):
        log_auth_event("totp_failed", email=None if not user else user.get("email"), ip=client_ip, extra={"reason": "not_configured"})
        raise HTTPException(status_code=400, detail="TOTP not configured")

    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(body.otp_code, valid_window=1):
        log_auth_event("totp_failed", user_id=str(user["id"]), email=user.get("email"), ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid OTP code")

    # Enable MFA if first-time verification
    if not user.get("mfa_enabled"):
        execute("UPDATE users SET mfa_enabled = TRUE WHERE id = %s", (user["id"],))
        log_auth_event("mfa_setup_complete", user_id=str(user["id"]), email=user.get("email"), ip=client_ip)

    # Issue real JWT valid for standard TTL
    access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
    _profile = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
    log_auth_event("totp_success", user_id=str(user["id"]), email=user.get("email"), ip=client_ip)

    # ── Trusted-device token (30 days) ────────────────────────────────────────
    trusted_device_token = None
    if body.trust_device:
        raw_td = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        td_hash = hashlib.sha256(raw_td.encode()).hexdigest()
        execute(
            """INSERT INTO trusted_devices (user_id, token_hash, expires_at, ip_address, user_agent)
               VALUES (%s, %s, NOW() + INTERVAL '30 days', %s, %s)""",
            (
                user["id"],
                td_hash,
                client_ip,
                (request.headers.get("User-Agent") or "")[:512],
            ),
        )
        trusted_device_token = raw_td

    payload_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
            "full_name": (_profile or {}).get("full_name") or user["email"],
        },
    }
    if trusted_device_token:
        payload_data["trusted_device_token"] = trusted_device_token

    resp = JSONResponse(content=payload_data)
    _set_auth_cookie(resp, access_token)
    return resp


# ── Email routing helper ──────────────────────────────────────────────────────

def _resolve_email_recipient(user_email: str, password_hash: str) -> str:
    """
    Determine where to send transactional emails for a given user.

    - Google-OAuth-only accounts (no password) with an @innovacx.net address
      send to the shared ops inbox, because Google Workspace accounts cannot
      receive external mail at the OAuth identity address directly.
    - All other accounts receive email at their own registered address.
    """
    is_oauth_only    = (password_hash or "") == "OAUTH_NO_PASSWORD"
    is_innovacx_domain = user_email.lower().endswith("@innovacx.net")
    if is_oauth_only and is_innovacx_domain:
        return "innovacx.reset@gmail.com"
    return user_email


# ── Email OTP (alternative 2FA) ───────────────────────────────────────────────

EMAIL_OTP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Your InnovaCX Verification Code</title>
<style>
  body{{margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Arial,sans-serif;}}
  .wrap{{max-width:520px;margin:40px auto;background:#13132a;border-radius:16px;overflow:hidden;border:1px solid rgba(139,92,246,.25);}}
  .hdr{{background:linear-gradient(135deg,#1e1040 0%,#2d1b69 50%,#1a0f35 100%);padding:36px 40px 28px;text-align:center;}}
  .logo{{font-size:22px;font-weight:700;color:#e9d5ff;letter-spacing:.5px;}}
  .logo span{{color:#a855f7;}}
  .body{{padding:32px 40px;}}
  h2{{margin:0 0 12px;font-size:20px;color:#f3e8ff;}}
  p{{margin:0 0 16px;font-size:15px;color:#c4b5fd;line-height:1.6;}}
  .code-box{{background:rgba(139,92,246,.12);border:1.5px solid rgba(139,92,246,.35);border-radius:12px;padding:20px;text-align:center;margin:20px 0;}}
  .code{{font-family:'Courier New',monospace;font-size:36px;font-weight:700;color:#e9d5ff;letter-spacing:8px;}}
  .expiry{{font-size:12px;color:#9ca3af;margin:8px 0 0;}}
  .footer{{padding:20px 40px 28px;text-align:center;border-top:1px solid rgba(139,92,246,.15);}}
  .fc{{font-size:12px;color:#6b7280;margin:4px 0;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><div class="logo">Innova<span>CX</span></div></div>
  <div class="body">
    <h2>Your verification code</h2>
    <p>Hi <strong style="color:#e9d5ff">{email}</strong>, use the code below to complete your login.</p>
    <div class="code-box">
      <div class="code">{otp_code}</div>
      <div class="expiry">Expires in 10 minutes &bull; Single use only</div>
    </div>
    <p>If you did not attempt to log in, please contact your administrator immediately.</p>
    <p style="font-size:13px;color:#9ca3af;">Do not share this code with anyone. InnovaCX staff will never ask for it.</p>
  </div>
  <div class="footer"><p class="fc">&copy; {year} InnovaCX. All rights reserved.</p></div>
</div>
</body>
</html>"""


class EmailOTPSendRequest(BaseModel):
    login_token: str


class EmailOTPVerifyRequest(BaseModel):
    login_token: str
    otp_code: str
    trust_device: bool = False


@api.post("/auth/email-otp-send")
@rate_limit_auth()
def email_otp_send(request: Request, body: EmailOTPSendRequest, _csrf: None = Depends(require_csrf)):
    """Send a 6-digit OTP to the user's registered email as an alternative to TOTP."""
    payload = verify_jwt(body.login_token)
    client_ip = request.client.host if request and request.client else None

    user = fetch_one(
        "SELECT id, email, password_hash FROM users WHERE id = %s AND is_active = TRUE",
        (payload.get("sub"),),
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Invalidate any prior unused codes for this user
    execute(
        "UPDATE email_otp_codes SET used_at = NOW() WHERE user_id = %s AND used_at IS NULL",
        (user["id"],),
    )

    # Generate a 6-digit code
    raw_otp  = str(secrets.randbelow(1_000_000)).zfill(6)
    otp_hash = hashlib.sha256(raw_otp.encode()).hexdigest()

    execute(
        """INSERT INTO email_otp_codes (user_id, otp_hash, expires_at)
           VALUES (%s, %s, NOW() + INTERVAL '10 minutes')""",
        (user["id"], otp_hash),
    )

    recipient = _resolve_email_recipient(user["email"], user.get("password_hash", ""))
    try:
        resend.Emails.send({
            "from": "no-reply@innovacx.net",
            "to": recipient,
            "subject": "Your InnovaCX verification code",
            "html": EMAIL_OTP_HTML.format(
                email=user["email"],
                otp_code=raw_otp,
                year=datetime.utcnow().year,
            ),
        })
    except Exception as exc:
        log_auth_event("email_otp_send_failed", user_id=str(user["id"]), email=user["email"], ip=client_ip, extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again.")

    log_auth_event("email_otp_sent", user_id=str(user["id"]), email=user["email"], ip=client_ip)
    return {"ok": True, "message": "Verification code sent to your email"}


@api.post("/auth/email-otp-verify")
@rate_limit_auth()
def email_otp_verify(request: Request, body: EmailOTPVerifyRequest, _csrf: None = Depends(require_csrf)):
    """Verify a 6-digit email OTP and issue a full session token."""
    payload = verify_jwt(body.login_token)
    client_ip = request.client.host if request and request.client else None

    if not body.otp_code or not _re.match(r"^\d{6}$", body.otp_code):
        raise HTTPException(status_code=400, detail="Invalid OTP format")

    user = fetch_one(
        "SELECT id, email, role, mfa_enabled FROM users WHERE id = %s AND is_active = TRUE",
        (payload.get("sub"),),
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid session")

    otp_hash = hashlib.sha256(body.otp_code.encode()).hexdigest()
    row = fetch_one(
        """SELECT id FROM email_otp_codes
           WHERE user_id = %s
             AND otp_hash = %s
             AND used_at IS NULL
             AND expires_at > NOW()""",
        (user["id"], otp_hash),
    )
    if not row:
        log_auth_event("email_otp_failed", user_id=str(user["id"]), email=user["email"], ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    # Mark code as used
    execute("UPDATE email_otp_codes SET used_at = NOW() WHERE id = %s", (row["id"],))

    # Issue full JWT
    access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
    _profile = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
    log_auth_event("email_otp_success", user_id=str(user["id"]), email=user["email"], ip=client_ip)

    # Trusted-device token (30 days)
    trusted_device_token = None
    if body.trust_device:
        raw_td  = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        td_hash = hashlib.sha256(raw_td.encode()).hexdigest()
        execute(
            """INSERT INTO trusted_devices (user_id, token_hash, expires_at, ip_address, user_agent)
               VALUES (%s, %s, NOW() + INTERVAL '30 days', %s, %s)""",
            (user["id"], td_hash, client_ip, (request.headers.get("User-Agent") or "")[:512]),
        )
        trusted_device_token = raw_td

    payload_data = {
        "access_token": access_token,
        "token_type":   "bearer",
        "user": {
            "id":        str(user["id"]),
            "email":     user["email"],
            "role":      user["role"],
            "full_name": (_profile or {}).get("full_name") or user["email"],
        },
    }
    if trusted_device_token:
        payload_data["trusted_device_token"] = trusted_device_token

    resp = JSONResponse(content=payload_data)
    _set_auth_cookie(resp, access_token)
    return resp


# Forgot Password and reset link api call
# Routes: Password Reset
RESET_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Reset Your InnovaCX Password</title>
<style>
  body{{margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Arial,sans-serif;}}
  .wrap{{max-width:520px;margin:40px auto;background:#13132a;border-radius:16px;overflow:hidden;border:1px solid rgba(139,92,246,.25);}}
  .hdr{{background:linear-gradient(135deg,#1e1040 0%,#2d1b69 50%,#1a0f35 100%);padding:36px 40px 28px;text-align:center;}}
  .logo{{font-size:22px;font-weight:700;color:#e9d5ff;letter-spacing:.5px;}}
  .logo span{{color:#a855f7;}}
  .body{{padding:32px 40px;}}
  h2{{margin:0 0 12px;font-size:20px;color:#f3e8ff;}}
  p{{margin:0 0 16px;font-size:15px;color:#c4b5fd;line-height:1.6;}}
  .btn-wrap{{text-align:center;margin:20px 0 24px;}}
  .btn{{display:inline-block;padding:14px 40px;background:linear-gradient(135deg,#6d28d9,#9333ea,#a855f7);color:#fff!important;text-decoration:none;border-radius:12px;font-size:15px;font-weight:700;box-shadow:0 4px 20px rgba(147,51,234,.45);}}
  .divider{{border:none;border-top:1px solid rgba(139,92,246,.15);margin:0 0 20px;}}
  .link-label{{font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:.12em;margin:0 0 8px;}}
  .link-box{{background:rgba(139,92,246,.08);border:1px solid rgba(139,92,246,.2);border-radius:10px;padding:10px 14px;margin:0 0 24px;}}
  .link-text{{font-family:'Courier New',monospace;font-size:12px;color:#a855f7;word-break:break-all;line-height:1.5;margin:0;}}
  .warning{{background:rgba(245,158,11,.06);border:1px solid rgba(245,158,11,.2);border-radius:10px;padding:14px 16px;}}
  .warning p{{margin:0;font-size:13px;color:rgba(251,191,36,.8);line-height:1.55;}}
  .warning strong{{color:#fbbf24;}}
  .footer{{padding:20px 40px 28px;text-align:center;border-top:1px solid rgba(139,92,246,.15);}}
  .fc{{font-size:12px;color:#6b7280;margin:4px 0;}}
  @media only screen and (max-width:600px){{
    .wrap{{border-radius:0;margin:0;}}
    .hdr,.body,.footer{{padding-left:24px;padding-right:24px;}}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><div class="logo">Innova<span>CX</span></div></div>
  <div class="body">
    <h2>Reset your password</h2>
    <p>Hi <strong style="color:#e9d5ff">{email}</strong>,</p>
    <p>We received a request to reset the password for your InnovaCX account.
       Click the button below to choose a new password.
       This link will expire in <strong style="color:#e9d5ff">30 minutes</strong>.</p>
    <div class="btn-wrap">
      <a href="{reset_link}" class="btn" target="_blank">Reset Password &rarr;</a>
    </div>
    <hr class="divider"/>
    <p class="link-label">Or copy this link</p>
    <div class="link-box"><p class="link-text">{reset_link}</p></div>
    <div class="warning">
      <p><strong>Didn't request this?</strong> Your password will not change unless you click the button above.
         If you're concerned about your account security, please contact support immediately.</p>
    </div>
    <p style="font-size:13px;color:#9ca3af;margin-top:20px;">This is an automated security email. Please do not reply.</p>
  </div>
  <div class="footer"><p class="fc">&copy; {year} InnovaCX. All rights reserved.</p></div>
</div>
</body>
</html>"""

PASSWORD_CHANGED_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Password Changed — InnovaCX</title>
<style>
  body{{margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Arial,sans-serif;}}
  .wrap{{max-width:520px;margin:40px auto;background:#13132a;border-radius:16px;overflow:hidden;border:1px solid rgba(139,92,246,.25);}}
  .hdr{{background:linear-gradient(135deg,#1e1040 0%,#2d1b69 50%,#1a0f35 100%);padding:36px 40px 28px;text-align:center;}}
  .logo{{font-size:22px;font-weight:700;color:#e9d5ff;letter-spacing:.5px;}}
  .logo span{{color:#a855f7;}}
  .body{{padding:32px 40px;}}
  h2{{margin:0 0 12px;font-size:20px;color:#f3e8ff;}}
  p{{margin:0 0 16px;font-size:15px;color:#c4b5fd;line-height:1.6;}}
  .alert{{background:rgba(139,92,246,.12);border:1px solid rgba(139,92,246,.3);border-radius:10px;padding:14px 16px;margin:20px 0;}}
  .alert p{{margin:0;font-size:14px;color:#ddd6fe;}}
  .footer{{padding:20px 40px 28px;text-align:center;border-top:1px solid rgba(139,92,246,.15);}}
  .fc{{font-size:12px;color:#6b7280;margin:4px 0;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <div class="logo">Innova<span>CX</span></div>
  </div>
  <div class="body">
    <h2>Your password has been changed</h2>
    <p>Hi <strong style="color:#e9d5ff">{email}</strong>,</p>
    <p>The password for your InnovaCX account was successfully updated on <strong style="color:#e9d5ff">{changed_at} UTC</strong>.</p>
    <div class="alert">
      <p>&#x26A0;&#xFE0F; If you did not make this change, your account may be compromised. Please contact your system administrator or operator immediately.</p>
    </div>
    <p style="font-size:13px;color:#9ca3af;">This is an automated security notification. Please do not reply to this email.</p>
  </div>
  <div class="footer">
    <p class="fc">&copy; {year} InnovaCX. All rights reserved.</p>
  </div>
</div>
</body>
</html>"""


@api.post("/auth/forgot-password")
@rate_limit_auth()
def forgot_password(request: Request, body: ForgotPasswordRequest, _csrf: None = Depends(require_csrf)):
    email = sanitize_email(body.email)
    client_ip = request.client.host if request and request.client else None
    user = fetch_one(
        "SELECT id, password_hash FROM users WHERE email = %s AND is_active = TRUE",
        (email,),
    )

    if user:
        raw_token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        # Invalidate all previous unused reset tokens for this user before issuing a new one.
        # This prevents token accumulation and limits the attack window.
        execute(
            """
            UPDATE password_reset_tokens
            SET used_at = NOW()
            WHERE user_id = %s AND used_at IS NULL
            """,
            (user["id"],),
        )
        execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, NOW() + interval '30 minutes')
            """,
            (user["id"], token_hash),
        )

        # FIX: Token is placed in the URL fragment (#) instead of a query parameter (?).
        # Fragments are never sent to the server, never appear in nginx/CDN/proxy access
        # logs, and are not stored in browser history on the server side. This prevents
        # a valid 30-minute account-takeover credential from leaking into log files.
        reset_link = f"https://innovacx.net/forgot-password#token={raw_token}"

        recipient = _resolve_email_recipient(email, user.get("password_hash", ""))
        resend.Emails.send({
            "from": "no-reply@innovacx.net",
            "to": recipient,
            "subject": "Reset your InnovaCX password",
            "html": RESET_EMAIL_HTML.format(
                email=email,
                reset_link=reset_link,
                year=datetime.utcnow().year,
            ),
        })

        # DEV_LOG_RESET_TOKENS defaults to false; set to true only in local dev envs.
        # Never enable in production — tokens grant full account takeover.
        if DEV_LOG_RESET_TOKENS:
            print(f"[DEV] Password reset token for {email}: {raw_token}")
            print(f"[DEV] Reset link: {reset_link}")
        log_auth_event("password_reset_requested", user_id=str(user["id"]), email=email, ip=client_ip)
    else:
        log_auth_event("password_reset_requested", email=email, ip=client_ip, extra={"user_exists": False})

    # Always return the same generic response regardless of whether the email exists.
    return {"ok": True, "message": "If an account exists for that email, reset instructions were sent."}


@api.post("/auth/reset-password")
@rate_limit_auth()  # FIX: added — prevents hammering a token even at low guess probability
def reset_password(request: Request, body: ResetPasswordRequest, _csrf: None = Depends(require_csrf)):
    # get_current_user removed — user is not logged in during a password reset
    raw_token = (body.token or "").strip()
    new_password = body.new_password or ""

    # FIX: tightened from < 10 to < 40. A real token is always 43 chars
    # (base64url of 32 random bytes, no padding). Anything shorter is
    # definitively malformed and not worth a DB round-trip.
    if len(raw_token) < 40:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    client_ip = request.client.host if request and request.client else None
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Join users to get email for password complexity validation
            cur.execute(
                """
                SELECT prt.id, prt.user_id, u.email
                FROM password_reset_tokens prt
                JOIN users u ON u.id = prt.user_id
                WHERE prt.token_hash = %s
                  AND prt.used_at IS NULL
                  AND prt.expires_at > NOW()
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Invalid or expired token")

            # Email comes from DB via token, not from a logged-in session
            validate_password_complexity(new_password, field_name="New password", email=row["email"])

            new_hash = hash_password(new_password)
            # Update password and stamp password_changed_at so existing JWTs issued
            # before this moment can be detected as stale on next verification.
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    password_changed_at = NOW()
                WHERE id = %s
                """,
                (new_hash, row["user_id"]),
            )
            # Mark token as used immediately — single-use enforcement.
            cur.execute(
                "UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s",
                (row["id"],),
            )

    log_auth_event("password_reset_complete", user_id=str(row["user_id"]), ip=client_ip)

    # Notify the user that their password was changed
    _pw_row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (row["user_id"],))
    _reset_recipient = _resolve_email_recipient(row["email"], (_pw_row or {}).get("password_hash", ""))
    try:
        resend.Emails.send({
            "from": "no-reply@innovacx.net",
            "to": _reset_recipient,
            "subject": "Your InnovaCX password has been changed",
            "html": PASSWORD_CHANGED_EMAIL_HTML.format(
                email=row["email"],
                changed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                year=datetime.utcnow().year,
            ),
        })
    except Exception:
        pass  # Never fail the reset just because the notification email failed

    return {"ok": True, "message": "Password updated successfully"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@api.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    validate_password_complexity(body.new_password, field_name="New password", email=user["email"])
    row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    if not row or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    execute(
        "UPDATE users SET password_hash = %s, password_changed_at = NOW() WHERE id = %s",
        (hash_password(body.new_password), user["id"]),
    )
    client_ip = request.client.host if request and request.client else None
    log_auth_event("password_changed", user_id=str(user["id"]), email=user.get("email"), ip=client_ip)

    # Notify the user that their password was changed
    # After the UPDATE, fetch the new hash to determine the correct recipient
    _new_hash_row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    _change_recipient = _resolve_email_recipient(
        user.get("email", ""),
        (_new_hash_row or {}).get("password_hash", ""),
    )
    try:
        resend.Emails.send({
            "from": "no-reply@innovacx.net",
            "to": _change_recipient,
            "subject": "Your InnovaCX password has been changed",
            "html": PASSWORD_CHANGED_EMAIL_HTML.format(
                email=user.get("email", ""),
                changed_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
                year=datetime.utcnow().year,
            ),
        })
    except Exception:
        pass  # Never fail the password change just because the notification email failed

    return {"ok": True}


# ── Operator: MFA Reset (email-confirmed) ────────────────────────────────────

MFA_RESET_EMAIL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Confirm MFA Reset — InnovaCX</title>
<style>
  body{{margin:0;padding:0;background:#0d0d1a;font-family:'Segoe UI',Arial,sans-serif;}}
  .wrap{{max-width:520px;margin:40px auto;background:#13132a;border-radius:16px;overflow:hidden;border:1px solid rgba(139,92,246,.25);}}
  .hdr{{background:linear-gradient(135deg,#1e1040 0%,#2d1b69 50%,#1a0f35 100%);padding:36px 40px 28px;text-align:center;}}
  .logo{{font-size:22px;font-weight:700;color:#e9d5ff;letter-spacing:.5px;}}
  .logo span{{color:#a855f7;}}
  .body{{padding:32px 40px;}}
  h2{{margin:0 0 12px;font-size:20px;color:#f3e8ff;}}
  p{{margin:0 0 16px;font-size:15px;color:#c4b5fd;line-height:1.6;}}
  .btn-wrap{{text-align:center;margin:24px 0;}}
  .btn{{display:inline-block;padding:14px 36px;background:linear-gradient(135deg,#6d28d9,#9333ea);color:#fff;text-decoration:none;border-radius:12px;font-size:15px;font-weight:700;box-shadow:0 6px 24px rgba(147,51,234,.4);}}
  .alert{{background:rgba(234,179,8,.07);border:1px solid rgba(234,179,8,.25);border-radius:10px;padding:14px 16px;margin:20px 0;}}
  .alert p{{margin:0;font-size:13px;color:#fde68a;}}
  .footer{{padding:20px 40px 28px;text-align:center;border-top:1px solid rgba(139,92,246,.15);}}
  .fc{{font-size:12px;color:#6b7280;margin:4px 0;}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><div class="logo">Innova<span>CX</span></div></div>
  <div class="body">
    <h2>Confirm MFA Reset</h2>
    <p>Hi <strong style="color:#e9d5ff">{email}</strong>,</p>
    <p>An administrator has requested to reset your two-factor authentication. Click the button below to confirm and proceed with re-enrollment.</p>
    <div class="btn-wrap">
      <a href="{confirm_link}" class="btn">Confirm MFA Reset</a>
    </div>
    <div class="alert">
      <p>&#x26A0;&#xFE0F; If you did not expect this, do not click the button above. Your MFA will remain unchanged unless you confirm.</p>
    </div>
    <p style="font-size:13px;color:#9ca3af;">This link expires in 15 minutes. After confirming, you will be prompted to set up a new authenticator on your next login.</p>
  </div>
  <div class="footer"><p class="fc">&copy; {year} InnovaCX. All rights reserved.</p></div>
</div>
</body>
</html>"""


@api.post("/operator/users/{user_id}/reset-mfa")
def operator_reset_mfa(
    user_id: str,
    request: Request,
    operator: Dict[str, Any] = Depends(require_operator),
    _csrf: None = Depends(require_csrf),
):
    """Operator requests MFA reset for a user — sends confirmation email to the user."""
    uid = user_id.strip()
    target = fetch_one(
        "SELECT id, email, full_name FROM users u LEFT JOIN user_profiles p ON p.user_id = u.id WHERE u.id = %s",
        (uid,),
    )
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Invalidate any existing unused MFA reset tokens for this user
    execute(
        "UPDATE mfa_reset_tokens SET used_at = NOW() WHERE user_id = %s AND used_at IS NULL",
        (target["id"],),
    )

    raw_token  = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    execute(
        """INSERT INTO mfa_reset_tokens (user_id, token_hash, expires_at)
           VALUES (%s, %s, NOW() + INTERVAL '15 minutes')""",
        (target["id"], token_hash),
    )

    confirm_link = f"https://innovacx.net/confirm-mfa-reset#token={raw_token}"
    try:
        resend.Emails.send({
            "from": "no-reply@innovacx.net",
            "to": "innovacx.reset@gmail.com",
            "subject": "Action required: Confirm your MFA reset — InnovaCX",
            "html": MFA_RESET_EMAIL_HTML.format(
                email=target["email"],
                confirm_link=confirm_link,
                year=datetime.utcnow().year,
            ),
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to send confirmation email.") from exc

    client_ip = request.client.host if request and request.client else None
    log_auth_event("mfa_reset_requested", user_id=str(target["id"]), email=target["email"], ip=client_ip, extra={"by_operator": str(operator["id"])})
    return {"ok": True, "message": "Confirmation email sent to the user."}


class ConfirmMfaResetRequest(BaseModel):
    token: str


@api.post("/auth/confirm-mfa-reset")
@rate_limit_auth()
def confirm_mfa_reset(request: Request, body: ConfirmMfaResetRequest, _csrf: None = Depends(require_csrf)):
    """User confirms MFA reset via token from email — clears totp_secret and mfa_enabled."""
    raw_token = (body.token or "").strip()
    if len(raw_token) < 40:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    row = fetch_one(
        """SELECT mrt.id, mrt.user_id, u.email
           FROM mfa_reset_tokens mrt
           JOIN users u ON u.id = mrt.user_id
           WHERE mrt.token_hash = %s
             AND mrt.used_at IS NULL
             AND mrt.expires_at > NOW()""",
        (token_hash,),
    )
    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Clear TOTP secret and disable MFA so QR setup re-appears on next login
    execute(
        "UPDATE users SET totp_secret = NULL, mfa_enabled = FALSE WHERE id = %s",
        (row["user_id"],),
    )
    execute(
        "UPDATE mfa_reset_tokens SET used_at = NOW() WHERE id = %s",
        (row["id"],),
    )

    client_ip = request.client.host if request and request.client else None
    log_auth_event("mfa_reset_confirmed", user_id=str(row["user_id"]), email=row["email"], ip=client_ip)
    return {"ok": True, "message": "MFA has been reset. You will be asked to set up a new authenticator on your next login."}


# ── OAuth Sign-Up / Sign-In (Google + Microsoft) ─────────────────────────────

GOOGLE_CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET", "")
MICROSOFT_CLIENT_ID   = os.getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")


class OAuthCallbackRequest(BaseModel):
    code: str
    redirect_uri: str


def _upsert_oauth_user(email: str, full_name: str, provider: str) -> dict:
    """Find or create a user from an OAuth login. Returns the user row."""
    email = sanitize_email(email)
    user = fetch_one("SELECT id, email, role, is_active FROM users WHERE email = %s", (email,))
    if user:
        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="Account is inactive. Please contact your administrator.")
        return user
    # Create new customer account (no password — OAuth only)
    import uuid as _uuid
    new_id = str(_uuid.uuid4())
    execute(
        """INSERT INTO users (id, email, password_hash, role, is_active, mfa_enabled)
           VALUES (%s, %s, %s, 'customer', TRUE, FALSE)""",
        (new_id, email, "OAUTH_NO_PASSWORD"),
    )
    execute(
        "INSERT INTO user_profiles (user_id, full_name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (new_id, full_name or email.split("@")[0]),
    )
    log_auth_event("oauth_signup", user_id=new_id, email=email, extra={"provider": provider})
    return fetch_one("SELECT id, email, role, is_active FROM users WHERE id = %s", (new_id,))


@api.post("/auth/oauth/google/callback")
@rate_limit_auth()
def oauth_google_callback(request: Request, body: OAuthCallbackRequest, _csrf: None = Depends(require_csrf)):
    """Exchange Google authorization code for a session token."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Google OAuth is not configured on this server.")

    client_ip = request.client.host if request and request.client else None

    # Exchange code for tokens
    try:
        token_res = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code":          body.code,
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri":  body.redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=10,
        )
        token_res.raise_for_status()
        token_data = token_res.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code with Google.") from exc

    # Decode id_token (we only need payload — not verifying signature here for brevity)
    id_token = token_data.get("id_token", "")
    try:
        parts   = id_token.split(".")
        padding = 4 - len(parts[1]) % 4
        decoded = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * padding))
        email   = decoded.get("email", "")
        name    = decoded.get("name", "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid identity token from Google.") from exc

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email address.")

    user    = _upsert_oauth_user(email, name, "google")
    profile = fetch_one(
        "SELECT full_name, totp_secret, mfa_enabled FROM user_profiles UP "
        "JOIN users U ON U.id = UP.user_id WHERE U.id = %s",
        (user["id"],),
    )
    # Fetch full user row so we can check / set totp_secret
    full_user = fetch_one(
        "SELECT id, email, role, totp_secret, mfa_enabled FROM users WHERE id = %s",
        (user["id"],),
    )
    # Generate TOTP secret if missing (required for MFA setup after first Google sign-in)
    if not full_user.get("totp_secret"):
        secret = pyotp.random_base32()
        execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, full_user["id"]))

    requires_setup = not full_user.get("mfa_enabled", False)

    # Issue a temporary token — frontend will route to /mfa-setup (first time) or /verify
    temp_token = create_jwt(
        {"sub": str(full_user["id"]), "type": "mfa_temp"},
        ttl_seconds=MFA_TEMP_TTL_SECONDS,
    )
    log_auth_event("oauth_login", user_id=str(full_user["id"]), email=email, ip=client_ip,
                   extra={"provider": "google", "requires_setup": bool(requires_setup), "temporary_token": True})

    full_name = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (full_user["id"],))
    return {
        "access_token":  temp_token,
        "token_type":    "temporary",
        "requiresSetup": requires_setup,
        "user": {
            "id":        str(full_user["id"]),
            "email":     full_user["email"],
            "role":      full_user["role"],
            "full_name": (full_name or {}).get("full_name") or name or email,
        },
    }


@api.post("/auth/oauth/microsoft/callback")
@rate_limit_auth()
def oauth_microsoft_callback(request: Request, body: OAuthCallbackRequest, _csrf: None = Depends(require_csrf)):
    """Exchange Microsoft authorization code for a session token."""
    if not MICROSOFT_CLIENT_ID or not MICROSOFT_CLIENT_SECRET:
        raise HTTPException(status_code=501, detail="Microsoft OAuth is not configured on this server.")

    client_ip = request.client.host if request and request.client else None

    # Exchange code for tokens
    try:
        token_res = httpx.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "code":          body.code,
                "client_id":     MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "redirect_uri":  body.redirect_uri,
                "grant_type":    "authorization_code",
                "scope":         "openid email profile User.Read",
            },
            timeout=10,
        )
        token_res.raise_for_status()
        token_data = token_res.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Failed to exchange authorization code with Microsoft.") from exc

    # Decode id_token payload
    id_token = token_data.get("id_token", "")
    try:
        parts   = id_token.split(".")
        padding = 4 - len(parts[1]) % 4
        decoded = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * padding))
        email   = decoded.get("email") or decoded.get("preferred_username", "")
        name    = decoded.get("name", "")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid identity token from Microsoft.") from exc

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Microsoft account has no valid email address.")

    user         = _upsert_oauth_user(email, name, "microsoft")
    access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
    profile      = fetch_one("SELECT full_name FROM user_profiles WHERE user_id = %s", (user["id"],))
    log_auth_event("oauth_login", user_id=str(user["id"]), email=email, ip=client_ip, extra={"provider": "microsoft"})

    resp = JSONResponse(content={
        "access_token": access_token,
        "token_type":   "bearer",
        "user": {
            "id":        str(user["id"]),
            "email":     user["email"],
            "role":      user["role"],
            "full_name": (profile or {}).get("full_name") or name or email,
        },
    })
    _set_auth_cookie(resp, access_token)
    return resp


@api.post("/auth/logout")
def auth_logout(
    authorization: Optional[str] = Header(default=None),
    request: Request = None,
    user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    # Token may be in the httpOnly cookie or Bearer header — try both.
    token = (request.cookies.get("access_token") if request else None) or None
    if not token and authorization:
        parts = authorization.split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            token = parts[1].strip()
    client_ip = request.client.host if request and request.client else None
    if token:
        try:
            payload = verify_jwt(token)
            logout_user(
                jti=str(payload.get("jti") or "") or None,
                token_exp=float(payload.get("exp")) if payload.get("exp") is not None else None,
                user_id=str(user["id"]),
                db_execute=execute,
                ip=client_ip,
            )
        except Exception:
            pass  # Token unreadable — still clear the cookie
    resp = JSONResponse(content={"ok": True})
    _clear_auth_cookie(resp)
    return resp

class ResetTokenEmailRequest(BaseModel):
    token: str

@api.post("/auth/reset-token-email")
@rate_limit_auth()
def reset_token_email(request: Request, body: ResetTokenEmailRequest, _csrf: None = Depends(require_csrf)):
    """
    Given a raw reset token, return the associated email address if the token
    is valid and unexpired. Used by the frontend to enable the "password too
    similar to email" client-side check on the reset form.

    This endpoint reveals nothing an attacker doesn't already have — the token
    itself is the credential. It does NOT mark the token as used. It is
    rate-limited identically to the other auth endpoints.
    """
    raw_token = (body.token or "").strip()

    # Same length guard as reset-password — reject garbage before DB round-trip
    if len(raw_token) < 40:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    row = fetch_one(
        """
        SELECT u.email
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token_hash = %s
          AND prt.used_at IS NULL
          AND prt.expires_at > NOW()
        """,
        (token_hash,),
    )

    if not row:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    return {"email": row["email"]}



# Employee Dashboard (EmployeeDashboard.jsx)
@api.get("/employee/dashboard")
def employee_dashboard(user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]

    profile = fetch_one(
        "SELECT full_name FROM user_profiles WHERE user_id = %s",
        (user_id,),
    )
    employee = {"name": (profile or {}).get("full_name") or user["email"]}

    kpi_row = fetch_one(
        """
        SELECT
          COUNT(*) FILTER (WHERE t.assigned_to_user_id = %s AND t.status <> 'Resolved') AS tickets_assigned,
          COUNT(*) FILTER (WHERE t.assigned_to_user_id = %s AND t.status IN ('Assigned','In Progress')) AS in_progress,
          COUNT(*) FILTER (
            WHERE (t.resolved_by_user_id = %s OR (t.resolved_by_user_id IS NULL AND t.assigned_to_user_id = %s))
              AND t.status = 'Resolved'
              AND t.resolved_at IS NOT NULL
              AND date_trunc('month', t.resolved_at) = date_trunc('month', now())
          ) AS resolved_this_month,
          COUNT(*) FILTER (WHERE t.assigned_to_user_id = %s AND t.status <> 'Resolved' AND t.priority = 'Critical') AS critical,
          COUNT(*) FILTER (WHERE t.assigned_to_user_id = %s AND t.status = 'Overdue') AS overdue,
          COUNT(*) FILTER (WHERE t.assigned_to_user_id = %s AND t.created_at::date = current_date) AS new_today
        FROM tickets t;
        """,
        (user_id, user_id, user_id, user_id, user_id, user_id, user_id),
    ) or {}

    kpis = {
        "ticketsAssigned": int(kpi_row.get("tickets_assigned") or 0),
        "inProgress": int(kpi_row.get("in_progress") or 0),
        "resolvedThisMonth": int(kpi_row.get("resolved_this_month") or 0),
        "critical": int(kpi_row.get("critical") or 0),
        "overdue": int(kpi_row.get("overdue") or 0),
        "newToday": int(kpi_row.get("new_today") or 0),
    }

    tickets = fetch_all(
        """
        SELECT
          t.ticket_code AS "ticketId",
          t.subject     AS "subject",
          t.priority    AS "priority",
          t.status      AS "status"
        FROM tickets t
        WHERE t.assigned_to_user_id = %s
          AND t.status <> 'Resolved'
        ORDER BY t.created_at DESC
        LIMIT 5;
        """,
        (user_id,),
    )

    reports = fetch_all(
        """
        SELECT
          er.month_label AS "label",
          (
            split_part(er.report_code, '-', 2) || '-' ||
            CASE split_part(er.report_code, '-', 1)
              WHEN 'jan' THEN '01' WHEN 'feb' THEN '02' WHEN 'mar' THEN '03'
              WHEN 'apr' THEN '04' WHEN 'may' THEN '05' WHEN 'jun' THEN '06'
              WHEN 'jul' THEN '07' WHEN 'aug' THEN '08' WHEN 'sep' THEN '09'
              WHEN 'oct' THEN '10' WHEN 'nov' THEN '11' WHEN 'dec' THEN '12'
              ELSE '01'
            END
          ) AS "month"
        FROM employee_reports er
        WHERE er.employee_user_id = %s
          AND er.report_code ~ '^[a-z]{3}-[0-9]{4}-[a-z0-9]+'
        ORDER BY
          split_part(er.report_code, '-', 2)::int DESC,
          CASE split_part(er.report_code, '-', 1)
            WHEN 'jan' THEN 1  WHEN 'feb' THEN 2  WHEN 'mar' THEN 3
            WHEN 'apr' THEN 4  WHEN 'may' THEN 5  WHEN 'jun' THEN 6
            WHEN 'jul' THEN 7  WHEN 'aug' THEN 8  WHEN 'sep' THEN 9
            WHEN 'oct' THEN 10 WHEN 'nov' THEN 11 WHEN 'dec' THEN 12
            ELSE 0
          END DESC
        LIMIT 6;
        """,
        (user_id,),
    )

    return {"employee": employee, "kpis": kpis, "tickets": tickets, "reports": reports}


# Employee View All Complaints (EmployeeViewAllComplaints.jsx)
# ONLY tickets assigned to this employee
@api.get("/employee/tickets")
def employee_tickets(user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]

    rows = fetch_all(
        """
        SELECT
          t.ticket_code,
          t.subject,
          t.priority,
          t.status,
          t.created_at,
          t.priority_assigned_at,
          t.assigned_at,
          t.respond_due_at,
          t.resolve_due_at,
          t.first_response_at,
          t.resolved_at
        FROM tickets t
        WHERE t.assigned_to_user_id = %s
        ORDER BY t.created_at DESC
        LIMIT 500;
        """,
        (user_id,),
    )

    tickets = []
    for r in rows:
        created_at = r.get("created_at")
        priority_assigned_at = r.get("priority_assigned_at")
        assigned_at = r.get("assigned_at")
        respond_due_at = r.get("respond_due_at")
        resolve_due_at = r.get("resolve_due_at")

        issue_date = created_at.date().isoformat() if created_at else ""

        resp_base = priority_assigned_at or assigned_at or created_at
        response_time = minutes_to_label(diff_minutes(respond_due_at, resp_base))
        resolution_time = minutes_to_label(diff_minutes(resolve_due_at, priority_assigned_at or created_at))

        tickets.append(
            {
                "ticketId": r.get("ticket_code"),
                "subject": r.get("subject"),
                "priority": r.get("priority"),
                "status": r.get("status"),
                "issueDate": issue_date,
                "minTimeToRespond": response_time,
                "minTimeToResolve": resolution_time,
            }
        )

    return {"tickets": tickets}


# SLA Summary
@api.get("/employee/sla")
def employee_sla(
    days: int = Query(default=30, ge=1, le=365),
    user: Dict[str, Any] = Depends(require_employee),
):
    user_id = user["id"]

    row = fetch_one(
        """
        SELECT
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE first_response_at IS NOT NULL) AS responded,
          COUNT(*) FILTER (WHERE first_response_at IS NOT NULL AND respond_due_at IS NOT NULL AND first_response_at <= respond_due_at) AS responded_on_time,
          COUNT(*) FILTER (WHERE resolved_at IS NOT NULL) AS resolved,
          COUNT(*) FILTER (WHERE resolved_at IS NOT NULL AND resolve_due_at IS NOT NULL AND resolved_at <= resolve_due_at) AS resolved_on_time,
          AVG(EXTRACT(EPOCH FROM (first_response_at - COALESCE(priority_assigned_at, assigned_at, created_at))) / 60.0)
            FILTER (WHERE first_response_at IS NOT NULL) AS avg_response_mins,
          AVG(EXTRACT(EPOCH FROM (resolved_at - COALESCE(priority_assigned_at, created_at))) / 60.0)
            FILTER (WHERE resolved_at IS NOT NULL) AS avg_resolution_mins
        FROM tickets
        WHERE assigned_to_user_id = %s
          AND created_at >= NOW() - (%s || ' days')::interval;
        """,
        (user_id, days),
    ) or {}

    total = int(row.get("total") or 0)
    responded = int(row.get("responded") or 0)
    responded_on_time = int(row.get("responded_on_time") or 0)
    resolved = int(row.get("resolved") or 0)
    resolved_on_time = int(row.get("resolved_on_time") or 0)

    def pct(a: int, b: int) -> float:
        return 0.0 if b <= 0 else round((a / b) * 100.0, 2)

    return {
        "windowDays": days,
        "totalAssigned": total,
        "response": {
            "responded": responded,
            "onTime": responded_on_time,
            "onTimePct": pct(responded_on_time, responded),
            "avgMinutes": round(float(row.get("avg_response_mins") or 0.0), 2),
        },
        "resolution": {
            "resolved": resolved,
            "onTime": resolved_on_time,
            "onTimePct": pct(resolved_on_time, resolved),
            "avgMinutes": round(float(row.get("avg_resolution_mins") or 0.0), 2),
        },
    }

# Employee Notifications (EmployeeNotifications.jsx)

@api.get("/employee/notifications")
def employee_notifications(
    limit: int = Query(default=200, ge=1, le=500),
    only_unread: bool = Query(default=False),
    user: Dict[str, Any] = Depends(require_employee),
):
    user_id = user["id"]

    rows = fetch_all(
        """
        SELECT
          n.id::text           AS "id",
          n.type::text         AS "type",
          n.title              AS "title",
          n.message            AS "message",
          n.priority::text     AS "priority",
          t.ticket_code        AS "ticketId",
          n.report_id          AS "reportId",
          n.read               AS "read",
          n.created_at         AS "timestamp"
        FROM notifications n
        LEFT JOIN tickets t ON t.id = n.ticket_id
        WHERE n.user_id = %s
          AND (%s = FALSE OR n.read = FALSE)
        ORDER BY n.created_at DESC
        LIMIT %s;
        """,
        (user_id, only_unread, limit),
    )

    unread_row = fetch_one(
        "SELECT COUNT(*)::int AS unread FROM notifications WHERE user_id = %s AND read = FALSE;",
        (user_id,),
    ) or {"unread": 0}

    # Make timestamp ISO for frontend formatting
    notifications = []
    for r in rows:
        ts = r.get("timestamp")
        notifications.append(
            {
                "id": r.get("id"),
                "type": r.get("type"),
                "title": r.get("title"),
                "message": r.get("message"),
                "priority": r.get("priority"),
                "ticketId": r.get("ticketId"),
                "reportId": r.get("reportId"),
                "read": bool(r.get("read")),
                "timestamp": ts.isoformat() if ts else None,
            }
        )

    return {"unreadCount": int(unread_row.get("unread") or 0), "notifications": notifications}


@api.post("/employee/notifications/{notification_id}/read")
def employee_notification_mark_read(
    notification_id: str,
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    user_id = user["id"]

    try:
        # Ensure it's a UUID-like string (basic guard)
        import uuid
        uuid.UUID(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification id")

    updated = execute(
        """
        UPDATE notifications
        SET read = TRUE
        WHERE id = %s::uuid AND user_id = %s;
        """,
        (notification_id, user_id),
    )

    if updated <= 0:
        # Either not found, or not owned by this user
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"ok": True}


@api.post("/employee/notifications/read-all")
def employee_notifications_mark_all_read(
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    user_id = user["id"]

    execute(
        """
        UPDATE notifications
        SET read = TRUE
        WHERE user_id = %s AND read = FALSE;
        """,
        (user_id,),
    )

    return {"ok": True}

class EmployeeResolveRequest(BaseModel):
    decision: str
    final_resolution: Optional[str] = None
    steps_taken: Optional[str] = None


@api.get("/employee/tickets/{ticket_code}/resolution-suggestion")
def employee_resolution_suggestion(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_employee),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    row = fetch_one(
        """
        SELECT
          t.id,
          t.ticket_code,
          t.ticket_type,
          t.subject,
          t.details,
          t.asset_type,
          t.priority,
          t.status,
          t.priority_assigned_at,
          t.suggested_resolution,
          d.name AS department_name
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.ticket_code = %s
          AND t.assigned_to_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to this employee")
    if not row.get("priority_assigned_at") or not row.get("department_name"):
        raise HTTPException(
            status_code=409,
            detail="Suggested resolution is available after priority and department are assigned",
        )

    suggestion = str(row.get("suggested_resolution") or "").strip()
    if not suggestion:
        raise HTTPException(
            status_code=404,
            detail="No suggested resolution available for this ticket yet",
        )

    return {"ticketId": row["ticket_code"], "suggestedResolution": suggestion}


def _extract_previous_resolutions(updates_rows: list) -> list:
    """Extract archived previous resolutions stored by Branch C at reopen time."""
    import json as _json
    result = []
    for u in updates_rows:
        if u.get("update_type") != "previous_resolution":
            continue
        try:
            data = _json.loads(u.get("message") or "{}")
            result.append({
                "resolution": str(data.get("resolution") or ""),
                "resolvedAt": data.get("resolved_at"),
            })
        except Exception:
            pass
    return result


@api.get("/employee/tickets/{ticket_code}")
def employee_ticket_details(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_employee),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]

    # Ticket must belong to this employee
    row = fetch_one(
        """
        SELECT
          t.id,
          t.ticket_code,
          t.subject,
          t.details,
          t.priority,
          t.status,
          t.created_at,
          t.priority_assigned_at,
          t.assigned_at,
          t.respond_due_at,
          t.resolve_due_at,
          t.first_response_at,
          t.resolved_at,
          t.suggested_resolution,
          t.model_suggestion,
          t.final_resolution,
          up.full_name AS submitter_name,
          up.phone     AS submitter_phone,
          up.location  AS submitter_location
        FROM tickets t
        JOIN users u ON u.id = t.created_by_user_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE t.ticket_code = %s
          AND t.assigned_to_user_id = %s
        """,
        (ticket_code, user_id),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Attachments
    atts = fetch_all(
        """
        SELECT
          file_name,
          COALESCE(file_url, '/uploads/' || file_name) AS file_url
        FROM ticket_attachments
        WHERE ticket_id = %s
        ORDER BY uploaded_at ASC
        """,
        (row["id"],),
    )

    # Steps taken
    steps = fetch_all(
        """
        SELECT
          tws.step_no AS step,
          COALESCE(tp.full_name, tu.email) AS technician,
          tws.occurred_at AS occurred_at,
          tws.notes AS notes
        FROM ticket_work_steps tws
        LEFT JOIN users tu ON tu.id = tws.technician_user_id
        LEFT JOIN user_profiles tp ON tp.user_id = tu.id
        WHERE tws.ticket_id = %s
        ORDER BY tws.step_no ASC
        """,
        (row["id"],),
    )

    created_at = row.get("created_at")
    priority_assigned_at = row.get("priority_assigned_at")
    assigned_at = row.get("assigned_at")
    respond_due_at = row.get("respond_due_at")
    resolve_due_at = row.get("resolve_due_at")

    issue_date = created_at.date().isoformat() if created_at else ""

    resp_base = priority_assigned_at or assigned_at or created_at
    # Summary shows SLA minimum windows, not elapsed averages.
    response_time = minutes_to_label(diff_minutes(respond_due_at, resp_base))
    resolution_time = minutes_to_label(diff_minutes(resolve_due_at, priority_assigned_at or created_at))

    # Ticket updates (for previous resolutions)
    updates_rows = fetch_all(
        """
        SELECT update_type, message
        FROM ticket_updates
        WHERE ticket_id = %s
        ORDER BY created_at ASC
        """,
        (row["id"],),
    )

    ticket = {
        "ticketId": row.get("ticket_code"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "issueDate": issue_date,
        "suggestedResolution": row.get("suggested_resolution") or "",
        "modelSuggestion": row.get("suggested_resolution") or row.get("model_suggestion"),
        "finalResolution": row.get("final_resolution") or "",
        "previousResolutions": _extract_previous_resolutions(updates_rows or []),
        "metrics": {
            "minTimeToRespond": response_time,
            "minTimeToResolve": resolution_time,
        },
        "submittedBy": {
            "name": row.get("submitter_name") or "Unknown",
            "contact": row.get("submitter_phone") or "",
            "location": row.get("submitter_location") or "",
        },
        "description": {
            "subject": row.get("subject"),
            "details": row.get("details"),
        },
        "attachments": [{"fileName": a["file_name"], "fileUrl": a["file_url"]} for a in atts] if atts else [],
        "stepsTaken": [
            {
                "step": s["step"],
                "technician": s["technician"],
                "time": (s["occurred_at"].isoformat() if s.get("occurred_at") else ""),
                "notes": s.get("notes") or "",
            }
            for s in steps
        ],
    }

    return {"ticket": ticket}




@api.post("/employee/tickets/{ticket_code}/resolve")
def employee_resolve_ticket(
    ticket_code: str,
    body: EmployeeResolveRequest,
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    decision = (body.decision or "").strip().lower()
    if decision not in {"accepted", "declined_custom"}:
        raise HTTPException(status_code=422, detail="decision must be 'accepted' or 'declined_custom'")

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  t.id,
                  t.ticket_code,
                  t.status,
                  t.suggested_resolution,
                  COALESCE(d.name, 'Unassigned') AS department_name
                FROM tickets
                LEFT JOIN departments d ON d.id = t.department_id
                WHERE t.ticket_code = %s
                  AND t.assigned_to_user_id = %s
                LIMIT 1;
                """,
                (ticket_code, user_id),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail="Ticket not found or not assigned to this employee")

            suggested_resolution = str(existing.get("suggested_resolution") or "").strip()
            if decision == "accepted":
                if not suggested_resolution:
                    raise HTTPException(status_code=409, detail="No suggested resolution available to accept")
                final_resolution = suggested_resolution
            else:
                final_resolution = (body.final_resolution or "").strip()
                if not final_resolution:
                    raise HTTPException(status_code=422, detail="final_resolution is required when declining suggestion")

            from_status = existing["status"]
            cur.execute(
                """
                UPDATE tickets
                SET
                  status = 'Resolved',
                  first_response_at = COALESCE(first_response_at, now()),
                  resolved_at = COALESCE(resolved_at, now()),
                  resolved_by_user_id = %s,
                  final_resolution = %s
                WHERE id = %s
                RETURNING id, ticket_code, status, resolved_at, final_resolution;
                """,
                (
                    user_id,
                    final_resolution,
                    existing["id"],
                ),
            )
            row = cur.fetchone()

            cur.execute(
                """
                INSERT INTO ticket_updates (
                  ticket_id,
                  author_user_id,
                  update_type,
                  message,
                  from_status,
                  to_status
                )
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    row["id"],
                    user_id,
                    "status_change",
                    "Ticket resolved by employee using AI suggestion."
                    if decision == "accepted"
                    else "Ticket resolved by employee with custom resolution.",
                    from_status,
                    row["status"],
                ),
            )

            cur.execute(
                """
                INSERT INTO suggested_resolution_usage (
                  ticket_id,
                  employee_user_id,
                  decision,
                  actor_role,
                  department,
                  suggested_text,
                  final_text,
                  used
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    row["id"],
                    user_id,
                    decision,
                    "employee",
                    str(existing.get("department_name") or "Unassigned").strip() or "Unassigned",
                    suggested_resolution or None,
                    final_resolution,
                    decision == "accepted",
                ),
            )

            if (body.steps_taken or "").strip():
                cur.execute(
                    """
                    INSERT INTO ticket_work_steps (ticket_id, step_no, technician_user_id, notes)
                    VALUES (
                      %s,
                      COALESCE((SELECT MAX(step_no) FROM ticket_work_steps WHERE ticket_id = %s), 0) + 1,
                      %s,
                      %s
                    );
                    """,
                    (row["id"], row["id"], user_id, body.steps_taken.strip()),
                )

            # Notifications on employee resolve
            # Fetch related user IDs and priority for notifications.
            cur.execute(
                """
                SELECT created_by_user_id, priority
                FROM tickets
                WHERE id = %s
                LIMIT 1;
                """,
                (existing["id"],),
            )
            # Notifications handled by DB triggers:
            #   trg_notify_on_ticket_resolved     → resolver + assigned employee + managers
            #   trg_notify_customer_status_change → customer

    logger.info(
        "ticket_status_update | ticket_id=%s status=%s resolved_at=%s",
        row["ticket_code"],
        row["status"],
        row["resolved_at"],
    )
    log_application_event(
        service="backend",
        event_key="ticket_status_update",
        ticket_id=existing["id"],
        ticket_code=row["ticket_code"],
        payload={
            "status": row["status"],
            "resolved_at": row["resolved_at"],
        },
    )
    return {
        "ok": True,
        "ticketId": row["ticket_code"],
        "status": row["status"],
        "decision": decision,
        "finalResolution": row.get("final_resolution"),
        "resolvedAt": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
    }


# Employee: Upload attachment for a ticket
@api.post("/employee/tickets/{ticket_code}/attachments")
async def employee_upload_attachment(
    ticket_code: str,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    """
    Stores an uploaded file under <UPLOADS_DIR>/<ticket_code>/<filename>
    and records it in ticket_attachments.
    """
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]

    row = fetch_one(
        "SELECT id FROM tickets WHERE ticket_code = %s AND assigned_to_user_id = %s LIMIT 1;",
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    ticket_id = row["id"]

    safe_name = _sanitize_filename(file.filename or "attachment")
    contents = await validate_upload_file(file)

    uploads_root = _ensure_uploads_root()
    upload_dir = os.path.join(uploads_root, ticket_code)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, safe_name)

    with open(file_path, "wb") as f_out:
        f_out.write(contents)

    file_url = f"/uploads/{ticket_code}/{safe_name}"

    execute(
        """
        INSERT INTO ticket_attachments (ticket_id, file_name, file_url, uploaded_by)
        VALUES (%s, %s, %s, %s);
        """,
        (ticket_id, safe_name, file_url, user_id),
    )

    logger.info("attachment_upload | ticket=%s file=%s saved=%s", ticket_code, safe_name, file_path)
    return {"ok": True, "fileName": safe_name, "fileUrl": file_url}


# Customer: Upload attachment for a ticket
@api.post("/customer/tickets/{ticket_code}/attachments")
async def customer_upload_attachment(
    ticket_code: str,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_customer),
    _csrf: None = Depends(require_csrf),
):
    """
    Stores an uploaded file under <UPLOADS_DIR>/<ticket_code>/<filename>
    and records it in ticket_attachments. Only the ticket's creator may upload.
    """
    user_id = user["id"]

    row = fetch_one(
        "SELECT id FROM tickets WHERE ticket_code = %s AND created_by = %s",
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_id = row["id"]

    safe_name = _sanitize_filename(file.filename or "attachment")
    contents = await validate_upload_file(file)

    uploads_root = _ensure_uploads_root()
    upload_dir = os.path.join(uploads_root, ticket_code)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, safe_name)
    with open(file_path, "wb") as fh:
        fh.write(contents)

    file_url = f"/uploads/{ticket_code}/{safe_name}"

    execute(
        """
        INSERT INTO ticket_attachments (ticket_id, file_name, file_url, uploaded_by)
        VALUES (%s, %s, %s, %s);
        """,
        (ticket_id, safe_name, file_url, user_id),
    )

    logger.info("customer_attachment_upload | ticket=%s file=%s", ticket_code, safe_name)
    return {"ok": True, "fileName": safe_name, "fileUrl": file_url}


# Employee Rescore + Reroute (ComplaintDetails.jsx)

class EmployeeRescoreRequest(BaseModel):
    new_priority: str
    reason: str


class EmployeeRerouteRequest(BaseModel):
    new_department: str
    reason: str

class ManagerRescoreRequest(BaseModel):
    new_priority: str
    reason: str

class ManagerResolveRequest(BaseModel):
    final_resolution: str
    steps_taken: Optional[str] = None


@api.post("/employee/tickets/{ticket_code}/rescore")
def employee_rescore_ticket(
    ticket_code: str,
    body: EmployeeRescoreRequest,
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    new_priority = (body.new_priority or "").strip()
    reason = (body.reason or "").strip()

    allowed = {"Low", "Medium", "High", "Critical"}
    if new_priority not in allowed:
        raise HTTPException(status_code=422, detail=f"Invalid priority. Must be one of: {', '.join(sorted(allowed))}")
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required")

    row = fetch_one(
        """
        SELECT t.id, t.ticket_code, t.priority AS current_priority
        FROM tickets t
        WHERE t.ticket_code = %s AND t.assigned_to_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    current_priority = row.get("current_priority") or "Unknown"
    request_code = f"REQ-{int(time.time() * 1000) % 10000000}"

    # Look up the manager of the ticket's department so the notification
    # trigger sends to exactly the right manager — not all managers.
    dept_manager_row = fetch_one(
        """
        SELECT u.id AS manager_id
        FROM tickets t
        JOIN user_profiles up ON up.department_id = t.department_id
        JOIN users u ON u.id = up.user_id
        WHERE t.id = %s
          AND u.role = 'manager'
          AND u.is_active = TRUE
        LIMIT 1;
        """,
        (row["id"],),
    ) or {}
    target_manager_id = dept_manager_row.get("manager_id") or None

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO approval_requests (
                  request_code, ticket_id, request_type,
                  current_value, requested_value,
                  request_reason, submitted_by_user_id,
                  requested_to_user_id,
                  submitted_at, status
                )
                VALUES (%s, %s, 'Rescoring', %s, %s, %s, %s, %s, now(), 'Pending')
                RETURNING request_code;
                """,
                (
                    request_code,
                    row["id"],
                    f"Priority: {current_priority}",
                    f"Priority: {new_priority}",
                    reason,
                    user_id,
                    target_manager_id,
                ),
            )
            result = cur.fetchone()
            # Notifications handled by DB triggers:
            #   trg_notify_manager_approval_request → correct dept manager only
            #     (requested_to_user_id is now set, so trigger routes to 1 manager)
            #   trg_notify_employee_approval_submit → submitting employee

    logger.info(
        "employee_rescore | ticket=%s from=%s to=%s request=%s by=%s",
        ticket_code, current_priority, new_priority, result["request_code"], user_id,
    )
    return {"ok": True, "requestCode": result["request_code"], "status": "Pending"}

@api.post("/employee/tickets/{ticket_code}/reroute")
def employee_reroute_ticket(
    ticket_code: str,
    body: EmployeeRerouteRequest,
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    new_dept_name = (body.new_department or "").strip()
    reason = (body.reason or "").strip()

    if not new_dept_name:
        raise HTTPException(status_code=422, detail="New department is required")
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required")

    row = fetch_one(
        """
        SELECT t.id, t.ticket_code, d.name AS current_dept
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.ticket_code = %s AND t.assigned_to_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    new_dept = fetch_one(
        "SELECT id, name FROM departments WHERE name = %s LIMIT 1;",
        (new_dept_name,),
    )
    if not new_dept:
        raise HTTPException(status_code=404, detail=f"Department '{new_dept_name}' not found")

    current_dept = row.get("current_dept") or "Unknown"
    request_code = f"REQ-{int(time.time() * 1000) % 10000000}"

    # Look up the manager of the ticket's current department so the notification
    # trigger sends to exactly the right manager — not all managers.
    dept_manager_row = fetch_one(
        """
        SELECT u.id AS manager_id
        FROM tickets t
        JOIN user_profiles up ON up.department_id = t.department_id
        JOIN users u ON u.id = up.user_id
        WHERE t.id = %s
          AND u.role = 'manager'
          AND u.is_active = TRUE
        LIMIT 1;
        """,
        (row["id"],),
    ) or {}
    target_manager_id = dept_manager_row.get("manager_id") or None

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO approval_requests (
                  request_code, ticket_id, request_type,
                  current_value, requested_value,
                  request_reason, submitted_by_user_id,
                  requested_to_user_id,
                  submitted_at, status
                )
                VALUES (%s, %s, 'Rerouting', %s, %s, %s, %s, %s, now(), 'Pending')
                RETURNING request_code;
                """,
                (
                    request_code,
                    row["id"],
                    f"Dept: {current_dept}",
                    f"Dept: {new_dept_name}",
                    reason,
                    user_id,
                    target_manager_id,
                ),
            )
            result = cur.fetchone()
            # Notifications handled by DB triggers:
            #   trg_notify_manager_approval_request → correct dept manager only
            #     (requested_to_user_id is now set, so trigger routes to 1 manager)
            #   trg_notify_employee_approval_submit → submitting employee

    logger.info(
        "employee_reroute | ticket=%s from=%s to=%s request=%s",
        ticket_code,
        current_dept,
        new_dept_name,
        result["request_code"],
    )
    return {"ok": True, "requestCode": result["request_code"], "status": "Pending"}


# Ticket Messages — employee ↔ customer conversation

class TicketMessageRequest(BaseModel):
    body: str

    @property
    def sanitized_body(self) -> str:
        v = (self.body or "").strip()
        if not v:
            raise HTTPException(status_code=422, detail="Message body cannot be empty.")
        if len(v) > 4000:
            raise HTTPException(status_code=422, detail="Message body exceeds maximum length of 4000 characters.")
        return v

@api.get("/employee/tickets/{ticket_code}/messages")
def employee_get_ticket_messages(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_employee),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    ticket = fetch_one(
        "SELECT id FROM tickets WHERE ticket_code = %s AND assigned_to_user_id = %s LIMIT 1;",
        (ticket_code, user_id),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")
    rows = fetch_all(
        """
        SELECT tm.id, tm.body, tm.sender_role, tm.created_at,
               COALESCE(up.full_name, u.email) AS sender_name
        FROM ticket_messages tm
        JOIN users u ON u.id = tm.sender_id
        LEFT JOIN user_profiles up ON up.user_id = tm.sender_id
        WHERE tm.ticket_id = %s
        ORDER BY tm.created_at ASC;
        """,
        (ticket["id"],),
    )
    return {"messages": [
        {
            "id": str(r["id"]),
            "body": r["body"],
            "senderRole": r["sender_role"],
            "senderName": r["sender_name"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in (rows or [])
    ]}


@api.post("/employee/tickets/{ticket_code}/messages")
def employee_post_ticket_message(
    ticket_code: str,
    body: TicketMessageRequest,
    user: Dict[str, Any] = Depends(require_employee),
    _csrf: None = Depends(require_csrf),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    text = body.sanitized_body

    ticket = fetch_one(
        """
        SELECT t.id, t.status, t.first_response_at, t.assigned_to_user_id,
               t.created_by_user_id
        FROM tickets t
        WHERE t.ticket_code = %s AND t.assigned_to_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    ticket_id = ticket["id"]
    is_first = ticket["first_response_at"] is None
    customer_user_id = ticket["created_by_user_id"]

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, body)
                VALUES (%s, %s, 'employee', %s)
                RETURNING id, body, sender_role, created_at;
                """,
                (ticket_id, user_id, text),
            )
            msg = cur.fetchone()

            if is_first:
                cur.execute(
                    """
                    UPDATE tickets
                    SET first_response_at = now(),
                        status = CASE WHEN status = 'Assigned' THEN 'In Progress' ELSE status END
                    WHERE id = %s;
                    """,
                    (ticket_id,),
                )
                cur.execute(
                    """
                    INSERT INTO ticket_updates (ticket_id, update_type, message, created_at)
                    VALUES (%s, 'status_change', 'Status updated to In Progress after first employee response', now());
                    """,
                    (ticket_id,),
                )

            if customer_user_id:
                _insert_notification(
                    cur,
                    user_id=str(customer_user_id),
                    notif_type="customer_reply",
                    title=f"New reply on your ticket {ticket_code}",
                    message=text[:200],
                    ticket_id=str(ticket_id),
                    priority=None,
                )

    logger.info(
        "employee_message_sent | ticket=%s employee=%s first_response=%s",
        ticket_code, user_id, is_first,
    )
    return {
        "ok": True,
        "message": {
            "id": str(msg["id"]),
            "body": msg["body"],
            "senderRole": msg["sender_role"],
            "createdAt": msg["created_at"].isoformat(),
        },
    }


@api.get("/customer/tickets/{ticket_code}/messages")
def customer_get_ticket_messages(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_customer),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    ticket = fetch_one(
        "SELECT id FROM tickets WHERE ticket_code = %s AND created_by_user_id = %s LIMIT 1;",
        (ticket_code, user_id),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    rows = fetch_all(
        """
        SELECT tm.id, tm.body, tm.sender_role, tm.created_at,
               COALESCE(up.full_name, u.email) AS sender_name
        FROM ticket_messages tm
        JOIN users u ON u.id = tm.sender_id
        LEFT JOIN user_profiles up ON up.user_id = tm.sender_id
        WHERE tm.ticket_id = %s
        ORDER BY tm.created_at ASC;
        """,
        (ticket["id"],),
    )
    return {"messages": [
        {
            "id": str(r["id"]),
            "body": r["body"],
            "senderRole": r["sender_role"],
            "senderName": r["sender_name"],
            "createdAt": r["created_at"].isoformat(),
        }
        for r in (rows or [])
    ]}


@api.post("/customer/tickets/{ticket_code}/messages")
def customer_post_ticket_message(
    ticket_code: str,
    body: TicketMessageRequest,
    user: Dict[str, Any] = Depends(require_customer),
    _csrf: None = Depends(require_csrf),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]
    text = body.sanitized_body

    ticket = fetch_one(
        """
        SELECT t.id, t.status, t.assigned_to_user_id
        FROM tickets t
        WHERE t.ticket_code = %s AND t.created_by_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["status"] == "Resolved":
        raise HTTPException(status_code=400, detail="Cannot reply to a resolved ticket")

    ticket_id = ticket["id"]
    assigned_to = ticket["assigned_to_user_id"]

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO ticket_messages (ticket_id, sender_id, sender_role, body)
                VALUES (%s, %s, 'customer', %s)
                RETURNING id, body, sender_role, created_at;
                """,
                (ticket_id, user_id, text),
            )
            msg = cur.fetchone()

            if assigned_to:
                _insert_notification(
                    cur,
                    user_id=str(assigned_to),
                    notif_type="customer_reply",
                    title=f"Customer replied on {ticket_code}",
                    message=text[:200],
                    ticket_id=str(ticket_id),
                    priority=None,
                )

    return {
        "ok": True,
        "message": {
            "id": str(msg["id"]),
            "body": msg["body"],
            "senderRole": msg["sender_role"],
            "createdAt": msg["created_at"].isoformat(),
        },
    }


# Employee Report Helpers

_MONTH_LABEL = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

_MONTH_ABBR = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr",
    5: "may", 6: "jun", 7: "jul", 8: "aug",
    9: "sep", 10: "oct", 11: "nov", 12: "dec",
}


def _safe_report_code(code: str) -> str:
    """Sanitise a report_code path param - allow only [a-z0-9-]."""
    import re
    sanitised = re.sub(r"[^a-z0-9\-]", "", code.lower())
    if not sanitised:
        raise HTTPException(status_code=400, detail="Invalid report code.")
    return sanitised


def _generate_employee_report(user_id: str, year: int, month: int) -> Optional[str]:
    """
    Build (or rebuild) the employee_report row for the given user/year/month.

    All analytics come exclusively from materialized views:
      - mv_employee_daily  → KPIs, weekly breakdown, rating components, notes
      - mv_acceptance_daily → AI Acceptance Rate (summary item)

    Returns the report_code on success, or None if the employee had no activity.
    Works for any employee — no hardcoded IDs or names.
    """
    from datetime import date

    period_start = date(year, month, 1)
    period_end   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    # activity check via MV
    activity = fetch_one(
        """
        SELECT SUM(total) AS cnt
        FROM mv_employee_daily
        WHERE employee_id = %s::uuid
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    )
    if not activity or (activity.get("cnt") or 0) == 0:
        return None

    # build user slug for report_code (safe, lowercase, alphanum only)
    user_slug_row = fetch_one(
        "SELECT split_part(email, '@', 1) AS slug FROM users WHERE id = %s::uuid",
        (user_id,),
    ) or {}
    import re as _re_slug
    raw_slug = str(user_slug_row.get("slug") or "").strip().lower()
    user_slug = _re_slug.sub(r"[^a-z0-9]", "", raw_slug)[:12]
    if not user_slug:
        user_slug = _re_slug.sub(r"[^a-z0-9]", "", str(user_id).replace("-", ""))[:8]

    # report_code: mon-year-slug  (e.g. mar-2026-ahmed)
    report_code = f"{_MONTH_ABBR[month]}-{year}-{user_slug}"
    month_label = f"{_MONTH_LABEL[month]} {year}"

    # aggregate monthly KPIs from mv_employee_daily
    kpi_row = fetch_one(
        """
        SELECT
            SUM(total)                                                      AS total,
            SUM(resolved)                                                   AS resolved,
            SUM(breached)                                                   AS breached,
            SUM(escalated)                                                  AS escalated,
            ROUND(
                SUM(total - breached)::numeric / NULLIF(SUM(total), 0) * 100, 1
            )                                                               AS sla_pct,
            ROUND(
                SUM(avg_respond_mins * total) / NULLIF(SUM(total), 0), 1
            )                                                               AS avg_response_mins
        FROM mv_employee_daily
        WHERE employee_id = %s::uuid
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    ) or {}

    total     = int(kpi_row.get("total")     or 0)
    resolved  = int(kpi_row.get("resolved")  or 0)
    breached  = int(kpi_row.get("breached")  or 0)
    escalated = int(kpi_row.get("escalated") or 0)
    sla_pct   = float(kpi_row.get("sla_pct") or 0)
    avg_resp  = kpi_row.get("avg_response_mins")
    avg_resp_f = float(avg_resp) if avg_resp is not None else None

    resolve_rate = round(resolved / total * 100, 1) if total else 0.0
    escalation_rate = round(escalated / total * 100, 1) if total else 0.0

    # Overall rating: weighted composite (50% closure rate + 50% SLA compliance)
    kpi_rating_num = round((resolve_rate * 0.5) + (sla_pct * 0.5), 1)
    # Format for display
    if kpi_rating_num >= 90:
        kpi_rating_label = f"{kpi_rating_num}% · Excellent"
    elif kpi_rating_num >= 75:
        kpi_rating_label = f"{kpi_rating_num}% · Good"
    elif kpi_rating_num >= 50:
        kpi_rating_label = f"{kpi_rating_num}% · Needs Improvement"
    else:
        kpi_rating_label = f"{kpi_rating_num}% · Poor"

    # KPI display strings
    kpi_sla_str = f"{sla_pct}%"
    kpi_avg_response_str = (
        f"{round(avg_resp_f)} min" if avg_resp_f is not None else "N/A"
    )

    subtitle = f"{resolved} of {total} tickets resolved · {sla_pct}% SLA compliance"

    # upsert employee_reports row
    existing = fetch_one(
        "SELECT id FROM employee_reports WHERE report_code = %s AND employee_user_id = %s::uuid",
        (report_code, user_id),
    )
    if existing:
        execute(
            """
            UPDATE employee_reports SET
                month_label       = %s,
                subtitle          = %s,
                kpi_rating        = %s,
                kpi_resolved      = %s,
                kpi_sla           = %s,
                kpi_avg_response  = %s,
                created_at        = NOW()
            WHERE id = %s
            """,
            (
                month_label, subtitle,
                kpi_rating_label, resolved, kpi_sla_str, kpi_avg_response_str,
                existing["id"],
            ),
        )
        report_id = existing["id"]
    else:
        row = fetch_one(
            """
            INSERT INTO employee_reports
                (employee_user_id, report_code, month_label, subtitle,
                 kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response)
            VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                user_id, report_code, month_label, subtitle,
                kpi_rating_label, resolved, kpi_sla_str, kpi_avg_response_str,
            ),
        )
        if not row:
            return None
        report_id = row["id"]

    # summary items
    # AI Acceptance Rate comes from mv_acceptance_daily
    acceptance_data = fetch_one(
        """
        SELECT
            SUM(total)    AS total_resolutions,
            SUM(accepted) AS accepted_count
        FROM mv_acceptance_daily
        WHERE employee_id = %s::uuid
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    ) or {}

    acceptance_total = int(acceptance_data.get("total_resolutions") or 0)
    acceptance_count = int(acceptance_data.get("accepted_count")    or 0)
    acceptance_rate  = (
        round(acceptance_count / acceptance_total * 100, 1)
        if acceptance_total > 0 else None
    )

    execute("DELETE FROM employee_report_summary_items WHERE report_id = %s", (report_id,))
    summary_items = [
        ("Tickets Assigned",   str(total)),
        ("Tickets Resolved",   str(resolved)),
        ("SLA Compliance",     kpi_sla_str),
        ("Avg First Response", kpi_avg_response_str),
        ("AI Acceptance Rate", f"{acceptance_rate}%" if acceptance_rate is not None else "N/A"),
        ("Escalated",          str(escalated)),
    ]
    for label, value in summary_items:
        execute(
            "INSERT INTO employee_report_summary_items (report_id, label, value_text) VALUES (%s, %s, %s)",
            (report_id, label, value),
        )

    # rating components
    # Each component is derived from MV aggregates; pct is its contribution (0-100)
    # score is the raw metric value (0-100 scale) for the progress bar.
    #
    # Components:
    #   1. Closure Rate        — resolved / total * 100
    #   2. SLA Compliance      — sla_pct (already 0-100)
    #   3. Response Speed      — score = max(0, 100 - (avg_response / 480 * 100))
    #                            (perfect=0min→100, 8h=0; capped 0-100)
    #   4. No Escalations      — score = max(0, 100 - escalation_rate)

    response_speed_score = (
        round(max(0.0, 100.0 - (avg_resp_f / 480.0 * 100.0)), 1)
        if avg_resp_f is not None else 0.0
    )
    no_escalation_score = round(max(0.0, 100.0 - escalation_rate), 1)

    rating_components_data = [
        ("Closure Rate",    resolve_rate,          resolve_rate),
        ("SLA Compliance",  sla_pct,               sla_pct),
        ("Response Speed",  response_speed_score,  response_speed_score),
        ("No Escalations",  no_escalation_score,   no_escalation_score),
    ]

    execute("DELETE FROM employee_report_rating_components WHERE report_id = %s", (report_id,))
    for rc_name, rc_score, rc_pct in rating_components_data:
        execute(
            """
            INSERT INTO employee_report_rating_components (report_id, name, score, pct)
            VALUES (%s, %s, %s, %s)
            """,
            (report_id, rc_name, round(rc_score, 1), round(rc_pct, 1)),
        )

    # weekly rows
    # Derive week-of-month from created_day; group mv_employee_daily by ISO week.
    # We use date_trunc('week', created_day) to get the Monday of each ISO week,
    # then label it as "Week N" relative to the start of the month.
    #
    # IMPORTANT — label clamping:
    # date_trunc('week', ...) in PostgreSQL always returns the Monday of the ISO
    # week, which can fall in the *previous* month when the 1st of the month is
    # not a Monday.  Example: April 1 2026 is a Wednesday → its ISO week Monday
    # is March 30.  We clamp the display date to period_start so that the first
    # week of April is always labelled with an April (or later) date.
    weekly_rows = fetch_all(
        """
        SELECT
            date_trunc('week', created_day)::date               AS week_monday,
            SUM(total)                                           AS assigned,
            SUM(resolved)                                        AS resolved,
            ROUND(
                SUM(total - breached)::numeric / NULLIF(SUM(total), 0) * 100, 1
            )                                                    AS sla_pct,
            ROUND(
                SUM(avg_respond_mins * total) / NULLIF(SUM(total), 0), 1
            )                                                    AS avg_respond_mins
        FROM mv_employee_daily
        WHERE employee_id = %s::uuid
          AND created_day >= %s AND created_day < %s
        GROUP BY date_trunc('week', created_day)::date
        ORDER BY week_monday
        """,
        (user_id, period_start, period_end),
    )

    execute("DELETE FROM employee_report_weekly WHERE report_id = %s", (report_id,))
    prev_resolved = None
    for week_num, wr in enumerate(weekly_rows, start=1):
        w_assigned = int(wr.get("assigned") or 0)
        w_resolved = int(wr.get("resolved") or 0)
        w_sla      = float(wr.get("sla_pct") or 0)
        w_avg      = wr.get("avg_respond_mins")
        w_avg_str  = f"{round(float(w_avg))} min" if w_avg is not None else "N/A"
        w_sla_str  = f"{w_sla}%"

        # Delta vs previous week (based on resolved count)
        if prev_resolved is None:
            delta_type = "neutral"
            delta_text = "—"
        elif w_resolved > prev_resolved:
            delta_type = "positive"
            delta_text = f"+{w_resolved - prev_resolved} resolved"
        elif w_resolved < prev_resolved:
            delta_type = "neutral"
            delta_text = f"{w_resolved - prev_resolved} resolved"
        else:
            delta_type = "neutral"
            delta_text = "No change"

        prev_resolved = w_resolved

        # Build the week label (e.g. "Week 1 (Apr 1)").
        # Clamp week_monday to period_start: date_trunc('week', ...) returns the
        # ISO Monday, which can precede the month boundary (e.g. Mar 30 for an
        # April report whose first ticket falls in ISO-week starting Mar 30).
        # Displaying that Monday is misleading — show the first day of the month
        # instead whenever week_monday falls before period_start.
        week_monday_obj = wr.get("week_monday")
        if week_monday_obj:
            # Normalise to datetime.date — psycopg2 may return datetime.datetime
            # or datetime.date depending on column type; explicit cast avoids a
            # silent TypeError when comparing with period_start (always date).
            import datetime as _dt
            if isinstance(week_monday_obj, _dt.datetime):
                wm_date = week_monday_obj.date()
            else:
                wm_date = week_monday_obj
            # Clamp: if the ISO Monday falls before this month's first day, use
            # period_start as the label anchor instead.
            label_date = wm_date if wm_date >= period_start else period_start
            week_label = f"Week {week_num} ({label_date.strftime('%b %-d')})"
        else:
            week_label = f"Week {week_num}"

        execute(
            """
            INSERT INTO employee_report_weekly
                (report_id, week_label, assigned, resolved, sla, avg_response, delta_type, delta_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                report_id, week_label,
                w_assigned, w_resolved, w_sla_str, w_avg_str,
                delta_type, delta_text,
            ),
        )

    # notes
    # Auto-generated from real MV data — no hardcoded copy.
    notes = []

    if total > 0:
        notes.append(
            f"You handled {total} ticket{'s' if total != 1 else ''} in {month_label}, "
            f"resolving {resolved} ({resolve_rate}% closure rate)."
        )

    if sla_pct >= 90:
        notes.append(
            f"Excellent SLA performance: {sla_pct}% of tickets were handled within agreed timeframes."
        )
    elif sla_pct >= 70:
        notes.append(
            f"Good SLA performance at {sla_pct}%. "
            f"{breached} ticket{'s' if breached != 1 else ''} breached SLA targets this month."
        )
    elif total > 0:
        notes.append(
            f"SLA compliance was {sla_pct}% — "
            f"{breached} ticket{'s' if breached != 1 else ''} breached SLA targets. "
            f"Focus on earlier first responses to improve this score."
        )

    if avg_resp_f is not None:
        if avg_resp_f <= 30:
            notes.append(
                f"Outstanding response speed: average first response was {round(avg_resp_f)} min."
            )
        elif avg_resp_f <= 120:
            notes.append(
                f"Average first response time was {round(avg_resp_f)} min, within a healthy range."
            )
        else:
            notes.append(
                f"Average first response time was {round(avg_resp_f)} min. "
                f"Reducing this will directly improve your overall rating."
            )

    if escalated > 0:
        notes.append(
            f"{escalated} ticket{'s were' if escalated != 1 else ' was'} escalated this month "
            f"({escalation_rate}% escalation rate)."
        )
    elif total > 0:
        notes.append("No tickets were escalated this month — great work on self-resolution.")

    if acceptance_rate is not None:
        if acceptance_rate >= 70:
            notes.append(
                f"AI-suggested resolutions were accepted {acceptance_rate}% of the time, "
                f"reflecting strong alignment with AI recommendations."
            )
        else:
            notes.append(
                f"AI-suggested resolutions were accepted {acceptance_rate}% of the time. "
                f"Consider reviewing AI suggestions before customising."
            )

    execute("DELETE FROM employee_report_notes WHERE report_id = %s", (report_id,))
    for note_text in notes:
        execute(
            "INSERT INTO employee_report_notes (report_id, note) VALUES (%s, %s)",
            (report_id, note_text),
        )

    logger.info("report_gen | generated report=%s user=%s (MV-based, full)", report_code, user_id)
    return report_code


# ── One-time repair: fix stale ISO week labels ────────────────────────────────
def _repair_week_labels_once() -> None:
    """One-time startup repair for reports generated before the ISO week label
    clamping fix.  Detects any employee_report_weekly row whose week_label
    contains a date from a *different* month than the report's own month, then
    force-regenerates that report using the fixed _generate_employee_report().

    Idempotent — once all labels are correct the query returns zero rows and
    this function exits immediately with no DB writes.  Safe to call on every
    startup; after the first run it becomes a no-op in under 1ms.
    """
    try:
        stale = fetch_all(
            """
            SELECT DISTINCT er.report_code,
                            er.employee_user_id,
                            EXTRACT(YEAR  FROM er.period_start)::int AS yr,
                            EXTRACT(MONTH FROM er.period_start)::int AS mo
            FROM employee_report_weekly ew
            JOIN employee_reports er ON er.id = ew.report_id
            WHERE ew.week_label ~ '\\(([A-Za-z]+ \\d+)\\)'
              AND to_date(
                    substring(ew.week_label FROM '\\(([A-Za-z]+ \\d+)\\)') || ' ' ||
                    EXTRACT(YEAR FROM er.period_start)::text,
                    'Mon DD YYYY'
                  ) < er.period_start
            """,
            (),
        )
        if not stale:
            logger.info("week_label_repair | all week labels are correct — nothing to fix")
            return
        logger.info("week_label_repair | found %d report(s) with stale week labels — repairing", len(stale))
        for row in stale:
            try:
                code = _generate_employee_report(
                    str(row["employee_user_id"]), int(row["yr"]), int(row["mo"])
                )
                logger.info("week_label_repair | repaired %s", code)
            except Exception as _e:
                logger.warning("week_label_repair | failed for %s: %s", row["report_code"], _e)
        logger.info("week_label_repair | repair complete")
    except Exception as exc:
        logger.warning("week_label_repair | skipped due to error: %s", exc)


# ── Report coverage guarantee (real MV data only) ────────────────────────────
def _ensure_recent_reports(user_id: str) -> None:
    """Ensure the employee has a FULLY POPULATED report for every month where
    they have real MV data in mv_employee_daily.

    No hardcoded months. No demo floor. Reports come from real data only.

    Two-pass logic per month:
      Pass 1 — generate missing reports (report row does not exist at all).
      Pass 2 — repair incomplete reports (row exists, rc_count = 0 → old generator).

    Safe to call repeatedly — generation is idempotent (upsert + DELETE + INSERT).
    """
    import re as _re_slug2

    # Build slug once for this user
    user_slug_row = fetch_one(
        "SELECT split_part(email, '@', 1) AS slug FROM users WHERE id = %s::uuid",
        (user_id,),
    ) or {}
    raw_slug = str(user_slug_row.get("slug") or "").strip().lower()
    user_slug = _re_slug2.sub(r"[^a-z0-9]", "", raw_slug)[:12]
    if not user_slug:
        user_slug = _re_slug2.sub(r"[^a-z0-9]", "", str(user_id).replace("-", ""))[:8]

    # ── Discover target months from real MV data for this employee ────────────
    mv_months = fetch_all(
        """
        SELECT DISTINCT
            EXTRACT(YEAR  FROM created_month)::int AS yr,
            EXTRACT(MONTH FROM created_month)::int AS mo
        FROM mv_employee_daily
        WHERE employee_id = %s::uuid
          AND EXTRACT(YEAR FROM created_month)::int >= 2026
        ORDER BY yr, mo
        """,
        (user_id,),
    )
    target_months = [(int(r["yr"]), int(r["mo"])) for r in mv_months]

    # ── Process each target month ─────────────────────────────────────────────
    for year, month in target_months:
        if year < 2026:
            continue            # absolute safety: never generate pre-2026

        report_code = f"{_MONTH_ABBR[month]}-{year}-{user_slug}"

        existing = fetch_one(
            """
            SELECT er.id,
                   (SELECT COUNT(*) FROM employee_report_rating_components
                    WHERE report_id = er.id) AS rc_count
            FROM employee_reports er
            WHERE er.report_code = %s AND er.employee_user_id = %s::uuid
            """,
            (report_code, user_id),
        )

        if not existing:
            _generate_employee_report(user_id, year, month)
        elif int(existing.get("rc_count") or 0) == 0:
            logger.info(
                "report_gen | repairing incomplete report=%s user=%s",
                report_code, user_id,
            )
            _generate_employee_report(user_id, year, month)


@api.get("/employee/reports")
def employee_reports_list(user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]

    # Ensure all MV-backed months are fully populated for this employee.
    try:
        _ensure_recent_reports(user_id)
    except Exception as exc:
        logger.warning("report_gen | auto-ensure failed user=%s err=%s", user_id, exc)

    rows = fetch_all(
        """
        SELECT "id", "month", "subtitle", "createdAt"
        FROM (
          SELECT DISTINCT ON (
              split_part(report_code, '-', 2),
              split_part(report_code, '-', 1)
            )
            report_code AS "id",
            month_label AS "month",
            subtitle    AS "subtitle",
            created_at  AS "createdAt"
          FROM employee_reports
          WHERE employee_user_id = %s
          AND report_code ~ '^[a-z]{3}-[0-9]{4}-[a-z0-9]+$'
          ORDER BY
            split_part(report_code, '-', 2),
            split_part(report_code, '-', 1),
            created_at DESC
        ) deduped
        ORDER BY
          split_part("id", '-', 2)::int DESC,
          CASE split_part("id", '-', 1)
            WHEN 'jan' THEN 1  WHEN 'feb' THEN 2  WHEN 'mar' THEN 3
            WHEN 'apr' THEN 4  WHEN 'may' THEN 5  WHEN 'jun' THEN 6
            WHEN 'jul' THEN 7  WHEN 'aug' THEN 8  WHEN 'sep' THEN 9
            WHEN 'oct' THEN 10 WHEN 'nov' THEN 11 WHEN 'dec' THEN 12
            ELSE 0
          END DESC
        LIMIT 24;
        """,
        (user_id,),
    )

    # Make createdAt ISO
    reports = []
    for r in rows:
        ca = r.get("createdAt")
        reports.append(
            {
                "id": r.get("id"),
                "month": r.get("month"),
                "subtitle": r.get("subtitle"),
                "createdAt": ca.isoformat() if ca else None,
            }
        )

    # fallback: if no reports, return empty list (frontend shows empty state)
    return {"reports": reports}


# IMPORTANT: this route MUST come before /{report_code} so FastAPI
# doesn't swallow "generate" as a report_code path param.
@api.get("/employee/reports/generate")
def employee_generate_report(
    year: int = Query(default=None),
    month: int = Query(default=None),
    user: Dict[str, Any] = Depends(require_employee),
):
    """
    Generates (or refreshes) the performance report for the given month.
    Defaults to the current calendar month.
    Returns the report_code so the frontend can immediately load it.

    Using GET (not POST) keeps this preflight-free and consistent with the
    other read-style report endpoints.
    """
    now = datetime.now(tz=timezone.utc)
    y = year  if year  and 2020 <= year  <= now.year + 1 else now.year
    m = month if month and 1   <= month  <= 12            else now.month

    code = _generate_employee_report(user["id"], y, m)
    if not code:
        raise HTTPException(status_code=404, detail="No ticket activity found for that month.")
    return {"reportCode": code, "month": f"{_MONTH_LABEL[m]} {y}"}


@api.get("/employee/reports/{report_code}")
def employee_report_detail(report_code: str, user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]
    # Safety net: if routing somehow sends 'generate' here, run the generator
    # instead of returning 400 Invalid report code.
    if report_code.lower() == "generate":
        now = datetime.now(tz=timezone.utc)
        code = _generate_employee_report(user_id, now.year, now.month)
        if not code:
            raise HTTPException(status_code=404, detail="No ticket activity found for this month.")
        return {"reportCode": code, "month": f"{_MONTH_LABEL[now.month]} {now.year}"}
    report_code = _safe_report_code(report_code)

    report = fetch_one(
        """
        SELECT
          id,
          report_code,
          employee_user_id,
          month_label,
          subtitle,
          kpi_rating,
          kpi_resolved,
          kpi_sla,
          kpi_avg_response
        FROM employee_reports
        WHERE report_code = %s AND employee_user_id = %s
        """,
        (report_code, user_id),
    )

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # employee meta for PDF
    profile = fetch_one(
        "SELECT full_name, employee_code FROM user_profiles WHERE user_id = %s",
        (user_id,),
    ) or {}

    summary_items = fetch_all(
        """
        SELECT label, value_text AS "value"
        FROM employee_report_summary_items
        WHERE report_id = %s
        ORDER BY label ASC;
        """,
        (report["id"],),
    )

    rating_components = fetch_all(
        """
        SELECT name, score, pct
        FROM employee_report_rating_components
        WHERE report_id = %s
        ORDER BY pct DESC;
        """,
        (report["id"],),
    )

    weekly = fetch_all(
        """
        SELECT
          week_label AS "week",
          assigned,
          resolved,
          sla,
          avg_response AS "avg",
          delta_type   AS "deltaType",
          delta_text   AS "deltaText"
        FROM employee_report_weekly
        WHERE report_id = %s
        ORDER BY week_label ASC;
        """,
        (report["id"],),
    )

    notes_rows = fetch_all(
        """
        SELECT note
        FROM employee_report_notes
        WHERE report_id = %s
        ORDER BY id ASC;
        """,
        (report["id"],),
    )

    return {
        "id": report["report_code"],
        "month": report["month_label"],
        "subtitle": report["subtitle"],
        "kpis": {
            "rating": report["kpi_rating"],
            "resolved": int(report["kpi_resolved"]),
            "sla": report["kpi_sla"],
            "avgResponse": report["kpi_avg_response"],
        },
        "summary": summary_items,  # [{label, value}]
        "ratingComponents": rating_components,  # [{name, score, pct}]
        "weekly": [
            {
                "week": w["week"],
                "assigned": int(w["assigned"]),
                "resolved": int(w["resolved"]),
                "sla": w["sla"],
                "avg": w["avg"],
                "delta": {"type": w["deltaType"], "text": w["deltaText"]},
            }
            for w in weekly
        ],
        "notes": [n["note"] for n in notes_rows],
        "employeeName": profile.get("full_name") or user.get("email"),
        "employeeId": profile.get("employee_code") or "",
    }


# Customer Dashboard
@api.get("/customer/dashboard")
def customer_dashboard(user: Dict[str, Any] = Depends(require_customer)):
    user_id = user["id"]

    # Get basic profile info
    profile = fetch_one(
        "SELECT full_name FROM user_profiles WHERE user_id = %s",
        (user_id,),
    )
    customer = {"name": (profile or {}).get("full_name") or user["email"]}

    # KPI summary
    kpi_row = fetch_one(
        """
        SELECT
          COUNT(*) AS totalTickets,
          COUNT(*) FILTER (WHERE status <> 'Resolved') AS openTickets,
          COUNT(*) FILTER (WHERE status = 'Resolved') AS resolvedTickets,
          COUNT(*) FILTER (WHERE created_at::date = current_date) AS newToday
        FROM tickets
        WHERE created_by_user_id = %s;
        """,
        (user_id,),
    ) or {}

    kpis = {
        "totalTickets": int(kpi_row.get("totalTickets") or 0),
        "openTickets": int(kpi_row.get("openTickets") or 0),
        "resolvedTickets": int(kpi_row.get("resolvedTickets") or 0),
        "newToday": int(kpi_row.get("newToday") or 0),
    }

    # Recent 5 tickets
    tickets = fetch_all(
        """
        SELECT
          ticket_code AS "ticketId",
          subject,
          priority,
          status,
          created_at
        FROM tickets
        WHERE created_by_user_id = %s
        ORDER BY created_at DESC
        LIMIT 5;
        """,
        (user_id,),
    )

    # Format date for frontend
    for t in tickets:
        t["issueDate"] = t["created_at"].date().isoformat() if t.get("created_at") else ""
        t.pop("created_at", None)

    return {"customer": customer, "kpis": kpis, "recentTickets": tickets}


# Customer History (All Tickets)
@api.get("/customer/mytickets")
def customer_mytickets(
    limit: int = Query(default=50, ge=1, le=500),
    user: Dict[str, Any] = Depends(require_customer),
):
    user_id = user["id"]

    rows = fetch_all(
        """
        SELECT
          ticket_code,
          subject,
          priority,
          ticket_type,
          status,
          created_at,
          priority_assigned_at,
          assigned_at,
          respond_due_at,
          resolve_due_at,
          first_response_at,
          resolved_at,
          linked_ticket_code
        FROM tickets
        WHERE created_by_user_id = %s
        ORDER BY created_at DESC
        LIMIT %s;
        """,
        (user_id, limit),
    )

    tickets = []
    for r in rows:
        created_at = r.get("created_at")
        priority_assigned_at = r.get("priority_assigned_at")
        assigned_at = r.get("assigned_at")
        respond_due_at = r.get("respond_due_at")
        resolve_due_at = r.get("resolve_due_at")

        issue_date = created_at.date().isoformat() if created_at else ""
        resp_base = priority_assigned_at or assigned_at or created_at
        response_time = minutes_to_label(diff_minutes(respond_due_at, resp_base))
        resolution_time = minutes_to_label(diff_minutes(resolve_due_at, priority_assigned_at or created_at))

        tickets.append(
            {
                "ticketId": r.get("ticket_code"),
                "subject": r.get("subject"),
                "priority": r.get("priority"),
                "ticketType": r.get("ticket_type"),
                "status": r.get("status"),
                "linkedTicketCode": r.get("linked_ticket_code") or None,
                "issueDate": issue_date,
                "minTimeToRespond": response_time,
                "minTimeToResolve": resolution_time,
            }
        )

    return {"tickets": tickets}


# Customer Ticket Details
@api.get("/customer/tickets/{ticket_code}")
def customer_ticket_details(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_customer),
):
    ticket_code = _sanitize_ticket_code(ticket_code)
    user_id = user["id"]

    row = fetch_one(
        """
        SELECT
          t.id,
          t.ticket_code,
          t.subject,
          t.details,
          t.priority,
          t.status,
          t.linked_ticket_code,
          t.created_at,
          t.priority_assigned_at,
          t.assigned_at,
          t.respond_due_at,
          t.resolve_due_at,
          t.first_response_at,
          t.resolved_at,
          t.model_suggestion,
          up.full_name AS assigned_employee_name
        FROM tickets t
        LEFT JOIN users u ON u.id = t.assigned_to_user_id
        LEFT JOIN user_profiles up ON up.user_id = u.id
        WHERE t.ticket_code = %s
          AND t.created_by_user_id = %s
        """,
        (ticket_code, user_id),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Attachments
    atts = fetch_all(
        """
        SELECT
          file_name,
          COALESCE(file_url, '/uploads/' || file_name) AS file_url
        FROM ticket_attachments
        WHERE ticket_id = %s
        ORDER BY uploaded_at ASC
        """,
        (row["id"],),
    )

    # Ticket Updates
    updates_rows = fetch_all(
        """
        SELECT
          tu.message,
          tu.update_type,
          tu.created_at,
          up.full_name AS author_name
        FROM ticket_updates tu
        LEFT JOIN user_profiles up ON up.user_id = tu.author_user_id
        WHERE tu.ticket_id = %s
        ORDER BY tu.created_at ASC
        """,
        (row["id"],),
    )

    created_at = row.get("created_at")
    priority_assigned_at = row.get("priority_assigned_at")
    assigned_at = row.get("assigned_at")
    respond_due_at = row.get("respond_due_at")
    resolve_due_at = row.get("resolve_due_at")

    issue_date = created_at.date().isoformat() if created_at else ""
    resp_base = priority_assigned_at or assigned_at or created_at
    response_time = minutes_to_label(diff_minutes(respond_due_at, resp_base))
    resolution_time = minutes_to_label(diff_minutes(resolve_due_at, priority_assigned_at or created_at))

    ticket = {
        "ticketId": row.get("ticket_code"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "linkedTicketCode": row.get("linked_ticket_code") or None,
        "issueDate": issue_date,
        "modelSuggestion": row.get("model_suggestion"),
        "assignedEmployee": row.get("assigned_employee_name") or None,
        "metrics": {
            "minTimeToRespond": response_time,
            "minTimeToResolve": resolution_time,
        },
        "description": {
            "subject": row.get("subject"),
            "details": row.get("details"),
        },
        "attachments": [{"fileName": a["file_name"], "fileUrl": a["file_url"]} for a in atts] if atts else [],

        "previousResolutions": _extract_previous_resolutions(updates_rows),
    }

    return {"ticket": ticket}


# Customer Notifications Popup
@api.get("/customer/notifications")
def customer_notifications_popup(
    limit: int = Query(default=10, ge=1, le=50),  # popup shows top N
    only_unread: bool = Query(default=False),
    mark_read: bool = Query(default=False),  # new param to mark them read
    user: Dict[str, Any] = Depends(require_customer),
):
    user_id = user["id"]
    # Fetch notifications
    rows = fetch_all(
        """
        SELECT
          n.id::text           AS "id",
          n.type::text         AS "type",
          n.title              AS "title",
          n.message            AS "message",
          n.priority::text     AS "priority",
          t.ticket_code        AS "ticketId",
          n.report_id          AS "reportId",
          n.read               AS "read",
          n.created_at         AS "timestamp"
        FROM notifications n
        LEFT JOIN tickets t ON t.id = n.ticket_id
        WHERE n.user_id = %s
          AND (%s = FALSE OR n.read = FALSE)
        ORDER BY n.created_at DESC
        LIMIT %s;
        """,
        (user_id, only_unread, limit),
    )

    # Mark the fetched notifications as read if requested
    if mark_read and rows:
        notification_ids = [r["id"] for r in rows]

        if notification_ids:
            # dynamically generate placeholders for IN clause
            placeholders = ", ".join(["%s"] * len(notification_ids))
            sql = f"""
            UPDATE notifications
            SET read = TRUE
            WHERE id IN ({placeholders});
            """
            execute(sql, notification_ids)

    # Count unread for badge
    unread_row = fetch_one(
        "SELECT COUNT(*)::int AS unread FROM notifications WHERE user_id = %s AND read = FALSE;",
        (user_id,),
    ) or {"unread": 0}

    # Format for frontend
    notifications = [
        {
            "id": r["id"],
            "type": r["type"],
            "title": r["title"],
            "message": r["message"],
            "priority": r["priority"],
            "ticketId": r["ticketId"],
            "reportId": r["reportId"],
            "read": bool(r["read"]),
            "timestamp": r["timestamp"].isoformat() if r["timestamp"] else None,
        }
        for r in rows
    ]

    return {"unreadCount": int(unread_row.get("unread") or 0), "notifications": notifications}

# Customer Create Ticket
class TicketAttachment(BaseModel):
    name: str
    type: Optional[str]
    size: Optional[int]
    lastModified: Optional[int]

class CreateTicketRequest(BaseModel):
    name: str
    email: str
    type: str
    asset_type: str
    subject: str
    details: str
    has_audio: Optional[bool] = False
    audio_features: Optional[dict] = None
    attachments: Optional[List[TicketAttachment]] = []
    sentiment: Optional[dict] = None

    from pydantic import validator

    @validator("name")
    def name_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("name must not be empty.")
        if len(v) > 120:
            raise ValueError("name exceeds maximum length of 120 characters.")
        return v

    @validator("email")
    def email_format(cls, v):
        import re as _r
        v = (v or "").strip().lower()
        if not _r.match(r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$', v):
            raise ValueError("Invalid email address.")
        if len(v) > 254:
            raise ValueError("Email address too long.")
        return v

    @validator("type")
    def type_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("type must not be empty.")
        if len(v) > 60:
            raise ValueError("type exceeds maximum length of 60 characters.")
        return v

    @validator("asset_type")
    def asset_type_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("asset_type must not be empty.")
        if len(v) > 120:
            raise ValueError("asset_type exceeds maximum length of 120 characters.")
        return v

    @validator("subject")
    def subject_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("subject must not be empty.")
        if len(v) > 300:
            raise ValueError("subject exceeds maximum length of 300 characters.")
        return v

    @validator("details")
    def details_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("details must not be empty.")
        if len(v) > 10000:
            raise ValueError("details exceeds maximum length of 10000 characters.")
        return v


class InternalCreateTicketRequest(BaseModel):
    created_by_user_id: str
    ticket_type: str
    subject: str
    details: str
    ticket_source: Optional[str] = "chatbot"
    asset_type: Optional[str] = "General"

    @field_validator("details")
    @classmethod
    def details_within_word_limit(cls, value: str) -> str:
        return _validate_customer_text_words(value, "details") or ""


def _dispatch_orchestrator_after_submit(
    *,
    ticket_code: str,
    details: str,
    ticket_type: Optional[str],
    subject: Optional[str],
    execution_id: Optional[str],
    has_audio: bool = False,
    audio_features: Optional[dict] = None,
) -> None:
    ok = dispatch_ticket_to_orchestrator(
        ticket_code=ticket_code,
        details=details,
        orchestrator_url=ORCHESTRATOR_URL,
        orchestrator_url_local=ORCHESTRATOR_URL_LOCAL,
        ticket_type=ticket_type,
        subject=subject,
        execution_id=execution_id,
        has_audio=has_audio,
        audio_features=audio_features,
    )
    if not ok:
        logger.warning("orchestrator_dispatch | failed for ticket=%s", ticket_code)
        log_application_event(
            service="backend",
            event_key="orchestrator_dispatch",
            level="WARNING",
            ticket_code=ticket_code,
            payload={"status": "failed"},
        )
    else:
        logger.info("orchestrator_dispatch | accepted for ticket=%s", ticket_code)
        log_application_event(
            service="backend",
            event_key="orchestrator_dispatch",
            ticket_code=ticket_code,
            payload={"status": "accepted"},
        )


@api.post("/internal/tickets/create")
def create_internal_ticket_via_gate(body: InternalCreateTicketRequest, _key: None = Depends(require_internal_key)):
    """
    Internal ticket creation endpoint for services (e.g., chatbot).
    Flow: ticket_creation_gate insert -> orchestrator dispatch.
    """
    requester = fetch_one("SELECT id FROM users WHERE id = %s LIMIT 1;", (body.created_by_user_id,))
    if not requester:
        raise HTTPException(status_code=404, detail="created_by_user_id not found")

    type_norm = str(body.ticket_type or "").strip().lower()
    ticket_type = "Inquiry" if type_norm == "inquiry" else "Complaint"
    subject = (body.subject or "").strip() or (body.details or "").strip()[:120] or f"Automated {ticket_type.lower()}"
    details = (body.details or "").strip()
    if not details:
        raise HTTPException(status_code=422, detail="details cannot be empty")

    with db_connect() as conn:
        with conn.cursor() as cur:
            created = create_ticket_via_gate(
                cur,
                created_by_user_id=body.created_by_user_id,
                ticket_type=ticket_type,
                subject=subject,
                details=details,
                priority=None,
                status="Open",
                ticket_source=(body.ticket_source or "chatbot").strip() or "chatbot",
                model_suggestion=json.dumps({"is_recurring": False}),
            )

    ticket_code = created["ticket_code"]
    orchestrator_dispatched = dispatch_ticket_to_orchestrator(
        ticket_code=ticket_code,
        details=details,
        orchestrator_url=ORCHESTRATOR_URL,
        orchestrator_url_local=ORCHESTRATOR_URL_LOCAL,
        ticket_type=ticket_type,
        subject=subject,
        execution_id=created.get("execution_id"),
    )
    if not orchestrator_dispatched:
        logger.warning(
            "orchestrator_dispatch | failed for internal ticket=%s",
            ticket_code,
        )

    return {
        "ok": True,
        "ticket_id": ticket_code,
        "status": created.get("status"),
        "priority": created.get("priority"),
        "priority_assigned_at": created.get("priority_assigned_at").isoformat() if created.get("priority_assigned_at") else None,
        "respond_due_at": created.get("respond_due_at").isoformat() if created.get("respond_due_at") else None,
        "resolve_due_at": created.get("resolve_due_at").isoformat() if created.get("resolve_due_at") else None,
    }


@api.post("/customer/tickets")
def create_customer_ticket(
    body: CreateTicketRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_customer),
    _csrf: None = Depends(require_csrf),
):
    is_recurring = predict_is_recurring(user_id=user["id"], subject=body.subject, details=body.details)
    model_suggestion = json.dumps({"is_recurring": is_recurring})

    # Insert ticket into database through centralized gate.
    ticket_id = None
    ticket_code = None
    execution_id = None
    with db_connect() as conn:
        with conn.cursor() as cur:
            normalized_ticket_type = (
                "Inquiry"
                if str(body.type or "").strip().lower() == "inquiry"
                else "Complaint"
            )
            created = create_ticket_via_gate(
                cur,
                created_by_user_id=user["id"],
                ticket_type=normalized_ticket_type,
                subject=body.subject,
                details=body.details,
                priority=None,
                status="Open",
                ticket_source="user",
                model_suggestion=model_suggestion,
            )
            ticket_id = created["id"]
            ticket_code = created["ticket_code"]
            execution_id = created.get("execution_id")
            logger.info(
                "customer_ticket_submit | ticket_code=%s user_id=%s type=%s status=%s priority=%s",
                ticket_code,
                user["id"],
                normalized_ticket_type,
                created.get("status"),
                created.get("priority"),
            )
            log_application_event(
                service="backend",
                event_key="customer_ticket_submit",
                ticket_id=ticket_id,
                ticket_code=ticket_code,
                payload={
                    "user_id": str(user["id"]),
                    "type": normalized_ticket_type,
                    "status": created.get("status"),
                    "priority": created.get("priority"),
                },
                cur=cur,
            )

            # Insert attachments if any
            for att in body.attachments or []:
                cur.execute(
                    """
                    INSERT INTO ticket_attachments (ticket_id, file_name)
                    VALUES (%s, %s);
                    """,
                    (ticket_id, att.name),
                )

            # Suggested resolution is generated by orchestrator flow.

    background_tasks.add_task(
        _dispatch_orchestrator_after_submit,
        ticket_code=ticket_code,
        details=body.details,
        ticket_type=body.type,
        subject=body.subject,
        execution_id=execution_id,
        has_audio=bool(body.has_audio),
        audio_features=body.audio_features if isinstance(body.audio_features, dict) else None,
    )
    logger.info("orchestrator_dispatch | queued for ticket=%s", ticket_code)
    log_application_event(
        service="backend",
        event_key="orchestrator_dispatch",
        ticket_id=ticket_id,
        ticket_code=ticket_code,
        payload={"status": "queued"},
    )

    return {
        "ok": True,
        "message": "Ticket created successfully",
        "ticket": {
            "ticketId": ticket_code,
            "ticketType": body.type,
            "subject": body.subject,
            "priority": created.get("priority"),
            "status": created.get("status"),
            "is_recurring": is_recurring,
            "priority_assigned_at": created.get("priority_assigned_at").isoformat() if created.get("priority_assigned_at") else None,
            "respond_due_at": created.get("respond_due_at").isoformat() if created.get("respond_due_at") else None,
            "resolve_due_at": created.get("resolve_due_at").isoformat() if created.get("resolve_due_at") else None,
        },
    }

# Customer Settings - GET
@api.get("/customer/setting")
def get_customer_settings(
    user: Dict[str, Any] = Depends(require_customer),
):
    user_id = user["id"]

    row = fetch_one(
        """
        SELECT
            u.email,
            u.role,
            up.full_name,
            up.phone,
            pref.language,
            pref.dark_mode,
            pref.default_complaint_type,
            pref.email_notifications,
            pref.in_app_notifications,
            pref.status_alerts
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN user_preferences pref ON pref.user_id = u.id
        WHERE u.id = %s
        """,
        (user_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "account": {
            "name": row["full_name"],
            "email": row["email"],
            "phone": row["phone"],
            "role": row["role"],
        },
        "preferences": {
            "language": row.get("language", "English"),
            "darkMode": row.get("dark_mode", False),
            "defaultComplaintType": row.get("default_complaint_type", "General"),
            "emailNotifications": row.get("email_notifications", True),
            "inAppNotifications": row.get("in_app_notifications", True),
            "statusAlerts": row.get("status_alerts", True),
        },
    }

# Customer Settings - UPDATE
@api.put("/customer/setting")
def update_customer_settings(
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_customer),
    _csrf: None = Depends(require_csrf),
):
    user_id = user["id"]

    execute(
        """
        INSERT INTO user_preferences (
            user_id,
            language,
            dark_mode,
            default_complaint_type,
            email_notifications,
            in_app_notifications,
            status_alerts
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET
            language = EXCLUDED.language,
            dark_mode = EXCLUDED.dark_mode,
            default_complaint_type = EXCLUDED.default_complaint_type,
            email_notifications = EXCLUDED.email_notifications,
            in_app_notifications = EXCLUDED.in_app_notifications,
            status_alerts = EXCLUDED.status_alerts,
            updated_at = now()
        """,
        (
            user_id,
            payload.get("language", "English"),
            payload.get("darkMode", False),
            payload.get("defaultComplaintType", "General"),
            payload.get("emailNotifications", True),
            payload.get("inAppNotifications", True),
            payload.get("statusAlerts", True),
        ),
    )

    return {"success": True}    

# Manager View

@api.get("/manager/employees")
def get_employees(user: Dict[str, Any] = Depends(require_manager)):
    dept_id = user.get("department_id")
    if dept_id:
        employees = fetch_all("""
            SELECT
                up.full_name AS name,
                up.employee_code AS id,
                up.job_title AS role,
                u.id AS user_id
            FROM user_profiles up
            JOIN users u ON u.id = up.user_id
            WHERE u.role = 'employee'
              AND u.is_active = TRUE
              AND up.department_id = %s
        """, (dept_id,))
    else:
        employees = fetch_all("""
            SELECT
                up.full_name AS name,
                up.employee_code AS id,
                up.job_title AS role,
                u.id AS user_id
            FROM user_profiles up
            JOIN users u ON u.id = up.user_id
            WHERE u.role = 'employee'
              AND u.is_active = TRUE
        """)

    result = []
    for emp in employees:
        completed = fetch_one(
            "SELECT COUNT(*) AS count FROM tickets WHERE assigned_to_user_id = %s AND status = 'Resolved'",
            (emp["user_id"],)
        )["count"]

        in_progress = fetch_one(
            "SELECT COUNT(*) AS count FROM tickets WHERE assigned_to_user_id = %s AND status IN ('Open','In Progress','Assigned')",
            (emp["user_id"],)
        )["count"]

        result.append({
            "name": emp["name"],
            "id": emp["id"],
            "role": emp["role"],
            "completed": completed,
            "inProgress": in_progress
        })

    return result



@api.get("/manager/complaints")
def get_complaints(user: Dict[str, Any] = Depends(require_manager)):
    dept_id = user.get("department_id")
    if dept_id:
        tickets = fetch_all("""
            SELECT
                t.id AS ticket_id,
                t.ticket_code,
                t.subject AS subject,
                t.status,
                t.priority,
                t.created_at,
                t.updated_at,
                t.priority_assigned_at,
                t.assigned_at,
                t.first_response_at,
                t.resolved_at,
                t.assigned_to_user_id,
                up.full_name AS assignee_name,
                d.name AS department_name
            FROM tickets t
            LEFT JOIN user_profiles up ON t.assigned_to_user_id = up.user_id
            LEFT JOIN departments d ON d.id = t.department_id
            WHERE t.department_id = %s
            ORDER BY t.created_at DESC;
        """, (dept_id,))
    else:
        tickets = fetch_all("""
            SELECT
                t.id AS ticket_id,
                t.ticket_code,
                t.subject AS subject,
                t.status,
                t.priority,
                t.created_at,
                t.updated_at,
                t.priority_assigned_at,
                t.assigned_at,
                t.first_response_at,
                t.resolved_at,
                t.assigned_to_user_id,
                up.full_name AS assignee_name,
                d.name AS department_name
            FROM tickets t
            LEFT JOIN user_profiles up ON t.assigned_to_user_id = up.user_id
            LEFT JOIN departments d ON d.id = t.department_id
            ORDER BY t.created_at DESC;
        """)

    result = []
    for t in tickets:
        issue_date = t["created_at"].date().isoformat() if t.get("created_at") else ""
        resp_base = t.get("priority_assigned_at") or t.get("assigned_at") or t.get("created_at")
        resp_mins = diff_minutes(t.get("first_response_at"), resp_base)
        respond_time = minutes_to_label(resp_mins)
        res_base = t.get("priority_assigned_at") or t.get("created_at")
        res_mins = diff_minutes(t.get("resolved_at"), res_base)
        resolve_time = minutes_to_label(res_mins)

        assignee = t.get("assignee_name") or "—"

        priority_map = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
        priority_text = priority_map.get((t.get("priority") or "").lower(), t.get("priority") or "")
        action = "Assign" if assignee == "—" else "Reassign"

        result.append({
            "id": t["ticket_id"],
            "resolvedAt": t["resolved_at"].isoformat() if t.get("resolved_at") else None,
            "subject": t.get("subject") or "No description",
            "priority": (t.get("priority") or "").lower(),
            "priorityText": priority_text,
            "status": t["status"],
            "assignee": assignee,
            "issueDate": issue_date,
            "respondTime": respond_time,
            "resolveTime": resolve_time,
            "action": action,
            "ticket_code": t.get("ticket_code") or "",
            "department": t.get("department_name") or "",
        })

    return result

class AssignTicketBody(BaseModel):
    employee_name: Optional[str] = None

# FIX (Issues 2 & 3): Register on both @app (legacy /manager/... path kept for
# backward-compat) AND @api (/api/manager/... path) so that frontend calls to
# /api/manager/complaints/{id}/assign work correctly on GCP prod where the
# @app routes at /manager/... may not share the same CORS/proxy config as /api/...
@app.patch("/manager/complaints/{ticket_id}/assign")
@api.patch("/manager/complaints/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    body: AssignTicketBody,
    authorization: Optional[str] = Header(default=None),
    _csrf: None = Depends(require_csrf),
):
    ticket_id = _sanitize_uuid(ticket_id, "ticket_id")
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

    if body.employee_name:
        emp = fetch_one(
            """
            SELECT u.id AS user_id
            FROM user_profiles up
            JOIN users u ON u.id = up.user_id
            WHERE up.full_name = %s AND u.role = 'employee'
            LIMIT 1
            """,
            (body.employee_name,),
        )
        if not emp:
            raise HTTPException(status_code=404, detail="Employee not found")

        execute(
            """
            UPDATE tickets
            SET
                assigned_to_user_id = %s,
                assigned_at         = NOW(),
                priority_assigned_at = COALESCE(priority_assigned_at, NOW()),
                updated_at          = NOW(),
                status              = CASE
                                        WHEN status = 'Resolved' THEN status
                                        ELSE 'Assigned'::ticket_status
                                      END
            WHERE id = %s
            """,
            (emp["user_id"], ticket_id),
        )
        return {"ticket_id": ticket_id, "assigned_to": body.employee_name, "action": "assigned"}

    else:
        execute(
            """
            UPDATE tickets
            SET
                assigned_to_user_id = NULL,
                assigned_at         = NULL,
                priority_assigned_at = NULL,
                respond_due_at = NULL,
                resolve_due_at = NULL,
                respond_time_left_seconds = NULL,
                resolve_time_left_seconds = NULL,
                respond_breached = FALSE,
                resolve_breached = FALSE,
                updated_at          = NOW(),
                status              = 'Open'
            WHERE id = %s
            """,
            (ticket_id,),
        )
        return {"ticket_id": ticket_id, "assigned_to": None, "action": "unassigned"}
class RouteTicketBody(BaseModel):
    department: str
    reason: Optional[str] = None

@app.patch("/manager/complaints/{ticket_id}/resolve")
@api.patch("/manager/complaints/{ticket_id}/resolve")
def manager_resolve_ticket(
    ticket_id: str,
    body: ManagerResolveRequest,
    authorization: Optional[str] = Header(default=None),
    _csrf: None = Depends(require_csrf),
):
    ticket_id = _sanitize_uuid(ticket_id, "ticket_id")
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

    final_resolution = (body.final_resolution or "").strip()
    if not final_resolution:
        raise HTTPException(status_code=422, detail="Resolution text is required")

    ticket = fetch_one(
        "SELECT id, ticket_code, status FROM tickets WHERE id = %s LIMIT 1;",
        (ticket_id,),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket["status"] == "Resolved":
        raise HTTPException(status_code=409, detail="Ticket is already resolved")

    from_status = ticket["status"]

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Update ticket — status, final_resolution, resolved_at, resolved_by
            cur.execute(
                """
                UPDATE tickets
                SET
                    status              = 'Resolved',
                    final_resolution    = %s,
                    resolved_at         = COALESCE(resolved_at, now()),
                    resolved_by_user_id = %s,
                    first_response_at   = COALESCE(first_response_at, now()),
                    updated_at          = now()
                WHERE id = %s
                RETURNING id, ticket_code, status, resolved_at;
                """,
                (final_resolution, user["id"], ticket_id),
            )
            row = cur.fetchone()

            # 2. Log in ticket_updates
            cur.execute(
                """
                INSERT INTO ticket_updates (
                    ticket_id, author_user_id, update_type,
                    message, from_status, to_status
                )
                VALUES (%s, %s, 'status_change', %s, %s, 'Resolved');
                """,
                (
                    ticket_id,
                    user["id"],
                    f"Ticket resolved by manager. Resolution: {final_resolution}",
                    from_status,
                ),
            )

            # 3. Store steps taken if provided
            if (body.steps_taken or "").strip():
                cur.execute(
                    """
                    INSERT INTO ticket_work_steps (
                        ticket_id, step_no, technician_user_id, notes
                    )
                    VALUES (
                        %s,
                        COALESCE(
                            (SELECT MAX(step_no) FROM ticket_work_steps WHERE ticket_id = %s),
                            0
                        ) + 1,
                        %s,
                        %s
                    );
                    """,
                    (ticket_id, ticket_id, user["id"], body.steps_taken.strip()),
                )
            
            # 4. Notifications handled by DB triggers:
            #   trg_notify_on_ticket_resolved     → resolver (manager) + assigned employee + managers
            #   trg_notify_customer_status_change → customer

    logger.info(
        "manager_resolve | ticket=%s from=%s resolved_at=%s by=%s",
        row["ticket_code"], from_status, row["resolved_at"], user["id"],
    )
    return {
        "ok": True,
        "ticketCode": row["ticket_code"],
        "status": row["status"],
        "resolvedAt": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
    }

@app.patch("/manager/complaints/{ticket_id}/priority")
@api.patch("/manager/complaints/{ticket_id}/priority")
def manager_rescore_ticket(
    ticket_id: str,
    body: ManagerRescoreRequest,
    authorization: Optional[str] = Header(default=None),
    _csrf: None = Depends(require_csrf),
):
    ticket_id = _sanitize_uuid(ticket_id, "ticket_id")
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

    allowed_priorities = {"Low", "Medium", "High", "Critical"}
    new_priority = (body.new_priority or "").strip()
    reason = (body.reason or "").strip()

    if new_priority not in allowed_priorities:
        raise HTTPException(status_code=422, detail=f"Invalid priority. Must be one of: {', '.join(sorted(allowed_priorities))}")
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required")

    # Fetch ticket to get current priority and code
    ticket = fetch_one(
        "SELECT id, ticket_code, priority FROM tickets WHERE id = %s LIMIT 1;",
        (ticket_id,),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    current_priority = ticket["priority"]
    ticket_code = ticket["ticket_code"]
    request_code = f"REQ-{int(time.time() * 1000) % 10000000}"

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # 1. Update the ticket priority immediately
            cur.execute(
                "UPDATE tickets SET priority = %s, updated_at = now() WHERE id = %s;",
                (new_priority, ticket_id),
            )

            # 2. Insert an approval_request already marked as Approved
            #    decided_by_user_id = manager, decided_at = now()
            cur.execute(
                """
                INSERT INTO approval_requests (
                  request_code, ticket_id, request_type,
                  current_value, requested_value,
                  request_reason, submitted_by_user_id,
                  submitted_at, status,
                  decided_by_user_id, decided_at, decision_notes
                )
                VALUES (%s, %s, 'Rescoring', %s, %s, %s, %s, now(), 'Approved', %s, now(), %s)
                RETURNING request_code;
                """,
                (
                    request_code,
                    ticket_id,
                    f"Priority: {current_priority}",
                    f"Priority: {new_priority}",
                    reason,
                    user["id"],   # submitted_by = manager themselves
                    user["id"],   # decided_by   = manager themselves
                    reason,       # decision_notes stores the reason too
                ),
            )
            result = cur.fetchone()

            # 3. Log it as a ticket_update for the activity trail
            cur.execute(
                """
                INSERT INTO ticket_updates (
                  ticket_id, author_user_id, update_type, message
                )
                VALUES (%s, %s, 'priority_change', %s);
                """,
                (
                    ticket_id,
                    user["id"],
                    f"Manager changed priority from {current_priority} to {new_priority}. Reason: {reason}",
                ),
            )

            # Notifications handled by DB trigger:
            #   trg_notify_on_manager_rescore → manager self-confirmation + assigned employee

    logger.info(
        "manager_rescore | ticket=%s from=%s to=%s request=%s by=%s",
        ticket_code, current_priority, new_priority, result["request_code"], user["id"],
    )
    _trigger_priority_relearning(ticket_id=ticket_id, approved_priority=new_priority)
    return {
        "ok": True,
        "requestCode": result["request_code"],
        "newPriority": new_priority,
        "status": "Approved",
    }

@app.patch("/manager/complaints/{ticket_id}/department")
@api.patch("/manager/complaints/{ticket_id}/department")
def route_ticket_department(
    ticket_id: str,
    body: RouteTicketBody,
    authorization: Optional[str] = Header(default=None),
    _csrf: None = Depends(require_csrf),
):
    ticket_id = _sanitize_uuid(ticket_id, "ticket_id")
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

    dept_name = (body.department or "").strip()
    if not dept_name:
        raise HTTPException(status_code=422, detail="Department is required")

    dept = fetch_one(
        "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s) LIMIT 1;",
        (dept_name,),
    )
    if not dept:
        raise HTTPException(status_code=404, detail=f"Department '{dept_name}' not found")

    # Fetch BEFORE updating so old_dept is still the current one
    t_info = fetch_one(
        """
        SELECT t.ticket_code, t.assigned_to_user_id, t.priority,
               d_old.name AS old_dept
        FROM tickets t
        LEFT JOIN departments d_old ON d_old.id = t.department_id
        WHERE t.id = %s LIMIT 1;
        """,
        (ticket_id,),
    ) or {}

    execute(
        """
        UPDATE tickets
        SET department_id = %s,
            updated_at    = NOW()
        WHERE id = %s
        """,
        (dept["id"], ticket_id),
    )

    ticket_code  = t_info.get("ticket_code") or ticket_id
    assigned_uid = t_info.get("assigned_to_user_id")
    t_priority   = t_info.get("priority")
    old_dept     = t_info.get("old_dept") or "Unknown"
    reroute_reason = (body.reason or "").strip()

    with db_connect() as conn:
        with conn.cursor() as cur:
            _insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=f"Ticket Rerouted: {ticket_code}",
                message=f"You rerouted ticket {ticket_code} from {old_dept} to {dept_name}."
                        + (f" Reason: {reroute_reason}" if reroute_reason else ""),
                ticket_id=ticket_id,
                priority=t_priority,
            )

            if assigned_uid and str(assigned_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(assigned_uid),
                    notif_type="status_change",
                    title=f"Ticket Rerouted: {ticket_code}",
                    message=f"Your ticket {ticket_code} has been rerouted from {old_dept} to the {dept_name} department."
                            + (f" Reason: {reroute_reason}" if reroute_reason else ""),
                    ticket_id=ticket_id,
                    priority=t_priority,
                )

    return {"ticket_id": ticket_id, "department": dept_name, "action": "rerouted"}

@app.get("/manager/departments")
@api.get("/manager/departments")
def get_departments(authorization: Optional[str] = Header(default=None)):
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")
    depts = fetch_all("SELECT name FROM departments ORDER BY name;")
    # FIX (Issue 1): normalize and deduplicate department names.
    # Live DB may have both "Legal & Compliance" and "Legal and Compliance".
    DEPT_NORMALIZE = {"legal and compliance": "Legal & Compliance"}
    seen = set()
    result = []
    for d in depts:
        canonical = DEPT_NORMALIZE.get((d["name"] or "").lower(), d["name"])
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result

@api.get("/manager")
def get_manager_kpis(user: Dict[str, Any] = Depends(require_manager)):
    dept_id = user.get("department_id")
    # Fetch the manager's department name for the frontend header
    dept_row = fetch_one("SELECT name FROM departments WHERE id = %s", (dept_id,)) if dept_id else None
    dept_name = (dept_row or {}).get("name") or ""

    if dept_id:
        row = fetch_one("""
            SELECT
                COUNT(*) FILTER (WHERE status <> 'Resolved')                                                        AS open_complaints,
                COUNT(*) FILTER (WHERE status NOT IN ('Resolved'::ticket_status, 'Open'::ticket_status))            AS in_progress,
                COUNT(*) FILTER (WHERE resolved_at::date = CURRENT_DATE)                                            AS resolved_today,
                (SELECT COUNT(*) FROM users u JOIN user_profiles up ON up.user_id = u.id
                 WHERE u.role = 'employee' AND up.department_id = %s)                                               AS active_employees,
                (SELECT COUNT(*) FROM approval_requests WHERE status = 'Pending')                                   AS pending_approvals
            FROM tickets
            WHERE department_id = %s;
        """, (dept_id, dept_id))
    else:
        row = fetch_one("""
            SELECT
                COUNT(*) FILTER (WHERE status <> 'Resolved')                                                        AS open_complaints,
                COUNT(*) FILTER (WHERE status NOT IN ('Resolved'::ticket_status, 'Open'::ticket_status))            AS in_progress,
                COUNT(*) FILTER (WHERE resolved_at::date = CURRENT_DATE)                                            AS resolved_today,
                (SELECT COUNT(*) FROM users WHERE role = 'employee')                                                AS active_employees,
                (SELECT COUNT(*) FROM approval_requests WHERE status = 'Pending')                                   AS pending_approvals
            FROM tickets;
        """)
    return {
        "openComplaints":   int((row or {}).get("open_complaints")   or 0),
        "inProgress":       int((row or {}).get("in_progress")       or 0),
        "resolvedToday":    int((row or {}).get("resolved_today")    or 0),
        "activeEmployees":  int((row or {}).get("active_employees")  or 0),
        "pendingApprovals": int((row or {}).get("pending_approvals") or 0),
        "managerName":      user.get("full_name") or user.get("email") or "",
        "departmentName":   dept_name,
    }


@api.get("/manager/approvals")
def get_approvals(user: Dict[str, Any] = Depends(require_manager)):
    dept_id = user.get("department_id")
    if dept_id:
        approvals = fetch_all("""
SELECT
    ar.id AS request_id,
    t.id AS ticket_id,
    t.ticket_code,
    t.subject AS ticket_subject,
    ar.request_type AS type,
    ar.current_value AS current,
    ar.requested_value AS requested,
    ar.request_reason AS request_reason,
    up.full_name AS submitted_by,
    ar.submitted_at AS submitted_on,
    ar.status AS status,
    du.full_name AS decided_by,
    ar.decided_at AS decision_date,
    ar.decision_notes
FROM approval_requests ar
LEFT JOIN tickets t ON ar.ticket_id = t.id
LEFT JOIN user_profiles up ON ar.submitted_by_user_id = up.user_id
LEFT JOIN user_profiles du ON ar.decided_by_user_id = du.user_id
WHERE t.department_id = %s
ORDER BY ar.submitted_at DESC;
""", (dept_id,))
    else:
        approvals = fetch_all("""
SELECT
    ar.id AS request_id,
    t.id AS ticket_id,
    t.ticket_code,
    t.subject AS ticket_subject,
    ar.request_type AS type,
    ar.current_value AS current,
    ar.requested_value AS requested,
    ar.request_reason AS request_reason,
    up.full_name AS submitted_by,
    ar.submitted_at AS submitted_on,
    ar.status AS status,
    du.full_name AS decided_by,
    ar.decided_at AS decision_date,
    ar.decision_notes
FROM approval_requests ar
LEFT JOIN tickets t ON ar.ticket_id = t.id
LEFT JOIN user_profiles up ON ar.submitted_by_user_id = up.user_id
LEFT JOIN user_profiles du ON ar.decided_by_user_id = du.user_id
ORDER BY ar.submitted_at DESC;
""")

    result = []

    for a in approvals:
        submitted_on = a["submitted_on"].isoformat() if a.get("submitted_on") else ""
        decision_date = a["decision_date"].isoformat() if a.get("decision_date") else ""

        result.append({
            "requestId": a["request_id"],
            "ticketId": a["ticket_id"],
            "ticketCode": a.get("ticket_code") or "",
            "ticketSubject": a.get("ticket_subject") or "No subject",
            "type": a.get("type") or "",
            "current": a.get("current") or "",
            "requested": a.get("requested") or "",
            "requestReason": a.get("request_reason") or "",
            "submittedBy": a.get("submitted_by") or "—",
            "submittedOn": submitted_on,
            "status": a.get("status") or "Pending",
            "decidedBy": a.get("decided_by") or "",
            "decisionDate": decision_date,
            "decisionNotes": a.get("decision_notes") or ""
        })

    return result


# Manager: Approve / Reject an approval request

class ApprovalDecisionRequest(BaseModel):
    decision: str                      # "Approved" or "Rejected"
    decision_notes: Optional[str] = None
    override_value: Optional[str] = None   # Manager override: priority name OR department name

@api.patch("/manager/approvals/{request_id}")
def decide_approval(
    request_id: str,
    body: ApprovalDecisionRequest,
    authorization: Optional[str] = Header(default=None),
    _csrf: None = Depends(require_csrf),
):
    request_id = _sanitize_uuid(request_id, "request_id")
    user = _validate_token_and_fetch_user(_get_bearer_token(authorization))
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")
    decision = (body.decision or "").strip()
    if decision not in ("Approved", "Rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'Approved' or 'Rejected'")

    # Fetch the approval request
    ar = fetch_one(
        """
        SELECT ar.id, ar.status, ar.request_type, ar.requested_value, ar.ticket_id
        FROM approval_requests ar
        WHERE ar.id::text = %s
        LIMIT 1;
        """,
        (request_id,),
    )
    if not ar:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if ar["status"] != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been decided")

    relearn_ticket_id = None
    relearn_priority = None

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Update the approval_requests record
            cur.execute(
                """
                UPDATE approval_requests
                SET
                    status             = %s,
                    decided_by_user_id = %s,
                    decided_at         = now(),
                    decision_notes     = %s
                WHERE id::text = %s;
                """,
                (decision, user["id"], body.decision_notes or "", request_id),
            )

            # 2. If approved, apply the change to the ticket
            #    If override_value is provided, the manager chose a different value
            #    than what the employee requested — use that instead.
            if decision == "Approved":
                req_type  = ar["request_type"]
                requested = ar["requested_value"] or ""
                current = ar.get("current_value") or ""
                ticket_id = ar["ticket_id"]
                override  = (body.override_value or "").strip()

                if req_type == "Rescoring":
                    # Use override priority if provided, otherwise use requested
                    if override:
                        new_priority = override
                    else:
                        new_priority = requested.replace("Priority:", "").strip()
                    allowed = {"Low", "Medium", "High", "Critical"}
                    if new_priority in allowed:
                        cur.execute(
                            "UPDATE tickets SET priority = %s WHERE id = %s;",
                            (new_priority, ticket_id),
                        )
                        old_priority = str(current).replace("Priority:", "").strip() or "Unknown"
                        change_source = "manager_override" if override else "employee_request"
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                                ticket_id, author_user_id, update_type, message
                            )
                            VALUES (%s, %s, 'priority_change', %s);
                            """,
                            (
                                ticket_id,
                                user["id"],
                                (
                                    f"Manager approved rescoring ({change_source}): "
                                    f"{old_priority} -> {new_priority}. "
                                    f"Request={request_id}."
                                ),
                            ),
                        )
                        relearn_ticket_id = str(ticket_id)
                        relearn_priority = new_priority

                elif req_type == "Rerouting":
                    # Use override department if provided, otherwise use requested
                    if override:
                        new_dept_name = override
                    else:
                        new_dept_name = requested.replace("Dept:", "").strip()
                    cur.execute(
                        "SELECT id FROM departments WHERE name = %s LIMIT 1;",
                        (new_dept_name,),
                    )
                    dept_row = cur.fetchone()
                    if dept_row:
                        cur.execute(
                            "UPDATE tickets SET department_id = %s WHERE id = %s;",
                            (dept_row["id"], ticket_id),
                        )
                        old_dept = str(current).replace("Dept:", "").strip() or "Unknown"
                        change_source = "manager_override" if override else "employee_request"
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                                ticket_id, author_user_id, update_type, message
                            )
                            VALUES (%s, %s, 'department_change', %s);
                            """,
                            (
                                ticket_id,
                                user["id"],
                                (
                                    f"Manager approved rerouting ({change_source}): "
                                    f"{old_dept} -> {new_dept_name}. "
                                    f"Request={request_id}."
                                ),
                            ),
                        )

            # Notifications handled by DB triggers:
            #   trg_notify_manager_approval_decision  → manager self-confirmation
            #   trg_notify_employee_approval_decision → submitting employee

    logger.info(
        "approval_decision | request=%s decision=%s by=%s",
        request_id, decision, user["id"],
    )
    log_application_event(
        service="backend",
        event_key="approval_decision",
        payload={
            "request_id": str(request_id),
            "decision": decision,
            "by": str(user["id"]),
        },
    )
    if decision == "Approved" and relearn_ticket_id and relearn_priority:
        _trigger_priority_relearning(
            ticket_id=relearn_ticket_id,
            approved_priority=relearn_priority,
        )
    return {"ok": True, "requestId": request_id, "decision": decision}


# Manager: Notifications


@app.get("/manager/complaints/{ticket_id}")
@api.get("/manager/complaints/{ticket_id}")
def get_manager_complaint_details(ticket_id: str, user: Dict[str, Any] = Depends(require_manager)):
    # Accepts both ticket_code (CX-…) and UUID
    _stripped = ticket_id.strip()
    if _TICKET_CODE_RE.match(_stripped.upper()):
        ticket_id = _stripped.upper()
    else:
        ticket_id = _sanitize_uuid(_stripped, "ticket_id")
    ticket = fetch_one("""
        SELECT
            t.id AS ticket_id,
            t.ticket_code,
            t.subject,
            t.status,
            t.details,
            t.priority,
            t.final_resolution,
            t.created_at,
            t.priority_assigned_at,
            t.assigned_at,
            t.respond_due_at,
            t.resolve_due_at,
            t.first_response_at,
            t.resolved_at,
            up.full_name AS assignee_name,
            d.name AS department_name
        FROM tickets t
        LEFT JOIN user_profiles up
            ON t.assigned_to_user_id = up.user_id
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.ticket_code = %s OR t.id::text = %s
        LIMIT 1;
    """, (ticket_id, ticket_id))

    if not ticket:
        return {"error": "Ticket not found"}

    # Steps taken
    steps = fetch_all(
        """
        SELECT
          tws.step_no AS step,
          COALESCE(tp.full_name, tu.email) AS technician,
          tws.occurred_at AS occurred_at,
          tws.notes AS notes
        FROM ticket_work_steps tws
        LEFT JOIN users tu ON tu.id = tws.technician_user_id
        LEFT JOIN user_profiles tp ON tp.user_id = tu.id
        WHERE tws.ticket_id = %s
        ORDER BY tws.step_no ASC
        """,
        (ticket["ticket_id"],),
    ) or []

    issue_date = ticket["created_at"].date().isoformat() if ticket.get("created_at") else ""
    resp_base = ticket.get("priority_assigned_at") or ticket.get("assigned_at") or ticket.get("created_at")
    respond_time = minutes_to_label(diff_minutes(ticket.get("respond_due_at"), resp_base))
    resolve_time = minutes_to_label(
        diff_minutes(ticket.get("resolve_due_at"), ticket.get("priority_assigned_at") or ticket.get("created_at"))
    )

    assignee = ticket.get("assignee_name") or "—"
    priority_raw = (ticket.get("priority") or "").lower()
    priority_map = {"low": "Low", "medium": "Medium", "high": "High", "critical": "Critical"}
    priority_text = priority_map.get(priority_raw, ticket.get("priority") or "")

    return {
        "id": ticket["ticket_id"],
        "ticket_code": ticket.get("ticket_code") or "",
        "subject": ticket.get("subject") or "",
        "priority": priority_raw,
        "priorityText": priority_text,
        "status": ticket["status"],
        "assignee": assignee,
        "details": ticket.get("details") or "",
        "issueDate": issue_date,
        "respondTime": respond_time,
        "resolveTime": resolve_time,
        "department": ticket.get("department_name") or "",
        "finalResolution": ticket.get("final_resolution") or "",
        "stepsTaken": [
            {
                "step": s["step"],
                "technician": s["technician"],
                "time": (s["occurred_at"].isoformat() if s.get("occurred_at") else ""),
                "notes": s.get("notes") or "",
            }
            for s in steps
        ],
    }


@api.get("/manager/trends")
def get_manager_trends(
    timeRange: str = Query("This Month"),
    department: str = Query("All Departments"),
    priority: str = Query("All Priorities"),
    user: Dict[str, Any] = Depends(require_manager),
):
    # Validate timeRange against known allowlist
    timeRange = _sanitize_time_range(timeRange)
    # Clamp department and priority to safe lengths (they are used in SQL via
    # parameterised queries, but we still reject absurdly long values early)
    if len(department) > 120:
        raise HTTPException(status_code=400, detail="Invalid department value.")
    if len(priority) > 40:
        raise HTTPException(status_code=400, detail="Invalid priority value.")
    # ── Resolve time window ───────────────────────────────────────────────────
    range_sql = {
        "7d":             "now() - interval '7 days'",
        "Last 7 Days":    "now() - interval '7 days'",
        "30d":            "now() - interval '30 days'",
        "Last 30 Days":   "now() - interval '30 days'",
        "This Month":     "date_trunc('month', now())",
        "Last 3 Months":  "date_trunc('month', now()) - interval '3 months'",
        "Last 6 Months":  "date_trunc('month', now()) - interval '6 months'",
        "Last 12 Months": "date_trunc('month', now()) - interval '12 months'",
        "90d":            "now() - interval '90 days'",
    }
    start_expr   = range_sql.get(timeRange, "date_trunc('month', now())")
    period_start = fetch_one(f"SELECT ({start_expr})::timestamptz AS start")["start"]
    period_end   = fetch_one("SELECT (now() + interval '1 day')::timestamptz AS ts")["ts"]
    window_secs  = (period_end - period_start).total_seconds()
    prev_start   = fetch_one(
        "SELECT (%s::timestamptz - make_interval(secs => %s)) AS start",
        (period_start, window_secs),
    )["start"]

    # Route through analytics_service (materialized views)
    # manager_dept_id scopes Section C (employee performance) to employees who
    # BELONG to this manager's department (user_profiles.department_id), which is
    # the only correct definition.  Without it, employees from other departments
    # who happen to have handled a cross-routed ticket appear in the wrong view.
    manager_dept_id = user.get("department_id")
    if _ANALYTICS_READY:
        try:
            return _analytics.get_trends_data(
                period_start=period_start,
                period_end=period_end,
                prev_start=prev_start,
                department=department,
                priority=priority,
                manager_dept_id=str(manager_dept_id) if manager_dept_id else None,
            )
        except Exception as _svc_err:
            logger.error(
                "analytics_service.get_trends_data failed — falling back to raw SQL. err=%s",
                _svc_err
            )
            # falls through to raw SQL below

    # RAW SQL FALLBACK (used only if analytics_service is unavailable)
    # This is the original implementation kept as a safety net.
    # If you are seeing this path in production logs, the MVs may not be installed.
    # Run: docker exec -i innovacx-db psql -U $POSTGRES_USER -d $POSTGRES_DB < database/scripts/analytics_mvs.sql

    filters = ["t.created_at >= %s", "t.created_at < %s"]
    params  = [period_start, period_end]
    dept_join = "LEFT JOIN departments d ON d.id = t.department_id"
    if department != "All Departments":
        filters.append("d.name = %s")
        params.append(department)
    priority_map_raw = {
        "All Priorities":  None,
        "Low":             ("Low",),
        "Medium":          ("Medium",),
        "High":            ("High",),
        "Critical":        ("Critical",),
        "High & Critical": ("High", "Critical"),
        "Critical only":   ("Critical",),
        "Low & Medium":    ("Low", "Medium"),
    }
    pv = priority_map_raw.get(priority)
    if pv:
        filters.append("t.priority = ANY(%s::ticket_priority[])")
        params.append(list(pv))
    where      = " AND ".join(filters)
    prev_params = [prev_start, period_start] + params[2:]
    prev_where  = where

    complaint_inquiry_daily = fetch_all(
        f"SELECT date_trunc('day', t.created_at)::date AS day, t.ticket_type, COUNT(*) AS count FROM tickets t {dept_join} WHERE {where} GROUP BY 1,2 ORDER BY 1",
        params,
    )
    cid_map: Dict[str, dict] = {}
    for r in complaint_inquiry_daily:
        key = r["day"].isoformat()
        if key not in cid_map:
            cid_map[key] = {"day": key, "complaints": 0, "inquiries": 0}
        if r["ticket_type"] == "Complaint":
            cid_map[key]["complaints"] = r["count"]
        else:
            cid_map[key]["inquiries"] = r["count"]
    complaint_vs_inquiry = sorted(cid_map.values(), key=lambda x: x["day"])

    recurring_heatmap = fetch_all(
        f"""SELECT COALESCE(d.name,'Unassigned') AS department, t.priority, COUNT(*) AS count
            FROM tickets t {dept_join} WHERE {where}
            AND t.created_by_user_id IN (
                SELECT t2.created_by_user_id FROM tickets t2
                WHERE t2.created_by_user_id IS NOT NULL
                GROUP BY t2.created_by_user_id, t2.department_id HAVING COUNT(*) > 1)
            GROUP BY 1,2 ORDER BY 1,2""", params)

    daily_volume_raw = fetch_all(
        f"""SELECT day, count, ROUND(AVG(count) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),1) AS rolling_avg
            FROM (SELECT date_trunc('day',t.created_at)::date AS day, COUNT(*) AS count
                  FROM tickets t {dept_join} WHERE {where} GROUP BY 1) sub ORDER BY day""", params)
    daily_volume_out = [{"day": r["day"].isoformat(), "count": r["count"],
                          "rollingAvg": float(r["rolling_avg"] or 0)} for r in daily_volume_raw]

    sla_overall = fetch_one(
        f"""SELECT COUNT(*) AS total,
            COUNT(*) FILTER (WHERE t.resolve_breached OR t.respond_breached) AS breached,
            COUNT(*) FILTER (WHERE t.status='Escalated') AS escalated,
            ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0)
                  FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond_mins,
            ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0)
                  FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve_mins
            FROM tickets t {dept_join} WHERE {where}""", params) or {}

    total_t         = sla_overall.get("total") or 0
    breached_t      = sla_overall.get("breached") or 0
    escalated_t     = sla_overall.get("escalated") or 0
    breach_rate     = round(breached_t / total_t * 100, 1) if total_t else 0
    escalation_rate = round(escalated_t / total_t * 100, 1) if total_t else 0
    avg_respond_mins = float(sla_overall.get("avg_respond_mins") or 0)
    avg_resolve_mins = float(sla_overall.get("avg_resolve_mins") or 0)
    sla_targets = {"respond":{"Critical":30,"High":60,"Medium":180,"Low":360},
                   "resolve":{"Critical":360,"High":1080,"Medium":2880,"Low":4320}}

    prev_sla       = fetch_one(f"SELECT COUNT(*) AS total, COUNT(*) FILTER(WHERE t.resolve_breached OR t.respond_breached) AS breached FROM tickets t {dept_join} WHERE {prev_where}", prev_params) or {}
    prev_total     = prev_sla.get("total") or 0
    prev_breached  = prev_sla.get("breached") or 0
    prev_breach_rate = round(prev_breached / prev_total * 100, 1) if prev_total else 0

    breach_by_dept = fetch_all(f"SELECT COALESCE(d.name,'Unassigned') AS department, t.priority, COUNT(*) AS total, COUNT(*) FILTER(WHERE t.resolve_breached OR t.respond_breached) AS breached FROM tickets t {dept_join} WHERE {where} GROUP BY 1,2 ORDER BY 1,2", params)
    dept_breach_map: Dict[str, dict] = {}
    for r in breach_by_dept:
        dept = r["department"]
        if dept not in dept_breach_map:
            dept_breach_map[dept] = {"department":dept,"total":0,"breached":0,"Critical":0,"High":0,"Medium":0,"Low":0,"Critical_total":0,"High_total":0,"Medium_total":0,"Low_total":0}
        p2 = r["priority"]
        dept_breach_map[dept]["total"] += r["total"]
        dept_breach_map[dept]["breached"] += r["breached"]
        if p2 in ("Critical","High","Medium","Low"):
            dept_breach_map[dept][f"{p2}_total"] += r["total"]
            dept_breach_map[dept][p2] += r["breached"]
    breach_by_dept_out = sorted([{"department":dept,"total":v["total"],"breachRate":round(v["breached"]/v["total"]*100,1) if v["total"] else 0,"Critical":round(v["Critical"]/v["Critical_total"]*100,1) if v["Critical_total"] else 0,"High":round(v["High"]/v["High_total"]*100,1) if v["High_total"] else 0,"Medium":round(v["Medium"]/v["Medium_total"]*100,1) if v["Medium_total"] else 0,"Low":round(v["Low"]/v["Low_total"]*100,1) if v["Low_total"] else 0} for dept,v in dept_breach_map.items()], key=lambda x: -x["breachRate"])

    breach_timeline_raw = fetch_all(f"SELECT date_trunc('day',t.created_at)::date AS day, t.priority, COUNT(*) AS total, COUNT(*) FILTER(WHERE t.resolve_breached OR t.respond_breached) AS breached FROM tickets t {dept_join} WHERE {where} GROUP BY 1,2 ORDER BY 1,2", params)
    bt_map: Dict[str, dict] = {}
    for r in breach_timeline_raw:
        key = r["day"].isoformat()
        if key not in bt_map:
            bt_map[key]={"day":key,"total":0,"Critical":0,"High":0,"Medium":0,"Low":0}
        bt_map[key]["total"]+=r["total"]
        if r["priority"] in ("Critical","High","Medium","Low"):
            bt_map[key][r["priority"]]+=r["breached"]
    breach_timeline_out = sorted(bt_map.values(), key=lambda x: x["day"])

    escalation_by_dept_raw = fetch_all(f"SELECT COALESCE(d.name,'Unassigned') AS department, COUNT(*) AS total, COUNT(*) FILTER(WHERE t.status='Escalated') AS escalated FROM tickets t {dept_join} WHERE {where} GROUP BY 1 ORDER BY escalated DESC", params)
    escalation_by_dept_out = [{"department":r["department"],"total":r["total"],"escalated":r["escalated"],"rate":round(r["escalated"]/r["total"]*100,1) if r["total"] else 0} for r in escalation_by_dept_raw]

    time_by_priority_raw = fetch_all(f"SELECT t.priority, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond, ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve, COUNT(*) AS total FROM tickets t {dept_join} WHERE {where} GROUP BY 1 ORDER BY CASE t.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END", params)
    time_by_priority_out = [{"priority":r["priority"],"avgRespond":float(r["avg_respond"] or 0),"avgResolve":float(r["avg_resolve"] or 0),"targetRespond":sla_targets["respond"].get(r["priority"],360),"targetResolve":sla_targets["resolve"].get(r["priority"],4320),"total":r["total"]} for r in time_by_priority_raw]

    # Section C: scope employee rows to THIS manager's department only
    # Use user_profiles.department_id (employee's HOME dept) not ticket's dept.
    # This matches the analytics_service.get_section_c() strategy.
    _fallback_dept_id = user.get("department_id")
    if _fallback_dept_id:
        _emp_dept_clause = " AND up.department_id = %s::uuid"
        _emp_params = params + [str(_fallback_dept_id)]
        _acc_dept_clause = " AND up.department_id = %s::uuid"
        _acc_params = [period_start, period_end, str(_fallback_dept_id)]
    else:
        _emp_dept_clause = ""
        _emp_params = params
        _acc_dept_clause = ""
        _acc_params = [period_start, period_end]

    employee_perf = fetch_all(f"SELECT up.full_name AS name, up.employee_code AS emp_id, up.job_title AS role, COUNT(t.id) AS total, COUNT(t.id) FILTER(WHERE t.status='Resolved') AS resolved, COUNT(t.id) FILTER(WHERE t.resolve_breached OR t.respond_breached) AS breached, ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve_mins, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond_mins FROM tickets t JOIN user_profiles up ON up.user_id=t.assigned_to_user_id JOIN users u ON u.id=t.assigned_to_user_id LEFT JOIN departments d ON d.id=t.department_id WHERE u.role='employee' AND {where}{_emp_dept_clause} GROUP BY up.full_name,up.employee_code,up.job_title ORDER BY resolved DESC", _emp_params)
    company_avg = fetch_one(f"SELECT ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond, COUNT(*) FILTER(WHERE t.resolve_breached OR t.respond_breached)::float/NULLIF(COUNT(*),0)*100 AS breach_rate FROM tickets t {dept_join} WHERE {where}", params) or {}
    acceptance_rows = fetch_all(f"SELECT up.full_name AS name, COUNT(*) AS total, COUNT(*) FILTER(WHERE sru.decision='accepted') AS accepted, COUNT(*) FILTER(WHERE sru.decision='declined_custom') AS declined FROM suggested_resolution_usage sru JOIN tickets t ON t.id=sru.ticket_id JOIN user_profiles up ON up.user_id=sru.employee_user_id WHERE sru.employee_user_id IS NOT NULL AND sru.decision IS NOT NULL AND t.created_at>=%s AND t.created_at<%s{_acc_dept_clause} GROUP BY up.full_name", _acc_params)
    acceptance_map = {r["name"]:{"total":r["total"],"accepted":r["accepted"],"declined":r["declined"],"rate":round(r["accepted"]/r["total"]*100,1) if r["total"] else 0} for r in acceptance_rows}
    rescore_rows = fetch_all(f"SELECT up.full_name AS name, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority) AS rescored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority AND((t.model_priority='Low' AND t.priority IN('Medium','High','Critical'))OR(t.model_priority='Medium' AND t.priority IN('High','Critical'))OR(t.model_priority='High' AND t.priority='Critical'))) AS upscored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority AND((t.model_priority='Critical' AND t.priority IN('Low','Medium','High'))OR(t.model_priority='High' AND t.priority IN('Low','Medium'))OR(t.model_priority='Medium' AND t.priority='Low'))) AS downscored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL) AS total_with_model FROM tickets t JOIN user_profiles up ON up.user_id=t.assigned_to_user_id JOIN users u ON u.id=t.assigned_to_user_id LEFT JOIN departments d ON d.id=t.department_id WHERE u.role='employee' AND {where}{_emp_dept_clause} GROUP BY up.full_name", _emp_params)
    rescore_map = {r["name"]:{"rescored":r["rescored"],"upscored":r["upscored"],"downscored":r["downscored"],"totalWithModel":r["total_with_model"],"rescoreRate":round(r["rescored"]/r["total_with_model"]*100,1) if r["total_with_model"] else 0} for r in rescore_rows}

    co_breach=float(company_avg.get("breach_rate") or 0)
    co_resolve=float(company_avg.get("avg_resolve") or 0)
    co_respond=float(company_avg.get("avg_respond") or 0)
    employee_out = []
    for e in employee_perf:
        name=e["name"]
        total=e["total"] or 0
        brate=round(e["breached"]/total*100,1) if total else 0
        acc=acceptance_map.get(name,{"rate":None,"accepted":0,"declined":0,"total":0})
        rsc=rescore_map.get(name,{"rescoreRate":0,"upscored":0,"downscored":0})
        employee_out.append({"name":name,"empId":e["emp_id"],"role":e["role"],"ticketsHandled":total,"resolved":e["resolved"] or 0,"breached":e["breached"] or 0,"breachRate":brate,"avgResolveMins":float(e["avg_resolve_mins"] or 0),"avgRespondMins":float(e["avg_respond_mins"] or 0),"companyBreachRate":round(co_breach,1),"companyResolveMins":round(co_resolve,1),"companyRespondMins":round(co_respond,1),"acceptanceRate":acc["rate"],"acceptedCount":acc["accepted"],"declinedCount":acc["declined"],"rescoreRate":rsc["rescoreRate"],"upscored":rsc["upscored"],"downscored":rsc["downscored"],"alertLowVolume":total<5,"alertHighBreach":brate>10,"alertSlowResolve":float(e["avg_resolve_mins"] or 0)>480,"alertLowAcceptance":acc["rate"] is not None and acc["rate"]<50,"alertHighRescore":rsc["rescoreRate"]>30})
    team_accept_avg = round(sum(e["acceptanceRate"] for e in employee_out if e["acceptanceRate"] is not None)/max(sum(1 for e in employee_out if e["acceptanceRate"] is not None),1),1)

    top_cat_row = fetch_one(f"SELECT COALESCE(d.name,'Unassigned') AS name, COUNT(*) AS count FROM tickets t {dept_join} WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 1", params)
    top_category = top_cat_row["name"] if top_cat_row else "—"
    repeat_row = fetch_one(f"SELECT COUNT(*) AS count FROM (SELECT t.created_by_user_id FROM tickets t {dept_join} WHERE {where} GROUP BY t.created_by_user_id HAVING COUNT(*)>1) r", params)
    repeat_pct = round(repeat_row["count"]/total_t*100) if total_t else 0
    bars_legacy = fetch_all(f"SELECT to_char(t.created_at,'Mon') AS label, COUNT(*) AS value FROM tickets t {dept_join} WHERE {where} GROUP BY label, date_trunc('month',t.created_at) ORDER BY date_trunc('month',t.created_at)", params)
    categories_legacy = fetch_all(f"SELECT COALESCE(d.name,'Unassigned') AS name, COUNT(*)*100.0/SUM(COUNT(*)) OVER() AS pct FROM tickets t {dept_join} WHERE {where} GROUP BY 1", params)
    table_legacy = fetch_all(f"SELECT to_char(t.created_at,'Month') AS month, COUNT(*) AS total, COUNT(*) FILTER(WHERE t.status='Resolved') AS resolved, ROUND(COUNT(*) FILTER(WHERE t.resolved_at<=t.resolve_due_at AND t.first_response_at IS NOT NULL)*100.0/NULLIF(COUNT(*),0)) AS within_sla, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60)) AS avg_response, ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/86400),1) AS avg_resolve FROM tickets t {dept_join} WHERE {where} GROUP BY date_trunc('month',t.created_at),month ORDER BY date_trunc('month',t.created_at)", params)

    return {
        "kpis":{"complaints":total_t,"sla":f"{100-breach_rate}%","response":f"{round(avg_respond_mins)} mins","resolve":f"{round(avg_resolve_mins/60,1)} hrs","topCategory":top_category,"repeat":f"{repeat_pct}%"},
        "bars": bars_legacy, "categories": categories_legacy, "table": table_legacy,
        "sectionA":{"complaintVsInquiry":complaint_vs_inquiry,"dailyVolume":daily_volume_out,"recurringHeatmap":recurring_heatmap},
        "sectionB":{"kpis":{"totalTickets":total_t,"breachRate":breach_rate,"prevBreachRate":prev_breach_rate,"breachDelta":round(breach_rate-prev_breach_rate,1),"escalationRate":escalation_rate,"avgRespondMins":round(avg_respond_mins,1),"avgResolveMins":round(avg_resolve_mins,1),"avgRespondHrs":round(avg_respond_mins/60,2),"avgResolveHrs":round(avg_resolve_mins/60,2)},"breachByDept":breach_by_dept_out,"breachTimeline":breach_timeline_out,"escalationByDept":escalation_by_dept_out,"timeByPriority":time_by_priority_out},
        "sectionC":{"employees":employee_out,"teamAcceptAvg":team_accept_avg,"companyBreachRate":round(co_breach,1)},
    }
@api.get("/manager/notifications")
def manager_notifications(
    limit: int = Query(default=200, ge=1, le=500),
    only_unread: bool = Query(default=False),
    user: Dict[str, Any] = Depends(require_manager),   # ← use Depends, not Header
):
    user_id = user["id"]
    dept_id = user.get("department_id")

    # Two-layer defence:
    # Layer 1 (generation): backend now sets requested_to_user_id on approval_requests
    #   so the DB trigger only inserts 1 notification for the correct dept manager.
    # Layer 2 (retrieval): even for notifications generated before this fix, we
    #   additionally filter at query time — ticket-linked notifications are only
    #   returned if their ticket.department_id matches this manager's department.
    #   System/report notifications (ticket_id IS NULL) always pass through.
    if dept_id:
        rows = fetch_all(
            """
            SELECT
              n.id::text           AS "id",
              n.type::text         AS "type",
              n.title              AS "title",
              n.message            AS "message",
              n.priority::text     AS "priority",
              t.id::text           AS "ticketId",
              t.ticket_code        AS "ticketCode",
              n.report_id          AS "reportId",
              n.read               AS "read",
              n.created_at         AS "timestamp"
            FROM notifications n
            LEFT JOIN tickets t ON t.id = n.ticket_id
            WHERE n.user_id = %s
              AND (%s = FALSE OR n.read = FALSE)
              AND (
                n.ticket_id IS NULL
                OR t.department_id = %s
              )
            ORDER BY n.created_at DESC
            LIMIT %s;
            """,
            (user_id, only_unread, dept_id, limit),
        )
        unread_row = fetch_one(
            """
            SELECT COUNT(*)::int AS unread
            FROM notifications n
            LEFT JOIN tickets t ON t.id = n.ticket_id
            WHERE n.user_id = %s
              AND n.read = FALSE
              AND (n.ticket_id IS NULL OR t.department_id = %s);
            """,
            (user_id, dept_id),
        ) or {"unread": 0}
    else:
        # Unassigned manager: graceful fallback — return all their notifications
        rows = fetch_all(
            """
            SELECT
              n.id::text           AS "id",
              n.type::text         AS "type",
              n.title              AS "title",
              n.message            AS "message",
              n.priority::text     AS "priority",
              t.id::text           AS "ticketId",
              t.ticket_code        AS "ticketCode",
              n.report_id          AS "reportId",
              n.read               AS "read",
              n.created_at         AS "timestamp"
            FROM notifications n
            LEFT JOIN tickets t ON t.id = n.ticket_id
            WHERE n.user_id = %s
              AND (%s = FALSE OR n.read = FALSE)
            ORDER BY n.created_at DESC
            LIMIT %s;
            """,
            (user_id, only_unread, limit),
        )
        unread_row = fetch_one(
            "SELECT COUNT(*)::int AS unread FROM notifications WHERE user_id = %s AND read = FALSE;",
            (user_id,),
        ) or {"unread": 0}

    notifications = []
    for r in rows:
        ts = r.get("timestamp")
        notifications.append({
            "id": r.get("id"),
            "type": r.get("type"),
            "title": r.get("title"),
            "message": r.get("message"),
            "priority": r.get("priority"),
            "ticketId": r.get("ticketId"),
            "ticketCode": r.get("ticketCode"),
            "reportId": r.get("reportId"),
            "read": bool(r.get("read")),
            "timestamp": ts.isoformat() if ts else None,
        })

    return {"unreadCount": int(unread_row.get("unread") or 0), "notifications": notifications}

@api.post("/manager/notifications/{notification_id}/read")
def manager_notification_mark_read(
    notification_id: str,
    user: Dict[str, Any] = Depends(require_manager),
    _csrf: None = Depends(require_csrf),
):
    import uuid
    try:
        uuid.UUID(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification id")

    updated = execute(
        "UPDATE notifications SET read = TRUE WHERE id = %s::uuid AND user_id = %s;",
        (notification_id, user["id"]),
    )
    if updated <= 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}

@api.post("/manager/notifications/read-all")
def manager_notifications_mark_all_read(
    user: Dict[str, Any] = Depends(require_manager),
    _csrf: None = Depends(require_csrf),
):
    execute(
        "UPDATE notifications SET read = TRUE WHERE user_id = %s AND read = FALSE;",
        (user["id"],),
    )
    return {"ok": True}


@api.get("/manager/routing-review")
def get_routing_review_queue(
    status_filter: str = Query(default="Pending"),
    user: Dict[str, Any] = Depends(require_manager),
):
    status_filter = _sanitize_status_filter(status_filter)
    manager_dept_row = fetch_one(
        """
        SELECT d.name AS department_name
        FROM user_profiles up
        LEFT JOIN departments d ON d.id = up.department_id
        WHERE up.user_id = %s
        LIMIT 1
        """,
        (user["id"],),
    ) or {}
    return get_routing_review_payload(
        fetch_all=fetch_all,
        status_filter=status_filter,
        manager_department_name=manager_dept_row.get("department_name"),
    )


class RoutingReviewDecisionRequest(BaseModel):
    decision:            Optional[str] = None
    approved_department: Optional[str] = None



@api.get("/manager/routing-review/{review_id}")
def get_routing_review_item(
    review_id: str,
    user: Dict[str, Any] = Depends(require_manager),
):
    """Fetch a single routing review item by its UUID."""
    review_id = _sanitize_uuid(review_id, "review_id")
    manager_dept_row = fetch_one(
        """
        SELECT d.name AS department_name
        FROM user_profiles up
        LEFT JOIN departments d ON d.id = up.department_id
        WHERE up.user_id = %s
        LIMIT 1
        """,
        (user["id"],),
    ) or {}
    manager_department_name = manager_dept_row.get("department_name")
    if not manager_department_name:
        raise HTTPException(status_code=403, detail="Manager is not assigned to a department")

    row = fetch_one(
        """
        SELECT
          dr.id::text                          AS "reviewId",
          CASE
            WHEN dr.routed_by = 'manager_denied' THEN 'Denied'
            WHEN dr.final_department IS NULL    THEN 'Pending'
            WHEN dr.routed_by = 'manager'       THEN 'Overridden'
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
          up.full_name                         AS "decidedBy"
        FROM department_routing dr
        JOIN tickets t ON t.id = dr.ticket_id
        LEFT JOIN departments d ON d.id = t.department_id
        LEFT JOIN user_profiles up ON up.user_id = dr.manager_id
        WHERE dr.id::text = %s
          AND dr.is_confident = FALSE
          AND (
            LOWER(dr.suggested_department) = LOWER(%s)
            OR NOT EXISTS (
              SELECT 1
              FROM users u2
              JOIN user_profiles up2 ON up2.user_id = u2.id
              JOIN departments d2 ON d2.id = up2.department_id
              WHERE u2.role = 'manager'
                AND LOWER(d2.name) = LOWER(dr.suggested_department)
            )
          )
        LIMIT 1
        """,
        (review_id, manager_department_name),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Routing review item not found")

    return {
        **{k: v for k, v in row.items() if k not in ("decidedAt", "createdAt", "confidencePct")},
        "confidencePct": float(row.get("confidencePct") or 0),
        "decidedAt":     row["decidedAt"].isoformat() if row.get("decidedAt") else None,
        "createdAt":     row["createdAt"].isoformat() if row.get("createdAt") else None,
    }

@api.patch("/manager/routing-review/{review_id}")
def decide_routing_review(
    review_id: str,
    body: RoutingReviewDecisionRequest,
    user: Dict[str, Any] = Depends(require_manager),
    _csrf: None = Depends(require_csrf),
):
    review_id = _sanitize_uuid(review_id, "review_id")
    manager_dept_row = fetch_one(
        """
        SELECT d.name AS department_name
        FROM user_profiles up
        LEFT JOIN departments d ON d.id = up.department_id
        WHERE up.user_id = %s
        LIMIT 1
        """,
        (user["id"],),
    ) or {}
    return decide_routing_review_service(
        review_id=review_id,
        decision=body.decision,
        approved_department=body.approved_department,
        user=user,
        manager_department_name=manager_dept_row.get("department_name"),
        fetch_one=fetch_one,
        db_connect=db_connect,
        auto_assign_ticket_if_needed=auto_assign_ticket_if_needed,
        insert_notification=_insert_notification,
        logger=logger,
    )

# Operator Notifications

@api.get("/operator/notifications")
def operator_notifications(
    limit: int = Query(default=200, ge=1, le=500),
    only_unread: bool = Query(default=False),
    user: Dict[str, Any] = Depends(require_operator),
):
    user_id = user["id"]

    rows = fetch_all(
        """
        SELECT
          n.id::text           AS "id",
          n.type::text         AS "type",
          n.title              AS "title",
          n.message            AS "message",
          n.priority::text     AS "priority",
          t.ticket_code        AS "ticketId",
          n.report_id          AS "reportId",
          n.read               AS "read",
          n.created_at         AS "timestamp"
        FROM notifications n
        LEFT JOIN tickets t ON t.id = n.ticket_id
        WHERE n.user_id = %s
          AND (%s = FALSE OR n.read = FALSE)
        ORDER BY n.created_at DESC
        LIMIT %s;
        """,
        (user_id, only_unread, limit),
    )

    unread_row = fetch_one(
        "SELECT COUNT(*)::int AS unread FROM notifications WHERE user_id = %s AND read = FALSE;",
        (user_id,),
    ) or {"unread": 0}

    notifications = []
    for r in rows:
        ts = r.get("timestamp")
        notifications.append({
            "id": r.get("id"),
            "type": r.get("type"),
            "title": r.get("title"),
            "message": r.get("message"),
            "priority": r.get("priority"),
            "ticketId": r.get("ticketId"),
            "reportId": r.get("reportId"),
            "read": bool(r.get("read")),
            "timestamp": ts.isoformat() if ts else None,
        })

    return {"unreadCount": int(unread_row.get("unread") or 0), "notifications": notifications}


@api.post("/operator/notifications/{notification_id}/read")
def operator_notification_mark_read(
    notification_id: str,
    user: Dict[str, Any] = Depends(require_operator),
    _csrf: None = Depends(require_csrf),
):
    import uuid
    try:
        uuid.UUID(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification id")

    updated = execute(
        "UPDATE notifications SET read = TRUE WHERE id = %s::uuid AND user_id = %s;",
        (notification_id, user["id"]),
    )
    if updated <= 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@api.post("/operator/notifications/read-all")
def operator_notifications_mark_all_read(
    user: Dict[str, Any] = Depends(require_operator),
    _csrf: None = Depends(require_csrf),
):
    execute(
        "UPDATE notifications SET read = TRUE WHERE user_id = %s AND read = FALSE;",
        (user["id"],),
    )
    return {"ok": True}

# Internal Orchestrator Endpoint (no JWT — Docker-network only)

class OrchestratorComplaintRequest(BaseModel):
    ticket_id: Optional[str] = None
    subject: Optional[str] = None
    transcript: Optional[str] = None
    asset_type: Optional[str] = None
    sentiment: Optional[float] = None
    audio_sentiment: Optional[float] = None
    priority: Optional[int] = None
    department: Optional[str] = None
    keywords: Optional[List[str]] = []
    label: Optional[str] = None
    status: Optional[str] = None
    classification_confidence: Optional[float] = None
    created_by_user_id: Optional[str] = None
    ticket_source: Optional[str] = None
    suggested_resolution: Optional[str] = None
    suggested_resolution_model: Optional[str] = None


class ChatbotProxyRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None

    from pydantic import validator

    @validator("message")
    def message_length(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("message must not be empty.")
        if len(v) > 4000:
            raise ValueError("message exceeds maximum length of 4000 characters.")
        return v

    @validator("user_id")
    def user_id_format(cls, v):
        import uuid as _u
        try:
            return str(_u.UUID(str(v).strip()))
        except (ValueError, AttributeError):
            raise ValueError("user_id must be a valid UUID.")

    @validator("session_id", pre=True, always=True)
    def session_id_length(cls, v):
        if v is not None and len(str(v)) > 128:
            raise ValueError("session_id exceeds maximum length of 128 characters.")
        return v


@api.post("/complaints")
def create_orchestrator_complaint(body: OrchestratorComplaintRequest, _key: None = Depends(require_internal_key)):
    """
    Internal endpoint called by the orchestrator service.
    Creates a ticket on behalf of the submitting user (or any active customer
    as fallback). No JWT required — relies on Docker-network isolation.
    """
    from api.ticket_creation_gate import create_ticket_via_gate
    # Resolve the user who submitted the ticket
    row = None
    if body.created_by_user_id:
        row = fetch_one(
            "SELECT id FROM users WHERE id = %s::uuid LIMIT 1",
            (body.created_by_user_id,),
        )
    if not row:
        # Fallback: any active customer
        row = fetch_one(
            "SELECT id FROM users WHERE role = 'customer' AND is_active = TRUE ORDER BY created_at ASC LIMIT 1",
            (),
        )
    if not row:
        raise HTTPException(
            status_code=503,
            detail="No usable customer account found to create ticket. "
                   "Ensure at least one active customer user exists.",
        )

    incoming_ticket_code = (body.ticket_id or "").strip() or None

    priority_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
    priority_label = priority_map.get(body.priority) if body.priority is not None else None

    label = (body.label or "").strip().lower() or None
    ticket_type = "Inquiry" if label == "inquiry" else ("Complaint" if label else None)
    requested_asset_type = (body.asset_type or "").strip() or None
    requested_department = (body.department or "").strip() or None
    routing_confidence_raw = body.classification_confidence
    if not requested_department and body.priority is not None:
        inferred_department, inferred_confidence = _predict_department_from_details(body.transcript or "")
        requested_department = inferred_department
        if routing_confidence_raw is None:
            routing_confidence_raw = inferred_confidence
    routing_meta = build_routing_meta(
        requested_department=requested_department,
        classification_confidence=routing_confidence_raw,
        threshold=ROUTING_CONFIDENCE_THRESHOLD,
    )
    has_routing_decision = routing_meta["has_routing_decision"]
    routing_confidence_pct = routing_meta["routing_confidence_pct"]
    routing_is_confident = routing_meta["routing_is_confident"]
    normalized_status = (body.status or "").strip() or None
    allowed_statuses = {
        "Open",
        "In Progress",
        "Assigned",
        "Escalated",
        "Overdue",
        "Resolved",
        "Review",
    }
    if normalized_status and normalized_status not in allowed_statuses:
        raise HTTPException(status_code=422, detail=f"Invalid status '{normalized_status}'")

    with db_connect() as conn:
        with conn.cursor() as cur:
            department_id = None
            if requested_department:
                cur.execute(
                    "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s) LIMIT 1",
                    (requested_department,),
                )
                dept_row = cur.fetchone()
                if dept_row:
                    department_id = dept_row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO departments (name)
                        VALUES (%s)
                        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                        RETURNING id;
                        """,
                        (requested_department,),
                    )
                    department_id = cur.fetchone()[0]

            if not incoming_ticket_code:
                # No ticket_id supplied → create a new ticket
                effective_department_id = department_id if (not has_routing_decision or routing_is_confident) else None
                effective_status = normalized_status or "Open"
                if has_routing_decision and routing_is_confident:
                    effective_status = "Assigned"
                elif has_routing_decision and not routing_is_confident:
                    effective_status = "Open"
                created = create_ticket_via_gate(
                    cur,
                    created_by_user_id=str(row["id"]),
                    ticket_type=ticket_type,
                    subject=(body.transcript or "")[:120].strip() or "Customer submission",
                    details=body.transcript or "",
                    priority=priority_label,
                    status=effective_status,
                    ticket_source="form",
                    department_id=effective_department_id,
                    sentiment_score=body.sentiment,
                    sentiment_label="orchestrator" if body.sentiment is not None else None,
                    model_priority=priority_label,
                    model_department_id=effective_department_id,
                    model_confidence=routing_confidence_raw,
                )
                cur.execute(
                    """
                    INSERT INTO ticket_updates (
                      ticket_id, author_user_id, update_type, message, to_status
                    )
                    VALUES (%s, %s, 'status_change', %s, %s);
                    """,
                    (
                        created["id"],
                        row["id"],
                        "Ticket created by orchestrator pipeline.",
                        created["status"],
                    ),
                )
                if created.get("priority"):
                    cur.execute(
                        """
                        INSERT INTO ticket_updates (
                          ticket_id, author_user_id, update_type, message
                        )
                        VALUES (%s, %s, 'priority_change', %s);
                        """,
                        (
                            created["id"],
                            row["id"],
                            f"Priority set to {created['priority']} by orchestrator.",
                        ),
                    )
                return {
                    "ticket_id":   str(created["id"]),
                    "ticket_code": created["ticket_code"],
                    "status":      created["status"],
                    "priority":    created["priority"],
                    "asset_type":  None,
                    "department":  (requested_department if routing_is_confident else None),
                    "priority_assigned_at": created["priority_assigned_at"].isoformat() if created.get("priority_assigned_at") else None,
                    "respond_due_at":       created["respond_due_at"].isoformat() if created.get("respond_due_at") else None,
                    "resolve_due_at":       created["resolve_due_at"].isoformat() if created.get("resolve_due_at") else None,
                }

            # ticket_id supplied → update existing ticket
            cur.execute(
                "SELECT id, priority_assigned_at, department_id, status, priority FROM tickets WHERE ticket_code = %s LIMIT 1",
                (incoming_ticket_code,),
            )
            existing = cur.fetchone()
            if existing:
                    existing_department_id = existing[2]
                    previous_status = existing[3]
                    previous_priority = existing[4]
                    # Never rewrite subject to synthetic placeholders like
                    # "[Dept] Automated complaint" on orchestrator updates.
                    subject_update = (body.subject or "").strip() or None

                    details_update = body.transcript if body.transcript else None
                    base_status = normalized_status or "Open"
                    if has_routing_decision:
                        effective_department_id = department_id if routing_is_confident else None
                        effective_status = "Assigned" if routing_is_confident else "Open"
                    else:
                        effective_department_id = department_id or existing_department_id
                        effective_status = base_status
                    now_utc = None
                    sentiment_label_update = "orchestrator" if body.sentiment is not None else None

                    cur.execute(
                        """
                        UPDATE tickets
                        SET
                          ticket_type = COALESCE(%s, ticket_type),
                          subject = COALESCE(%s, subject),
                          details = COALESCE(%s, details),
                          asset_type = COALESCE(%s, asset_type),
                          priority = COALESCE(%s, priority),
                          status = COALESCE(%s, status),
                          department_id = COALESCE(%s, department_id),
                          sentiment_score = COALESCE(%s, sentiment_score),
                          sentiment_label = COALESCE(%s, sentiment_label),
                          model_priority = COALESCE(%s, model_priority),
                          model_department_id = COALESCE(%s, model_department_id),
                          model_confidence = COALESCE(%s, model_confidence),
                          suggested_resolution = COALESCE(%s, suggested_resolution),
                          suggested_resolution_model = COALESCE(%s, suggested_resolution_model),
                          suggested_resolution_generated_at = CASE
                            WHEN %s IS NOT NULL THEN now()
                            ELSE suggested_resolution_generated_at
                          END,
                          priority_assigned_at = COALESCE(%s, priority_assigned_at)
                        WHERE ticket_code = %s
                        RETURNING ticket_code, status, priority, asset_type, priority_assigned_at, respond_due_at, resolve_due_at, department_id;
                        """,
                        (
                            ticket_type,
                            subject_update,
                            details_update,
                            requested_asset_type,
                            priority_label,
                            effective_status,
                            effective_department_id,
                            body.sentiment,
                            sentiment_label_update,
                            priority_label,
                            effective_department_id,
                            routing_confidence_raw,
                            (body.suggested_resolution or "").strip() or None,
                            (body.suggested_resolution_model or "").strip() or None,
                            (body.suggested_resolution or "").strip() or None,
                            now_utc,
                            incoming_ticket_code,
                        ),
                    )
                    updated = cur.fetchone()
                    if has_routing_decision and not routing_is_confident:
                        cur.execute(
                            """
                            UPDATE tickets
                            SET
                              department_id = NULL,
                              status = CASE
                                WHEN status IN ('Resolved', 'Escalated', 'Overdue') THEN status
                                ELSE 'Open'
                              END,
                              updated_at = now()
                            WHERE ticket_code = %s
                            RETURNING ticket_code, status, priority, asset_type, priority_assigned_at, respond_due_at, resolve_due_at, department_id;
                            """,
                            (incoming_ticket_code,),
                        )
                        updated = cur.fetchone()
                    if previous_status != updated[1]:
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                              ticket_id, author_user_id, update_type, message, from_status, to_status
                            )
                            VALUES (%s, %s, 'status_change', %s, %s, %s);
                            """,
                            (
                                existing[0],
                                row["id"],
                                f"Orchestrator updated status from {previous_status or 'Unknown'} to {updated[1]}.",
                                previous_status,
                                updated[1],
                            ),
                        )
                    if previous_priority != updated[2] and updated[2]:
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                              ticket_id, author_user_id, update_type, message
                            )
                            VALUES (%s, %s, 'priority_change', %s);
                            """,
                            (
                                existing[0],
                                row["id"],
                                f"Orchestrator updated priority from {previous_priority or 'Unknown'} to {updated[2]}.",
                            ),
                        )
                    if existing_department_id != updated[7]:
                        old_dept_name = "Unassigned"
                        new_dept_name = "Unassigned"
                        if existing_department_id:
                            cur.execute("SELECT name FROM departments WHERE id = %s LIMIT 1;", (existing_department_id,))
                            old_dept_name = (cur.fetchone() or [old_dept_name])[0]
                        if updated[7]:
                            cur.execute("SELECT name FROM departments WHERE id = %s LIMIT 1;", (updated[7],))
                            new_dept_name = (cur.fetchone() or [new_dept_name])[0]
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                              ticket_id, author_user_id, update_type, message
                            )
                            VALUES (%s, %s, 'department_change', %s);
                            """,
                            (
                                existing[0],
                                row["id"],
                                f"Orchestrator updated department from {old_dept_name} to {new_dept_name}.",
                            ),
                        )
                    logger.info(
                        "orchestrator_ticket_update | ticket_id=%s status=%s priority=%s asset_type=%s department=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                        updated[0],
                        updated[1],
                        updated[2],
                        updated[3],
                        (requested_department if routing_is_confident else None),
                        updated[4],
                        updated[5],
                        updated[6],
                    )
                    log_application_event(
                        service="backend",
                        event_key="orchestrator_ticket_update",
                        ticket_id=existing[0],
                        ticket_code=updated[0],
                        payload={
                            "status": updated[1],
                            "priority": updated[2],
                            "asset_type": updated[3],
                            "department": requested_department if routing_is_confident else None,
                            "priority_assigned_at": updated[4],
                            "respond_due_at": updated[5],
                            "resolve_due_at": updated[6],
                        },
                        cur=cur,
                    )

                    auto_assigned_user_id = auto_assign_ticket_if_needed(
                        cur,
                        ticket_code=updated[0],
                        status=updated[1],
                        department_id=effective_department_id,
                        priority=updated[2],
                    )
                    if auto_assigned_user_id:
                        logger.info(
                            "auto_assign | ticket_id=%s assignee=%s dept_id=%s priority=%s",
                            updated[0],
                            auto_assigned_user_id,
                            effective_department_id,
                            updated[2],
                        )
                    
                    queued_for_review = False
                    if has_routing_decision and existing:
                        ticket_uuid = str(existing[0])
                        queued_for_review = record_department_routing_decision(
                            cur,
                            ticket_uuid=ticket_uuid,
                            ticket_code=updated[0],
                            suggested_department=requested_department,
                            routing_confidence_pct=float(routing_confidence_pct),
                            routing_is_confident=routing_is_confident,
                            department_id=str(department_id) if department_id else None,
                            priority=updated[2],
                            insert_notification=_insert_notification,
                            logger=logger,
                        )

                    return {
                        "ticket_id":        str(existing[0]),
                        "ticket_code":      updated[0],
                        "status":           updated[1],
                        "priority":         updated[2],
                        "asset_type":       updated[3],
                        "department":       (requested_department if routing_is_confident else None),
                        "queued_for_review": queued_for_review,
                        "priority_assigned_at": updated[4].isoformat() if updated[4] else None,
                        "respond_due_at":   updated[5].isoformat() if updated[5] else None,
                        "resolve_due_at":   updated[6].isoformat() if updated[6] else None,
                    }

            # Create new ticket via central ticket creation gate when no ticket_id
            # was supplied or when supplied ticket_id is not found.
            requester_user_id = str(body.created_by_user_id or "").strip() or row["id"]
            if requester_user_id != row["id"]:
                requester_exists = fetch_one(
                    "SELECT id FROM users WHERE id = %s LIMIT 1;",
                    (requester_user_id,),
                )
                if not requester_exists:
                    requester_user_id = row["id"]
            ticket_source = str(body.ticket_source or "").strip() or (
                "chatbot" if str(body.created_by_user_id or "").strip() else "orchestrator"
            )
            normalized_type = ticket_type or None
            initial_priority = priority_label
            initial_status = normalized_status or "Open"
            initial_department_id = department_id
            if has_routing_decision:
                if routing_is_confident:
                    initial_status = "Assigned"
                else:
                    initial_department_id = None
                    initial_status = "Open"
            initial_priority_assigned_at = None
            subject_text = (
                (body.subject or "").strip()
                or (body.transcript or "").strip()[:120]
                or "Automated ticket"
            )
            details_text = (body.transcript or "").strip()
            created = create_ticket_via_gate(
                cur,
                created_by_user_id=requester_user_id,
                ticket_type=normalized_type,
                subject=subject_text,
                details=details_text,
                priority=initial_priority,
                status=initial_status,
                ticket_source=ticket_source,
                department_id=initial_department_id,
                sentiment_score=body.sentiment,
                sentiment_label="orchestrator" if body.sentiment is not None else None,
                model_priority=initial_priority,
                model_department_id=department_id,
                model_confidence=routing_confidence_raw,
                priority_assigned_at=initial_priority_assigned_at,
            )
            auto_assign_ticket_if_needed(
                cur,
                ticket_code=created.get("ticket_code"),
                status=created.get("status"),
                department_id=initial_department_id,
                priority=created.get("priority"),
            )

            queued_for_review = False
            if has_routing_decision and created.get("ticket_code"):
                cur.execute(
                    "SELECT id::text AS id FROM tickets WHERE ticket_code = %s LIMIT 1;",
                    (created.get("ticket_code"),),
                )
                created_row = cur.fetchone()
                if created_row:
                    ticket_uuid = str(created_row[0])
                    queued_for_review = record_department_routing_decision(
                        cur,
                        ticket_uuid=ticket_uuid,
                        ticket_code=str(created.get("ticket_code")),
                        suggested_department=requested_department,
                        routing_confidence_pct=float(routing_confidence_pct),
                        routing_is_confident=routing_is_confident,
                        department_id=str(department_id) if department_id else None,
                        priority=created.get("priority"),
                        insert_notification=_insert_notification,
                        logger=logger,
                    )

            return {
                "ticket_id": str(created["id"]) if created.get("id") else created.get("ticket_code"),
                "ticket_code": created.get("ticket_code"),
                "status": created.get("status"),
                "priority": created.get("priority"),
                "asset_type": requested_asset_type,
                "department": (requested_department if routing_is_confident else None),
                "queued_for_review": queued_for_review,
                "priority_assigned_at": created.get("priority_assigned_at").isoformat()
                if created.get("priority_assigned_at")
                else None,
                "respond_due_at": created.get("respond_due_at").isoformat()
                if created.get("respond_due_at")
                else None,
                "resolve_due_at": created.get("resolve_due_at").isoformat()
                if created.get("resolve_due_at")
                else None,
            }


@api.post("/internal/tickets/{ticket_code}/generate-suggested-resolution")
def internal_generate_suggested_resolution(ticket_code: str, _key: None = Depends(require_internal_key)):
    """
    Return the latest stored suggestion for a ticket code.
    Suggested resolution generation is owned by the orchestrator pipeline.
    """
    ticket_code = _sanitize_ticket_code(ticket_code)
    row = fetch_one(
        """
        SELECT
          t.id,
          t.ticket_code,
          t.ticket_type,
          t.subject,
          t.details,
          t.asset_type,
          t.priority,
          t.status,
          t.priority_assigned_at,
          t.suggested_resolution,
          t.suggested_resolution_model,
          d.name AS department_name
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.ticket_code = %s
        LIMIT 1;
        """,
        (ticket_code,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    refreshed = fetch_one(
        """
        SELECT suggested_resolution, suggested_resolution_model
        FROM tickets
        WHERE ticket_code = %s
        LIMIT 1;
        """,
        (ticket_code,),
    ) or {}
    suggestion = str(refreshed.get("suggested_resolution") or "").strip()
    if not suggestion:
        raise HTTPException(status_code=409, detail="Suggested resolution is owned by orchestrator pipeline and is not available yet")
    model_name = str(refreshed.get("suggested_resolution_model") or "orchestrator").strip() or "orchestrator"

    return {
        "ticketId": ticket_code,
        "suggestedResolution": suggestion,
        "model": model_name,
    }


@api.post("/chatbot/chat")
async def proxy_chatbot_chat(body: ChatbotProxyRequest, _csrf: None = Depends(require_csrf)):
    """
    Frontend-facing chatbot proxy.
    Keeps chatbot service private behind backend API.
    """
    chatbot_url = os.getenv("CHATBOT_URL", "http://chatbot:8000")
    local_fallback = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001")

    payload = {
        "message": body.message,
        "user_id": body.user_id,
        "session_id": body.session_id,
    }
    last_error = None

    for base in [chatbot_url, local_fallback]:
        try:
            async with httpx.AsyncClient(timeout=CHATBOT_PROXY_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{base}/api/chat", json=payload)
                response.raise_for_status()
                data = response.json()
                return {
                    "session_id": data.get("session_id"),
                    "response": data.get("response", ""),
                    "response_type": data.get("response_type", "unknown"),
                    "show_buttons": data.get("show_buttons", []),
                    # Backward-compatible key for older UIs.
                    "reply": data.get("response", ""),
                }
        except Exception as exc:
            last_error = exc
            continue

    logger.warning("chatbot_proxy | all endpoints failed: %s", last_error)
    raise HTTPException(status_code=503, detail="Chat service is temporarily unavailable. Please try again later.")


@api.post("/transcriber/transcribe")
@api.post("/whisper/transcribe")
async def proxy_transcriber_transcribe(audio: UploadFile = File(...), _user: Dict[str, Any] = Depends(get_current_user)):
    """
    Frontend-facing transcriber proxy.
    Forwards multipart audio to transcriber service and returns transcript.
    """
    transcriber_url = os.getenv("TRANSCRIBER_URL", "http://transcriber:3001")
    local_fallback = os.getenv("TRANSCRIBER_URL_LOCAL", "http://localhost:3001")

    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty")

    file_name = audio.filename or "recording.webm"
    content_type = audio.content_type or "audio/webm"
    last_error = None

    for base in [transcriber_url, local_fallback]:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{base}/transcribe",
                    files={"audio": (file_name, audio_bytes, content_type)},
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "transcript": data.get("transcript", ""),
                    "audio_features": data.get("audio_features"),
                }
        except Exception as exc:
            last_error = exc
            continue

    logger.warning("transcriber_proxy | all endpoints failed: %s", last_error)
    raise HTTPException(status_code=503, detail="Transcription service is temporarily unavailable. Please try again later.")


@api.post("/orchestrator/process/text")
async def proxy_orchestrator_process_text(request: Request, _user: Dict[str, Any] = Depends(get_current_user)):
    """
    Frontend-facing orchestrator proxy for form-based ticket submission.
    The orchestrator is not exposed to the internet, so the backend proxies
    requests from the browser to orchestrator:8004/process/text.
    """
    body_bytes = await request.body()
    content_type = request.headers.get("content-type", "application/x-www-form-urlencoded")
    last_error = None
    base_candidates = [
        ORCHESTRATOR_URL,
        ORCHESTRATOR_URL_LOCAL,
        "http://innovacx-orchestrator:8004",
    ]
    bases: list[str] = []
    for base in base_candidates:
        normalized = (base or "").rstrip("/")
        if normalized and normalized not in bases:
            bases.append(normalized)

    for attempt in range(1, 4):
        for base in bases:
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    response = await client.post(
                        f"{base}/process/text",
                        content=body_bytes,
                        headers={"Content-Type": content_type},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.HTTPStatusError as exc:
                # Preserve user/input errors from orchestrator, retry only 5xx.
                status_code = exc.response.status_code
                if 400 <= status_code < 500:
                    detail = None
                    try:
                        payload = exc.response.json()
                        detail = payload.get("detail")
                    except Exception:
                        detail = exc.response.text or "Request rejected by orchestrator"
                    raise HTTPException(status_code=status_code, detail=detail)
                last_error = exc
            except Exception as exc:
                last_error = exc
                continue
        await asyncio.sleep(0.5 * attempt)

    logger.warning("orchestrator_proxy | all endpoints failed: %s", last_error)
    raise HTTPException(status_code=503, detail="Service is temporarily unavailable. Please try again later.")


# OPERATOR ANALYTICS ENDPOINTS
def _parse_time_range(
    timeRange: str,
    dateFrom: Optional[str] = None,
    dateTo:   Optional[str] = None,
):
    """
    Resolves (period_start, period_end) from either explicit ISO date strings
    or a named preset. Custom range takes priority when both dateFrom and dateTo
    are provided.
    """
    if dateFrom and dateTo:
        period_start = fetch_one("SELECT %s::timestamptz AS ts", [dateFrom])["ts"]
        period_end   = fetch_one("SELECT (%s::date + interval '1 day - 1 second')::timestamptz AS ts", [dateTo])["ts"]
        return period_start, period_end

    range_sql = {
        "last7days":    "now() - interval '7 days'",
        "Last 7 Days":  "now() - interval '7 days'",
        "last30days":   "now() - interval '30 days'",
        "Last 30 Days": "now() - interval '30 days'",
        "quarter":      "date_trunc('quarter', now())",
        "This Quarter": "date_trunc('quarter', now())",
    }
    start_expr   = range_sql.get(timeRange, "now() - interval '30 days'")
    period_start = fetch_one(f"SELECT ({start_expr})::timestamptz AS start")["start"]
    # Add 1 day so today's rows are included by the standard "created_day < period_end" filter
    period_end   = fetch_one("SELECT (now() + interval '1 day')::timestamptz AS ts")["ts"]
    return period_start, period_end

@api.get("/operator/analytics/qc/acceptance")
def get_operator_qc_acceptance(
    timeRange:  str           = Query("last30days"),
    department: str           = Query("All Departments"),
    dateFrom:   Optional[str] = Query(None),
    dateTo:     Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Acceptance tab — called only when that tab is clicked."""
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)
    if not _ANALYTICS_READY:
        raise HTTPException(status_code=503, detail="Analytics MVs not ready.")
    try:
        full = _analytics.get_operator_qc_data(period_start, period_end, department)
        return full["acceptance"]
    except Exception as e:
        logger.error("get_operator_qc_acceptance failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/operator/analytics/qc/rescoring")
def get_operator_qc_rescoring(
    timeRange:  str           = Query("last30days"),
    department: str           = Query("All Departments"),
    dateFrom:   Optional[str] = Query(None),
    dateTo:     Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Rescoring tab — called only when that tab is clicked."""
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)
    if not _ANALYTICS_READY:
        raise HTTPException(status_code=503, detail="Analytics MVs not ready.")
    try:
        full = _analytics.get_operator_qc_data(period_start, period_end, department)
        return full["rescoring"]
    except Exception as e:
        logger.error("get_operator_qc_rescoring failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/operator/analytics/qc/rerouting")
def get_operator_qc_rerouting(
    timeRange:  str           = Query("last30days"),
    department: str           = Query("All Departments"),
    dateFrom:   Optional[str] = Query(None),
    dateTo:     Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Rerouting tab — called only when that tab is clicked."""
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)
    if not _ANALYTICS_READY:
        raise HTTPException(status_code=503, detail="Analytics MVs not ready.")
    try:
        full = _analytics.get_operator_qc_data(period_start, period_end, department)
        return full["rerouting"]
    except Exception as e:
        logger.error("get_operator_qc_rerouting failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

@api.get("/operator/analytics/qc/rescoring-rerouting")
def get_operator_qc_rescoring_rerouting(
    timeRange:  str           = Query("last30days"),
    department: str           = Query("All Departments"),
    dateFrom:   Optional[str] = Query(None),
    dateTo:     Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    """
    Merged Rescoring + Rerouting tab payload.
    Returns rescoring kpis, reassignmentByDept (all departments, incl. 0-value rows),
    and reroutingKpis — all in one response for the unified B tab.
    """
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)
    if not _ANALYTICS_READY:
        raise HTTPException(status_code=503, detail="Analytics MVs not ready.")
    try:
        full = _analytics.get_operator_qc_data(period_start, period_end, department)
        rescoring = full["rescoring"]
        return {
            "kpis":               rescoring["kpis"],
            "byDepartment":       rescoring["byDepartment"],
            "reassignmentByDept": rescoring["reassignmentByDept"],
            "reroutingKpis":      rescoring["reroutingKpis"],
        }
    except Exception as e:
        logger.error("get_operator_qc_rescoring_rerouting failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@api.get("/operator/learning/reroute")
def get_learning_reroute(
    department: Optional[str] = Query(None),
    limit:      int           = Query(200),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Routing correction records from reroute_reference."""
    with db_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT
                    r.id, r.ticket_id, r.department,
                    r.original_dept, r.corrected_dept,
                    r.source_type, r.decided_by,
                    r.created_at,
                    t.ticket_code, t.subject,
                    u.full_name AS decided_by_name
                FROM reroute_reference r
                LEFT JOIN tickets t ON t.id = r.ticket_id
                LEFT JOIN user_profiles u ON u.user_id = r.decided_by
            """
            params: list = []
            if department and department != "All Departments":
                sql += " WHERE r.department = %s"
                params.append(department)
            sql += " ORDER BY r.created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


@api.get("/operator/learning/rescore")
def get_learning_rescore(
    department: Optional[str] = Query(None),
    limit:      int           = Query(200),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Priority correction records from rescore_reference."""
    with db_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT
                    r.id, r.ticket_id, r.department,
                    r.original_priority, r.corrected_priority,
                    r.source_type, r.decided_by,
                    r.created_at,
                    t.ticket_code, t.subject,
                    u.full_name AS decided_by_name
                FROM rescore_reference r
                LEFT JOIN tickets t ON t.id = r.ticket_id
                LEFT JOIN user_profiles u ON u.user_id = r.decided_by
            """
            params: list = []
            if department and department != "All Departments":
                sql += " WHERE r.department = %s"
                params.append(department)
            sql += " ORDER BY r.created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


@api.get("/operator/learning/resolution")
def get_learning_resolution(
    department: Optional[str] = Query(None),
    limit:      int           = Query(200),
    user: Dict[str, Any] = Depends(require_operator),
):
    """Suggested resolution usage records from suggested_resolution_usage."""
    with db_connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = """
                SELECT
                    s.id, s.ticket_id, s.employee_user_id,
                    s.decision, s.used,
                    s.suggested_text, s.final_text,
                    s.created_at,
                    t.ticket_code, t.subject,
                    t.department_id,
                    d.name AS department,
                    u.full_name AS employee_name
                FROM suggested_resolution_usage s
                LEFT JOIN tickets t ON t.id = s.ticket_id
                LEFT JOIN departments d ON d.id = t.department_id
                LEFT JOIN user_profiles u ON u.user_id = s.employee_user_id
            """
            params: list = []
            if department and department != "All Departments":
                sql += " WHERE d.name = %s"
                params.append(department)
            sql += " ORDER BY s.created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


@api.get("/operator/analytics/model-health/chatbot")
def get_operator_chatbot(
    timeRange: str           = Query("last30days"),
    dateFrom:  Optional[str] = Query(None),
    dateTo:    Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)

    if _ANALYTICS_READY:
        try:
            return _analytics.get_operator_chatbot_data(
                period_start=period_start,
                period_end=period_end,
            )
        except Exception as _svc_err:
            logger.error(
                "analytics_service.get_operator_chatbot_data failed. err=%s", _svc_err
            )
            raise HTTPException(status_code=500, detail=f"Analytics service error: {_svc_err}")

    raise HTTPException(
        status_code=503,
        detail="Analytics MVs not ready. Run database/scripts/analytics_mvs.sql first."
    )


@api.get("/operator/analytics/model-health/sentiment")
def get_operator_sentiment(
    timeRange: str           = Query("last30days"),
    dateFrom:  Optional[str] = Query(None),
    dateTo:    Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)

    if _ANALYTICS_READY:
        try:
            return _analytics.get_operator_sentiment_data(
                period_start=period_start,
                period_end=period_end,
                department=department,
            )
        except Exception as _svc_err:
            logger.error("analytics_service.get_operator_sentiment_data failed. err=%s", _svc_err)
            raise HTTPException(status_code=500, detail=f"Analytics service error: {_svc_err}")

    raise HTTPException(
        status_code=503,
        detail="Analytics MVs not ready. Run database/scripts/analytics_mvs.sql first."
    )


@api.get("/operator/analytics/model-health/feature")
def get_operator_feature(
    timeRange: str           = Query("last30days"),
    dateFrom:  Optional[str] = Query(None),
    dateTo:    Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_operator),
):
    period_start, period_end = _parse_time_range(timeRange, dateFrom, dateTo)

    if _ANALYTICS_READY:
        try:
            return _analytics.get_operator_feature_data(
                period_start=period_start,
                period_end=period_end,
                department=department,
            )
        except Exception as _svc_err:
            logger.error("analytics_service.get_operator_feature_data failed. err=%s", _svc_err)
            raise HTTPException(status_code=500, detail=f"Analytics service error: {_svc_err}")

    raise HTTPException(
        status_code=503,
        detail="Analytics MVs not ready. Run database/scripts/analytics_mvs.sql first."
    )
# OPERATOR DASHBOARD SUMMARY  

@api.get("/operator/dashboard/summary")
def operator_dashboard_summary(user: Dict[str, Any] = Depends(require_operator)):
    """
    Returns live model-health and quality-control metrics for the
    Operator Dashboard summary cards.

    Model health window : last 1 hour
    Drift window        : last 24 hours
    QC pending/oldest   : current pending queue
    QC avg review time + flagged today : last 24 hours
    """

    # Model Health
    try:
        mh_row = fetch_one(
            """
            SELECT
              COALESCE(AVG(latency_ms), 0)::numeric           AS avg_latency_ms,
              COALESCE(
                SUM(CASE WHEN is_error THEN 1 ELSE 0 END)::numeric
                / NULLIF(COUNT(*), 0) * 100,
                0
              )                                               AS error_rate_pct
            FROM model_metrics
            WHERE created_at >= now() - interval '1 hour';
            """
        ) or {}
        avg_latency_ms = float(mh_row.get("avg_latency_ms") or 0)
        error_rate_pct = round(float(mh_row.get("error_rate_pct") or 0), 2)
        model_metrics_available = True
    except Exception:
        avg_latency_ms = 0.0
        error_rate_pct = 0.0
        model_metrics_available = False

    try:
        drift_row = fetch_one(
            """
            SELECT COUNT(*) AS cnt
            FROM drift_events
            WHERE detected_at >= now() - interval '24 hours';
            """
        ) or {}
        drift_detected = int(drift_row.get("cnt") or 0) > 0
    except Exception:
        drift_detected = False

    # Status logic (exact as spec)
    if not model_metrics_available:
        status = "No Data"
    elif error_rate_pct > 3 or avg_latency_ms > 1500:
        status = "Critical"
    elif (1 <= error_rate_pct <= 3) or (800 <= avg_latency_ms <= 1500):
        status = "Degraded"
    else:
        status = "Healthy"

    # Quality Control
    try:
        qc_row = fetch_one(
            """
            SELECT
              -- pending queue
              COUNT(*) FILTER (WHERE status = 'pending')                   AS pending_reviews,
              -- oldest pending age (seconds since created_at)
              COALESCE(
                EXTRACT(EPOCH FROM (now() - MIN(created_at) FILTER (WHERE status = 'pending')))
              , 0)::int                                                     AS oldest_pending_age_sec,
              -- average review time for completed reviews in last 24h
              COALESCE(
                AVG(
                  CASE
                    WHEN review_duration_sec IS NOT NULL THEN review_duration_sec
                    WHEN reviewed_at IS NOT NULL
                      THEN EXTRACT(EPOCH FROM (reviewed_at - created_at))
                    ELSE NULL
                  END
                ) FILTER (
                  WHERE status IN ('approved', 'rejected')
                    AND created_at >= now() - interval '24 hours'
                ),
                0
              )::int                                                        AS avg_review_time_sec,
              -- flagged today
              COUNT(*) FILTER (
                WHERE flagged = TRUE
                  AND created_at >= now() - interval '24 hours'
              )                                                              AS flagged_today
            FROM qc_reviews;
            """
        ) or {}
    except Exception:
        qc_row = {}

    return {
        "modelHealth": {
            "status":                   status,
            "avg_latency_ms":           round(avg_latency_ms, 1),
            "error_rate_pct":           error_rate_pct,
            "drift_detected":           drift_detected,
            "model_metrics_available":  model_metrics_available,
        },
        "qualityControl": {
            "pending_reviews":      int(qc_row.get("pending_reviews")      or 0),
            "avg_review_time_sec":  int(qc_row.get("avg_review_time_sec")  or 0),
            "flagged_today":        int(qc_row.get("flagged_today")         or 0),
            "oldest_pending_age_sec": int(qc_row.get("oldest_pending_age_sec") or 0),
        },
    }

# Operator – Quality Control / Ticket Review Detail

@api.get("/operator/complaints/{ticket_id}")
def get_operator_complaint_detail(
    ticket_id: str,
    user: Dict[str, Any] = Depends(require_operator),
):
    """
    Full ticket detail for the QC TicketReviewDetail page.
    Accepts either a ticket_code (e.g. CX-0042) or a raw UUID.
    """
    # Accept both ticket_code (CX-…) and UUID — validate accordingly
    _stripped = ticket_id.strip()
    if _TICKET_CODE_RE.match(_stripped.upper()):
        ticket_id = _stripped.upper()
    else:
        ticket_id = _sanitize_uuid(_stripped, "ticket_id")
    ticket = fetch_one(
        """
        SELECT
            t.id                                    AS ticket_id,
            t.ticket_code,
            t.subject,
            t.details,
            t.status,
            t.priority,
            t.model_priority,
            t.model_confidence                      AS priority_confidence,
            t.sentiment_label,
            t.sentiment_score,
            t.suggested_resolution,
            t.suggested_resolution_model,
            t.created_at,
            t.first_response_at,
            t.resolved_at,
            t.respond_due_at,
            t.resolve_due_at,
            t.respond_breached,
            t.resolve_breached,
            t.human_overridden,
            t.override_reason,
            t.is_recurring,
            t.asset_type,
            d.name                                  AS department_name,
            md.name                                 AS model_dept,
            up_assigned.full_name                   AS assigned_to_name,
            up_assigned.job_title                   AS assigned_to_title,
            up_created.full_name                    AS created_by_name,
            u_created.role                          AS created_by_role
        FROM tickets t
        LEFT JOIN departments   d            ON d.id  = t.department_id
        LEFT JOIN departments   md           ON md.id = t.model_department_id
        LEFT JOIN user_profiles up_assigned  ON up_assigned.user_id = t.assigned_to_user_id
        LEFT JOIN user_profiles up_created   ON up_created.user_id  = t.created_by_user_id
        LEFT JOIN users         u_created    ON u_created.id         = t.created_by_user_id
        WHERE t.ticket_code = %s OR t.id::text = %s
        LIMIT 1
        """,
        (ticket_id, ticket_id),
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    tid = ticket["ticket_id"]

    # approval requests
    approval_requests = fetch_all(
        """
        SELECT
            request_code,
            request_type,
            current_value,
            requested_value,
            request_reason,
            status,
            submitted_at,
            decided_at,
            decision_notes
        FROM approval_requests
        WHERE ticket_id = %s
        ORDER BY submitted_at DESC
        """,
        (tid,),
    ) or []

    # model execution log
    execution_log = fetch_all(
        """
        SELECT
            agent_name,
            model_version,
            started_at,
            ROUND(
                EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000
            )::int                              AS duration_ms,
            status
        FROM model_execution_log
        WHERE ticket_id = %s
        ORDER BY started_at ASC
        """,
        (tid,),
    ) or []


    # ticket updates
    ticket_updates = fetch_all(
        """
        SELECT
            update_type,
            from_status,
            to_status,
            message,
            created_at
        FROM ticket_updates
        WHERE ticket_id = %s
        ORDER BY created_at ASC
        """,
        (tid,),
    ) or []

    # current-run AI outputs
    sentiment = fetch_one(
        """
        SELECT sentiment_label, sentiment_score,
               confidence_score AS sentiment_confidence
        FROM sentiment_outputs
        WHERE ticket_id = %s AND is_current = TRUE
        LIMIT 1
        """,
        (tid,),
    )
    feature = fetch_one(
        """
        SELECT asset_category, topic_labels,
               confidence_score AS feature_confidence
        FROM feature_outputs
        WHERE ticket_id = %s AND is_current = TRUE
        LIMIT 1
        """,
        (tid,),
    )
    resolution = fetch_one(
        """
        SELECT suggested_text   AS suggested_resolution,
               model_version    AS suggested_resolution_model
        FROM resolution_outputs
        WHERE ticket_id = %s AND is_current = TRUE
        LIMIT 1
        """,
        (tid,),
    )
    # Some flows persist directly on tickets table without a current
    # resolution_outputs row. Fall back so the UI can still show suggestions.
    if not str((resolution or {}).get("suggested_resolution") or "").strip():
        resolution = {
            "suggested_resolution": ticket.get("suggested_resolution"),
            "suggested_resolution_model": ticket.get("suggested_resolution_model"),
        }
    routing = fetch_one(
        """
        SELECT confidence_score AS routing_confidence,
               reasoning        AS routing_reason
        FROM routing_outputs
        WHERE ticket_id = %s AND is_current = TRUE
        LIMIT 1
        """,
        (tid,),
    )
    feedback = fetch_one(
        """
        SELECT
            CASE WHEN sru.used THEN 'accepted' ELSE 'declined_custom' END AS feedback_decision,
            sru.final_text AS final_resolution
        FROM suggested_resolution_usage sru
        WHERE sru.ticket_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (tid,),
    )

    # chat sentiment series (for escalated tickets)
    chat_sentiment = fetch_all(
        """
        SELECT sentiment_score, created_at
        FROM user_chat_logs
        WHERE ticket_id = %s
        ORDER BY created_at ASC
        """,
        (tid,),
    ) or []

    # helpers
    def _iso(val):
        return val.isoformat() if val else None

    def _flt(val):
        return float(val) if val is not None else None

    return {
        "ticketCode":          ticket["ticket_code"],
        "subject":             ticket["subject"],
        "details":             ticket["details"],
        "status":              ticket["status"],
        "priority":            ticket["priority"],
        "modelPriority":       ticket["model_priority"],
        "priorityConfidence":  _flt(ticket.get("priority_confidence")),
        "sentimentLabel":      (sentiment or {}).get("sentiment_label")  or ticket.get("sentiment_label"),
        "sentimentScore":      _flt((sentiment or {}).get("sentiment_score") or ticket.get("sentiment_score")) or 0.0,
        "sentimentConfidence": _flt((sentiment or {}).get("sentiment_confidence")),
        "modelDept":           ticket.get("model_dept"),
        "finalDept":           ticket.get("department_name"),
        "routingConfidence":   _flt((routing or {}).get("routing_confidence")),
        "routingReason":       (routing or {}).get("routing_reason") or "",
        "humanOverridden":     ticket.get("human_overridden"),
        "overrideReason":      ticket.get("override_reason"),
        "isRecurring":         ticket.get("is_recurring"),
        "respondBreached":     ticket.get("respond_breached"),
        "resolveBreached":     ticket.get("resolve_breached"),
        "createdAt":           _iso(ticket.get("created_at")),
        "resolvedAt":          _iso(ticket.get("resolved_at")),
        "firstResponseAt":     _iso(ticket.get("first_response_at")),
        "respondDueAt":        _iso(ticket.get("respond_due_at")),
        "resolveDueAt":        _iso(ticket.get("resolve_due_at")),
        "assetCategory":       (feature or {}).get("asset_category") or ticket.get("asset_type"),
        "topicLabels":         (feature or {}).get("topic_labels") or [],
        "featureConfidence":   _flt((feature or {}).get("feature_confidence")),
        "assignedToName":      ticket.get("assigned_to_name") or "Not Assigned",
        "assignedToTitle":     ticket.get("assigned_to_title") or "",
        "createdByName":       ticket.get("created_by_name") or "Unknown",
        "createdByRole":       ticket.get("created_by_role") or "",
        "suggestedResolution": (resolution or {}).get("suggested_resolution") or "",
        "resolutionModel":     (resolution or {}).get("suggested_resolution_model") or "",
        "finalResolution":     (feedback or {}).get("final_resolution"),
        "feedbackDecision":    (feedback or {}).get("feedback_decision"),
        "approvalRequests": [
            {
                "requestCode":    r.get("request_code"),
                "requestType":    r.get("request_type"),
                "currentValue":   r.get("current_value"),
                "requestedValue": r.get("requested_value"),
                "requestReason":  r.get("request_reason"),
                "status":         r.get("status"),
                "submittedAt":    _iso(r.get("submitted_at")),
                "decidedAt":      _iso(r.get("decided_at")),
                "decisionNotes":  r.get("decision_notes"),
            }
            for r in approval_requests
        ],
        "executionLog": [
            {
                "agentName":    e.get("agent_name"),
                "modelVersion": e.get("model_version"),
                "startedAt":    _iso(e.get("started_at")),
                "durationMs":   e.get("duration_ms"),
                "status":       e.get("status"),
            }
            for e in execution_log
        ],
        "ticketUpdates": [
            {
                "updateType": u.get("update_type"),
                "fromStatus": u.get("from_status"),
                "toStatus":   u.get("to_status"),
                "message":    u.get("message"),
                "createdAt":  _iso(u.get("created_at")),
            }
            for u in ticket_updates
        ],
        "chatSentimentSeries": [
            {"score": _flt(c["sentiment_score"])}
            for c in chat_sentiment
            if c.get("sentiment_score") is not None
        ],
    }


# Operator – User Management
_VALID_ROLES    = {"customer", "employee", "manager", "operator"}
_VALID_STATUSES = {"active", "inactive"}
_SAFE_TEXT_RE   = _re.compile(r'^[\w\s\-\.,\'\+\(\)@/]+$', _re.UNICODE)


def _sanitize_text(value: str, field: str, max_len: int = 120) -> str:
    v = value.strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} must not be empty.")
    if len(v) > max_len:
        raise HTTPException(status_code=422, detail=f"{field} exceeds maximum length of {max_len}.")
    if not _SAFE_TEXT_RE.match(v):
        raise HTTPException(status_code=422, detail=f"{field} contains invalid characters.")
    return v


def _sanitize_email(value: str) -> str:
    v = value.strip().lower()
    pattern = _re.compile(r'^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$')
    if not pattern.match(v):
        raise HTTPException(status_code=422, detail="Invalid email address.")
    if len(v) > 254:
        raise HTTPException(status_code=422, detail="Email address too long.")
    return v

def _validate_type(value, expected_type, field: str):
    if not isinstance(value, expected_type):
        raise HTTPException(
            status_code=422,
            detail=f"{field} must be of type {expected_type.__name__}."
        )
    return value


# ── Path-parameter sanitisation helpers ──────────────────────────────────────

def _sanitize_uuid(value: str, field: str = "ID") -> str:
    """Validate that a path parameter is a well-formed UUID.
    Returns the lower-cased canonical string form.
    Raises HTTP 400 on failure so callers never reach the DB with garbage.
    """
    try:
        return str(_uuid_mod.UUID(str(value).strip()))
    except (ValueError, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: must be a valid UUID.")


_TICKET_CODE_RE = _re.compile(r'^CX-\d{1,10}$', _re.IGNORECASE)

def _sanitize_ticket_code(value: str, field: str = "ticket code") -> str:
    """Validate a ticket_code path parameter (format: CX-<digits>).
    Returns the upper-cased canonical form.
    Raises HTTP 400 on failure.
    """
    v = (value or "").strip().upper()
    if not _TICKET_CODE_RE.match(v):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: expected format CX-<number>.")
    return v


_ALLOWED_TIME_RANGES = frozenset({
    "7d", "Last 7 Days", "30d", "Last 30 Days",
    "This Month", "Last 3 Months", "Last 6 Months",
    "Last 12 Months", "90d", "last30days",
})

def _sanitize_time_range(value: str) -> str:
    """Reject timeRange query params not in the known allowlist."""
    if value not in _ALLOWED_TIME_RANGES:
        raise HTTPException(status_code=400, detail=f"Invalid timeRange value: '{value}'.")
    return value


_ALLOWED_ROUTING_STATUSES = frozenset({"Pending", "Approved", "Overridden", "Denied", "All"})

def _sanitize_status_filter(value: str) -> str:
    """Reject status_filter values not in the known allowlist."""
    if value not in _ALLOWED_ROUTING_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status_filter value: '{value}'.")
    return value

class CreateUserRequest(BaseModel):
    fullName:   str
    email:      str
    phone:      str
    location:   str
    password:   str
    role:       str
    # Department is required for non-customer roles; for customers it can be omitted/empty.
    department: Optional[str] = None
    status:     str = "active"


@api.post("/operator/user-creation")
def operator_create_user(
    body: CreateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    """
    Create a new user (operator-only).
    - All fields sanitized/validated before touching the DB.
    - Password hashed with bcrypt (cost 12) – plain text never persisted.
    - Every DB write uses parameterised queries; no string interpolation.
    """
    if current_user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Only operators can create users.")

    # Sanitize & validate
    # ----- TYPE VALIDATION (NEW - SAFE ADD)
    _validate_type(body.fullName, str,"Full name")
    _validate_type(body.email, str,"Email")
    _validate_type(body.phone, str,"Phone")
    _validate_type(body.location, str,"Location")
    _validate_type(body.password, str,"Password")
    _validate_type(body.role, str,"Role")

    if body.department is not None:
        _validate_type(body.department, str, "Department")

    _validate_type(body.status, str, "Status")

    full_name  = _sanitize_text(body.fullName,   "Full name")
    email      = _sanitize_email(body.email)
    phone      = _sanitize_text(body.phone,      "Phone",      max_len=30)
    location   = _sanitize_text(body.location,   "Location")

    # Department is only applicable for non-customer roles.
    department: Optional[str] = None
    if body.role != "customer":
        if not (body.department or "").strip():
            raise HTTPException(status_code=422, detail="Department is required for non-customer roles.")
        department = _sanitize_text(body.department, "Department")

    if body.role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role '{body.role}'.")
    if body.status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{body.status}'.")

    raw_password = body.password
    validate_password_complexity(raw_password, field_name="Password", email=email)
    # Hash with bcrypt cost-12
    password_hash = bcrypt.hashpw(
        raw_password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    # Persist (fully parameterised)
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:

                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="A user with that email already exists.")

                dept_id = None
                if department is not None:
                    cur.execute(
                        "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s)", (department,)
                    )
                    dept_row = cur.fetchone()
                    if dept_row:
                        dept_id = dept_row["id"]
                    else:
                        cur.execute(
                            "INSERT INTO departments (name) VALUES (%s) RETURNING id", (department,)
                        )
                        dept_id = cur.fetchone()["id"]

                is_active = body.status == "active"
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, role, is_active, mfa_enabled)
                    VALUES (%s, %s, %s::user_role, %s, FALSE)
                    RETURNING id
                    """,
                    (email, password_hash, body.role, is_active),
                )
                user_id = cur.fetchone()["id"]

                cur.execute(
                    """
                    INSERT INTO user_profiles (user_id, full_name, phone, location, department_id)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(user_id), full_name, phone, location, dept_id),
                )

            conn.commit()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("operator_create_user error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create user. Please try again.")

    logger.info(
        "operator_create_user | user_id=%s email=%s role=%s by operator=%s",
        user_id, email, body.role, current_user["id"],
    )

    return {
        "success": True,
        "userId": str(user_id),
        "message": f"User '{full_name}' created successfully.",
    }


@api.get("/operator/users")
def operator_list_users(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return all users with profiles (operator-only)."""
    if current_user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Only operators can view users.")

    rows = fetch_all(
        """
        SELECT
            u.id,
            u.email,
            u.role,
            u.is_active,
            u.created_at,
            up.full_name,
            up.phone,
            up.location,
            d.name AS department
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN departments    d  ON d.id = up.department_id
        ORDER BY u.created_at DESC
        """,
    )

    return [
        {
            "id":         str(r["id"]),
            "email":      r["email"],
            "role":       r["role"],
            "status":     "active" if r["is_active"] else "inactive",
            "createdAt":  r["created_at"].isoformat() if r.get("created_at") else None,
            "fullName":   r.get("full_name") or "",
            "phone":      r.get("phone") or "",
            "location":   r.get("location") or "",
            "department": r.get("department") or "",
        }
        for r in rows
    ]


class UpdateUserRequest(BaseModel):
    fullName: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    # Department is only applicable for non-customer roles
    department: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None
    # Optional password update
    password: Optional[str] = None


class UpdateUserStatusRequest(BaseModel):
    status: str


@api.put("/operator/users/{user_id}")
def operator_update_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    """Update user + profile (operator-only)."""
    user_id = _sanitize_uuid(user_id, "user_id")
    if current_user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Only operators can update users.")

    # Load current state
    existing = fetch_one(
        """
        SELECT
            u.id,
            u.email,
            u.role,
            u.is_active,
            up.full_name,
            up.phone,
            up.location,
            up.department_id,
            d.name AS department
        FROM users u
        LEFT JOIN user_profiles up ON up.user_id = u.id
        LEFT JOIN departments d ON d.id = up.department_id
        WHERE u.id = %s
        """,
        (user_id,),
    )
    if not existing:
        raise HTTPException(status_code=404, detail="User not found.")

    new_email = _sanitize_email(body.email) if body.email is not None else existing["email"]

    new_role = (body.role or existing["role"] or "customer").lower()
    if new_role not in _VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Invalid role '{new_role}'.")

    new_status = (body.status or ("active" if existing["is_active"] else "inactive")).lower()
    if new_status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{new_status}'.")

    new_full_name = _sanitize_text(body.fullName, "Full name") if body.fullName is not None else (existing.get("full_name") or "")
    new_phone = _sanitize_text(body.phone, "Phone", max_len=30) if body.phone is not None else (existing.get("phone") or "")
    new_location = _sanitize_text(body.location, "Location") if body.location is not None else (existing.get("location") or "")

    # Department rules:
    # - customer: department cleared (NULL)
    # - non-customer: department required; can keep existing if not provided
    department_value: Optional[str] = None
    if new_role != "customer":
        if body.department is not None:
            department_value = _sanitize_text(body.department, "Department")
        else:
            # keep existing, but must exist for non-customer roles
            department_value = (existing.get("department") or "").strip()
            if not department_value:
                raise HTTPException(status_code=422, detail="Department is required for non-customer roles.")

    # Optional password update
    password_hash: Optional[str] = None
    if body.password is not None:
        validate_password_complexity(
            body.password,
            field_name="Password",
            email=new_email,
        )
        password_hash = bcrypt.hashpw(
            body.password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Email uniqueness if changed
                if new_email != existing["email"]:
                    cur.execute("SELECT id FROM users WHERE email = %s", (new_email,))
                    row = cur.fetchone()
                    if row:
                        raise HTTPException(status_code=409, detail="A user with that email already exists.")

                # Department lookup/create (if applicable)
                dept_id = None
                if department_value is not None:
                    cur.execute(
                        "SELECT id FROM departments WHERE LOWER(name) = LOWER(%s)", (department_value,)
                    )
                    dept_row = cur.fetchone()
                    if dept_row:
                        dept_id = dept_row["id"]
                    else:
                        cur.execute(
                            "INSERT INTO departments (name) VALUES (%s) RETURNING id", (department_value,)
                        )
                        dept_id = cur.fetchone()["id"]

                # Update users
                is_active = new_status == "active"
                if password_hash is not None:
                    cur.execute(
                        """
                        UPDATE users
                        SET email=%s, role=%s::user_role, is_active=%s, password_hash=%s
                        WHERE id=%s
                        """,
                        (new_email, new_role, is_active, password_hash, user_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE users
                        SET email=%s, role=%s::user_role, is_active=%s
                        WHERE id=%s
                        """,
                        (new_email, new_role, is_active, user_id),
                    )

                # Ensure profile row exists, then update
                cur.execute("SELECT user_id FROM user_profiles WHERE user_id=%s", (user_id,))
                has_profile = cur.fetchone() is not None
                if not has_profile:
                    cur.execute(
                        """
                        INSERT INTO user_profiles (user_id, full_name, phone, location, department_id)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (user_id, new_full_name, new_phone, new_location, dept_id),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE user_profiles
                        SET full_name=%s, phone=%s, location=%s, department_id=%s
                        WHERE user_id=%s
                        """,
                        (new_full_name, new_phone, new_location, dept_id, user_id),
                    )

            conn.commit()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("operator_update_user error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user. Please try again.")

    return {"success": True, "message": "User updated successfully."}


@api.patch("/operator/users/{user_id}/status")
def operator_update_user_status(
    user_id: str,
    body: UpdateUserStatusRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    """Activate/Deactivate user (operator-only)."""
    user_id = _sanitize_uuid(user_id, "user_id")
    if current_user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Only operators can update users.")

    status = (body.status or "").lower()
    if status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Invalid status '{status}'.")

    is_active = status == "active"
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET is_active=%s WHERE id=%s", (is_active, user_id))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found.")
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("operator_update_user_status error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update user status.")

    return {"success": True, "message": f"User {status}."}


@api.delete("/operator/users/{user_id}")
def operator_delete_user(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    _csrf: None = Depends(require_csrf),
):
    """Delete a user (operator-only)."""
    user_id = _sanitize_uuid(user_id, "user_id")
    if current_user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Only operators can delete users.")

    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id=%s", (user_id,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="User not found.")
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("operator_delete_user error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete user.")

    return {"success": True, "message": "User deleted successfully."}


# TTS — call-centre audio reply

try:
    import edge_tts as _edge_tts
except ImportError:
    _edge_tts = None

_TTS_VOICE = "en-US-JennyNeural"

_TTS_TEMPLATES: dict = {
    "ticket_logged": (
        "Thank you for contacting us. "
        "Your {ticket_type} has been successfully logged. "
        "Your ticket ID is {ticket_id}. "
        "Our team will review your concern and respond as soon as possible."
    ),
    "inquiry_handled": (
        "Thank you for your inquiry. "
        "Our team has been notified and will get back to you shortly."
    ),
    "generic": "{text}",
}


async def _generate_tts_bytes(text: str, voice: str = _TTS_VOICE) -> bytes:
    communicate = _edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return buf.read()


class TTSSpeakRequest(BaseModel):
    message_type: Optional[str] = "ticket_logged"
    ticket_id: Optional[str] = None
    ticket_type: Optional[str] = "complaint"
    text: Optional[str] = None


@api.post("/tts/speak")
async def tts_speak(body: TTSSpeakRequest, _user: Dict[str, Any] = Depends(get_current_user)):
    if _edge_tts is None:
        return JSONResponse(
            status_code=503,
            content={"detail": "TTS unavailable: edge-tts package not installed"},
        )
    try:
        if body.text and body.text.strip():
            text = body.text.strip()
        else:
            template = _TTS_TEMPLATES.get(
                body.message_type or "ticket_logged",
                _TTS_TEMPLATES["ticket_logged"],
            )
            text = template.format(
                ticket_id=body.ticket_id or "unknown",
                ticket_type=body.ticket_type or "complaint",
                text="",
            )
        if not text:
            return JSONResponse(
                status_code=400,
                content={"detail": "No text provided for synthesis"},
            )
        audio_bytes = await _generate_tts_bytes(text)
        if not audio_bytes:
            return JSONResponse(
                status_code=503,
                content={"detail": "TTS returned empty audio"},
            )
        return {
            "audio_base64": base64.b64encode(audio_bytes).decode(),
            "mime_type": "audio/mpeg",
            "text": text,
        }
    except Exception as exc:
        logger.warning("TTS generation failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"detail": f"TTS unavailable: {exc}"},
        )


# Internal — pipeline queue notifications
# (called by orchestrator queue_manager, no user auth)

class InternalNotifyOperatorsRequest(BaseModel):
    ticket_id: Optional[str] = None
    ticket_code: Optional[str] = None
    notification_type: Optional[str] = None  # "pipeline_held" or "system"
    title: str
    message: str

@api.post("/internal/notify-operators")
def internal_notify_operators(body: InternalNotifyOperatorsRequest, _key: None = Depends(require_internal_key)):
    """Send a notification to all active operators (pipeline_held or system warning)."""
    notif_type = body.notification_type or "pipeline_held"
    priority = "Medium" if notif_type == "system" else "High"
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM users WHERE role = 'operator' AND is_active = TRUE")
                operator_ids = [r["id"] for r in cur.fetchall()]
                for op_id in operator_ids:
                    _insert_notification(
                        cur,
                        user_id=str(op_id),
                        notif_type=notif_type,
                        title=body.title,
                        message=body.message,
                        ticket_id=body.ticket_id,
                        priority=priority,
                    )
    except Exception as exc:
        logger.error("internal_notify_operators | failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True, "notified": len(operator_ids)}


# Internal — Review Agent verdict
# (called by orchestrator ReviewAgent after pipeline completes)

class ReviewVerdictRequest(BaseModel):
    ticket_id: str
    ticket_code: Optional[str] = None
    verdict: str  # approved | approved_operator_override | approved_routing_review | held_operator_review
    priority_label: Optional[str] = None
    department: Optional[str] = None
    routing_overridden: bool = False
    routing_sent_to_review: bool = False
    review_decision_id: Optional[str] = None


@api.post("/internal/review-verdict")
def internal_review_verdict(body: ReviewVerdictRequest, _key: None = Depends(require_internal_key)):
    """
    Apply the Review Agent's verdict to the ticket.

    - approved:                 no status change needed (ticket already Assigned/Open)
    - approved_operator_override:
                                no status change needed; operators are notified separately
    - approved_routing_review:  mark department_routing.is_confident=FALSE so the
                                department manager sees it in their review queue
    - held_operator_review:     set ticket.status='Review' so operators can inspect
    """
    ticket_uuid: str | None = None
    try:
        with db_connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Resolve ticket UUID
                cur.execute(
                    "SELECT id, ticket_code, status FROM tickets WHERE id = %s::uuid",
                    (body.ticket_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ticket not found")
                ticket_uuid = str(row["id"])

                final_priority = str(body.priority_label or "").strip().lower() or None
                valid_priority = final_priority in {"low", "medium", "high", "critical"}
                cur.execute(
                    "SELECT priority::text, department_id FROM tickets WHERE id = %s::uuid",
                    (ticket_uuid,),
                )
                priority_row = cur.fetchone() or {}
                previous_ticket_priority = str(priority_row.get("priority") or "")

                if body.verdict == "held_operator_review":
                    cur.execute(
                        "UPDATE tickets SET status = 'Review' WHERE id = %s::uuid",
                        (ticket_uuid,),
                    )
                    logger.info(
                        "review_verdict | ticket=%s verdict=held_operator_review → status=Review",
                        body.ticket_code or ticket_uuid,
                    )

                elif body.verdict == "approved_routing_review":
                    # Mark department routing as low-confidence → manager review queue picks it up
                    cur.execute(
                        "UPDATE department_routing SET is_confident = FALSE WHERE ticket_id = %s::uuid",
                        (ticket_uuid,),
                    )
                    # If routing was overridden by Review Agent, update final_department
                    if body.routing_overridden and body.department:
                        cur.execute(
                            """
                            UPDATE department_routing
                               SET final_department = %s
                             WHERE ticket_id = %s::uuid
                            """,
                            (body.department, ticket_uuid),
                        )
                        # Also update the ticket's department if it changed
                        cur.execute(
                            """
                            UPDATE tickets t
                               SET department_id = d.id
                              FROM departments d
                             WHERE d.name = %s
                               AND t.id = %s::uuid
                            """,
                            (body.department, ticket_uuid),
                        )
                    logger.info(
                        "review_verdict | ticket=%s verdict=approved_routing_review overridden=%s dept=%s",
                        body.ticket_code or ticket_uuid,
                        body.routing_overridden,
                        body.department,
                    )

                elif body.verdict in {"approved", "approved_operator_override"}:
                    cur.execute(
                        """
                        UPDATE tickets
                           SET status = CASE
                               WHEN department_id IS NOT NULL THEN 'Assigned'
                               ELSE 'Open'
                           END,
                               updated_at = now()
                         WHERE id = %s::uuid
                        """,
                        (ticket_uuid,),
                    )

                # Keep the final ticket row aligned with the last approved pipeline priority.
                if body.verdict != "held_operator_review" and valid_priority:
                    final_priority_title = final_priority.capitalize()
                    cur.execute(
                        """
                        UPDATE tickets
                        SET priority = %s::ticket_priority,
                            model_priority = %s::ticket_priority,
                            priority_assigned_at = COALESCE(priority_assigned_at, now()),
                            updated_at = now()
                        WHERE id = %s::uuid
                        """,
                        (final_priority_title, final_priority_title, ticket_uuid),
                    )
                    if previous_ticket_priority.lower() != final_priority:
                        cur.execute(
                            """
                            INSERT INTO ticket_updates (
                              ticket_id, update_type, message
                            )
                            VALUES (%s::uuid, 'priority_change', %s)
                            """,
                            (
                                ticket_uuid,
                                f"Review Agent finalized priority from {previous_ticket_priority or 'Unknown'} to {final_priority_title}.",
                            ),
                        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("review_verdict | failed ticket=%s: %s", body.ticket_id, exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return {"ok": True, "ticket_id": ticket_uuid, "verdict": body.verdict}


# Operator — delete ticket

@api.delete("/operator/tickets/{ticket_id}")
def operator_delete_ticket(
    ticket_id: str,
    user: Dict[str, Any] = Depends(require_operator),
    _csrf: None = Depends(require_csrf),
):
    """
    Hard-delete a ticket and all related rows (cascades via FK).
    Also removes the ticket from pipeline_queue if present.
    """
    ticket_id = _sanitize_uuid(ticket_id, "ticket_id")
    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, ticket_code FROM tickets WHERE id = %s::uuid", (ticket_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Ticket not found")
            cur.execute("DELETE FROM tickets WHERE id = %s::uuid", (ticket_id,))
    return {"ok": True, "deleted_ticket_id": ticket_id}


# Attach router LAST
app.include_router(api)

# Serve uploaded files at GET /uploads/<path>
# Using FileResponse instead of StaticFiles to avoid the
# Starlette empty-directory 404 bug.
_uploads_root = os.getenv("UPLOADS_DIR", "/app/uploads")
os.makedirs(_uploads_root, exist_ok=True)

@app.get("/uploads/{file_path:path}")
async def serve_upload(file_path: str):
    full_path = os.path.join(_uploads_root, file_path)
    full_path = os.path.normpath(full_path)
    # Security: prevent path traversal outside uploads root
    if not full_path.startswith(os.path.normpath(_uploads_root)):
        raise HTTPException(status_code=403, detail="Forbidden")
    if not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    return FileResponse(full_path)