"""Pydantic schemas for API responses."""

from datetime import datetime

from pydantic import BaseModel


class SyncSourceResult(BaseModel):
    source_name: str
    status: str
    sync_mode: str
    records_seen: int
    records_upserted: int
    records_rejected: int
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class SyncRunSummary(BaseModel):
    total_sources: int
    success: int
    failed: int


class SyncRunResponse(BaseModel):
    sync_run_id: int
    status: str
    summary: SyncRunSummary
    sources: list[SyncSourceResult]


class SyncRunDetailResponse(BaseModel):
    id: int
    status: str
    trigger: str
    started_at: datetime
    completed_at: datetime | None
    summary: SyncRunSummary | None
    sources: list[SyncSourceResult]


class MessageResponse(BaseModel):
    message: str
