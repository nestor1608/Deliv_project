"""
Lockout service for brute-force protection.

Uses django.core.cache (backed by Redis in production) to track
failed login attempts and enforce exponential backoff lockout.
"""

import logging

from django.core.cache import cache
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

# How many failed attempts before lockout kicks in
MAX_FAILED_ATTEMPTS = 5

# Lockout durations in seconds (exponential backoff stages)
LOCKOUT_DURATIONS = [
    60,  # 1 minute  (after 5th failure)
    300,  # 5 minutes (after 6th)
    900,  # 15 minutes (after 7th)
    3600,  # 1 hour    (after 8th)
    3600,  # 1 hour    (after 9th, caps here)
]

# Cache TTL for attempt counter (reset if no activity for this long)
COUNTER_TTL = 3600  # 1 hour

# Cache key prefix
PREFIX = "lockout:"


def _attempts_key(identifier: str) -> str:
    """Cache key for the failed-attempts counter."""
    return f"{PREFIX}attempts:{identifier}"


def _lock_key(identifier: str) -> str:
    """Cache key for the active lockout."""
    return f"{PREFIX}lock:{identifier}"


def get_failed_attempts(identifier: str) -> int:
    """Return the current failed-attempt count."""
    return cache.get(_attempts_key(identifier), 0)


def record_failed_attempt(identifier: str) -> int:
    """
    Increment the failed-attempt counter and apply lockout if threshold met.

    Returns the new attempt count.
    """
    key = _attempts_key(identifier)
    attempts = cache.get(key, 0) + 1
    # Reset the TTL on each failed attempt so counter lives for COUNTER_TTL
    # of inactivity. Works with any Django cache backend (LocMem, Redis, etc.).
    cache.set(key, attempts, timeout=COUNTER_TTL)

    if attempts >= MAX_FAILED_ATTEMPTS:
        # Determine lockout duration based on excess attempts
        excess = attempts - MAX_FAILED_ATTEMPTS
        duration_idx = min(excess, len(LOCKOUT_DURATIONS) - 1)
        duration = LOCKOUT_DURATIONS[duration_idx]

        lock_key = _lock_key(identifier)
        cache.set(lock_key, True, timeout=duration)
        logger.warning(
            "Account locked out",
            extra={
                "identifier": identifier,
                "attempts": attempts,
                "lockout_duration": duration,
            },
        )

    return attempts


def reset_attempts(identifier: str) -> None:
    """Clear failed-attempt counter and lockout on successful login."""
    cache.delete(_attempts_key(identifier))
    cache.delete(_lock_key(identifier))
    logger.info("Lockout reset for %s", identifier)


def is_locked(identifier: str) -> bool:
    """Return True if the account is currently locked out."""
    return cache.get(_lock_key(identifier), False)


def get_lockout_remaining(identifier: str) -> int:
    """Return remaining lockout time in seconds (0 if not locked)."""
    lock_key = _lock_key(identifier)
    # Some backends (LocMemCache) don't expose ttl(); fall back to 0.
    try:
        ttl = cache.ttl(lock_key)
        return max(ttl, 0)
    except (AttributeError, NotImplementedError):
        return 0


def check_lockout(identifier: str) -> None:
    """
    Check if account is locked; raise LockedError if so.

    Call this at the START of a login attempt, BEFORE authentication.
    """
    if is_locked(identifier):
        remaining = get_lockout_remaining(identifier)
        logger.warning(
            "Blocked login attempt on locked account",
            extra={"identifier": identifier, "remaining": remaining},
        )
        raise LockedError(remaining)


class LockedError(APIException):
    """HTTP 423 Locked — account is temporarily locked."""

    status_code = 423
    default_detail = "Cuenta bloqueada temporalmente por múltiples intentos fallidos"
    default_code = "account_locked"

    def __init__(self, remaining=0, detail=None, code=None):
        if detail is None:
            minutes = remaining // 60
            seconds = remaining % 60
            if minutes > 0:
                detail = f"Cuenta bloqueada. Intente nuevamente en {minutes} minuto(s)."
            else:
                detail = f"Cuenta bloqueada. Intente nuevamente en {seconds} segundo(s)."
        self.remaining = remaining
        super().__init__(detail, code)
