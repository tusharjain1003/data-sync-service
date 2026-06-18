"""Idempotent persistence layer — upsert helpers for all entity types."""

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.event import Event
from app.models.external_record import ExternalRecord
from app.models.transaction import Transaction


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


async def upsert_contact(
    session: AsyncSession,
    source_name: str,
    source_record_id: str,
    email: str | None,
    name: str | None,
    company: str | None,
    source_updated_at: datetime | None,
) -> None:
    stmt = pg_insert(Contact).values(
        source_name=source_name,
        source_record_id=source_record_id,
        email=email,
        name=name,
        company=company,
        source_updated_at=source_updated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_name", "source_record_id"],
        set_={
            "email": stmt.excluded.email,
            "name": stmt.excluded.name,
            "company": stmt.excluded.company,
            "source_updated_at": stmt.excluded.source_updated_at,
        },
    )
    await session.execute(stmt)


async def upsert_event(
    session: AsyncSession,
    source_name: str,
    source_record_id: str,
    title: str,
    starts_at: datetime | None,
    ends_at: datetime | None,
    attendee_emails: list[str] | None,
    source_updated_at: datetime | None,
) -> None:
    stmt = pg_insert(Event).values(
        source_name=source_name,
        source_record_id=source_record_id,
        title=title,
        starts_at=starts_at,
        ends_at=ends_at,
        attendee_emails=attendee_emails,
        source_updated_at=source_updated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_name", "source_record_id"],
        set_={
            "title": stmt.excluded.title,
            "starts_at": stmt.excluded.starts_at,
            "ends_at": stmt.excluded.ends_at,
            "attendee_emails": stmt.excluded.attendee_emails,
            "source_updated_at": stmt.excluded.source_updated_at,
        },
    )
    await session.execute(stmt)


async def upsert_transaction(
    session: AsyncSession,
    source_name: str,
    source_record_id: str,
    customer_email: str | None,
    amount_minor: int,
    currency: str,
    canonical_status: str,
    source_status: str,
    occurred_at: datetime | None,
    source_updated_at: datetime | None,
) -> None:
    stmt = pg_insert(Transaction).values(
        source_name=source_name,
        source_record_id=source_record_id,
        customer_email=customer_email,
        amount_minor=amount_minor,
        currency=currency,
        canonical_status=canonical_status,
        source_status=source_status,
        occurred_at=occurred_at,
        source_updated_at=source_updated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_name", "source_record_id"],
        set_={
            "customer_email": stmt.excluded.customer_email,
            "amount_minor": stmt.excluded.amount_minor,
            "currency": stmt.excluded.currency,
            "canonical_status": stmt.excluded.canonical_status,
            "source_status": stmt.excluded.source_status,
            "occurred_at": stmt.excluded.occurred_at,
            "source_updated_at": stmt.excluded.source_updated_at,
        },
    )
    await session.execute(stmt)


async def upsert_external_record(
    session: AsyncSession,
    source_name: str,
    source_record_id: str,
    record_type: str,
    payload: dict[str, Any],
    source_updated_at: datetime | None,
) -> None:
    stmt = pg_insert(ExternalRecord).values(
        source_name=source_name,
        source_record_id=source_record_id,
        record_type=record_type,
        payload=payload,
        payload_hash=_payload_hash(payload),
        source_updated_at=source_updated_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source_name", "source_record_id", "record_type"],
        set_={
            "payload": stmt.excluded.payload,
            "payload_hash": stmt.excluded.payload_hash,
            "source_updated_at": stmt.excluded.source_updated_at,
        },
    )
    await session.execute(stmt)


async def count_rows(session: AsyncSession, model: Any) -> int:

    stmt = select(func.count()).select_from(model)
    result = await session.execute(stmt)
    return result.scalar_one()
