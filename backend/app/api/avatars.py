"""Avatar upload/serve.

Upload (`POST /me/avatar`) is authenticated and goes through `/me`, which the
ingress + Next rewrites already route to the API. Serving (`GET /avatars/{id}`)
is public and cacheable so it works on any profile/card. Images are re-encoded
server-side to a small JPEG square, so the input size is bounded at the door and
the stored bytes are tiny regardless of what was uploaded (Postgres, capped)."""

import hashlib
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.catalog.db import get_session
from app.catalog.models import User, UserAvatar
from app.config import settings

router = APIRouter()

# Decompression-bomb guard: a few-MB file (esp. PNG of uniform data) can encode
# enormous dimensions that blow up RAM when decoded — the 5 MB input cap does
# NOT bound the decoded pixel array. Reject oversized images by dimensions
# *before* the full decode, with Pillow's own limit as a backstop.
MAX_AVATAR_PIXELS = 50_000_000  # ~50 MP (e.g. 7000×7000) — ample for a source photo
Image.MAX_IMAGE_PIXELS = MAX_AVATAR_PIXELS


def _process_image(raw: bytes) -> bytes:
    """Validate `raw` is a real image and re-encode it to a small JPEG square.

    Center-crops to a square, resizes to avatar_size_px, flattens any alpha onto
    white, and strips metadata (EXIF) by re-saving. Raises HTTPException(400) if
    the bytes aren't a decodable image or exceed the pixel cap."""
    try:
        img = Image.open(io.BytesIO(raw))  # lazy — reads the header/dimensions
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a valid image") from None
    # Reject by dimensions before img.load() allocates the full bitmap.
    if (img.width or 0) * (img.height or 0) > MAX_AVATAR_PIXELS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image dimensions too large")
    try:
        img.load()  # force decode now so a truncated/bomb image fails here
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a valid image") from None

    img = img.convert("RGB")  # drop alpha/palette; JPEG needs RGB
    side = min(img.size)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((settings.avatar_size_px, settings.avatar_size_px), Image.LANCZOS)

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=settings.avatar_jpeg_quality, optimize=True)
    return out.getvalue()


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Accept an image, resize it, and store it as the user's avatar."""
    # Read at most max_upload+1 bytes so an oversized (or lying Content-Length)
    # upload is rejected without pulling the whole thing into memory.
    raw = await file.read(settings.avatar_max_upload_bytes + 1)
    if len(raw) > settings.avatar_max_upload_bytes:
        mb = settings.avatar_max_upload_bytes // (1024 * 1024)
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"Image too large (max {mb} MB)"
        )
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty upload")

    data = _process_image(raw)

    session.execute(
        pg_insert(UserAvatar)
        .values(user_id=user.id, data=data, content_type="image/jpeg")
        .on_conflict_do_update(
            index_elements=[UserAvatar.user_id],
            set_={"data": data, "content_type": "image/jpeg", "updated_at": datetime.now(timezone.utc)},
        )
    )
    # Point avatar_url at the public serve route, cache-busted so the browser
    # picks up the new image immediately.
    version = int(datetime.now(timezone.utc).timestamp())
    db_user = session.get(User, user.id)
    db_user.avatar_url = f"/avatars/{user.id}?v={version}"
    session.commit()
    return {"avatar_url": db_user.avatar_url}


@router.delete("/me/avatar")
def delete_avatar(
    user: User = Depends(current_user), session: Session = Depends(get_session)
) -> dict:
    """Remove the user's uploaded avatar (falls back to the initial placeholder)."""
    session.query(UserAvatar).filter(UserAvatar.user_id == user.id).delete()
    db_user = session.get(User, user.id)
    db_user.avatar_url = None
    session.commit()
    return {"status": "removed"}


@router.get("/avatars/{user_id}")
def get_avatar(
    user_id: uuid.UUID, request: Request, session: Session = Depends(get_session)
) -> Response:
    """Serve a user's avatar bytes. Public + cacheable (avatars appear on public
    profiles and user cards). 304 on a matching ETag."""
    avatar = session.get(UserAvatar, user_id)
    if avatar is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No avatar")
    etag = f'"{hashlib.sha1(avatar.data).hexdigest()}"'  # noqa: S324 (cache tag, not security)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    return Response(
        content=avatar.data,
        media_type=avatar.content_type,
        headers={"Cache-Control": "public, max-age=86400", "ETag": etag},
    )
