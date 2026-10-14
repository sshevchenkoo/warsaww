"""Attachments: files a user pins to an event or place (a PDF ticket, a photo).

Everything is under `/me`, which the ingress + Next rewrites already route to
the API, and everything is private: list, upload, serve and delete all filter
on the session user (and RLS scopes `user_files` to that user underneath).

The type is decided from the bytes, never from the client's filename or
Content-Type: a PDF must start with `%PDF-`, an image must open in Pillow as
one of the allowed formats. Files are stored as uploaded (no re-encode, unlike
avatars) so a ticket's barcode stays exactly as issued."""

import io
import re
import uuid
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.catalog.db import get_session
from app.catalog.models import Item, User, UserFile
from app.config import settings

router = APIRouter()

# Pillow format name → the MIME type we store and serve. Keep in sync with
# ck_user_files_type and FILE_TYPES in frontend/src/lib/files.ts.
IMAGE_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
PDF_TYPE = "application/pdf"
FILE_TYPES = {PDF_TYPE, *IMAGE_FORMATS.values()}

# Same decompression-bomb bound as avatars: refuse by header dimensions before
# Pillow touches the pixel data.
MAX_FILE_PIXELS = 50_000_000
MAX_FILENAME = 120


class FileOut(BaseModel):
    id: uuid.UUID
    item_id: uuid.UUID
    item_name: str
    filename: str
    content_type: str
    size: int
    created_at: datetime


def _sniff(raw: bytes) -> str:
    """Return the stored MIME type for `raw`, or raise 415 if it is neither a
    PDF nor a valid PNG/JPEG/WebP/GIF image."""
    if raw.startswith(b"%PDF-"):
        return PDF_TYPE
    unsupported = HTTPException(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use a PDF or a PNG, JPEG, WebP or GIF image"
    )
    try:
        img = Image.open(io.BytesIO(raw))  # lazy — reads the header only
    except (UnidentifiedImageError, OSError, ValueError):
        raise unsupported from None
    mime = IMAGE_FORMATS.get(img.format or "")
    if mime is None:
        raise unsupported
    if (img.width or 0) * (img.height or 0) > MAX_FILE_PIXELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image dimensions too large")
    try:
        img.verify()  # structural check (truncated/corrupt files fail here)
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a valid image") from None
    return mime


def _clean_filename(name: str | None) -> str:
    """Display name only (never a path): drop any directory part and control
    characters, cap the length."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    return base[:MAX_FILENAME] or "file"


def _out(f: UserFile, item_name: str) -> FileOut:
    return FileOut(
        id=f.id,
        item_id=f.item_id,
        item_name=item_name,
        filename=f.filename,
        content_type=f.content_type,
        size=f.size,
        created_at=f.created_at,
    )


@router.get("/me/files")
def list_files(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> list[FileOut]:
    """The user's attachments, newest first, with the item each belongs to.
    Bounded by files_max_per_user, so no pagination is needed."""
    rows = session.execute(
        select(UserFile, Item.name)
        .join(Item, Item.id == UserFile.item_id)
        .where(UserFile.user_id == user.id)
        .order_by(UserFile.created_at.desc())
    ).all()
    return [_out(f, name) for f, name in rows]


@router.post("/me/files", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile,
    item_id: uuid.UUID = Form(),
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> FileOut:
    """Attach a PDF or an image to an event/place."""
    # Read at most max+1 bytes so an oversized (or lying Content-Length) upload
    # is rejected without pulling the whole thing into memory.
    raw = await file.read(settings.files_max_upload_bytes + 1)
    if len(raw) > settings.files_max_upload_bytes:
        mb = settings.files_max_upload_bytes // (1024 * 1024)
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"File too large (max {mb} MB)")
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload")
    content_type = _sniff(raw)

    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")

    # Lock the user's row so two parallel uploads can't both pass the count
    # check and land the user one file over the limit.
    session.execute(select(User.id).where(User.id == user.id).with_for_update())
    count = session.scalar(select(func.count()).where(UserFile.user_id == user.id))
    if count >= settings.files_max_per_user:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You can keep up to {settings.files_max_per_user} files. Delete one first.",
        )

    row = UserFile(
        user_id=user.id,
        item_id=item.id,
        filename=_clean_filename(file.filename),
        content_type=content_type,
        size=len(raw),
        data=raw,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _out(row, item.name)


def _own_file(session: Session, file_id: uuid.UUID, user: User) -> UserFile:
    """The caller's file, or 404 — someone else's file looks exactly like a
    missing one, so ids can't be probed."""
    f = session.scalar(
        select(UserFile).where(UserFile.id == file_id, UserFile.user_id == user.id)
    )
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    return f


@router.get("/me/files/{file_id}")
def get_file(
    file_id: uuid.UUID,
    download: bool = False,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Serve the bytes to their owner: inline for the preview, or as a download
    with ?download=1."""
    f = _own_file(session, file_id, user)
    disposition = "attachment" if download else "inline"
    return Response(
        content=f.data,
        media_type=f.content_type,
        headers={
            # RFC 5987 form, so any UTF-8 name survives and nothing can break
            # out of the header value.
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(f.filename)}",
            # The type was sniffed on upload; stop the browser second-guessing it.
            "X-Content-Type-Options": "nosniff",
            # Private data: never in a shared cache.
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/me/files/{file_id}")
def delete_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    session.delete(_own_file(session, file_id, user))
    session.commit()
    return {"status": "removed"}
