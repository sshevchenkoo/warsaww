"""Auth routes: Google OAuth login/callback, logout, and the current-user probe.

Flow: the browser hits /auth/login/google → Google consent → /auth/callback (the
registered redirect URI) → we upsert the user, store their id in the signed session
cookie, and bounce back to the frontend. The frontend then just reads /me.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.oauth import oauth
from app.catalog.db import get_session
from app.catalog.models import User
from app.config import settings

router = APIRouter()


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
    if not sub:
        raise HTTPException(400, "Google did not return a user id")

    user = session.query(User).filter_by(google_sub=sub).one_or_none()
    if user is None:
        user = User(google_sub=sub)
        session.add(user)
    # Refresh the mutable profile fields on every login.
    user.email = info.get("email")
    user.name = info.get("name")
    user.avatar_url = info.get("picture")
    session.commit()

    request.session["user_id"] = str(user.id)
    return RedirectResponse(settings.frontend_url)


@router.post("/auth/logout")
async def logout(request: Request) -> dict:
    request.session.clear()
    return {"status": "ok"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
    }
