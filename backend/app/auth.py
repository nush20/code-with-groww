from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuthSession


SESSION_COOKIE = "catchup_session"
DEMO_USER_ID = "demo-user"
_request_user: ContextVar[str] = ContextVar("request_user", default=DEMO_USER_ID)


def active_user_id() -> str:
    return _request_user.get()


def set_request_user(user_id: str):
    return _request_user.set(user_id)


def reset_request_user(token) -> None:
    _request_user.reset(token)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    iterations = 310_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.urlsafe_b64decode(salt), int(iterations))
        return hmac.compare_digest(candidate, base64.urlsafe_b64decode(expected))
    except (ValueError, TypeError):
        return False


def new_session(db: Session, user_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(AuthSession(
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    ))
    return raw


def session_user(db: Session, raw: str | None) -> str | None:
    if not raw:
        return None
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == hashlib.sha256(raw.encode()).hexdigest()))
    if session is None:
        return None
    expires = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    return session.user_id if expires > datetime.now(timezone.utc) else None
