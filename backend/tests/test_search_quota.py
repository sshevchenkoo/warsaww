import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes import SearchRequest, search
from app.config import settings


def _run_search_over_quota(session: dict) -> MagicMock:
    """Call search() with the quota exhausted, so it stops with 429 right after
    the quota check — before any LLM/embedding/DB work. Returns the quota mock."""
    request = MagicMock()
    request.session = session
    with (
        patch.object(settings, "require_verified_email_to_search", False),
        patch("app.api.routes.check_search_quota", return_value=(False, 0)) as check,
        pytest.raises(HTTPException) as exc,
    ):
        search(SearchRequest(prompt="test"), request)
    assert exc.value.status_code == 429
    return check


def test_search_quota_uses_user_id_when_logged_in():
    user_id = str(uuid.uuid4())
    check = _run_search_over_quota({"user_id": user_id, "sid": "some-sid"})
    check.assert_called_once_with(user_id)


def test_search_quota_uses_sid_when_logged_out():
    check = _run_search_over_quota({"sid": "some-sid"})
    check.assert_called_once_with("some-sid")


def test_search_quota_issues_sid_for_new_anonymous_visitor():
    session: dict = {}
    check = _run_search_over_quota(session)
    assert session["sid"]
    check.assert_called_once_with(session["sid"])
