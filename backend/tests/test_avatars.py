"""Unit tests for avatar processing — the decompression-bomb guard and image
validation — and for DELETE /me/avatar. No DB needed: _process_image is pure and
delete_avatar runs against a fake session."""

import io
import uuid

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api import avatars


def _png(size: tuple[int, int], color: str = "red") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_valid_image_becomes_jpeg_square():
    out = avatars._process_image(_png((40, 24)))  # non-square input
    assert out[:2] == b"\xff\xd8"  # JPEG magic
    result = Image.open(io.BytesIO(out))
    assert result.width == result.height == avatars.settings.avatar_size_px


def test_oversized_dimensions_rejected(monkeypatch):
    # Cap tiny so a small test image trips the guard without allocating memory.
    monkeypatch.setattr(avatars, "MAX_AVATAR_PIXELS", 100)  # 10x10
    with pytest.raises(HTTPException) as exc:
        avatars._process_image(_png((50, 50)))  # 2500 px > 100
    assert exc.value.status_code == 400


def test_non_image_bytes_rejected():
    with pytest.raises(HTTPException) as exc:
        avatars._process_image(b"definitely not an image")
    assert exc.value.status_code == 400


def test_module_caps_pillow_pixel_limit():
    # The module sets Pillow's global backstop so a bomb outside our own check
    # still can't decode unbounded.
    assert Image.MAX_IMAGE_PIXELS == avatars.MAX_AVATAR_PIXELS


class _User:
    def __init__(self, avatar_url):
        self.id = uuid.uuid4()
        self.avatar_url = avatar_url


class _Session:
    """Fakes the bits delete_avatar uses: query(UserAvatar).filter().delete(),
    get(User, id) and commit. `avatars` is the set of user ids with a stored row."""

    def __init__(self, user, avatars=()):
        self.user = user
        self.avatars = set(avatars)
        self.commits = 0

    def query(self, _model):
        return self

    def filter(self, _cond):
        return self

    def delete(self):
        removed = int(self.user.id in self.avatars)
        self.avatars.discard(self.user.id)
        return removed

    def get(self, _model, user_id):
        return self.user if user_id == self.user.id else None

    def commit(self):
        self.commits += 1


def test_delete_removes_uploaded_avatar_and_clears_url():
    user = _User(avatar_url="/avatars/x?v=1")
    session = _Session(user, avatars={user.id})
    assert avatars.delete_avatar(user=user, session=session) == {"status": "removed"}
    assert user.id not in session.avatars  # stored bytes are gone, not just unlinked
    assert user.avatar_url is None  # the UI falls back to the initial placeholder
    assert session.commits == 1


def test_delete_clears_google_photo_url_without_stored_row():
    # A Google account's avatar_url points at Google, with no row of ours. Delete
    # still clears it (the photo comes back on the next Google login, by design).
    user = _User(avatar_url="https://lh3.googleusercontent.com/a/photo")
    session = _Session(user)
    avatars.delete_avatar(user=user, session=session)
    assert user.avatar_url is None
    assert session.commits == 1


def test_delete_without_avatar_is_a_noop_success():
    user = _User(avatar_url=None)
    session = _Session(user)
    assert avatars.delete_avatar(user=user, session=session) == {"status": "removed"}
    assert user.avatar_url is None
