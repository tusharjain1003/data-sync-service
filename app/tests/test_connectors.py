"""Tests for the connector interface and mock connectors."""

import pytest

from app.connectors import (
    CursorExpiredError,
    MockCalendarConnector,
    MockCrmConnector,
    MockPaymentsConnector,
    SourceUnavailableError,
    SyncConnector,
)


def test_crm_is_sync_connector() -> None:
    assert isinstance(MockCrmConnector(), SyncConnector)


def test_calendar_is_sync_connector() -> None:
    assert isinstance(MockCalendarConnector(), SyncConnector)


def test_payments_is_sync_connector() -> None:
    assert isinstance(MockPaymentsConnector(), SyncConnector)


@pytest.mark.asyncio
async def test_crm_full_fetch_returns_records() -> None:
    connector = MockCrmConnector()
    result = await connector.fetch_full()
    assert len(result.records) == 3
    assert result.cursor is not None
    assert result.cursor.startswith("full_cursor_")


@pytest.mark.asyncio
async def test_calendar_full_fetch_returns_records() -> None:
    connector = MockCalendarConnector()
    result = await connector.fetch_full()
    assert len(result.records) == 2
    assert result.cursor is not None


@pytest.mark.asyncio
async def test_payments_full_fetch_returns_records() -> None:
    connector = MockPaymentsConnector()
    result = await connector.fetch_full()
    assert len(result.records) == 3
    assert result.cursor is not None


@pytest.mark.asyncio
async def test_incremental_without_cursor_falls_back_to_full() -> None:
    connector = MockCrmConnector()
    result = await connector.fetch_incremental(None)
    assert len(result.records) == 3


@pytest.mark.asyncio
async def test_incremental_with_cursor_returns_new_records() -> None:
    connector = MockCrmConnector()
    result = await connector.fetch_incremental("some-cursor")
    assert len(result.records) == 1
    assert result.records[0]["id"] == "crm-004"
    assert result.cursor is not None
    assert result.cursor.startswith("incr_cursor_")


@pytest.mark.asyncio
async def test_cursor_expired_error_can_be_raised() -> None:
    connector = MockCrmConnector()
    connector.simulate = "cursor_expired"
    with pytest.raises(CursorExpiredError, match="cursor expired"):
        await connector.fetch_incremental("some-cursor")


@pytest.mark.asyncio
async def test_cursor_expired_error_raised_on_incremental() -> None:
    connector = MockCalendarConnector()
    connector.simulate = "cursor_expired"
    with pytest.raises(CursorExpiredError, match="cursor expired"):
        await connector.fetch_incremental("some-cursor")


@pytest.mark.asyncio
async def test_source_unavailable_error_can_be_raised() -> None:
    connector = MockPaymentsConnector()
    connector.simulate = "source_unavailable"
    with pytest.raises(SourceUnavailableError, match="source unavailable"):
        await connector.fetch_full()


@pytest.mark.asyncio
async def test_source_unavailable_error_on_incremental() -> None:
    connector = MockCrmConnector()
    connector.simulate = "source_unavailable"
    with pytest.raises(SourceUnavailableError, match="source unavailable"):
        await connector.fetch_incremental("cursor")


@pytest.mark.asyncio
async def test_crm_source_name_and_type() -> None:
    connector = MockCrmConnector()
    assert connector.source_name == "mock_crm"
    assert connector.source_type == "crm"


@pytest.mark.asyncio
async def test_calendar_source_name_and_type() -> None:
    connector = MockCalendarConnector()
    assert connector.source_name == "mock_calendar"
    assert connector.source_type == "calendar"


@pytest.mark.asyncio
async def test_payments_source_name_and_type() -> None:
    connector = MockPaymentsConnector()
    assert connector.source_name == "mock_payments"
    assert connector.source_type == "payments"
