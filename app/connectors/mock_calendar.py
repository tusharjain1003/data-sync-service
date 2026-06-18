from datetime import UTC, datetime
from typing import Any

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError


class MockCalendarConnector(SyncConnector):
    """Mock calendar connector that returns sample event records."""

    simulate: str = "normal"  # normal | cursor_expired | source_unavailable

    @property
    def source_name(self) -> str:
        return "mock_calendar"

    @property
    def source_type(self) -> str:
        return "calendar"

    _sample_records: list[dict[str, Any]] = [
        {
            "id": "cal-001",
            "summary": "Team standup",
            "start": "2026-06-10T09:00:00Z",
            "end": "2026-06-10T09:30:00Z",
            "attendees": [
                {"email": "alice@example.com"},
                {"email": "bob@example.com"},
            ],
            "updated_at": "2026-06-09T08:00:00Z",
        },
        {
            "id": "cal-002",
            "summary": "Sprint planning",
            "start": "2026-06-11T10:00:00Z",
            "end": "2026-06-11T11:00:00Z",
            "attendees": [
                {"email": "carol@example.com"},
                {"email": "dan@example.com"},
            ],
            "updated_at": "2026-06-10T12:00:00Z",
        },
    ]

    def _check_source_unavailable(self) -> None:
        if self.simulate == "source_unavailable":
            raise SourceUnavailableError(
                "Mock calendar source unavailable: service returned 503"
            )

    async def fetch_full(self) -> FetchResult:
        self._check_source_unavailable()
        return FetchResult(
            records=self._sample_records,
            cursor=f"full_cursor_{datetime.now(UTC).isoformat()}",
        )

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        self._check_source_unavailable()
        if self.simulate == "cursor_expired":
            raise CursorExpiredError(
                "Mock calendar cursor expired: sync token is invalid"
            )

        if cursor is None:
            return await self.fetch_full()

        return FetchResult(
            records=[
                {
                    "id": "cal-003",
                    "summary": "Sprint retro",
                    "start": "2026-06-12T10:00:00Z",
                    "end": "2026-06-12T11:00:00Z",
                    "attendees": [
                        {"email": "alice@example.com"},
                        {"email": "carol@example.com"},
                    ],
                    "updated_at": "2026-06-11T14:00:00Z",
                },
            ],
            cursor=f"incr_cursor_{datetime.now(UTC).isoformat()}",
        )
