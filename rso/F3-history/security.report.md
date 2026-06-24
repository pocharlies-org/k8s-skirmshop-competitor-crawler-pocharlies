# F3 Security Report - History Append-Only

**Date:** 2026-06-25T00:39:00+02:00
**Role:** Codex RSO/Security exception after Claude CLI stalls
**Scope:** new F3 crawler/DDL/test/report artifacts plus infra Database CR shape. No secret values read.

## RHO Checklist

### Directives

- [x] No secrets exposed. Evidence: scans over new F3 files found no API keys, passwords, bearer tokens, private keys, or decoded Secret data.
- [x] No new competitor-facing actions. Evidence: `src/history_writer.py` imports no HTTP client and performs no network calls; F3 DDL/tests do not fetch pages.
- [x] No cart/checkout/login/CAPTCHA behavior. Evidence: only `cart_probe` appears as a future enum value required by the approved contract; F3 writer comments state it never emits cart-probe data; no checkout/login/CAPTCHA code added.
- [x] No Brain/Falkor history writes. Evidence: `src/history_writer.py` only builds SQL inserts for Postgres; `Brain/Falkor` appears only in a comment stating no writes.
- [x] Raw snapshots not exposed. Evidence: `raw_snapshot_s3` is a nullable URI/key field only; fixtures/reports contain no raw HTML snapshots.
- [x] Append-only posture preserved. Evidence: migration has no uncommented destructive DDL/DML; writer only uses ledger `INSERT ... ON CONFLICT DO NOTHING` and observation `INSERT`.

### Commands / Evidence

```text
rg -n "httpx|requests|aiohttp|urllib|fetch|cart|checkout|login|captcha|push|Brain|Falkor|BRAIN|secret|password|token|raw_snapshot|open\\(" \
  src/history_writer.py db/migrations/001_f3_history.sql tests/test_history_writer.py tests/fixtures rso/F3-history/backend.report.md rso/F3-history/devops.report.md
```

Relevant matches were expected:

- `cart_probe` in enum/DDL/test contract only.
- `raw_snapshot_s3` as nullable field only.
- `Brain/Falkor` in comments/report stating no history writes.
- No HTTP client imports, no credential literals, no raw HTML.

```text
rg -n "BEGIN|CREATE|INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|COPY|PROGRAM|dblink|http|file_fdw|CREATE EXTENSION" \
  db/migrations/001_f3_history.sql src/history_writer.py tests/test_history_writer.py
```

Relevant matches:

- Runtime SQL is `INSERT` only.
- Migration DDL is `CREATE SCHEMA/TABLE/INDEX/FUNCTION/VIEW`; destructive words appear only in comments and tests strip comments before checking.

## Residual Risks

- [blocked] F3 reuses owner `skirmshop` for the future `competitor_intel` DB. This matches current shared app pattern but is broader than least privilege; before F7/nightly, create or approve a dedicated role/secret if required.
- [blocked] Live migration/runbook not yet implemented; when it exists, re-check logs for secret/raw snapshot leakage.
