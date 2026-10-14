"""Attachments (/me/files): type sniffing and filename cleanup as pure unit tests,
then the endpoints end to end against a real Postgres — ownership, limits,
headers, cascades — and the user_files RLS policy as the runtime role.

The DB tests are skipped unless TEST_DATABASE_URL is set (see conftest)."""

import io
import os
import uuid

import pytest
from fastapi import Depends, HTTPException, Request
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import files
from app.auth.deps import current_user
from app.catalog.db import get_session
from app.catalog.models import User
from app.main import app

requires_db = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"
)

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _image(fmt: str, size=(8, 8)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, "red").save(buf, fmt)
    return buf.getvalue()


# ─── _sniff ───────────────────────────────────────────────────────────────────
def test_pdf_is_detected_by_magic_bytes():
    assert files._sniff(PDF) == "application/pdf"


@pytest.mark.parametrize(
    ("fmt", "mime"),
    [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("GIF", "image/gif")],
)
def test_allowed_images_are_detected(fmt, mime):
    assert files._sniff(_image(fmt)) == mime


def test_text_is_refused_with_415():
    with pytest.raises(HTTPException) as exc:
        files._sniff(b"just some text, saved as ticket.pdf")
    assert exc.value.status_code == 415


def test_image_format_outside_the_list_is_refused():
    with pytest.raises(HTTPException) as exc:
        files._sniff(_image("BMP"))
    assert exc.value.status_code == 415


def test_oversized_dimensions_rejected(monkeypatch):
    monkeypatch.setattr(files, "MAX_FILE_PIXELS", 100)  # 10x10
    with pytest.raises(HTTPException) as exc:
        files._sniff(_image("PNG", (50, 50)))
    assert exc.value.status_code == 400


# ─── _clean_filename ──────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("ticket.pdf", "ticket.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\bilet.pdf", "bilet.pdf"),
        ("evil\r\nX-Header: 1.pdf", "evilX-Header: 1.pdf"),
        ("", "file"),
        (None, "file"),
        ("dir/", "file"),
    ],
)
def test_clean_filename(raw, clean):
    assert files._clean_filename(raw) == clean


def test_clean_filename_is_capped():
    assert len(files._clean_filename("a" * 500 + ".pdf")) == files.MAX_FILENAME


def test_endpoints_require_a_session():
    client = TestClient(app)
    assert client.get("/me/files").status_code == 401


# ─── endpoints against a real DB ──────────────────────────────────────────────
@pytest.fixture
def api(clean_db):
    """A TestClient on the test DB. The caller picks the user per request with an
    `x-test-user` header, standing in for the signed session cookie."""

    def _session():
        with Session(clean_db) as s:
            yield s

    def _user(request: Request, session: Session = Depends(get_session)) -> User:
        user = session.get(User, uuid.UUID(request.headers["x-test-user"]))
        if user is None:
            raise HTTPException(401, "Not authenticated")
        return user

    app.dependency_overrides[get_session] = _session
    app.dependency_overrides[current_user] = _user
    yield TestClient(app), clean_db
    app.dependency_overrides.clear()


def _seed_user(conn, name="A"):
    uid = uuid.uuid4()
    conn.execute(text("INSERT INTO users (id, name) VALUES (:id, :n)"), {"id": uid, "n": name})
    return uid


def _seed_item(conn, name="Concert"):
    iid = uuid.uuid4()
    conn.execute(
        text("INSERT INTO items (id, kind, name, source) VALUES (:id, 'event', :n, 'test')"),
        {"id": iid, "n": name},
    )
    return iid


def _upload(client, user, item, body=PDF, name="ticket.pdf"):
    return client.post(
        "/me/files",
        headers={"x-test-user": str(user)},
        data={"item_id": str(item)},
        files={"file": (name, body, "application/octet-stream")},
    )


@requires_db
def test_upload_list_serve_delete(api):
    client, eng = api
    with eng.begin() as c:
        a, item = _seed_user(c), _seed_item(c, "Opera night")

    res = _upload(client, a, item)
    assert res.status_code == 201
    out = res.json()
    # The type comes from the bytes, not the octet-stream the client claimed.
    assert out["content_type"] == "application/pdf"
    assert out["item_name"] == "Opera night"
    assert out["size"] == len(PDF)

    listed = client.get("/me/files", headers={"x-test-user": str(a)}).json()
    assert [f["id"] for f in listed] == [out["id"]]

    got = client.get(f"/me/files/{out['id']}", headers={"x-test-user": str(a)})
    assert got.status_code == 200
    assert got.content == PDF
    assert got.headers["content-type"] == "application/pdf"
    assert got.headers["x-content-type-options"] == "nosniff"
    assert got.headers["content-disposition"] == "inline; filename*=UTF-8''ticket.pdf"
    dl = client.get(f"/me/files/{out['id']}?download=1", headers={"x-test-user": str(a)})
    assert dl.headers["content-disposition"].startswith("attachment;")

    assert client.delete(f"/me/files/{out['id']}", headers={"x-test-user": str(a)}).status_code == 200
    assert client.get("/me/files", headers={"x-test-user": str(a)}).json() == []


@requires_db
def test_other_users_file_is_a_404(api):
    client, eng = api
    with eng.begin() as c:
        a, b, item = _seed_user(c, "A"), _seed_user(c, "B"), _seed_item(c)
    fid = _upload(client, a, item).json()["id"]

    as_b = {"x-test-user": str(b)}
    assert client.get(f"/me/files/{fid}", headers=as_b).status_code == 404
    assert client.delete(f"/me/files/{fid}", headers=as_b).status_code == 404
    assert client.get("/me/files", headers=as_b).json() == []
    # Still there for its owner.
    assert client.get(f"/me/files/{fid}", headers={"x-test-user": str(a)}).status_code == 200


@requires_db
def test_unknown_item_is_a_404(api):
    client, eng = api
    with eng.begin() as c:
        a = _seed_user(c)
    assert _upload(client, a, uuid.uuid4()).status_code == 404


@requires_db
def test_bad_type_and_size_are_refused(api, monkeypatch):
    client, eng = api
    with eng.begin() as c:
        a, item = _seed_user(c), _seed_item(c)
    assert _upload(client, a, item, body=b"not a pdf", name="fake.pdf").status_code == 415
    assert _upload(client, a, item, body=b"", name="empty.pdf").status_code == 400
    monkeypatch.setattr(files.settings, "files_max_upload_bytes", 10)
    assert _upload(client, a, item).status_code == 413


@requires_db
def test_per_user_file_limit(api, monkeypatch):
    client, eng = api
    monkeypatch.setattr(files.settings, "files_max_per_user", 2)
    with eng.begin() as c:
        a, b, item = _seed_user(c, "A"), _seed_user(c, "B"), _seed_item(c)
    assert _upload(client, a, item).status_code == 201
    assert _upload(client, a, item).status_code == 201
    assert _upload(client, a, item).status_code == 409
    # The limit is per user.
    assert _upload(client, b, item).status_code == 201


@requires_db
def test_files_go_with_the_account_and_the_item(api):
    client, eng = api
    with eng.begin() as c:
        a, b = _seed_user(c, "A"), _seed_user(c, "B")
        item_a, item_b = _seed_item(c, "one"), _seed_item(c, "two")
    _upload(client, a, item_a)
    _upload(client, b, item_b)

    with eng.begin() as c:
        c.execute(text("DELETE FROM users WHERE id = :id"), {"id": a})
        c.execute(text("DELETE FROM items WHERE id = :id"), {"id": item_b})
        assert c.execute(text("SELECT count(*) FROM user_files")).scalar() == 0


# ─── RLS ──────────────────────────────────────────────────────────────────────
@requires_db
def test_rls_scopes_user_files_to_owner(clean_db):
    eng = clean_db
    with eng.begin() as c:
        a, b, item = _seed_user(c, "A"), _seed_user(c, "B"), _seed_item(c)
        for owner in (a, b):
            c.execute(
                text(
                    "INSERT INTO user_files (user_id, item_id, filename, content_type, size, data) "
                    "VALUES (:u, :i, 'f.pdf', 'application/pdf', 4, '\\x25504446')"
                ),
                {"u": owner, "i": item},
            )

    with eng.connect() as conn, conn.begin():
        conn.execute(text("SET LOCAL ROLE warsaw_app"))
        conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(a)})
        owners = {r[0] for r in conn.execute(text("SELECT user_id FROM user_files"))}
        assert owners == {a}
        # Writing a row that claims to be B's is refused by WITH CHECK.
        with pytest.raises(Exception, match="row-level security"):
            conn.execute(
                text(
                    "INSERT INTO user_files (user_id, item_id, filename, content_type, size, data) "
                    "VALUES (:u, :i, 'x.pdf', 'application/pdf', 4, '\\x25504446')"
                ),
                {"u": b, "i": item},
            )
