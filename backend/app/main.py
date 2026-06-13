import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from app.api.routes import router
from app.catalog import models  # noqa: F401 — registers tables in metadata
from app.catalog.db import Base, engine


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
app.include_router(router)
