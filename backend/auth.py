"""Authentication: bcrypt password, server-side sessions, login rate limiting.

Design notes / security:
  * Password is hashed with bcrypt (cost 12). The plaintext ADMIN_PASSWORD env
    is only used to seed the hash on first boot, then never touched again.
  * Sessions are stored server-side (in memory). The cookie holds only an
    opaque random token — never any user data. Cookie is HttpOnly + SameSite
    Strict; Secure is enabled when COOKIE_SECURE=true (behind TLS).
  * Login rate limit: max N *failed* attempts per IP within a rolling window
    (default 5 / 10 min). A successful login clears the counter. The 6th
    failed attempt within the window is rejected before the password is even
    checked.
"""
from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import bcrypt

import settings as settings_mod

log = logging.getLogger("smokeping_easy.auth")

COOKIE_NAME = "sp_session"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

SESSION_TTL_MINUTES = int(os.environ.get("SESSION_TTL_MINUTES", "120"))
LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_MINUTES = int(os.environ.get("LOGIN_WINDOW_MINUTES", "10"))

BCRYPT_ROUNDS = 12

_lock = threading.RLock()


# --- Password hashing ------------------------------------------------------


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    ).decode("ascii")


def verify_password(password: str, hashed: Optional[str]) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def ensure_admin_seeded() -> None:
    """On first boot, seed the admin password.

    If ADMIN_PASSWORD is set, it seeds the hash. Otherwise a random password is
    generated and printed to the logs ONCE so the operator can log in without
    having to invent a password up front (they should change it immediately).
    """
    data = settings_mod.load()
    if data.get("auth", {}).get("password_hash"):
        return
    seed = os.environ.get("ADMIN_PASSWORD", "").strip()
    generated = False
    if not seed:
        seed = secrets.token_urlsafe(12)
        generated = True
    settings_mod.update_section("auth", {"password_hash": hash_password(seed)})
    if generated:
        bar = "=" * 64
        log.warning(bar)
        log.warning("Initial admin password (auto-generated): %s", seed)
        log.warning("Log in with it, then change it in Settings -> Change password.")
        log.warning(bar)
    else:
        log.info("Seeded admin password from ADMIN_PASSWORD.")


def set_password(new_password: str) -> None:
    settings_mod.update_section("auth", {"password_hash": hash_password(new_password)})
    # Invalidate all existing sessions when the password changes.
    clear_all_sessions()


def check_credentials(password: str) -> bool:
    data = settings_mod.load()
    return verify_password(password, data.get("auth", {}).get("password_hash"))


def password_is_configured() -> bool:
    return bool(settings_mod.load().get("auth", {}).get("password_hash"))


# --- Sessions --------------------------------------------------------------


@dataclass
class Session:
    token: str
    created_at: float
    expires_at: float
    ip: str


_sessions: dict[str, Session] = {}


def _now() -> float:
    return time.time()


def create_session(ip: str) -> Session:
    token = secrets.token_urlsafe(32)
    now = _now()
    sess = Session(
        token=token,
        created_at=now,
        expires_at=now + SESSION_TTL_MINUTES * 60,
        ip=ip,
    )
    with _lock:
        _sessions[token] = sess
    return sess


def get_session(token: Optional[str]) -> Optional[Session]:
    if not token:
        return None
    with _lock:
        sess = _sessions.get(token)
        if sess is None:
            return None
        if sess.expires_at < _now():
            _sessions.pop(token, None)
            return None
        return sess


def destroy_session(token: Optional[str]) -> None:
    if not token:
        return
    with _lock:
        _sessions.pop(token, None)


def clear_all_sessions() -> None:
    with _lock:
        _sessions.clear()


def purge_expired() -> int:
    now = _now()
    with _lock:
        expired = [t for t, s in _sessions.items() if s.expires_at < now]
        for t in expired:
            _sessions.pop(t, None)
    return len(expired)


# --- Login rate limiting (failed attempts per IP) --------------------------


@dataclass
class _AttemptWindow:
    failures: list[float] = field(default_factory=list)


_attempts: dict[str, _AttemptWindow] = {}


def _window_seconds() -> int:
    return LOGIN_WINDOW_MINUTES * 60


def is_rate_limited(ip: str) -> bool:
    """True if this IP has reached the failed-attempt limit in the window."""
    now = _now()
    cutoff = now - _window_seconds()
    with _lock:
        win = _attempts.get(ip)
        if not win:
            return False
        win.failures = [t for t in win.failures if t >= cutoff]
        return len(win.failures) >= LOGIN_MAX_ATTEMPTS


def record_failure(ip: str) -> None:
    now = _now()
    cutoff = now - _window_seconds()
    with _lock:
        win = _attempts.setdefault(ip, _AttemptWindow())
        win.failures = [t for t in win.failures if t >= cutoff]
        win.failures.append(now)


def clear_failures(ip: str) -> None:
    with _lock:
        _attempts.pop(ip, None)


def retry_after_seconds(ip: str) -> int:
    """Seconds until the oldest failure leaves the window (for Retry-After)."""
    now = _now()
    with _lock:
        win = _attempts.get(ip)
        if not win or not win.failures:
            return 0
        oldest = min(win.failures)
    return max(0, int(oldest + _window_seconds() - now))
