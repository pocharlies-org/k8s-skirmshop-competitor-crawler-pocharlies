# F7 DB Live Report - competitor_intel

## Scope
- Gate: F7 DB/Migration.
- Live resource: CNPG `Database/competitor-intel` in namespace `databases`.
- Migration: `db/migrations/001_f3_history.sql`.
- Activation impact: database only. Crawler Deployment remains `replicas: 0`; CronJobs remain `suspend: true`.

## Live Apply Evidence
- Applied only the `Database/competitor-intel` CR with server-side apply.
- `kubectl apply --server-side --dry-run=server -f -` accepted the object.
- `kubectl apply --server-side -f -` applied the object.
- `kubectl -n databases get database competitor-intel -o wide` returned `APPLIED true`.

## Migration Evidence
- Migration was applied with role `skirmshop` using password from Kubernetes `secret/skirmshop-db-credentials`; no secret values were printed.
- Command result included:
  - `CREATE SCHEMA`
  - `CREATE TABLE`
  - `CREATE INDEX`
  - `CREATE FUNCTION`
  - two `ensure_price_stock_partition` calls
  - `CREATE VIEW`

## Verification SQL Evidence
- Connection check: `skirmshop|competitor_intel`.
- Tables:
  - `competitor_intel.competitor_intel_observation_key`
  - `competitor_intel.price_stock_observation`
  - `competitor_intel.price_stock_observation_202606`
  - `competitor_intel.price_stock_observation_202607`
- View:
  - `competitor_intel.estimated_sales_daily`
- Ownership:
  - schema owner `skirmshop`
  - tables/partitions/view owner `skirmshop`
- Empty live view check: `SELECT count(*) FROM competitor_intel.estimated_sales_daily;` returned `0`.

## Transactional Smoke
- Inserted two smoke observations inside `BEGIN`.
- `estimated_sales_daily` returned `3|estimated`.
- Executed `ROLLBACK`.
- Post-rollback persistence check returned `0` rows for `domain='rso.local'`.

## GitOps Reconciliation
- The live CR was applied directly to unblock the DB gate without pushing to `deploy/prod`.
- Clean GitOps reconciliation branch prepared from `origin/deploy/prod`:
  - repo: `k8s-infra-pocharlies`
  - branch: `codex/competitor-crawler-F7-db-gitops`
  - commit: `9140897 postgres: add competitor intel database`
  - PR: `https://github.com/pocharlies-org/k8s-infra-pocharlies/pull/15`
- Residual blocker: PR is not merged, so `deploy/prod` does not yet contain the CR.

## Checklist
- [x] Live database exists and CNPG reports `APPLIED true`.
- [x] Migration applied successfully.
- [x] App role `skirmshop` owns schema objects.
- [x] Tables, monthly partitions and view verified.
- [x] Smoke write/estimate path verified in a rolled-back transaction.
- [blocked] GitOps reconciliation PR is open but not merged.
