"""GenericProber - default-deny for unrecognised platforms (mock-only).

A generic domain has no proven-safe add-to-cart pattern, so F4 refuses to
touch the network: the prober makes **zero** transport calls and returns a
SKIPPED result with ``error_code=no_safe_pattern``. A domain may only be probed
once an explicit per-domain pattern is allowlisted and covered by tests
(architect decision: generic probing is default-deny).
"""
from __future__ import annotations

from datetime import datetime

from .contract import CleanupStatus, ProbeResult, ProbeStatus, ProbeTarget, StockStatus
from .metrics import Metrics
from .transport import ProbeTransport

NO_SAFE_PATTERN = "no_safe_pattern"


class GenericProber:
    platform = "generic"

    def __init__(self, transport: ProbeTransport, metrics: Metrics) -> None:
        # Transport is accepted for a uniform constructor but never used: a
        # generic probe must not issue any request.
        self._transport = transport
        self._metrics = metrics

    def probe(self, target: ProbeTarget, observed_at: datetime) -> ProbeResult:
        self._metrics.inc_probe(
            domain=target.domain,
            platform=self.platform,
            status=ProbeStatus.SKIPPED.value,
        )
        return ProbeResult(
            domain=target.domain,
            product_key=target.product_key,
            url=target.url,
            platform=target.platform,
            observed_at=observed_at,
            variant_id=target.variant_id,
            probe_status=ProbeStatus.SKIPPED,
            stock_status=StockStatus.UNKNOWN.value,
            stock_qty=None,
            block_reason=None,
            error_code=NO_SAFE_PATTERN,
            cleanup_status=CleanupStatus.NOT_NEEDED,
        )


__all__ = ["GenericProber", "NO_SAFE_PATTERN"]
