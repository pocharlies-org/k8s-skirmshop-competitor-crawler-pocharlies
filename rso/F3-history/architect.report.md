# F3 Architect Report - History Append-Only Contract

**Date:** 2026-06-24T22:32:00+02:00  
**Role:** Codex RSO/PMO architecture exception after Claude CLI timeout  
**Scope:** architecture contract only. No product code, no infra edits, no DDL/apply.

## RHO Checklist

### Directives
- [x] Start with Claude CLI architect. Evidence: `timeout 180s env RSO_DELEGATED_ROLE=rho-architect claude ... --agent rho-architect --permission-mode acceptEdits` exited `124`.
- [x] No product/infra implementation by Codex. Evidence: this report defines the contract only; no code/manifests/SQL files changed outside RSO docs.
- [x] Preserve F3/F4/F6/F7 boundaries. Evidence: architecture excludes cart-probe, `prices.py`/`intel.py`, and CronJob activation.
- [x] Preserve approved plan intent. Evidence: chooses DB `competitor_intel` in CNPG, table `price_stock_observation`, monthly partitions, and view `estimated_sales_daily`.

## Decisions

### DECISION-F3-001 - Persistence Target

Use a dedicated CNPG database:

```yaml
kind: Database
metadata:
  name: competitor-intel
  namespace: databases
spec:
  name: competitor_intel
  owner: skirmshop
  cluster:
    name: postgres-shared
```

Reasoning:
- The approved plan explicitly names DB `competitor_intel`.
- Live research confirmed this DB does not exist yet.
- Existing CNPG pattern uses `Database` CRs in `databases/postgres-shared/app-databases.yaml`.
- Owner `skirmshop` allows initial use of existing app credential pattern (`shared-postgres-app`) without creating a new Vault secret during F3. Security may later split a dedicated least-privilege role before F7/nightly.

Residual risk:
- Reusing `skirmshop` is broader than ideal. F3 remains acceptable if DDL is additive and writer scope is limited; F7 should revisit dedicated role/secret before nocturnal production.

### DECISION-F3-002 - Strict Idempotency With Monthly Partitions

Postgres partitioned-table unique constraints must include the partition key. A native unique constraint on `(domain, product_key, run_id)` cannot be enforced globally on a table partitioned by `observed_at`.

Use a non-partitioned idempotency ledger plus the partitioned observation table:

```sql
CREATE TABLE competitor_intel_observation_key (
  domain text NOT NULL,
  product_key text NOT NULL,
  run_id text NOT NULL,
  idempotency_key text GENERATED ALWAYS AS (domain || '|' || product_key || '|' || run_id) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (domain, product_key, run_id),
  UNIQUE (idempotency_key)
);

CREATE TABLE price_stock_observation (
  idempotency_key text NOT NULL,
  domain text NOT NULL,
  product_key text NOT NULL,
  run_id text NOT NULL,
  observed_at timestamptz NOT NULL,
  price numeric(12,4),
  currency char(3) NOT NULL DEFAULT 'EUR',
  vat_incl boolean,
  stock_qty integer,
  stock_status text NOT NULL,
  stock_method text NOT NULL,
  is_promotion boolean NOT NULL DEFAULT false,
  raw_snapshot_s3 text,
  crawl_success boolean NOT NULL DEFAULT true,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (price IS NULL OR price >= 0),
  CHECK (stock_qty IS NULL OR stock_qty >= 0),
  CHECK (stock_status IN ('in_stock','out_of_stock','unknown')),
  CHECK (stock_method IN ('visible','cart_probe','unknown')),
  CHECK (crawl_success OR error_code IS NOT NULL),
  PRIMARY KEY (observed_at, idempotency_key),
  FOREIGN KEY (domain, product_key, run_id)
    REFERENCES competitor_intel_observation_key(domain, product_key, run_id)
) PARTITION BY RANGE (observed_at);
```

Writer contract:
- In one transaction, first insert `(domain, product_key, run_id)` into the ledger with `ON CONFLICT DO NOTHING`.
- Insert into `price_stock_observation` only when the ledger insert succeeds.
- Re-running the same `(domain, product_key, run_id)` is a no-op, so append-only rows are not duplicated or updated.

### DECISION-F3-003 - Partitioning

Partition `price_stock_observation` monthly by `observed_at`.

Minimum F3 migration must create:
- parent table
- current-month partition
- next-month partition, or a documented function `ensure_price_stock_partition(month_start date)`

Reasoning:
- The plan requires monthly partitioning.
- Creating current + next month keeps the first two-runs smoke simple.

### DECISION-F3-004 - Estimated Sales View

`estimated_sales_daily` should compute over successful/failed observations without inventing sales:

```sql
CREATE VIEW estimated_sales_daily AS
WITH ordered AS (
  SELECT
    domain,
    product_key,
    date_trunc('day', observed_at)::date AS observed_day,
    observed_at,
    stock_qty,
    crawl_success,
    LAG(stock_qty) OVER (
      PARTITION BY domain, product_key ORDER BY observed_at
    ) AS prev_stock_qty,
    LAG(crawl_success) OVER (
      PARTITION BY domain, product_key ORDER BY observed_at
    ) AS prev_crawl_success,
    LAG(observed_at) OVER (
      PARTITION BY domain, product_key ORDER BY observed_at
    ) AS prev_observed_at
  FROM price_stock_observation
)
SELECT
  domain,
  product_key,
  observed_day,
  observed_at,
  prev_observed_at,
  prev_stock_qty,
  stock_qty,
  CASE
    WHEN prev_observed_at IS NULL THEN NULL
    WHEN NOT crawl_success OR NOT prev_crawl_success THEN NULL
    WHEN stock_qty IS NULL OR prev_stock_qty IS NULL THEN NULL
    WHEN observed_at - prev_observed_at > interval '36 hours' THEN NULL
    WHEN prev_stock_qty - stock_qty > 0 THEN prev_stock_qty - stock_qty
    WHEN prev_stock_qty - stock_qty = 0 THEN 0
    ELSE NULL
  END AS estimated_units_sold,
  CASE
    WHEN prev_observed_at IS NULL THEN 'indeterminate'
    WHEN NOT crawl_success OR NOT prev_crawl_success THEN 'indeterminate'
    WHEN stock_qty IS NULL OR prev_stock_qty IS NULL THEN 'indeterminate'
    WHEN observed_at - prev_observed_at > interval '36 hours' THEN 'indeterminate'
    WHEN prev_stock_qty - stock_qty > 0 THEN 'estimated'
    WHEN prev_stock_qty - stock_qty = 0 THEN 'none'
    ELSE 'indeterminate'
  END AS estimate_status
FROM ordered;
```

Notes:
- `crawl_success` is the justified extra column required by the plan's `last_success` language.
- `error_code` explains failed crawls without treating missing price/stock as zero.
- The 36h threshold is a conservative daily-cadence gap detector for F3 smoke; make it configurable later if scheduler cadence changes.

### DECISION-F3-005 - F2 Numeric Stock Gap

F2 intentionally strips numeric stock. Therefore:
- F3 schema supports `stock_qty`.
- F3 writer must preserve `stock_status`/`stock_method` from F2 and set `stock_qty=NULL` when no numeric source exists.
- Real F2-only crawls will produce historical observations but `estimated_sales_daily` will be `indeterminate` until F4 cart-probe or another numeric source supplies `stock_qty`.
- F3 acceptance for delta correctness must use controlled fixtures or synthetic observations with `stock_qty`, not pretend F2 produced quantities.

### DECISION-F3-006 - Raw Snapshots

`raw_snapshot_s3` is nullable in F3.

Reasoning:
- Plan wants snapshots in MinIO/S3.
- F3 can store only URI/key and avoid logging raw HTML.
- Actual snapshot upload can be implemented behind existing `skirmshop-drive-s3-app` credentials, but F3 PASS does not require full snapshot archive if the field and no-secret handling are present.

## Implementation Boundary For Claude Roles

### Backend
- Add a migration SQL artifact, preferably under `db/migrations/001_f3_history.sql` in the crawler repo unless DevOps chooses an infra migration location.
- Add an append-only writer module that:
  - builds `idempotency_key` consistently,
  - validates `stock_status`/`stock_method`,
  - uses a transaction,
  - inserts ledger first,
  - inserts observation only if ledger inserted,
  - never updates/deletes observations.
- Add tests for:
  - idempotent same run,
  - two-run positive delta,
  - replenishment `indeterminate`,
  - failed/gap/null `indeterminate`,
  - F2 no-quantity -> observation with `stock_qty=NULL`.

### DevOps
- Use a clean branch/worktree for `k8s-infra-pocharlies`; current local worktree is dirty on `deploy/prod`.
- Add CNPG `Database` CR for `competitor_intel` only after confirming owner/role.
- Prefer a one-shot migration Job or documented manual psql command using `shared-postgres-app`/`postgres-shared-rw`, with SQL mounted from ConfigMap or repo artifact.
- Validate with `kubectl apply --dry-run=server` and live read-only `psql` queries.

### Security
- Confirm broad `skirmshop` role is acceptable for F3 or require dedicated role before live apply.
- Verify no secrets in logs/reports.
- Verify no cart/checkout/login code is introduced.
- Verify `raw_snapshot_s3` stores only URI/key in reports.

## Residual Risks

- [blocked] Claude architect did not produce a report; this is PMO-authored architecture.
- [blocked] Dedicated least-privilege role is deferred unless Security rejects shared `skirmshop` owner.
- [blocked] Live DDL apply remains blocked until DevOps has a clean infra branch/worktree and a validated migration/apply path.
- [blocked] Real sales estimates remain `indeterminate` for F2-only crawls because F2 has no numeric `stock_qty`.
