"""Sync orchestration service — runs connectors, normalizes, persists, tracks runs."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import SyncConnector
from app.connectors.errors import (
    ConnectorError,
    CursorExpiredError,
    SourcePayloadError,
)
from app.models.source_connection import SourceConnection
from app.models.sync_run import SyncRun
from app.models.sync_run_source import SyncRunSource
from app.normalizers.contact_normalizer import normalize_contact
from app.normalizers.event_normalizer import normalize_event
from app.normalizers.transaction_normalizer import normalize_transaction
from app.services.repository import (
    upsert_contact,
    upsert_event,
    upsert_external_record,
    upsert_transaction,
)

_NORMALIZERS: dict[str, Any] = {
    "crm": normalize_contact,
    "calendar": normalize_event,
    "payments": normalize_transaction,
}

_UPSERT_MAP: dict[str, tuple[str, Any]] = {
    "crm": ("contact", upsert_contact),
    "calendar": ("event", upsert_event),
    "payments": ("transaction", upsert_transaction),
}


async def _get_or_create_source_connection(
    session: AsyncSession, connector: SyncConnector
) -> SourceConnection:
    result = await session.execute(
        select(SourceConnection).where(
            SourceConnection.source_name == connector.source_name
        )
    )
    conn = result.scalar_one_or_none()
    if conn is None:
        conn = SourceConnection(
            source_name=connector.source_name,
            source_type=connector.source_type,
        )
        session.add(conn)
        await session.flush()
    return conn


async def run_sync(
    session: AsyncSession, connectors: list[SyncConnector]
) -> SyncRun:
    """Run sync for all given connectors and return the SyncRun record."""
    now = datetime.now(UTC)
    sync_run = SyncRun(
        started_at=now,
        status="running",
        trigger="manual",
    )
    session.add(sync_run)
    await session.flush()

    source_results: list[SyncRunSource] = []
    for connector in connectors:
        result = await _run_one_source(session, connector, sync_run.id)
        source_results.append(result)

    all_success = all(r.status == "success" for r in source_results)
    any_success = any(r.status == "success" for r in source_results)

    if all_success:
        sync_run.status = "success"
    elif any_success:
        sync_run.status = "partial_success"
    else:
        sync_run.status = "failed"

    sync_run.completed_at = datetime.now(UTC)
    sync_run.summary = {
        "total_sources": len(source_results),
        "success": sum(1 for r in source_results if r.status == "success"),
        "failed": sum(1 for r in source_results if r.status == "failed"),
    }

    await session.flush()
    return sync_run


async def _run_one_source(
    session: AsyncSession,
    connector: SyncConnector,
    sync_run_id: int,
) -> SyncRunSource:
    started_at = datetime.now(UTC)
    source_result = SyncRunSource(
        sync_run_id=sync_run_id,
        source_name=connector.source_name,
        status="running",
        sync_mode="unknown",
        records_seen=0,
        records_upserted=0,
        records_rejected=0,
        started_at=started_at,
    )
    session.add(source_result)
    await session.flush()

    records_seen = 0
    records_upserted_count = 0
    records_rejected_count = 0

    try:
        source_conn = await _get_or_create_source_connection(session, connector)
        cursor = source_conn.cursor

        sync_mode: str
        fallback_from_expired = False

        if cursor is not None:
            try:
                fetch_result = await connector.fetch_incremental(cursor)
                sync_mode = "incremental"
            except CursorExpiredError:
                fallback_from_expired = True
                fetch_result = await connector.fetch_full()
                sync_mode = "full_after_cursor_expired"
        else:
            fetch_result = await connector.fetch_full()
            sync_mode = "full"

        normalizer = _NORMALIZERS.get(connector.source_type)
        upsert_info = _UPSERT_MAP.get(connector.source_type)
        if normalizer is None or upsert_info is None:
            raise SourcePayloadError(
                f"No normalizer/upsert for source_type={connector.source_type}"
            )
        record_type_label, upsert_fn = upsert_info

        raw_records = fetch_result.records or []
        records_seen = len(raw_records)

        for raw in raw_records:
            try:
                normalized = normalizer(raw, connector.source_name)
            except SourcePayloadError:
                records_rejected_count += 1
                continue

            await upsert_fn(session, **normalized)
            records_upserted_count += 1

            await upsert_external_record(
                session,
                source_name=connector.source_name,
                source_record_id=normalized["source_record_id"],
                record_type=record_type_label,
                payload=raw,
                source_updated_at=normalized.get("source_updated_at"),
            )

        source_conn.cursor = fetch_result.cursor
        source_conn.cursor_updated_at = datetime.now(UTC)
        if sync_mode == "full" or fallback_from_expired:
            source_conn.last_full_sync_at = datetime.now(UTC)
        else:
            source_conn.last_incremental_sync_at = datetime.now(UTC)

        source_result.status = "success"
        source_result.sync_mode = sync_mode
        source_result.records_seen = records_seen
        source_result.records_upserted = records_upserted_count
        source_result.records_rejected = records_rejected_count
        source_result.completed_at = datetime.now(UTC)

    except ConnectorError as e:
        source_result.status = "failed"
        source_result.sync_mode = sync_mode if "sync_mode" in locals() else "unknown"
        source_result.records_seen = records_seen
        source_result.records_rejected = records_rejected_count
        source_result.error_code = type(e).__name__
        source_result.error_message = str(e)
        source_result.completed_at = datetime.now(UTC)

    except Exception:
        source_result.status = "failed"
        source_result.sync_mode = sync_mode if "sync_mode" in locals() else "unknown"
        source_result.records_seen = records_seen
        source_result.records_rejected = records_rejected_count
        source_result.error_code = "UNEXPECTED_SOURCE_ERROR"
        source_result.error_message = (
            "An unexpected error occurred while syncing this source."
        )
        source_result.completed_at = datetime.now(UTC)

    return source_result
