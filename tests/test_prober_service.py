"""F4 2D tests: probe_stock facade dispatch over scripted fakes (mock-only)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.prober.contract import ProbeStatus, ProbeTarget, StockStatus
from src.prober.generic import NO_SAFE_PATTERN
from src.prober.killswitch import DomainGuard
from src.prober.metrics import Metrics
from src.prober.service import probe_stock
from src.prober.shopify import ADD_PATH as SHOPIFY_ADD_PATH
from src.prober.shopify import CLEAR_PATH as SHOPIFY_CLEAR_PATH
from src.prober.transport import ProbeResponse
from src.prober.woo import ADD_PATH as WOO_ADD_PATH
from src.prober.woo import REMOVE_PATH as WOO_REMOVE_PATH

OBSERVED_AT = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)


class RecordingTransport:
    """Scripted fake: ``responder(method, url, json)`` returns a ProbeResponse.

    Records every call so tests can assert exactly what hit the network. A
    default-deny path is verified by asserting ``calls == []``.
    """

    def __init__(self, responder=None) -> None:
        self._responder = responder
        self.calls = []

    def request(self, method, url, json=None):
        self.calls.append((method, url, json))
        if self._responder is None:  # pragma: no cover - must not run
            raise AssertionError("transport must not be called")
        return self._responder(method, url, json)


def _setup():
    metrics = Metrics()
    guard = DomainGuard(metrics)
    return metrics, guard


def test_shopify_target_dispatches_to_shopify_prober():
    # 422 leaks exact remaining stock; nothing is added to the cart.
    def responder(method, url, json):
        assert url.endswith(SHOPIFY_ADD_PATH), url
        return ProbeResponse(
            status_code=422,
            json_body={"description": "You can only add 3 of this item to your cart."},
        )

    transport = RecordingTransport(responder)
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="shop.example.com",
        product_key="sku-1",
        url="https://shop.example.com/products/widget/",
        platform="shopify",
        variant_id="40123",
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty == 3
    # Routed to Shopify (cart/add.js), single add, no double metric increment.
    assert all(c[1].endswith(SHOPIFY_ADD_PATH) for c in transport.calls)
    assert len(transport.calls) == 1
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="probed"
    ) == 1


def test_woo_target_dispatches_to_woo_prober_maximum_path():
    def responder(method, url, json):
        if url.endswith(WOO_REMOVE_PATH):
            return ProbeResponse(status_code=200)
        assert url.endswith(WOO_ADD_PATH), url
        return ProbeResponse(
            status_code=200,
            json_body={"quantity_limits": {"minimum": 1, "maximum": 7}},
        )

    transport = RecordingTransport(responder)
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="woo.example.com",
        product_key="sku-2",
        url="https://woo.example.com/product/widget/",
        platform="woocommerce",
        variant_id="55",
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_qty == 7
    # Routed to the Woo Store API add + verified remove cleanup.
    assert any(c[1].endswith(WOO_ADD_PATH) for c in transport.calls)
    assert any(c[1].endswith(WOO_REMOVE_PATH) for c in transport.calls)
    assert metrics.probe_value(
        domain="woo.example.com", platform="woocommerce", status="probed"
    ) == 1


@pytest.mark.parametrize("platform", ["woo", "woocommerce"])
def test_woo_alias_both_dispatch(platform):
    def responder(method, url, json):
        if url.endswith(WOO_REMOVE_PATH):
            return ProbeResponse(status_code=200)
        return ProbeResponse(status_code=200, json_body={"items": [{"id": 1}]})

    transport = RecordingTransport(responder)
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="woo.example.com",
        product_key="sku-2",
        url="https://woo.example.com/product/widget/",
        platform=platform,
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)
    assert result.probe_status is ProbeStatus.PROBED


def test_generic_html_target_dispatches_generic_zero_network():
    transport = RecordingTransport()  # no responder: any call raises
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="example.com",
        product_key="sku-3",
        url="https://example.com/p/1",
        platform="generic_html",
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.SKIPPED
    assert result.error_code == NO_SAFE_PATTERN
    assert transport.calls == []
    assert metrics.probe_value(
        domain="example.com", platform="generic", status=ProbeStatus.SKIPPED.value
    ) == 1


def test_airsoftquimera_target_dispatches_to_approved_adapter():
    def responder(method, url, json):
        assert method == "GET"
        assert url.endswith("/cacc_4_50_1_15229_10_0/"), url
        return ProbeResponse(
            status_code=200,
            text="Actualmente tenemos en stock 6",
        )

    transport = RecordingTransport(responder)
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="airsoftquimera.com",
        product_key="competitor:airsoftquimera.com:15229",
        url=(
            "https://www.airsoftquimera.com/"
            "cargador-midcap-para-m4-200bbs-tornado-p-4-50-15229/"
        ),
        platform="airsoftquimera",
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_qty == 6
    assert metrics.probe_value(
        domain="airsoftquimera.com",
        platform="airsoftquimera",
        status=ProbeStatus.PROBED.value,
    ) == 1


def test_unknown_platform_default_deny_zero_network():
    transport = RecordingTransport()  # no responder: any call raises
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="weird.example.com",
        product_key="sku-4",
        url="https://weird.example.com/p/1",
        platform="bigcommerce",
    )

    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.SKIPPED
    assert result.error_code == NO_SAFE_PATTERN
    assert transport.calls == []
    assert metrics.probe_value(
        domain="weird.example.com",
        platform="generic",
        status=ProbeStatus.SKIPPED.value,
    ) == 1


def test_cooldown_active_before_shopify_returns_blocked_zero_network():
    metrics, guard = _setup()
    target = ProbeTarget(
        domain="shop.example.com",
        product_key="sku-1",
        url="https://shop.example.com/products/widget/",
        platform="shopify",
        variant_id="40123",
    )
    # Trip the domain into cooldown before the probe runs.
    guard.record_block(target.domain, "429", OBSERVED_AT)

    transport = RecordingTransport()  # no responder: any call raises
    result = probe_stock(target, transport, guard, metrics, OBSERVED_AT)

    assert result.probe_status is ProbeStatus.BLOCKED
    assert result.block_reason == "cooldown_active"
    # The prober's guard short-circuits: nothing hit the network.
    assert transport.calls == []
    assert metrics.probe_value(
        domain="shop.example.com", platform="shopify", status="blocked"
    ) == 1
