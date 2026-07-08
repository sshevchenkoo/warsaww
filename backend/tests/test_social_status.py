"""Friendship status resolution (`_status`) — the pure logic that maps a
friendship row + the requester to the relationship label shown in the UI."""

import uuid

from app.api.social import _status


class _Row:
    def __init__(self, requester_id, addressee_id, status):
        self.requester_id = requester_id
        self.addressee_id = addressee_id
        self.status = status


def test_no_row_is_none():
    me = uuid.uuid4()
    assert _status(None, me) == "none"


def test_accepted_is_friends_either_direction():
    me, other = uuid.uuid4(), uuid.uuid4()
    assert _status(_Row(me, other, "accepted"), me) == "friends"
    assert _status(_Row(other, me, "accepted"), me) == "friends"


def test_pending_i_sent():
    me, other = uuid.uuid4(), uuid.uuid4()
    assert _status(_Row(me, other, "pending"), me) == "request_sent"


def test_pending_i_received():
    me, other = uuid.uuid4(), uuid.uuid4()
    assert _status(_Row(other, me, "pending"), me) == "request_received"
