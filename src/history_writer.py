"""F3 History Append-Only writer / ingest.

Persists competitor price/stock observations into the ``competitor_intel``
schema (see ``db/migrations/001_f3_history.sql``) following the architect
contract in ``rso/F3-history/architect.report.md``.

Design:
  * Append-only. The writer never UPDATEs or DELETEs observations.
  * Global idempotency by ``(domain, product_key, run_id)`` via a non-partitioned
    ledger. In one transaction the ledger row is inserted first with
    ``ON CONFLICT DO NOTHING``; the partitioned observation row is inserted ONLY
    when the ledger insert actually created a row. Re-running the same
    ``(domain, product_key, run_id)`` is therefore a no-op.
  * DB-API / psycopg compatible: SQL is parameterised with ``%s`` placeholders
    and the writer uses ``conn.cursor()`` / ``commit`` / ``rollback``. It does
    NOT import psycopg, so unit tests can drive it with a fake connection.

This module produces NO cart-probe data (F4) and writes NOTHING to Brain/Falkor
(F3 history lives only in Postgres append-only).
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence

# --- Domain enums (mirror DB CHECK constraints) -----------------------------
VALID_STOCK_STATUS: frozenset[str] = frozenset({"in_stock", "out_of_stock", "unknown"})
# 'cart_probe' is accepted for FUTURE F4; the F3 normalizer never emits it.
VALID_STOCK_METHOD: frozenset[str] = frozenset({"visible", "cart_probe", "unknown"})

DEFAULT_SCHEMA = "competitor_intel"
DEFAULT_CURRENCY = "EUR"

# Gap threshold for the sales estimator mirror (DECISION-F3-004).
GAP_THRESHOLD = timedelta(hours=36)


def build_idempotency_key(domain: str, product_key: str, run_id: str) -> str:
    """Build the deterministic idempotency key (mirrors the DB GENERATED column)."""
    return f"{domain}|{product_key}|{run_id}"


# ---------------------------------------------------------------------------
# Observation
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Observation:
    """A single append-only price/stock observation.

    Field set matches ``competitor_intel.price_stock_observation``. Validation
    here mirrors the DB CHECK constraints so the writer never attempts an insert
    the database would reject (errors are explicit, never silently dropped).
    """

    domain: str
    product_key: str
    run_id: str
    observed_at: datetime
    price: Optional[float] = None
    currency: str = DEFAULT_CURRENCY
    vat_incl: Optional[bool] = None
    stock_qty: Optional[int] = None
    stock_status: str = "unknown"
    stock_method: str = "unknown"
    is_promotion: bool = False
    raw_snapshot_s3: Optional[str] = None
    crawl_success: bool = True
    error_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("Observation.domain is required")
        if not self.product_key:
            raise ValueError("Observation.product_key is required")
        if not self.run_id:
            raise ValueError("Observation.run_id is required")
        if not isinstance(self.observed_at, datetime):
            raise ValueError("Observation.observed_at must be a datetime")
        if self.stock_status not in VALID_STOCK_STATUS:
            raise ValueError(
                f"invalid stock_status {self.stock_status!r}; "
                f"expected one of {sorted(VALID_STOCK_STATUS)}"
            )
        if self.stock_method not in VALID_STOCK_METHOD:
            raise ValueError(
                f"invalid stock_method {self.stock_method!r}; "
                f"expected one of {sorted(VALID_STOCK_METHOD)}"
            )
        if self.price is not None and self.price < 0:
            raise ValueError(f"price must be >= 0, got {self.price}")
        if self.stock_qty is not None and self.stock_qty < 0:
            raise ValueError(f"stock_qty must be >= 0, got {self.stock_qty}")
        if self.currency is None or len(self.currency) != 3:
            raise ValueError(f"currency must be a 3-char code, got {self.currency!r}")
        # Mirrors CHECK (crawl_success OR error_code IS NOT NULL).
        if not self.crawl_success and not self.error_code:
            raise ValueError("error_code is required when crawl_success is False")

    @property
    def idempotency_key(self) -> str:
        return build_idempotency_key(self.domain, self.product_key, self.run_id)


@dataclasses.dataclass(frozen=True)
class WriteResult:
    """Outcome of a ``write_observations`` call."""

    inserted: int = 0
    skipped: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.skipped


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------
def _ledger_sql(schema: str) -> str:
    return (
        f"INSERT INTO {schema}.competitor_intel_observation_key "
        f"(domain, product_key, run_id) VALUES (%s, %s, %s) "
        f"ON CONFLICT (domain, product_key, run_id) DO NOTHING"
    )


def _observation_sql(schema: str) -> str:
    return (
        f"INSERT INTO {schema}.price_stock_observation ("
        f"idempotency_key, domain, product_key, run_id, observed_at, "
        f"price, currency, vat_incl, stock_qty, stock_status, stock_method, "
        f"is_promotion, raw_snapshot_s3, crawl_success, error_code"
        f") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )


def write_observations(
    conn: Any,
    observations: Iterable[Observation],
    *,
    schema: str = DEFAULT_SCHEMA,
) -> WriteResult:
    """Append observations idempotently inside a single transaction.

    For each observation, the ledger row is inserted first with
    ``ON CONFLICT DO NOTHING``. The observation row is inserted ONLY when the
    ledger insert created a row (``cursor.rowcount == 1``), so a repeated
    ``(domain, product_key, run_id)`` neither duplicates nor updates rows.

    The whole batch is committed together; any error rolls the batch back and
    re-raises (no silent catch).
    """
    ledger_sql = _ledger_sql(schema)
    observation_sql = _observation_sql(schema)

    inserted = 0
    skipped = 0
    cur = conn.cursor()
    try:
        for obs in observations:
            cur.execute(ledger_sql, (obs.domain, obs.product_key, obs.run_id))
            if cur.rowcount == 1:
                cur.execute(
                    observation_sql,
                    (
                        obs.idempotency_key,
                        obs.domain,
                        obs.product_key,
                        obs.run_id,
                        obs.observed_at,
                        obs.price,
                        obs.currency,
                        obs.vat_incl,
                        obs.stock_qty,
                        obs.stock_status,
                        obs.stock_method,
                        obs.is_promotion,
                        obs.raw_snapshot_s3,
                        obs.crawl_success,
                        obs.error_code,
                    ),
                )
                inserted += 1
            else:
                # Ledger conflict => this (domain, product_key, run_id) already
                # exists; append-only no-op.
                skipped += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        close = getattr(cur, "close", None)
        if callable(close):
            close()

    return WriteResult(inserted=inserted, skipped=skipped)


# ---------------------------------------------------------------------------
# Normalizer: F1/F2 dry-run payload -> Observations
# ---------------------------------------------------------------------------
def from_dry_run_payload(
    payload: Mapping[str, Any],
    run_id: str,
    observed_at: datetime,
) -> list[Observation]:
    """Map an F1/F2 dry-run JSON payload to a list of Observations.

    Mapping (per HANDOFF / DECISION-F3-005):
      * product_key  = product['source_id'] (the graph node id).
      * domain       = product['domain'] or payload['domain'].
      * currency defaults to EUR.
      * stock_status/stock_method are preserved from F2 (default 'unknown').
      * stock_qty is OPTIONAL: F2 strips numeric stock, so it stays NULL and
        the estimator will report 'indeterminate' rather than inventing sales.
    """
    products = payload.get("products", [])
    domain_default = payload.get("domain")

    observations: list[Observation] = []
    for product in products:
        product_key = product.get("source_id")
        if not product_key:
            raise ValueError(
                "product missing 'source_id' (product_key) for url="
                f"{product.get('url')!r}"
            )
        domain = product.get("domain") or domain_default
        observations.append(
            Observation(
                domain=domain,
                product_key=product_key,
                run_id=run_id,
                observed_at=observed_at,
                price=product.get("price"),
                currency=(product.get("currency") or DEFAULT_CURRENCY),
                vat_incl=product.get("vat_incl"),
                stock_qty=product.get("stock_qty"),
                stock_status=(product.get("stock_status") or "unknown"),
                stock_method=(product.get("stock_method") or "unknown"),
                is_promotion=bool(product.get("is_promotion", False)),
                raw_snapshot_s3=product.get("raw_snapshot_s3"),
                crawl_success=bool(product.get("crawl_success", True)),
                error_code=product.get("error_code"),
            )
        )
    return observations


# ---------------------------------------------------------------------------
# Sales estimator (pure-Python mirror of estimated_sales_daily view)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class SalesEstimate:
    """One row of the estimated-sales computation (mirrors the SQL view)."""

    domain: str
    product_key: str
    observed_at: datetime
    prev_observed_at: Optional[datetime]
    prev_stock_qty: Optional[int]
    stock_qty: Optional[int]
    estimated_units_sold: Optional[int]
    estimate_status: str


@dataclasses.dataclass(frozen=True)
class _Row:
    domain: str
    product_key: str
    observed_at: datetime
    stock_qty: Optional[int]
    crawl_success: bool


def _as_row(obs: Any) -> _Row:
    if isinstance(obs, Observation):
        return _Row(obs.domain, obs.product_key, obs.observed_at, obs.stock_qty, obs.crawl_success)
    # Mapping-like fallback.
    return _Row(
        obs["domain"],
        obs["product_key"],
        obs["observed_at"],
        obs.get("stock_qty"),
        bool(obs.get("crawl_success", True)),
    )


def _classify(prev: _Row, curr: _Row) -> tuple[Optional[int], str]:
    """Classify a consecutive observation pair (mirrors the view CASE order)."""
    if not curr.crawl_success or not prev.crawl_success:
        return None, "indeterminate"
    if curr.stock_qty is None or prev.stock_qty is None:
        return None, "indeterminate"
    if curr.observed_at - prev.observed_at > GAP_THRESHOLD:
        return None, "indeterminate"
    delta = prev.stock_qty - curr.stock_qty
    if delta > 0:
        return delta, "estimated"
    if delta == 0:
        return 0, "none"
    return None, "indeterminate"  # delta < 0 => replenishment


def estimate_sales(observations: Iterable[Any]) -> list[SalesEstimate]:
    """Pure-Python equivalent of ``competitor_intel.estimated_sales_daily``.

    Uses LAG semantics: within each (domain, product_key) partition ordered by
    observed_at, compares each observation to its predecessor. The first
    observation of a partition has no predecessor and is 'indeterminate'.

    This mirror exists ONLY to unit-test the delta/gap logic without a live
    Postgres; the canonical computation is the SQL view in the migration.
    """
    rows = sorted(
        (_as_row(o) for o in observations),
        key=lambda r: (r.domain, r.product_key, r.observed_at),
    )

    out: list[SalesEstimate] = []
    prev: Optional[_Row] = None
    for row in rows:
        same_partition = (
            prev is not None
            and prev.domain == row.domain
            and prev.product_key == row.product_key
        )
        if not same_partition:
            out.append(
                SalesEstimate(
                    domain=row.domain,
                    product_key=row.product_key,
                    observed_at=row.observed_at,
                    prev_observed_at=None,
                    prev_stock_qty=None,
                    stock_qty=row.stock_qty,
                    estimated_units_sold=None,
                    estimate_status="indeterminate",
                )
            )
        else:
            assert prev is not None
            units, status = _classify(prev, row)
            out.append(
                SalesEstimate(
                    domain=row.domain,
                    product_key=row.product_key,
                    observed_at=row.observed_at,
                    prev_observed_at=prev.observed_at,
                    prev_stock_qty=prev.stock_qty,
                    stock_qty=row.stock_qty,
                    estimated_units_sold=units,
                    estimate_status=status,
                )
            )
        prev = row
    return out


__all__ = [
    "VALID_STOCK_STATUS",
    "VALID_STOCK_METHOD",
    "DEFAULT_SCHEMA",
    "DEFAULT_CURRENCY",
    "GAP_THRESHOLD",
    "Observation",
    "WriteResult",
    "SalesEstimate",
    "build_idempotency_key",
    "write_observations",
    "from_dry_run_payload",
    "estimate_sales",
]
