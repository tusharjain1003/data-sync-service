"""Tests for the idempotent persistence layer."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.event import Event
from app.models.external_record import ExternalRecord
from app.models.transaction import Transaction
from app.services.repository import (
    count_rows,
    upsert_contact,
    upsert_event,
    upsert_external_record,
    upsert_transaction,
)


@pytest.fixture
def dt() -> datetime:
    return datetime.now(UTC)


# ── Contact upsert idempotency ──────────────────────────────────────────────


class TestContactUpsert:
    async def test_insert_then_upsert_same_contact_keeps_one_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_contact(
            async_session, "mock_crm", "crm-001",
            "alice@example.com", "Alice Smith", "Acme Corp", dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Contact) == 1

        await upsert_contact(
            async_session, "mock_crm", "crm-001",
            "alice@example.com", "Alice Smith", "Acme Corp", dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Contact) == 1

    async def test_insert_two_different_contacts_creates_two_rows(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_contact(
            async_session, "mock_crm", "crm-001",
            "alice@example.com", "Alice Smith", None, dt,
        )
        await upsert_contact(
            async_session, "mock_crm", "crm-002",
            "bob@example.com", "Bob Jones", None, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Contact) == 2

    async def test_upsert_updates_existing_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_contact(
            async_session, "mock_crm", "crm-001",
            "old@example.com", "Old Name", None, dt,
        )
        await async_session.commit()

        new_dt = datetime(2026, 7, 1, tzinfo=UTC)
        await upsert_contact(
            async_session, "mock_crm", "crm-001",
            "new@example.com", "New Name", None, new_dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Contact) == 1


# ── Event upsert idempotency ────────────────────────────────────────────────


class TestEventUpsert:
    async def test_insert_then_upsert_same_event_keeps_one_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_event(
            async_session, "mock_calendar", "cal-001",
            "Standup", dt, dt, ["alice@test.com"], dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Event) == 1

        await upsert_event(
            async_session, "mock_calendar", "cal-001",
            "Standup", dt, dt, ["alice@test.com"], dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Event) == 1

    async def test_upsert_updates_existing_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_event(
            async_session, "mock_calendar", "cal-001",
            "Old title", dt, dt, None, dt,
        )
        await async_session.commit()

        await upsert_event(
            async_session, "mock_calendar", "cal-001",
            "Updated title", dt, dt, None, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Event) == 1


# ── Transaction upsert idempotency ──────────────────────────────────────────


class TestTransactionUpsert:
    async def test_insert_then_upsert_same_transaction_keeps_one_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_transaction(
            async_session, "mock_payments", "pay-001",
            "alice@example.com", 2999, "usd", "collected", "succeeded", dt, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Transaction) == 1

        await upsert_transaction(
            async_session, "mock_payments", "pay-001",
            "alice@example.com", 2999, "usd", "collected", "succeeded", dt, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Transaction) == 1

    async def test_upsert_updates_existing_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_transaction(
            async_session, "mock_payments", "pay-001",
            "old@example.com", 1000, "usd", "pending", "pending", dt, dt,
        )
        await async_session.commit()

        await upsert_transaction(
            async_session, "mock_payments", "pay-001",
            "new@example.com", 2000, "usd", "collected", "paid", dt, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, Transaction) == 1


# ── External record upsert idempotency ──────────────────────────────────────


class TestExternalRecordUpsert:
    async def test_insert_then_upsert_same_record_keeps_one_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact",
            {"name": "Alice"}, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, ExternalRecord) == 1

        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact",
            {"name": "Alice"}, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, ExternalRecord) == 1

    async def test_different_record_type_is_different_row(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact",
            {"name": "Alice"}, dt,
        )
        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact_raw",
            {"raw": {"name": "Alice"}}, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, ExternalRecord) == 2

    async def test_reingest_changed_payload_updates_hash_and_content(
        self, async_session: AsyncSession, dt: datetime
    ) -> None:
        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact",
            {"name": "Alice", "email": "alice@example.com"}, dt,
        )
        await async_session.commit()

        await upsert_external_record(
            async_session, "mock_crm", "crm-001", "contact",
            {"name": "Alice Updated", "email": "alice@new.com"}, dt,
        )
        await async_session.commit()
        assert await count_rows(async_session, ExternalRecord) == 1

        updated = await async_session.get(ExternalRecord, 1)
        assert updated is not None
        assert updated.payload == {"name": "Alice Updated", "email": "alice@new.com"}
