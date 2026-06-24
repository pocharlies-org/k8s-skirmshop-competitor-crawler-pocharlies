"""F4 2B tests: ShopifyProber over a scripted fake transport (mock-only)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.prober.contract import (
    CleanupStatus,
    ProbeStatus,
    ProbeTarget,
    StockStatus,
)
from src.prober.killswitch import DomainGuard
from src.prober.metrics import Metrics
from src.prober.shopify import ADD_PATH, CLEAR_PATH, ShopifyProber
from src.prober.transport import ProbeResponse, ProbeTransport, TransportError

OBSERVED_AT = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    """Fake transport: ``add_fn(qty)`` scripts adds; clear returns ``clear_code``.

    Records every call so tests can assert exactly what hit the network.
    """

    def __init__(self, add_fn, *, clear_code: int = 200, clear_exc=None) -> None:
        self._add_fn = add_fn
        self._clear_code = clear_code
        self._clear_exc = clear_exc
        self.calls = []  # list of (method, url, json)

    def request(self, method, url, json=None):
        self.calls.append((method, url, json))
        if url.endswith(CLEAR_PATH):
            if self._clear_exc is not None:
                raise self._clear_exc
            return ProbeResponse(status_code=self._clear_code)
        assert url.endswith(ADD_PATH), url
        return self._add_fn(json["quantity"])

    # convenience views ----------------------------------------------------
    @property
    def add_calls(self):
        return [c for c in self.calls if c[1].endswith(ADD_PATH)]

    @property
    def clear_calls(self):
        return [c for c in self.calls if c[1].endswith(CLEAR_PATH)]


def _target() -> ProbeTarget:
    return ProbeTarget(
        domain="shop.example.com",
        product_key="sku-1",
        url="https://shop.example.com/products/widget/",
        platform="shopify",
        variant_id="40123",
    )


def _prober(transport, guard=None, metrics=None, **kw):
    metrics = metrics or Metrics()
    guard = guard or DomainGuard(metrics)
    return ShopifyProber(transport, guard, metrics, **kw), guard, metrics


def _resp422(description: str) -> ProbeResponse:
    return ProbeResponse(status_code=422, json_body={"description": description})


def test_recording_transport_satisfies_protocol():
    assert isinstance(FakeTransport(lambda q: ProbeResponse(200)), ProbeTransport)


def test_422_leaks_exact_stock_no_cleanup():
    # 422 message leaks remaining inventory; nothing is ever added to the cart.
    transport = FakeTransport(
        lambda q: _resp422("You can only add 5 of this item to your cart.")
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty == 5
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    # Single add, no cleanup (nothing was added).
    assert len(transport.add_calls) == 1
    assert transport.clear_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="probed"
    ) == 1


def test_422_sold_out_is_unavailable():
    transport = FakeTransport(lambda q: _resp422("This product is sold out."))
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.UNAVAILABLE
    assert result.stock_status == StockStatus.OUT_OF_STOCK.value
    assert result.stock_qty == 0
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.clear_calls == []


def test_binary_search_fallback_finds_max():
    # Unparseable 422 forces the qty=1 fallback + exponential/binary search.
    # Adds of qty <= 7 succeed (200); larger adds return an unparseable 422.
    def add_fn(qty):
        if qty <= 7:
            return ProbeResponse(status_code=200, json_body={"ok": True})
        return _resp422("Cart error, please retry.")

    transport = FakeTransport(add_fn)
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_qty == 7
    # An add succeeded, so the cart was cleared exactly once.
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert len(transport.clear_calls) == 1
    # high_qty (99) add came first and was the unparseable 422 trigger.
    assert transport.add_calls[0][2]["quantity"] == 99


def test_high_qty_accepted_uncapped():
    # Every add up to max_qty succeeds -> inventory is reported uncapped (None).
    transport = FakeTransport(
        lambda q: ProbeResponse(status_code=200, json_body={"ok": True})
    )
    prober, _guard, metrics = _prober(transport, max_qty=10000)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty is None  # uncapped
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert len(transport.clear_calls) == 1
    # Search never tries to add more than the cap.
    assert max(c[2]["quantity"] for c in transport.add_calls) == 10000


@pytest.mark.parametrize(
    "first_resp,reason",
    [
        (ProbeResponse(status_code=429), "429"),
        (ProbeResponse(status_code=403, is_challenge=True), "challenge"),
    ],
)
def test_antibot_blocks_and_trips_cooldown(first_resp, reason):
    transport = FakeTransport(lambda q: first_resp)
    metrics = Metrics()
    guard = DomainGuard(metrics)
    prober, _guard, _metrics = _prober(transport, guard=guard, metrics=metrics)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.BLOCKED
    assert result.block_reason == reason
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED  # nothing added
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="blocked"
    ) == 1
    assert metrics.block_value(domain="shop.example.com", reason=reason) == 1

    # Cooldown now active: the next probe is refused without touching network.
    transport.calls.clear()
    second = prober.probe(_target(), OBSERVED_AT)
    assert second.probe_status is ProbeStatus.BLOCKED
    assert second.block_reason == "cooldown_active"
    assert transport.calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="blocked"
    ) == 2


def test_cleanup_failure_after_add_is_error_dirty():
    # An add succeeds (via the unparseable-422 fallback) but cleanup returns
    # 500 -> the cart may be dirty, so the probe is demoted to ERROR/DIRTY.
    def add_fn(qty):
        if qty <= 3:
            return ProbeResponse(status_code=200, json_body={"ok": True})
        return ProbeResponse(status_code=422, json_body={"description": "cart error"})

    transport = FakeTransport(add_fn, clear_code=500)
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "cart_cleanup_failed"
    assert result.cleanup_status is CleanupStatus.DIRTY
    assert result.stock_qty is None
    assert len(transport.clear_calls) == 1
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="error"
    ) == 1


def test_unexpected_status_on_fallback_is_error_no_cleanup():
    # high_qty add is an unparseable 422 -> fall back to qty=1, which returns an
    # unexpected 500. That carries no stock meaning, so it must become ERROR
    # unexpected_status_500 (never silently capped/unavailable). Nothing was
    # ever added (no 200), so no cleanup is attempted.
    def add_fn(qty):
        if qty == 1:
            return ProbeResponse(status_code=500, json_body={"err": "boom"})
        return _resp422("Cart error, please retry.")

    transport = FakeTransport(add_fn)
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "unexpected_status_500"
    assert result.stock_qty is None
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.clear_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="error"
    ) == 1


def test_unexpected_status_during_binary_search_is_error_with_cleanup():
    # Unparseable 422 forces the qty=1 fallback; qty<=3 adds succeed (200) so the
    # cart is dirty, then a larger add returns an unexpected 500. The result is
    # ERROR unexpected_status_500 and cleanup IS attempted (cart was dirtied).
    def add_fn(qty):
        if qty <= 3:
            return ProbeResponse(status_code=200, json_body={"ok": True})
        if qty == 99:
            return _resp422("Cart error, please retry.")
        return ProbeResponse(status_code=500, json_body={"err": "boom"})

    transport = FakeTransport(add_fn)
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "unexpected_status_500"
    assert result.stock_qty is None
    # An add succeeded, so cleanup was attempted (and here it cleared cleanly).
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert len(transport.clear_calls) == 1
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="error"
    ) == 1


def test_transport_exception_on_add_is_error_no_cleanup():
    def add_fn(qty):
        raise TransportError("connection reset")

    transport = FakeTransport(add_fn)
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "transport_error"
    # Nothing was added, so no cleanup is attempted.
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.clear_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="error"
    ) == 1
