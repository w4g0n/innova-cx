# backend/api/main.py

import os
import subprocess
import time
import json
import logging
import asyncio
import hmac
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError
import httpx

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import pyotp  # for RFC 6238 TOTP
import qrcode
import io
import re as _re

# ── Analytics service (reads from materialized views) ────────────────────────
try:
    import sys
    import os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
SLA_HEARTBEAT_SECONDS = int(os.getenv("SLA_HEARTBEAT_SECONDS", "300"))
CHATBOT_PROXY_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_PROXY_TIMEOUT_SECONDS", "120"))
ANALYTICS_REFRESH_INTERVAL_SECONDS = int(os.getenv("ANALYTICS_REFRESH_INTERVAL_HOURS", "12")) * 3600
_sla_heartbeat_task: Optional[asyncio.Task] = None
_analytics_refresh_task: Optional[asyncio.Task] = None
_has_sla_policy_fn = False

# =========================================================
# App
# =========================================================
app = FastAPI(title="InnovaCX API (DB-backed)", version="0.1.0")


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
def _ensure_uploads_root() -> str:
    # Use env var if provided, otherwise default
    root = os.getenv("UPLOADS_DIR", "/app/uploads")
    os.makedirs(root, exist_ok=True)
    return root


# =========================================================
# Database helpers
# =========================================================
def build_default_dsn() -> str:
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "complaints_db")
    user = os.getenv("DB_USER", "innovacx_admin")
    password = os.getenv("DB_PASSWORD", "changeme123")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def get_dsn() -> str:
    return os.getenv("DATABASE_URL") or build_default_dsn()


def db_connect():
    try:
        return psycopg2.connect(get_dsn())
    except OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")


def _ensure_runtime_schema_compatibility() -> None:
    """
    Keeps backend compatible with older DB volumes that skipped newer SQL scripts.
    """
    try:
        with db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS asset_type TEXT;")
                cur.execute("UPDATE tickets SET asset_type = 'General' WHERE asset_type IS NULL OR btrim(asset_type) = '';")
                cur.execute("ALTER TABLE tickets ALTER COLUMN asset_type SET DEFAULT 'General';")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS priority_assigned_at TIMESTAMPTZ;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS respond_time_left_seconds INTEGER;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolve_time_left_seconds INTEGER;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution TEXT;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_model TEXT;")
                cur.execute("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_resolution_generated_at TIMESTAMPTZ;")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ticket_resolution_feedback (
                      id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                      ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
                      employee_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                      decision TEXT NOT NULL CHECK (decision IN ('accepted', 'declined_custom')),
                      suggested_resolution TEXT,
                      employee_resolution TEXT,
                      final_resolution TEXT NOT NULL,
                      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    );
                    """
                )
                # Ensure MFA columns exist even on older volumes
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT;")
                cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
    except Exception as exc:
        logger.warning("db_compat | failed to apply compatibility DDL: %s", exc)


def _ensure_analytics_mvs() -> None:
    """
    Installs analytics materialized views if they don't exist yet.
    Runs database/scripts/analytics_mvs.sql via psql using the DATABASE_URL.
    Called from startup with retry logic so it safely handles the case where
    the DB is still running its own init.sql.
    """
    MV_SQL = "/app/database/scripts/analytics_mvs.sql"
    if not os.path.exists(MV_SQL):
        logger.warning("_ensure_analytics_mvs | %s not found — skipping", MV_SQL)
        return

    required_mvs = [
        "mv_ticket_base",
        "mv_daily_volume",
        "mv_employee_daily",
        "mv_acceptance_daily",
        "mv_operator_qc_daily",
        "mv_chatbot_daily",
        "mv_sentiment_daily",
        "mv_feature_daily",
    ]

    # Check if all required MVs already exist
    try:
        row = fetch_one(
            "SELECT COUNT(*) AS cnt FROM pg_matviews "
            "WHERE schemaname='public' AND matviewname = ANY(%s)",
            (required_mvs,),
        )
        if row and int(row.get("cnt") or 0) == len(required_mvs):
            logger.info(
                "_ensure_analytics_mvs | all required MVs exist (%s/%s) — skipping install",
                int(row.get("cnt") or 0),
                len(required_mvs),
            )
            return
        logger.info(
            "_ensure_analytics_mvs | incomplete MV set (%s/%s) — installing",
            int((row or {}).get("cnt") or 0),
            len(required_mvs),
        )
    except Exception as _check_err:
        logger.info("_ensure_analytics_mvs | cannot check pg_matviews — attempting MV install anyway")

    # Parse DATABASE_URL → psql connection args
    db_url = os.getenv("DATABASE_URL", "")
    # Format: postgresql://user:pass@host:port/dbname
    try:
        import urllib.parse as _urlparse
        p = _urlparse.urlparse(db_url)
        psql_env = {
            **os.environ,
            "PGPASSWORD": p.password or "",
        }
        psql_cmd = [
            "psql",
            "-h", p.hostname or "postgres",
            "-p", str(p.port or 5432),
            "-U", p.username or "postgres",
            "-d", (p.path or "/postgres").lstrip("/"),
            "-v", "ON_ERROR_STOP=1",
            "-f", MV_SQL,
        ]
        result = subprocess.run(
            psql_cmd, env=psql_env,
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            logger.info("_ensure_analytics_mvs | MVs installed successfully")
        else:
            logger.error("_ensure_analytics_mvs | install failed: %s", result.stderr[-500:])
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


def _apply_sla_policies_once(log_result: bool = False, source: str = "request") -> None:
    """
    Applies time-based SLA policies (escalation/overdue) if migration is installed.
    Safe no-op when function is unavailable.
    """
    if not _has_sla_policy_fn:
        return
    try:
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
        except Exception as _e:
            logger.warning(
                "analytics_refresh | refresh failed — will retry next cycle. err=%s", _e
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


# =========================================================
# Auth helpers (bcrypt + JWT)
# =========================================================
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", "86400"))  # 24h
DEV_LOG_RESET_TOKENS = os.getenv("DEV_LOG_RESET_TOKENS", "true").lower() == "true"
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
    payload = {**payload, "iat": now, "exp": now + ttl_seconds}

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    sig = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(sig)
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_jwt(token: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
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
        ("customer1@innova.cx", "customer"),
        ("manager@innova.cx", "manager"),
        ("operator@innova.cx", "operator"),
        ("ahmed@innova.cx", "employee"),
        ("maria@innova.cx", "employee"),
        ("omar@innova.cx", "employee"),
        ("sara@innova.cx", "employee"),
        ("bilal@innova.cx", "employee"),
        ("fatima@innova.cx", "employee"),
        ("yousef@innova.cx", "employee"),
        ("khalid@innova.cx", "employee"),
    ]

    # Optional display names (won't break anything if missing)
    demo_names = {
        "customer1@innova.cx": "Customer One",
        "manager@innova.cx": "Manager",
        "operator@innova.cx": "Operator",
        "ahmed@innova.cx": "Ahmed Hassan",
        "maria@innova.cx": "Maria Lopez",
        "omar@innova.cx": "Omar Ali",
        "sara@innova.cx": "Sara Ahmed",
        "bilal@innova.cx": "Bilal Khan",
        "fatima@innova.cx": "Fatima Noor",
        "yousef@innova.cx": "Yousef Karim",
        "khalid@innova.cx": "Khalid Musa",
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
    _ensure_runtime_schema_compatibility()

    # ✅ permanent dev seed (works even with existing DB volume)
    _ensure_dev_seed_users()

    # ── Wire analytics service to DB helpers and warm-up refresh ─────────────
    if _ANALYTICS_READY:
        try:
            _analytics.init(fetch_one, fetch_all, db_connect)
            # ── Self-healing: install MVs if zzz_analytics_mvs.sh was skipped ──
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

    # ── Start background MV refresh loop ─────────────────────────────────────
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


# =========================================================
# Auth dependencies
# =========================================================
def _get_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    return parts[1].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _get_bearer_token(authorization)
    payload = verify_jwt(token)
    user = fetch_one(
        # ✅ include totp_secret + mfa_enabled so totp_setup can work correctly
        "SELECT id, email, role, is_active, totp_secret, mfa_enabled FROM users WHERE id = %s",
        (payload.get("sub"),),
    )
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    return user


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

# =========================================================
# Recurring complaint prediction
# =========================================================
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


CHATBOT_URL = os.getenv("CHATBOT_URL", "http://chatbot:8000")
CHATBOT_URL_LOCAL = os.getenv("CHATBOT_URL_LOCAL", "http://localhost:8001")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8004")
ORCHESTRATOR_URL_LOCAL = os.getenv("ORCHESTRATOR_URL_LOCAL", "http://localhost:8004")


def _generate_resolution_suggestion(ticket: Dict[str, Any]) -> str:
    payload = {
        "ticket_code": ticket.get("ticket_code"),
        "ticket_type": ticket.get("ticket_type") or "Complaint",
        "subject": ticket.get("subject") or "No subject",
        "details": ticket.get("details") or "",
        "asset_type": ticket.get("asset_type") or "General",
        "priority": ticket.get("priority") or "Medium",
        "department": ticket.get("department_name") or "General",
        "status": ticket.get("status") or "Assigned",
    }
    last_error = None
    for base in [CHATBOT_URL, CHATBOT_URL_LOCAL]:
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{base}/api/suggest-resolution", json=payload)
                resp.raise_for_status()
                data = resp.json()
                suggestion = str(data.get("suggested_resolution") or "").strip()
                if suggestion:
                    return suggestion
        except Exception as exc:
            last_error = exc
            continue
    raise HTTPException(status_code=503, detail=f"Resolution suggestion service unavailable: {last_error}")

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

def _trigger_resolution_retraining() -> None:
    for base in [CHATBOT_URL, CHATBOT_URL_LOCAL]:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(f"{base}/api/retrain-resolution-model", json={"max_examples": 12})
                resp.raise_for_status()
                logger.info("resolution_retrain | triggered via %s", base)
                return
        except Exception:
            continue
    logger.warning("resolution_retrain | failed to trigger retraining endpoint")


def _trigger_priority_relearning(ticket_id: str, approved_priority: str, retrain_now: bool = False) -> None:
    payload = {
        "ticket_id": str(ticket_id),
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
                    ticket_id,
                    approved_priority,
                )
                return
        except Exception:
            continue
    logger.warning(
        "priority_relearn | failed to trigger for ticket=%s label=%s",
        ticket_id,
        approved_priority,
    )


def _generate_suggestion_if_ready(ticket_code: str) -> None:
    """
    Generate and persist suggested resolution once ticket has both:
      - first priority assignment timestamp
      - assigned department
    """
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
        LIMIT 1;
        """,
        (ticket_code,),
    )
    if not row:
        return
    if not row.get("priority_assigned_at") or not row.get("department_name"):
        return
    if str(row.get("suggested_resolution") or "").strip():
        return

    suggestion = _generate_resolution_suggestion(row)
    execute(
        """
        UPDATE tickets
        SET
          suggested_resolution = %s,
          suggested_resolution_model = %s,
          suggested_resolution_generated_at = now()
        WHERE id = %s;
        """,
        (suggestion, "falcon", row["id"]),
    )

# =========================================================
# Helpers for response/resolution time
# =========================================================
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


# =========================================================
# Models
# =========================================================
class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyTOTPRequest(BaseModel):
    login_token: str
    otp_code: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# =========================================================
# Routes: Health & Root
# =========================================================
@api.get("/health")
def health():
    row = fetch_one("SELECT NOW() as db_time;")
    db_time = row["db_time"]
    return {"ok": True, "dbTime": db_time.isoformat()}


@api.get("/")
def api_root():
    return {"message": "InnovaCX API is running", "time": datetime.now(timezone.utc).isoformat()}


# ----------------------------
# MFA / TOTP Setup & Verification
# ----------------------------
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
def login(body: LoginRequest):
    """
    Login route returns a temporary token.
    If MFA is not yet enabled, frontend should show QR code.
    """
    email = body.email.strip().lower()
    user = fetch_one(
        "SELECT id, email, password_hash, role, is_active, totp_secret, mfa_enabled FROM users WHERE email = %s",
        (email,),
    )

    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    execute("UPDATE users SET last_login_at = NOW() WHERE id = %s", (user["id"],))

    # Bypass TOTP when explicitly disabled (dev/demo only — set DISABLE_MFA=true in .env on VM)
    if DISABLE_MFA:
        access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "requiresSetup": False,
            "user": {
                "id": str(user["id"]),
                "email": user["email"],
                "role": user["role"],
            },
        }

    # Generate secret if missing
    if not user.get("totp_secret"):
        secret = pyotp.random_base32()
        execute("UPDATE users SET totp_secret = %s WHERE id = %s", (secret, user["id"]))
        user["totp_secret"] = secret

    # Temporary token valid for 10 minutes
    temp_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=600)

    # Flag to indicate MFA setup required
    requires_setup = not user.get("mfa_enabled", False)

    return {
        "access_token": temp_token,
        "token_type": "temporary",
        "requiresSetup": requires_setup,
        "user": {
            "id": str(user["id"]),
            "email": user["email"],
            "role": user["role"],
        },
    }

@api.post("/auth/totp-setup-complete")
def totp_setup_complete(user: Dict[str, Any] = Depends(get_current_user)):
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
def totp_verify(body: VerifyTOTPRequest):
    """
    Verifies the OTP code from user.
    If correct, marks MFA as enabled (first-time setup) and returns a full JWT.
    """
    payload = verify_jwt(body.login_token)
    user = fetch_one(
        "SELECT id, email, role, totp_secret, mfa_enabled FROM users WHERE id = %s",
        (payload.get("sub"),),
    )

    if not user or not user.get("totp_secret"):
        raise HTTPException(status_code=400, detail="TOTP not configured")

    totp = pyotp.TOTP(user["totp_secret"])
    if not totp.verify(body.otp_code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid OTP code")

    # Enable MFA if first-time verification
    if not user.get("mfa_enabled"):
        execute("UPDATE users SET mfa_enabled = TRUE WHERE id = %s", (user["id"],))

    # Issue real JWT valid for standard TTL
    access_token = create_jwt({"sub": str(user["id"])}, ttl_seconds=JWT_TTL_SECONDS)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": str(user["id"]), "email": user["email"], "role": user["role"]},
    }


# =========================================================
# Routes: Password Reset
# =========================================================
@api.post("/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest):
    email = body.email.strip().lower()
    user = fetch_one(
        "SELECT id FROM users WHERE email = %s AND is_active = TRUE",
        (email,),
    )

    if user:
        raw_token = base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        execute(
            """
            INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, NOW() + interval '30 minutes')
            """,
            (user["id"], token_hash),
        )
        if DEV_LOG_RESET_TOKENS:
            print(f"[DEV] Password reset token for {email}: {raw_token}")

    return {"ok": True, "message": "If an account exists for that email, reset instructions were sent."}


@api.post("/auth/reset-password")
def reset_password(body: ResetPasswordRequest):
    raw_token = (body.token or "").strip()
    new_password = body.new_password or ""

    if len(raw_token) < 10:
        raise HTTPException(status_code=400, detail="Invalid token")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id
                FROM password_reset_tokens
                WHERE token_hash = %s AND used_at IS NULL AND expires_at > NOW()
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=400, detail="Invalid or expired token")

            new_hash = hash_password(new_password)
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, row["user_id"]))
            cur.execute("UPDATE password_reset_tokens SET used_at = NOW() WHERE id = %s", (row["id"],))

    return {"ok": True, "message": "Password updated successfully"}

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@api.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: Dict[str, Any] = Depends(get_current_user),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters.")
    if len(body.new_password) > 128:
        raise HTTPException(status_code=422, detail="Password too long.")
    row = fetch_one("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    if not row or not verify_password(body.current_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    execute("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(body.new_password), user["id"]))
    return {"ok": True}
    
# =========================================================
# Employee Dashboard (EmployeeDashboard.jsx)
# =========================================================
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
        ORDER BY er.created_at DESC
        LIMIT 6;
        """,
        (user_id,),
    )

    return {"employee": employee, "kpis": kpis, "tickets": tickets, "reports": reports}


# =========================================================
# Employee View All Complaints (EmployeeViewAllComplaints.jsx)
# ONLY tickets assigned to this employee
# =========================================================
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
        first_response_at = r.get("first_response_at")
        resolved_at = r.get("resolved_at")

        issue_date = created_at.date().isoformat() if created_at else ""

        resp_base = priority_assigned_at or assigned_at or created_at
        resp_mins = diff_minutes(first_response_at, resp_base)
        response_time = minutes_to_label(resp_mins)

        res_base = priority_assigned_at or created_at
        res_mins = diff_minutes(resolved_at, res_base)
        resolution_time = minutes_to_label(res_mins)

        tickets.append(
            {
                "ticketId": r.get("ticket_code"),
                "subject": r.get("subject"),
                "priority": r.get("priority"),
                "status": r.get("status"),
                "issueDate": issue_date,
                "responseTime": response_time,
                "resolutionTime": resolution_time,
            }
        )

    return {"tickets": tickets}


# =========================================================
# SLA Summary
# =========================================================
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

# =========================================================
# Employee Notifications (EmployeeNotifications.jsx)
# =========================================================

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
        suggestion = _generate_resolution_suggestion(row)
        execute(
            """
            UPDATE tickets
            SET
              suggested_resolution = %s,
              suggested_resolution_model = %s,
              suggested_resolution_generated_at = now()
            WHERE id = %s;
            """,
            (suggestion, "falcon", row["id"]),
        )

    return {"ticketId": row["ticket_code"], "suggestedResolution": suggestion}


@api.get("/employee/tickets/{ticket_code}")
def employee_ticket_details(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_employee),
):
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
          t.first_response_at,
          t.resolved_at,
          t.suggested_resolution,
          t.model_suggestion,
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
    first_response_at = row.get("first_response_at")
    resolved_at = row.get("resolved_at")

    issue_date = created_at.date().isoformat() if created_at else ""

    resp_base = priority_assigned_at or assigned_at or created_at
    resp_mins = diff_minutes(first_response_at, resp_base)
    response_time = minutes_to_label(resp_mins)

    res_base = priority_assigned_at or created_at
    res_mins = diff_minutes(resolved_at, res_base)
    resolution_time = minutes_to_label(res_mins)

    ticket = {
        "ticketId": row.get("ticket_code"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "issueDate": issue_date,
        "modelSuggestion": row.get("suggested_resolution") or row.get("model_suggestion"),
        "metrics": {
            "meanTimeToRespond": response_time,
            "meanTimeToResolve": resolution_time,
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
):
    user_id = user["id"]
    decision = (body.decision or "").strip().lower()
    if decision not in {"accepted", "declined_custom"}:
        raise HTTPException(status_code=422, detail="decision must be 'accepted' or 'declined_custom'")

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                  id, ticket_code, status, suggested_resolution
                FROM tickets
                WHERE ticket_code = %s
                  AND assigned_to_user_id = %s
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
                INSERT INTO ticket_resolution_feedback (
                  ticket_id,
                  employee_user_id,
                  decision,
                  suggested_resolution,
                  employee_resolution,
                  final_resolution
                )
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    row["id"],
                    user_id,
                    decision,
                    suggested_resolution or None,
                    (body.final_resolution or "").strip() or None,
                    final_resolution,
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

    logger.info(
        "ticket_status_update | ticket_id=%s status=%s resolved_at=%s",
        row["ticket_code"],
        row["status"],
        row["resolved_at"],
    )
    _trigger_resolution_retraining()

    return {
        "ok": True,
        "ticketId": row["ticket_code"],
        "status": row["status"],
        "decision": decision,
        "finalResolution": row.get("final_resolution"),
        "resolvedAt": row["resolved_at"].isoformat() if row.get("resolved_at") else None,
    }


# =========================================================
# Employee: Upload attachment for a ticket
# =========================================================
@api.post("/employee/tickets/{ticket_code}/attachments")
async def employee_upload_attachment(
    ticket_code: str,
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(require_employee),
):
    """
    Stores an uploaded file under <UPLOADS_DIR>/<ticket_code>/<filename>
    and records it in ticket_attachments.
    """
    user_id = user["id"]

    row = fetch_one(
        "SELECT id FROM tickets WHERE ticket_code = %s AND assigned_to_user_id = %s LIMIT 1;",
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    ticket_id = row["id"]

    safe_name = os.path.basename(file.filename or "attachment").replace(" ", "_")

    uploads_root = _ensure_uploads_root()
    upload_dir = os.path.join(uploads_root, ticket_code)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, safe_name)

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload")

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


# =========================================================
# Employee Rescore + Reroute (ComplaintDetails.jsx)
# =========================================================

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
):
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

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO approval_requests (
                  request_code, ticket_id, request_type,
                  current_value, requested_value,
                  request_reason, submitted_by_user_id,
                  submitted_at, status
                )
                VALUES (%s, %s, 'Rescoring', %s, %s, %s, %s, now(), 'Pending')
                RETURNING request_code;
                """,
                (
                    request_code,
                    row["id"],
                    f"Priority: {current_priority}",
                    f"Priority: {new_priority}",
                    reason,
                    user_id,
                ),
            )
            result = cur.fetchone()

            profile = fetch_one(
                "SELECT full_name FROM user_profiles WHERE user_id = %s", (user_id,)
            ) or {}
            employee_name = profile.get("full_name") or user.get("email", "An employee")

            manager_row = fetch_one("SELECT id FROM users WHERE role = 'manager' LIMIT 1;")
            if manager_row and str(manager_row["id"]) != str(user_id):
                _insert_notification(
                    cur,
                    user_id=str(manager_row["id"]),
                    notif_type="ticket_assignment",
                    title=f"Rescoring Request — {ticket_code}",
                    message=f"{employee_name} requested a priority change for {ticket_code}: {current_priority} → {new_priority}. Reason: {reason}",
                    ticket_id=str(row["id"]),
                    priority=new_priority,
                )

            _insert_notification(
                cur,
                user_id=str(user_id),
                notif_type="ticket_assignment",
                title=f"Rescoring Request Submitted — {ticket_code}",
                message=f"You requested a priority change for {ticket_code}: {current_priority} → {new_priority}. Reason: {reason}. Awaiting manager approval.",
                ticket_id=str(row["id"]),
                priority=new_priority,
            )

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
):
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

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO approval_requests (
                  request_code, ticket_id, request_type,
                  current_value, requested_value,
                  request_reason, submitted_by_user_id,
                  submitted_at, status
                )
                VALUES (%s, %s, 'Rerouting', %s, %s, %s, %s, now(), 'Pending')
                RETURNING request_code;
                """,
                (
                    request_code,
                    row["id"],
                    f"Dept: {current_dept}",
                    f"Dept: {new_dept_name}",
                    reason,
                    user_id,
                ),
            )
            result = cur.fetchone()

            # Only notify the employee themselves (confirmation)
            # Manager is notified by the DB trigger notify_manager_on_approval_request
            _insert_notification(
                cur,
                user_id=str(user_id),
                notif_type="ticket_assignment",
                title=f"Rerouting Request Submitted — {ticket_code}",
                message=f"You requested a department change for {ticket_code}: {current_dept} → {new_dept_name}. Reason: {reason}. Awaiting manager approval.",
                ticket_id=str(row["id"]),
                priority=None,
            )

    logger.info(
        "employee_reroute | ticket=%s from=%s to=%s request=%s",
        ticket_code,
        current_dept,
        new_dept_name,
        result["request_code"],
    )
    return {"ok": True, "requestCode": result["request_code"], "status": "Pending"}


# =========================================================
# Employee Report Helpers
# =========================================================

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
    Uses mv_employee_daily and mv_acceptance_daily for fast pre-aggregated data.
    Returns the report_code on success, or None if the employee had no activity.
    """
    from datetime import date
    period_start = date(year, month, 1)
    period_end   = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    # ── activity check via MV ─────────────────────────────────────────────────
    activity = fetch_one(
        """
        SELECT SUM(total) AS cnt
        FROM mv_employee_daily
        WHERE employee_id = %s
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    )
    if not activity or (activity.get("cnt") or 0) == 0:
        return None

    user_slug_row = fetch_one(
        "SELECT split_part(email, '@', 1) AS slug FROM users WHERE id = %s",
        (user_id,),
    ) or {}
    user_slug = str(user_slug_row.get("slug") or "").strip().lower()
    if not user_slug:
        user_slug = str(user_id).replace("-", "")[:8]

    # Keep year in the second token for existing ORDER BY logic:
    # mon-year-user (e.g. mar-2026-ahmed)
    report_code = f"{_MONTH_ABBR[month]}-{year}-{user_slug}"
    month_label = f"{_MONTH_LABEL[month]} {year}"

    # ── aggregate KPIs from mv_employee_daily ─────────────────────────────────
    kpi_row = fetch_one(
        """
        SELECT
            SUM(total)    AS total,
            SUM(resolved) AS resolved,
            ROUND(
                SUM(total - breached)::numeric / NULLIF(SUM(total), 0) * 100, 1
            ) AS sla_pct,
            ROUND(
                SUM(avg_respond_mins * total) / NULLIF(SUM(total), 0), 1
            ) AS avg_response_mins
        FROM mv_employee_daily
        WHERE employee_id = %s
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    ) or {}

    total    = int(kpi_row.get("total")    or 0)
    resolved = int(kpi_row.get("resolved") or 0)
    sla_pct  = float(kpi_row.get("sla_pct") or 0)
    avg_resp = kpi_row.get("avg_response_mins")

    resolve_rate = round(resolved / total * 100, 1) if total else 0
    kpi_rating   = round((resolve_rate * 0.5) + (sla_pct * 0.5), 1)
    subtitle     = f"{resolved} of {total} tickets resolved · {sla_pct}% SLA compliance"

    # ── upsert employee_reports row ───────────────────────────────────────────
    existing = fetch_one(
        "SELECT id FROM employee_reports WHERE report_code = %s AND employee_user_id = %s",
        (report_code, user_id),
    )
    if existing:
        execute(
            """
            UPDATE employee_reports SET
                month_label = %s, subtitle = %s,
                kpi_rating = %s, kpi_resolved = %s, kpi_sla = %s, kpi_avg_response = %s,
                created_at = NOW()
            WHERE id = %s
            """,
            (month_label, subtitle, kpi_rating, resolved, sla_pct, avg_resp, existing["id"]),
        )
        report_id = existing["id"]
    else:
        row = fetch_one(
            """
            INSERT INTO employee_reports
                (employee_user_id, report_code, month_label, subtitle,
                 kpi_rating, kpi_resolved, kpi_sla, kpi_avg_response)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, report_code, month_label, subtitle,
             kpi_rating, resolved, sla_pct, avg_resp),
        )
        if not row:
            return None
        report_id = row["id"]

    # ── summary items (includes AI Acceptance Rate from mv_acceptance_daily) ──
    execute("DELETE FROM employee_report_summary_items WHERE report_id = %s", (report_id,))

    acceptance_data = fetch_one(
        """
        SELECT
            SUM(total)    AS total_resolutions,
            SUM(accepted) AS accepted_count
        FROM mv_acceptance_daily
        WHERE employee_id = %s
          AND created_day >= %s AND created_day < %s
        """,
        (user_id, period_start, period_end),
    )
    acceptance_rate = None
    if acceptance_data and acceptance_data.get("total_resolutions"):
        acceptance_rate = round(
            (acceptance_data["accepted_count"] / acceptance_data["total_resolutions"]) * 100, 1
        )

    summary_items = [
        ("Tickets Assigned",   str(total)),
        ("Tickets Resolved",   str(resolved)),
        ("SLA Compliance",     f"{sla_pct}%"),
        ("Avg First Response", f"{round(avg_resp)} min" if avg_resp else "N/A"),
        ("AI Acceptance Rate", f"{acceptance_rate}%" if acceptance_rate is not None else "N/A"),
    ]
    for label, value in summary_items:
        execute(
            "INSERT INTO employee_report_summary_items (report_id, label, value_text) VALUES (%s, %s, %s)",
            (report_id, label, value),
        )

    logger.info("report_gen | generated report=%s user=%s (MV-based)", report_code, user_id)
    return report_code


def _ensure_recent_reports(user_id: str, months: int = 3) -> None:
    """Ensure the employee has a report for each of the last `months` calendar months."""
    today = datetime.now(tz=timezone.utc)
    year, month = today.year, today.month
    for _ in range(months):
        existing = fetch_one(
            "SELECT id FROM employee_reports WHERE report_code = %s AND employee_user_id = %s",
            (f"{_MONTH_ABBR[month]}-{year}", user_id),
        )
        if not existing:
            _generate_employee_report(user_id, year, month)
        if month == 1:
            month = 12
            year -= 1
        else:
            month -= 1

@api.get("/employee/reports")
def employee_reports_list(user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]

    # Auto-generate reports for the last 3 months if they don't exist yet
    # This means every employee always has at least their current-month report
    try:
        _ensure_recent_reports(user_id, months=3)
    except Exception as exc:
        logger.warning("report_gen | auto-ensure failed user=%s err=%s", user_id, exc)

    rows = fetch_all(
        """
        SELECT
          report_code AS "id",
          month_label AS "month",
          subtitle    AS "subtitle",
          created_at  AS "createdAt"
        FROM employee_reports
        WHERE employee_user_id = %s
        AND report_code ~ '^[a-z]{3}-[0-9]{4}$'
        ORDER BY
        split_part(report_code, '-', 2)::int DESC,
        CASE split_part(report_code, '-', 1)
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


# ── IMPORTANT: this route MUST come before /{report_code} so FastAPI
# doesn't swallow "generate" as a report_code path param. ────────────────────
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


# -----------------------------
# Customer Dashboard
# -----------------------------
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


# -----------------------------
# Customer History (All Tickets)
# -----------------------------
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
          first_response_at,
          resolved_at
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
        first_response_at = r.get("first_response_at")
        resolved_at = r.get("resolved_at")

        issue_date = created_at.date().isoformat() if created_at else ""
        resp_base = priority_assigned_at or assigned_at or created_at
        resp_mins = diff_minutes(first_response_at, resp_base)
        response_time = minutes_to_label(resp_mins)
        res_base = priority_assigned_at or created_at
        res_mins = diff_minutes(resolved_at, res_base)
        resolution_time = minutes_to_label(res_mins)

        tickets.append(
            {
                "ticketId": r.get("ticket_code"),
                "subject": r.get("subject"),
                "priority": r.get("priority"),
                "ticketType": r.get("ticket_type"),
                "status": r.get("status"),
                "issueDate": issue_date,
                "responseTime": response_time,
                "resolutionTime": resolution_time,
            }
        )

    return {"tickets": tickets}


# -----------------------------
# Customer Ticket Details
# -----------------------------
@api.get("/customer/tickets/{ticket_code}")
def customer_ticket_details(
    ticket_code: str,
    user: Dict[str, Any] = Depends(require_customer),
):
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
          t.created_at,
          t.priority_assigned_at,
          t.assigned_at,
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

    # ✅ Ticket Updates
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
    first_response_at = row.get("first_response_at")
    resolved_at = row.get("resolved_at")

    issue_date = created_at.date().isoformat() if created_at else ""
    resp_base = priority_assigned_at or assigned_at or created_at
    resp_mins = diff_minutes(first_response_at, resp_base)
    response_time = minutes_to_label(resp_mins)
    res_base = priority_assigned_at or created_at
    res_mins = diff_minutes(resolved_at, res_base)
    resolution_time = minutes_to_label(res_mins)

    ticket = {
        "ticketId": row.get("ticket_code"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "issueDate": issue_date,
        "modelSuggestion": row.get("model_suggestion"),
        "assignedEmployee": row.get("assigned_employee_name") or None,
        "metrics": {
            "meanTimeToRespond": response_time,
            "meanTimeToResolve": resolution_time,
        },
        "description": {
            "subject": row.get("subject"),
            "details": row.get("details"),
        },
        "attachments": [{"fileName": a["file_name"], "fileUrl": a["file_url"]} for a in atts] if atts else [],

        # ✅ Added Updates Section
        "updates": [
            {
                "message": u.get("message"),
                "type": u.get("update_type"),
                "author": u.get("author_name"),
                "date": u.get("created_at").isoformat() if u.get("created_at") else None,
            }
            for u in updates_rows
        ],
    }

    return {"ticket": ticket}


# -----------------------------
# Customer Notifications Popup
# -----------------------------
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

# -----------------------------
# Customer Create Ticket
# -----------------------------
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
    attachments: Optional[List[TicketAttachment]] = []
    sentiment: Optional[dict] = None


@api.post("/customer/tickets")
def create_customer_ticket(
    body: CreateTicketRequest,
    user: Dict[str, Any] = Depends(require_customer),
):
    # Generate a unique ticket code (could also use DB sequence)
    ticket_code = f"CX-{int(time.time())}-{user['id']}"
    is_recurring = predict_is_recurring(user_id=user["id"], subject=body.subject, details=body.details)
    model_suggestion = json.dumps({"is_recurring": is_recurring})

    # Insert ticket into database
    ticket_id = None
    with db_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tickets (
                    ticket_code,
                    ticket_type,
                    subject,
                    details,
                    asset_type,
                    priority,
                    status,
                    created_by_user_id,
                    model_suggestion,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
                """,
                (
                    ticket_code,
                    body.type,         
                    body.subject,
                    body.details,
                    body.asset_type,
                    "Low",
                    "Unassigned",
                    user["id"],
                    model_suggestion,
                ),
            )
            ticket_id = cur.fetchone()[0]

            # Insert attachments if any
            for att in body.attachments or []:
                cur.execute(
                    """
                    INSERT INTO ticket_attachments (ticket_id, file_name)
                    VALUES (%s, %s);
                    """,
                    (ticket_id, att.name),
                )

    return {
        "ok": True,
        "message": "Ticket created successfully",
        "ticket": {
            "ticketId": ticket_code,
            "ticketType": body.type, 
            "subject": body.subject,
            "priority": "Normal",
            "status": "New",
            "is_recurring": is_recurring,
        },
    }

# -----------------------------
# Customer Settings - GET
# -----------------------------
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

# -----------------------------
# Customer Settings - UPDATE
# -----------------------------
@api.put("/customer/setting")
def update_customer_settings(
    payload: Dict[str, Any],
    user: Dict[str, Any] = Depends(require_customer),
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

# -----------------------------
# Manager View
# -----------------------------

@api.get("/manager/employees")
def get_employees(user: Dict[str, Any] = Depends(require_manager)):
    employees = fetch_all("""
        SELECT
            up.full_name AS name,
            up.employee_code AS id,
            up.job_title AS role,
            u.id AS user_id
        FROM user_profiles up
        JOIN users u ON u.id = up.user_id
        WHERE up.job_title NOT IN ('Customer', 'Department Manager')
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


 #-------------------------------------------------------------

@api.get("/manager/complaints")
def get_complaints(user: Dict[str, Any] = Depends(require_manager)):
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

@app.patch("/manager/complaints/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    body: AssignTicketBody,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
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
                updated_at          = NOW(),
                status              = CASE
                                        WHEN status = 'Unassigned' THEN 'Assigned'::ticket_status
                                        ELSE status
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
                updated_at          = NOW(),
                status              = 'Unassigned'
            WHERE id = %s
            """,
            (ticket_id,),
        )
        return {"ticket_id": ticket_id, "assigned_to": None, "action": "unassigned"}
class RouteTicketBody(BaseModel):
    department: str

@app.patch("/manager/complaints/{ticket_id}/resolve")
def manager_resolve_ticket(
    ticket_id: str,
    body: ManagerResolveRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
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
            
            # 4. Fetch assigned employee + customer user IDs and ticket priority
            cur.execute(
                """
                SELECT
                    t.assigned_to_user_id,
                    t.created_by_user_id,
                    t.priority,
                    t.ticket_code
                FROM tickets t
                WHERE t.id = %s
                LIMIT 1;
                """,
                (ticket_id,),
            )
            t_info = cur.fetchone()
            ticket_code   = (t_info or {}).get("ticket_code") or ticket_id
            t_priority    = (t_info or {}).get("priority")
            assigned_uid  = (t_info or {}).get("assigned_to_user_id")
            customer_uid  = (t_info or {}).get("created_by_user_id")

            # Notify manager (confirmation)
            _insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=f"Resolved: {ticket_code}",
                message=f"You resolved ticket {ticket_code}. Resolution: {final_resolution[:120]}",
                ticket_id=ticket_id,
                priority=t_priority,
            )

            # Notify assigned employee
            if assigned_uid and str(assigned_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(assigned_uid),
                    notif_type="status_change",
                    title=f"Ticket Resolved: {ticket_code}",
                    message=f"Your ticket {ticket_code} was resolved by the manager. Resolution: {final_resolution[:120]}",
                    ticket_id=ticket_id,
                    priority=t_priority,
                )

            # Notify customer
            if customer_uid and str(customer_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(customer_uid),
                    notif_type="status_change",
                    title=f"Your Ticket Has Been Resolved: {ticket_code}",
                    message=f"Ticket {ticket_code} has been resolved. Resolution: {final_resolution[:120]}",
                    ticket_id=ticket_id,
                    priority=t_priority,
                )

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
def manager_rescore_ticket(
    ticket_id: str,
    body: ManagerRescoreRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
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

            # 4. Fetch assigned employee + priority for notifications
            cur.execute(
                "SELECT assigned_to_user_id, priority FROM tickets WHERE id = %s LIMIT 1;",
                (ticket_id,),
            )
            t_info = cur.fetchone()
            assigned_uid = (t_info or {}).get("assigned_to_user_id")
            t_priority   = (t_info or {}).get("priority")

            # Notify manager (confirmation)
            _insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=f"Priority Updated: {ticket_code}",
                message=f"You changed priority of {ticket_code} from {current_priority} to {new_priority}. Reason: {reason}",
                ticket_id=ticket_id,
                priority=t_priority,
            )

            # Notify assigned employee
            if assigned_uid and str(assigned_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(assigned_uid),
                    notif_type="status_change",
                    title=f"Priority Changed: {ticket_code}",
                    message=f"The priority of your ticket {ticket_code} was changed from {current_priority} to {new_priority} by the manager.",
                    ticket_id=ticket_id,
                    priority=t_priority,
                )

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
def route_ticket_department(
    ticket_id: str,
    body: RouteTicketBody,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
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

    # ✅ Fetch BEFORE updating so old_dept is still the current one
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

    with db_connect() as conn:
        with conn.cursor() as cur:
            _insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=f"Ticket Rerouted: {ticket_code}",
                message=f"You rerouted ticket {ticket_code} from {old_dept} to {dept_name}.",
                ticket_id=ticket_id,
                priority=t_priority,
            )

            if assigned_uid and str(assigned_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(assigned_uid),
                    notif_type="status_change",
                    title=f"Ticket Rerouted: {ticket_code}",
                    message=f"Your ticket {ticket_code} has been rerouted from {old_dept} to the {dept_name} department.",
                    ticket_id=ticket_id,
                    priority=t_priority,
                )

    return {"ticket_id": ticket_id, "department": dept_name, "action": "rerouted"}

@app.get("/manager/departments")
def get_departments(authorization: Optional[str] = Header(default=None)):
    user = get_current_user(authorization)
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")
    depts = fetch_all("SELECT name FROM departments ORDER BY name;")
    return [d["name"] for d in depts]
#============================================

@api.get("/manager")
def get_manager_kpis(user: Dict[str, Any] = Depends(require_manager)):
    row = fetch_one("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'Open')                            AS open_complaints,
            COUNT(*) FILTER (WHERE status = 'In Progress')                     AS in_progress,
            COUNT(*) FILTER (WHERE resolved_at::date = CURRENT_DATE)           AS resolved_today,
            (SELECT COUNT(*) FROM users WHERE role = 'employee')               AS active_employees,
            (SELECT COUNT(*) FROM approval_requests WHERE status = 'Pending')  AS pending_approvals
        FROM tickets;
    """)
    return {
        "openComplaints":   int(row["open_complaints"]   or 0),
        "inProgress":       int(row["in_progress"]       or 0),
        "resolvedToday":    int(row["resolved_today"]    or 0),
        "activeEmployees":  int(row["active_employees"]  or 0),
        "pendingApprovals": int(row["pending_approvals"] or 0),
    }

# ==========================

@api.get("/manager/approvals")
def get_approvals(user: Dict[str, Any] = Depends(require_manager)):
    approvals = fetch_all("""
SELECT
    ar.id AS request_id,
    t.id AS ticket_id,
    t.ticket_code,
    t.subject AS ticket_subject,
    ar.request_type AS type,
    ar.current_value AS current,
    ar.requested_value AS requested,
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
            "submittedBy": a.get("submitted_by") or "—",
            "submittedOn": submitted_on,
            "status": a.get("status") or "Pending",
            "decidedBy": a.get("decided_by") or "",
            "decisionDate": decision_date,
            "decisionNotes": a.get("decision_notes") or ""
        })

    return result


# =========================================================
# Manager: Approve / Reject an approval request
# =========================================================

class ApprovalDecisionRequest(BaseModel):
    decision: str          # "Approved" or "Rejected"
    decision_notes: Optional[str] = None

@api.patch("/manager/approvals/{request_id}")
def decide_approval(
    request_id: str,
    body: ApprovalDecisionRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
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
            if decision == "Approved":
                req_type  = ar["request_type"]
                requested = ar["requested_value"] or ""
                ticket_id = ar["ticket_id"]

                if req_type == "Rescoring":
                    new_priority = requested.replace("Priority:", "").strip()
                    allowed = {"Low", "Medium", "High", "Critical"}
                    if new_priority in allowed:
                        cur.execute(
                            "UPDATE tickets SET priority = %s WHERE id = %s;",
                            (new_priority, ticket_id),
                        )
                        relearn_ticket_id = str(ticket_id)
                        relearn_priority = new_priority

                elif req_type == "Rerouting":
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

            # ── Notifications for approval decision ──────────────────────────
            # NOTE: This block is OUTSIDE the "if decision == Approved" block
            #       so it fires for BOTH Approved AND Rejected decisions.
            cur.execute(
                """
                SELECT
                    t.ticket_code,
                    t.priority,
                    ar.submitted_by_user_id,
                    ar.request_type,
                    ar.current_value,
                    ar.requested_value
                FROM approval_requests ar
                JOIN tickets t ON t.id = ar.ticket_id
                WHERE ar.id::text = %s
                LIMIT 1;
                """,
                (request_id,),
            )
            ar_info = cur.fetchone() or {}
            notif_ticket_code = ar_info.get("ticket_code") or ""
            notif_priority    = ar_info.get("priority")
            submitter_uid     = ar_info.get("submitted_by_user_id")
            notif_req_type    = (ar_info.get("request_type") or "").lower()
            notif_current     = ar_info.get("current_value") or ""
            notif_requested   = ar_info.get("requested_value") or ""
            notif_ticket_id   = ar["ticket_id"]

            decision_word = "approved" if decision == "Approved" else "rejected"

            # Notify the employee who submitted the request
            if submitter_uid and str(submitter_uid) != str(user["id"]):
                _insert_notification(
                    cur,
                    user_id=str(submitter_uid),
                    notif_type="status_change",
                    title=f"Request {decision}: {notif_ticket_code}",
                    message=(
                        f"Your {notif_req_type} request for ticket {notif_ticket_code} "
                        f"was {decision_word} by the manager. "
                        f"Change: {notif_current} → {notif_requested}."
                    ),
                    ticket_id=str(notif_ticket_id),
                    priority=notif_priority,
                )

            # Notify the manager (confirmation to themselves)
            _insert_notification(
                cur,
                user_id=str(user["id"]),
                notif_type="status_change",
                title=f"You {decision} a Request: {notif_ticket_code}",
                message=(
                    f"You {decision_word} the {notif_req_type} request for ticket "
                    f"{notif_ticket_code}. Change: {notif_current} → {notif_requested}."
                ),
                ticket_id=str(notif_ticket_id),
                priority=notif_priority,
            )

    logger.info(
        "approval_decision | request=%s decision=%s by=%s",
        request_id, decision, user["id"],
    )
    if decision == "Approved" and relearn_ticket_id and relearn_priority:
        _trigger_priority_relearning(
            ticket_id=relearn_ticket_id,
            approved_priority=relearn_priority,
        )
    return {"ok": True, "requestId": request_id, "decision": decision}


# =========================================================
# Manager: Notifications
# =========================================================

# =========================================================

@app.get("/manager/complaints/{ticket_id}")
def get_manager_complaint_details(ticket_id: str, user: Dict[str, Any] = Depends(require_manager)):
    ticket = fetch_one("""
        SELECT
            t.id AS ticket_id,
            t.ticket_code,
            t.subject,
            t.status,
            t.details,
            t.priority,
            t.created_at,
            t.priority_assigned_at,
            t.assigned_at,
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

    issue_date = ticket["created_at"].date().isoformat() if ticket.get("created_at") else ""
    resp_base = ticket.get("priority_assigned_at") or ticket.get("assigned_at") or ticket.get("created_at")
    resp_mins = diff_minutes(ticket.get("first_response_at"), resp_base)
    respond_time = minutes_to_label(resp_mins)
    res_base = ticket.get("priority_assigned_at") or ticket.get("created_at")
    res_mins = diff_minutes(ticket.get("resolved_at"), res_base)
    resolve_time = minutes_to_label(res_mins)

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
    }

#============================================

@api.get("/manager/trends")
def get_manager_trends(
    timeRange: str = Query("This Month"),
    department: str = Query("All Departments"),
    priority: str = Query("All Priorities"),
    user: Dict[str, Any] = Depends(require_manager),
):
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

    # ── Route through analytics_service (materialized views) ─────────────────
    if _ANALYTICS_READY:
        try:
            return _analytics.get_trends_data(
                period_start=period_start,
                period_end=period_end,
                prev_start=prev_start,
                department=department,
                priority=priority,
            )
        except Exception as _svc_err:
            logger.error(
                "analytics_service.get_trends_data failed — falling back to raw SQL. err=%s",
                _svc_err
            )
            # falls through to raw SQL below

    # ── RAW SQL FALLBACK (used only if analytics_service is unavailable) ──────
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

    employee_perf = fetch_all(f"SELECT up.full_name AS name, up.employee_code AS emp_id, up.job_title AS role, COUNT(t.id) AS total, COUNT(t.id) FILTER(WHERE t.status='Resolved') AS resolved, COUNT(t.id) FILTER(WHERE t.resolve_breached OR t.respond_breached) AS breached, ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve_mins, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond_mins FROM tickets t JOIN user_profiles up ON up.user_id=t.assigned_to_user_id JOIN users u ON u.id=t.assigned_to_user_id LEFT JOIN departments d ON d.id=t.department_id WHERE u.role='employee' AND {where} GROUP BY up.full_name,up.employee_code,up.job_title ORDER BY resolved DESC", params)
    company_avg = fetch_one(f"SELECT ROUND(AVG(EXTRACT(EPOCH FROM(t.resolved_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.resolved_at IS NOT NULL),1) AS avg_resolve, ROUND(AVG(EXTRACT(EPOCH FROM(t.first_response_at-COALESCE(t.priority_assigned_at,t.created_at)))/60.0) FILTER(WHERE t.first_response_at IS NOT NULL),1) AS avg_respond, COUNT(*) FILTER(WHERE t.resolve_breached OR t.respond_breached)::float/NULLIF(COUNT(*),0)*100 AS breach_rate FROM tickets t {dept_join} WHERE {where}", params) or {}
    acceptance_rows = fetch_all("SELECT up.full_name AS name, COUNT(*) AS total, COUNT(*) FILTER(WHERE trf.decision='accepted') AS accepted, COUNT(*) FILTER(WHERE trf.decision='declined_custom') AS declined FROM ticket_resolution_feedback trf JOIN tickets t ON t.id=trf.ticket_id JOIN user_profiles up ON up.user_id=trf.employee_user_id WHERE t.created_at>=%s AND t.created_at<%s GROUP BY up.full_name", [period_start, period_end])
    acceptance_map = {r["name"]:{"total":r["total"],"accepted":r["accepted"],"declined":r["declined"],"rate":round(r["accepted"]/r["total"]*100,1) if r["total"] else 0} for r in acceptance_rows}
    rescore_rows = fetch_all(f"SELECT up.full_name AS name, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority) AS rescored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority AND((t.model_priority='Low' AND t.priority IN('Medium','High','Critical'))OR(t.model_priority='Medium' AND t.priority IN('High','Critical'))OR(t.model_priority='High' AND t.priority='Critical'))) AS upscored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL AND t.priority!=t.model_priority AND((t.model_priority='Critical' AND t.priority IN('Low','Medium','High'))OR(t.model_priority='High' AND t.priority IN('Low','Medium'))OR(t.model_priority='Medium' AND t.priority='Low'))) AS downscored, COUNT(*) FILTER(WHERE t.model_priority IS NOT NULL) AS total_with_model FROM tickets t JOIN user_profiles up ON up.user_id=t.assigned_to_user_id JOIN users u ON u.id=t.assigned_to_user_id LEFT JOIN departments d ON d.id=t.department_id WHERE u.role='employee' AND {where} GROUP BY up.full_name", params)
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
#--------------------------------------------
@api.get("/manager/notifications")
def manager_notifications(
    limit: int = Query(default=200, ge=1, le=500),
    only_unread: bool = Query(default=False),
    user: Dict[str, Any] = Depends(require_manager),   # ← use Depends, not Header
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
):
    execute(
        "UPDATE notifications SET read = TRUE WHERE user_id = %s AND read = FALSE;",
        (user["id"],),
    )
    return {"ok": True}

# =========================================================
# Operator Notifications
# =========================================================

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
):
    execute(
        "UPDATE notifications SET read = TRUE WHERE user_id = %s AND read = FALSE;",
        (user["id"],),
    )
    return {"ok": True}

# =========================================================
# Internal Orchestrator Endpoint (no JWT — Docker-network only)
# =========================================================

class OrchestratorComplaintRequest(BaseModel):
    ticket_id: Optional[str] = None
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


class ChatbotProxyRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None


@api.post("/complaints")
def create_orchestrator_complaint(body: OrchestratorComplaintRequest):
    """
    Internal endpoint called by the orchestrator service.
    Creates a ticket using the system user account (no JWT required).
    Relies on Docker-network isolation for security.
    """
    system_email = os.getenv("SYSTEM_USER_EMAIL", "customer1@innova.cx")

    row = fetch_one(
        "SELECT id FROM users WHERE email = %s LIMIT 1",
        (system_email,),
    )
    if not row:
        raise HTTPException(
            status_code=503,
            detail=f"System user '{system_email}' not found. "
                   "Set SYSTEM_USER_EMAIL to a valid user.",
        )

    system_user_id = row["id"]
    incoming_ticket_code = (body.ticket_id or "").strip() or None

    priority_map = {1: "Low", 2: "Medium", 3: "High", 4: "Critical"}
    priority_label = priority_map.get(body.priority) if body.priority is not None else None

    label = (body.label or "").strip().lower() or None
    ticket_type = "Inquiry" if label == "inquiry" else ("Complaint" if label else None)
    requested_asset_type = (body.asset_type or "").strip() or None
    requested_department = (body.department or "").strip() or None
    normalized_status = (body.status or "").strip() or None
    allowed_statuses = {
        "Open",
        "In Progress",
        "Unassigned",
        "Assigned",
        "Escalated",
        "Overdue",
        "Reopened",
        "Resolved",
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

            if incoming_ticket_code:
                cur.execute(
                    "SELECT id, priority_assigned_at FROM tickets WHERE ticket_code = %s LIMIT 1",
                    (incoming_ticket_code,),
                )
                existing = cur.fetchone()
                if existing:
                    had_priority_before = existing[1] is not None
                    subject_update = None
                    if requested_department and ticket_type:
                        subject_update = f"[{requested_department.title()}] Automated {ticket_type.lower()}"

                    details_update = body.transcript if body.transcript else None
                    now_utc = datetime.now(timezone.utc) if priority_label else None
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
                          priority_assigned_at = COALESCE(%s, priority_assigned_at)
                        WHERE ticket_code = %s
                        RETURNING ticket_code, status, priority, asset_type, priority_assigned_at, respond_due_at, resolve_due_at;
                        """,
                        (
                            ticket_type,
                            subject_update,
                            details_update,
                            requested_asset_type,
                            priority_label,
                            normalized_status,
                            department_id,
                            body.sentiment,
                            sentiment_label_update,
                            priority_label,
                            department_id,
                            body.classification_confidence,
                            now_utc,
                            incoming_ticket_code,
                        ),
                    )
                    updated = cur.fetchone()
                    logger.info(
                        "orchestrator_ticket_update | ticket_id=%s status=%s priority=%s asset_type=%s department=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                        updated[0],
                        updated[1],
                        updated[2],
                        updated[3],
                        requested_department,
                        updated[4],
                        updated[5],
                        updated[6],
                    )
                    if (not had_priority_before) and updated[4]:
                        try:
                            _generate_suggestion_if_ready(updated[0])
                        except Exception as exc:
                            logger.warning(
                                "suggested_resolution | generation failed at first priority assignment ticket=%s err=%s",
                                updated[0],
                                exc,
                            )
                    return {
                        "ticket_id": updated[0],
                        "status": updated[1],
                        "priority": updated[2],
                        "asset_type": updated[3],
                        "department": requested_department,
                        "priority_assigned_at": updated[4].isoformat() if updated[4] else None,
                        "respond_due_at": updated[5].isoformat() if updated[5] else None,
                        "resolve_due_at": updated[6].isoformat() if updated[6] else None,
                    }

            if not body.transcript:
                raise HTTPException(status_code=422, detail="transcript is required when creating a new ticket")

            ticket_code = f"CX-{int(time.time())}"
            ticket_type_create = ticket_type or "Complaint"
            priority_create = priority_label or "Medium"
            status_create = normalized_status or "Open"
            asset_type_create = requested_asset_type or "General"
            department_name_create = requested_department or "General"
            subject = f"[{department_name_create.title()}] Automated {ticket_type_create.lower()}"
            details = body.transcript

            cur.execute(
                """
                INSERT INTO tickets (
                    ticket_code,
                    ticket_type,
                    subject,
                    details,
                    asset_type,
                    priority,
                    status,
                    created_by_user_id,
                    department_id,
                    sentiment_score,
                    sentiment_label,
                    model_priority,
                    model_department_id,
                    model_confidence,
                    priority_assigned_at,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING ticket_code, status, priority, asset_type, priority_assigned_at, respond_due_at, resolve_due_at;
                """,
                (
                    ticket_code,
                    ticket_type_create,
                    subject,
                    details,
                    asset_type_create,
                    priority_create,
                    status_create,
                    system_user_id,
                    department_id,
                    body.sentiment,
                    "orchestrator",
                    priority_label,
                    department_id,
                    body.classification_confidence,
                    datetime.now(timezone.utc),
                ),
            )
            created = cur.fetchone()
            logger.info(
                "orchestrator_ticket_create | ticket_id=%s status=%s priority=%s asset_type=%s department=%s priority_assigned_at=%s respond_due_at=%s resolve_due_at=%s",
                created[0],
                created[1],
                created[2],
                created[3],
                requested_department,
                created[4],
                created[5],
                created[6],
            )
            if created[4]:
                try:
                    _generate_suggestion_if_ready(created[0])
                except Exception as exc:
                    logger.warning(
                        "suggested_resolution | generation failed at ticket creation ticket=%s err=%s",
                        created[0],
                        exc,
                    )

    return {
        "ticket_id": created[0],
        "status": created[1],
        "priority": created[2],
        "asset_type": created[3],
        "department": requested_department,
        "priority_assigned_at": created[4].isoformat() if created[4] else None,
        "respond_due_at": created[5].isoformat() if created[5] else None,
        "resolve_due_at": created[6].isoformat() if created[6] else None,
    }


@api.post("/chatbot/chat")
async def proxy_chatbot_chat(body: ChatbotProxyRequest):
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

    raise HTTPException(status_code=503, detail=f"Chatbot service unavailable: {last_error}")


@api.post("/transcriber/transcribe")
@api.post("/whisper/transcribe")
async def proxy_transcriber_transcribe(audio: UploadFile = File(...)):
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

    raise HTTPException(status_code=503, detail=f"Transcriber service unavailable: {last_error}")


# =========================================================
# OPERATOR ANALYTICS ENDPOINTS
# =========================================================
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

# =========================================================
# Operator – Quality Control / Ticket Review Detail
# =========================================================

@api.get("/operator/complaints/{ticket_id}")
def get_operator_complaint_detail(
    ticket_id: str,
    user: Dict[str, Any] = Depends(require_operator),
):
    """
    Full ticket detail for the QC TicketReviewDetail page.
    Accepts either a ticket_code (e.g. CX-0042) or a raw UUID.
    """
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

    # ── approval requests ─────────────────────────────────────────────────────
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

    # ── model execution log ───────────────────────────────────────────────────
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

    # ── ticket updates ────────────────────────────────────────────────────────
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

    # ── current-run AI outputs ────────────────────────────────────────────────
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
        SELECT decision AS feedback_decision, final_resolution
        FROM ticket_resolution_feedback
        WHERE ticket_id = %s
        LIMIT 1
        """,
        (tid,),
    )

    # ── chat sentiment series (for escalated tickets) ─────────────────────────
    chat_sentiment = fetch_all(
        """
        SELECT sentiment_score, created_at
        FROM user_chat_logs
        WHERE ticket_id = %s
        ORDER BY created_at ASC
        """,
        (tid,),
    ) or []

    # ── helpers ───────────────────────────────────────────────────────────────
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
        "assignedToName":      ticket.get("assigned_to_name") or "Unassigned",
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


# =========================================================
# Operator – User Management
# =========================================================
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
    if not raw_password or len(raw_password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    if len(raw_password) > 128:
        raise HTTPException(status_code=422, detail="Password too long (max 128 characters).")

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
):
    """Update user + profile (operator-only)."""
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
        if not body.password or len(body.password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
        if len(body.password) > 128:
            raise HTTPException(status_code=422, detail="Password too long (max 128 characters).")
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
):
    """Activate/Deactivate user (operator-only)."""
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
):
    """Delete a user (operator-only)."""
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


# =========================================================
# Attach router LAST
# =========================================================
app.include_router(api)

# =========================================================
# Serve uploaded files at GET /uploads/<path>
# Using FileResponse instead of StaticFiles to avoid the
# Starlette empty-directory 404 bug.
# =========================================================
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
