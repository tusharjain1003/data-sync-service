from datetime import datetime
from typing import Any

from app.connectors.errors import SourcePayloadError


def normalize_contact(
    raw: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    """Normalize a raw CRM record into a canonical contact dict.

    Required fields: id
    Optional: email, first_name, last_name, company, updated_at
    """
    source_record_id = raw.get("id")
    if not source_record_id:
        raise SourcePayloadError("Contact record missing 'id'")

    first = raw.get("first_name", "")
    last = raw.get("last_name", "")
    name = f"{first} {last}".strip() or None

    updated_str = raw.get("updated_at")
    source_updated_at: datetime | None = None
    if updated_str:
        try:
            source_updated_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            source_updated_at = None

    return {
        "source_name": source_name,
        "source_record_id": str(source_record_id),
        "email": raw.get("email"),
        "name": name,
        "company": raw.get("company"),
        "source_updated_at": source_updated_at,
    }
