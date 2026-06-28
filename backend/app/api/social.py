"""Social routes: find users, mutual friendships (request → accept), and sharing
items with friends. All require the logged-in user."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.routes import ItemOut
from app.auth.deps import current_user
from app.catalog.db import get_session
from app.catalog.models import Friendship, Item, SavedItem, SharedEvent, User

router = APIRouter()


# ─── Response shapes ──────────────────────────────────────────────────────────
class PublicUser(BaseModel):
    id: uuid.UUID
    name: str | None
    avatar_url: str | None
    # relationship to the requester: self | friends | request_sent | request_received | none
    friendship: str = "none"


class SharedEventOut(BaseModel):
    id: uuid.UUID
    item: ItemOut
    from_user: PublicUser
    message: str | None
    created_at: datetime


class ShareRequest(BaseModel):
    to_user_id: uuid.UUID
    item_id: uuid.UUID
    message: str | None = None


# ─── Friendship helpers ───────────────────────────────────────────────────────
def _friendship(session: Session, a: uuid.UUID, b: uuid.UUID) -> Friendship | None:
    """The friendship row between a and b in either direction, if any."""
    return session.execute(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == a, Friendship.addressee_id == b),
                and_(Friendship.requester_id == b, Friendship.addressee_id == a),
            )
        )
    ).scalar_one_or_none()


def _status(row: Friendship | None, me: uuid.UUID) -> str:
    if row is None:
        return "none"
    if row.status == "accepted":
        return "friends"
    return "request_sent" if row.requester_id == me else "request_received"


def _are_friends(session: Session, a: uuid.UUID, b: uuid.UUID) -> bool:
    row = _friendship(session, a, b)
    return row is not None and row.status == "accepted"


def _public(user: User, friendship: str) -> PublicUser:
    return PublicUser(
        id=user.id, name=user.name, avatar_url=user.avatar_url, friendship=friendship
    )


# ─── User search & profiles ───────────────────────────────────────────────────
@router.get("/users/search")
def search_users(
    q: str = Query(min_length=2, max_length=100),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> list[PublicUser]:
    """Find users by name (substring) or exact email, excluding yourself."""
    term = q.strip()
    found = (
        session.query(User)
        .filter(User.id != user.id)
        .filter(or_(User.name.ilike(f"%{term}%"), User.email == term))
        .order_by(User.name.asc())
        .limit(20)
        .all()
    )
    status_by_other = _my_statuses(session, user.id)
    return [_public(u, status_by_other.get(u.id, "none")) for u in found]


def _my_statuses(session: Session, me: uuid.UUID) -> dict[uuid.UUID, str]:
    """Map of other_user_id → friendship status, for every relation I'm part of."""
    rows = session.execute(
        select(Friendship).where(
            or_(Friendship.requester_id == me, Friendship.addressee_id == me)
        )
    ).scalars().all()
    out: dict[uuid.UUID, str] = {}
    for r in rows:
        other = r.addressee_id if r.requester_id == me else r.requester_id
        out[other] = _status(r, me)
    return out


@router.get("/users/{user_id}")
def get_profile(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> PublicUser:
    """Public profile of a user (name/avatar + relationship to you)."""
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    rel = "self" if target.id == user.id else _status(_friendship(session, user.id, target.id), user.id)
    return _public(target, rel)


@router.get("/users/{user_id}/saved")
def get_user_saved(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> list[ItemOut]:
    """Another user's saved items — visible to the user themselves and to friends."""
    if user_id != user.id and not _are_friends(session, user.id, user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only friends can see saved items")
    items = (
        session.query(Item)
        .join(SavedItem, SavedItem.item_id == Item.id)
        .filter(SavedItem.user_id == user_id)
        .order_by(SavedItem.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ItemOut.model_validate(item) for item in items]


# ─── Friend requests ──────────────────────────────────────────────────────────
@router.post("/friends/request/{user_id}")
def send_request(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot friend yourself")
    if session.get(User, user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    existing = _friendship(session, user.id, user_id)
    if existing is not None:
        if existing.status == "accepted":
            raise HTTPException(status.HTTP_409_CONFLICT, "Already friends")
        if existing.requester_id == user.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Request already sent")
        # They had already requested me → accept it (mutual now).
        existing.status = "accepted"
        session.commit()
        return {"status": "friends"}

    session.add(Friendship(requester_id=user.id, addressee_id=user_id, status="pending"))
    session.commit()
    return {"status": "request_sent"}


@router.post("/friends/accept/{user_id}")
def accept_request(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Accept a pending request that user_id sent to me."""
    row = session.execute(
        select(Friendship).where(
            Friendship.requester_id == user_id,
            Friendship.addressee_id == user.id,
            Friendship.status == "pending",
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending request from this user")
    row.status = "accepted"
    session.commit()
    return {"status": "friends"}


@router.post("/friends/decline/{user_id}")
def decline_request(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Decline a pending request that user_id sent to me."""
    session.execute(
        delete(Friendship).where(
            Friendship.requester_id == user_id,
            Friendship.addressee_id == user.id,
            Friendship.status == "pending",
        )
    )
    session.commit()
    return {"status": "declined"}


@router.delete("/friends/{user_id}")
def remove_friend(
    user_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Remove a friend, or cancel an outgoing request (deletes the row either way)."""
    session.execute(
        delete(Friendship).where(
            or_(
                and_(Friendship.requester_id == user.id, Friendship.addressee_id == user_id),
                and_(Friendship.requester_id == user_id, Friendship.addressee_id == user.id),
            )
        )
    )
    session.commit()
    return {"status": "removed"}


@router.get("/friends")
def list_friends(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = Query(200, ge=1, le=500),
) -> list[PublicUser]:
    """My accepted friends (bounded — audit #8)."""
    rows = session.execute(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        ).limit(limit)
    ).scalars().all()
    other_ids = [
        r.addressee_id if r.requester_id == user.id else r.requester_id for r in rows
    ]
    if not other_ids:
        return []
    users = session.query(User).filter(User.id.in_(other_ids)).all()
    return [_public(u, "friends") for u in users]


@router.get("/friends/requests")
def list_requests(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = Query(200, ge=1, le=500),
) -> list[PublicUser]:
    """Incoming pending requests (people who asked to be my friend; bounded #8)."""
    rows = session.execute(
        select(Friendship).where(
            Friendship.addressee_id == user.id, Friendship.status == "pending"
        ).limit(limit)
    ).scalars().all()
    requester_ids = [r.requester_id for r in rows]
    if not requester_ids:
        return []
    users = session.query(User).filter(User.id.in_(requester_ids)).all()
    return [_public(u, "request_received") for u in users]


# ─── Sharing ──────────────────────────────────────────────────────────────────
@router.post("/share")
def share_event(
    req: ShareRequest,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Share an item with a friend. Both directions must be accepted friends."""
    if not _are_friends(session, user.id, req.to_user_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only share with friends")
    if session.get(Item, req.item_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    # Idempotent: re-sharing the same item to the same friend is a no-op.
    session.execute(
        pg_insert(SharedEvent)
        .values(
            from_user_id=user.id,
            to_user_id=req.to_user_id,
            item_id=req.item_id,
            message=req.message,
        )
        .on_conflict_do_nothing(constraint="uq_share_once")
    )
    session.commit()
    return {"status": "shared"}


@router.get("/me/shared")
def list_shared_with_me(
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
) -> list[SharedEventOut]:
    """Items friends shared with me, newest first (bounded — audit #8)."""
    rows = (
        session.query(SharedEvent, Item, User)
        .join(Item, Item.id == SharedEvent.item_id)
        .join(User, User.id == SharedEvent.from_user_id)
        .filter(SharedEvent.to_user_id == user.id)
        .order_by(SharedEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        SharedEventOut(
            id=shared.id,
            item=ItemOut.model_validate(item),
            from_user=_public(sender, "friends"),
            message=shared.message,
            created_at=shared.created_at,
        )
        for shared, item, sender in rows
    ]


@router.delete("/me/shared/{share_id}")
def dismiss_shared(
    share_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Remove a share from my inbox."""
    session.execute(
        delete(SharedEvent).where(
            SharedEvent.id == share_id, SharedEvent.to_user_id == user.id
        )
    )
    session.commit()
    return {"status": "removed"}
