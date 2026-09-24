"""PATCH /me (profile edit) and the email-change confirmation through
/auth/verify. Pure logic with fakes — no HTTP server, DB, Redis or email."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.api import auth as authmod
from app.api.auth import (
    UpdateMeRequest,
    VerifyRequest,
    resend_verification,
    update_me,
    verify_email,
)
from app.auth.email import hash_code
from app.auth.passwords import hash_password

PASSWORD = "correct horse battery"
PASSWORD_HASH = hash_password(PASSWORD)  # bcrypt is slow — hash once


class _Req:
    def __init__(self):
        self.session = {}
        self.headers = {}
        self.client = type("C", (), {"host": "1.2.3.4"})()


class _User:
    def __init__(self, *, google=False, verified=True, pending=None):
        self.id = uuid.uuid4()
        self.email = "old@example.com"
        self.name = "Old Name"
        self.avatar_url = None
        self.google_sub = "g-123" if google else None
        self.password_hash = None if google else PASSWORD_HASH
        self.email_verified = verified
        self.pending_email = pending
        self.email_verify_code_hash = None
        self.email_verify_code_expires_at = None
        self.email_verify_attempts = 0


class _Session:
    """Fakes the bits the endpoints use: the `_email_taken` query chain
    (query().filter().first()), commit and rollback. `taken` is the set of
    emails other accounts already own; `commit_error` makes commit raise."""

    def __init__(self, taken=(), commit_error=None):
        self.taken = set(taken)
        self.commit_error = commit_error
        self.commits = 0
        self.rollbacks = 0
        self._email = None

    def query(self, _model):
        return self

    def filter(self, email_clause, _id_clause):
        self._email = email_clause.right.value  # User.email == <value>
        return self

    def first(self):
        return object() if self._email in self.taken else None

    def commit(self):
        if self.commit_error:
            raise self.commit_error
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    # The brute-force limiter hits Redis; bypass it.
    monkeypatch.setattr(authmod, "_rate_limit_auth", lambda request: None)


@pytest.fixture
def sent(monkeypatch):
    """Capture outgoing verification emails as (to, code) pairs."""
    out = []
    monkeypatch.setattr(authmod, "send_verification_email", lambda to, code: out.append((to, code)))
    return out


def _patch(user, session=None, **body):
    return update_me(UpdateMeRequest(**body), _Req(), session or _Session(), user)


# ─── name ─────────────────────────────────────────────────────────────────────
def test_name_change_applies_at_once(sent):
    u = _User()
    out = _patch(u, name="  New Name  ")
    assert u.name == "New Name"  # trimmed
    assert out["name"] == "New Name"
    assert sent == []  # a name change sends nothing


def test_blank_name_clears_it():
    u = _User()
    _patch(u, name="   ")
    assert u.name is None


def test_omitted_name_is_left_alone():
    u = _User()
    _patch(u)
    assert u.name == "Old Name"


def test_name_too_long_is_rejected():
    with pytest.raises(ValueError):
        UpdateMeRequest(name="x" * 101)


# ─── email change request ─────────────────────────────────────────────────────
def test_email_change_goes_to_pending_and_codes_the_new_address(sent):
    u = _User()
    out = _patch(u, email="new@example.com", current_password=PASSWORD)
    assert u.email == "old@example.com"  # login address unchanged until confirmed
    assert u.email_verified is True  # search stays open meanwhile
    assert u.pending_email == "new@example.com"
    assert out["pending_email"] == "new@example.com"
    assert [to for to, _ in sent] == ["new@example.com"]
    assert u.email_verify_code_hash == hash_code(sent[0][1])


def test_email_change_needs_the_current_password(sent):
    u = _User()
    for pw in (None, "wrong password"):
        with pytest.raises(HTTPException) as e:
            _patch(u, email="new@example.com", current_password=pw)
        assert e.value.status_code == 403
    assert u.pending_email is None
    assert sent == []


def test_email_taken_by_another_account_is_409(sent):
    u = _User()
    with pytest.raises(HTTPException) as e:
        _patch(
            u,
            _Session(taken={"new@example.com"}),
            email="new@example.com",
            current_password=PASSWORD,
        )
    assert e.value.status_code == 409
    assert u.pending_email is None
    assert sent == []


def test_refused_email_change_does_not_apply_the_name():
    u = _User()
    with pytest.raises(HTTPException):
        _patch(u, name="New Name", email="new@example.com", current_password="wrong")
    assert u.name == "Old Name"


def test_google_account_cannot_change_email(sent):
    u = _User(google=True)
    with pytest.raises(HTTPException) as e:
        _patch(u, email="new@example.com")
    assert e.value.status_code == 403
    assert u.email == "old@example.com"
    assert u.pending_email is None


def test_google_account_can_still_change_name():
    u = _User(google=True)
    _patch(u, name="New Name", email="old@example.com")  # same email = no change
    assert u.name == "New Name"


def test_resubmitting_current_email_cancels_the_pending_change(sent):
    u = _User(pending="new@example.com")
    u.email_verify_code_hash = hash_code("123456")
    _patch(u, email="old@example.com")  # no password needed: nothing changes hands
    assert u.pending_email is None
    assert u.email_verify_code_hash is None  # the code for new@ is dead too
    assert sent == []


# ─── confirming the change via /auth/verify ───────────────────────────────────
def _with_code(u, code="123456"):
    u.email_verify_code_hash = hash_code(code)
    u.email_verify_code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    return u


def test_verify_swaps_in_the_pending_email():
    u = _with_code(_User(pending="new@example.com"))
    out = verify_email(VerifyRequest(code="123456"), _Req(), _Session(), u)
    assert u.email == "new@example.com"
    assert u.pending_email is None
    assert u.email_verified is True
    assert u.email_verify_code_hash is None
    assert out["email"] == "new@example.com"


def test_verify_on_unverified_account_with_pending_email_verifies_the_new_one():
    u = _with_code(_User(verified=False, pending="new@example.com"))
    verify_email(VerifyRequest(code="123456"), _Req(), _Session(), u)
    assert (u.email, u.email_verified) == ("new@example.com", True)


def test_verify_wrong_code_keeps_the_old_email():
    u = _with_code(_User(pending="new@example.com"))
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="000000"), _Req(), _Session(), u)
    assert e.value.status_code == 400
    assert u.email == "old@example.com"
    assert u.pending_email == "new@example.com"


def test_verify_409_and_drops_request_if_address_was_claimed_meanwhile():
    u = _with_code(_User(pending="new@example.com"))
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="123456"), _Req(), _Session(taken={"new@example.com"}), u)
    assert e.value.status_code == 409
    assert u.email == "old@example.com"
    assert u.pending_email is None
    assert u.email_verify_code_hash is None


def test_verify_409_when_unique_constraint_loses_a_race():
    u = _with_code(_User(pending="new@example.com"))
    s = _Session(commit_error=IntegrityError("UPDATE users", {}, Exception("dup")))
    with pytest.raises(HTTPException) as e:
        verify_email(VerifyRequest(code="123456"), _Req(), s, u)
    assert e.value.status_code == 409
    assert s.rollbacks == 1


# ─── /auth/resend with a pending change ───────────────────────────────────────
def test_resend_codes_the_pending_address_even_when_verified(sent):
    u = _User(verified=True, pending="new@example.com")
    assert resend_verification(_Req(), _Session(), u) == {"status": "sent"}
    assert [to for to, _ in sent] == ["new@example.com"]


def test_resend_is_noop_when_verified_and_nothing_pending(sent):
    u = _User(verified=True)
    assert resend_verification(_Req(), _Session(), u) == {"status": "already_verified"}
    assert sent == []
