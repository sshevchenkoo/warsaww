from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.catalog import models  # noqa: F401 — registers tables in metadata
from app.catalog.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Warsaw Events API", lifespan=lifespan)
app.include_router(router)
