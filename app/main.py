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


_ALTER_TZ_COLUMNS: list[str] = [
    "ALTER TABLE contacts ALTER COLUMN source_updated_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING source_updated_at AT TIME ZONE 'UTC'",
    "ALTER TABLE events ALTER COLUMN starts_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING starts_at AT TIME ZONE 'UTC'",
    "ALTER TABLE events ALTER COLUMN ends_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING ends_at AT TIME ZONE 'UTC'",
    "ALTER TABLE events ALTER COLUMN source_updated_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING source_updated_at AT TIME ZONE 'UTC'",
    "ALTER TABLE transactions ALTER COLUMN occurred_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING occurred_at AT TIME ZONE 'UTC'",
    "ALTER TABLE transactions ALTER COLUMN source_updated_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING source_updated_at AT TIME ZONE 'UTC'",
    "ALTER TABLE external_records ALTER COLUMN source_updated_at"
    " TYPE TIMESTAMP WITH TIME ZONE USING source_updated_at AT TIME ZONE 'UTC'",
    "ALTER TABLE source_connections ALTER COLUMN cursor_updated_at"
    " TYPE TIMESTAMP WITH TIME ZONE USING cursor_updated_at AT TIME ZONE 'UTC'",
    "ALTER TABLE source_connections ALTER COLUMN last_full_sync_at"
    " TYPE TIMESTAMP WITH TIME ZONE USING last_full_sync_at AT TIME ZONE 'UTC'",
    "ALTER TABLE source_connections ALTER COLUMN last_incremental_sync_at"
    " TYPE TIMESTAMP WITH TIME ZONE USING last_incremental_sync_at AT TIME ZONE 'UTC'",
    "ALTER TABLE sync_runs ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING started_at AT TIME ZONE 'UTC'",
    "ALTER TABLE sync_runs ALTER COLUMN completed_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING completed_at AT TIME ZONE 'UTC'",
    "ALTER TABLE sync_run_sources ALTER COLUMN started_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING started_at AT TIME ZONE 'UTC'",
    "ALTER TABLE sync_run_sources ALTER COLUMN completed_at TYPE TIMESTAMP WITH TIME ZONE"
    " USING completed_at AT TIME ZONE 'UTC'",
]


async def _run_migrations() -> None:
    """Run database migrations on startup."""
    try:
        from sqlalchemy import pool
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import async_engine_from_config

        from app.models import Base

        cfg = {
            "sqlalchemy.url": settings.database_url,
            "sqlalchemy.echo": "false",
        }
        engine = async_engine_from_config(
            cfg, prefix="sqlalchemy.", poolclass=pool.NullPool
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for stmt in _ALTER_TZ_COLUMNS:
                try:
                    await conn.execute(sa_text(stmt))
                except Exception:
                    logger.warning("Column already timestamptz or not applicable: %s", stmt[:60])
            result = await conn.execute(
                sa_text(
                    "SELECT 1 FROM collected_status_allowlist "
                    "WHERE canonical_status = 'collected'"
                )
            )
            if result.scalar_one_or_none() is None:
                await conn.execute(
                    sa_text(
                        "INSERT INTO collected_status_allowlist "
                        "(canonical_status, counts_as_collected) "
                        "VALUES ('collected', true)"
                    )
                )
        await engine.dispose()
        logger.info("Database tables created/verified on startup")
    except Exception as e:
        logger.warning("Database init failed: %s", e)


app = FastAPI(title="Data Sync Service", lifespan=lifespan)
app.include_router(health_router)
app.include_router(sync_router)
app.include_router(metrics_router)

if settings.enable_demo_routes:
    from app.api.demo import router as demo_router

    app.include_router(demo_router)
