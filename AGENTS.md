# AGENTS.md

## Project Context

This repository is for a backend-focused assignment about reliable data sync and revenue metrics correctness.

Primary source documents:

- `PROBLEM_STATEMENT.md` defines the assignment requirements.
- `IMPLEMENTATION_PLAN.md` defines the intended architecture and implementation milestones.

No UI is required. Prefer CLI scripts, backend endpoints, tests, and deployment artifacts that demonstrate correctness under failure.

## Working Principles

- Treat all code as production code.
- First read the relevant problem statement, implementation plan, nearby code, tests, and configuration before editing.
- Prefer small, focused, reversible changes.
- Do not rewrite large parts of the project unless explicitly requested.
- Do not introduce placeholder logic, fake fallbacks, dead code, or unnecessary abstractions.
- Do not weaken validation, authentication, authorization, rate limits, or security checks.
- Never hardcode secrets, tokens, credentials, private URLs, or local environment values.
- Use environment variables for credentials and document required variables clearly.
- If requirements are ambiguous, make the safest minimal assumption and document it.
- Ask for clarification only when proceeding could cause data loss, security risk, API breakage, or a large architectural change.

## Assignment Priorities

The assignment cares most about data correctness and failure behavior.

For sync pipeline work, preserve these invariants:

- Incremental sync must not silently lose data.
- If a cursor is stale, expired, or rejected, fall back to a full fetch/backfill.
- Re-running the same sync or receiving the same webhook twice must not create duplicate normalized rows.
- Failure in one source must not prevent healthy sources from landing data.
- Malformed records should be rejected explicitly without hiding the failure or wedging the whole run.
- Source-specific field names and shapes must be normalized through a clear mapping layer.

For revenue metrics work, preserve these invariants:

- There must be one canonical definition of collected revenue.
- Count collected revenue with an allow-list of canonical statuses, never an exclusion list.
- Unknown or newly introduced statuses must not count as revenue by default.
- Summary and breakdown revenue endpoints must use the same shared calculation path.
- Tests should catch a future duplicate or divergent implementation of the same metric.

## Preferred Architecture

Follow `IMPLEMENTATION_PLAN.md` unless the user explicitly changes direction.

Expected layers:

- API layer for request validation and response formatting.
- Source connector layer for HubSpot, Google Calendar, and finance provider calls.
- Sync orchestration layer for cursor handling, full backfill fallback, partial failure behavior, and run tracking.
- Normalization layer for provider-specific payload mapping and validation.
- Persistence layer for database access, idempotent upserts, cursors, and sync run history.
- Metrics layer for canonical collected revenue calculations.

Keep business logic out of route handlers when a service layer exists.

## Data and Persistence Rules

- Use database constraints to enforce idempotency, especially unique keys such as `(source_name, source_record_id)`.
- Use upserts for repeated ingestion of the same external record.
- Store enough raw or wrapped external payload data to debug ingestion behavior.
- Update sync cursors only after the corresponding source has been processed successfully.
- Treat schema changes as high risk.
- Inspect existing models, migrations, and schema history before adding or changing migrations.
- Include migrations where required.
- Avoid destructive migrations unless the user explicitly requests them.
- Mention rollback and data-preservation risks for destructive or high-risk schema work.

## External Integrations

Expected live/free-tier integrations:

- HubSpot developer account for CRM data.
- Google Calendar API for event data.
- Stripe test mode or another free finance/test-mode provider for payments or invoices.
- Supabase Postgres for persistence.
- Render free tier for deployment.

Rules:

- Keep provider-specific API behavior inside connector modules.
- Convert provider errors into typed application errors where practical.
- Do not silently substitute mocked data when real credentials are expected.
- Demo or local seed helpers are acceptable only when clearly named and documented as demo-only.
- Do not commit secrets or generated local credential files.

## Testing Standards

Add or update tests for changed behavior.

Cover at least:

- Happy path sync.
- Duplicate sync or duplicate webhook idempotency.
- Expired cursor fallback to full fetch.
- One source failing while other sources succeed.
- Malformed source payload rejection.
- Status normalization.
- Unknown status exclusion from collected revenue.
- Summary revenue matching the sum of breakdown revenue for the same date range.
- Validation of date ranges and API inputs.

Prefer existing test style and utilities once the project has them.

Run the smallest relevant test first, then broader tests if available.

If tests cannot be run:

- Explain the exact blocker.
- Describe which tests should be run.
- Mention missing infrastructure, dependency, secret, service, or environment setup.
- Still perform static checks or local reasoning where possible.

## Command Guidance

Before assuming commands, inspect files such as:

- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `package.json`
- `Makefile`
- `Dockerfile`
- Render or deployment config files

Likely commands if the planned Python/FastAPI stack is used:

- `pytest`
- `ruff check .`
- `mypy .`
- `python -m uvicorn app.main:app --reload`

Use the commands actually defined by the repo once implementation exists.

## Documentation Requirements

Keep documentation current for:

- Local setup.
- Required environment variables.
- How to run sync jobs.
- How to call metrics endpoints.
- Test commands.
- Deployment steps.
- Tradeoffs and known limitations.
- Sources and references used.
- AI usage and shared chat/export links, if applicable.

The final assignment submission should include:

- Live Render deployment.
- Public GitHub repo link.
- README with local run instructions and tradeoffs.
- Sources and references.
- AI usage note.
- Demo video up to 5 minutes, including at least one failure or edge case.

## Git and Editing Hygiene

- Keep diffs focused on the requested task.
- Do not perform opportunistic refactors or unrelated formatting changes.
- Do not revert changes you did not make unless the user explicitly asks.
- If unrelated changes are present, leave them alone.
- If related user changes affect the task, work with them rather than overwriting them.
- Never use destructive git commands such as `git reset --hard` or `git checkout --` unless explicitly requested.
- Never commit secrets, local environment files, or generated credential artifacts.

## Final Response Format

Always include:

1. Summary of what changed
2. Files changed
3. Tests/checks run
4. Risks or assumptions
5. Manual verification steps
