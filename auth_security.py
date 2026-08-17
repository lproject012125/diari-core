"""
Session CSRF checks and lightweight in-memory rate limits (no extra DB round-trips).
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict
from threading import Lock
from typing import Any, Dict, List, Optional

_lock = Lock()
_hits: Dict[str, List[float]] = defaultdict(list)
_login_failures: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"attempts": [], "locked_until": 0.0})

MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 900.0  # 15 minutes


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
    keys = []
    ident_norm = (identifier or "").strip().lower()
    if ident_norm:
        keys.append(f"user:{ident_norm}")
    ip = client_ip(request)
    if ip and ip != "unknown":
        keys.append(f"ip:{ip}")
    return keys


def check_login_lockout(request, identifier: str) -> tuple[bool, int, str]:
    """
    Check if the user identifier or IP is locked out.
    Returns (is_locked, remaining_seconds, message).
    """
    keys = _get_login_keys(request, identifier)
    now = time.monotonic()
    with _lock:
        max_remaining = 0
        for k in keys:
            data = _login_failures.get(k)
            if data and data.get("locked_until", 0.0) > now:
                rem = int(data["locked_until"] - now) + 1
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
    Record a failed login attempt for the identifier and IP.
    Returns (is_locked, remaining_seconds, attempts_left, message).
    """
    keys = _get_login_keys(request, identifier)
    now = time.monotonic()
    window = LOGIN_LOCKOUT_SECONDS
    with _lock:
        worst_locked = False
        worst_remaining = 0
        min_attempts_left = MAX_LOGIN_ATTEMPTS

        for k in keys:
            entry = _login_failures[k]
            # Prune attempts older than the lockout window
            entry["attempts"] = [t for t in entry["attempts"] if now - t < window]
            entry["attempts"].append(now)

            if len(entry["attempts"]) >= MAX_LOGIN_ATTEMPTS:
                entry["locked_until"] = now + LOGIN_LOCKOUT_SECONDS
                entry["attempts"] = []
                worst_locked = True
                worst_remaining = int(LOGIN_LOCKOUT_SECONDS)
            else:
                left = MAX_LOGIN_ATTEMPTS - len(entry["attempts"])
                if left < min_attempts_left:
                    min_attempts_left = left

        if worst_locked:
            msg = (
                "Too many failed login attempts. To protect your account, login has been locked for 15 minutes."
            )
            return True, worst_remaining, 0, msg
        else:
            msg = (
                f"Incorrect username or password. {min_attempts_left} attempt{'s' if min_attempts_left != 1 else ''} remaining before temporary lockout."
            )
            return False, 0, min_attempts_left, msg


def clear_login_failures(request, identifier: str) -> None:
    """Clear failed login attempts and lockouts on successful login."""
    keys = _get_login_keys(request, identifier)
    with _lock:
        for k in keys:
            _login_failures.pop(k, None)


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
