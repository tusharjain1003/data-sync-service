"""Connector registry — creates connectors and manages simulation overrides."""

from app.connectors.base import SyncConnector
from app.connectors.errors import SourceUnavailableError
from app.connectors.google_calendar_connector import GoogleCalendarConnector
from app.connectors.hubspot_connector import HubspotCrmConnector
from app.connectors.mock_calendar import MockCalendarConnector
from app.connectors.mock_crm import MockCrmConnector
from app.connectors.mock_payments import MockPaymentsConnector
from app.connectors.stripe_connector import StripeConnector
from app.core.config import settings

_SIMULATION_STATE: dict[str, str] = {}

_MOCK_SOURCES: dict[str, type[SyncConnector]] = {
    "mock_crm": MockCrmConnector,
    "mock_calendar": MockCalendarConnector,
    "mock_payments": MockPaymentsConnector,
}

_REAL_SOURCES: dict[str, type[SyncConnector]] = {
    "hubspot_crm": HubspotCrmConnector,
    "google_calendar": GoogleCalendarConnector,
    "stripe": StripeConnector,
}

_ALL_SOURCES: dict[str, type[SyncConnector]] = {**_MOCK_SOURCES, **_REAL_SOURCES}


def _get_active_sources() -> dict[str, type[SyncConnector]]:
    if settings.use_mock_connectors:
        return dict(_MOCK_SOURCES)
    return dict(_REAL_SOURCES)


def _validate_production_config() -> None:
    """Check that all real connectors have their required credentials configured."""
    if settings.use_mock_connectors:
        return
    errors: list[str] = []
    if not settings.hubspot_access_token:
        errors.append("HUBSPOT_ACCESS_TOKEN is not configured")
    if (
        not settings.google_client_id
        or not settings.google_client_secret
        or not settings.google_refresh_token
        or not settings.google_calendar_id
    ):
        errors.append(
            "GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, "
            "GOOGLE_REFRESH_TOKEN, and GOOGLE_CALENDAR_ID must be configured"
        )
    if not settings.stripe_secret_key:
        errors.append("STRIPE_SECRET_KEY is not configured")
    if errors:
        raise SourceUnavailableError(
            "Real connectors require credentials: " + "; ".join(errors)
        )


def get_connector(source_name: str) -> SyncConnector:
    active = _get_active_sources()
    cls = active.get(source_name)
    if cls is None:
        raise ValueError(f"Unknown source: {source_name}")
    connector = cls()
    if source_name in _SIMULATION_STATE:
        connector.simulate = _SIMULATION_STATE[source_name]  # type: ignore[attr-defined]
    return connector


def get_all_connectors() -> list[SyncConnector]:
    _validate_production_config()
    return [get_connector(name) for name in _get_active_sources()]


def list_known_sources() -> list[str]:
    return list(_ALL_SOURCES)


def list_active_sources() -> list[str]:
    if not settings.use_mock_connectors:
        _validate_production_config()
    return list(_get_active_sources())


def set_simulation(source_name: str, mode: str) -> None:
    if source_name not in _ALL_SOURCES:
        raise ValueError(f"Unknown source: {source_name}")
    _SIMULATION_STATE[source_name] = mode


def reset_simulations() -> None:
    _SIMULATION_STATE.clear()
