from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.sync import router as sync_router
from app.core.config import settings

logger = getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _run_migrations()
    yield


async def _run_migrations() -> None:
    """Run Alembic migrations on startup so no manual alembic upgrade head is needed."""
    try:
        import asyncio

        import alembic.command
        import alembic.config

        cfg = alembic.config.Config("alembic.ini")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, lambda: alembic.command.upgrade(cfg, "head")
        )
        logger.info("Database migrations applied on startup")
    except Exception as e:
        logger.warning("Could not run startup migrations: %s", e)


app = FastAPI(title="Data Sync Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(sync_router)
app.include_router(metrics_router)

if settings.enable_demo_routes:
    from app.api.demo import router as demo_router

    app.include_router(demo_router)
