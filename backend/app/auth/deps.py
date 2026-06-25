"""Auth dependency: resolve the logged-in user from the signed session cookie."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.catalog.db import get_session
from app.catalog.models import User


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Return the logged-in User, or raise 401. The cookie holds only the user id;
    the row is the source of truth (a stale cookie clears itself)."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        # A tampered or stale-format cookie value: clear it and treat as
        # unauthenticated rather than letting the parse raise a 500.
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated") from None
    user = session.get(User, user_uuid)
    if user is None:
        request.session.clear()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user
