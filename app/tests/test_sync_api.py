from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.demo import router as demo_router
from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.sync import router as sync_router
from app.core.database import get_session


def _build_app(include_demo: bool = True) -> FastAPI:
    app = FastAPI(title="Test App")
    app.include_router(health_router)
    app.include_router(sync_router)
    if include_demo:
        app.include_router(demo_router)
    app.include_router(metrics_router)
    return app


@pytest.fixture
async def client(async_engine: Any) -> AsyncGenerator[TestClient, None]:
    from app.connectors.registry import reset_simulations

    reset_simulations()
    app = _build_app(include_demo=True)
    factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)


@pytest.fixture
async def prod_client(async_engine: Any) -> AsyncGenerator[TestClient, None]:
    from app.connectors.registry import reset_simulations

    reset_simulations()
    app = _build_app(include_demo=False)
    factory = async_sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)


class TestSyncEndpoints:
    def test_post_sync_returns_success(self, client: TestClient) -> None:
        resp = client.post("/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert "sync_run_id" in data
        assert data["status"] == "success"
        assert len(data["sources"]) == 3

    def test_post_sync_returns_per_source_results(self, client: TestClient) -> None:
        resp = client.post("/sync")
        assert resp.status_code == 200
        data = resp.json()
        for src in data["sources"]:
            assert src["status"] == "success"
            assert src["sync_mode"] == "full"
            assert src["records_seen"] > 0

    def test_post_sync_idempotent(self, client: TestClient) -> None:
        client.post("/sync")
        # After first sync, cursor is saved. Second sync runs incremental.
        resp2 = client.post("/sync")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["status"] == "success"
        for src in data2["sources"]:
            assert src["sync_mode"] in ("incremental",)

    async def test_post_sync_idempotent_row_counts(
        self, client: TestClient, async_session: AsyncSession
    ) -> None:
        """End-to-end: re-running sync with same data must not increase DB row counts."""
        from app.models.contact import Contact
        from app.models.event import Event
        from app.models.external_record import ExternalRecord
        from app.models.transaction import Transaction
        from app.services.repository import count_rows

        # First sync: full fetch lands initial data
        client.post("/sync")
        # Second sync: incremental fetch adds 1 new record per source
        client.post("/sync")

        contacts = await count_rows(async_session, Contact)
        events = await count_rows(async_session, Event)
        transactions = await count_rows(async_session, Transaction)
        externals = await count_rows(async_session, ExternalRecord)

        # Third sync: same data already in DB, upsert must be no-op
        client.post("/sync")

        assert await count_rows(async_session, Contact) == contacts
        assert await count_rows(async_session, Event) == events
        assert await count_rows(async_session, Transaction) == transactions
        assert await count_rows(async_session, ExternalRecord) == externals

    def test_post_sync_by_source(self, client: TestClient) -> None:
        resp = client.post("/sync/mock_crm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["source_name"] == "mock_crm"

    def test_post_sync_unknown_source_returns_404(self, client: TestClient) -> None:
        resp = client.post("/sync/unknown_source")
        assert resp.status_code == 404
        assert "unknown_source" in resp.json()["detail"]

    def test_get_sync_run(self, client: TestClient) -> None:
        create = client.post("/sync")
        run_id = create.json()["sync_run_id"]

        resp = client.get(f"/sync-runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == run_id
        assert data["status"] == "success"
        assert len(data["sources"]) == 3

    def test_get_sync_run_not_found(self, client: TestClient) -> None:
        resp = client.get("/sync-runs/99999")
        assert resp.status_code == 404

    def test_get_sync_run_shows_source_details(self, client: TestClient) -> None:
        create = client.post("/sync/mock_crm")
        run_id = create.json()["sync_run_id"]

        resp = client.get(f"/sync-runs/{run_id}")
        data = resp.json()
        assert len(data["sources"]) == 1
        src = data["sources"][0]
        assert src["source_name"] == "mock_crm"
        assert src["records_upserted"] == 3
        assert src["records_rejected"] == 0


class TestDemoEndpoints:
    def test_simulate_cursor_expired(self, client: TestClient) -> None:
        resp = client.post("/demo/simulate-cursor-expired/mock_crm")
        assert resp.status_code == 200
        assert "cursor_expired" in resp.json()["message"]

    def test_simulate_source_failure(self, client: TestClient) -> None:
        resp = client.post("/demo/simulate-source-failure/mock_crm")
        assert resp.status_code == 200
        assert "source_unavailable" in resp.json()["message"]

    def test_simulate_unknown_source(self, client: TestClient) -> None:
        resp = client.post("/demo/simulate-cursor-expired/unknown")
        assert resp.status_code == 404

    def test_reset_simulations(self, client: TestClient) -> None:
        client.post("/demo/simulate-cursor-expired/mock_crm")
        resp = client.post("/demo/reset-simulations")
        assert resp.status_code == 200

    def test_cursor_expired_simulation_affects_sync(
        self, client: TestClient
    ) -> None:
        # First sync to create cursor
        client.post("/sync")

        # Activate simulation
        client.post("/demo/simulate-cursor-expired/mock_crm")

        # Second sync — mock_crm should fall back to full fetch
        resp = client.post("/sync/mock_crm")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["sources"][0]["sync_mode"] == "full_after_cursor_expired"

    def test_source_failure_simulation_affects_sync(
        self, client: TestClient
    ) -> None:
        client.post("/demo/simulate-source-failure/mock_crm")
        resp = client.post("/sync")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "partial_success"
        failed_sources = [
            s for s in data["sources"] if s["source_name"] == "mock_crm"
        ]
        assert len(failed_sources) == 1
        assert failed_sources[0]["status"] == "failed"


class TestDemoSeed:
    def test_seed_returns_summary(self, client: TestClient) -> None:
        resp = client.post("/demo/seed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contacts"] == 3
        assert data["events"] == 2
        assert data["transactions"] == 8

    async def test_seed_is_idempotent(
        self, client: TestClient, async_session: AsyncSession
    ) -> None:
        from app.models.contact import Contact
        from app.models.event import Event
        from app.models.transaction import Transaction
        from app.services.repository import count_rows

        client.post("/demo/seed")
        resp1 = client.post("/demo/seed")
        assert resp1.status_code == 200

        contacts = await count_rows(async_session, Contact)
        events = await count_rows(async_session, Event)
        transactions = await count_rows(async_session, Transaction)

        assert contacts == 3
        assert events == 2
        assert transactions == 8

    def test_seed_data_queryable_via_sync_run(self, client: TestClient) -> None:
        client.post("/demo/seed")
        resp = client.post("/sync")
        assert resp.status_code == 200
        # Sync should read the seeded cursor and do incremental or full
        # At minimum, the sync should succeed
        assert resp.json()["status"] in ("success", "partial_success")

    def test_seed_then_sync_shows_correct_revenue(self, client: TestClient) -> None:
        client.post("/demo/seed")
        client.post("/sync")
        resp = client.get(
            "/metrics/revenue/summary?start=2026-06-01&end=2026-06-30"
        )
        assert resp.status_code == 200
        data = resp.json()
        # Mock collected: pay-001 (2999) + pay-002 (4999)
        # Seed collected: 4 transactions (2999+4999+1599+2000)
        mock_collected = 2999 + 4999
        seed_collected = 2999 + 4999 + 1599 + 2000
        assert data["items"][0]["total_amount_minor"] == mock_collected + seed_collected


class TestDemoRoutesDisabledInProduction:
    def test_production_demo_seed_unavailable(self, prod_client: TestClient) -> None:
        resp = prod_client.post("/demo/seed")
        assert resp.status_code == 404

    def test_production_demo_simulate_source_failure_unavailable(
        self, prod_client: TestClient
    ) -> None:
        resp = prod_client.post("/demo/simulate-source-failure/mock_crm")
        assert resp.status_code == 404

    def test_production_health_still_works(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestMainAppDefaultNoDemo:
    """Verifies the actual app.main app has demo routes disabled by default."""

    def test_main_app_demo_returns_404(self) -> None:
        from app.main import app as prod_app

        client = TestClient(prod_app)
        resp = client.post("/demo/seed")
        assert resp.status_code == 404

    def test_main_app_health_works(self) -> None:
        from app.main import app as prod_app

        client = TestClient(prod_app)
        resp = client.get("/health")
        assert resp.status_code == 200
