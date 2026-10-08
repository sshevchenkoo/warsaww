import json
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import EmailStr

from app.api.auth import DeleteMeRequest, delete_me, export_me
from app.auth.passwords import hash_password
from app.catalog.models import Friendship, SavedItem, SharedEvent, User


class FakeSession:
    def __init__(self):
        self.deleted_objects = []
        self.committed = False

    def delete(self, obj):
        self.deleted_objects.append(obj)

    def commit(self):
        self.committed = True

    def query(self, *args, **kwargs):
        # mock a chain: query().filter().all() returning empty
        class Chain:
            def filter(self, *args, **kwargs):
                return self
            def all(self):
                return []
        return Chain()


class FakeRequest:
    class _SessionDict(dict):
        def __init__(self, d):
            super().__init__(d)
            self.cleared = False
        def clear(self):
            self.cleared = True
            super().clear()

    @property
    def session(self) -> _SessionDict:
        if not hasattr(self, "_sess"):
            self._sess = self._SessionDict({"user_id": "fake"})
        return self._sess


def test_export_me():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Test User",
        avatar_url=None,
        email_verified=True,
        pending_email=None,
    )
    sess = FakeSession()

    resp = export_me(user=user, session=sess)
    assert resp.status_code == 200
    data = json.loads(resp.body)
    assert data["email"] == "test@example.com"
    assert "saved_items" in data
    assert "friendships" in data
    assert "shared_events" in data


def test_delete_me_password_required():
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("mypassword"),
    )
    request = FakeRequest()
    sess = FakeSession()

    with pytest.raises(HTTPException) as exc:
        delete_me(request=request, req=DeleteMeRequest(current_password=None), user=user, session=sess)
    assert exc.value.status_code == 400

    with pytest.raises(HTTPException) as exc:
        delete_me(request=request, req=DeleteMeRequest(current_password="wrong"), user=user, session=sess)
    assert exc.value.status_code == 401


def test_delete_me_success(monkeypatch):
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        password_hash=hash_password("mypassword"),
    )
    request = FakeRequest()
    sess = FakeSession()

    emails_sent = []
    monkeypatch.setattr("app.api.auth.send_email", lambda to, subj, html: emails_sent.append(to))

    res = delete_me(
        request=request,
        req=DeleteMeRequest(current_password="mypassword"),
        user=user,
        session=sess,
    )
    
    assert res["status"] == "deleted"
    assert user in sess.deleted_objects
    assert sess.committed
    assert request.session.cleared
    assert "test@example.com" in emails_sent
