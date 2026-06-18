"""Canonical revenue metrics service.

Both summary and breakdown share a single query builder so the calculation
path cannot diverge.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.collected_status_allowlist import CollectedStatusAllowlist
from app.models.transaction import Transaction


@dataclass
class RevenueSummaryRow:
    currency: str
    total_amount_minor: int


@dataclass
class RevenueBreakdownRow:
    date: str
    currency: str
    amount_minor: int


def _validate_date_range(start: date, end: date) -> None:
    if end < start:
        raise ValueError("end must be on or after start")


def _build_base_query(start: date, end: date, group_by: list[Any]) -> Any:
    """Shared query builder — both summary and breakdown use this path."""
    _validate_date_range(start, end)
    return (
        select(*group_by)
        .join(
            CollectedStatusAllowlist,
            Transaction.canonical_status
            == CollectedStatusAllowlist.canonical_status,
        )
        .where(CollectedStatusAllowlist.counts_as_collected.is_(True))
        .where(Transaction.occurred_at >= datetime.combine(start, datetime.min.time()))
        .where(Transaction.occurred_at < datetime.combine(end, datetime.max.time()))
    )


async def get_revenue_summary(
    session: AsyncSession,
    start: date,
    end: date,
) -> list[RevenueSummaryRow]:
    _validate_date_range(start, end)

    stmt = _build_base_query(
        start, end,
        [
            Transaction.currency,
            func.sum(Transaction.amount_minor).label("total_amount_minor"),
        ],
    )
    stmt = stmt.group_by(Transaction.currency)

    result = await session.execute(stmt)
    rows = result.all()
    return [
        RevenueSummaryRow(
            currency=row.currency,
            total_amount_minor=int(row.total_amount_minor),
        )
        for row in rows
    ]


async def get_revenue_breakdown(
    session: AsyncSession,
    start: date,
    end: date,
    interval: str = "day",
) -> list[RevenueBreakdownRow]:
    _validate_date_range(start, end)

    if interval != "day":
        raise ValueError(f"Unsupported interval: {interval}")

    date_col = func.date(Transaction.occurred_at).label("date")

    stmt = _build_base_query(
        start, end,
        [
            date_col,
            Transaction.currency,
            func.sum(Transaction.amount_minor).label("amount_minor"),
        ],
    )
    stmt = stmt.group_by(date_col, Transaction.currency).order_by(date_col)

    result = await session.execute(stmt)
    rows = result.all()
    return [
        RevenueBreakdownRow(
            date=row.date.isoformat() if hasattr(row.date, "isoformat") else str(row.date),
            currency=row.currency,
            amount_minor=int(row.amount_minor),
        )
        for row in rows
    ]
