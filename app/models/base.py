from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def utcnow_column(*, server_default: bool = False) -> Mapped[datetime]:
    if server_default:
        return mapped_column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        )
    return mapped_column(DateTime(timezone=True), nullable=False)
