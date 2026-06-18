"""Tests for the normalization layer and status mapper."""

from datetime import datetime

import pytest

from app.connectors.errors import SourcePayloadError
from app.normalizers import (
    map_status,
    normalize_contact,
    normalize_event,
    normalize_status,
    normalize_transaction,
)

# ── Status mapper ──────────────────────────────────────────────────────────


class TestStatusMapper:
    def test_paid_maps_to_collected(self) -> None:
        assert normalize_status("paid") == "collected"

    def test_succeeded_maps_to_collected(self) -> None:
        assert normalize_status("succeeded") == "collected"

    def test_completed_maps_to_collected(self) -> None:
        assert normalize_status("completed") == "collected"

    def test_pending_stays_pending(self) -> None:
        assert normalize_status("pending") == "pending"

    def test_failed_stays_failed(self) -> None:
        assert normalize_status("failed") == "failed"

    def test_voided_stays_voided(self) -> None:
        assert normalize_status("voided") == "voided"

    def test_refunded_stays_refunded(self) -> None:
        assert normalize_status("refunded") == "refunded"

    def test_unknown_status_maps_to_unknown(self) -> None:
        assert normalize_status("new_unexpected_status") == "unknown"

    def test_empty_string_maps_to_unknown(self) -> None:
        assert normalize_status("") == "unknown"

    def test_all_known_statuses_covered(self) -> None:
        mapping = map_status()
        assert "paid" in mapping
        assert "succeeded" in mapping
        assert "completed" in mapping
        assert "pending" in mapping
        assert "failed" in mapping
        assert "voided" in mapping
        assert "refunded" in mapping
        assert len(mapping) == 7


# ── Contact normalizer ─────────────────────────────────────────────────────


class TestContactNormalizer:
    CRM_RECORD = {
        "id": "crm-001",
        "email": "alice@example.com",
        "first_name": "Alice",
        "last_name": "Smith",
        "company": "Acme Corp",
        "updated_at": "2026-06-01T10:00:00Z",
    }

    def test_valid_contact(self) -> None:
        result = normalize_contact(self.CRM_RECORD, "mock_crm")
        assert result["source_name"] == "mock_crm"
        assert result["source_record_id"] == "crm-001"
        assert result["email"] == "alice@example.com"
        assert result["name"] == "Alice Smith"
        assert result["company"] == "Acme Corp"
        assert isinstance(result["source_updated_at"], datetime)

    def test_missing_id_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="missing 'id'"):
            normalize_contact({"email": "test@test.com"}, "mock_crm")

    def test_empty_id_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="missing 'id'"):
            normalize_contact({"id": "", "email": "test@test.com"}, "mock_crm")

    def test_missing_optional_fields(self) -> None:
        result = normalize_contact({"id": "crm-999"}, "mock_crm")
        assert result["email"] is None
        assert result["name"] is None
        assert result["company"] is None
        assert result["source_updated_at"] is None

    def test_name_combined_from_first_and_last(self) -> None:
        result = normalize_contact(
            {"id": "1", "first_name": "John", "last_name": "Doe"}, "mock_crm"
        )
        assert result["name"] == "John Doe"

    def test_partial_name(self) -> None:
        result = normalize_contact({"id": "1", "first_name": "John"}, "mock_crm")
        assert result["name"] == "John"

    def test_invalid_date_does_not_crash(self) -> None:
        result = normalize_contact(
            {"id": "1", "updated_at": "not-a-date"}, "mock_crm"
        )
        assert result["source_updated_at"] is None


# ── Event normalizer ───────────────────────────────────────────────────────


class TestEventNormalizer:
    CALENDAR_RECORD = {
        "id": "cal-001",
        "summary": "Team standup",
        "start": "2026-06-10T09:00:00Z",
        "end": "2026-06-10T09:30:00Z",
        "attendees": [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"},
        ],
        "updated_at": "2026-06-09T08:00:00Z",
    }

    def test_valid_event(self) -> None:
        result = normalize_event(self.CALENDAR_RECORD, "mock_calendar")
        assert result["source_name"] == "mock_calendar"
        assert result["source_record_id"] == "cal-001"
        assert result["title"] == "Team standup"
        assert isinstance(result["starts_at"], datetime)
        assert isinstance(result["ends_at"], datetime)
        assert result["attendee_emails"] == ["alice@example.com", "bob@example.com"]

    def test_missing_id_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="missing 'id'"):
            normalize_event({"summary": "Test"}, "mock_calendar")

    def test_missing_summary_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="missing 'summary'"):
            normalize_event({"id": "e-001", "summary": ""}, "mock_calendar")

    def test_no_attendees(self) -> None:
        result = normalize_event(
            {"id": "e-001", "summary": "Solo event"}, "mock_calendar"
        )
        assert result["attendee_emails"] is None

    def test_attendee_without_email_skipped(self) -> None:
        result = normalize_event(
            {
                "id": "e-001",
                "summary": "Test",
                "attendees": [{"name": "No Email"}, {}],
            },
            "mock_calendar",
        )
        assert result["attendee_emails"] is None

    def test_invalid_dates_do_not_crash(self) -> None:
        result = normalize_event(
            {
                "id": "e-001",
                "summary": "Test",
                "start": "bad-date",
                "end": "bad-date",
            },
            "mock_calendar",
        )
        assert result["starts_at"] is None
        assert result["ends_at"] is None


# ── Transaction normalizer ──────────────────────────────────────────────────


class TestTransactionNormalizer:
    PAYMENT_RECORD = {
        "id": "pay-001",
        "customer_email": "alice@example.com",
        "amount": 2999,
        "currency": "usd",
        "status": "succeeded",
        "created": "2026-06-05T10:00:00Z",
        "updated_at": "2026-06-05T10:00:00Z",
    }

    def test_valid_transaction(self) -> None:
        result = normalize_transaction(self.PAYMENT_RECORD, "mock_payments")
        assert result["source_name"] == "mock_payments"
        assert result["source_record_id"] == "pay-001"
        assert result["customer_email"] == "alice@example.com"
        assert result["amount_minor"] == 2999
        assert result["currency"] == "usd"
        assert result["canonical_status"] == "collected"
        assert result["source_status"] == "succeeded"
        assert isinstance(result["occurred_at"], datetime)

    def test_missing_id_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="missing 'id'"):
            normalize_transaction(
                {"amount": 100, "currency": "usd", "status": "paid"}, "mock_payments"
            )

    def test_missing_amount_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="amount"):
            normalize_transaction(
                {"id": "t-001", "currency": "usd", "status": "paid"}, "mock_payments"
            )

    def test_non_integer_amount_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="amount"):
            normalize_transaction(
                {"id": "t-001", "amount": 12.99, "currency": "usd", "status": "paid"},
                "mock_payments",
            )

    def test_negative_amount_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="amount"):
            normalize_transaction(
                {"id": "t-001", "amount": -1, "currency": "usd", "status": "paid"},
                "mock_payments",
            )

    def test_missing_currency_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="currency"):
            normalize_transaction(
                {"id": "t-001", "amount": 100, "status": "paid"}, "mock_payments"
            )

    def test_missing_status_raises_error(self) -> None:
        with pytest.raises(SourcePayloadError, match="status"):
            normalize_transaction(
                {"id": "t-001", "amount": 100, "currency": "usd"}, "mock_payments"
            )

    @pytest.mark.parametrize(
        "source_status,expected_canonical",
        [
            ("paid", "collected"),
            ("succeeded", "collected"),
            ("completed", "collected"),
            ("pending", "pending"),
            ("failed", "failed"),
            ("voided", "voided"),
            ("refunded", "refunded"),
            ("some_new_status", "unknown"),
        ],
    )
    def test_status_mapping_in_transaction(
        self, source_status: str, expected_canonical: str
    ) -> None:
        result = normalize_transaction(
            {
                "id": "t-001",
                "amount": 100,
                "currency": "usd",
                "status": source_status,
            },
            "mock_payments",
        )
        assert result["canonical_status"] == expected_canonical
        assert result["source_status"] == source_status

    def test_no_created_date(self) -> None:
        result = normalize_transaction(
            {"id": "t-001", "amount": 100, "currency": "usd", "status": "paid"},
            "mock_payments",
        )
        assert result["occurred_at"] is None
