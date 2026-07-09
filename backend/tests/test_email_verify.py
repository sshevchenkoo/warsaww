"""Email verification via a numeric code: code generation, keyed hashing, and
the send no-op path. No network / no DB."""

import re

from app.auth import email as emailmod
from app.auth.email import generate_code, hash_code, send_verification_email, verify_code


def test_generate_code_is_six_digits():
    for _ in range(50):
        assert re.fullmatch(r"\d{6}", generate_code())  # always zero-padded 6 digits


def test_hash_roundtrip_and_reject_wrong_code():
    code = generate_code()
    h = hash_code(code)
    assert h != code  # never store the code itself
    assert verify_code(code, h) is True
    wrong = "111111" if code != "111111" else "222222"
    assert verify_code(wrong, h) is False


def test_hash_is_keyed_by_session_secret(monkeypatch):
    # Same code under two secrets → different hash, and a hash made under one
    # secret must not verify under another (keyed HMAC, not a bare digest).
    monkeypatch.setattr(emailmod.settings, "session_secret", "secret-A")
    h_a = hash_code("123456")
    monkeypatch.setattr(emailmod.settings, "session_secret", "secret-B")
    assert hash_code("123456") != h_a
    assert verify_code("123456", h_a) is False


def test_send_is_noop_without_api_key(monkeypatch, caplog):
    # Unconfigured environment must not raise — registration still works.
    monkeypatch.setattr(emailmod.settings, "resend_api_key", None)
    send_verification_email("user@example.com", "123456")
    assert any("not sent" in r.message for r in caplog.records)
