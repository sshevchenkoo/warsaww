"""Malformed bodies on the auth and profile form paths come back as a 422 with
a form-friendly line, not pydantic's wording. No DB is touched: validation fails
before the handler runs."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_login_email_without_dot_gets_form_message():
    res = client.post("/auth/login", json={"email": "user@test", "password": "12"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Enter a valid email address, like name@example.com."}


def test_register_short_password_gets_form_message():
    res = client.post("/auth/register", json={"email": "a@example.com", "password": "123"})
    assert res.status_code == 422
    assert res.json() == {"detail": "Password must be 8-72 characters."}


def test_other_paths_keep_pydantic_body():
    res = client.post("/search", json={"query": 123, "limit": "x"})
    assert res.status_code == 422
    assert isinstance(res.json()["detail"], list)
