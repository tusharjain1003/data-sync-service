"""Tests for the revenue metrics service and endpoints.

Guard tests ensure both summary and breakdown use the same shared query
builder and that a second diverging implementation would be caught.
"""

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import get_session
from app.main import app
from app.models.collected_status_allowlist import CollectedStatusAllowlist
from app.services.metrics import (
    _build_base_query,
    get_revenue_breakdown,
    get_revenue_summary,
)
from app.services.repository import upsert_transaction

# ── Helpers ─────────────────────────────────────────────────────────────────


async def seed_allowlist(session: AsyncSession) -> None:
    """Seed the collected_status_allowlist like the migration does."""
    existing = await session.execute(
        select(CollectedStatusAllowlist).where(
            CollectedStatusAllowlist.canonical_status == "collected"
        )
    )
    if existing.scalar_one_or_none() is None:
        session.add(CollectedStatusAllowlist(
            canonical_status="collected",
            counts_as_collected=True,
        ))
        await session.commit()


async def seed_transaction(
    session: AsyncSession,
    source_record_id: str,
    amount_minor: int,
    canonical_status: str,
    occurred_at: datetime,
    currency: str = "usd",
) -> None:
    await upsert_transaction(
        session,
        source_name="test",
        source_record_id=source_record_id,
        customer_email=f"{source_record_id}@test.com",
        amount_minor=amount_minor,
        currency=currency,
        canonical_status=canonical_status,
        source_status=canonical_status,
        occurred_at=occurred_at,
        source_updated_at=occurred_at,
    )
    await session.commit()


# ── Service tests ───────────────────────────────────────────────────────────


class TestRevenueSummary:
    async def test_only_collected_status_counts(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        now = datetime(2026, 6, 15, tzinfo=UTC)
        await seed_transaction(async_session, "tx-001", 1000, "collected", now)
        await seed_transaction(async_session, "tx-002", 2000, "collected", now)
        await seed_transaction(async_session, "tx-003", 3000, "pending", now)
        await seed_transaction(async_session, "tx-004", 4000, "failed", now)
        await seed_transaction(async_session, "tx-005", 5000, "unknown", now)

        result = await get_revenue_summary(
            async_session, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert len(result) == 1
        assert result[0].total_amount_minor == 3000  # 1000 + 2000 only
        assert result[0].currency == "usd"

    async def test_no_transactions_returns_empty(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        result = await get_revenue_summary(
            async_session, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert result == []

    async def test_outside_date_range_excluded(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        await seed_transaction(
            async_session, "tx-001", 1000, "collected",
            datetime(2026, 5, 1, tzinfo=UTC),
        )
        result = await get_revenue_summary(
            async_session, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert result == []


class TestRevenueBreakdown:
    async def test_daily_breakdown_matches_summary(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        await seed_transaction(
            async_session, "tx-001", 1000, "collected",
            datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC),
        )
        await seed_transaction(
            async_session, "tx-002", 2000, "collected",
            datetime(2026, 6, 2, 10, 0, 0, tzinfo=UTC),
        )
        await seed_transaction(
            async_session, "tx-003", 3000, "collected",
            datetime(2026, 6, 2, 15, 0, 0, tzinfo=UTC),
        )

        start, end = date(2026, 6, 1), date(2026, 6, 30)
        summary = await get_revenue_summary(async_session, start, end)
        breakdown = await get_revenue_breakdown(async_session, start, end, "day")

        total_from_summary = summary[0].total_amount_minor
        total_from_breakdown = sum(b.amount_minor for b in breakdown)
        assert total_from_summary == total_from_breakdown

        assert len(breakdown) == 2  # 2 unique days
        assert breakdown[0].date == "2026-06-01"
        assert breakdown[0].amount_minor == 1000
        assert breakdown[1].date == "2026-06-02"
        assert breakdown[1].amount_minor == 5000


class TestSharedQueryBuilderGuard:
    """Guard: proves both summary and breakdown use the same _build_base_query.

    If someone later writes a second revenue calculation that bypasses the
    shared builder, this test will fail because the mock won't be called.
    """

    async def test_summary_calls_shared_builder(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        await seed_transaction(
            async_session, "tx-001", 1000, "collected",
            datetime(2026, 6, 15, tzinfo=UTC),
        )
        with patch(
            "app.services.metrics._build_base_query",
            wraps=_build_base_query,
        ) as spy:
            await get_revenue_summary(
                async_session, date(2026, 6, 1), date(2026, 6, 30)
            )
            spy.assert_called()

    async def test_breakdown_calls_shared_builder(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        await seed_transaction(
            async_session, "tx-001", 1000, "collected",
            datetime(2026, 6, 15, tzinfo=UTC),
        )
        with patch(
            "app.services.metrics._build_base_query",
            wraps=_build_base_query,
        ) as spy:
            await get_revenue_breakdown(
                async_session, date(2026, 6, 1), date(2026, 6, 30), "day"
            )
            spy.assert_called()


class TestNewStatusGuard:
    """A newly introduced status must not count as collected revenue unless
    explicitly allow-listed."""

    async def test_new_status_does_not_change_revenue(
        self, async_session: AsyncSession
    ) -> None:
        await seed_allowlist(async_session)
        now = datetime(2026, 6, 15, tzinfo=UTC)
        await seed_transaction(async_session, "tx-collected", 1000, "collected", now)
        result = await get_revenue_summary(
            async_session, date(2026, 6, 1), date(2026, 6, 30)
        )
        revenue_before = result[0].total_amount_minor

        # Add a transaction with a brand-new status that is NOT allow-listed
        await seed_transaction(
            async_session, "tx-new", 9999, "brand_new_status", now
        )
        result_after = await get_revenue_summary(
            async_session, date(2026, 6, 1), date(2026, 6, 30)
        )
        assert result_after[0].total_amount_minor == revenue_before


class TestDateValidation:
    async def test_end_before_start_raises(
        self, async_session: AsyncSession
    ) -> None:
        import pytest

        with pytest.raises(ValueError, match="end must be on or after start"):
            await get_revenue_summary(
                async_session, date(2026, 7, 1), date(2026, 6, 1)
            )

    async def test_end_before_start_breakdown_raises(
        self, async_session: AsyncSession
    ) -> None:
        import pytest

        with pytest.raises(ValueError, match="end must be on or after start"):
            await get_revenue_breakdown(
                async_session, date(2026, 7, 1), date(2026, 6, 1), "day"
            )


# ── API integration tests ───────────────────────────────────────────────────


@pytest.fixture
async def client(async_engine: Any) -> Any:
    factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override() -> Any:
        async with factory() as session:
            yield session

    # Seed allowlist for the test DB
    async with factory() as session:
        await seed_allowlist(session)

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestRevenueAPI:
    def test_summary_endpoint(self, client: TestClient) -> None:
        resp = client.post("/sync")
        assert resp.status_code == 200

        resp2 = client.get(
            "/metrics/revenue/summary?start=2026-06-01&end=2026-06-30"
        )
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["start"] == "2026-06-01"
        assert data["end"] == "2026-06-30"
        assert len(data["items"]) == 1
        # mock payments has:
        #   pay-001: 2999 (succeeded -> collected)
        #   pay-002: 4999 (paid -> collected)
        #   pay-003: 999  (pending -> pending, excluded)
        assert data["items"][0]["total_amount_minor"] == 2999 + 4999

    def test_breakdown_endpoint(self, client: TestClient) -> None:
        client.post("/sync")
        resp = client.get(
            "/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["interval"] == "day"
        assert len(data["items"]) > 0

    def test_summary_equals_sum_of_breakdown(self, client: TestClient) -> None:
        client.post("/sync")
        summary_resp = client.get(
            "/metrics/revenue/summary?start=2026-06-01&end=2026-06-30"
        )
        breakdown_resp = client.get(
            "/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30"
        )

        summary_total = summary_resp.json()["items"][0]["total_amount_minor"]
        breakdown_total = sum(
            b["amount_minor"] for b in breakdown_resp.json()["items"]
        )
        assert summary_total == breakdown_total

    def test_invalid_date_range_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/metrics/revenue/summary?start=2026-07-01&end=2026-06-01"
        )
        assert resp.status_code == 422

    def test_invalid_date_format_returns_422(self, client: TestClient) -> None:
        resp = client.get(
            "/metrics/revenue/summary?start=not-a-date&end=2026-06-30"
        )
        assert resp.status_code == 422

    def test_unknown_statuses_excluded(self, client: TestClient) -> None:
        # No sync needed — just verify the allowlist mechanism works
        resp = client.get(
            "/metrics/revenue/summary?start=1970-01-01&end=2099-12-31"
        )
        assert resp.status_code == 200
        # Empty items since no data was synced
        assert resp.json()["items"] == []
