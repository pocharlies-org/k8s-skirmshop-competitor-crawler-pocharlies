# RHO Backend - F7 runtime history integration

## Scope
- Implementer: Codex PMO exception after two `rho-backend` Claude CLI attempts produced no stdout and no diff.
- Files touched: `src/history_runtime.py`, `src/scheduler.py`, `requirements.txt`, `tests/test_history_runtime.py`, `tests/test_scheduler.py`.
- No production activation, no live traffic, no DB writes from tests.

## Design
- History is disabled by default.
- `HISTORY_ENABLED=true` enables fail-closed DB config validation before a tier crawl starts.
- DB config comes from `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, and optional `PGCONNECT_TIMEOUT`.
- Crawler docs are mapped to F3 `Observation` objects:
  - `source_id` -> `product_key`
  - metadata/domain or store domain -> `domain`
  - metadata/price -> `price`
  - metadata/availability -> `stock_status`/`stock_method` via `normalize_availability`
  - no `stock_qty` is invented
- History is written before Brain push for each store. If history write fails, Brain push for that store is skipped and the tier failure count increments, so `run_once --fail-on-push-errors` can exit non-zero.

## Checklist
- [x] Disabled mode preserves previous behavior. Evidence: history no-op when `HISTORY_ENABLED` is false.
- [x] Enabled mode fails closed on missing DB env. Evidence: tests assert `HistoryConfigError` names missing env without secret values.
- [x] Runtime maps docs to append-only observations without inventing stock quantity. Evidence: `tests/test_history_runtime.py`.
- [x] Scheduler calls history before Brain push when enabled. Evidence: `tests/test_scheduler.py`.
- [x] History failure is not silent. Evidence: scheduler test asserts failed count increments and push is skipped.
- [blocked] DevOps env/Secret/NetworkPolicy wiring is still pending.

## Residual Risks
- Runtime history writes visible-stock observations only; exact `stock_qty` remains unavailable until prober live transport is approved.
- This is a PMO implementation exception because delegated Claude backend did not produce changes. It requires independent verifier/security review before activation.
