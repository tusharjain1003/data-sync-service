# Demo Walkthrough

5-minute demo showing the key behaviors. All commands assume the service is running locally at `http://localhost:8000`.

## Local Setup

Before running demo commands, ensure your `.env` enables demo routes:

```bash
cp .env.example .env
# Then edit .env to set:
#   APP_ENV=development
#   USE_MOCK_CONNECTORS=true
#   ENABLE_DEMO_ROUTES=true
```

Demo endpoints are disabled by default for production safety.
For local demo only, set `ENABLE_DEMO_ROUTES=true`.
Do not enable demo routes in production/Render unless demonstrating against a disposable demo database.

---

## 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status":"ok","app_env":"development","mock_connectors":true}
```

---

## 2. Seed Demo Data

Creates 3 contacts, 2 events, and 8 transactions (mix of collected, pending, failed, refunded, unknown statuses).

```bash
curl -X POST http://localhost:8000/demo/seed
```

Expected:
```json
{"contacts":3,"events":2,"transactions":8}
```

Re-run it — idempotent:
```bash
curl -X POST http://localhost:8000/demo/seed
```
Same response. The seed checks existence before inserting.

---

## 3. First Sync

```bash
curl -X POST http://localhost:8000/sync
```

Expected (3 mock sources):
```json
{
  "sync_run_id": 1,
  "status": "success",
  "summary": {"total_sources":3, "success":3, "failed":0},
  "sources": [
    {"source_name":"mock_crm","status":"success","sync_mode":"full","records_upserted":3},
    {"source_name":"mock_calendar","status":"success","sync_mode":"full","records_upserted":2},
    {"source_name":"mock_payments","status":"success","sync_mode":"full","records_upserted":3}
  ]
}
```

---

## 4. Idempotency — Re-run Sync

Second run uses **incremental** fetch (1 new record per source):

```bash
curl -X POST http://localhost:8000/sync
```

Third run — same incremental data, upserts are idempotent (no new rows added):

```bash
curl -X POST http://localhost:8000/sync
```

Expected:
```json
{
  "status": "success",
  "sources": [
    {"source_name":"mock_crm","sync_mode":"incremental","records_upserted":1},
    {"source_name":"mock_calendar","sync_mode":"incremental","records_upserted":1},
    {"source_name":"mock_payments","sync_mode":"incremental","records_upserted":1}
  ]
}
```

No duplicate rows — upserts match on `(source_name, source_record_id)`.
The row counts (contacts=4, events=3, transactions=4) remain unchanged from the second sync.
`records_upserted` counts upsert calls processed; existing rows are updated in place, not duplicated.

---

## 5. Expired Cursor → Full Backfill Fallback

```bash
# Expire the CRM cursor
curl -X POST http://localhost:8000/demo/simulate-cursor-expired/mock_crm

# Sync — CRM does full fetch; others do incremental
curl -X POST http://localhost:8000/sync
```

Expected — CRM shows `sync_mode: "full_after_cursor_expired"`:
```json
{
  "sources": [
    {"source_name":"mock_crm","sync_mode":"full_after_cursor_expired","records_upserted":3},
    ...
  ]
}
```

```bash
curl -X POST http://localhost:8000/demo/reset-simulations
```

---

## 6. Partial Source Failure

```bash
# Fail the calendar source
curl -X POST http://localhost:8000/demo/simulate-source-failure/mock_calendar

# Sync — calendar fails, CRM and payments succeed
curl -X POST http://localhost:8000/sync
```

Expected:
```json
{
  "status": "partial_success",
  "summary": {"total_sources":3, "success":2, "failed":1},
  "sources": [
    {"source_name":"mock_crm","status":"success"},
    {"source_name":"mock_calendar","status":"failed","error_code":"SourceUnavailableError"},
    {"source_name":"mock_payments","status":"success"}
  ]
}
```

```bash
curl -X POST http://localhost:8000/demo/reset-simulations
```

---

## 7. Revenue Summary

```bash
curl "http://localhost:8000/metrics/revenue/summary?start=2026-06-01&end=2026-06-30"
```

Expected (after seeding + syncing):
```json
{
  "start": "2026-06-01",
  "end": "2026-06-30",
  "items": [
    {"currency": "usd", "total_amount_minor": 21194}
  ]
}
```

Revenue includes both seeded demo transactions and synced mock payment transactions.
- **Seed collected**: tx-col-001 (2999) + tx-col-002 (4999) + tx-col-003 (1599) + tx-col-004 (2000) = **11597**
- **Full sync mock collected**: pay-001 (2999) + pay-002 (4999) = **7998**
- **Incremental sync mock collected**: pay-004 (1599) = **1599**
- **Total**: 11597 + 7998 + 1599 = **21194**
The other 5 transactions (pending, failed, refunded, unknown, pending mock) are excluded.

---

## 8. Revenue Breakdown

```bash
curl "http://localhost:8000/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30&interval=day"
```

Expected — each day shows the combined seed + mock amount for that date:
```json
{
  "start": "2026-06-01",
  "end": "2026-06-30",
  "interval": "day",
  "items": [
    {"date": "2026-06-05", "currency": "usd", "amount_minor": 5998},
    {"date": "2026-06-06", "currency": "usd", "amount_minor": 9998},
    {"date": "2026-06-08", "currency": "usd", "amount_minor": 3198},
    {"date": "2026-06-12", "currency": "usd", "amount_minor": 2000}
  ]
}
```

Sum: 5998 + 9998 + 3198 + 2000 = **21194** — matches summary total.

---

## 9. Summary Equals Sum of Breakdown

```bash
SUMMARY=$(curl -s "http://localhost:8000/metrics/revenue/summary?start=2026-06-01&end=2026-06-30")
BREAKDOWN=$(curl -s "http://localhost:8000/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30")

# Compare — both use the same _build_base_query()
echo "$SUMMARY" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Summary:', d['items'][0]['total_amount_minor'])
"
echo "$BREAKDOWN" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Breakdown sum:', sum(i['amount_minor'] for i in d['items']))
"
```

Both must agree — they cannot diverge because there is only one `_build_base_query()` in the codebase and a guard test proves both endpoints call it.

---

## 10. Unknown Status Does Not Count

The seeded transaction `tx-unk-001` has source status `new_unexpected_status` which normalizes to `unknown`. It is stored in `transactions` and `external_records` but excluded from revenue because `unknown` is not allow-listed.

Total collected = **21194** (not 22194). The $10 unknown transaction is excluded.

---

## Full Script

Copy and run all demo steps at once:

```bash
#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://localhost:8000}"

echo "=== Health ==="
curl -s "$BASE/health" | python3 -m json.tool

echo -e "\n=== Seed ==="
curl -s -X POST "$BASE/demo/seed" | python3 -m json.tool

echo -e "\n=== Sync 1 (full) ==="
curl -s -X POST "$BASE/sync" | python3 -m json.tool

echo -e "\n=== Sync 2 (incremental) ==="
curl -s -X POST "$BASE/sync" | python3 -m json.tool

echo -e "\n=== Sync 3 (idempotent upserts, no duplicate rows) ==="
curl -s -X POST "$BASE/sync" | python3 -m json.tool

echo -e "\n=== Cursor expiry -> full backfill ==="
curl -s -X POST "$BASE/demo/simulate-cursor-expired/mock_crm" | python3 -m json.tool
curl -s -X POST "$BASE/sync" | python3 -m json.tool
curl -s -X POST "$BASE/demo/reset-simulations" | python3 -m json.tool

echo -e "\n=== Partial failure ==="
curl -s -X POST "$BASE/demo/simulate-source-failure/mock_calendar" | python3 -m json.tool
curl -s -X POST "$BASE/sync" | python3 -m json.tool
curl -s -X POST "$BASE/demo/reset-simulations" | python3 -m json.tool

echo -e "\n=== Revenue summary ==="
curl -s "$BASE/metrics/revenue/summary?start=2026-06-01&end=2026-06-30" | python3 -m json.tool

echo -e "\n=== Revenue breakdown ==="
curl -s "$BASE/metrics/revenue/breakdown?start=2026-06-01&end=2026-06-30&interval=day" | python3 -m json.tool

echo -e "\n=== Done ==="
```
