from datetime import datetime
from typing import Any

from app.connectors.errors import SourcePayloadError


def normalize_event(
    raw: dict[str, Any],
    source_name: str,
) -> dict[str, Any]:
    """Normalize a raw calendar record into a canonical event dict.

    Required fields: id, summary
    Optional: start, end, attendees, updated_at
    """
    source_record_id = raw.get("id")
    if not source_record_id:
        raise SourcePayloadError("Event record missing 'id'")

    title = raw.get("summary", "").strip() or None
    if not title:
        raise SourcePayloadError("Event record missing 'summary'")

    starts_at: datetime | None = None
    start_str = raw.get("start")
    if start_str:
        try:
            starts_at = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            starts_at = None

    ends_at: datetime | None = None
    end_str = raw.get("end")
    if end_str:
        try:
            ends_at = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            ends_at = None

    raw_attendees: list[dict[str, Any]] = raw.get("attendees") or []
    attendee_emails: list[str] = []
    for att in raw_attendees:
        email = att.get("email")
        if email:
            attendee_emails.append(email)

    updated_str = raw.get("updated_at")
    source_updated_at: datetime | None = None
    if updated_str:
        try:
            source_updated_at = datetime.fromisoformat(str(updated_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            source_updated_at = None

    return {
        "source_name": source_name,
        "source_record_id": str(source_record_id),
        "title": title,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "attendee_emails": attendee_emails or None,
        "source_updated_at": source_updated_at,
    }
