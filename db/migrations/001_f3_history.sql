-- ============================================================================
-- F3 History Append-Only — competitor_intel schema (LOCAL MIGRATION ARTIFACT)
-- ============================================================================
-- Scope:   Append-only historical price/stock observations for competitors.
-- Target:  CNPG database `competitor_intel` (DECISION-F3-001). Objects are
--          placed in schema `competitor_intel` so the migration is portable:
--          it can be applied to the dedicated `competitor_intel` DB OR as an
--          isolated schema inside an existing DB without polluting `public`.
-- Contract: rso/F3-history/architect.report.md (Decisions F3-001..F3-006).
--
-- Safety / invariants:
--   * ADDITIVE ONLY. No DROP / TRUNCATE / DELETE / destructive UPDATE here.
--   * Idempotent DDL (IF NOT EXISTS / CREATE OR REPLACE) so re-applying is safe.
--   * Reversible by a *new* migration (e.g. DROP SCHEMA competitor_intel CASCADE),
--     never by editing/removing this one.
--   * This file is the LOCAL DDL artifact only. Live apply is owned by DevOps
--     via GitOps/approved psql; it is NOT applied by F3 backend.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS competitor_intel;

-- ----------------------------------------------------------------------------
-- Idempotency ledger (NON-partitioned).
-- DECISION-F3-002: Postgres partitioned-table unique constraints must include
-- the partition key, so a global UNIQUE on (domain, product_key, run_id) cannot
-- be enforced on a table partitioned by observed_at. The ledger enforces global
-- idempotency; the partitioned observation table references it by FK.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competitor_intel.competitor_intel_observation_key (
    domain          text NOT NULL,
    product_key     text NOT NULL,
    run_id          text NOT NULL,
    idempotency_key text GENERATED ALWAYS AS (domain || '|' || product_key || '|' || run_id) STORED,
    created_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, product_key, run_id),
    UNIQUE (idempotency_key)
);

-- ----------------------------------------------------------------------------
-- Partitioned observation table (RANGE by observed_at, monthly partitions).
-- DECISION-F3-003. Columns are the F3 contract minimum plus justified extras:
--   crawl_success / error_code  -> required for last_success / gap semantics.
--   created_at                  -> ingest audit timestamp.
-- stock_method accepts 'cart_probe' for FUTURE F4; the F3 writer never emits it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competitor_intel.price_stock_observation (
    idempotency_key text NOT NULL,
    domain          text NOT NULL,
    product_key     text NOT NULL,
    run_id          text NOT NULL,
    observed_at     timestamptz NOT NULL,
    price           numeric(12,4),
    currency        char(3) NOT NULL DEFAULT 'EUR',
    vat_incl        boolean,
    stock_qty       integer,
    stock_status    text NOT NULL,
    stock_method    text NOT NULL,
    is_promotion    boolean NOT NULL DEFAULT false,
    raw_snapshot_s3 text,
    crawl_success   boolean NOT NULL DEFAULT true,
    error_code      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pso_price_nonneg     CHECK (price IS NULL OR price >= 0),
    CONSTRAINT pso_stock_qty_nonneg CHECK (stock_qty IS NULL OR stock_qty >= 0),
    CONSTRAINT pso_stock_status_enum CHECK (stock_status IN ('in_stock','out_of_stock','unknown')),
    CONSTRAINT pso_stock_method_enum CHECK (stock_method IN ('visible','cart_probe','unknown')),
    CONSTRAINT pso_failure_has_error CHECK (crawl_success OR error_code IS NOT NULL),
    PRIMARY KEY (observed_at, idempotency_key),
    FOREIGN KEY (domain, product_key, run_id)
        REFERENCES competitor_intel.competitor_intel_observation_key (domain, product_key, run_id)
) PARTITION BY RANGE (observed_at);

-- Index propagates to all (current and future) partitions.
-- DECISION/HANDOFF: (domain, product_key, observed_at DESC) for latest-first reads.
CREATE INDEX IF NOT EXISTS idx_pso_domain_key_observed_at_desc
    ON competitor_intel.price_stock_observation (domain, product_key, observed_at DESC);

-- ----------------------------------------------------------------------------
-- Monthly partition provisioner.
-- DECISION-F3-003: ensure_price_stock_partition(month_start date) creates the
-- monthly partition for the month containing month_start if it does not exist.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION competitor_intel.ensure_price_stock_partition(month_start date)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    start_date     date := date_trunc('month', month_start)::date;
    end_date       date := (date_trunc('month', month_start) + interval '1 month')::date;
    partition_name text := format('price_stock_observation_%s', to_char(start_date, 'YYYYMM'));
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname = partition_name
          AND n.nspname = 'competitor_intel'
    ) THEN
        EXECUTE format(
            'CREATE TABLE competitor_intel.%I PARTITION OF competitor_intel.price_stock_observation '
            'FOR VALUES FROM (%L) TO (%L)',
            partition_name, start_date, end_date
        );
    END IF;
END;
$$;

-- Bootstrap current-month and next-month partitions (DECISION-F3-003).
SELECT competitor_intel.ensure_price_stock_partition(date_trunc('month', now())::date);
SELECT competitor_intel.ensure_price_stock_partition((date_trunc('month', now()) + interval '1 month')::date);

-- ----------------------------------------------------------------------------
-- estimated_sales_daily view (DECISION-F3-004).
-- Sales are estimated ONLY when prev and current stock_qty exist, both
-- observations succeeded, the gap is <= 36h, and prev_qty - curr_qty > 0.
-- delta = 0 -> 'none'; replenishment (delta < 0), gaps > 36h, failures, or
-- nulls -> 'indeterminate'. Never invents sales from missing data.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW competitor_intel.estimated_sales_daily AS
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
    FROM competitor_intel.price_stock_observation
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
