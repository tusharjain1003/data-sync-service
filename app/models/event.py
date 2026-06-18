from datetime import datetime

from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_column


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    attendee_emails: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = utcnow_column(server_default=True)
    updated_at: Mapped[datetime] = utcnow_column(server_default=True)

    __table_args__ = (
        UniqueConstraint(
            "source_name", "source_record_id",
            name="uq_events_source",
        ),
    )
