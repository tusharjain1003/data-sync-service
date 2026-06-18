"""Sync API endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    SyncRunDetailResponse,
    SyncRunResponse,
    SyncRunSummary,
    SyncSourceResult,
)
from app.connectors.registry import (
    get_all_connectors,
    get_connector,
    list_known_sources,
)
from app.core.database import get_session
from app.models.sync_run import SyncRun
from app.models.sync_run_source import SyncRunSource
from app.services.sync_orchestrator import run_sync

router = APIRouter(tags=["sync"])


def _build_summary(raw: dict[str, Any] | None) -> SyncRunSummary:
    if raw is None:
        return SyncRunSummary(total_sources=0, success=0, failed=0)
    return SyncRunSummary(**raw)


def _build_source_result(src: SyncRunSource) -> SyncSourceResult:
    return SyncSourceResult(
        source_name=src.source_name,
        status=src.status,
        sync_mode=src.sync_mode,
        records_seen=src.records_seen,
        records_upserted=src.records_upserted,
        records_rejected=src.records_rejected,
        error_code=src.error_code,
        error_message=src.error_message,
        started_at=src.started_at,
        completed_at=src.completed_at,
    )


@router.post("/sync", response_model=SyncRunResponse)
async def trigger_sync(session: AsyncSession = Depends(get_session)) -> SyncRunResponse:
    connectors = get_all_connectors()
    sync_run = await run_sync(session, connectors)
    await session.commit()

    result = await session.execute(
        select(SyncRunSource).where(SyncRunSource.sync_run_id == sync_run.id)
    )
    sources = list(result.scalars().all())

    return SyncRunResponse(
        sync_run_id=sync_run.id,
        status=sync_run.status,
        summary=_build_summary(sync_run.summary),
        sources=[_build_source_result(s) for s in sources],
    )


@router.post("/sync/{source_name}", response_model=SyncRunResponse)
async def trigger_source_sync(
    source_name: str, session: AsyncSession = Depends(get_session)
) -> SyncRunResponse:
    try:
        connector = get_connector(source_name)
    except ValueError:
        known = ", ".join(list_known_sources())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown source '{source_name}'. Known sources: {known}",
        )

    sync_run = await run_sync(session, [connector])
    await session.commit()

    result = await session.execute(
        select(SyncRunSource).where(SyncRunSource.sync_run_id == sync_run.id)
    )
    sources = list(result.scalars().all())

    return SyncRunResponse(
        sync_run_id=sync_run.id,
        status=sync_run.status,
        summary=_build_summary(sync_run.summary),
        sources=[_build_source_result(s) for s in sources],
    )


@router.get("/sync-runs/{sync_run_id}", response_model=SyncRunDetailResponse)
async def get_sync_run(
    sync_run_id: int, session: AsyncSession = Depends(get_session)
) -> SyncRunDetailResponse:
    run = await session.get(SyncRun, sync_run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")

    result = await session.execute(
        select(SyncRunSource).where(SyncRunSource.sync_run_id == sync_run_id)
    )
    sources = list(result.scalars().all())

    return SyncRunDetailResponse(
        id=run.id,
        status=run.status,
        trigger=run.trigger,
        started_at=run.started_at,
        completed_at=run.completed_at,
        summary=SyncRunSummary(**run.summary) if run.summary else None,
        sources=[_build_source_result(s) for s in sources],
    )
