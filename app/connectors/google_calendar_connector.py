"""Real Google Calendar connector — fetches events from Google Calendar API.

Requires GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN,
and GOOGLE_CALENDAR_ID to be configured in the environment.
"""

from datetime import UTC, datetime
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.core.config import settings


class GoogleCalendarConnector(SyncConnector):
    """Connector that fetches Event records from Google Calendar API."""

    def __init__(self) -> None:
        self._client_id = settings.google_client_id
        self._client_secret = settings.google_client_secret
        self._refresh_token = settings.google_refresh_token
        self._calendar_id = settings.google_calendar_id
        self._service: Any = None

    def _ensure_service(self) -> Any:
        if self._service is not None:
            return self._service
        if not self._client_id or not self._client_secret or not self._refresh_token:
            raise SourceUnavailableError(
                "Google Calendar source unavailable: "
                "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and "
                "GOOGLE_REFRESH_TOKEN must be configured"
            )
        creds = Credentials(  # type: ignore[no-untyped-call]
            token=None,
            refresh_token=self._refresh_token,
            token_uri="https://oauth2.googleapis.com/token",  # noqa: S106
            client_id=self._client_id,
            client_secret=self._client_secret,
        )
        creds.refresh(Request())  # type: ignore[no-untyped-call]
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service

    @property
    def source_name(self) -> str:
        return "google_calendar"

    @property
    def source_type(self) -> str:
        return "calendar"

    @staticmethod
    def _to_record(event: dict[str, Any]) -> dict[str, Any]:
        start_info = event.get("start") or {}
        end_info = event.get("end") or {}

        return {
            "id": event["id"],
            "summary": event.get("summary", ""),
            "start": start_info.get("dateTime") or start_info.get("date"),
            "end": end_info.get("dateTime") or end_info.get("date"),
            "attendees": event.get("attendees") or [],
            "updated_at": event.get("updated"),
        }

    async def fetch_full(self) -> FetchResult:
        service = self._ensure_service()
        try:
            events, sync_token = _list_all_events(service, self._calendar_id)
        except HttpError as e:
            _raise_typed_error(e, "full fetch")

        records = [self._to_record(e) for e in events]
        cursor = sync_token or str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=cursor)

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()

        service = self._ensure_service()
        try:
            events, sync_token = _list_events_since(
                service, self._calendar_id, cursor
            )
        except HttpError as e:
            _raise_typed_error(e, "incremental fetch")

        records = [self._to_record(e) for e in events]
        new_cursor = sync_token or str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=new_cursor)


# ── Module-level helpers ──────────────────────────────────────────────────


def _list_all_events(
    service: Any, calendar_id: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch all events with pagination, returning (events, next_sync_token)."""
    all_events: list[dict[str, Any]] = []
    page_token: str | None = None
    sync_token: str | None = None

    while True:
        kwargs: dict[str, Any] = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = service.events().list(**kwargs).execute()
        all_events.extend(response.get("items", []))
        sync_token = response.get("nextSyncToken")

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_events, sync_token


def _list_events_since(
    service: Any, calendar_id: str, sync_token: str
) -> tuple[list[dict[str, Any]], str | None]:
    """Fetch events changed since the given sync token."""
    all_events: list[dict[str, Any]] = []
    page_token: str | None = None
    next_sync_token: str | None = None

    while True:
        kwargs: dict[str, Any] = {
            "calendarId": calendar_id,
            "syncToken": sync_token,
            "singleEvents": True,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        response = service.events().list(**kwargs).execute()
        all_events.extend(response.get("items", []))
        next_sync_token = response.get("nextSyncToken")

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return all_events, next_sync_token


def _raise_typed_error(error: HttpError, context: str) -> None:
    status = error.status_code if hasattr(error, "status_code") else None

    if status in (401, 403):
        raise SourceUnavailableError(
            f"Google Calendar authentication failed during {context}: {error}"
        )
    if status == 410:
        raise CursorExpiredError(
            f"Google Calendar sync token expired during {context}: {error}"
        )
    if status in (429,) or (status is not None and status >= 500):
        raise SourceUnavailableError(
            f"Google Calendar source unavailable during {context}: {error}"
        )
    raise SourceUnavailableError(
        f"Google Calendar source unavailable during {context}: {error}"
    )
