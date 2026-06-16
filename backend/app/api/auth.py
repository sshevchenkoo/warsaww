"""Auth routes. Two ways to sign in, both ending in the same session cookie:

- Google OAuth: /auth/login/google → Google consent → /auth/callback.
- Email + password: /auth/register, /auth/login.

Plus /auth/logout and the /me probe. Accounts are keyed by email, so signing up
by password and later using Google with the same email is one account.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.oauth import oauth
from app.auth.passwords import MAX_PASSWORD_BYTES, hash_password, verify_password
from app.catalog.db import get_session
from app.catalog.models import User
from app.config import settings

router = APIRouter()


def _user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
    }


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
    token = await oauth.google.authorize_access_token(request)
    info = token.get("userinfo") or await oauth.google.userinfo(token=token)
    sub = info.get("sub")
    email = info.get("email")
    if not sub:
        raise HTTPException(400, "Google did not return a user id")

    user = session.query(User).filter_by(google_sub=sub).one_or_none()
    if user is None and email:
        # Link to an existing account with the same email (e.g. one made by password).
        user = session.query(User).filter_by(email=email).one_or_none()
    if user is None:
        user = User()
        session.add(user)

    user.google_sub = sub
    if email:
        user.email = email
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
    return _user_payload(user)


@router.post("/auth/login")
def login(
    req: LoginRequest, request: Request, session: Session = Depends(get_session)
) -> dict:
    user = session.query(User).filter_by(email=req.email).one_or_none()
    if user is None or not user.password_hash or not verify_password(
        req.password, user.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    request.session["user_id"] = str(user.id)
    return _user_payload(user)


@router.post("/auth/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return _user_payload(user)
