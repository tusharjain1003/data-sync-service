from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.sync import router as sync_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(title="Data Sync Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(sync_router)
app.include_router(metrics_router)

if settings.enable_demo_routes:
    from app.api.demo import router as demo_router

    app.include_router(demo_router)
