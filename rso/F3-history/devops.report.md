# F3 DevOps Report - Postgres History Validation

**Date:** 2026-06-25T00:34:00+02:00
**Role:** Codex RSO/DevOps exception after Claude CLI edit/report stalls
**Scope:** local/ephemeral Postgres smoke plus GitOps dry-run. No live apply.

## RHO Checklist

### Directives

- [x] Do not touch dirty `deploy/prod` worktree. Evidence: infra change made in isolated worktree `/home/dibanez/k8s/_worktrees/k8s-infra-competitor-crawler-F3` on branch `codex/competitor-crawler-F3-history`.
- [x] No production mutation. Evidence: only `kubectl apply --dry-run=server -k databases/postgres-shared` was run; no non-dry-run `kubectl apply` or live `psql` DDL was run.
- [x] Validate migration against real Postgres. Evidence: Docker `postgres:16` ephemeral container; `psql -v ON_ERROR_STOP=1 -f db/migrations/001_f3_history.sql` succeeded.
- [x] Validate CNPG Database CR render/apply shape. Evidence: `kubectl kustomize databases/postgres-shared`; `kubectl apply --dry-run=server -k databases/postgres-shared` reported `database.postgresql.cnpg.io/competitor-intel created (server dry run)`.

### Evidence

Ephemeral Postgres smoke:

```text
MIGRATION_OBJECTS
 competitor_intel_observation_key
 price_stock_observation
 price_stock_observation_202606

INSERT_FIXTURES
 inserted_observations = 10

DUPLICATE_RUN_ID_RERUN
 duplicate_inserted_observations = 0

OBS_COUNTS
 observations_total = 10
 product_a_run2_rows = 1

ESTIMATED_SALES_SMOKE
 A stock_qty=7 prev_stock_qty=10 estimated_units_sold=3 estimate_status=estimated
 B stock_qty=8 prev_stock_qty=5 estimated_units_sold=NULL estimate_status=indeterminate
 C stock_qty=NULL prev_stock_qty=4 estimated_units_sold=NULL estimate_status=indeterminate
 D stock_qty=15 prev_stock_qty=20 estimated_units_sold=NULL estimate_status=indeterminate
```

Infra dry-run:

```text
database.postgresql.cnpg.io/competitor-intel created (server dry run)
```

## Files Touched

- Crawler repo: `rso/F3-history/devops.report.md`, `rso/F3-history/CHECKLIST.md`.
- Infra worktree: `/home/dibanez/k8s/_worktrees/k8s-infra-competitor-crawler-F3/databases/postgres-shared/app-databases.yaml`.

## Residual Risks

- [blocked] The CNPG `Database` CR has not been applied live. It is ready as GitOps branch evidence only.
- [blocked] The SQL migration has been validated in ephemeral Postgres, but not applied to live `competitor_intel` because that DB does not exist live yet.
- [blocked] A production migration Job/manual runbook is still needed before F7/nightly.
