from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.sync_run import SyncRun


class SyncRunSource(Base):
    __tablename__ = "sync_run_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sync_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sync_runs.id"), nullable=False
    )
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    records_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_upserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sync_run: Mapped[SyncRun] = relationship(back_populates="source_results")
