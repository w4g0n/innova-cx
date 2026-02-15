# backend/api/main.py

import os
import time
import json
import hmac
import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

import bcrypt
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import pyotp  # for RFC 6238 TOTP
import qrcode
import io



# =========================================================
# App
# =========================================================
app = FastAPI(title="InnovaCX API (DB-backed)", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")


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
        "SELECT id, email, role, is_active FROM users WHERE id = %s",
        (payload.get("sub"),),
    )
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Invalid or inactive user")
    return user


def require_employee(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "employee":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


def require_customer(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user


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
        assigned_at = r.get("assigned_at")
        first_response_at = r.get("first_response_at")
        resolved_at = r.get("resolved_at")

        issue_date = created_at.date().isoformat() if created_at else ""

        resp_base = assigned_at or created_at
        resp_mins = diff_minutes(first_response_at, resp_base)
        response_time = minutes_to_label(resp_mins)

        res_mins = diff_minutes(resolved_at, created_at)
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
          AVG(EXTRACT(EPOCH FROM (first_response_at - COALESCE(assigned_at, created_at))) / 60.0)
            FILTER (WHERE first_response_at IS NOT NULL) AS avg_response_mins,
          AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60.0)
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
          t.assigned_at,
          t.first_response_at,
          t.resolved_at,
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
        SELECT file_name
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
    assigned_at = row.get("assigned_at")
    first_response_at = row.get("first_response_at")
    resolved_at = row.get("resolved_at")

    issue_date = created_at.date().isoformat() if created_at else ""

    resp_base = assigned_at or created_at
    resp_mins = diff_minutes(first_response_at, resp_base)
    response_time = minutes_to_label(resp_mins)

    res_mins = diff_minutes(resolved_at, created_at)
    resolution_time = minutes_to_label(res_mins)

    ticket = {
        "ticketId": row.get("ticket_code"),
        "priority": row.get("priority"),
        "status": row.get("status"),
        "issueDate": issue_date,
        "modelSuggestion": row.get("model_suggestion"),
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
        "attachments": [a["file_name"] for a in atts] if atts else [],
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
        assigned_at = r.get("assigned_at")
        first_response_at = r.get("first_response_at")
        resolved_at = r.get("resolved_at")

        issue_date = created_at.date().isoformat() if created_at else ""
        resp_base = assigned_at or created_at
        resp_mins = diff_minutes(first_response_at, resp_base)
        response_time = minutes_to_label(resp_mins)
        res_mins = diff_minutes(resolved_at, created_at)
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
        SELECT file_name
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
    assigned_at = row.get("assigned_at")
    first_response_at = row.get("first_response_at")
    resolved_at = row.get("resolved_at")

    issue_date = created_at.date().isoformat() if created_at else ""
    resp_base = assigned_at or created_at
    resp_mins = diff_minutes(first_response_at, resp_base)
    response_time = minutes_to_label(resp_mins)
    res_mins = diff_minutes(resolved_at, created_at)
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
        "attachments": [a["file_name"] for a in atts] if atts else [],

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
    limit: int = Query(default=10, ge=1, le=50),  # popup usually shows only top 5-10
    only_unread: bool = Query(default=False),
    user: Dict[str, Any] = Depends(require_customer),
):
    user_id = user["id"]

    print("Customer notifications called!")

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

    # Count unread for badge
    unread_row = fetch_one(
        "SELECT COUNT(*)::int AS unread FROM notifications WHERE user_id = %s AND read = FALSE;",
        (user_id,),
    ) or {"unread": 0}

    # Format for frontend popup
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
    ticket_code = f"TKT-{int(time.time())}-{user['id']}"

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
                    priority,
                    status,
                    created_by_user_id,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id;
                """,
                (
                    ticket_code,
                    body.type,         
                    body.subject,
                    body.details,
                    "Low",
                    "Unassigned",
                    user["id"],
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
        },
    }



# =========================================================
# Attach router LAST
# =========================================================
app.include_router(api)
