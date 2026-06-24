"""F4 2C tests: WooProber over a scripted fake transport (mock-only)."""
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
from src.prober.transport import ProbeResponse, ProbeTransport, TransportError
from src.prober.woo import ADD_PATH, REMOVE_PATH, WooProber

OBSERVED_AT = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)


class FakeTransport:
    """Fake transport: ``add_resp`` scripts the add; remove returns ``remove_code``.

    Records every call so tests can assert exactly what hit the network.
    """

    def __init__(self, add_resp, *, remove_code: int = 200, remove_exc=None) -> None:
        self._add_resp = add_resp
        self._remove_code = remove_code
        self._remove_exc = remove_exc
        self.calls = []  # list of (method, url, json)

    def request(self, method, url, json=None):
        self.calls.append((method, url, json))
        if url.endswith(REMOVE_PATH):
            if self._remove_exc is not None:
                raise self._remove_exc
            return ProbeResponse(status_code=self._remove_code)
        assert url.endswith(ADD_PATH), url
        if isinstance(self._add_resp, Exception):
            raise self._add_resp
        return self._add_resp

    @property
    def add_calls(self):
        return [c for c in self.calls if c[1].endswith(ADD_PATH)]

    @property
    def remove_calls(self):
        return [c for c in self.calls if c[1].endswith(REMOVE_PATH)]


def _target() -> ProbeTarget:
    return ProbeTarget(
        domain="shop.example.com",
        product_key="sku-1",
        url="https://shop.example.com/product/widget/",
        platform="woocommerce",
        variant_id="40123",
    )


def _prober(transport, guard=None, metrics=None):
    metrics = metrics or Metrics()
    guard = guard or DomainGuard(metrics)
    return WooProber(transport, guard, metrics), guard, metrics


def test_recording_transport_satisfies_protocol():
    assert isinstance(FakeTransport(ProbeResponse(200)), ProbeTransport)


def test_quantity_limit_maximum_leaks_stock_with_cleanup():
    transport = FakeTransport(
        ProbeResponse(
            status_code=200,
            json_body={"quantity_limits": {"minimum": 1, "maximum": 5}},
        )
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty == 5
    # The add put an item in the cart, so it was removed and verified once.
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert len(transport.add_calls) == 1
    assert transport.add_calls[0][2] == {"id": "40123", "quantity": 1}
    assert len(transport.remove_calls) == 1
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="probed"
    ) == 1


def test_200_without_maximum_is_probed_qty_none_with_cleanup():
    transport = FakeTransport(
        ProbeResponse(status_code=200, json_body={"items": [{"id": 1}]})
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty is None  # in stock, unknown finite cap
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert len(transport.remove_calls) == 1


def test_out_of_stock_error_is_unavailable_no_cleanup():
    transport = FakeTransport(
        ProbeResponse(
            status_code=400,
            json_body={
                "code": "woocommerce_rest_product_out_of_stock",
                "message": "This product is out of stock.",
            },
        )
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.UNAVAILABLE
    assert result.stock_status == StockStatus.OUT_OF_STOCK.value
    assert result.stock_qty == 0
    # Nothing was added, so no cleanup is attempted.
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.remove_calls == []


@pytest.mark.parametrize(
    "add_resp,reason",
    [
        (ProbeResponse(status_code=403), "403"),
        (ProbeResponse(status_code=429), "429"),
        (ProbeResponse(status_code=200, is_challenge=True), "challenge"),
    ],
)
def test_antibot_blocks_and_trips_cooldown(add_resp, reason):
    transport = FakeTransport(add_resp)
    metrics = Metrics()
    guard = DomainGuard(metrics)
    prober, _guard, _metrics = _prober(transport, guard=guard, metrics=metrics)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.BLOCKED
    assert result.block_reason == reason
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED  # nothing added
    assert transport.remove_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="blocked"
    ) == 1
    assert metrics.block_value(domain="shop.example.com", reason=reason) == 1

    # Cooldown now active: the next probe is refused without touching network.
    transport.calls.clear()
    second = prober.probe(_target(), OBSERVED_AT)
    assert second.probe_status is ProbeStatus.BLOCKED
    assert second.block_reason == "cooldown_active"
    assert transport.calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="blocked"
    ) == 2


def test_cleanup_failure_after_add_is_error_dirty():
    transport = FakeTransport(
        ProbeResponse(
            status_code=200,
            json_body={"quantity_limits": {"maximum": 3}},
        ),
        remove_code=500,
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "cart_cleanup_failed"
    assert result.cleanup_status is CleanupStatus.DIRTY
    assert result.stock_qty is None
    assert len(transport.remove_calls) == 1
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="error"
    ) == 1


def test_unexpected_status_is_error_no_cleanup():
    transport = FakeTransport(
        ProbeResponse(status_code=500, json_body={"err": "boom"})
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "unexpected_status_500"
    assert result.stock_qty is None
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.remove_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="error"
    ) == 1


def test_transport_exception_before_add_is_error_no_cleanup():
    transport = FakeTransport(TransportError("connection reset"))
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "transport_error"
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.remove_calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="woocommerce", status="error"
    ) == 1
