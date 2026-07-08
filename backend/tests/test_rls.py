"""Row-Level Security integration tests (audit #5). Seed as the table owner
(bypasses RLS), then read/write as the non-owner `warsaw_app` role with
`app.user_id` set — exactly how the app runs in prod — and assert the policies
scope every user-owned row to the requester.

Skipped unless TEST_DATABASE_URL points at a Postgres with pgvector + pg_trgm
(CI provides one; local `pytest` skips these)."""

import os
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)


# ─── seed helpers (run as owner) ──────────────────────────────────────────────
def _user(conn, name):
    uid = uuid.uuid4()
    conn.execute(text("INSERT INTO users (id, name) VALUES (:id, :n)"), {"id": uid, "n": name})
    return uid


def _item(conn, name="Some event"):
    iid = uuid.uuid4()
    conn.execute(
        text("INSERT INTO items (id, kind, name, source) VALUES (:id, 'event', :n, 'test')"),
        {"id": iid, "n": name},
    )
    return iid


def _save(conn, user_id, item_id):
    conn.execute(
        text("INSERT INTO saved_items (user_id, item_id) VALUES (:u, :i)"),
        {"u": user_id, "i": item_id},
    )


def _friend(conn, a, b, status="accepted"):
    conn.execute(
        text(
            "INSERT INTO friendships (requester_id, addressee_id, status) "
            "VALUES (:a, :b, :s)"
        ),
        {"a": a, "b": b, "s": status},
    )


# ─── query as the runtime role, scoped by RLS ─────────────────────────────────
def _as_user(engine, user_id, sql, params=None):
    """Run `sql` as warsaw_app with app.user_id = user_id (RLS applies)."""
    with engine.connect() as conn, conn.begin():
        conn.execute(text("SET LOCAL ROLE warsaw_app"))
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
        return conn.execute(text(sql), params or {}).fetchall()


# ─── tests ────────────────────────────────────────────────────────────────────
def test_saved_items_scoped_to_owner(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b = _user(c, "A"), _user(c, "B")
        i1, i2 = _item(c, "one"), _item(c, "two")
        _save(c, a, i1)
        _save(c, b, i2)

    a_seen = {r[0] for r in _as_user(eng, a, "SELECT item_id FROM saved_items")}
    b_seen = {r[0] for r in _as_user(eng, b, "SELECT item_id FROM saved_items")}
    assert a_seen == {i1}
    assert b_seen == {i2}


def test_saved_items_visible_to_accepted_friend_not_stranger(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b, stranger = _user(c, "A"), _user(c, "B"), _user(c, "C")
        ib, istr = _item(c, "b-save"), _item(c, "stranger-save")
        _save(c, b, ib)
        _save(c, stranger, istr)
        _friend(c, a, b, "accepted")  # A and B are friends; C is not

    seen = {r[0] for r in _as_user(eng, a, "SELECT item_id FROM saved_items")}
    assert ib in seen          # friend B's save is visible to A
    assert istr not in seen    # a stranger's save is not


def test_pending_friend_saved_items_not_visible(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b = _user(c, "A"), _user(c, "B")
        ib = _item(c, "b-save")
        _save(c, b, ib)
        _friend(c, a, b, "pending")  # only a pending request, not accepted

    seen = {r[0] for r in _as_user(eng, a, "SELECT item_id FROM saved_items")}
    assert ib not in seen


def test_friendship_row_visible_only_to_parties(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b, c_user = _user(c, "A"), _user(c, "B"), _user(c, "C")
        _friend(c, a, b, "accepted")

    assert len(_as_user(eng, a, "SELECT 1 FROM friendships")) == 1
    assert len(_as_user(eng, b, "SELECT 1 FROM friendships")) == 1
    assert len(_as_user(eng, c_user, "SELECT 1 FROM friendships")) == 0  # unrelated


def test_shared_events_readable_by_sender_and_recipient_only(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b, stranger = _user(c, "A"), _user(c, "B"), _user(c, "C")
        item = _item(c, "shared")
        c.execute(
            text(
                "INSERT INTO shared_events (from_user_id, to_user_id, item_id) "
                "VALUES (:f, :t, :i)"
            ),
            {"f": a, "t": b, "i": item},
        )

    assert len(_as_user(eng, a, "SELECT 1 FROM shared_events")) == 1  # sender
    assert len(_as_user(eng, b, "SELECT 1 FROM shared_events")) == 1  # recipient
    assert len(_as_user(eng, stranger, "SELECT 1 FROM shared_events")) == 0


def test_saved_insert_check_rejects_other_users_id(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b = _user(c, "A"), _user(c, "B")
        item = _item(c, "x")

    # As A, try to insert a saved_item owned by B — the INSERT WITH CHECK policy
    # (user_id = app.user_id) must reject it.
    with pytest.raises(Exception):  # noqa: B017 — psycopg raises a driver error
        with eng.connect() as conn, conn.begin():
            conn.execute(text("SET LOCAL ROLE warsaw_app"))
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(a)})
            conn.execute(
                text("INSERT INTO saved_items (user_id, item_id) VALUES (:u, :i)"),
                {"u": b, "i": item},  # B's id, not A's → violates WITH CHECK
            )
