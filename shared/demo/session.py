"""Cryptographic capability token management for Sentinel Demo Mode.

A client-supplied header alone never grants access. Every demo request requires
a cryptographically signed, server-issued capability token (`X-Sentinel-Demo-Session`)
with an HMAC-SHA256 signature and a bounded time-to-live (TTL).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from pydantic import BaseModel, ConfigDict

# Secret key for signing demo session tokens. In production, read from env;
# fallback to a stable process-level secret.
DEMO_SECRET_KEY = os.environ.get("SENTINEL_DEMO_SECRET", "sentinel_demo_capability_hmac_secret_v1_scoped")
DEMO_SESSION_TTL_SECONDS = 7200  # 2 hours -- covers typical hackathon judging windows


class DemoSessionClaims(BaseModel):
    """Server-resolved claims extracted from a verified demo session capability."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    issued_at: int
    expires_at: int
    display_name: str = "Demo Analyst"
    role: str = "ANALYST"


def generate_session_id() -> str:
    """Generate a high-entropy 128-bit random session identifier."""
    return secrets.token_hex(16)


def create_demo_session_token(
    session_id: str | None = None,
    ttl_seconds: int = DEMO_SESSION_TTL_SECONDS,
    secret_key: str = DEMO_SECRET_KEY,
) -> tuple[str, DemoSessionClaims]:
    """Issue a cryptographically signed capability token for a demo session.

    :param session_id: Optional 128-bit session identifier; generated if omitted.
    :param ttl_seconds: Lifetime of this token in seconds.
    :param secret_key: Secret key used for the HMAC signature.
    :return: (token_string, claims)
    """
    sid = session_id or generate_session_id()
    now = int(time.time())
    exp = now + ttl_seconds
    claims = DemoSessionClaims(session_id=sid, issued_at=now, expires_at=exp)

    payload = f"{sid}.{now}.{exp}"
    signature = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    token = f"{payload}.{signature}"
    return token, claims


def verify_demo_session_token(token: str, secret_key: str = DEMO_SECRET_KEY) -> DemoSessionClaims | None:
    """Verify an incoming demo capability token.

    Enforces:
    1. Correct format: `<session_id>.<issued_at>.<expires_at>.<hmac_signature>`.
    2. Valid HMAC-SHA256 signature using constant-time comparison.
    3. Expiration: current UTC time must be strictly before `expires_at`.

    :param token: The raw capability token from `X-Sentinel-Demo-Session`.
    :param secret_key: Secret key used for the HMAC verification.
    :return: DemoSessionClaims if valid and active, or None if invalid or expired.
    """
    if not token or not isinstance(token, str):
        return None

    parts = token.strip().split(".")
    if len(parts) != 4:
        return None

    sid, issued_str, exp_str, signature = parts

    # Validate session_id format (32-character hex)
    if len(sid) != 32 or not all(c in "0123456789abcdefABCDEF" for c in sid):
        return None

    try:
        issued_at = int(issued_str)
        expires_at = int(exp_str)
    except ValueError:
        return None

    now = int(time.time())
    if now >= expires_at:
        return None

    payload = f"{sid}.{issued_str}.{exp_str}"
    expected_sig = hmac.new(secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        return None

    return DemoSessionClaims(session_id=sid.lower(), issued_at=issued_at, expires_at=expires_at)
