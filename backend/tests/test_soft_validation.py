"""Malformed bodies on the soft-fail auth paths come back as 200 {error} with
a form-friendly line, not a 422 with pydantic's wording. No DB is touched:
validation fails before the handler runs."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_email_without_dot_is_soft():
    res = client.post("/auth/login", json={"email": "user@test", "password": "12"})
    assert res.status_code == 200
    assert res.json() == {"error": "Enter a valid email address, like name@example.com."}


def test_register_short_password_is_soft():
    res = client.post("/auth/register", json={"email": "a@example.com", "password": "123"})
    assert res.status_code == 200
    assert res.json() == {"error": "Password must be 8-72 characters."}


def test_other_paths_keep_422():
    res = client.post("/search", json={"query": 123, "limit": "x"})
    assert res.status_code == 422
