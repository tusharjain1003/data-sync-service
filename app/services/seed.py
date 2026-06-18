"""Deterministic demo seed data for local development and demos.

This module creates sample CRM contacts, calendar events, and transactions
with various statuses across multiple days.  Running it twice is safe —
all inserts use idempotent upserts so rows are never duplicated.

Do not use this as a fallback when real credentials are missing.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_status_allowlist import CollectedStatusAllowlist
from app.services.repository import (
    upsert_contact,
    upsert_event,
    upsert_external_record,
    upsert_transaction,
)


async def ensure_collected_allowlist(session: AsyncSession) -> None:
    """Seed collected_status_allowlist if not already present."""
    result = await session.execute(
        select(CollectedStatusAllowlist).where(
            CollectedStatusAllowlist.canonical_status == "collected"
        )
    )
    if result.scalar_one_or_none() is None:
        session.add(CollectedStatusAllowlist(
            canonical_status="collected",
            counts_as_collected=True,
        ))


async def seed_demo_data(session: AsyncSession) -> dict[str, int]:
    """Insert deterministic demo data.

    Returns a summary dict with counts of seeded records.
    """
    await ensure_collected_allowlist(session)

    source = "demo"

    # ── Contacts ─────────────────────────────────────────────────────────
    contacts_data = [
        ("contact-001", "alice@example.com", "Alice Smith", "Acme Corp"),
        ("contact-002", "bob@example.com", "Bob Jones", "Beta Inc"),
        ("contact-003", "carol@example.com", "Carol White", "Gamma LLC"),
    ]
    for record_id, email, name, company in contacts_data:
        await upsert_contact(
            session, source, record_id, email, name, company,
            datetime(2026, 6, 1, tzinfo=UTC),
        )

    # ── Events ───────────────────────────────────────────────────────────
    events_data = [
        ("event-001", "Team standup",
         datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
         datetime(2026, 6, 10, 9, 30, tzinfo=UTC),
         ["alice@example.com", "bob@example.com"]),
        ("event-002", "Sprint planning",
         datetime(2026, 6, 11, 10, 0, tzinfo=UTC),
         datetime(2026, 6, 11, 11, 0, tzinfo=UTC),
         ["carol@example.com"]),
    ]
    for record_id, title, start, end, attendees in events_data:
        await upsert_event(
            session, source, record_id, title, start, end, attendees,
            datetime(2026, 6, 9, tzinfo=UTC),
        )

    # ── Transactions (various statuses across multiple days) ─────────────
    transactions_data = [
        # (id, email, amount, currency, canonical_status, source_status, occurred_at)
        ("tx-col-001", "alice@example.com", 2999, "usd", "collected", "succeeded",
         datetime(2026, 6, 5, tzinfo=UTC)),
        ("tx-col-002", "bob@example.com", 4999, "usd", "collected", "paid",
         datetime(2026, 6, 6, tzinfo=UTC)),
        ("tx-pen-001", "carol@example.com", 999, "usd", "pending", "pending",
         datetime(2026, 6, 7, tzinfo=UTC)),
        ("tx-col-003", "dan@example.com", 1599, "usd", "collected", "completed",
         datetime(2026, 6, 8, tzinfo=UTC)),
        ("tx-fai-001", "eve@example.com", 5000, "usd", "failed", "failed",
         datetime(2026, 6, 9, tzinfo=UTC)),
        ("tx-ref-001", "frank@example.com", 2500, "usd", "refunded", "refunded",
         datetime(2026, 6, 10, tzinfo=UTC)),
        ("tx-unk-001", "grace@example.com", 1000, "usd", "unknown", "new_unexpected_status",
         datetime(2026, 6, 11, tzinfo=UTC)),
        ("tx-dup-001", "heidi@example.com", 2000, "usd", "collected", "succeeded",
         datetime(2026, 6, 12, tzinfo=UTC)),
    ]
    for record_id, email, amount, currency, canonical, source_status, occurred in transactions_data:
        await upsert_transaction(
            session, source, record_id, email, amount, currency,
            canonical, source_status, occurred, occurred,
        )

    # ── External records for each upserted entity ────────────────────────
    for record_id, *_ in contacts_data:
        await upsert_external_record(
            session, source, record_id, "contact",
            {"id": record_id, "source": "demo_seed"},
            datetime(2026, 6, 1, tzinfo=UTC),
        )
    for record_id, *_ in events_data:
        await upsert_external_record(
            session, source, record_id, "event",
            {"id": record_id, "source": "demo_seed"},
            datetime(2026, 6, 9, tzinfo=UTC),
        )
    for record_id, *_ in transactions_data:
        await upsert_external_record(
            session, source, record_id, "transaction",
            {"id": record_id, "source": "demo_seed"},
            datetime(2026, 6, 1, tzinfo=UTC),
        )

    await session.commit()

    return {
        "contacts": len(contacts_data),
        "events": len(events_data),
        "transactions": len(transactions_data),
    }
