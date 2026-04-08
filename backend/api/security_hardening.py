# backend/api/security_hardening.py
# Centralised security helpers imported by main.py
#
# Controls implemented here:
#   [S1]  Password complexity (length, upper, lower, digit, special)
#   [S2]  Account lockout — 5 failures → 15-min lock, keyed by email
#   [S3]  Rate limiting via slowapi (optional dep — graceful fallback)
#   [S4]  SecurityHeadersMiddleware — CSP, HSTS, X-Frame, etc.
#   [S5]  File upload validation — magic bytes, size cap, MIME allowlist
#   [S6]  Auth event logging — structured, never logs credentials
#   [S7]  (fix in main.py) — parameterised ANY(%s::uuid[]) for IN clauses
#   [S8]  (fix in main.py) — generic 404 messages
#   [S9]  (fix in main.py) — Depends(require_*) on dual-registered routes
#   [S10] (fix in main.py) — totp_setup_complete registered as a route
#
# Additional controls in this file:
#   [S11] Refresh-token table helpers  (create_refresh_token / rotate)
#   [S12] Token revocation list        (revoke_token / is_token_revoked)
#   [S13] Logout endpoint helper       (logout_user)
#   [S14] Input sanitisation utilities (_sanitize_filename, _sanitize_text)

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# [S1] Password complexity
_MIN_PASSWORD_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
_MAX_PASSWORD_LENGTH = int(os.getenv("PASSWORD_MAX_LENGTH", "128"))

# Common weak passwords that pass character-class checks
_COMMON_PASSWORDS: frozenset = frozenset(
    {
        "password", "password1", "password123", "passw0rd",
        "qwerty123", "letmein1", "welcome1", "abc123456",
        "changeme1", "admin1234", "iloveyou1",
    }
)

_COMPLEXITY_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()\-_=+\[\]{}|;:',.<>?/`~\"\\]).{"
    + str(_MIN_PASSWORD_LENGTH)
    + ","
    + str(_MAX_PASSWORD_LENGTH)
    + r"}$"
)


def validate_password_complexity(
    password: str,
    field_name: str = "Password",
    email: Optional[str] = None,
) -> None:
    """
    Raises HTTPException(422) if the password does not meet policy.

    Policy:
      - Minimum length: PASSWORD_MIN_LENGTH
      - Maximum length: PASSWORD_MAX_LENGTH 
      - At least one lowercase letter
      - At least one uppercase letter
      - At least one digit
      - At least one special character from the allowed set
      - Not on the common-password block list
      - Must not be similar to the user's email
    """
    if not password:
        raise HTTPException(status_code=422, detail=f"{field_name} is required.")

    if len(password) < _MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must be at least {_MIN_PASSWORD_LENGTH} characters.",
        )

    if len(password) > _MAX_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} must not exceed {_MAX_PASSWORD_LENGTH} characters.",
        )

    if password.lower() in _COMMON_PASSWORDS:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} is too common. Choose a less predictable password.",
        )

    if email:
        email_value = (email or "").strip().lower()
        local_part = email_value.split("@", 1)[0]
        password_lower = password.lower()

        # direct similarity check
        if local_part and (local_part in password_lower or password_lower in local_part):
            raise HTTPException(
                status_code=422,
                detail=f"{field_name} must not be similar to your email.",
            )

        # normalized similarity check (remove symbols/numbers separators)
        normalized_local = re.sub(r"[^a-z0-9]", "", local_part)
        normalized_password = re.sub(r"[^a-z0-9]", "", password_lower)

        if normalized_local and normalized_local in normalized_password:
            raise HTTPException(
                status_code=422,
                detail=f"{field_name} must not be similar to your email.",
            )

    if not _COMPLEXITY_RE.match(password):
        raise HTTPException(
            status_code=422,
            detail=(
                f"{field_name} must contain at least one uppercase letter, "
                "one lowercase letter, one digit, and one special character "
                "(!@#$%^&*()-_=+[]{}|;:',.<>?/`~\"\\)."
            ),
        )


# [S2] Account lockout (in-process store — fine for single-instance)
#      For multi-instance deployments, replace _lockout_store with
#      a shared Redis backend.
_LOCKOUT_MAX_ATTEMPTS: int = int(os.getenv("LOCKOUT_MAX_ATTEMPTS", "5"))
_LOCKOUT_WINDOW_SECONDS: int = int(os.getenv("LOCKOUT_WINDOW_SECONDS", "900"))  # 15 min

# { email_lower: {"count": int, "first_fail": float, "locked_until": float} }
_lockout_store: Dict[str, Dict[str, Any]] = defaultdict(
    lambda: {"count": 0, "first_fail": 0.0, "locked_until": 0.0}
)


def is_account_locked(email: str) -> bool:
    """Return True when the account is in a lockout period."""
    key = email.strip().lower()
    entry = _lockout_store[key]
    if entry["locked_until"] > time.time():
        return True
    # Expired lock — reset silently so a subsequent successful login clears it
    if entry["locked_until"] and entry["locked_until"] <= time.time():
        _lockout_store[key] = {"count": 0, "first_fail": 0.0, "locked_until": 0.0}
    return False


def check_and_record_failed_login(email: str) -> None:
    """
    Record a failed login attempt. Locks the account for LOCKOUT_WINDOW_SECONDS
    once LOCKOUT_MAX_ATTEMPTS is reached within the same window.
    """
    key = email.strip().lower()
    now = time.time()
    entry = _lockout_store[key]

    # Reset counter when the previous window has expired
    if entry["first_fail"] and (now - entry["first_fail"]) > _LOCKOUT_WINDOW_SECONDS:
        entry.update({"count": 0, "first_fail": 0.0, "locked_until": 0.0})

    entry["count"] += 1
    if entry["count"] == 1:
        entry["first_fail"] = now

    if entry["count"] >= _LOCKOUT_MAX_ATTEMPTS:
        entry["locked_until"] = now + _LOCKOUT_WINDOW_SECONDS
        log_auth_event(
            "account_locked",
            email=email,
            extra={"attempts": entry["count"], "locked_for_seconds": _LOCKOUT_WINDOW_SECONDS},
        )
        logger.warning(
            "account_lockout | email=%s attempts=%d locked_until=%s",
            key,
            entry["count"],
            datetime.fromtimestamp(entry["locked_until"], tz=timezone.utc).isoformat(),
        )


def clear_failed_logins(email: str) -> None:
    """Reset the failed-login counter after a successful authentication."""
    key = email.strip().lower()
    _lockout_store[key] = {"count": 0, "first_fail": 0.0, "locked_until": 0.0}


# [S3] Rate limiting via slowapi
#      slowapi is an optional dependency — all callers check
#      SLOWAPI_AVAILABLE before using the limiter.
SLOWAPI_AVAILABLE: bool = False
_limiter_instance: Any = None

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _DEFAULT_AUTH_RATE = os.getenv("AUTH_RATE_LIMIT", "20/minute")

    def get_limiter() -> "Limiter":  # type: ignore[name-defined]
        global _limiter_instance
        if _limiter_instance is None:
            _limiter_instance = Limiter(key_func=get_remote_address)
        return _limiter_instance

    def rate_limit_auth(limit: str = _DEFAULT_AUTH_RATE):
        """
        Decorator factory for auth endpoints.

        Usage:
            @api.post("/auth/login")
            @rate_limit_auth()
            def login(request: Request, body: LoginRequest):
                ...

        The decorated function MUST have `request: Request` as a parameter
        so slowapi can extract the client IP.
        """
        limiter = get_limiter()
        return limiter.limit(limit)

    SLOWAPI_AVAILABLE = True
    logger.info("security_hardening | slowapi available — rate limiting active")

except ImportError:
    logger.warning(
        "security_hardening | slowapi not installed — rate limiting disabled. "
        "Add 'slowapi' to requirements.txt to enable it."
    )

    def get_limiter() -> None:  # type: ignore[misc]
        return None

    def rate_limit_auth(limit: str = ""):  # type: ignore[misc]
        """No-op decorator when slowapi is absent."""
        def decorator(func: Callable) -> Callable:
            return func
        return decorator


# [S4] Security headers middleware
#      Adds OWASP-recommended response headers on every reply.
#      Must be added BEFORE CORS middleware in main.py so headers
#      are present on all responses including CORS preflight.
_NONCE_LENGTH = 16  # bytes → 32 hex chars

_CSP_DIRECTIVES_DEFAULT = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self';"
)

# Allow overriding CSP from environment for deployments that embed fonts/CDNs
_CSP_DIRECTIVES: str = os.getenv("CSP_DIRECTIVES", _CSP_DIRECTIVES_DEFAULT)

_HSTS_MAX_AGE: int = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year
_HSTS_INCLUDE_SUBDOMAINS: bool = os.getenv("HSTS_INCLUDE_SUBDOMAINS", "true").lower() == "true"
_HSTS_PRELOAD: bool = os.getenv("HSTS_PRELOAD", "false").lower() == "true"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security headers into every HTTP response.

    Headers applied:
      • Content-Security-Policy
      • Strict-Transport-Security (HTTPS only — skipped on HTTP in dev)
      • X-Content-Type-Options: nosniff
      • X-Frame-Options: DENY
      • Referrer-Policy: strict-origin-when-cross-origin
      • Permissions-Policy: restricts camera/microphone/geolocation
      • Cache-Control: no-store  (auth/API responses only)
      • X-Permitted-Cross-Domain-Policies: none
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        hsts_value = f"max-age={_HSTS_MAX_AGE}"
        if _HSTS_INCLUDE_SUBDOMAINS:
            hsts_value += "; includeSubDomains"
        if _HSTS_PRELOAD:
            hsts_value += "; preload"
        self._hsts = hsts_value

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = _CSP_DIRECTIVES

        # HSTS only over HTTPS
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = self._hsts

        # Prevent caching of API responses
        if request.url.path.startswith("/api/"):
            response.headers.setdefault(
                "Cache-Control", "no-store, no-cache, must-revalidate, private"
            )
            response.headers.setdefault("Pragma", "no-cache")

        # Remove headers that leak server information
        if "Server" in response.headers:
            del response.headers["Server"]
        if "X-Powered-By" in response.headers:
            del response.headers["X-Powered-By"]

        return response


# [S5] File upload validation

# Magic-byte signatures for allowed MIME types
# Format: { mime_type: [(offset, bytes_to_match), ...] }
_MAGIC_BYTES: Dict[str, List[Tuple[int, bytes]]] = {
    "image/jpeg":      [(0, b"\xff\xd8\xff")],
    "image/png":       [(0, b"\x89PNG\r\n\x1a\n")],
    "image/gif":       [(0, b"GIF87a"), (0, b"GIF89a")],
    "image/webp":      [(0, b"RIFF"), (8, b"WEBP")],
    "application/pdf": [(0, b"%PDF")],
    "text/plain":      [],  # No magic bytes — checked by extension only
    "text/csv":        [],
    # ZIP-based office formats (docx, xlsx, pptx)
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":   [(0, b"PK\x03\x04")],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":         [(0, b"PK\x03\x04")],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [(0, b"PK\x03\x04")],
    "application/msword":   [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")],  # OLE2
    "application/vnd.ms-excel": [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")],
    # Audio (for voice complaint transcription)
    "audio/webm":   [(0, b"\x1aE\xdf\xa3")],
    "audio/ogg":    [(0, b"OggS")],
    "audio/mpeg":   [(0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2"), (0, b"ID3")],
    "audio/wav":    [(0, b"RIFF"), (8, b"WAVE")],
    "audio/x-wav":  [(0, b"RIFF"), (8, b"WAVE")],
    "audio/mp4":    [(4, b"ftyp")],
    "video/mp4":    [(4, b"ftyp")],
    "video/webm":   [(0, b"\x1aE\xdf\xa3")],
}

ALLOWED_UPLOAD_TYPES: frozenset = frozenset(_MAGIC_BYTES.keys())

# Default 10 MB; overridable via env
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

# Map MIME → safe extension list (to validate filename extension)
_MIME_EXTENSIONS: Dict[str, List[str]] = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png":  [".png"],
    "image/gif":  [".gif"],
    "image/webp": [".webp"],
    "application/pdf": [".pdf"],
    "text/plain": [".txt"],
    "text/csv":   [".csv"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":   [".docx"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":         [".xlsx"],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [".pptx"],
    "application/msword":       [".doc"],
    "application/vnd.ms-excel": [".xls"],
    "audio/webm":  [".webm"],
    "audio/ogg":   [".ogg", ".oga"],
    "audio/mpeg":  [".mp3"],
    "audio/wav":   [".wav"],
    "audio/x-wav": [".wav"],
    "audio/mp4":   [".m4a", ".mp4"],
    "video/mp4":   [".mp4"],
    "video/webm":  [".webm"],
}

# Extensions that should never be accepted regardless of MIME
_BLOCKED_EXTENSIONS: frozenset = frozenset(
    {
        ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".ts",
        ".php", ".py", ".rb", ".pl", ".jar", ".war", ".class",
        ".dll", ".so", ".dylib", ".msi", ".scr", ".hta", ".pif",
        ".com", ".cpl", ".inf", ".reg", ".lnk", ".url",
        ".svg",  # SVG can contain inline JS
    }
)


def _check_magic_bytes(data: bytes, mime_type: str) -> bool:
    """
    Verify that `data` starts with the expected magic bytes for `mime_type`.
    Returns True when the check passes or when no magic bytes are registered
    for that MIME type (plain text, CSV).
    """
    signatures = _MAGIC_BYTES.get(mime_type)
    if signatures is None:
        return False  # unknown MIME type — reject
    if not signatures:
        return True  # no magic bytes registered — accept by extension

    # Some formats (RIFF-based) require checking at two offsets; all must match
    if len(signatures) > 1 and mime_type in ("image/webp", "audio/wav", "audio/x-wav"):
        return all(data[off: off + len(sig)] == sig for off, sig in signatures)

    # For all others, any one signature matching is sufficient
    for off, sig in signatures:
        if data[off: off + len(sig)] == sig:
            return True
    return False


def _sanitize_filename(filename: str) -> str:
    """
    Return a safe filename:
      • Path separators removed
      • Only alphanumerics, hyphens, underscores, dots kept
      • Leading dots stripped (hidden files)
      • Blocked extensions rejected
      • Max 200 chars
    """
    # Strip directory components
    name = os.path.basename(filename or "attachment")
    # Remove anything that isn't a safe character
    name = re.sub(r"[^\w.\- ]", "_", name)
    # Collapse spaces
    name = name.strip().replace(" ", "_")
    # Strip leading dots
    while name.startswith("."):
        name = name[1:]
    if not name:
        name = "upload"

    # Check blocked extension
    _, ext = os.path.splitext(name.lower())
    if ext in _BLOCKED_EXTENSIONS:
        raise HTTPException(
            status_code=400, detail="File type not allowed."
        )

    # Truncate
    return name[:200]


async def validate_upload_file(
    file: UploadFile,
    max_bytes: int = MAX_UPLOAD_BYTES,
    allowed_types: Optional[frozenset] = None,
) -> bytes:
    """
    Read and validate an uploaded file. Returns the raw bytes on success.

    Checks performed:
      1. Content-Type header against the MIME allowlist
      2. File size ≤ max_bytes (default 10 MB)
      3. Magic-byte signature matches declared MIME type
      4. Filename extension not in blocked list

    Raises HTTPException(400 / 413 / 415) on failure.
    """
    if allowed_types is None:
        allowed_types = ALLOWED_UPLOAD_TYPES

    # 1. MIME allowlist
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed_types))}",
        )

    # 2. Read with size cap
    contents = await file.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {max_bytes // (1024 * 1024)} MB.",
        )
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 3. Magic bytes
    if not _check_magic_bytes(contents, content_type):
        logger.warning(
            "upload_validation | magic-byte mismatch mime=%s filename=%s size=%d",
            content_type,
            file.filename,
            len(contents),
        )
        raise HTTPException(
            status_code=400,
            detail="File content does not match the declared file type.",
        )

    # 4. Extension check
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        if ext in _BLOCKED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="File type not allowed.")

    return contents


# [S6] Auth event logging
#      Structured, never logs passwords, tokens, or secrets.
_auth_logger = logging.getLogger("auth_events")


def log_auth_event(
    event: str,
    *,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    ip: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Write a structured auth event to the 'auth_events' logger.

    The log record contains only metadata — no passwords, raw tokens,
    TOTP secrets, or other sensitive values are ever included.

    Standard events:
        login_success | login_failed | login_failed_unknown_email
        login_blocked_locked | totp_success | totp_failed
        mfa_setup_complete | password_reset_requested
        password_reset_complete | password_changed
        account_locked | refresh_token_issued | refresh_token_rotated
        token_revoked | logout
    """
    record: Dict[str, Any] = {
        "event":   event,
        "ts":      datetime.now(timezone.utc).isoformat(),
    }
    if user_id:
        record["user_id"] = user_id
    if email:
        # Partially mask the local part to limit PII in logs
        parts = email.split("@", 1)
        if len(parts) == 2 and len(parts[0]) > 2:
            masked_local = parts[0][:2] + "***"
        else:
            masked_local = "***"
        record["email_masked"] = f"{masked_local}@{parts[1] if len(parts) > 1 else '?'}"
    if ip:
        record["ip"] = ip
    if extra:
        # Only scalar / non-sensitive values
        record["extra"] = {
            k: v for k, v in extra.items()
            if k not in {"password", "token", "secret", "otp", "hash"}
        }

    _auth_logger.info("%s", record)


# [S11] Refresh token helpers
#       Requires a `refresh_tokens` table (see migration below).
#
#       CREATE TABLE IF NOT EXISTS refresh_tokens (
#         id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#         user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
#         token_hash  TEXT NOT NULL UNIQUE,
#         issued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
#         expires_at  TIMESTAMPTZ NOT NULL,
#         revoked_at  TIMESTAMPTZ,
#         user_agent  TEXT,
#         ip_address  TEXT
#       );
#       CREATE INDEX ON refresh_tokens(token_hash) WHERE revoked_at IS NULL;
#       CREATE INDEX ON refresh_tokens(user_id)    WHERE revoked_at IS NULL;
_REFRESH_TTL_SECONDS: int = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", str(30 * 24 * 3600)))  # 30 days
_REFRESH_TOKEN_BYTES: int = 32


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_refresh_token(
    user_id: str,
    db_execute: Callable,
    *,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Generate a new refresh token, persist its hash, and return the raw value.
    The raw value is returned once; only the hash is stored.
    """
    import secrets
    raw = secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)
    token_hash = _hash_token(raw)

    db_execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at, ip_address, user_agent)
        VALUES (%s, %s, now() + (%s || ' seconds')::interval, %s, %s)
        """,
        (user_id, token_hash, str(_REFRESH_TTL_SECONDS), ip, user_agent),
    )
    log_auth_event("refresh_token_issued", user_id=user_id, ip=ip)
    return raw


def rotate_refresh_token(
    raw_token: str,
    db_connect: Callable,
    db_execute: Callable,
    *,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Validate and rotate a refresh token.

    Steps:
      1. Look up the token hash.
      2. Verify it is not revoked and not expired.
      3. Revoke the old token.
      4. Issue a new token for the same user.

    Returns (new_raw_token, user_id).
    Raises HTTPException(401) on any failure.
    """
    from psycopg2.extras import RealDictCursor

    token_hash = _hash_token(raw_token)

    with db_connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at, revoked_at
                FROM refresh_tokens
                WHERE token_hash = %s
                LIMIT 1
                """,
                (token_hash,),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    if row["revoked_at"] is not None:
        # Possible token-theft attempt — revoke ALL tokens for this user
        db_execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
            (str(row["user_id"]),),
        )
        log_auth_event(
            "refresh_token_reuse_detected",
            user_id=str(row["user_id"]),
            ip=ip,
            extra={"action": "all_tokens_revoked"},
        )
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    now_utc = datetime.now(timezone.utc)
    if row["expires_at"] and row["expires_at"] < now_utc:
        raise HTTPException(status_code=401, detail="Refresh token expired. Please log in again.")

    user_id = str(row["user_id"])

    # Revoke the consumed token
    db_execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE id = %s",
        (str(row["id"]),),
    )

    # Issue replacement
    new_raw = create_refresh_token(user_id, db_execute, ip=ip, user_agent=user_agent)
    log_auth_event("refresh_token_rotated", user_id=user_id, ip=ip)
    return new_raw, user_id


def revoke_all_refresh_tokens(user_id: str, db_execute: Callable) -> int:
    """Revoke every active refresh token for the given user. Returns rows updated."""
    count = db_execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )
    log_auth_event("refresh_tokens_all_revoked", user_id=user_id)
    return count


# [S12] Short-term token revocation list
#       For access tokens (JWTs), which cannot be made stateless-revokable
#       without a server-side list. Stores jti (JWT ID) or token hash.
#
#       For multi-instance deployments replace the in-process dict with Redis.
#
#       Requires JWTs to include a "jti" claim (UUID). Add to create_jwt():
#           payload["jti"] = str(uuid.uuid4())
# { jti_or_token_hash: expires_at_unix_float }
_revoked_tokens: Dict[str, float] = {}
_REVOCATION_CLEANUP_INTERVAL: int = 3600  # prune expired entries every hour
_last_cleanup: float = time.time()


def revoke_token(jti: str, expires_at: float) -> None:
    """Add a JWT jti to the revocation list until its natural expiry."""
    _revoked_tokens[jti] = expires_at
    _prune_revoked_tokens()


def is_token_revoked(jti: str) -> bool:
    """Return True if the token has been explicitly revoked."""
    _prune_revoked_tokens()
    exp = _revoked_tokens.get(jti)
    if exp is None:
        return False
    if exp <= time.time():
        _revoked_tokens.pop(jti, None)
        return False
    return True


def _prune_revoked_tokens() -> None:
    """Remove entries whose natural expiry has passed (keeps memory bounded)."""
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _REVOCATION_CLEANUP_INTERVAL:
        return
    expired = [jti for jti, exp in list(_revoked_tokens.items()) if exp <= now]
    for jti in expired:
        _revoked_tokens.pop(jti, None)
    _last_cleanup = now


# [S13] Logout helper
#       Call from the /auth/logout endpoint.
def logout_user(
    *,
    jti: Optional[str],
    token_exp: Optional[float],
    user_id: str,
    db_execute: Callable,
    ip: Optional[str] = None,
) -> None:
    """
    Invalidate the current access token (via revocation list) and
    revoke all active refresh tokens for the user.
    """
    if jti and token_exp:
        revoke_token(jti, token_exp)
    revoke_all_refresh_tokens(user_id, db_execute)
    log_auth_event("logout", user_id=user_id, ip=ip)


# Input sanitisation utilities (shared, also used by main.py)
_SAFE_TEXT_RE = re.compile(r"^[\w\s\-.,\'+()\[\]@/]+$", re.UNICODE)


def sanitize_text(value: str, field: str, max_len: int = 120) -> str:
    """
    Validate a free-text field.
    Raises HTTPException(422) if empty, too long, or contains unsafe chars.
    """
    v = (value or "").strip()
    if not v:
        raise HTTPException(status_code=422, detail=f"{field} must not be empty.")
    if len(v) > max_len:
        raise HTTPException(
            status_code=422,
            detail=f"{field} exceeds maximum length of {max_len} characters.",
        )
    if not _SAFE_TEXT_RE.match(v):
        raise HTTPException(
            status_code=422,
            detail=f"{field} contains invalid characters.",
        )
    return v


def sanitize_email(value: str) -> str:
    """Normalise and validate an email address. Raises HTTPException(422) on failure."""
    v = (value or "").strip().lower()
    pattern = re.compile(r"^[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+$")
    if not pattern.match(v):
        raise HTTPException(status_code=422, detail="Invalid email address.")
    if len(v) > 254:
        raise HTTPException(status_code=422, detail="Email address too long.")
    return v


# [S15] CSRF helpers — stateless HMAC-signed token
_CSRF_SECRET = os.getenv("CSRF_SECRET", os.getenv("JWT_SECRET", "dev-csrf-secret"))


def generate_csrf_token() -> str:
    """Generate a stateless CSRF token: nonce.hmac_signature."""
    nonce = secrets.token_hex(16)
    mac = hmac.new(_CSRF_SECRET.encode(), nonce.encode(), hashlib.sha256)
    return f"{nonce}.{mac.hexdigest()}"


def verify_csrf_token(token: str) -> bool:
    """Verify a CSRF token's HMAC signature. Uses constant-time comparison."""
    if not token or "." not in token:
        return False
    nonce, sig = token.split(".", 1)
    expected = hmac.new(_CSRF_SECRET.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig, expected)


# Exports — everything main.py imports from this module
__all__ = [
    # S1
    "validate_password_complexity",
    # S2
    "is_account_locked",
    "check_and_record_failed_login",
    "clear_failed_logins",
    # S3
    "get_limiter",
    "rate_limit_auth",
    "SLOWAPI_AVAILABLE",
    # S4
    "SecurityHeadersMiddleware",
    # S5
    "validate_upload_file",
    "MAX_UPLOAD_BYTES",
    "ALLOWED_UPLOAD_TYPES",
    "_sanitize_filename",
    # S6
    "log_auth_event",
    # S11
    "create_refresh_token",
    "rotate_refresh_token",
    "revoke_all_refresh_tokens",
    # S12
    "revoke_token",
    "is_token_revoked",
    # S13
    "logout_user",
    # Shared utilities
    "sanitize_text",
    "sanitize_email",
    # S15
    "generate_csrf_token",
    "verify_csrf_token",
]