"""Two-factor sign-in: POST /auth/login parks a password login until the
emailed code comes back through POST /auth/login/2fa, and PATCH /me toggles it.
Pure logic with fakes — no HTTP server, DB, Redis or email."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.api import auth as authmod
from app.api.auth import (
    LoginRequest,
    UpdateMeRequest,
    VerifyRequest,
    login,
    login_2fa,
    update_me,
    verify_email,
)
from app.auth.email import hash_code
from app.auth.passwords import hash_password
from app.config import settings

EMAIL = "user@example.com"
PASSWORD = "correct horse battery"
PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt is slow — hash once


class _Req:
    def __init__(self, session=None):
        self.session = dict(session or {})
        self.headers = {}
        self.client = type("C", (), {"host": "1.2.3.4"})()


class _User:
    def __init__(self, *, two_factor=True, google=False, verified=True, pending=None):
        self.id = uuid.uuid4()
        self.email = EMAIL
        self.name = None
        self.avatar_url = None
        self.google_sub = "g-123" if google else None
        self.password_hash = None if google else PASSWORD_HASH
        self.email_verified = verified
        self.pending_email = pending
        self.email_verify_code_hash = None
        self.email_verify_code_expires_at = None
        self.email_verify_attempts = 0
        self.two_factor_enabled = two_factor
        self.login_code_hash = None
        self.login_code_expires_at = None
        self.login_code_attempts = 0


class _Session:
    """One-user fake covering what the endpoints call: the login lookup
    (query().filter_by().one_or_none()), get() by id, and commit."""

    def __init__(self, user):
        self.user = user
        self.commits = 0

    def query(self, _model):
        return self

    def filter_by(self, email):
        self._email = email
        return self

    def one_or_none(self):
        return self.user if self.user.email == self._email else None

    def get(self, _model, user_id):
        return self.user if self.user.id == user_id else None

    def commit(self):
        self.commits += 1


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    # The brute-force limiter hits Redis; bypass it.
    monkeypatch.setattr(authmod, "_rate_limit_auth", lambda request: None)


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing login codes as (to, code) pairs."""
    out = []
    monkeypatch.setattr(authmod, "send_login_code_email", lambda to, code: out.append((to, code)))
    return out


def _login(user, req=None):
    req = req or _Req()
    out = login(LoginRequest(email=EMAIL, password=PASSWORD), req, _Session(user))
    return out, req


def _second_step(user, req, code):
    return login_2fa(VerifyRequest(code=code), req, _Session(user))


def _wrong(code):
    return "000000" if code != "000000" else "111111"


# ─── POST /auth/login ─────────────────────────────────────────────────────────
def test_login_without_2fa_signs_in_at_once(sent):
    u = _User(two_factor=False)
    out, req = _login(u)
    assert req.session == {"user_id": str(u.id)}
    assert out["two_factor_enabled"] is False
    assert sent == []


def test_login_with_2fa_parks_the_session_and_emails_a_code(sent):
    u = _User()
    out, req = _login(u)
    assert out == {"pending_2fa": True}  # no user payload before the second step
    assert req.session == {"pending_2fa": str(u.id)}
    [(to, code)] = sent
    assert to == EMAIL
    assert u.login_code_hash == hash_code(code)  # only the keyed hash is stored
    assert u.login_code_attempts == 0


def test_login_with_2fa_drops_an_existing_session(sent):
    u = _User()
    _, req = _login(u, _Req({"user_id": str(uuid.uuid4())}))
    assert "user_id" not in req.session


def test_wrong_password_issues_no_code(sent):
    u = _User()
    with pytest.raises(HTTPException) as e:
        login(LoginRequest(email=EMAIL, password="nope"), _Req(), _Session(u))
    assert e.value.status_code == 401
    assert sent == []


# ─── POST /auth/login/2fa ─────────────────────────────────────────────────────
def test_right_code_completes_the_login(sent):
    u = _User()
    _, req = _login(u)
    out = _second_step(u, req, sent[0][1])
    assert req.session == {"user_id": str(u.id)}
    assert out["id"] == str(u.id)
    assert out["two_factor_enabled"] is True
    assert u.login_code_hash is None  # single use


def test_code_is_single_use(sent):
    u = _User()
    _, req = _login(u)
    code = sent[0][1]
    _second_step(u, req, code)
    with pytest.raises(HTTPException) as e:
        _second_step(u, _Req({"pending_2fa": str(u.id)}), code)
    assert e.value.status_code == 400


def test_wrong_code_five_times_locks_the_code(sent):
    u = _User()
    _, req = _login(u)
    code = sent[0][1]
    for _ in range(settings.email_verify_max_attempts):
        with pytest.raises(HTTPException) as e:
            _second_step(u, req, _wrong(code))
        assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _second_step(u, req, code)  # even the right code is refused now
    assert e.value.status_code == 429
    assert "user_id" not in req.session


def test_signing_in_again_issues_a_fresh_code(sent):
    u = _User()
    _, req = _login(u)
    u.login_code_attempts = settings.email_verify_max_attempts  # locked
    _, req = _login(u, req)
    _second_step(u, req, sent[-1][1])
    assert req.session == {"user_id": str(u.id)}


def test_expired_code_is_refused(sent):
    u = _User()
    _, req = _login(u)
    u.login_code_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with pytest.raises(HTTPException) as e:
        _second_step(u, req, sent[0][1])
    assert e.value.status_code == 400
    assert "user_id" not in req.session


def test_second_step_without_a_pending_login_is_401():
    u = _User()
    with pytest.raises(HTTPException) as e:
        _second_step(u, _Req(), "123456")
    assert e.value.status_code == 401


def test_second_step_after_2fa_was_turned_off_is_401(sent):
    u = _User()
    _, req = _login(u)
    u.two_factor_enabled = False
    with pytest.raises(HTTPException) as e:
        _second_step(u, req, sent[0][1])
    assert e.value.status_code == 401
    assert req.session == {}


def test_login_code_cannot_confirm_a_pending_email(sent):
    # The login code goes to the old address; it must not prove ownership of
    # the new one through /auth/verify.
    u = _User(pending="new@example.com")
    u.email_verify_code_hash = hash_code("999999")
    u.email_verify_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    _login(u)
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code=sent[0][1]), _Req(), _Session(u), u)
    assert e.value.status_code == 400
    assert u.email == EMAIL
    assert u.email_verify_code_hash == hash_code("999999")  # untouched by the login


# ─── PATCH /me toggle ─────────────────────────────────────────────────────────
def _patch(user, **body):
    return update_me(UpdateMeRequest(**body), _Req(), _Session(user), user)


def test_turning_2fa_on_needs_no_password():
    u = _User(two_factor=False)
    out = _patch(u, two_factor_enabled=True)
    assert u.two_factor_enabled is True
    assert out["two_factor_enabled"] is True


def test_turning_2fa_on_needs_a_verified_email():
    u = _User(two_factor=False, verified=False)
    with pytest.raises(HTTPException) as e:
        _patch(u, two_factor_enabled=True)
    assert e.value.status_code == 400
    assert u.two_factor_enabled is False


def test_turning_2fa_off_needs_the_current_password():
    u = _User()
    with pytest.raises(HTTPException) as e:
        _patch(u, two_factor_enabled=False, current_password="wrong")
    assert e.value.status_code == 403
    assert u.two_factor_enabled is True


def test_turning_2fa_off_lets_the_password_alone_sign_in(sent):
    u = _User()
    _patch(u, two_factor_enabled=False, current_password=PASSWORD)
    _, req = _login(u)
    assert req.session == {"user_id": str(u.id)}
    assert sent == []


def test_google_account_cannot_toggle_2fa():
    u = _User(two_factor=False, google=True)
    with pytest.raises(HTTPException) as e:
        _patch(u, two_factor_enabled=True)
    assert e.value.status_code == 403


def test_sending_the_current_value_is_a_noop():
    u = _User()
    _patch(u, two_factor_enabled=True)  # no password needed, nothing changes
    assert u.two_factor_enabled is True
