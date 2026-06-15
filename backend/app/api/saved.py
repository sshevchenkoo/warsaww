"""Saved-items routes: a logged-in user's favorites. All require current_user."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.routes import ItemOut
from app.auth.deps import current_user
from app.catalog.db import get_session
from app.catalog.models import Item, SavedItem, User

router = APIRouter()


@router.get("/me/saved")
def list_saved(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[ItemOut]:
    """The user's saved items, newest first."""
    items = (
        session.query(Item)
        .join(SavedItem, SavedItem.item_id == Item.id)
        .filter(SavedItem.user_id == user.id)
        .order_by(SavedItem.created_at.desc())
        .all()
    )
    return [ItemOut.model_validate(item) for item in items]


@router.get("/me/saved/ids")
def saved_ids(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[uuid.UUID]:
    """Just the saved item ids — used to mark hearts on the search page cheaply."""
    rows = session.execute(
        select(SavedItem.item_id).where(SavedItem.user_id == user.id)
    ).scalars()
    return list(rows)


@router.post("/me/saved/{item_id}")
def save_item(
    item_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    if session.get(Item, item_id) is None:
        raise HTTPException(404, "Item not found")
    # Idempotent: saving an already-saved item is a no-op, not an error.
    session.execute(
        pg_insert(SavedItem)
        .values(user_id=user.id, item_id=item_id)
        .on_conflict_do_nothing(constraint="uq_saved_user_item")
    )
    session.commit()
    return {"status": "saved"}


@router.delete("/me/saved/{item_id}")
def unsave_item(
    item_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    session.execute(
        delete(SavedItem).where(
            SavedItem.user_id == user.id, SavedItem.item_id == item_id
        )
    )
    session.commit()
    return {"status": "removed"}
