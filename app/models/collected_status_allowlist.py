from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utcnow_column


class CollectedStatusAllowlist(Base):
    __tablename__ = "collected_status_allowlist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_status: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    counts_as_collected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime] = utcnow_column(server_default=True)
