"""Auth routes. Two ways to sign in, both ending in the same session cookie:

- Google OAuth: /auth/login/google → Google consent → /auth/callback.
- Email + password: /auth/register, /auth/login.

Plus /auth/logout, the /me probe and PATCH /me (profile edit). Accounts are keyed
by email, so signing up by password and later using Google with the same email is
one account.
"""

import logging
from datetime import datetime, timedelta, timezone

from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.email import generate_code, hash_code, send_verification_email, verify_code
from app.auth.oauth import oauth
from app.auth.passwords import MAX_PASSWORD_BYTES, hash_password, verify_password
from app.catalog.db import get_session
from app.catalog.models import User
from app.config import settings
from app.ratelimit import check_auth_rate

log = logging.getLogger(__name__)

router = APIRouter()


def _client_ip(request: Request) -> str:
    """Best-effort client IP for the auth rate limit. Behind the ingress the real
    client is the first hop in X-Forwarded-For; fall back to the socket peer."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_auth(request: Request) -> None:
    """Throttle auth attempts per client IP; raise 429 when the minute cap is hit."""
    if not check_auth_rate(_client_ip(request)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many attempts. Try again in a minute.",
        )


def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "email_verified": user.email_verified,
        "pending_email": user.pending_email,
    }


def _issue_verification(user: User, session: Session) -> None:
    """Generate a fresh verification code for `user`, store its keyed hash + expiry
    (resetting the attempt counter), and email the code. It goes to the pending
    address while an email change is in flight, otherwise to the account's own
    email if that is still unverified; no-op when there is nothing to verify."""
    target = user.pending_email or (None if user.email_verified else user.email)
    if not target:
        return
    code = generate_code()
    user.email_verify_code_hash = hash_code(code)
    user.email_verify_code_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.email_verify_code_ttl_minutes
    )
    user.email_verify_attempts = 0
    session.commit()
    send_verification_email(target, code)


def _email_taken(session: Session, email: str, user: User) -> bool:
    """True if another account already uses `email` as its login."""
    return (
        session.query(User).filter(User.email == email, User.id != user.id).first()
        is not None
    )


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_BYTES)
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.get("/auth/login/google")
async def login_google(request: Request) -> RedirectResponse:
    redirect_uri = f"{settings.frontend_url}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(
    request: Request, session: Session = Depends(get_session)
) -> RedirectResponse:
    try:
        token = await oauth.google.authorize_access_token(request)
        info = token.get("userinfo") or await oauth.google.userinfo(token=token)
    except OAuthError as exc:
        # Expected failure modes (state mismatch, expired/denied code, Google
        # 5xx) are routine — send the user back to login with an error flag
        # instead of returning a 500.
        log.warning("OAuth callback failed: %s", exc)
        return RedirectResponse(f"{settings.frontend_url}/login?error=oauth")
    sub = info.get("sub")
    email = info.get("email")
    if not sub:
        raise HTTPException(400, "Google did not return a user id")

    user = session.query(User).filter_by(google_sub=sub).one_or_none()
    if user is None and email:
        # Link to an existing account with the same email (e.g. one made by
        # password). Google has verified the user owns this email, so linking is
        # legitimate — BUT any password already on that account was set before
        # ownership was proven and could belong to an attacker who pre-registered
        # this email (account pre-hijacking). Void it on link: the account becomes
        # Google-owned and the pre-set password stops working.
        user = session.query(User).filter_by(email=email).one_or_none()
        if user is not None and user.password_hash is not None:
            log.info("OAuth link: clearing pre-existing password on account %s", user.id)
            user.password_hash = None
    if user is None:
        user = User()
        session.add(user)

    user.google_sub = sub
    if email:
        user.email = email
        user.email_verified = True  # Google has verified the address
    if info.get("name"):
        user.name = info["name"]
    if info.get("picture"):
        user.avatar_url = info["picture"]
    session.commit()

    request.session["user_id"] = str(user.id)
    return RedirectResponse(settings.frontend_url)


@router.post("/auth/register")
def register(
    req: RegisterRequest, request: Request, session: Session = Depends(get_session)
) -> dict:
    _rate_limit_auth(request)
    if session.query(User).filter_by(email=req.email).one_or_none() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=str(req.email),
        name=req.name,
        password_hash=hash_password(req.password),
    )
    session.add(user)
    session.commit()
    request.session["user_id"] = str(user.id)
    _issue_verification(user, session)
    return _user_payload(user)


@router.post("/auth/login")
def login(
    req: LoginRequest, request: Request, session: Session = Depends(get_session)
) -> dict:
    _rate_limit_auth(request)
    user = session.query(User).filter_by(email=req.email).one_or_none()
    if user is None or not user.password_hash or not verify_password(
        req.password, user.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    # Optional gate (off by default): refuse login until the email is verified.
    if settings.require_email_verification and not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Please verify your email before signing in. Check your inbox or request a new link.",
        )
    request.session["user_id"] = str(user.id)
    return _user_payload(user)


class VerifyRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


@router.post("/auth/verify")
def verify_email(
    req: VerifyRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Confirm the logged-in user's email with the code we emailed. Wrong codes
    are counted and capped; an expired or exhausted code needs a fresh resend.
    With an email change pending, a correct code swaps the new address in.
    Returns the updated user payload (email_verified flips to true on success)."""
    _rate_limit_auth(request)
    if user.email_verified and not user.pending_email:
        return _user_payload(user)
    now = datetime.now(timezone.utc)
    if (
        not user.email_verify_code_hash
        or user.email_verify_code_expires_at is None
        or user.email_verify_code_expires_at < now
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Your code expired. Request a new one."
        )
    if user.email_verify_attempts >= settings.email_verify_max_attempts:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Request a new code."
        )
    if not verify_code(req.code, user.email_verify_code_hash):
        user.email_verify_attempts += 1
        session.commit()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid code.")
    if user.pending_email:
        # The code proved ownership of the new address. Another account may have
        # claimed it since the change was requested — then drop the request so
        # the user can pick a different address.
        if _email_taken(session, user.pending_email, user):
            user.pending_email = None
            _clear_code(user)
            session.commit()
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
        user.email = user.pending_email
        user.pending_email = None
    user.email_verified = True
    _clear_code(user)
    try:
        session.commit()
    except IntegrityError:
        # Lost a race with another account claiming the same address.
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered") from None
    return _user_payload(user)


def _clear_code(user: User) -> None:
    user.email_verify_code_hash = None
    user.email_verify_code_expires_at = None
    user.email_verify_attempts = 0


@router.post("/auth/resend")
def resend_verification(
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Re-send a fresh verification code to the logged-in user (rate-limited to
    prevent using it as an email-spam relay)."""
    _rate_limit_auth(request)
    if user.email_verified and not user.pending_email:
        return {"status": "already_verified"}
    _issue_verification(user, session)
    return {"status": "sent"}


@router.post("/auth/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_payload(user)


class UpdateMeRequest(BaseModel):
    """Omitted fields stay unchanged; `name` set to null or blank clears it."""

    name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    # Needed to change a password account's email, so a hijacked session alone
    # can't move the account to an address the attacker controls.
    current_password: str | None = Field(default=None, max_length=MAX_PASSWORD_BYTES)


@router.patch("/me")
def update_me(
    req: UpdateMeRequest,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(current_user),
) -> dict:
    """Edit the profile. A name change applies at once. An email change is only
    requested: the new address lands in `pending_email` and gets a verification
    code, and POST /auth/verify swaps it in. Until then the old email keeps
    working for login, so a typo can't lock the user out, and search stays open.
    Sending the current email again cancels a pending change."""
    new_email = str(req.email) if req.email is not None else None
    changing_email = new_email is not None and new_email != user.email
    # Validate everything before touching the row, so a refused email change
    # doesn't half-apply a name change.
    if changing_email:
        if user.google_sub:
            # auth_callback rewrites user.email from Google on every login, so a
            # change made here would silently revert.
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "This account's email is managed by Google."
            )
        _rate_limit_auth(request)  # current_password is otherwise guessable here
        if not user.password_hash or not verify_password(
            req.current_password or "", user.password_hash
        ):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Current password is incorrect.")
        if _email_taken(session, new_email, user):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    if "name" in req.model_fields_set:
        user.name = (req.name or "").strip() or None

    if changing_email:
        user.pending_email = new_email
        _issue_verification(user, session)  # commits
    else:
        if new_email is not None and user.pending_email:
            user.pending_email = None
            _clear_code(user)
        session.commit()
    return _user_payload(user)
