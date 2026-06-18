PROMPTS.md

How to Use This File

This file contains the full step-by-step prompt sequence for building the assignment.

Use this workflow:

1. Open the repo in Codex, Cursor, Claude Code, or any coding agent.
2. Ask the agent to read this file fully.
3. Ask it to implement only one prompt at a time.
4. Review the diff after every prompt.
5. Run tests after every implementation slice.
6. Do not allow the agent to continue to the next prompt unless explicitly asked.

Do not ask the agent to implement all prompts in one go.

⸻

Global Rules for the Coding Agent

Follow these rules for every prompt in this file.

Scope Control

* Implement only the current prompt.
* Do not continue to the next prompt unless explicitly asked.
* Do not implement future features early.
* Do not rewrite unrelated files.
* Keep diffs small and reviewable.
* Prefer simple, testable code over over-engineering.
* Do not introduce hidden fallbacks.
* Do not silently fall back from real providers to mock providers.
* Do not hardcode secrets.
* Do not commit credentials, tokens, API keys, or local .env files.

Quality Bar

* Backend only unless explicitly requested.
* Data correctness matters more than UI.
* Tests are required for important behavior.
* Route handlers should stay thin.
* Business logic should live in services.
* Provider-specific code should live inside connector modules.
* Shared logic should not be duplicated.
* All assumptions must be stated clearly.

Reporting Format After Each Implementation Prompt

After completing each implementation prompt, report:

1. Files changed
2. What was implemented
3. Tests added or updated
4. Commands to run
5. Any assumptions
6. Any remaining risks or TODOs

If Blocked

If a prompt is blocked:

1. Stop.
2. Explain the blocker.
3. Do not guess or fake behavior.
4. Suggest the smallest next step.

⸻

Prompt 1: Repo Understanding and Implementation Strategy

Read the following files fully:

* PROBLEM_STATEMENT.md
* IMPLEMENTATION_PLAN.md
* AGENTS.md

Do not write code yet.

Give me:

1. A concise implementation strategy for this repo.
2. The exact project structure you recommend for a Python FastAPI backend.
3. The first small slice to implement.
4. Any assumptions you are making.
5. Any risks in the current implementation plan.

Important constraints:

* Backend only, no UI.
* Data correctness matters more than visuals.
* Start with mock connectors before real HubSpot, Google Calendar, or Stripe integrations.
* Keep code small, testable, and production-quality.
* Do not introduce fake hidden fallbacks.
* Do not hardcode secrets.

Stop after analysis. Do not modify code.

⸻

Prompt 2: Initial FastAPI Project Scaffold

Implement the initial Python/FastAPI project scaffold.

Requirements:

* FastAPI app with GET /health.
* Clean folder structure:
    * app/api
    * app/core
    * app/db
    * app/models
    * app/services
    * app/connectors
    * app/normalizers
    * tests
* Environment config using pydantic-settings or equivalent.
* Basic pytest setup.
* requirements.txt or pyproject.toml.
* README section with local setup commands.

Do not implement sync logic yet.

Do not add real external integrations yet.

Keep this slice minimal and runnable.

After implementation, tell me:

1. Files changed
2. How to run the app
3. How to run tests

⸻

Prompt 3: Database Schema and Migrations

Implement the database schema from IMPLEMENTATION_PLAN.md.

Use Postgres-compatible SQL/migrations.

Tables required:

* source_connections
* sync_runs
* sync_run_sources
* external_records
* contacts
* events
* transactions
* collected_status_allowlist

Important constraints:

* Add unique constraints for idempotency:
    * external_records: source_name, source_record_id, record_type
    * contacts: source_name, source_record_id
    * events: source_name, source_record_id
    * transactions: source_name, source_record_id
* Store raw payloads as JSONB.
* Store amount as integer minor units.
* Seed collected_status_allowlist with:
    * canonical_status = collected
    * counts_as_collected = true
* Do not add destructive migrations.

Also add a small database helper layer for getting connections/sessions.

Add tests or migration verification if the repo already has a test DB pattern.

Do not implement sync endpoints yet.

⸻

Prompt 4: Connector Interfaces and Mock Connectors

Implement the source connector abstraction and mock connectors.

Create a common connector interface with:

* source_name
* source_type
* fetch_incremental(cursor)
* fetch_full()
* returned records
* next cursor

Add typed errors:

* CursorExpiredError
* SourceUnavailableError
* SourcePayloadError or equivalent

Implement mock connectors for:

1. mock_crm
2. mock_calendar
3. mock_payments

Mock behavior should support:

* normal successful full fetch
* normal successful incremental fetch
* cursor expired error
* source unavailable error
* malformed record included in response

Do not connect to HubSpot, Google Calendar, or Stripe yet.

Add tests proving:

* connector interface works
* cursor expired error can be raised
* source unavailable error can be raised

⸻

Prompt 5: Normalization Layer

Implement the normalization layer.

Create normalizers for:

1. CRM/contact records
2. Calendar/event records
3. Payment/transaction records

Normalize different source shapes into canonical models.

For transactions, implement a single canonical status mapper:

* paid -> collected
* succeeded -> collected
* completed -> collected
* pending -> pending
* failed -> failed
* voided -> voided
* refunded -> refunded
* anything unknown -> unknown

Important:

* Unknown statuses must be stored as unknown.
* Unknown statuses must not count as revenue later.
* Required fields should be validated.
* Malformed records should be rejected visibly, not silently ignored.

Add unit tests for:

* valid CRM normalization
* valid calendar normalization
* valid transaction normalization
* malformed record rejection
* all status mapping cases
* unknown status mapping

⸻

Prompt 6: Idempotent Persistence Layer

Implement the persistence layer for normalized records.

Requirements:

* Upsert contacts by source_name + source_record_id.
* Upsert events by source_name + source_record_id.
* Upsert transactions by source_name + source_record_id.
* Upsert external records by source_name + source_record_id + record_type.
* Store payload_hash for external records.
* Re-ingesting the same record should update existing rows, not create duplicates.
* Keep business logic outside route handlers.

Add tests:

1. Insert the same contact twice and assert row count remains 1.
2. Insert the same event twice and assert row count remains 1.
3. Insert the same transaction twice and assert row count remains 1.
4. Re-ingest changed payload and assert existing row updates.

⸻

Prompt 7: Sync Orchestration Service

Implement the sync orchestration service.

Behavior for each source:

1. Load stored cursor.
2. If cursor exists, try incremental fetch.
3. If incremental fetch raises CursorExpiredError, record that fallback happened and run full fetch.
4. If no cursor exists, run full fetch.
5. Normalize each record.
6. Reject malformed records explicitly and count them.
7. Upsert valid normalized records and external payloads.
8. Update the cursor only after successful processing for that source.
9. Record sync_run_sources row with:
    * source_name
    * sync_mode
    * status
    * records_seen
    * records_upserted
    * records_rejected
    * error_code
    * error_message
10. Continue other sources if one source fails.

Top-level sync_run status:

* success if all sources succeed
* partial_success if at least one succeeds and at least one fails
* failed if all sources fail

Do not add real external integrations yet.

Add tests for:

* first full sync
* second incremental sync
* duplicate sync does not duplicate rows
* expired cursor falls back to full fetch
* one source failure does not block other sources
* malformed record is rejected but valid records still land

⸻

Prompt 8: Sync API Endpoints

Add API endpoints for sync.

Endpoints:

POST /sync

Triggers all configured mock sources.

Returns:

* sync_run_id
* top-level status
* per-source summary

POST /sync/{source_name}

Triggers one source.

Returns source-level result.

GET /sync-runs/{sync_run_id}

Returns:

* top-level run status
* source-level outcomes

Optional demo endpoints:

* POST /demo/simulate-cursor-expired/{source_name}
* POST /demo/simulate-source-failure/{source_name}
* POST /demo/reset-simulations

Important:

* Demo endpoints must be clearly named as demo-only.
* Do not silently use demo behavior in production paths.
* Route handlers should be thin and call service layer methods.

Add API tests for these endpoints.

⸻

Prompt 9: Revenue Metrics Service

Implement the canonical revenue metrics service.

Requirements:

* Revenue must be computed only from transactions with canonical statuses allow-listed in collected_status_allowlist.
* Do not use exclusion logic like status != failed.
* Unknown statuses must not count.
* The summary and breakdown endpoints must use the same shared query/service path.
* The code should make it hard for another developer to create a second divergent revenue calculation.

Endpoints:

GET /metrics/revenue/summary?start=YYYY-MM-DD&end=YYYY-MM-DD

Returns revenue summary for the date range.

GET /metrics/revenue/breakdown?start=YYYY-MM-DD&end=YYYY-MM-DD&interval=day

Returns daily revenue breakdown for the date range.

Rules:

* Validate date range.
* Reject invalid dates.
* Reject end before start.
* Use amount_minor.
* Return currency clearly.
* If multiple currencies exist, either group by currency or explicitly document single-currency assumption.

Add tests:

1. paid, succeeded, and completed count as collected after normalization.
2. pending, failed, refunded, voided, and unknown do not count.
3. Summary total equals sum of breakdown for the same date range.
4. Adding a new unexpected status does not change revenue.
5. Invalid date range is rejected.

⸻

Prompt 10: Guard Against Duplicate Revenue Logic

Add a test or structural guard that catches accidental duplicate revenue calculation logic.

Goal:

If someone later implements another slightly different way of calculating collected revenue, tests should fail or the code review surface should be obvious.

Preferred approach:

* Keep one RevenueMetricsService.
* Both summary and breakdown must call a shared private/internal query builder or shared method.
* Add a test that monkeypatches or spies on the shared method and proves both endpoints use it.

Alternative approach:

* Add an integration test with tricky statuses where summary and breakdown must agree exactly.

Do not over-engineer.

Keep the solution simple and explain the guard in README.

⸻

Prompt 11: Deterministic Demo Seed Data

Add deterministic demo seed data.

Requirements:

* Demo seed should create sample CRM contacts, calendar events, and transactions.
* Include transaction statuses:
    * paid
    * succeeded
    * completed
    * pending
    * failed
    * refunded
    * unknown/new status
* Include enough data across multiple days to prove breakdown works.
* Include duplicate source_record_id cases to prove idempotency.
* Add POST /demo/seed or a CLI script.

Important:

* Clearly mark this as demo/local helper.
* Do not use demo seed as a hidden fallback for missing real credentials.
* README should explain how to run it.

Add tests if practical.

⸻

Prompt 12: Real Stripe Connector

Implement the real Stripe test-mode connector as the finance provider.

Requirements:

* Use STRIPE_SECRET_KEY from environment.
* Fetch payment intents, charges, or invoices from Stripe test mode.
* Map Stripe statuses into canonical transaction records.
* Support full fetch.
* Support incremental fetch using created/updated timestamp cursor where practical.
* Convert provider errors into typed connector errors.
* Do not hardcode secrets.
* Keep Stripe-specific logic inside the connector module.

Add mocked tests for:

* successful fetch
* failed Stripe API call
* status normalization
* cursor behavior where applicable

Do not implement HubSpot or Google Calendar in this slice.

Update README env vars.

⸻

Prompt 13: Real Google Calendar Connector

Implement the real Google Calendar connector.

Requirements:

* Use env vars:
    * GOOGLE_CLIENT_ID
    * GOOGLE_CLIENT_SECRET
    * GOOGLE_REFRESH_TOKEN
    * GOOGLE_CALENDAR_ID
* Fetch calendar events.
* Support full fetch.
* Support incremental fetch using Google sync tokens if practical.
* If Google returns a 410 or expired sync token response, raise CursorExpiredError so orchestration falls back to full fetch.
* Normalize events into canonical event records.
* Keep Google-specific logic inside the connector module.
* Do not commit credential files.

Add mocked tests for:

* full fetch
* incremental fetch
* 410 expired sync token -> CursorExpiredError
* malformed event payload

Update README env vars.

⸻

Prompt 14: Real HubSpot Connector

Implement the real HubSpot CRM connector.

Requirements:

* Use HUBSPOT_ACCESS_TOKEN from environment.
* Fetch contacts from HubSpot CRM.
* Support full fetch.
* Support incremental fetch using last modified timestamp or equivalent.
* Convert HubSpot API errors into typed connector errors.
* Normalize HubSpot contact shape into canonical contact records.
* Keep HubSpot-specific logic inside the connector module.
* Do not hardcode secrets.

Add mocked tests for:

* full fetch
* incremental fetch
* API failure
* malformed contact payload

Update README env vars.

⸻

Prompt 15: Connector Registry and Source Selection

Implement a connector registry that chooses between mock connectors and real connectors.

Requirements:

* In local/demo mode, allow mock connectors.
* In production mode, use real connectors when credentials are configured.
* Do not silently fall back from real connectors to mock connectors if credentials are missing.
* If required credentials are missing, fail clearly with a useful error.
* POST /sync should use all configured connectors.
* POST /sync/{source_name} should validate source_name.

Add tests:

* mock mode registry
* production mode missing credentials fails clearly
* unknown source name returns validation error

⸻

Prompt 16: Render Deployment Support

Add deployment support for Render free tier.

Requirements:

* Add render.yaml if appropriate.
* Add start command for FastAPI.
* Ensure app binds to the PORT provided by Render.
* Document required environment variables.
* Document database migration/setup steps.
* Ensure /health works without external credentials.
* Do not include secrets.

Also update README with:

* Local run
* Test commands
* Render deployment steps
* Required env vars
* How to trigger sync
* How to call metrics endpoints

⸻

Prompt 17: Final Test Hardening

Review the whole codebase against:

* PROBLEM_STATEMENT.md
* IMPLEMENTATION_PLAN.md

Do not add new features unless required.

Find gaps in:

* idempotency
* cursor fallback
* partial source failure
* malformed record handling
* unknown status handling
* revenue allow-list behavior
* summary/breakdown consistency
* README/demo instructions
* deployment readiness

Then fix only the gaps needed for the assignment.

Run:

* pytest
* lint/type checks if configured

Report:

1. What was missing
2. What you fixed
3. Tests/checks run
4. Remaining risks

⸻

Prompt 18: README Polish

Improve README.md for assignment submission.

README must include:

1. Problem summary
2. Architecture overview
3. Data model overview
4. Local setup
5. Environment variables
6. How to run migrations
7. How to run the app
8. How to trigger sync
9. How to test idempotency
10. How to simulate cursor expiry
11. How to simulate one source failure
12. How to call revenue summary and breakdown
13. How the code prevents revenue drift
14. Tradeoffs and known limitations
15. Sources/references used
16. AI usage note

Keep it clear and evaluator-friendly.

Do not exaggerate what is implemented.

⸻

Prompt 19: Demo Walkthrough File

Create a DEMO.md file for a 5-minute walkthrough.

The demo should show:

1. Render /health endpoint.
2. POST /demo/seed.
3. POST /sync success.
4. Re-run POST /sync and show row counts do not duplicate.
5. Simulate expired cursor and show full backfill fallback.
6. Simulate one source failure and show partial_success.
7. Call revenue summary endpoint.
8. Call revenue breakdown endpoint.
9. Show summary equals sum of breakdown.
10. Show unknown/non-collected status does not count.

Include exact curl commands and expected response snippets.

Do not claim anything that cannot be shown live.

⸻

Prompt 20: Final Assignment Readiness Review

Do a final assignment-readiness review.

Read:

* PROBLEM_STATEMENT.md
* IMPLEMENTATION_PLAN.md
* README.md
* DEMO.md
* tests

Check whether the implementation proves each required behavior.

Create a final checklist with:

* Requirement
* Where it is implemented
* Which test proves it
* Which demo command shows it
* Any remaining limitation

Do not change code unless you find a concrete bug.

⸻

Commands to Use During Development

Use these commands when working with the coding agent.

Start the process

Read PROMPTS.md fully.
Follow the Global Rules section strictly.
Start with Prompt 1 only.
Do not modify code for Prompt 1. Just analyze and respond.

Implement the next prompt

Now implement Prompt <NUMBER> only.
Keep the diff small and focused.
Do not implement anything from later prompts.
After implementation, summarize:
1. Files changed
2. Tests added or updated
3. Commands to run
4. Assumptions
5. Remaining risks

Self-review after a prompt

Review your own changes for Prompt <NUMBER>.
Check for:
- unnecessary files
- scope creep
- broken imports
- missing tests
- duplicated logic
- future-prompt implementation done too early
Fix only issues related to Prompt <NUMBER>.

If the diff is too large

Before making more changes, explain why this diff is larger than expected.
List any files changed that were not necessary for the current prompt.
Then propose a smaller patch.
Do not continue coding until the scope is clear.

If tests fail

The tests are failing.
Do not rewrite large parts of the code.
First explain:
1. Which tests are failing
2. The likely root cause
3. The smallest fix
Then apply only the smallest fix.

Before moving to real integrations

Before implementing real external integrations, confirm that all mock connector, normalization, sync, idempotency, and revenue tests pass.
Do not add real provider code until the core behavior is correct.

Final review command

Do a final review against PROBLEM_STATEMENT.md.
Create a requirement-by-requirement checklist.
For each requirement, show:
1. Implementation file
2. Test file
3. Demo command if available
4. Any limitation
Do not modify code unless there is a clear bug.

⸻

Important Warning

Do not use this command:

Implement all prompts one by one.

That usually creates a giant, messy diff.

Use this instead:

Implement the next prompt only. Stop after completing it.