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


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
SLA_HEARTBEAT_SECONDS = int(os.getenv("SLA_HEARTBEAT_SECONDS", "300"))
CHATBOT_PROXY_TIMEOUT_SECONDS = float(os.getenv("CHATBOT_PROXY_TIMEOUT_SECONDS", "120"))
_sla_heartbeat_task: Optional[asyncio.Task] = None
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

    _has_sla_policy_fn = _detect_sla_policy_function()
    if not _has_sla_policy_fn:
        logger.warning("sla_heartbeat | disabled (apply_ticket_sla_policies() not found)")
        return
    if SLA_HEARTBEAT_SECONDS <= 0:
        logger.info("sla_heartbeat | disabled (SLA_HEARTBEAT_SECONDS=%s)", SLA_HEARTBEAT_SECONDS)
        return
    if _sla_heartbeat_task is None or _sla_heartbeat_task.done():
        _sla_heartbeat_task = asyncio.create_task(_sla_heartbeat_loop())
        logger.info("sla_heartbeat | started interval_s=%s", SLA_HEARTBEAT_SECONDS)


@app.on_event("shutdown")
async def _stop_sla_heartbeat() -> None:
    global _sla_heartbeat_task
    if _sla_heartbeat_task and not _sla_heartbeat_task.done():
        _sla_heartbeat_task.cancel()
        try:
            await _sla_heartbeat_task
        except asyncio.CancelledError:
            pass
    _sla_heartbeat_task = None


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


@api.post("/employee/tickets/{ticket_code}/rescore")
def employee_rescore_ticket(
    ticket_code: str,
    body: EmployeeRescoreRequest,
    user: Dict[str, Any] = Depends(require_employee),
):
    user_id = user["id"]
    allowed_priorities = {"Low", "Medium", "High", "Critical"}
    new_priority = (body.new_priority or "").strip()
    reason = (body.reason or "").strip()

    if new_priority not in allowed_priorities:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid priority. Must be one of: {', '.join(sorted(allowed_priorities))}",
        )
    if not reason:
        raise HTTPException(status_code=422, detail="Reason is required")

    row = fetch_one(
        """
        SELECT id, ticket_code, priority
        FROM tickets
        WHERE ticket_code = %s AND assigned_to_user_id = %s
        LIMIT 1;
        """,
        (ticket_code, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found or not assigned to you")

    current_priority = row["priority"]
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

    logger.info(
        "employee_rescore | ticket=%s from=%s to=%s request=%s",
        ticket_code,
        current_priority,
        new_priority,
        result["request_code"],
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

    logger.info(
        "employee_reroute | ticket=%s from=%s to=%s request=%s",
        ticket_code,
        current_dept,
        new_dept_name,
        result["request_code"],
    )
    return {"ok": True, "requestCode": result["request_code"], "status": "Pending"}


# =========================================================
# Employee Reports (AutoGeneratedReports.jsx)
# =========================================================

def _safe_report_code(code: str) -> str:
    code = (code or "").strip().lower()
    # Expect like "oct-2025"
    if len(code) != 8 or code[3] != "-" or not code[:3].isalpha() or not code[4:].isdigit():
        raise HTTPException(status_code=400, detail="Invalid report code")
    return code

@api.get("/employee/reports")
def employee_reports_list(user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]

    rows = fetch_all(
        """
        SELECT
          report_code AS "id",
          month_label AS "month",
          subtitle    AS "subtitle",
          created_at  AS "createdAt"
        FROM employee_reports
        WHERE employee_user_id = %s
        ORDER BY created_at DESC
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


@api.get("/employee/reports/{report_code}")
def employee_report_detail(report_code: str, user: Dict[str, Any] = Depends(require_employee)):
    user_id = user["id"]
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

@app.get("/manager/employees")
def get_employees():
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

@app.get("/manager/complaints")
def get_complaints():
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
            up.full_name AS assignee_name
        FROM tickets t
        LEFT JOIN user_profiles up ON t.assigned_to_user_id = up.user_id
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
#============================================

@app.get("/manager")
def get_manager_kpis():
    # Total complaints
    open_complaints = fetch_one(
        "SELECT COUNT(*) AS count FROM tickets WHERE status='Open';"
    )["count"]
    in_progress = fetch_one(
        "SELECT COUNT(*) AS count FROM tickets WHERE status='In Progress';"
    )["count"]
    resolved_today = fetch_one(
        "SELECT COUNT(*) AS count FROM tickets WHERE resolved_at::date = CURRENT_DATE;"
    )["count"]

    # Active employees (consider role='employee' in users table)
    active_employees = fetch_one(
        "SELECT COUNT(*) AS count FROM users WHERE role='employee';"
    )["count"]

    # Pending approvals (from approval_requests table)
    pending_approvals = fetch_one(
        "SELECT COUNT(*) AS count FROM approval_requests WHERE status='Pending';"
    )["count"]

    return {
        "open_complaints": open_complaints,
        "in_progress": in_progress,
        "resolved_today": resolved_today,
        "active_employees": active_employees,
        "pending_approvals": pending_approvals
    }

# ==========================

@app.get("/manager/approvals")
def get_approvals():
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
    user: Dict[str, Any] = Depends(require_manager),
):
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

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:

            # 1. Update the approval_requests record
            cur.execute(
                """
                UPDATE approval_requests
                SET
                    status           = %s,
                    decided_by_user_id = %s,
                    decided_at       = now(),
                    decision_notes   = %s
                WHERE id::text = %s;
                """,
                (decision, user["id"], body.decision_notes or "", request_id),
            )

            # 2. If approved, apply the change to the ticket
            if decision == "Approved":
                req_type = ar["request_type"]          # 'Rescoring' or 'Rerouting'
                requested = ar["requested_value"] or "" # e.g. "Priority: Critical" / "Dept: Security"
                ticket_id = ar["ticket_id"]

                if req_type == "Rescoring":
                    # Extract priority from "Priority: <value>"
                    new_priority = requested.replace("Priority:", "").strip()
                    allowed = {"Low", "Medium", "High", "Critical"}
                    if new_priority in allowed:
                        cur.execute(
                            "UPDATE tickets SET priority = %s WHERE id = %s;",
                            (new_priority, ticket_id),
                        )

                elif req_type == "Rerouting":
                    # Extract department name from "Dept: <name>"
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

    logger.info(
        "approval_decision | request=%s decision=%s by=%s",
        request_id, decision, user["id"],
    )
    return {"ok": True, "requestId": request_id, "decision": decision}


# =========================================================

@app.get("/manager/complaints/{ticket_id}")
def get_manager_complaint_details(ticket_id: str):
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
            up.full_name AS assignee_name
        FROM tickets t
        LEFT JOIN user_profiles up
            ON t.assigned_to_user_id = up.user_id
        WHERE t.id = %s
        LIMIT 1;
    """, (ticket_id,))

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
        "ticket_code": ticket.get("ticket_code") or "",  # add this line
        "subject": ticket.get("subject") or "",
        "priority": priority_raw,
        "priorityText": priority_text,
        "status": ticket["status"],
        "assignee": assignee,
        "details": ticket.get("details") or "",  # <-- fixed
        "issueDate": issue_date,
        "respondTime": respond_time,
        "resolveTime": resolve_time
    }

#============================================

@app.get("/manager/trends")
def get_manager_trends(
    timeRange: str = Query("This Month"),
    department: str = Query("All Departments"),
    priority: str = Query("All Priorities")
):
    # ---------- TIME RANGE ----------
    if timeRange == "Last 3 Months":
        month_start = fetch_one("SELECT now() - interval '3 months' AS start")["start"]
    elif timeRange == "Last 6 Months":
        month_start = fetch_one("SELECT now() - interval '6 months' AS start")["start"]
    elif timeRange == "Last 12 Months":
        month_start = fetch_one("SELECT now() - interval '12 months' AS start")["start"]
    else:
        month_start = fetch_one("SELECT date_trunc('month', now()) AS start")["start"]
    # ---------- FILTERS ----------
    filters = ["t.created_at >= %s"]
    params = [month_start]

    # Department filter
    if department != "All Departments":
        filters.append("d.name = %s")
        params.append(department)

   # Priority filter
    priority_map = {
        "Low": "Low",
        "Medium": "Medium",
        "High": "High",
        "Critical": "Critical",
    }
    priority_value = priority_map.get(priority)
    if priority_value:
        filters.append("t.priority = %s::ticket_priority")
        params.append(priority_value)

    where_clause = " AND ".join(filters)

    # ---------- TOTAL COMPLAINTS ----------
    total_complaints = fetch_one(
        f"""
        SELECT COUNT(*) AS count
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
        """,
        params,
    )["count"]

    # ---------- SLA ----------
    sla_row = fetch_one(
        f"""
        SELECT
          COUNT(*) FILTER (
            WHERE t.resolved_at IS NOT NULL
              AND t.resolve_due_at IS NOT NULL
              AND t.resolved_at <= t.resolve_due_at
              AND t.first_response_at IS NOT NULL
          ) AS on_time,
          COUNT(*) FILTER (
            WHERE t.resolved_at IS NOT NULL
              AND t.resolve_due_at IS NOT NULL
              AND t.first_response_at IS NOT NULL
          ) AS total
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
        """,
        params,
    )
    sla_pct = round((sla_row["on_time"] / sla_row["total"]) * 100) if sla_row["total"] else 0

    # ---------- AVERAGE RESPONSE TIME ----------
    avg_response = fetch_one(
        f"""
        SELECT
          AVG(EXTRACT(EPOCH FROM (t.first_response_at - COALESCE(t.priority_assigned_at, t.created_at))) / 60) AS mins
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.first_response_at IS NOT NULL
          AND {where_clause}
        """,
        params,
    )["mins"] or 0

    # ---------- AVERAGE RESOLVE TIME ----------
    avg_resolve = fetch_one(
        f"""
        SELECT
          AVG(EXTRACT(EPOCH FROM (t.resolved_at - COALESCE(t.priority_assigned_at, t.created_at))) / 86400) AS days
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE t.resolved_at IS NOT NULL
          AND {where_clause}
        """,
        params,
    )["days"] or 0

    # ---------- TOP CATEGORY ----------
    top_category_row = fetch_one(
        f"""
        SELECT d.name, COUNT(*) AS count
        FROM tickets t
        JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
        GROUP BY d.name
        ORDER BY count DESC
        LIMIT 1
        """,
        params,
    )
    top_category = top_category_row["name"] if top_category_row else "—"

    # ---------- REPEAT COMPLAINTS ----------
    repeat_row = fetch_one(
        f"""
        SELECT COUNT(*) AS count FROM (
          SELECT t.created_by_user_id, t.department_id
          FROM tickets t
          LEFT JOIN departments d ON d.id = t.department_id
          WHERE {where_clause}
          GROUP BY t.created_by_user_id, t.department_id
          HAVING COUNT(*) > 1
        ) r
        """,
        params,
    )
    repeat_pct = round((repeat_row["count"] / total_complaints) * 100) if total_complaints else 0

    # ---------- MONTHLY BARS ----------
    bars = fetch_all(
        f"""
        SELECT
          to_char(t.created_at, 'Mon') AS label,
          COUNT(*) AS value
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
        GROUP BY label, date_trunc('month', t.created_at)
        ORDER BY date_trunc('month', t.created_at)
        """,
        params,
    )

    # ---------- CATEGORY SHARE ----------
    categories = fetch_all(
        f"""
        SELECT
          d.name AS name,
          ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER ()) AS pct
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
          AND d.name IS NOT NULL
        GROUP BY d.name
        ORDER BY pct DESC
        """,
        params,
    )

# =========================================================
# MONTHLY TABLE
# =========================================================
    table = fetch_all(
        f"""
        SELECT
          to_char(t.created_at, 'Month') AS month,
          COUNT(*) AS total,
          COUNT(*) FILTER (WHERE t.status = 'Resolved') AS resolved,
          ROUND(
            COUNT(*) FILTER (
              WHERE t.resolved_at <= t.resolve_due_at
                AND t.first_response_at IS NOT NULL
            ) * 100.0 / NULLIF(COUNT(*), 0)
          ) AS within_sla,
          ROUND(
            AVG(EXTRACT(EPOCH FROM (t.first_response_at - COALESCE(t.priority_assigned_at, t.created_at))) / 60)
          ) AS avg_response,
          ROUND(
            AVG(EXTRACT(EPOCH FROM (t.resolved_at - COALESCE(t.priority_assigned_at, t.created_at))) / 86400), 1
          ) AS avg_resolve
        FROM tickets t
        LEFT JOIN departments d ON d.id = t.department_id
        WHERE {where_clause}
        GROUP BY date_trunc('month', t.created_at), month
        ORDER BY date_trunc('month', t.created_at)
        """,
        params,
    )

    return {
        "kpis": {
            "complaints": total_complaints,
            "sla": f"{sla_pct}%",
            "response": f"{round(avg_response)} mins",
            "resolve": f"{round(avg_resolve,1)} days",
            "topCategory": top_category,
            "repeat": f"{repeat_pct}%"
        },
        "bars": bars,
        "categories": categories,
        "table": table
    }
#--------------------------------------------
@app.get("/manager/notifications")
def manager_notifications(
    limit: int = Query(default=200, ge=1, le=500),
    only_unread: bool = Query(default=False),
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

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


@app.post("/manager/notifications/{notification_id}/read")
def manager_notification_mark_read(
    notification_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

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


@app.post("/manager/notifications/read-all")
def manager_notifications_mark_all_read(
    authorization: Optional[str] = Header(default=None),
):
    user = get_current_user(authorization)
    if user.get("role") != "manager":
        raise HTTPException(status_code=403, detail="Forbidden")

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
