import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.routes import router
from app.api.saved import router as saved_router
from app.api.social import router as social_router
from app.catalog import models  # noqa: F401 — registers tables in metadata
from app.catalog.db import Base, engine
from app.config import settings
from app.observability import setup_observability

log = logging.getLogger(__name__)


def _ensure_extensions() -> None:
    """Enable the extensions search relies on — `vector` (semantic) and
    `pg_trgm` (lexical/hybrid) — before create_all builds their indexes.

    On managed Postgres the app role often lacks CREATE EXTENSION; there they
    are created out-of-band (`make do-db-init` / db/init.sql), so a permission
    failure here is downgraded to a warning rather than blocking startup."""
    for ext in ("vector", "pg_trgm"):
        try:
            with engine.begin() as conn:
                conn.execute(text(f"CREATE EXTENSION IF NOT EXISTS {ext}"))
        except OperationalError:
            raise  # DB not accepting connections yet — let the retry loop wait
        except SQLAlchemyError:
            log.warning(
                "could not ensure extension %r (assuming it is created "
                "out-of-band); continuing", ext, exc_info=True,
            )


def _ensure_indexes() -> None:
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
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def _create_schema(retries: int = 30, delay: float = 2.0) -> None:
    """Create tables on startup, waiting for Postgres to accept connections
    (it may still be booting in compose / k8s)."""
    for attempt in range(retries):
        try:
            _ensure_extensions()
            Base.metadata.create_all(engine)
            _ensure_indexes()
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

# Prometheus /metrics (always) + OpenTelemetry traces (when OTEL endpoint set).
setup_observability(app)
