"""Mocked tests for the Stripe connector.

These tests mock stripe.PaymentIntent.list so no real Stripe API key is needed.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from stripe import StripeError

from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.connectors.stripe_connector import StripeConnector


def _fake_pi(
    pi_id: str,
    amount: int = 2999,
    currency: str = "usd",
    status: str = "succeeded",
    created: int = 1718000000,
    receipt_email: str | None = "test@example.com",
) -> MagicMock:
    """Create a fake PaymentIntent-like object."""
    pi = MagicMock()
    pi.id = pi_id
    pi.amount = amount
    pi.currency = currency
    pi.status = status
    pi.created = created
    pi.receipt_email = receipt_email
    return pi


def _fake_list_response(items: list[Any]) -> MagicMock:
    """Create a fake PaymentIntent list response that supports auto_paging_iter."""
    mock_list = MagicMock()
    mock_list.auto_paging_iter.return_value = iter(items)
    return mock_list


# ── Tests ───────────────────────────────────────────────────────────────────


class TestStripeFetchFull:
    @patch("stripe.PaymentIntent.list")
    async def test_full_fetch_returns_records(
        self, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = _fake_list_response([
            _fake_pi("pi_001", amount=2999, status="succeeded"),
            _fake_pi("pi_002", amount=4999, status="succeeded"),
            _fake_pi("pi_003", amount=999, status="pending"),
        ])

        connector = StripeConnector()
        result = await connector.fetch_full()

        assert len(result.records) == 3
        assert result.cursor is not None
        # Verify record shape matches the normalizer's expected input
        assert result.records[0]["id"] == "pi_001"
        assert result.records[0]["amount"] == 2999
        assert result.records[0]["status"] == "succeeded"

    @patch("stripe.PaymentIntent.list")
    async def test_full_fetch_empty(self, mock_list: MagicMock) -> None:
        mock_list.return_value = _fake_list_response([])

        connector = StripeConnector()
        result = await connector.fetch_full()

        assert result.records == []
        assert result.cursor is not None

    @patch("stripe.PaymentIntent.list")
    async def test_full_fetch_stripe_error(
        self, mock_list: MagicMock
    ) -> None:
        error = StripeError("API error")
        error.http_status = 500
        mock_list.side_effect = error

        connector = StripeConnector()
        with pytest.raises(SourceUnavailableError, match="Stripe source unavailable"):
            await connector.fetch_full()


class TestStripeFetchIncremental:
    @patch("stripe.PaymentIntent.list")
    async def test_incremental_returns_only_new_records(
        self, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = _fake_list_response([
            _fake_pi("pi_004", amount=1599, status="succeeded",
                     created=1718100000),
        ])

        connector = StripeConnector()
        result = await connector.fetch_incremental("1718000000")

        assert len(result.records) == 1
        assert result.records[0]["id"] == "pi_004"
        mock_list.assert_called_once_with(
            limit=100, created={"gte": 1718000000}
        )

    @patch("stripe.PaymentIntent.list")
    async def test_incremental_without_cursor_falls_back_to_full(
        self, mock_list: MagicMock
    ) -> None:
        mock_list.return_value = _fake_list_response([
            _fake_pi("pi_001", amount=2999, status="succeeded"),
        ])

        connector = StripeConnector()
        result = await connector.fetch_incremental(None)

        assert len(result.records) == 1
        # Full fetch doesn't pass created filter
        mock_list.assert_called_once_with(limit=100)

    async def test_invalid_cursor_raises_expired(self) -> None:
        connector = StripeConnector()
        with pytest.raises(CursorExpiredError, match="Stripe cursor is invalid"):
            await connector.fetch_incremental("not-a-number")

    @patch("stripe.PaymentIntent.list")
    async def test_incremental_stripe_error(
        self, mock_list: MagicMock
    ) -> None:
        error = StripeError("Rate limit exceeded")
        error.http_status = 429
        mock_list.side_effect = error

        connector = StripeConnector()
        with pytest.raises(SourceUnavailableError, match="Stripe source unavailable"):
            await connector.fetch_incremental("1718000000")

    @patch("stripe.PaymentIntent.list")
    async def test_auth_error(
        self, mock_list: MagicMock
    ) -> None:
        error = StripeError("Invalid API Key")
        error.http_status = 401
        mock_list.side_effect = error

        connector = StripeConnector()
        with pytest.raises(SourceUnavailableError, match="Stripe authentication failed"):
            await connector.fetch_full()


class TestStatusMapping:
    """Verify Stripe statuses map correctly through the normalizer."""

    async def test_stripe_statuses_map_via_normalizer(self) -> None:
        from app.normalizers.transaction_normalizer import normalize_transaction

        connector = StripeConnector()
        pi = _fake_pi("pi_001", amount=2999, status="succeeded")
        record = connector._to_record(pi)

        normalized = normalize_transaction(record, "stripe")
        assert normalized["canonical_status"] == "collected"
        assert normalized["source_status"] == "succeeded"
        assert normalized["amount_minor"] == 2999
        assert normalized["currency"] == "usd"

    async def test_pending_status_maps_correctly(self) -> None:
        from app.normalizers.transaction_normalizer import normalize_transaction

        connector = StripeConnector()
        pi = _fake_pi("pi_002", amount=999, status="processing")
        record = connector._to_record(pi)

        normalized = normalize_transaction(record, "stripe")
        assert normalized["canonical_status"] == "unknown"
        assert normalized["source_status"] == "processing"

    async def test_canceled_status_maps_correctly(self) -> None:
        from app.normalizers.transaction_normalizer import normalize_transaction

        connector = StripeConnector()
        pi = _fake_pi("pi_003", amount=5000, status="canceled")
        record = connector._to_record(pi)

        normalized = normalize_transaction(record, "stripe")
        assert normalized["canonical_status"] == "unknown"
        assert normalized["source_status"] == "canceled"
