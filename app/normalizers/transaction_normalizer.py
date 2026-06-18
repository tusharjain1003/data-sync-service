from datetime import datetime
from typing import Any

from app.connectors.errors import SourcePayloadError
from app.normalizers.status_mapper import normalize_status


def normalize_transaction(
    raw: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    """Normalize a raw payment record into a canonical transaction dict.

    Required fields: id, amount, currency, status
    Optional: customer_email, created, updated_at
    """
    source_record_id = raw.get("id")
    if not source_record_id:
        raise SourcePayloadError("Transaction record missing 'id'")

    amount = raw.get("amount")
    if amount is None or not isinstance(amount, int) or amount < 0:
        raise SourcePayloadError(
            f"Transaction record missing or invalid 'amount': {amount!r}"
        )

    currency = raw.get("currency")
    if not currency or not isinstance(currency, str):
        raise SourcePayloadError(
            f"Transaction record missing or invalid 'currency': {currency!r}"
        )

    source_status = raw.get("status")
    if not source_status or not isinstance(source_status, str):
        raise SourcePayloadError(
            f"Transaction record missing or invalid 'status': {source_status!r}"
        )

    occurred_at: datetime | None = None
    created_str = raw.get("created")
    if created_str:
        try:
            occurred_at = datetime.fromisoformat(
                str(created_str).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            occurred_at = None

    updated_str = raw.get("updated_at")
    source_updated_at: datetime | None = None
    if updated_str:
        try:
            source_updated_at = datetime.fromisoformat(
                str(updated_str).replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            source_updated_at = None

    return {
        "source_name": source_name,
        "source_record_id": str(source_record_id),
        "customer_email": raw.get("customer_email"),
        "amount_minor": amount,
        "currency": str(currency).lower(),
        "canonical_status": normalize_status(source_status),
        "source_status": source_status,
        "occurred_at": occurred_at,
        "source_updated_at": source_updated_at,
    }
