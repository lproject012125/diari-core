"""
Session CSRF checks, in-memory request rate limits, and persistent login lockouts.
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Optional

import db

_lock = Lock()
_hits: Dict[str, List[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900.0  # 15 minutes

MAX_OTP_REQUESTS = 5
OTP_RATE_WINDOW_SECONDS = 900.0  # 15 minutes
OTP_RATE_LOCKOUT_SECONDS = 900.0  # 15 minutes
OTP_RATE_LIMIT_MESSAGE = "Too many OTP requests. Please try again later."


def client_ip(request) -> str:
    if request is None:
        return "unknown"
    try:
        forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return forwarded or (request.remote_addr or "unknown")
    except Exception:
        return "unknown"


def rate_limit_check(request, scope: str, limit: int, window_sec: float) -> Optional[str]:
    """Return an error message if rate limited, else None."""
    if limit <= 0:
        return None
    key = f"{scope}:{client_ip(request)}"
    now = time.monotonic()
    with _lock:
        bucket = _hits[key]
        bucket[:] = [t for t in bucket if now - t < window_sec]
        if len(bucket) >= limit:
            return "Too many requests. Please wait a moment and try again."
        bucket.append(now)
    return None


def _get_login_keys(request, identifier: str) -> List[str]:
    ident_norm = (identifier or "").strip().lower()
    return [db.get_login_lockout_key(ident_norm)] if ident_norm else []


def check_login_lockout(request, identifier: str) -> tuple[bool, int, str]:
    """
    Check if the account identifier is locked out.
    Returns (is_locked, remaining_seconds, message).
    """
    keys = _get_login_keys(request, identifier)
    now = datetime.now(timezone.utc)
    max_remaining = 0
    for k in keys:
        _, locked_until = db.get_login_lockout(k)
        if locked_until and locked_until > now:
            rem = int((locked_until - now).total_seconds()) + 1
            if rem > max_remaining:
                max_remaining = rem
        if max_remaining > 0:
            mins = (max_remaining + 59) // 60
            msg = (
                f"Too many failed login attempts. To protect your account, login is temporarily locked. "
                f"Please try again in {mins} minute{'s' if mins != 1 else ''}."
            )
            return True, max_remaining, msg
    return False, 0, ""


def record_login_failure(request, identifier: str) -> tuple[bool, int, int, str]:
    """
    Record a failed login attempt for the account identifier.
    Returns (is_locked, remaining_seconds, attempts_left, message).
    """
    keys = _get_login_keys(request, identifier)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
    worst_locked = False
    worst_remaining = 0
    min_attempts_left = MAX_LOGIN_ATTEMPTS

    for k in keys:
        attempts, locked_until = db.get_login_lockout(k)
        parsed_attempts = []
        for attempt in attempts:
            try:
                timestamp = datetime.fromisoformat(attempt.replace("Z", "+00:00"))
                timestamp = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
                if timestamp >= window_start:
                    parsed_attempts.append(timestamp)
            except ValueError:
                continue
        parsed_attempts.append(now)

        if len(parsed_attempts) >= MAX_LOGIN_ATTEMPTS:
            locked_until = now + timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
            db.save_login_lockout(k, [], locked_until)
            worst_locked = True
            worst_remaining = int(LOGIN_LOCKOUT_SECONDS)
        else:
            db.save_login_lockout(k, [attempt.isoformat() for attempt in parsed_attempts], None)
            left = MAX_LOGIN_ATTEMPTS - len(parsed_attempts)
            if left < min_attempts_left:
                min_attempts_left = left

    if worst_locked:
        msg = (
            "Too many failed login attempts. To protect your account, login has been locked for 15 minutes."
        )
        return True, worst_remaining, 0, msg
    msg = (
        f"Incorrect username or password. {min_attempts_left} attempt{'s' if min_attempts_left != 1 else ''} remaining before temporary lockout."
    )
    return False, 0, min_attempts_left, msg


def clear_login_failures(request, identifier: str) -> None:
    """Clear failed login attempts and lockouts on successful login."""
    keys = _get_login_keys(request, identifier)
    for k in keys:
        db.clear_login_lockout(k)


def check_otp_resend_limit(account_key: str) -> tuple[bool, int]:
    """Return (is_locked, remaining_seconds) for the OTP resend rate limit."""
    _, locked_until = db.get_otp_resend_limit(account_key)
    now = datetime.now(timezone.utc)
    if locked_until and locked_until > now:
        return True, int((locked_until - now).total_seconds()) + 1
    return False, 0


def record_otp_resend(account_key: str) -> tuple[bool, int, str]:
    """
    Record an OTP request for an account, enforcing 5 requests per 15 minutes.
    The 6th request within the window locks the account for 15 minutes.
    Returns (is_locked, remaining_seconds, message).
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(seconds=OTP_RATE_WINDOW_SECONDS)
    attempts, locked_until = db.get_otp_resend_limit(account_key)

    if locked_until and locked_until > now:
        return True, int((locked_until - now).total_seconds()) + 1, OTP_RATE_LIMIT_MESSAGE

    recent: List[datetime] = []
    for attempt in attempts:
        try:
            ts = datetime.fromisoformat(str(attempt).replace("Z", "+00:00"))
            ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if ts >= window_start:
                recent.append(ts)
        except ValueError:
            continue

    if len(recent) >= MAX_OTP_REQUESTS:
        locked_until = now + timedelta(seconds=OTP_RATE_LOCKOUT_SECONDS)
        db.save_otp_resend_limit(account_key, [], locked_until)
        return True, int(OTP_RATE_LOCKOUT_SECONDS), OTP_RATE_LIMIT_MESSAGE

    recent.append(now)
    db.save_otp_resend_limit(account_key, [ts.isoformat() for ts in recent], None)
    return False, 0, ""


def validate_csrf(request, session_map: Any) -> Optional[str]:
    """Same-origin session POST protection without per-request DB access."""
    token = session_map.get("csrf_token")
    if not token:
        return "Session expired. Please sign in again."

    header = (request.headers.get("X-CSRF-Token") or "").strip()
    if header and secrets.compare_digest(header, token):
        return None

    origin = (request.headers.get("Origin") or "").strip()
    if origin:
        try:
            from urllib.parse import urlparse

            o = urlparse(origin)
            host = (request.host or "").split(":")[0]
            if o.hostname and host and o.hostname == host:
                return None
        except Exception:
            pass

    referer = (request.headers.get("Referer") or "").strip()
    if referer:
        try:
            from urllib.parse import urlparse

            r = urlparse(referer)
            host = (request.host or "").split(":")[0]
            if r.hostname and host and r.hostname == host:
                return None
        except Exception:
            pass

    return "Invalid request. Refresh the page and try again."
