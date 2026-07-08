"""Email verification: signed, time-limited tokens (itsdangerous) + transactional
send (Resend).

The token carries the user id, signed with the session secret — no DB storage,
self-expiring. Sending goes through Resend's REST API; without an API key it is a
logged no-op so local dev / an unconfigured deploy still works (links just aren't
delivered). The API key travels in the Authorization header, never a URL."""

import logging
import uuid

import httpx
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings

log = logging.getLogger(__name__)

_SALT = "email-verify"
RESEND_URL = "https://api.resend.com/emails"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_SALT)


def make_verify_token(user_id: uuid.UUID) -> str:
    return _serializer().dumps(str(user_id))


def read_verify_token(token: str) -> uuid.UUID | None:
    """Return the user id from a valid, unexpired token, else None."""
    try:
        raw = _serializer().loads(token, max_age=settings.email_verify_ttl_hours * 3600)
        return uuid.UUID(raw)
    except (BadSignature, SignatureExpired, ValueError, TypeError):
        return None


def send_verification_email(to_email: str, verify_url: str) -> None:
    """Send the verification link via Resend. No-op (warning) without an API key,
    and never raises — a provider hiccup must not fail registration (the user can
    request a resend)."""
    if not settings.resend_api_key:
        log.warning("RESEND_API_KEY not set — verification email to %s not sent", to_email)
        return
    html = (
        "<p>Confirm your email for Warsaw Events:</p>"
        f'<p><a href="{verify_url}">Verify my email</a></p>'
        f"<p>Or paste this link into your browser:<br>{verify_url}</p>"
        f"<p>This link expires in {settings.email_verify_ttl_hours} hours.</p>"
    )
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.email_from,
                "to": [to_email],
                "subject": "Verify your email — Warsaw Events",
                "html": html,
            },
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        log.warning("failed to send verification email to %s", to_email, exc_info=True)
