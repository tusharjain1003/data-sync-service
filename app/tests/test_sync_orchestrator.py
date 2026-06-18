"""Tests for the sync orchestration service."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError
from app.connectors.mock_calendar import MockCalendarConnector
from app.connectors.mock_crm import MockCrmConnector
from app.connectors.mock_payments import MockPaymentsConnector
from app.models.contact import Contact
from app.models.event import Event
from app.models.source_connection import SourceConnection
from app.models.sync_run import SyncRun
from app.models.sync_run_source import SyncRunSource
from app.models.transaction import Transaction
from app.services.sync_orchestrator import run_sync

# ── Test helpers: connectors with specific failure patterns ─────────────────


class MockCrmCursorExpiredOnIncremental(MockCrmConnector):
    """Raises CursorExpiredError only from fetch_incremental; fetch_full works."""

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()
        raise CursorExpiredError("Simulated cursor expired")


class MockCrmWithMalformed(MockCrmConnector):
    """Extends mock CRM to include a malformed record (missing id)."""

    async def fetch_full(self) -> FetchResult:
        result = await super().fetch_full()
        result.records.append(
            {
                "company": "Missing ID Inc",
                "email": "no-id@example.com",
            }
        )
        return result

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()
        result = await super().fetch_incremental(cursor)
        result.records.append(
            {
                "company": "Incremental No ID",
                "email": "incr-no-id@test.com",
            }
        )
        return result


class MockCalendarWithMalformed(MockCalendarConnector):
    """Extends mock Calendar to include a malformed event (missing summary)."""

    async def fetch_full(self) -> FetchResult:
        result = await super().fetch_full()
        result.records.append(
            {
                "id": "cal-malformed",
                "start": "2026-06-10T09:00:00Z",
                "end": "2026-06-10T09:30:00Z",
            }
        )
        return result

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()
        result = await super().fetch_incremental(cursor)
        result.records.append(
            {
                "id": "cal-incr-malformed",
                "start": "2026-06-10T09:00:00Z",
            }
        )
        return result


class MockCrmWithUnexpectedError(MockCrmConnector):
    """Raises TypeError on any fetch."""

    async def fetch_full(self) -> FetchResult:
        raise TypeError("unexpected type error in CRM")

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        raise TypeError("unexpected type error in CRM")


class MockCalendarWithAttributeError(MockCalendarConnector):
    """Raises AttributeError on any fetch."""

    async def fetch_full(self) -> FetchResult:
        raise AttributeError("unexpected attribute error in Calendar")

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        raise AttributeError("unexpected attribute error in Calendar")


class MockPaymentsWithMalformed(MockPaymentsConnector):
    """Extends mock Payments to include a malformed transaction (missing amount)."""

    async def fetch_full(self) -> FetchResult:
        result = await super().fetch_full()
        result.records.append(
            {
                "id": "pay-malformed",
                "currency": "usd",
                "status": "succeeded",
            }
        )
        return result

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()
        result = await super().fetch_incremental(cursor)
        result.records.append(
            {
                "id": "pay-incr-malformed",
                "currency": "usd",
                "status": "succeeded",
            }
        )
        return result


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def connectors() -> list[SyncConnector]:
    return [
        MockCrmConnector(),
        MockCalendarConnector(),
        MockPaymentsConnector(),
    ]


@pytest.fixture
async def synced_run(
    async_session: AsyncSession, connectors: list[SyncConnector]
) -> SyncRun:
    result = await run_sync(async_session, connectors)
    await async_session.commit()
    return result


# ── Tests ───────────────────────────────────────────────────────────────────


class TestFullSync:
    """First sync — no cursor exists, expect full fetch for every source."""

    async def test_all_sources_succeed(self, synced_run: SyncRun) -> None:
        assert synced_run.status == "success"

    async def test_all_sources_use_full_sync_mode(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        results = await _source_results(async_session, synced_run.id)
        for r in results:
            assert r.sync_mode == "full", f"{r.source_name} was {r.sync_mode}"

    async def test_contacts_are_persisted(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        assert await _count(async_session, Contact) == 3

    async def test_events_are_persisted(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        assert await _count(async_session, Event) == 2

    async def test_transactions_are_persisted(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        assert await _count(async_session, Transaction) == 3

    async def test_cursor_is_saved(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        for name in ("mock_crm", "mock_calendar", "mock_payments"):
            conn = await _source_connection(async_session, name)
            assert conn is not None
            assert conn.cursor is not None
            assert conn.last_full_sync_at is not None

    async def test_source_results_recorded(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        results = await _source_results(async_session, synced_run.id)
        assert len(results) == 3
        for r in results:
            assert r.status == "success"
            assert r.records_rejected == 0
            assert r.records_seen == r.records_upserted


class TestSecondIncrementalSync:
    """Second sync — cursor exists, expect incremental fetch."""

    async def test_incremental_sync_mode(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        second_run = await run_sync(async_session, [
            MockCrmConnector(),
            MockCalendarConnector(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()

        results = await _source_results(async_session, second_run.id)
        for r in results:
            assert r.sync_mode == "incremental"

    async def test_new_records_are_upserted(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        await run_sync(async_session, [
            MockCrmConnector(),
            MockCalendarConnector(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()

        assert await _count(async_session, Contact) == 4  # 3 + 1 new
        assert await _count(async_session, Event) == 3  # 2 + 1 new
        assert await _count(async_session, Transaction) == 4  # 3 + 1 new


class TestDuplicateSyncIsIdempotent:
    """Re-running the same data must not increase row counts beyond what the
    first incremental pass already brought in."""

    async def test_third_run_does_not_add_rows(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        # Second run — incremental, adds 1 new record per source
        await run_sync(async_session, [
            MockCrmConnector(),
        ])
        await async_session.commit()
        after_second = await _count(async_session, Contact)

        # Third run — same incremental data already in DB, upsert is no-op
        await run_sync(async_session, [
            MockCrmConnector(),
        ])
        await async_session.commit()
        after_third = await _count(async_session, Contact)

        assert after_third == after_second


class TestCursorExpiryFallback:
    """When incremental raises CursorExpiredError, orchestrator falls back to full fetch."""

    async def test_falls_back_to_full_fetch(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmCursorExpiredOnIncremental()
        second_run = await run_sync(async_session, [crm])
        await async_session.commit()

        assert second_run.status == "success"
        results = await _source_results(async_session, second_run.id)
        assert len(results) == 1
        assert results[0].sync_mode == "full_after_cursor_expired"

    async def test_data_still_lands(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmCursorExpiredOnIncremental()
        await run_sync(async_session, [crm])
        await async_session.commit()
        # Should have the 3 original rows (upserted again during full fetch)
        assert await _count(async_session, Contact) == 3


class TestPartialFailure:
    """One source failing must not prevent others from syncing."""

    async def test_partial_success_status(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmConnector()
        crm.simulate = "source_unavailable"
        second_run = await run_sync(async_session, [
            crm,
            MockCalendarConnector(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()
        assert second_run.status == "partial_success"

    async def test_failed_source_has_error(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmConnector()
        crm.simulate = "source_unavailable"
        second_run = await run_sync(async_session, [crm])
        await async_session.commit()
        results = await _source_results(async_session, second_run.id)
        assert len(results) == 1
        assert results[0].status == "failed"
        assert results[0].error_code == "SourceUnavailableError"

    async def test_healthy_sources_still_land_data(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmConnector()
        crm.simulate = "source_unavailable"
        await run_sync(async_session, [
            crm,
            MockCalendarConnector(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()

        # Calendar did incremental (synced_run already synced it once)
        assert await _count(async_session, Event) == 3  # 2 full + 1 incremental
        # Payments did incremental
        assert await _count(async_session, Transaction) == 4  # 3 full + 1 incremental

    async def test_healthy_sources_use_incremental_on_second_run(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        crm = MockCrmConnector()
        crm.simulate = "source_unavailable"
        second_run = await run_sync(async_session, [
            crm,
            MockCalendarConnector(),
        ])
        await async_session.commit()
        results = await _source_results(async_session, second_run.id)
        for r in results:
            if r.source_name == "mock_crm":
                assert r.status == "failed"
            else:
                assert r.status == "success"


class TestMalformedRecordRejection:
    """Malformed records are rejected but valid records still land."""

    async def test_malformed_contacts_are_rejected(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        crm = MockCrmWithMalformed()
        run = await run_sync(async_session, [crm])
        await async_session.commit()
        results = await _source_results(async_session, run.id)
        assert len(results) == 1
        assert results[0].records_rejected == 1
        assert results[0].records_seen == 4  # 3 valid + 1 malformed
        assert results[0].records_upserted == 3

    async def test_valid_contacts_still_land(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        crm = MockCrmWithMalformed()
        await run_sync(async_session, [crm])
        await async_session.commit()
        assert await _count(async_session, Contact) == 3

    async def test_malformed_events_are_rejected(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        cal = MockCalendarWithMalformed()
        run = await run_sync(async_session, [cal])
        await async_session.commit()
        results = await _source_results(async_session, run.id)
        assert len(results) == 1
        assert results[0].records_rejected == 1
        assert results[0].records_seen == 3
        assert results[0].records_upserted == 2

    async def test_valid_events_still_land(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        cal = MockCalendarWithMalformed()
        await run_sync(async_session, [cal])
        await async_session.commit()
        assert await _count(async_session, Event) == 2

    async def test_malformed_transactions_are_rejected(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        pay = MockPaymentsWithMalformed()
        run = await run_sync(async_session, [pay])
        await async_session.commit()
        results = await _source_results(async_session, run.id)
        assert len(results) == 1
        assert results[0].records_rejected == 1
        assert results[0].records_seen == 4
        assert results[0].records_upserted == 3

    async def test_valid_transactions_still_land(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        pay = MockPaymentsWithMalformed()
        await run_sync(async_session, [pay])
        await async_session.commit()
        assert await _count(async_session, Transaction) == 3


class TestAllSourcesFail:
    """When all sources fail, run status is 'failed'."""

    async def test_all_failed_status(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        connectors_ = [
            MockCrmConnector(),
            MockCalendarConnector(),
        ]
        for c in connectors_:
            c.simulate = "source_unavailable"  # type: ignore[attr-defined]
        run = await run_sync(async_session, connectors_)
        await async_session.commit()
        assert run.status == "failed"

    async def test_summary_counts(
        self, async_session: AsyncSession, synced_run: SyncRun
    ) -> None:
        connectors_ = [
            MockCrmConnector(),
            MockCalendarConnector(),
        ]
        for c in connectors_:
            c.simulate = "source_unavailable"  # type: ignore[attr-defined]
        run = await run_sync(async_session, connectors_)
        await async_session.commit()
        assert run.summary == {
            "total_sources": 2,
            "success": 0,
            "failed": 2,
        }


class TestUnexpectedSourceErrors:
    """Unexpected exceptions in one source must not prevent other sources from syncing."""

    async def test_type_error_in_one_source_does_not_block_others(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        run = await run_sync(async_session, [
            MockCrmWithUnexpectedError(),
            MockCalendarConnector(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()
        assert run.status == "partial_success"

        results = await _source_results(async_session, run.id)
        results_by_name = {r.source_name: r for r in results}
        assert results_by_name["mock_crm"].status == "failed"
        assert results_by_name["mock_crm"].error_code == "UNEXPECTED_SOURCE_ERROR"
        assert results_by_name["mock_calendar"].status == "success"
        assert results_by_name["mock_payments"].status == "success"

    async def test_attribute_error_in_one_source_does_not_block_others(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        run = await run_sync(async_session, [
            MockCrmConnector(),
            MockCalendarWithAttributeError(),
            MockPaymentsConnector(),
        ])
        await async_session.commit()
        assert run.status == "partial_success"

        results = await _source_results(async_session, run.id)
        results_by_name = {r.source_name: r for r in results}
        assert results_by_name["mock_calendar"].status == "failed"
        assert results_by_name["mock_calendar"].error_code == "UNEXPECTED_SOURCE_ERROR"
        assert results_by_name["mock_crm"].status == "success"
        assert results_by_name["mock_payments"].status == "success"

    async def test_all_sources_with_unexpected_error_status_is_failed(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        run = await run_sync(async_session, [
            MockCrmWithUnexpectedError(),
            MockCalendarWithAttributeError(),
        ])
        await async_session.commit()
        assert run.status == "failed"

        results = await _source_results(async_session, run.id)
        for r in results:
            assert r.status == "failed"
            assert r.error_code == "UNEXPECTED_SOURCE_ERROR"

    async def test_unexpected_error_does_not_hide_malformed_rejection(
        self, async_session: AsyncSession, connectors: list[SyncConnector]
    ) -> None:
        run = await run_sync(async_session, [
            MockCrmWithUnexpectedError(),
            MockPaymentsWithMalformed(),
        ])
        await async_session.commit()
        assert run.status == "partial_success"

        results = await _source_results(async_session, run.id)
        results_by_name = {r.source_name: r for r in results}
        assert results_by_name["mock_crm"].status == "failed"
        assert results_by_name["mock_payments"].status == "success"
        # Rejected count is present (not zero), validating that record-level
        # SourcePayloadError rejection still works alongside unexpected errors.
        assert results_by_name["mock_payments"].records_rejected >= 1


# ── Helpers ─────────────────────────────────────────────────────────────────


async def _count(session: AsyncSession, model: Any) -> int:
    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    result = await session.execute(sa_select(sa_func.count()).select_from(model))
    return result.scalar_one()


async def _source_results(
    session: AsyncSession, sync_run_id: int
) -> list[SyncRunSource]:
    result = await session.execute(
        select(SyncRunSource).where(SyncRunSource.sync_run_id == sync_run_id)
    )
    return list(result.scalars().all())


async def _source_connection(
    session: AsyncSession, source_name: str
) -> SourceConnection | None:
    result = await session.execute(
        select(SourceConnection).where(SourceConnection.source_name == source_name)
    )
    return result.scalar_one_or_none()
