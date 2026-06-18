"""Real Stripe connector — fetches PaymentIntents from Stripe test mode.

Requires STRIPE_SECRET_KEY to be configured in the environment.
"""

from datetime import UTC, datetime
from typing import Any

import stripe
from stripe import StripeError

from app.connectors.base import FetchResult, SyncConnector
from app.connectors.errors import CursorExpiredError, SourceUnavailableError
from app.core.config import settings


class StripeConnector(SyncConnector):
    """Connector that fetches PaymentIntent records from Stripe."""

    def __init__(self) -> None:
        stripe.api_key = settings.stripe_secret_key

    @property
    def source_name(self) -> str:
        return "stripe"

    @property
    def source_type(self) -> str:
        return "payments"

    @staticmethod
    def _to_record(pi: Any) -> dict[str, Any]:
        occurred = datetime.fromtimestamp(pi.created, tz=UTC) if pi.created else None
        updated = (
            datetime.fromtimestamp(pi.created, tz=UTC) if pi.created else None
        )

        return {
            "id": pi.id,
            "customer_email": getattr(pi, "receipt_email", None),
            "amount": pi.amount,
            "currency": pi.currency,
            "status": pi.status,
            "created": occurred.isoformat() if occurred else None,
            "updated_at": updated.isoformat() if updated else None,
        }

    async def fetch_full(self) -> FetchResult:
        try:
            payment_intents = _list_all_payment_intents()
        except StripeError as e:
            _raise_typed_error(e, "full fetch")

        records = [self._to_record(pi) for pi in payment_intents]
        cursor = str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=cursor)

    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        if cursor is None:
            return await self.fetch_full()

        try:
            cursor_ts = int(cursor)
        except (ValueError, TypeError):
            raise CursorExpiredError(
                f"Stripe cursor is invalid: {cursor!r}"
            )

        try:
            payment_intents = _list_payment_intents_since(cursor_ts)
        except StripeError as e:
            _raise_typed_error(e, "incremental fetch")

        records = [self._to_record(pi) for pi in payment_intents]
        new_cursor = str(int(datetime.now(UTC).timestamp()))
        return FetchResult(records=records, cursor=new_cursor)


def _list_all_payment_intents() -> list[Any]:
    """Fetch all PaymentIntents."""
    result: list[Any] = []
    for pi in stripe.PaymentIntent.list(limit=100).auto_paging_iter():
        result.append(pi)
    return result


def _list_payment_intents_since(cursor_ts: int) -> list[Any]:
    """Fetch PaymentIntents created at or after the given timestamp."""
    result: list[Any] = []
    for pi in stripe.PaymentIntent.list(
        limit=100, created={"gte": cursor_ts}
    ).auto_paging_iter():
        result.append(pi)
    return result


def _raise_typed_error(error: StripeError, context: str) -> None:
    if hasattr(error, "http_status") and error.http_status is not None:
        status = error.http_status
        if status in (401, 403):
            raise SourceUnavailableError(
                f"Stripe authentication failed during {context}: {error}"
            )
        if status in (429,) or status >= 500:
            raise SourceUnavailableError(
                f"Stripe source unavailable during {context}: {error}"
            )
    if "expired" in str(error).lower() or "invalid" in str(error).lower():
        raise CursorExpiredError(
            f"Stripe cursor expired during {context}: {error}"
        )
    raise SourceUnavailableError(
        f"Stripe source unavailable during {context}: {error}"
    )
