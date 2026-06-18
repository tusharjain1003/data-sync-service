from datetime import datetime

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_column


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False)
    canonical_status: Mapped[str] = mapped_column(String(50), nullable=False)
    source_status: Mapped[str] = mapped_column(String(100), nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = utcnow_column(server_default=True)
    updated_at: Mapped[datetime] = utcnow_column(server_default=True)

    __table_args__ = (
        UniqueConstraint(
            "source_name", "source_record_id",
            name="uq_transactions_source",
        ),
    )
