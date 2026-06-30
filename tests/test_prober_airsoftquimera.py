"""B1 tests: AirsoftQuimera approved-domain prober over fake transport."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.prober.airsoftquimera import AirsoftQuimeraProber
from src.prober.contract import CleanupStatus, ProbeStatus, ProbeTarget, StockStatus
from src.prober.killswitch import DomainGuard
from src.prober.metrics import Metrics
from src.prober.transport import ProbeResponse, TransportError

OBSERVED_AT = datetime(2026, 6, 30, 0, 0, tzinfo=timezone.utc)


class FakeTransport:
    def __init__(self, add_resp, *, cleanup_resp=None) -> None:
        self._add_resp = add_resp
        self._cleanup_resp = cleanup_resp or ProbeResponse(status_code=200)
        self.calls = []

    def request(self, method, url, json=None):
        self.calls.append((method, url, json))
        if "cacc_4_50_2_" in url:
            if isinstance(self._cleanup_resp, Exception):
                raise self._cleanup_resp
            return self._cleanup_resp
        if isinstance(self._add_resp, Exception):
            raise self._add_resp
        return self._add_resp

    @property
    def add_calls(self):
        return [call for call in self.calls if "cacc_4_50_1_" in call[1]]

    @property
    def cleanup_calls(self):
        return [call for call in self.calls if "cacc_4_50_2_" in call[1]]


def _target(**overrides) -> ProbeTarget:
    values = {
        "domain": "airsoftquimera.com",
        "product_key": "competitor:airsoftquimera.com:15229",
        "url": (
            "https://www.airsoftquimera.com/"
            "cargador-midcap-para-m4-200bbs-tornado-p-4-50-15229/"
        ),
        "platform": "airsoftquimera",
        "variant_id": None,
    }
    values.update(overrides)
    return ProbeTarget(**values)


def _prober(transport, *, metrics=None, guard=None, max_qty=10):
    metrics = metrics or Metrics()
    guard = guard or DomainGuard(metrics)
    return AirsoftQuimeraProber(
        transport,
        guard,
        metrics,
        max_qty=max_qty,
    ), guard, metrics


def test_limit_response_reports_exact_stock_without_cleanup():
    transport = FakeTransport(
        ProbeResponse(
            status_code=200,
            text="No tenemos tantas unidades en stock de ese producto. "
            "Actualmente tenemos en stock 6",
        )
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty == 6
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert len(transport.add_calls) == 1
    assert transport.add_calls[0][1].endswith("/cacc_4_50_1_15229_10_0/")
    assert transport.cleanup_calls == []
    assert metrics.probe_value(
        domain="airsoftquimera.com", platform="airsoftquimera", status="probed"
    ) == 1


def test_successful_add_is_cleaned_and_reports_in_stock_unknown_ceiling():
    transport = FakeTransport(
        ProbeResponse(status_code=200, text="Producto añadido a su selección")
    )
    prober, _guard, _metrics = _prober(transport, max_qty=5)

    result = prober.probe(_target(variant_id="22046"), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.PROBED
    assert result.stock_status == StockStatus.IN_STOCK.value
    assert result.stock_qty is None
    assert result.cleanup_status is CleanupStatus.CLEAN
    assert transport.add_calls[0][1].endswith("/cacc_4_50_1_22046_5_0/")
    assert transport.cleanup_calls[0][1].endswith("/cacc_4_50_2_22046_0_0/")


def test_cleanup_failure_demotes_to_error_dirty():
    transport = FakeTransport(
        ProbeResponse(status_code=200, text="Producto añadido a su selección"),
        cleanup_resp=ProbeResponse(status_code=500),
    )
    prober, _guard, metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "cart_cleanup_failed"
    assert result.cleanup_status is CleanupStatus.DIRTY
    assert result.stock_qty is None
    assert metrics.probe_value(
        domain="airsoftquimera.com", platform="airsoftquimera", status="error"
    ) == 1


def test_503_blocks_and_trips_cooldown():
    transport = FakeTransport(ProbeResponse(status_code=503, text="temporary wall"))
    metrics = Metrics()
    guard = DomainGuard(metrics)
    prober, _guard, _metrics = _prober(transport, metrics=metrics, guard=guard)

    first = prober.probe(_target(), OBSERVED_AT)

    assert first.probe_status is ProbeStatus.BLOCKED
    assert first.block_reason == "503"
    assert metrics.block_value(domain="airsoftquimera.com", reason="503") == 1

    transport.calls.clear()
    second = prober.probe(_target(), OBSERVED_AT)
    assert second.probe_status is ProbeStatus.BLOCKED
    assert second.block_reason == "cooldown_active"
    assert transport.calls == []


def test_transport_error_is_error_without_cleanup():
    transport = FakeTransport(TransportError("timeout"))
    prober, _guard, _metrics = _prober(transport)

    result = prober.probe(_target(), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "transport_error"
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert transport.cleanup_calls == []


def test_missing_product_id_returns_error_without_network():
    transport = FakeTransport(ProbeResponse(status_code=200))
    prober, _guard, _metrics = _prober(transport)

    result = prober.probe(_target(url="https://www.airsoftquimera.com/no-id/"), OBSERVED_AT)

    assert result.probe_status is ProbeStatus.ERROR
    assert result.error_code == "product_id_missing"
    assert transport.calls == []


def test_max_qty_above_b1_ceiling_is_rejected():
    with pytest.raises(ValueError, match="max_qty"):
        _prober(FakeTransport(ProbeResponse(status_code=200)), max_qty=11)
