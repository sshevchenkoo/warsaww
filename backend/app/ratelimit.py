"""Per-session daily rate limit for /search, backed by Redis.

Each session (anonymous or logged-in) gets N searches per calendar day
(Europe/Warsaw); the counter resets at midnight. Fail-open: if Redis is
unreachable we allow the request — the limit is cost control, not security.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import redis

from app.config import settings

_redis = redis.from_url(settings.redis_url, decode_responses=True)
_TZ = ZoneInfo("Europe/Warsaw")


def _seconds_to_midnight(now: datetime) -> int:
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


def check_search_quota(sid: str) -> tuple[bool, int]:
    """Count one search for this session today. Returns (allowed, remaining)."""
    now = datetime.now(_TZ)
    key = f"ratelimit:search:{sid}:{now:%Y-%m-%d}"
    try:
        used = _redis.incr(key)
        if used == 1:  # first hit today — expire the counter at midnight
            _redis.expire(key, _seconds_to_midnight(now) + 60)
    except redis.RedisError:
        return True, settings.search_daily_limit  # fail-open
    remaining = max(0, settings.search_daily_limit - used)
    return used <= settings.search_daily_limit, remaining


def check_auth_rate(client_ip: str) -> bool:
    """Per-IP, per-minute cap on auth attempts (login/register brute-force guard).

    Returns True if the attempt is allowed. Fail-open on Redis errors — this is
    abuse mitigation, not an authorization boundary. Keyed per-minute bucket so a
    burst is throttled but the limit resets quickly for legitimate users."""
    now = datetime.now(_TZ)
    key = f"ratelimit:auth:{client_ip}:{now:%Y-%m-%d-%H-%M}"
    try:
        used = _redis.incr(key)
        if used == 1:  # first hit in this minute — expire the bucket
            _redis.expire(key, 60)
    except redis.RedisError:
        return True  # fail-open
    return used <= settings.auth_attempts_per_minute
