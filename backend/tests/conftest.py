"""Shared fixtures for the DB-integration tests (RLS + search).

These need a real Postgres with pgvector + pg_trgm. They are SKIPPED unless
TEST_DATABASE_URL is set, so the pure-logic unit tests still run anywhere (and
local `pytest` stays green without a database). CI sets TEST_DATABASE_URL to a
throwaway `pgvector/pgvector` service container on the runner.
"""

import os

import pytest
from sqlalchemy import create_engine, text

TEST_DB = os.environ.get("TEST_DATABASE_URL")

# Decorate DB-dependent tests with @requires_db.
requires_db = pytest.mark.skipif(
    not TEST_DB, reason="TEST_DATABASE_URL not set — no test Postgres"
)


@pytest.fixture(scope="session")
def db_engine():
    """A session-wide engine against the test DB, with the real app schema + RLS
    built on it, plus a non-owner `warsaw_app` DML role.

    RLS is not FORCEd, so the table owner bypasses it — to actually exercise the
    policies a test must `SET ROLE warsaw_app` (mirrors the prod runtime role)."""
    if not TEST_DB:
        pytest.skip("no test DB")
    from app.main import _create_schema  # imported lazily so unit tests need no DB

    eng = create_engine(TEST_DB, future=True)
    _create_schema(retries=15, delay=1.0, eng=eng)  # extensions + create_all + RLS
    with eng.begin() as c:
        c.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='warsaw_app') "
                "THEN CREATE ROLE warsaw_app; END IF; END $$;"
            )
        )
        c.execute(
            text(
                "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                "TO warsaw_app"
            )
        )
        c.execute(text("GRANT USAGE ON SCHEMA public TO warsaw_app"))
    yield eng
    eng.dispose()


@pytest.fixture
def clean_db(db_engine):
    """Truncate the app tables before each test so cases don't bleed into each
    other. Run as the owner (bypasses RLS)."""
    with db_engine.begin() as c:
        c.execute(
            text(
                "TRUNCATE saved_items, shared_events, friendships, items, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    return db_engine
