# Implementation Plan

## Goal

Build a backend-focused sync and metrics service that demonstrates data correctness under retry, cursor expiry, source failure, schema differences, and status vocabulary drift.

The solution will prioritize Problem Statement 1 and Problem Statement 2 together because they share the same core system: source ingestion into a normalized Postgres schema, followed by canonical metrics computed from that normalized data.

## Proposed Scope

- Backend API and job runner only; no UI.
- Real integrations where practical:
  - HubSpot developer account for CRM records.
  - Google Calendar API for event records.
  - One finance/test-mode provider for payments or invoices, preferably Stripe test mode because it has stable test data, webhooks, and clear status semantics.
  - Supabase Postgres for persistence.
- Render free-tier deployment.
- README with setup, tradeoffs, references, AI usage note, and demo commands.
- Short demo flow that can be run with curl or a job endpoint.

## Architecture

Use a small service-oriented backend:

- API layer:
  - Exposes sync trigger endpoints.
  - Exposes metrics endpoints.
  - Handles request validation and response formatting only.
- Source connector layer:
  - Encapsulates HubSpot, Google Calendar, and finance provider API calls.
  - Supports full fetch and incremental fetch.
  - Converts provider-specific errors into typed source errors.
- Sync orchestration layer:
  - Runs each source independently.
  - Falls back from incremental sync to full backfill when a cursor is stale or rejected.
  - Continues syncing healthy sources when another source fails or returns invalid data.
  - Records per-source sync results.
- Normalization layer:
  - Maps source-specific record shapes into canonical internal records.
  - Validates required fields before persistence.
- Persistence layer:
  - Uses Supabase Postgres.
  - Performs idempotent upserts keyed by source and source record id.
  - Stores sync cursors and run history.
- Metrics layer:
  - Computes collected revenue through one shared canonical query/service.
  - Uses an allow-list of statuses that count as collected.
  - Powers both summary and time-bucket endpoints from the same calculation path.

## Technology Choices

Preferred stack:

- Python with FastAPI for API endpoints and job triggers.
- SQLAlchemy or direct SQL with asyncpg/psycopg for database access.
- Pydantic for request, response, and normalized record validation.
- Pytest for unit and integration tests.
- Supabase Postgres as the hosted database.
- Render web service for deployment.

Rationale:

- FastAPI keeps the backend small and explicit.
- Pydantic is useful for validating heterogeneous external payloads.
- SQL upserts make idempotency straightforward and testable.
- Python has mature clients for Google APIs, HubSpot, and Stripe.

If the existing implementation later favors Node/TypeScript, the same design should be preserved with equivalent libraries.

## Data Model

Create a normalized schema with these core tables.

### `source_connections`

Tracks source-level state.

- `id`
- `source_name`
- `source_type`
- `cursor`
- `cursor_updated_at`
- `last_full_sync_at`
- `last_incremental_sync_at`
- `created_at`
- `updated_at`

### `sync_runs`

Tracks each sync attempt.

- `id`
- `started_at`
- `completed_at`
- `status`
- `trigger`
- `summary`

### `sync_run_sources`

Tracks source-specific outcomes within a run.

- `id`
- `sync_run_id`
- `source_name`
- `sync_mode`
- `status`
- `records_seen`
- `records_upserted`
- `records_rejected`
- `error_code`
- `error_message`
- `started_at`
- `completed_at`

### `external_records`

Stores raw or lightly wrapped source payloads for audit/debugging.

- `id`
- `source_name`
- `source_record_id`
- `record_type`
- `payload`
- `payload_hash`
- `source_updated_at`
- `ingested_at`

Unique constraint:

- `(source_name, source_record_id, record_type)`

### `contacts`

Normalized CRM-like records.

- `id`
- `source_name`
- `source_record_id`
- `email`
- `name`
- `company`
- `source_updated_at`
- `created_at`
- `updated_at`

Unique constraint:

- `(source_name, source_record_id)`

### `events`

Normalized calendar/event records.

- `id`
- `source_name`
- `source_record_id`
- `title`
- `starts_at`
- `ends_at`
- `attendee_emails`
- `source_updated_at`
- `created_at`
- `updated_at`

Unique constraint:

- `(source_name, source_record_id)`

### `transactions`

Normalized payments/invoices.

- `id`
- `source_name`
- `source_record_id`
- `customer_email`
- `amount_minor`
- `currency`
- `canonical_status`
- `source_status`
- `occurred_at`
- `source_updated_at`
- `created_at`
- `updated_at`

Unique constraint:

- `(source_name, source_record_id)`

### `collected_status_allowlist`

Defines exactly which canonical statuses count as revenue.

- `canonical_status`
- `counts_as_collected`
- `created_at`

Initial collected status:

- `collected`

Non-collected statuses such as `pending`, `failed`, `refunded`, `voided`, and `unknown` must not count unless explicitly allow-listed.

## Status Normalization

Create a single status mapper used during ingestion:

- Stripe-like `succeeded` -> `collected`
- Invoice-like `paid` -> `collected`
- Generic `completed` -> `collected`
- `pending` -> `pending`
- `failed` -> `failed`
- `voided` -> `voided`
- `refunded` -> `refunded`
- Any unknown status -> `unknown`

Revenue metrics must use `collected_status_allowlist` or an equivalent central allow-list, never `status != failed` style exclusion logic.

Unknown statuses should be stored and visible in diagnostics, but should not count as collected revenue.

## API Endpoints

### Health

- `GET /health`
  - Confirms service is running.

### Sync

- `POST /sync`
  - Triggers all configured sources.
  - Returns per-source success/failure summary.

- `POST /sync/{source_name}`
  - Triggers one source.

- `GET /sync-runs/{sync_run_id}`
  - Returns run status and source-level outcomes.

Optional demo helpers:

- `POST /demo/seed`
  - Seeds local/demo records if external credentials are unavailable in local development.
  - Must be clearly marked as demo-only and not used as a silent production fallback.

- `POST /demo/simulate-cursor-expired/{source_name}`
  - Forces the next source sync to exercise the full-backfill fallback.

### Metrics

- `GET /metrics/revenue/summary?start=YYYY-MM-DD&end=YYYY-MM-DD`
  - Returns one total collected revenue number for the date range.

- `GET /metrics/revenue/breakdown?start=YYYY-MM-DD&end=YYYY-MM-DD&interval=day`
  - Returns day-by-day totals.

Both metrics endpoints must call the same metrics service/query builder so they cannot drift.

## Sync Behavior

For each source:

1. Load the stored cursor.
2. Attempt incremental fetch when a cursor exists.
3. If the source rejects the cursor as stale or expired, record the failure reason and run a full fetch.
4. Normalize each record.
5. Reject invalid records explicitly and continue processing the rest.
6. Upsert valid normalized records using source-specific unique keys.
7. Store raw external payloads for auditability.
8. Update the cursor only after successful processing for that source.
9. Record per-source counts and errors in `sync_run_sources`.

The top-level sync run should be `partial_success` when at least one source succeeds and at least one source fails.

## Idempotency Strategy

- Use database unique constraints on `(source_name, source_record_id)` for normalized tables.
- Use upserts for all normalized records.
- Store raw payloads with a unique source identity and update payload/hash on repeated ingest.
- Treat duplicate webhook/job delivery as a normal retry path.
- Add tests that run the same sync twice and assert row counts do not increase.

## Failure Handling

Expected failure cases:

- Expired/stale incremental cursor.
  - Fall back to full fetch.
  - Record the fallback in sync run metadata.
- One source API unavailable.
  - Mark that source as failed.
  - Continue other sources.
  - Return partial success.
- Malformed source record.
  - Reject only that record.
  - Continue with valid records.
  - Store rejection count and reason.
- Unknown transaction status.
  - Normalize to `unknown`.
  - Exclude from collected revenue.
  - Surface in diagnostics or logs.

## Testing Plan

### Unit Tests

- Source status normalization:
  - `paid`, `succeeded`, and `completed` map to `collected`.
  - `pending`, `failed`, `voided`, and `refunded` do not map to collected.
  - Unknown statuses map to `unknown`.
- Revenue allow-list behavior:
  - Only allow-listed canonical statuses count.
  - New unexpected statuses do not count by default.
- Date range validation:
  - Reject invalid dates.
  - Reject `end < start`.
- Source payload normalization:
  - Required fields are validated.
  - Malformed records are rejected visibly.

### Integration Tests

- Running the same sync twice does not duplicate rows.
- Expired cursor error triggers full backfill.
- One failing source does not prevent other sources from syncing.
- Summary revenue equals the sum of breakdown revenue for the same range.
- Adding a new source status does not affect revenue unless mapped and allow-listed.

### Contract or Mocked API Tests

- Mock HubSpot incremental and full fetch responses.
- Mock Google Calendar incremental and full fetch responses, including a 410-style expired sync token.
- Mock finance provider transaction responses.

## Deployment Plan

1. Create Supabase project and database schema.
2. Configure provider credentials as Render environment variables.
3. Deploy FastAPI service to Render.
4. Run migrations or schema setup.
5. Seed sample records in HubSpot, Google Calendar, and finance test mode.
6. Trigger `/sync` against deployed service.
7. Verify metrics endpoints return consistent values.

Required environment variables:

- `DATABASE_URL`
- `HUBSPOT_ACCESS_TOKEN`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REFRESH_TOKEN`
- `GOOGLE_CALENDAR_ID`
- `STRIPE_SECRET_KEY` or equivalent finance provider key

## Demo Plan

The demo video should show:

1. Service health endpoint on Render.
2. Triggering a successful sync.
3. Re-running the same sync and showing no duplicate rows.
4. Simulating or demonstrating an expired cursor and showing full-backfill fallback.
5. Simulating one source failure and showing the other sources still sync.
6. Calling both revenue endpoints for the same date range.
7. Showing summary revenue equals the sum of breakdown revenue.
8. Showing an unknown or non-collected status does not count as revenue.

## Milestones

1. Project scaffold and configuration.
2. Database schema and migrations.
3. Source connector interfaces and mocked connectors.
4. Normalization and idempotent persistence.
5. Sync orchestration and run tracking.
6. Metrics service and endpoints.
7. Tests for idempotency, fallback, partial failure, and metric consistency.
8. Real provider integrations.
9. Render deployment.
10. README, references, AI usage note, and demo script.

## Risks and Assumptions

- Real external account setup can be time-consuming; mocked connector tests should be built first so core correctness is proven before live credentials are configured.
- Google Calendar incremental sync token expiry should be tested with a mock because forcing real token expiry on demand may be awkward.
- Demo-only failure simulation endpoints are acceptable if clearly documented and not hidden production behavior.
- Supabase free-tier limits are sufficient for sample data.
- The finance provider choice is assumed to be Stripe test mode unless project constraints require another provider.
- No UI will be built unless requested later.
