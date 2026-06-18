"""Tests for the connector registry and source selection."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.connectors.base import SyncConnector
from app.connectors.errors import SourceUnavailableError
from app.connectors.registry import (
    _get_active_sources,
    get_all_connectors,
    get_connector,
    list_active_sources,
    list_known_sources,
    reset_simulations,
    set_simulation,
)


class TestActiveSources:
    def test_mock_mode_returns_only_mock_sources(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            sources = list_active_sources()
            assert sorted(sources) == [
                "mock_calendar",
                "mock_crm",
                "mock_payments",
            ]

    def test_mock_mode_get_all_returns_mock_connectors(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            connectors = get_all_connectors()
            names = [c.source_name for c in connectors]
            assert sorted(names) == [
                "mock_calendar",
                "mock_crm",
                "mock_payments",
            ]

    def test_mock_mode_get_all_connectors_are_sync_connector(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            for c in get_all_connectors():
                assert isinstance(c, SyncConnector)

    def test_real_mode_returns_only_real_sources(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            sources = list_active_sources()
            assert sorted(sources) == [
                "google_calendar",
                "hubspot_crm",
                "stripe",
            ]

    def test_real_mode_get_all_returns_real_connectors(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            connectors = get_all_connectors()
            names = [c.source_name for c in connectors]
            assert sorted(names) == [
                "google_calendar",
                "hubspot_crm",
                "stripe",
            ]

    def test_real_mode_get_all_connectors_are_sync_connector(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            for c in get_all_connectors():
                assert isinstance(c, SyncConnector)

    def test_real_mode_does_not_include_mock_sources(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            sources = list_active_sources()
            assert "mock_crm" not in sources
            assert "mock_calendar" not in sources
            assert "mock_payments" not in sources

    def test_real_mode_missing_credentials_raises(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ):
            with pytest.raises(
                SourceUnavailableError, match="HUBSPOT_ACCESS_TOKEN"
            ):
                list_active_sources()

    def test_real_mode_get_connector_rejects_mock_sources(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            with pytest.raises(ValueError, match="Unknown source"):
                get_connector("mock_crm")

    def test_mock_mode_get_connector_rejects_real_sources(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            with pytest.raises(ValueError, match="Unknown source"):
                get_connector("hubspot_crm")


class TestKnownSources:
    def test_list_known_sources_includes_all_sources(self) -> None:
        sources = list_known_sources()
        assert "mock_crm" in sources
        assert "mock_calendar" in sources
        assert "mock_payments" in sources
        assert "hubspot_crm" in sources
        assert "google_calendar" in sources
        assert "stripe" in sources
        assert len(sources) >= 6

    def test_get_connector_returns_correct_types(self) -> None:
        from app.connectors.mock_crm import MockCrmConnector

        connector = get_connector("mock_crm")
        assert isinstance(connector, MockCrmConnector)
        assert connector.source_name == "mock_crm"

    def test_get_connector_unknown_source_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown source"):
            get_connector("nonexistent_source")


class TestSimulation:
    def test_set_simulation_updates_state(self) -> None:
        reset_simulations()
        set_simulation("mock_crm", "cursor_expired")
        connector = get_connector("mock_crm")
        assert connector.simulate == "cursor_expired"  # type: ignore[attr-defined]

    def test_set_simulation_unknown_source_raises_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown source"):
            set_simulation("unknown", "cursor_expired")

    def test_reset_simulations_clears_state(self) -> None:
        set_simulation("mock_crm", "cursor_expired")
        reset_simulations()
        connector = get_connector("mock_crm")
        assert connector.simulate == "normal"  # type: ignore[attr-defined]


class TestGetActiveSourcesPrivate:
    def test_active_sources_mock_mode(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            active = _get_active_sources()
            assert "mock_crm" in active
            assert "hubspot_crm" not in active

    def test_active_sources_real_mode(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ):
            active = _get_active_sources()
            assert "hubspot_crm" in active
            assert "mock_crm" not in active


class TestGoogleCalendarIdValidation:
    def test_real_mode_missing_google_calendar_id_fails(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", ""
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            with pytest.raises(
                SourceUnavailableError, match="GOOGLE_CALENDAR_ID"
            ):
                list_active_sources()

    def test_real_mode_all_google_env_vars_present_registers_connector(
        self,
    ) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            sources = list_active_sources()
            assert "google_calendar" in sources

    def test_mock_mode_does_not_require_google_calendar_id(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", ""
        ):
            sources = list_active_sources()
            assert "mock_calendar" in sources

    def test_real_mode_get_connector_google_calendar_missing_calendar_id_fails(
        self,
    ) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", ""
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            with pytest.raises(
                SourceUnavailableError, match="GOOGLE_CALENDAR_ID"
            ):
                get_connector("google_calendar")

    def test_real_mode_get_connector_google_calendar_all_credentials_present(
        self,
    ) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            connector = get_connector("google_calendar")
            assert connector.source_name == "google_calendar"

    def test_real_mode_get_connector_fails_on_missing_hubspot_token(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", False
        ), patch(
            "app.connectors.registry.settings.hubspot_access_token", ""
        ), patch(
            "app.connectors.registry.settings.google_client_id", "test"
        ), patch(
            "app.connectors.registry.settings.google_client_secret", "test"
        ), patch(
            "app.connectors.registry.settings.google_refresh_token", "test"
        ), patch(
            "app.connectors.registry.settings.google_calendar_id", "test"
        ), patch(
            "app.connectors.registry.settings.stripe_secret_key", "test"
        ):
            with pytest.raises(
                SourceUnavailableError, match="HUBSPOT_ACCESS_TOKEN"
            ):
                get_connector("hubspot_crm")

    def test_mock_mode_get_connector_does_not_require_any_credentials(self) -> None:
        with patch(
            "app.connectors.registry.settings.use_mock_connectors", True
        ):
            connector = get_connector("mock_crm")
            assert connector.source_name == "mock_crm"
