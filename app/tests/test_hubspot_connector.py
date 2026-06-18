"""Mocked tests for the HubSpot CRM connector.

These tests mock hubspot.Client and all API calls so no real HubSpot
access token is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.normalizers.contact_normalizer import normalize_contact


def _fake_contact(
    contact_id: str,
    email: str | None = "test@example.com",
    firstname: str = "Test",
    lastname: str = "User",
    company: str = "Acme",
    updated_at: str = "2026-06-01T10:00:00Z",
) -> MagicMock:
    c = MagicMock()
    c.id = contact_id
    c.properties = {
        "email": email,
        "firstname": firstname,
        "lastname": lastname,
        "company": company,
    }
    c.created_at = "2026-01-01T00:00:00Z"
    c.updated_at = updated_at
    return c


def _fake_page(
    contacts: list[Any],
    next_after: str | None = None,
) -> MagicMock:
    page = MagicMock()
    page.results = contacts
    if next_after:
        page.paging = MagicMock()
        page.paging.next = MagicMock()
        page.paging.next.after = next_after
    else:
        page.paging = None
    return page


# ── Tests ───────────────────────────────────────────────────────────────────


@patch("app.connectors.hubspot_connector.settings.hubspot_access_token", "test-token")
class TestHubspotFetchFull:
    @patch("hubspot.Client.create")
    async def test_full_fetch_returns_records(
        self, mock_create: MagicMock
    ) -> None:
        client = MagicMock()
        mock_create.return_value = client
        client.crm.contacts.basic_api.get_page.side_effect = [
            _fake_page(
                [_fake_contact("001", email="alice@example.com", firstname="Alice")],
                next_after="abc",
            ),
            _fake_page(
                [_fake_contact("002", email="bob@example.com", firstname="Bob")],
            ),
        ]

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        result = await connector.fetch_full()

        assert len(result.records) == 2
        assert result.records[0]["id"] == "001"
        assert result.records[0]["email"] == "alice@example.com"
        assert result.records[1]["id"] == "002"
        assert result.records[1]["email"] == "bob@example.com"
        assert result.cursor is not None

    @patch("hubspot.Client.create")
    async def test_full_fetch_empty(self, mock_create: MagicMock) -> None:
        client = MagicMock()
        mock_create.return_value = client
        client.crm.contacts.basic_api.get_page.return_value = _fake_page([])

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        result = await connector.fetch_full()

        assert result.records == []
        assert result.cursor is not None

    @patch("hubspot.Client.create")
    async def test_full_fetch_api_error(self, mock_create: MagicMock) -> None:
        from hubspot.crm.contacts import ApiException

        client = MagicMock()
        mock_create.return_value = client
        error = ApiException(http_resp=MagicMock(status=500))
        client.crm.contacts.basic_api.get_page.side_effect = error

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        with pytest.raises(SourceUnavailableError, match="HubSpot source unavailable"):
            await connector.fetch_full()

    @patch("hubspot.Client.create")
    async def test_auth_error(self, mock_create: MagicMock) -> None:
        from hubspot.crm.contacts import ApiException

        client = MagicMock()
        mock_create.return_value = client
        error = ApiException(http_resp=MagicMock(status=401))
        client.crm.contacts.basic_api.get_page.side_effect = error

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        with pytest.raises(SourceUnavailableError, match="HubSpot authentication failed"):
            await connector.fetch_full()


@patch("app.connectors.hubspot_connector.settings.hubspot_access_token", "test-token")
class TestHubspotFetchIncremental:
    @patch("hubspot.Client.create")
    async def test_incremental_returns_modified_records(
        self, mock_create: MagicMock
    ) -> None:
        client = MagicMock()
        mock_create.return_value = client
        client.crm.contacts.search_api.do_search.return_value = _fake_page(
            [_fake_contact("003", email="carol@example.com")]
        )

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        result = await connector.fetch_incremental("1718000000")

        assert len(result.records) == 1
        assert result.records[0]["id"] == "003"
        assert result.cursor is not None

    @patch("hubspot.Client.create")
    async def test_incremental_without_cursor_falls_back_to_full(
        self, mock_create: MagicMock
    ) -> None:
        client = MagicMock()
        mock_create.return_value = client
        client.crm.contacts.basic_api.get_page.return_value = _fake_page(
            [_fake_contact("001")]
        )

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        result = await connector.fetch_incremental(None)

        assert len(result.records) == 1
        # Should use get_page (full fetch), not search
        client.crm.contacts.basic_api.get_page.assert_called_once()

    @patch("hubspot.Client.create")
    async def test_invalid_cursor_raises_expired(
        self, mock_create: MagicMock
    ) -> None:
        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        with pytest.raises(CursorExpiredError):
            await connector.fetch_incremental("not-a-number")

    @patch("hubspot.Client.create")
    async def test_incremental_api_error(self, mock_create: MagicMock) -> None:
        from hubspot.crm.contacts import ApiException

        client = MagicMock()
        mock_create.return_value = client
        error = ApiException(http_resp=MagicMock(status=429))
        client.crm.contacts.search_api.do_search.side_effect = error

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        with pytest.raises(SourceUnavailableError):
            await connector.fetch_incremental("1718000000")

    @patch("hubspot.Client.create")
    async def test_gone_status_raises_cursor_expired(
        self, mock_create: MagicMock
    ) -> None:
        from hubspot.crm.contacts import ApiException

        client = MagicMock()
        mock_create.return_value = client
        error = ApiException(http_resp=MagicMock(status=410))
        client.crm.contacts.search_api.do_search.side_effect = error

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        with pytest.raises(CursorExpiredError):
            await connector.fetch_incremental("1718000000")


class TestNormalization:
    async def test_contact_normalizes_through_normalizer(self) -> None:
        """Verify HubSpot contact shape works with the shared normalizer."""
        contact = _fake_contact(
            "001",
            email="alice@example.com",
            firstname="Alice",
            lastname="Smith",
            company="Acme Corp",
        )

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        record = connector._to_record(contact)

        normalized = normalize_contact(record, "hubspot_crm")
        assert normalized["source_record_id"] == "001"
        assert normalized["email"] == "alice@example.com"
        assert normalized["name"] == "Alice Smith"
        assert normalized["company"] == "Acme Corp"

    async def test_contact_missing_email(self) -> None:
        contact = _fake_contact("002", email=None)

        from app.connectors.hubspot_connector import HubspotCrmConnector

        connector = HubspotCrmConnector()
        record = connector._to_record(contact)

        normalized = normalize_contact(record, "hubspot_crm")
        assert normalized["source_record_id"] == "002"
        assert normalized["email"] is None
