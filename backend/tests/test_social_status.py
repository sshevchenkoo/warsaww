"""Friendship status resolution (`_status`) — the pure logic that maps a
friendship row + the requester to the relationship label shown in the UI — plus
the presence check (`_is_online`)."""

import uuid
from datetime import datetime, timedelta, timezone

from app.api.social import ONLINE_WINDOW, _is_online, _status


class _Row:
    def __init__(self, requester_id, addressee_id, status):
        self.requester_id = requester_id
        self.addressee_id = addressee_id
        self.status = status


class _Seen:
    """Minimal stand-in for a User carrying just the presence timestamp."""

    def __init__(self, last_seen_at):
        self.last_seen_at = last_seen_at


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


def test_online_never_seen_is_offline():
    assert _is_online(_Seen(None)) is False


def test_online_recent_ping_is_online():
    just_now = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert _is_online(_Seen(just_now)) is True


def test_online_stale_ping_is_offline():
    stale = datetime.now(timezone.utc) - ONLINE_WINDOW - timedelta(seconds=5)
    assert _is_online(_Seen(stale)) is False


def test_online_naive_timestamp_treated_as_utc():
    # The DB hands back a naive UTC timestamp; a fresh one must still read online.
    naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
    assert _is_online(_Seen(naive_now)) is True
