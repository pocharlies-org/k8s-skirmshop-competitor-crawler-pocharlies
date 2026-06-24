"""F4 2A tests: minimal transport value object + default-deny GenericProber."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.prober.contract import (
    CleanupStatus,
    ProbeStatus,
    ProbeTarget,
    StockStatus,
)
from src.prober.generic import NO_SAFE_PATTERN, GenericProber
from src.prober.metrics import Metrics
from src.prober.transport import ProbeResponse, ProbeTransport

OBSERVED_AT = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)


class RecordingTransport:
    """Fake transport that fails loudly if the prober ever calls it."""

    def __init__(self) -> None:
        self.calls = []

    def request(self, method, url, json=None):  # pragma: no cover - must not run
        self.calls.append((method, url, json))
        raise AssertionError("GenericProber must not touch the transport")


def _target() -> ProbeTarget:
    return ProbeTarget(
        domain="example.com",
        product_key="sku-1",
        url="https://example.com/p/1",
        platform="generic",
    )


def test_generic_default_deny_skips_without_network():
    transport = RecordingTransport()
    metrics = Metrics()
    prober = GenericProber(transport, metrics)

    result = prober.probe(_target(), OBSERVED_AT)

    # Default-deny outcome.
    assert result.probe_status is ProbeStatus.SKIPPED
    assert result.stock_status == StockStatus.UNKNOWN.value
    assert result.stock_qty is None
    assert result.block_reason is None
    assert result.cleanup_status is CleanupStatus.NOT_NEEDED
    assert result.error_code == NO_SAFE_PATTERN
    assert result.observed_at == OBSERVED_AT

    # No network was touched.
    assert transport.calls == []

    # Metric incremented exactly once for the skipped probe.
    assert metrics.probe_value(
        domain="example.com", platform="generic", status=ProbeStatus.SKIPPED.value
    ) == 1


def test_recording_transport_satisfies_protocol():
    assert isinstance(RecordingTransport(), ProbeTransport)


def test_probe_response_json_empty_when_none():
    resp = ProbeResponse(status_code=204)
    assert resp.json_body is None
    assert resp.is_challenge is False
    assert resp.json() == {}


def test_probe_response_json_returns_body():
    resp = ProbeResponse(status_code=200, json_body={"ok": True})
    assert resp.json() == {"ok": True}
    # json() returns a copy, not the stored mapping.
    resp.json()["ok"] = False
    assert resp.json() == {"ok": True}


@pytest.mark.parametrize("is_challenge", [True, False])
def test_probe_response_challenge_flag(is_challenge):
    resp = ProbeResponse(status_code=403, is_challenge=is_challenge)
    assert resp.is_challenge is is_challenge
