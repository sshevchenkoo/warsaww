"""Email-verification tokens (signed, self-expiring) and the send no-op path.
No network / no DB."""

import uuid

from app.auth import email as emailmod
from app.auth.email import make_verify_token, read_verify_token, send_verification_email


def test_token_roundtrip():
    uid = uuid.uuid4()
    token = make_verify_token(uid)
    assert read_verify_token(token) == uid


def test_tampered_or_garbage_token_is_none():
    assert read_verify_token("not-a-real-token") is None
    token = make_verify_token(uuid.uuid4())
    assert read_verify_token(token + "x") is None  # signature no longer valid


def test_token_uses_distinct_salt_from_sessions():
    # A token signed for a different purpose must not validate as a verify token.
    from itsdangerous import URLSafeTimedSerializer

    from app.config import settings

    other = URLSafeTimedSerializer(settings.session_secret, salt="something-else")
    assert read_verify_token(other.dumps(str(uuid.uuid4()))) is None


def test_send_is_noop_without_api_key(monkeypatch, caplog):
    # Unconfigured environment must not raise — registration still works.
    monkeypatch.setattr(emailmod.settings, "resend_api_key", None)
    send_verification_email("user@example.com", "https://example.com/verify?token=x")
    assert any("not sent" in r.message for r in caplog.records)
