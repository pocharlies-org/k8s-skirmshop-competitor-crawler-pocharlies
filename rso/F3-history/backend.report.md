# F3 Backend Report - History Append-Only Local Implementation

**Date:** 2026-06-25T00:21:49+02:00
**Role:** rho-backend via Claude CLI, with Codex RSO test/report exception
**Scope:** crawler repo only. No live DB, no kubectl/apply, no infra repo, no secrets.

## Execution Note

Claude CLI produced partial backend artifacts but did not return a report:

- Normal `rho-backend` invocation was interrupted after ~6 minutes with no stdout; it had created `db/migrations/001_f3_history.sql`, `src/history_writer.py`, and `tests/fixtures/*.json`.
- Safe-mode follow-up invocations with `acceptEdits` and then `bypassPermissions` stayed alive without writing tests/reports.
- Codex RSO completed only the verification test harness and this report as an explicit process exception. Runtime/product implementation artifacts remain attributable to the Claude backend attempt.

## RHO Checklist

### Directives

- [x] Keep F3 boundary: no cart-probe, checkout, login, Brain/FalkorDB history writes, F6 `prices.py`/`intel.py`, or F7 scheduling. Evidence: touched files are limited to `db/migrations/001_f3_history.sql`, `src/history_writer.py`, `tests/fixtures/*.json`, `tests/test_history_writer.py`, and `rso/F3-history/*`; `pytest -q` PASS.
- [x] Keep backend local only; no live DB or GitOps apply. Evidence: no `kubectl`/`psql` apply command was run for this backend pass; `competitor_intel` live smoke remains blocked for DevOps.
- [x] Preserve append-only contract. Evidence: migration has no uncommented `DROP`, `TRUNCATE`, `DELETE`, or `UPDATE`; writer only issues `INSERT INTO ... ON CONFLICT DO NOTHING` for the ledger and `INSERT INTO ... price_stock_observation`.
- [x] No secrets in artifacts. Evidence: new files contain DDL, Python code, JSON fixtures, and test/report text only; no secret values or raw HTML snapshots were added.

### Acceptance Criteria

- [x] Migration SQL artifact exists with F3 contract. Evidence: `db/migrations/001_f3_history.sql`; `tests/test_history_writer.py::test_migration_sql_contract_is_append_only_and_matches_f3_schema`; `pytest -q` -> `58 passed in 0.43s`.
- [x] Append-only writer implemented. Evidence: `src/history_writer.py` defines `Observation`, `write_observations`, `from_dry_run_payload`, and `estimate_sales`; `test_write_observations_inserts_ledger_before_observation_and_rerun_skips` verifies ledger-first idempotency/no duplicate observation on same `(domain, product_key, run_id)`.
- [x] F1/F2 payload normalization preserves missing numeric stock. Evidence: `test_from_dry_run_payload_maps_f2_payload_without_inventing_stock_qty` verifies `stock_qty is None` when absent and default currency `EUR`.
- [x] Two-run local fixture logic verified for >=3 products. Evidence: fixtures `run1.json`, `run2.json`, `run3_gap.json`; `test_estimate_sales_matches_f3_two_runs_and_gap_cases` verifies Product A `estimated_units_sold=3/status=estimated`, Product B replenishment `indeterminate`, Product C failed/null `indeterminate`, Product D gap `indeterminate`, Product E delta zero `none`.
- [blocked] Live SQL smoke with real `estimated_sales_daily` view not executed. Blocker: F3 backend did not apply DDL to a Postgres target; DevOps must create/apply `competitor_intel` or provide an approved test DB, then RSO must run SQL queries.
- [x] Local tests/checks pass. Evidence: `pytest -q` -> `58 passed in 0.43s`; `git diff --check` -> PASS; `python3 -m compileall src tests` -> PASS. Note: `python -m compileall src tests` failed because `/bin/bash: python: command not found`, so the verified command is `python3`.

### Files Touched

- `db/migrations/001_f3_history.sql`
- `src/history_writer.py`
- `tests/fixtures/run1.json`
- `tests/fixtures/run2.json`
- `tests/fixtures/run3_gap.json`
- `tests/test_history_writer.py` (Codex RSO test exception)
- `rso/F3-history/backend.report.md` (Codex RSO report exception)
- `rso/F3-history/CHECKLIST.md` (Codex RSO checklist reconciliation)

### Residual Risks

- [blocked] No live Postgres DDL/view execution yet; SQL syntax and view semantics are checked statically/unit-side only.
- [blocked] DevOps still needs CNPG `Database`/migration path and SQL smoke evidence.
- [blocked] Security and independent verifier roles have not yet signed off.
- [blocked] Claude CLI implementer remains unreliable for long edit/report prompts; future phases should use smaller role prompts or fix the CLI execution issue before relying on it for unattended implementation.
