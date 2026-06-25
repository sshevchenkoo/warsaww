import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.routes import router
from app.api.saved import router as saved_router
from app.catalog import models  # noqa: F401 — registers tables in metadata
from app.catalog.db import Base, engine
from app.config import settings
from app.observability import setup_observability


def _create_schema(retries: int = 30, delay: float = 2.0) -> None:
    """Create tables on startup, waiting for Postgres to accept connections
    (it may still be booting in compose / k8s)."""
    for attempt in range(retries):
        try:
            Base.metadata.create_all(engine)
            return
        except OperationalError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
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

# Prometheus /metrics (always) + OpenTelemetry traces (when OTEL endpoint set).
setup_observability(app)
