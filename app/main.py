from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import health_router
from app.api.sync import router as sync_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Data Sync Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(sync_router)

if settings.enable_demo_routes:
    from app.api.demo import router as demo_router

    app.include_router(demo_router)
