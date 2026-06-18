from datetime import UTC, datetime
from typing import Any

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError


class MockPaymentsConnector(SyncConnector):
    """Mock payments connector that returns sample transaction records."""

    simulate: str = "normal"  # normal | cursor_expired | source_unavailable

    @property
    def source_name(self) -> str:
        return "mock_payments"

    @property
    def source_type(self) -> str:
        return "payments"

    _sample_records: list[dict[str, Any]] = [
        {
            "id": "pay-001",
            "customer_email": "alice@example.com",
            "amount": 2999,
            "currency": "usd",
            "status": "succeeded",
            "created": "2026-06-05T10:00:00Z",
            "updated_at": "2026-06-05T10:00:00Z",
        },
        {
            "id": "pay-002",
            "customer_email": "bob@example.com",
            "amount": 4999,
            "currency": "usd",
            "status": "paid",
            "created": "2026-06-06T12:00:00Z",
            "updated_at": "2026-06-06T12:00:00Z",
        },
        {
            "id": "pay-003",
            "customer_email": "carol@example.com",
            "amount": 999,
            "currency": "usd",
            "status": "pending",
            "created": "2026-06-07T08:00:00Z",
            "updated_at": "2026-06-07T08:00:00Z",
        },
    ]

    def _check_source_unavailable(self) -> None:
        if self.simulate == "source_unavailable":
            raise SourceUnavailableError(
                "Mock payments source unavailable: service returned 503"
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
                "Mock payments cursor expired: pagination token is invalid"
            )

        if cursor is None:
            return await self.fetch_full()

        return FetchResult(
            records=[
                {
                    "id": "pay-004",
                    "customer_email": "dan@example.com",
                    "amount": 1599,
                    "currency": "usd",
                    "status": "completed",
                    "created": "2026-06-08T09:00:00Z",
                    "updated_at": "2026-06-08T09:00:00Z",
                },
            ],
            cursor=f"incr_cursor_{datetime.now(UTC).isoformat()}",
        )
