"""Email verification via a short numeric code.

Registration emails the user a 6-digit code; they type it back into the app to
prove they own the address. Only a keyed hash of the code is stored (HMAC-SHA256
under the session secret), never the code itself, and it is compared in constant
time. Delivery goes through Resend's REST API; without an API key it is a logged
no-op so local dev / an unconfigured deploy still works (codes just aren't
delivered). The API key travels in the Authorization header."""

import hmac
import logging
import secrets
from hashlib import sha256

import httpx

from app.config import settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
CODE_DIGITS = 6


def generate_code() -> str:
    """A zero-padded 6-digit code, uniformly random (secrets, not random)."""
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def hash_code(code: str) -> str:
    """Keyed hash of a code — what we store. The session secret keys the HMAC so a
    leaked DB alone can't be brute-forced offline without it."""
    return hmac.new(settings.session_secret.encode(), code.encode(), sha256).hexdigest()


def verify_code(code: str, code_hash: str) -> bool:
    """Constant-time comparison against a stored hash."""
    return hmac.compare_digest(hash_code(code), code_hash)


def send_verification_email(to_email: str, code: str) -> None:
    """Email the verification code via Resend. No-op (warning) without an API key,
    and never raises — a provider hiccup must not fail registration (the user can
    request a resend)."""
    if not settings.resend_api_key:
        log.warning("RESEND_API_KEY not set — verification code to %s not sent", to_email)
        return
    minutes = settings.email_verify_code_ttl_minutes
    html = (
        "<p>Your Warsaw Events verification code:</p>"
        f'<p style="font-size:28px;font-weight:700;letter-spacing:4px">{code}</p>'
        f"<p>Enter it in the app to confirm your email. It expires in {minutes} minutes.</p>"
    )
    payload = {
        "from": settings.email_from,
        "to": [to_email],
        "subject": f"{code} is your Warsaw Events verification code",
        "html": html,
    }
    if settings.email_reply_to:
        payload["reply_to"] = settings.email_reply_to  # replies land in your inbox
    try:
        resp = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        log.warning("failed to send verification code to %s", to_email, exc_info=True)
