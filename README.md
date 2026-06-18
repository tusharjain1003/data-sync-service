# Data Sync Service

Backend service for reliable multi-source data sync and revenue metrics correctness.

Built for a backend-focused assignment ([Problem Statement](./PROBLEM_STATEMENT.md)) that evaluates how data correctness and failure behavior are handled — no UI, no visuals.

---

## Problem Summary

**Sync pipeline**: Ingest records from 3 data sources (CRM, Calendar, Payments) each with different schemas into one normalized database. Handle cursor expiry (full backfill fallback), partial source failure (other sources continue), malformed records (reject individually), and idempotent writes (no duplicates on replay).

**Revenue metrics**: Compute collected revenue from transactions using one canonical definition and an allow-list of statuses. The summary and breakdown endpoints must always agree and must be structurally prevented from diverging.

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  API Layer  │────▶│ Orchestrator │────▶│  Connectors  │
│  (FastAPI)  │     │  run_sync()  │     │ (per-source) │
└──────┬──────┘     └──────┬───────┘     └──────┬───────┘
       │                   │                     │
       │            ┌──────▼───────┐     ┌──────▼───────┐
       │            │ Normalizers  │     │  Mock/Real   │
       │            │ (validate &  │     │ CRM/Calendar │
       │            │  map fields) │     │ /Payments    │
       │            └──────┬───────┘     └──────────────┘
       │                   │
       │            ┌──────▼───────┐
       ├───────────▶│ Repository   │
       │            │ (upserts,    │
       │            │  idempotent) │
       │            └──────┬───────┘
       │                   │
       │            ┌──────▼───────┐
       └───────────▶│  Metrics     │
                    │  (revenue)   │
                    └──────────────┘
```

- **Connectors** (`app/connectors/`): Per-source fetchers implementing `SyncConnector` ABC. Mock connectors for development; real connectors for HubSpot CRM, Google Calendar, and Stripe (test mode).
- **Orchestrator** (`app/services/sync_orchestrator.py`): Drives each source independently — cursor lookup, incremental fetch, fallback to full fetch on expiry, normalization, upsert, per-source result tracking.
- **Normalizers** (`app/normalizers/`): Map source-specific field shapes to canonical models. Validate required fields. Map transaction statuses to a canonical set.
- **Repository** (`app/services/repository.py`): Idempotent upserts via `ON CONFLICT DO UPDATE` on unique keys `(source_name, source_record_id)`.
- **Metrics** (`app/services/metrics.py`): Single `_build_base_query()` shared by summary and breakdown. Allow-list join on `collected_status_allowlist` — no exclusion logic.

---

## Data Model

8 tables managed via SQLAlchemy + Alembic migrations:

| Table | Key Columns | Idempotency Key |
|---|---|---|
| `source_connections` | cursor, last sync timestamps | `source_name` (PK) |
| `sync_runs` | start/end time, status, trigger | `id` (PK) |
| `sync_run_sources` | per-source outcome within a run | `(sync_run_id, source_name)` |
| `external_records` | raw source payload, payload_hash | `(source_name, source_record_id, record_type)` |
| `contacts` | email, name, company | `(source_name, source_record_id)` |
| `events` | title, start/end, attendee emails | `(source_name, source_record_id)` |
| `transactions` | amount_minor, currency, canonical_status | `(source_name, source_record_id)` |
| `collected_status_allowlist` | canonical_status → counts_as_collected | `canonical_status` (PK) |

All upserts use PostgreSQL `ON CONFLICT DO UPDATE`. Tests use SQLite with `@compiles` handlers that map JSONB → TEXT and PostgreSQL-specific upsert syntax to equivalent SQLite syntax.

---

## Local Setup

Prerequisites: Python 3.11+, PostgreSQL (optional for local dev — tests use SQLite).

```bash
# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies (including dev extras)
pip install -e ".[dev]"

# Copy env template — USE_MOCK_CONNECTORS=true by default
cp .env.example .env

# Run database migrations (requires PostgreSQL)
alembic upgrade head

# Start the server (SQLite development mode not supported for runtime — use PostgreSQL)
uvicorn app.main:app --reload
```

Without PostgreSQL, you can still run all tests and verify correctness via the demo seed endpoint (SQLite-backed test infrastructure).

---

## Environment Variables

See [`.env.example`](.env.example) for the full template. Never commit `.env` files.

| Variable | Default | Required for |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | Runtime |
| `APP_ENV` | `development` | Runtime |
| `USE_MOCK_CONNECTORS` | `true` | Local dev (set to `false` for real APIs) |
| `ENABLE_DEMO_ROUTES` | `false` | Set to `true` to expose `/demo/*` endpoints |
| `HUBSPOT_ACCESS_TOKEN` | — | HubSpot real connector |
| `GOOGLE_CLIENT_ID` | — | Google Calendar real connector |
| `GOOGLE_CLIENT_SECRET` | — | Google Calendar real connector |
| `GOOGLE_REFRESH_TOKEN` | — | Google Calendar real connector |
| `GOOGLE_CALENDAR_ID` | — | Google Calendar real connector |
| `STRIPE_SECRET_KEY` | — | Stripe real connector |

In mock mode (`USE_MOCK_CONNECTORS=true`), the app runs without any real credentials.

---

## Run Tests

```bash
# All tests (uses SQLite in-memory, no external DB needed)
pytest

# With coverage
pytest --cov=app
```

## Code Quality

```bash
ruff check .
mypy .
```

--- 

## Trigger Sync

```bash
# Sync all active sources
curl -X POST http://localhost:8000/sync

# Sync a single source by name
curl -X POST http://localhost:8000/sync/mock_crm

# Check a previous sync run
curl http://localhost:8000/sync-runs/<sync_run_id>
```

---

## Demo Endpoints

Demo routes (`/demo/*`) are **disabled by default** and only available when `ENABLE_DEMO_ROUTES=true` is set. In local development, set this flag to use the seed and simulation endpoints. In production, leave the flag unset or set to `false`.

## Demo Idempotency

Seed demo data, sync twice, and verify row counts stay the same on the second sync:

```bash
# 1. Seed demo records
curl -X POST http://localhost:8000/demo/seed

# 2. Sync to ingest them
curl -X POST http://localhost:8000/sync

# 3. Sync again — should not duplicate rows
curl -X POST http://localhost:8000/sync
```

The second sync reads the same records via incremental fetch. The upserts match on `(source_name, source_record_id)` and update in place rather than inserting new rows.

---

## Simulate Failure Modes

```bash
# Simulate cursor expiry — next sync will fall back to full backfill
curl -X POST http://localhost:8000/demo/simulate-cursor-expired/mock_crm

# Simulate source API failure — other sources still sync
curl -X POST http://localhost:8000/demo/simulate-source-failure/mock_calendar

# Reset all simulation states back to normal
curl -X POST http://localhost:8000/demo/reset-simulations

# Trigger sync with failures active
curl -X POST http://localhost:8000/sync
# Expect: partial_success, one source failed, two succeeded
```

---

## Revenue Metrics

```bash
# Revenue summary for a date range
curl "http://localhost:8000/metrics/revenue/summary?start=2026-06-01&end=2026-06-30"

# Daily revenue breakdown
curl "http://localhost:8000/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30&interval=day"
```

### How revenue drift prevention works

Both endpoints call the same `RevenueMetricsService` which delegates to a shared **private** `_build_base_query()` method. A structural guard test monkeypatches this method and verifies both endpoints use it. There is no second revenue calculation path in the codebase.

Revenue is computed by **joining** on `collected_status_allowlist WHERE counts_as_collected = true` — never by excluding statuses. New or unknown statuses are normalized to `unknown` and excluded from revenue by default unless explicitly allow-listed.

---

## Health Check

```bash
curl http://localhost:8000/health
# {"status": "ok", "app_env": "development", ...}
```

Requires no database or external credentials.

---

## Render Deployment

1. Push the repository to GitHub.
2. Create a **Web Service** on Render connected to your repo (or use Blueprint with `render.yaml`).
3. Add environment variables from `.env.example` in the Render dashboard. **Sync mode must be manual** for secrets — do not commit them to the repo.
4. Set `APP_ENV=production`, `USE_MOCK_CONNECTORS=false`, and `ENABLE_DEMO_ROUTES=false` in production.
5. Run migrations after deploy:
   ```bash
   # Via Render shell or a startup script
   alembic upgrade head
   ```
6. Verify with `GET /health`.

Build command: `pip install .`
Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## Tradeoffs and Known Limitations

| Tradeoff | Rationale |
|---|---|
| **Mock mode by default** | Local development without real credentials. Not a silent fallback — mock mode is explicit and each connector class is distinct. |
| **Mock connectors are not real connectors** | Real HubSpot, Google Calendar, and Stripe connectors exist alongside mocks. Switching to real mode requires credentials and explicit `USE_MOCK_CONNECTORS=false`. |
| **SQLite in tests, PostgreSQL in production** | SQLite runs each test in-memory (fast, isolated). `@compiles` handlers bridge JSONB and upsert syntax differences. Not suitable for production — PostgreSQL expected for runtime. |
| **One canonical status per transaction** | A transaction has one `canonical_status` — not a history of status transitions. This simplifies the model and matches the assignment scope. |
| **Single-currency assumption** | Revenue metrics assume all amounts are in the same currency. If multi-currency support is needed, the metric query should group or convert. |
| **No real webhook support** | The sync pipeline is pull-based (scheduled or manual trigger). Webhook ingestion would add at-least-once delivery with the same idempotency mechanism but is not implemented. |
| **`setuptools<70` pin** | Required because `hubspot-api-client>=9.0` imports `pkg_resources` internally. This will be obsolete once the client library drops the dependency. |
| **Google Calendar sync tokens are opaque** | The connector stores whatever `nextSyncToken` the API returns. If Google ever changes token format, the connector may need updating — the orchestration layer is agnostic. |
| **Rate limiting not implemented** | Real connectors do not throttle or retry on 429s. For a production service, exponential backoff and rate-limit awareness should be added. |

---

## Sources and References

- [FastAPI](https://fastapi.tiangolo.com/) — web framework
- [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) — ORM and async sessions
- [Alembic](https://alembic.sqlalchemy.org/) — database migrations
- [Pydantic v2](https://docs.pydantic.dev/latest/) — settings and record validation
- [pytest](https://docs.pytest.org/) — test framework
- [ruff](https://docs.astral.sh/ruff/) — Python linter
- [mypy](https://mypy-lang.org/) — static type checking
- [hubspot-api-client](https://github.com/HubSpot/hubspot-api-python) — HubSpot CRM SDK
- [google-api-python-client](https://github.com/googleapis/google-api-python-client) — Google Calendar API
- [stripe-python](https://github.com/stripe/stripe-python) — Stripe SDK
- [Render](https://render.com/docs) — deployment platform
- [Supabase](https://supabase.com/docs) — PostgreSQL hosting (recommended)
- [httpx](https://www.python-httpx.org/) — HTTP client (used by FastAPI TestClient)

---

## AI Usage

This project was built with assistance from Claude (Anthropic) as the coding agent. The workflow followed prompts defined in [PROMPTS.md](./PROMPTS.md), implemented one at a time with human review after each step. AI was used for:

- Generating code according to the implementation plan
- Writing tests for all behavior
- Documentation and README generation
- Refactoring and cleanup

All AI output was reviewed and validated by running the test suite, linter, and type checker after every prompt.
