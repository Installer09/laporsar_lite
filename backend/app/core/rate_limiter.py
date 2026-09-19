"""
Rate Limiter & Security Utilities
=================================
Sliding-window / counter rate limiter supporting Redis with automatic in-memory fallback.
Also includes CSV Formula Injection sanitization utility.
"""

import time
import logging
from typing import Optional, Tuple, Any, Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

# In-memory storage fallback for development / test environments
_in_memory_limits: Dict[str, List[float]] = defaultdict(list)
_in_memory_attempts: Dict[str, Dict[str, Any]] = {}


async def check_rate_limit(
    redis_client: Optional[Any],
    key: str,
    max_requests: int,
    window_seconds: int
) -> bool:
    """
    Check if a rate limit is exceeded.
    Returns True if allowed, False if exceeded.
    """
    full_key = f"ratelimit:{key}"

    if redis_client and hasattr(redis_client, "incr") and hasattr(redis_client, "expire"):
        try:
            current = await redis_client.incr(full_key)
            if current == 1:
                await redis_client.expire(full_key, window_seconds)
            return current <= max_requests
        except Exception as e:
            logger.warning(f"Redis rate limit check failed ({e}), using in-memory fallback")

    # In-memory fallback
    now = time.time()
    timestamps = [ts for ts in _in_memory_limits[full_key] if now - ts < window_seconds]
    if len(timestamps) >= max_requests:
        _in_memory_limits[full_key] = timestamps
        return False

    timestamps.append(now)
    _in_memory_limits[full_key] = timestamps
    return True


async def record_failed_attempt(
    redis_client: Optional[Any],
    key: str,
    max_attempts: int,
    window_seconds: int = 300
) -> Tuple[int, bool]:
    """
    Record a failed attempt (e.g. invalid OTP or password).
    Returns (current_attempts, is_locked_out).
    """
    full_key = f"attempts:{key}"

    if redis_client and hasattr(redis_client, "incr") and hasattr(redis_client, "expire"):
        try:
            current = await redis_client.incr(full_key)
            if current == 1:
                await redis_client.expire(full_key, window_seconds)
            is_locked = current >= max_attempts
            return current, is_locked
        except Exception as e:
            logger.warning(f"Redis attempt tracking failed ({e}), using in-memory fallback")

    # In-memory fallback
    now = time.time()
    record = _in_memory_attempts.get(full_key)
    if not record or now - record["timestamp"] > window_seconds:
        _in_memory_attempts[full_key] = {"count": 1, "timestamp": now}
        return 1, 1 >= max_attempts

    record["count"] += 1
    return record["count"], record["count"] >= max_attempts


async def reset_failed_attempts(redis_client: Optional[Any], key: str) -> None:
    """Reset / clear failed attempts counter on successful authentication."""
    full_key = f"attempts:{key}"
    if redis_client:
        try:
            await redis_client.delete(full_key)
        except Exception:
            pass
    _in_memory_attempts.pop(full_key, None)


def sanitize_csv_cell(val: Any) -> str:
    """
    Sanitize value to prevent CSV Formula Injection (CWE-1236).
    If a string starts with =, +, -, @, \\t, or \\r, prepend a single quote (')
    so spreadsheet software (Excel, LibreOffice, Google Sheets) treats it as plain text.
    """
    if val is None:
        return ""
    str_val = str(val)
    if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{str_val}"
    return str_val
