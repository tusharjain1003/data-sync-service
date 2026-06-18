from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import Insert as PgInsert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.main import app
from app.models import Base

# ── SQLite compatibility for PostgreSQL-specific types ──────────────────────


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(  # type: ignore[no-untyped-def]
    element: JSONB, compiler, **kw
) -> str:
    return "TEXT"


@compiles(PgInsert, "sqlite")
def _compile_pg_insert_sqlite(  # type: ignore[no-untyped-def]
    insert_stmt: Any, compiler, **kw
) -> str:
    """Compile a PostgreSQL insert (with ON CONFLICT) for SQLite."""
    return compiler.visit_insert(insert_stmt, **kw)  # type: ignore[no-any-return]


# ── Sync fixtures (health endpoint) ────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── Sync SQLite fixtures ───────────────────────────────────────────────────


@pytest.fixture
def sqla_engine() -> Generator[Engine, None, None]:
    engine = create_engine("sqlite://", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def sqla_session(sqla_engine: Engine) -> Generator[Session, None, None]:
    with Session(sqla_engine) as session:
        yield session


# ── Async SQLite fixtures for repository tests ─────────────────────────────


@pytest.fixture
async def async_engine() -> AsyncGenerator[Any, None]:
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
