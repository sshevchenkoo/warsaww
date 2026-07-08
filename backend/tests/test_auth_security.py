"""Unit tests for the auth hardening — password hashing, the brute-force rate
limiter, and client-IP extraction. No DB/Redis needed (Redis is faked)."""

import pytest
import redis as redislib

from app import ratelimit
from app.api.auth import _client_ip
from app.auth.passwords import MAX_PASSWORD_BYTES, hash_password, verify_password


# ─── password hashing ─────────────────────────────────────────────────────────
def test_password_roundtrip():
    h = hash_password("correct horse battery")
    assert h != "correct horse battery"  # never store plaintext
    assert verify_password("correct horse battery", h) is True
    assert verify_password("wrong password", h) is False


def test_password_hash_is_salted():
    # Two hashes of the same password differ (random salt).
    assert hash_password("same") != hash_password("same")


def test_verify_bad_hash_is_false_not_raise():
    # A malformed stored hash must return False, not blow up.
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_max_password_bytes_is_bcrypt_limit():
    assert MAX_PASSWORD_BYTES == 72  # bcrypt silently truncates beyond this


# ─── auth rate limiter (fake Redis) ───────────────────────────────────────────
class _FakeRedis:
    def __init__(self):
        self.counts: dict[str, int] = {}

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, seconds):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ratelimit, "_redis", fake)
    return fake


def test_auth_rate_blocks_after_limit(fake_redis, monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "auth_attempts_per_minute", 3)
    results = [ratelimit.check_auth_rate("1.2.3.4") for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_auth_rate_is_per_ip(fake_redis, monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "auth_attempts_per_minute", 1)
    assert ratelimit.check_auth_rate("1.1.1.1") is True
    assert ratelimit.check_auth_rate("1.1.1.1") is False  # same IP exhausted
    assert ratelimit.check_auth_rate("2.2.2.2") is True   # different IP, own bucket


def test_auth_rate_fails_open_when_redis_down(monkeypatch):
    class _BoomRedis:
        def incr(self, key):
            raise redislib.RedisError("down")

        def expire(self, key, seconds):
            pass

    monkeypatch.setattr(ratelimit, "_redis", _BoomRedis())
    # Rate limit is abuse control, not a security boundary — never lock users out
    # of auth because Redis is unavailable.
    assert ratelimit.check_auth_rate("9.9.9.9") is True


# ─── client IP extraction (behind the ingress) ────────────────────────────────
class _FakeRequest:
    def __init__(self, xff=None, host="10.0.0.9"):
        self.headers = {"x-forwarded-for": xff} if xff is not None else {}
        self.client = type("C", (), {"host": host})() if host else None


def test_client_ip_prefers_first_xff_hop():
    req = _FakeRequest(xff="203.0.113.5, 10.0.0.1")
    assert _client_ip(req) == "203.0.113.5"


def test_client_ip_falls_back_to_peer():
    assert _client_ip(_FakeRequest(host="198.51.100.2")) == "198.51.100.2"


def test_client_ip_unknown_when_no_client():
    assert _client_ip(_FakeRequest(host=None)) == "unknown"
