"""Mocked tests for the Google Calendar connector.

These mock _ensure_service on the connector directly to avoid needing real
Google Calendar credentials.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.normalizers.event_normalizer import normalize_event


def _fake_event(
    event_id: str,
    summary: str = "Test event",
    start: str = "2026-06-10T09:00:00Z",
    end: str = "2026-06-10T09:30:00Z",
    updated: str = "2026-06-09T08:00:00Z",
    attendees: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start, "timeZone": "UTC"},
        "end": {"dateTime": end, "timeZone": "UTC"},
        "attendees": attendees or [],
        "updated": updated,
    }


def _fake_response(
    events: list[dict[str, Any]],
    next_sync_token: str | None = "sync_token_abc",
    next_page_token: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"items": events}
    if next_sync_token:
        result["nextSyncToken"] = next_sync_token
    if next_page_token:
        result["nextPageToken"] = next_page_token
    return result


def _make_mock_service() -> MagicMock:
    """Build a mock service that returns empty responses by default."""
    service = MagicMock()
    service.events().list().execute.return_value = _fake_response([])
    return service


# ── Tests ───────────────────────────────────────────────────────────────────


class TestGoogleCalendarFetchFull:
    async def test_full_fetch_returns_records(self) -> None:
        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        service.events().list().execute.return_value = _fake_response(
            [
                _fake_event("evt_001", summary="Standup"),
                _fake_event("evt_002", summary="Planning"),
            ],
            next_sync_token="sync_new",
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        result = await connector.fetch_full()

        assert len(result.records) == 2
        assert result.records[0]["id"] == "evt_001"
        assert result.records[0]["summary"] == "Standup"
        assert result.records[1]["id"] == "evt_002"
        assert result.records[1]["summary"] == "Planning"
        assert result.cursor == "sync_new"

    async def test_full_fetch_empty(self) -> None:
        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        connector._ensure_service = _make_mock_service  # type: ignore[method-assign]

        result = await connector.fetch_full()

        assert result.records == []
        assert result.cursor is not None

    async def test_full_fetch_api_error(self) -> None:
        from googleapiclient.errors import HttpError

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        resp = MagicMock()
        resp.status = 500
        service.events().list().execute.side_effect = HttpError(
            resp, b"Internal error"
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        with pytest.raises(
            SourceUnavailableError, match="Google Calendar source unavailable"
        ):
            await connector.fetch_full()

    async def test_auth_error(self) -> None:
        from googleapiclient.errors import HttpError

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        resp = MagicMock()
        resp.status = 401
        service.events().list().execute.side_effect = HttpError(
            resp, b"Unauthorized"
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        with pytest.raises(
            SourceUnavailableError,
            match="Google Calendar authentication failed",
        ):
            await connector.fetch_full()


class TestGoogleCalendarFetchIncremental:
    async def test_incremental_returns_changed_events(self) -> None:
        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        service.events().list().execute.return_value = _fake_response(
            [_fake_event("evt_003", summary="New event")],
            next_sync_token="sync_token_xyz",
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        result = await connector.fetch_incremental("sync_token_abc")

        assert len(result.records) == 1
        assert result.records[0]["id"] == "evt_003"
        assert result.cursor == "sync_token_xyz"
        call_kwargs = service.events().list.call_args[1]
        assert call_kwargs.get("syncToken") == "sync_token_abc"

    async def test_incremental_without_cursor_falls_back_to_full(self) -> None:
        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        result = await connector.fetch_incremental(None)

        assert len(result.records) == 0
        call_kwargs = service.events().list.call_args[1]
        assert "syncToken" not in call_kwargs

    async def test_gone_status_raises_cursor_expired(self) -> None:
        from googleapiclient.errors import HttpError

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        resp = MagicMock()
        resp.status = 410
        service.events().list().execute.side_effect = HttpError(
            resp, b"Sync token expired"
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        with pytest.raises(CursorExpiredError, match="sync token expired"):
            await connector.fetch_incremental("expired_token")

    async def test_incremental_api_error(self) -> None:
        from googleapiclient.errors import HttpError

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        service = _make_mock_service()
        resp = MagicMock()
        resp.status = 500
        service.events().list().execute.side_effect = HttpError(
            resp, b"Server error"
        )
        connector._ensure_service = lambda: service  # type: ignore[method-assign]

        with pytest.raises(SourceUnavailableError):
            await connector.fetch_incremental("some_token")


class TestNormalization:
    async def test_event_normalizes_through_normalizer(self) -> None:
        """Verify Google Calendar event shape works with the shared normalizer."""
        event = _fake_event(
            "evt_001",
            summary="Team standup",
            start="2026-06-10T09:00:00Z",
            end="2026-06-10T09:30:00Z",
            attendees=[{"email": "alice@example.com"}],
        )

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        record = connector._to_record(event)

        normalized = normalize_event(record, "google_calendar")
        assert normalized["source_record_id"] == "evt_001"
        assert normalized["title"] == "Team standup"
        assert normalized["starts_at"] is not None
        assert normalized["ends_at"] is not None
        assert normalized["attendee_emails"] == ["alice@example.com"]

    async def test_event_missing_summary(self) -> None:
        event = _fake_event("evt_002", summary="")

        from app.connectors.google_calendar_connector import (
            GoogleCalendarConnector,
        )

        connector = GoogleCalendarConnector()
        record = connector._to_record(event)

        with pytest.raises(Exception, match="missing.*summary"):
            normalize_event(record, "google_calendar")
