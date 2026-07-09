import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.avatars import router as avatars_router
from app.api.routes import router
from app.api.saved import router as saved_router
from app.api.social import router as social_router
from app.catalog import models  # noqa: F401 — registers tables in metadata
from app.catalog.db import Base, engine
from app.config import settings
from app.observability import setup_observability

log = logging.getLogger(__name__)


def _ensure_extensions(eng=engine) -> None:
    """Enable the extensions search relies on — `vector` (semantic) and
    `pg_trgm` (lexical/hybrid) — before create_all builds their indexes.

    On managed Postgres the app role often lacks CREATE EXTENSION; there they
    are created out-of-band (`make do-db-init` / db/init.sql), so a permission
    failure here is downgraded to a warning rather than blocking startup.

    `eng` defaults to the app engine; tests pass a throwaway one so they build
    the exact same schema + RLS the app does."""
    for ext in ("vector", "pg_trgm"):
        try:
            with eng.begin() as conn:
                conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
        except OperationalError:
            raise  # DB not accepting connections yet — let the retry loop wait
        except SQLAlchemyError:
            log.warning(
                "could not ensure extension %r (assuming it is created "
                "out-of-band); continuing", ext, exc_info=True,
            )


def _ensure_indexes(eng=engine) -> None:
    """create_all does not add new indexes to already-existing tables, so the
    indexes added after those tables first shipped are ensured explicitly
    (idempotent). Covers hybrid-search trigram indexes (audit #7) and the FK
    indexes Postgres doesn't create automatically (audit #6)."""
    stmts = (
        # Trigram (pg_trgm) indexes for lexical / ILIKE search.
        "CREATE INDEX IF NOT EXISTS ix_items_name_trgm ON items USING gin (name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_users_name_trgm ON users USING gin (name gin_trgm_ops)",
        # Foreign-key indexes (speed ON DELETE CASCADE from items + item_id lookups).
        "CREATE INDEX IF NOT EXISTS ix_saved_items_item_id ON saved_items (item_id)",
        "CREATE INDEX IF NOT EXISTS ix_shared_events_item_id ON shared_events (item_id)",
    )
    with eng.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _ensure_constraints(eng=engine) -> None:
    """create_all won't add a constraint to an already-existing table, so the
    CHECK constraints (audit #9) are added idempotently. Existing prod data
    already conforms (items.kind in event/place; friendships empty)."""
    checks = (
        ("ck_items_kind", "items", "kind IN ('event', 'place')"),
        ("ck_friendship_status", "friendships", "status IN ('pending', 'accepted')"),
    )
    with eng.begin() as conn:
        for name, table, expr in checks:
            conn.execute(
                text(
                    f"DO $$ BEGIN "
                    f"IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname = '{name}') THEN "
                    f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expr}); "
                    f"END IF; END $$;"
                )
            )


def _ensure_columns(eng=engine) -> None:
    """create_all won't add a new column to an already-existing table, so columns
    introduced after a table first shipped are added idempotently. `email_verified`
    backfills to true for Google accounts (Google already proved the address);
    password accounts stay unverified until they confirm."""
    with eng.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified "
                "boolean NOT NULL DEFAULT false"
            )
        )
        conn.execute(
            text(
                "UPDATE users SET email_verified = true "
                "WHERE google_sub IS NOT NULL AND email_verified = false"
            )
        )
        # Code-based email verification (added after email_verified shipped).
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "email_verify_code_hash text"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "email_verify_code_expires_at timestamptz"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
                "email_verify_attempts integer NOT NULL DEFAULT 0"
            )
        )


def _ensure_rls(eng=engine) -> None:
    """Row-Level Security (audit #5): a DB-enforced backstop under the app-layer
    authz, scoping every user-owned row to the requester via `app.user_id` (set
    per request in auth.deps.current_user).

    Idempotent (drop+recreate policies). RLS only bites a non-owner role, so it
    enforces against the runtime role `warsaw_app` while the owner (doadmin,
    which runs this migrate) and any superuser bypass it — admin/migrate work is
    unaffected. NOT forced, so local dev (which connects as the table owner)
    also bypasses it. `users`/`items`/`intent_logs` are public/non-tenant and
    keep no RLS. The current_setting is wrapped in a (select ...) so the planner
    evaluates it once per statement (security-rls-performance)."""
    me = "(select nullif(current_setting('app.user_id', true), ''))::uuid"
    stmts = [
        # friendships: only the two parties can see or change the row.
        "ALTER TABLE friendships ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS p_friendships ON friendships",
        f"CREATE POLICY p_friendships ON friendships "
        f"USING (requester_id = {me} OR addressee_id = {me}) "
        f"WITH CHECK (requester_id = {me} OR addressee_id = {me})",
        # shared_events: sender + recipient read; only the sender inserts; only
        # the recipient deletes (dismiss from inbox).
        "ALTER TABLE shared_events ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS p_shared_select ON shared_events",
        f"CREATE POLICY p_shared_select ON shared_events FOR SELECT "
        f"USING (to_user_id = {me} OR from_user_id = {me})",
        "DROP POLICY IF EXISTS p_shared_insert ON shared_events",
        f"CREATE POLICY p_shared_insert ON shared_events FOR INSERT "
        f"WITH CHECK (from_user_id = {me})",
        "DROP POLICY IF EXISTS p_shared_delete ON shared_events",
        f"CREATE POLICY p_shared_delete ON shared_events FOR DELETE "
        f"USING (to_user_id = {me})",
        # saved_items: write only your own; read your own OR an accepted friend's
        # (the friend check reads friendships, itself RLS-scoped to my rows).
        "ALTER TABLE saved_items ENABLE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS p_saved_select ON saved_items",
        f"CREATE POLICY p_saved_select ON saved_items FOR SELECT USING ("
        f"user_id = {me} OR EXISTS (SELECT 1 FROM friendships f "
        f"WHERE f.status = 'accepted' AND ("
        f"(f.requester_id = {me} AND f.addressee_id = saved_items.user_id) OR "
        f"(f.addressee_id = {me} AND f.requester_id = saved_items.user_id))))",
        "DROP POLICY IF EXISTS p_saved_insert ON saved_items",
        f"CREATE POLICY p_saved_insert ON saved_items FOR INSERT WITH CHECK (user_id = {me})",
        "DROP POLICY IF EXISTS p_saved_delete ON saved_items",
        f"CREATE POLICY p_saved_delete ON saved_items FOR DELETE USING (user_id = {me})",
    ]
    with eng.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _create_schema(retries: int = 30, delay: float = 2.0, eng=engine) -> None:
    """Create tables on startup, waiting for Postgres to accept connections
    (it may still be booting in compose / k8s)."""
    for attempt in range(retries):
        try:
            _ensure_extensions(eng)
            Base.metadata.create_all(eng)
            _ensure_columns(eng)
            _ensure_indexes(eng)
            _ensure_constraints(eng)
            _ensure_rls(eng)
            return
        except OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only bootstrap the schema when allowed (audit #4): in prod the runtime role
    # is least-privilege DML-only and can't run DDL — schema is managed by the
    # admin-run `make do-db-migrate` step. Local dev keeps db_bootstrap=True.
    if settings.db_bootstrap:
        _create_schema()
    yield


app = FastAPI(title="Warsaw Events API", lifespan=lifespan)

# Signed-cookie sessions (no server-side state → the API stays stateless across
# replicas). Holds only the logged-in user id; signed with session_secret.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.session_https_only,
)

# The frontend (a separate origin) calls /search from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(saved_router)
app.include_router(social_router)
app.include_router(avatars_router)

# Prometheus /metrics (always) + OpenTelemetry traces (when OTEL endpoint set).
setup_observability(app)
