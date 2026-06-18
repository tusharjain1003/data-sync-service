_STATUS_MAP: dict[str, str] = {
    "paid": "collected",
    "succeeded": "collected",
    "completed": "collected",
    "pending": "pending",
    "failed": "failed",
    "voided": "voided",
    "refunded": "refunded",
}


def normalize_status(source_status: str) -> str:
    """Map a source-specific status to a canonical status.

    Any status not in the known map is returned as 'unknown'.
    """
    return _STATUS_MAP.get(source_status, "unknown")


def map_status() -> dict[str, str]:
    """Return a copy of the canonical status mapping (for inspection/testing)."""
    return dict(_STATUS_MAP)
