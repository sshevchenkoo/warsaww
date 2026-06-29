"""Auth dependency: resolve the logged-in user from the signed session cookie."""

import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.catalog.db import get_session
from app.catalog.models import User


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Return the logged-in User, or raise 401. The cookie holds only the user id;
    the row is the source of truth (a stale cookie clears itself).

    Also pins the request's DB identity for Row-Level Security: every
    authenticated endpoint depends on this, so `app.user_id` is set on the
    request's transaction before any query to an RLS-protected table. It is
    transaction-local (`set_config(..., is_local => true)`), so it is cleared
    automatically when the transaction ends and never leaks across pooled
    connections. Anonymous endpoints don't set it and don't touch RLS tables."""
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
    session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user.id)}
    )
    return user
