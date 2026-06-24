"""F4 cart-probe contract / kill-switch / metrics tests."""
from datetime import datetime, timedelta, timezone

import pytest

from src.history_writer import Observation, write_observations
from src.prober.contract import (
    CleanupStatus,
    ProbeResult,
    ProbeStatus,
    StockStatus,
    probe_result_to_observation,
)
from src.prober.killswitch import DEFAULT_COOLDOWN, DomainGuard
from src.prober.metrics import CRAWL_BLOCK_TOTAL, PROBE_TOTAL, Metrics

T0 = datetime(2026, 6, 25, 8, 0, tzinfo=timezone.utc)
RUN_ID = "run-f4-0001"


# --- fake F3 connection (mirrors tests/test_history_writer.py) -------------
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


def _probed(qty):
    return ProbeResult(
        domain="shop.example.com",
        product_key="gid://1",
        url="https://shop.example.com/p/1",
        platform="shopify",
        observed_at=T0,
        probe_status=ProbeStatus.PROBED,
        stock_status=StockStatus.IN_STOCK.value,
        stock_qty=qty,
        cleanup_status=CleanupStatus.CLEAN,
    )


# --- F3 mapper -------------------------------------------------------------
def test_probed_exact_qty_maps_and_writes_idempotently():
    result = _probed(7)
    obs = probe_result_to_observation(result, RUN_ID)

    assert isinstance(obs, Observation)
    assert obs.stock_method == "cart_probe"
    assert obs.stock_qty == 7
    assert obs.stock_status == "in_stock"
    assert obs.crawl_success is True
    assert obs.error_code is None

    conn = FakeConnection()
    first = write_observations(conn, [obs])
    second = write_observations(conn, [obs])
    assert first.inserted == 1 and first.skipped == 0
    assert second.inserted == 0 and second.skipped == 1
    assert len(conn.observation_rows) == 1  # idempotent: no duplicate row


def test_uncapped_in_stock_qty_none_is_allowed():
    result = _probed(None)  # uncapped inventory
    assert result.stock_qty is None
    obs = probe_result_to_observation(result, RUN_ID)
    assert obs.stock_qty is None
    assert obs.stock_status == "in_stock"
    assert obs.crawl_success is True


# --- validation matrix -----------------------------------------------------
def test_blocked_with_qty_raises():
    with pytest.raises(ValueError):
        ProbeResult(
            domain="shop.example.com",
            product_key="gid://1",
            url="https://shop.example.com/p/1",
            platform="shopify",
            observed_at=T0,
            probe_status=ProbeStatus.BLOCKED,
            stock_status=StockStatus.UNKNOWN.value,
            stock_qty=3,
            block_reason="429",
        )


def test_error_without_error_code_raises():
    with pytest.raises(ValueError):
        ProbeResult(
            domain="shop.example.com",
            product_key="gid://1",
            url="https://shop.example.com/p/1",
            platform="shopify",
            observed_at=T0,
            probe_status=ProbeStatus.ERROR,
            stock_status=StockStatus.UNKNOWN.value,
        )


# --- DomainGuard / cooldown ------------------------------------------------
def test_domain_guard_trip_then_cooldown_blocks_and_increments_metric():
    metrics = Metrics()
    guard = DomainGuard(metrics)

    assert DEFAULT_COOLDOWN == timedelta(hours=36)

    # Clear domain -> no guard result.
    assert guard.guard_result(
        "shop.example.com", "gid://1", "https://x/1", "shopify", T0
    ) is None

    # Trip on a 429.
    guard.record_block("shop.example.com", "429", T0)
    assert guard.is_blocked("shop.example.com", T0 + timedelta(hours=1)) is True

    blocked = guard.guard_result(
        "shop.example.com",
        "gid://1",
        "https://x/1",
        "shopify",
        T0 + timedelta(hours=1),
    )
    assert blocked is not None
    assert blocked.probe_status is ProbeStatus.BLOCKED
    assert blocked.block_reason == "cooldown_active"
    assert blocked.stock_status == "unknown"
    assert blocked.stock_qty is None

    # One increment for the trip (429) + one for the cooldown refusal.
    assert metrics.get(CRAWL_BLOCK_TOTAL, domain="shop.example.com", reason="429") == 1
    assert (
        metrics.get(
            CRAWL_BLOCK_TOTAL, domain="shop.example.com", reason="cooldown_active"
        )
        == 1
    )

    # Cooldown elapsed -> domain clears, probing allowed again.
    assert guard.is_blocked("shop.example.com", T0 + timedelta(hours=37)) is False
    assert guard.guard_result(
        "shop.example.com", "gid://1", "https://x/1", "shopify", T0 + timedelta(hours=37)
    ) is None


# --- metrics labels --------------------------------------------------------
def test_metric_counter_labels_are_independent():
    metrics = Metrics()
    metrics.inc_probe(domain="a.com", platform="shopify", status="probed")
    metrics.inc_probe(domain="a.com", platform="shopify", status="probed")
    metrics.inc_probe(domain="a.com", platform="woo", status="probed")
    metrics.inc_block(domain="a.com", reason="403")

    assert metrics.get(PROBE_TOTAL, domain="a.com", platform="shopify", status="probed") == 2
    assert metrics.get(PROBE_TOTAL, domain="a.com", platform="woo", status="probed") == 1
    assert metrics.get(PROBE_TOTAL, domain="a.com", platform="shopify", status="error") == 0
    assert metrics.get(CRAWL_BLOCK_TOTAL, domain="a.com", reason="403") == 1

    snap = metrics.snapshot()
    assert (PROBE_TOTAL, {"domain": "a.com", "platform": "shopify", "status": "probed"}, 2) in snap
    assert (CRAWL_BLOCK_TOTAL, {"domain": "a.com", "reason": "403"}, 1) in snap
