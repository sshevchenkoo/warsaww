"""The /search product gate (logged-in + email-verified only) and the code
verification endpoint's accept/reject/expiry/attempt-cap logic. Pure logic with
fakes — no HTTP server, DB, or Redis."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api import auth as authmod
from app.api import routes
from app.api.auth import VerifyRequest, verify_email
from app.auth.email import hash_code


# ─── /search gate: _require_verified_user ─────────────────────────────────────
class _FakeSession:
    """Stands in for a SessionLocal() context manager; .get returns a fixed user."""

    def __init__(self, user):
        self._user = user

    def get(self, _model, _uid):
        return self._user

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Req:
    def __init__(self, user_id):
        self.session = {"user_id": user_id} if user_id is not None else {}
        self.headers = {}
        self.client = type("C", (), {"host": "1.2.3.4"})()


class _User:
    def __init__(self, verified, code_hash=None, expires_at=None, attempts=0):
        self.id = uuid.uuid4()
        self.email = "u@example.com"
        self.name = None
        self.avatar_url = None
        self.email_verified = verified
        self.email_verify_code_hash = code_hash
        self.email_verify_code_expires_at = expires_at
        self.email_verify_attempts = attempts


def _patch_sessionlocal(monkeypatch, user):
    monkeypatch.setattr(routes, "SessionLocal", lambda: _FakeSession(user))


def test_gate_401_when_not_logged_in(monkeypatch):
    _patch_sessionlocal(monkeypatch, None)
    with pytest.raises(HTTPException) as e:
        routes._require_verified_user(_Req(None))
    assert e.value.status_code == 401


def test_gate_401_when_cookie_user_gone_from_db(monkeypatch):
    _patch_sessionlocal(monkeypatch, None)  # session.get returns None
    with pytest.raises(HTTPException) as e:
        routes._require_verified_user(_Req(str(uuid.uuid4())))
    assert e.value.status_code == 401


def test_gate_403_when_unverified(monkeypatch):
    _patch_sessionlocal(monkeypatch, _User(verified=False))
    with pytest.raises(HTTPException) as e:
        routes._require_verified_user(_Req(str(uuid.uuid4())))
    assert e.value.status_code == 403


def test_gate_passes_when_verified(monkeypatch):
    _patch_sessionlocal(monkeypatch, _User(verified=True))
    routes._require_verified_user(_Req(str(uuid.uuid4())))  # must not raise


def test_gate_401_and_clears_malformed_cookie(monkeypatch):
    _patch_sessionlocal(monkeypatch, _User(verified=True))
    req = _Req("not-a-uuid")
    with pytest.raises(HTTPException) as e:
        routes._require_verified_user(req)
    assert e.value.status_code == 401
    assert req.session == {}  # tampered cookie is cleared


# ─── /auth/verify: code accept / reject / expiry / attempt cap ─────────────────
@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    # The endpoint's brute-force limiter hits Redis; bypass it for these tests.
    monkeypatch.setattr(authmod, "_rate_limit_auth", lambda request: None)


class _CommitSession:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def _future():
    return datetime.now(timezone.utc) + timedelta(minutes=15)


def test_verify_success_marks_verified_and_clears_code():
    u = _User(verified=False, code_hash=hash_code("123456"), expires_at=_future())
    out = verify_email(VerifyRequest(code="123456"), _Req(str(u.id)), _CommitSession(), u)
    assert u.email_verified is True
    assert u.email_verify_code_hash is None
    assert u.email_verify_code_expires_at is None
    assert out["email_verified"] is True


def test_verify_wrong_code_increments_attempts_and_400():
    u = _User(verified=False, code_hash=hash_code("123456"), expires_at=_future())
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="000000"), _Req(str(u.id)), _CommitSession(), u)
    assert e.value.status_code == 400
    assert u.email_verify_attempts == 1
    assert u.email_verified is False


def test_verify_expired_code_400():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    u = _User(verified=False, code_hash=hash_code("123456"), expires_at=past)
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="123456"), _Req(str(u.id)), _CommitSession(), u)
    assert e.value.status_code == 400  # correct code, but too late


def test_verify_blocks_after_max_attempts(monkeypatch):
    monkeypatch.setattr(authmod.settings, "email_verify_max_attempts", 3)
    u = _User(verified=False, code_hash=hash_code("123456"), expires_at=_future(), attempts=3)
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="123456"), _Req(str(u.id)), _CommitSession(), u)
    assert e.value.status_code == 429  # even the right code is refused until resend


def test_verify_when_already_verified_is_noop():
    u = _User(verified=True)
    out = verify_email(VerifyRequest(code="123456"), _Req(str(u.id)), _CommitSession(), u)
    assert out["email_verified"] is True
