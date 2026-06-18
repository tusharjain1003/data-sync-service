from datetime import UTC, datetime
from typing import Any

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError


class MockCrmConnector(SyncConnector):
    """Mock CRM connector that returns sample contact records."""

    simulate: str = "normal"  # normal | cursor_expired | source_unavailable

    @property
    def source_name(self) -> str:
        return "mock_crm"

    @property
    def source_type(self) -> str:
        return "crm"

    _sample_records: list[dict[str, Any]] = [
        {
            "id": "crm-001",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Smith",
            "company": "Acme Corp",
            "updated_at": "2026-06-01T10:00:00Z",
        },
        {
            "id": "crm-002",
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Jones",
            "company": "Beta Inc",
            "updated_at": "2026-06-02T12:00:00Z",
        },
        {
            "id": "crm-003",
            "email": "carol@example.com",
            "first_name": "Carol",
            "last_name": "White",
            "company": "Gamma LLC",
            "updated_at": "2026-06-03T08:00:00Z",
        },
    ]

    def _check_source_unavailable(self) -> None:
        if self.simulate == "source_unavailable":
            raise SourceUnavailableError(
                "Mock CRM source unavailable: service returned 503"
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
                "Mock CRM cursor expired: token is no longer valid"
            )

        if cursor is None:
            return await self.fetch_full()

        return FetchResult(
            records=[
                {
                    "id": "crm-004",
                    "email": "dan@example.com",
                    "first_name": "Dan",
                    "last_name": "Brown",
                    "company": "Delta Co",
                    "updated_at": "2026-06-04T09:00:00Z",
                },
            ],
            cursor=f"incr_cursor_{datetime.now(UTC).isoformat()}",
        )
