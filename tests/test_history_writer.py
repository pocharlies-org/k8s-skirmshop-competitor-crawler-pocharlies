import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.history_writer import (
    Observation,
    estimate_sales,
    from_dry_run_payload,
    write_observations,
)


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
MIGRATION = ROOT / "db" / "migrations" / "001_f3_history.sql"
T0 = datetime(2026, 6, 24, 8, 0, tzinfo=timezone.utc)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0
        self.closed = False

    def execute(self, sql, params):
        self.conn.operations.append((sql, params))
        if "competitor_intel_observation_key" in sql:
            key = tuple(params)
            if key in self.conn.ledger_keys:
                self.rowcount = 0
            else:
                self.conn.ledger_keys.add(key)
                self.rowcount = 1
            return
        if "price_stock_observation" in sql:
            self.conn.observation_rows.append(params)
            self.rowcount = 1
            return
        raise AssertionError(f"unexpected SQL: {sql}")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.ledger_keys = set()
        self.observation_rows = []
        self.operations = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_observation_validates_contract():
    with pytest.raises(ValueError, match="invalid stock_status"):
        Observation(
            domain="leopard.es",
            product_key="competitor:leopard.es:p1",
            run_id="run-1",
            observed_at=T0,
            stock_status="available",
        )

    with pytest.raises(ValueError, match="invalid stock_method"):
        Observation(
            domain="leopard.es",
            product_key="competitor:leopard.es:p1",
            run_id="run-1",
            observed_at=T0,
            stock_method="cart",
        )

    with pytest.raises(ValueError, match="error_code is required"):
        Observation(
            domain="leopard.es",
            product_key="competitor:leopard.es:p1",
            run_id="run-1",
            observed_at=T0,
            crawl_success=False,
        )


def test_from_dry_run_payload_maps_f2_payload_without_inventing_stock_qty():
    payload = {
        "domain": "leopard.es",
        "products": [
            {
                "source_id": "competitor:leopard.es:https://example.test/p1",
                "price": 19.95,
                "stock_status": "in_stock",
                "stock_method": "visible",
            }
        ],
    }

    observations = from_dry_run_payload(payload, "run-f2", T0)

    assert len(observations) == 1
    obs = observations[0]
    assert obs.domain == "leopard.es"
    assert obs.product_key == "competitor:leopard.es:https://example.test/p1"
    assert obs.currency == "EUR"
    assert obs.stock_status == "in_stock"
    assert obs.stock_method == "visible"
    assert obs.stock_qty is None


def test_write_observations_inserts_ledger_before_observation_and_rerun_skips():
    conn = FakeConnection()
    obs = Observation(
        domain="leopard.es",
        product_key="competitor:leopard.es:https://example.test/p1",
        run_id="run-1",
        observed_at=T0,
        price=10.0,
        stock_qty=5,
        stock_status="in_stock",
        stock_method="visible",
    )

    first = write_observations(conn, [obs])
    second = write_observations(conn, [obs])

    assert first.inserted == 1
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 1
    assert len(conn.observation_rows) == 1
    assert conn.commits == 2
    assert conn.rollbacks == 0

    first_sql, _ = conn.operations[0]
    second_sql, _ = conn.operations[1]
    assert "competitor_intel_observation_key" in first_sql
    assert "price_stock_observation" in second_sql


def test_estimate_sales_matches_f3_two_runs_and_gap_cases():
    observations = []
    observations.extend(from_dry_run_payload(load_fixture("run1.json"), "run-1", T0))
    observations.extend(
        from_dry_run_payload(load_fixture("run2.json"), "run-2", T0 + timedelta(hours=24))
    )
    observations.extend(
        from_dry_run_payload(
            load_fixture("run3_gap.json"),
            "run-3",
            T0 + timedelta(hours=48),
        )
    )

    estimates = {
        (row.product_key.rsplit("/", 1)[-1], row.observed_at): row
        for row in estimate_sales(observations)
    }

    product_a = estimates[("A", T0 + timedelta(hours=24))]
    assert product_a.estimated_units_sold == 3
    assert product_a.estimate_status == "estimated"

    product_b = estimates[("B", T0 + timedelta(hours=24))]
    assert product_b.estimated_units_sold is None
    assert product_b.estimate_status == "indeterminate"

    product_c = estimates[("C", T0 + timedelta(hours=24))]
    assert product_c.estimated_units_sold is None
    assert product_c.estimate_status == "indeterminate"

    product_d = estimates[("D", T0 + timedelta(hours=48))]
    assert product_d.estimated_units_sold is None
    assert product_d.estimate_status == "indeterminate"

    product_e = estimates[("E", T0 + timedelta(hours=24))]
    assert product_e.estimated_units_sold == 0
    assert product_e.estimate_status == "none"


def test_migration_sql_contract_is_append_only_and_matches_f3_schema():
    sql = MIGRATION.read_text()
    normalized = " ".join(sql.lower().split())
    uncommented = re.sub(r"--.*", "", sql.lower())

    assert "create table if not exists competitor_intel.competitor_intel_observation_key" in normalized
    assert "primary key (domain, product_key, run_id)" in normalized
    assert "create table if not exists competitor_intel.price_stock_observation" in normalized
    assert "partition by range (observed_at)" in normalized
    assert "ensure_price_stock_partition" in normalized
    assert "idx_pso_domain_key_observed_at_desc" in normalized
    assert "domain, product_key, observed_at desc" in normalized
    assert "create or replace view competitor_intel.estimated_sales_daily" in normalized
    assert "lag(stock_qty) over" in normalized
    assert "interval '36 hours'" in normalized
    assert "stock_status in ('in_stock','out_of_stock','unknown')" in normalized
    assert "stock_method in ('visible','cart_probe','unknown')" in normalized
    assert not re.search(r"\b(drop|truncate|delete|update)\b", uncommented)
