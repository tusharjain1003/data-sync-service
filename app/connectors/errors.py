class ConnectorError(Exception):
    """Base error for all connector failures."""


class CursorExpiredError(ConnectorError):
    """Raised when the incremental cursor is stale, expired, or rejected by the source."""


class SourceUnavailableError(ConnectorError):
    """Raised when the source API is unreachable or returns a server error."""


class SourcePayloadError(ConnectorError):
    """Raised when an individual record from the source is malformed or invalid."""
