"""ShareRequest validation — the share message is length-capped at the API edge."""

import uuid

import pytest
from pydantic import ValidationError

from app.api.social import MAX_SHARE_MESSAGE, ShareRequest


def _req(message):
    return ShareRequest(to_user_id=uuid.uuid4(), item_id=uuid.uuid4(), message=message)


def test_message_is_optional():
    assert _req(None).message is None


def test_message_at_limit_is_accepted():
    assert len(_req("x" * MAX_SHARE_MESSAGE).message) == MAX_SHARE_MESSAGE


def test_message_over_limit_is_rejected():
    with pytest.raises(ValidationError):
        _req("x" * (MAX_SHARE_MESSAGE + 1))
