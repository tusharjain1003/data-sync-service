"""Real HubSpot CRM connector — fetches contacts from HubSpot CRM.

Requires HUBSPOT_ACCESS_TOKEN to be configured in the environment.
"""

from datetime import UTC, datetime
from typing import Any

import hubspot
from hubspot.crm.contacts import (
    ApiException,
    Filter,
    FilterGroup,
    PublicObjectSearchRequest,
)

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.core.config import settings

_CONTACT_PROPERTIES = ["email", "firstname", "lastname", "company"]


class HubspotCrmConnector(SyncConnector):
    """Connector that fetches Contact records from HubSpot CRM."""

    def __init__(self) -> None:
        self._token = settings.hubspot_access_token
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self._token:
            raise SourceUnavailableError(
                "HubSpot source unavailable: HUBSPOT_ACCESS_TOKEN is not configured"
            )
        self._client = hubspot.Client.create(access_token=self._token)
        return self._client

    @property
    def source_name(self) -> str:
        return "hubspot_crm"

    @property
    def source_type(self) -> str:
        return "crm"

    @staticmethod
    def _to_record(contact: Any) -> dict[str, Any]:
        props = contact.properties or {}
        return {
            "id": contact.id,
            "email": props.get("email"),
            "first_name": props.get("firstname"),
            "last_name": props.get("lastname"),
            "company": props.get("company"),
            "updated_at": contact.updated_at,
        }

    async def fetch_full(self) -> FetchResult:
        client = self._ensure_client()
        try:
            contacts = _list_all_contacts(client)
        except ApiException as e:
            _raise_typed_error(e, "full fetch")

        records = [self._to_record(c) for c in contacts]
        cursor = str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=cursor)

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()

        try:
            cursor_ts = int(cursor)
        except (ValueError, TypeError):
            raise CursorExpiredError(
                f"HubSpot cursor is invalid: {cursor!r}"
            )

        cursor_dt = datetime.fromtimestamp(cursor_ts, tz=UTC).isoformat()
        client = self._ensure_client()

        try:
            contacts = _search_contacts_modified_since(client, cursor_dt)
        except ApiException as e:
            _raise_typed_error(e, "incremental fetch")

        records = [self._to_record(c) for c in contacts]
        new_cursor = str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=new_cursor)


# ── Module-level helpers ──────────────────────────────────────────────────


def _list_all_contacts(client: Any) -> list[Any]:
    """Fetch all contacts using paging."""
    results: list[Any] = []
    after: str | None = None

    while True:
        kwargs: dict[str, Any] = {"limit": 100, "properties": _CONTACT_PROPERTIES}
        if after:
            kwargs["after"] = after

        page = client.crm.contacts.basic_api.get_page(**kwargs)
        results.extend(page.results)

        if page.paging and page.paging.next:
            after = page.paging.next.after
        else:
            break

    return results


def _search_contacts_modified_since(
    client: Any, since_dt: str
) -> list[Any]:
    """Search contacts modified since the given datetime."""
    filter_group = FilterGroup(
        filters=[
            Filter(
                property_name="hs_lastmodifieddate",
                operator="GTE",
                value=since_dt,
            )
        ]
    )
    search_request = PublicObjectSearchRequest(
        filter_groups=[filter_group],
        properties=_CONTACT_PROPERTIES,
        limit=100,
    )

    results: list[Any] = []
    after: str | None = None

    while True:
        if after:
            search_request.after = after
        else:
            search_request.after = None

        page = client.crm.contacts.search_api.do_search(search_request)
        results.extend(page.results)

        if page.paging and page.paging.next:
            after = page.paging.next.after
        else:
            break

    return results


def _raise_typed_error(error: ApiException, context: str) -> None:
    status = error.status if hasattr(error, "status") else None
    body = str(error.body) if hasattr(error, "body") and error.body else ""

    if status in (401, 403):
        raise SourceUnavailableError(
            f"HubSpot authentication failed during {context}: {error}"
        )
    if status == 410:
        raise CursorExpiredError(
            f"HubSpot cursor expired during {context}: {error}"
        )
    if status in (429,) or (status is not None and status >= 500):
        raise SourceUnavailableError(
            f"HubSpot source unavailable during {context}: {error}"
        )
    if "expired" in body.lower() or "invalid" in body.lower():
        raise CursorExpiredError(
            f"HubSpot cursor expired during {context}: {error}"
        )
    raise SourceUnavailableError(
        f"HubSpot source unavailable during {context}: {error}"
    )
