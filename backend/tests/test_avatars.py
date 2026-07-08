"""Unit tests for avatar processing — the decompression-bomb guard and image
validation. No DB needed (only _process_image is exercised)."""

import io

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
