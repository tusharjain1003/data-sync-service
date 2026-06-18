from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Data Sync Service", lifespan=lifespan)
app.include_router(health_router)
