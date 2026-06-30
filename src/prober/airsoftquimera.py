"""Approved AirsoftQuimera path-based stock prober.

The adapter is limited to the pattern calibrated in F4:

* add: ``/cacc_4_50_1_<product_id>_<qty>_0/``
* remove: ``/cacc_4_50_2_<product_id>_0_0/``

It probes a conservative ceiling (default 10) and returns exact stock only when
the site responds with its own LIMIT(N) text.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from .contract import (
    CleanupStatus,
    ProbeResult,
    ProbeStatus,
    ProbeTarget,
    StockStatus,
)
from .killswitch import DomainGuard
from .metrics import Metrics
from .transport import ProbeResponse, ProbeTransport, TransportError

PLATFORM = "airsoftquimera"
APPROVED_DOMAIN = "airsoftquimera.com"
DEFAULT_MAX_QTY = 10

ERROR_TRANSPORT = "transport_error"
ERROR_CLEANUP_FAILED = "cart_cleanup_failed"
ERROR_PRODUCT_ID_MISSING = "product_id_missing"
ERROR_UNEXPECTED_RESPONSE = "unexpected_response"

_PRODUCT_ID_RE = re.compile(r"-p-4-50-(\d+)/?$")
_LIMIT_RE = re.compile(r"actualmente\s+tenemos\s+en\s+stock\s+(\d+)", re.I)
_ADDED_MARKERS = (
    "producto añadido",
    "producto anadido",
    "añadido a su selección",
    "anadido a su seleccion",
)
_SOLD_OUT_MARKERS = (
    "sin stock",
    "agotado",
    "no disponible",
)


class AirsoftQuimeraProber:
    platform = PLATFORM

    def __init__(
        self,
        transport: ProbeTransport,
        guard: DomainGuard,
        metrics: Metrics,
        *,
        max_qty: int = DEFAULT_MAX_QTY,
    ) -> None:
        if not 1 <= max_qty <= DEFAULT_MAX_QTY:
            raise ValueError(f"max_qty must be between 1 and {DEFAULT_MAX_QTY}")
        self._transport = transport
        self._guard = guard
        self._metrics = metrics
        self._max_qty = max_qty

    def probe(self, target: ProbeTarget, observed_at: datetime) -> ProbeResult:
        guarded = self._guard.guard_result(
            target.domain,
            target.product_key,
            target.url,
            target.platform,
            observed_at,
        )
        if guarded is not None:
            self._metrics.inc_probe(
                domain=target.domain,
                platform=self.platform,
                status=guarded.probe_status.value,
            )
            return guarded

        product_id = _product_id(target)
        if product_id is None:
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.ERROR,
                error_code=ERROR_PRODUCT_ID_MISSING,
            )

        origin = _origin(target.url)
        add_url = f"{origin}/cacc_4_50_1_{product_id}_{self._max_qty}_0/"
        remove_url = f"{origin}/cacc_4_50_2_{product_id}_0_0/"

        try:
            resp = self._transport.request("GET", add_url)
        except TransportError:
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.ERROR,
                error_code=ERROR_TRANSPORT,
            )

        reason = _block_reason(resp)
        if reason is not None:
            self._guard.record_block(target.domain, reason, observed_at)
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.BLOCKED,
                block_reason=reason,
            )

        classified = _classify(resp)
        if classified.kind == "limit":
            if classified.qty == 0:
                return self._result(
                    target,
                    observed_at,
                    probe_status=ProbeStatus.UNAVAILABLE,
                    stock_status=StockStatus.OUT_OF_STOCK.value,
                    stock_qty=0,
                )
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.PROBED,
                stock_status=StockStatus.IN_STOCK.value,
                stock_qty=classified.qty,
            )
        if classified.kind == "sold_out":
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.UNAVAILABLE,
                stock_status=StockStatus.OUT_OF_STOCK.value,
                stock_qty=0,
            )
        if classified.kind == "added":
            if self._cleanup(remove_url):
                return self._result(
                    target,
                    observed_at,
                    probe_status=ProbeStatus.PROBED,
                    stock_status=StockStatus.IN_STOCK.value,
                    stock_qty=None,
                    cleanup_status=CleanupStatus.CLEAN,
                )
            return self._result(
                target,
                observed_at,
                probe_status=ProbeStatus.ERROR,
                error_code=ERROR_CLEANUP_FAILED,
                cleanup_status=CleanupStatus.DIRTY,
            )

        cleanup_status = CleanupStatus.NOT_NEEDED
        if resp.status_code == 200:
            cleanup_status = (
                CleanupStatus.CLEAN if self._cleanup(remove_url) else CleanupStatus.DIRTY
            )
        error_code = ERROR_UNEXPECTED_RESPONSE
        if resp.status_code != 200:
            error_code = f"unexpected_status_{resp.status_code}"
        return self._result(
            target,
            observed_at,
            probe_status=ProbeStatus.ERROR,
            error_code=error_code,
            cleanup_status=cleanup_status,
        )

    def _cleanup(self, remove_url: str) -> bool:
        try:
            resp = self._transport.request("GET", remove_url)
        except TransportError:
            return False
        return resp.status_code == 200 and not resp.is_challenge

    def _result(
        self,
        target: ProbeTarget,
        observed_at: datetime,
        *,
        probe_status: ProbeStatus,
        stock_status: str = StockStatus.UNKNOWN.value,
        stock_qty: Optional[int] = None,
        block_reason: str | None = None,
        error_code: str | None = None,
        cleanup_status: CleanupStatus = CleanupStatus.NOT_NEEDED,
    ) -> ProbeResult:
        result = ProbeResult(
            domain=target.domain,
            product_key=target.product_key,
            url=target.url,
            platform=target.platform,
            observed_at=observed_at,
            variant_id=target.variant_id,
            probe_status=probe_status,
            stock_status=stock_status,
            stock_qty=stock_qty,
            block_reason=block_reason,
            error_code=error_code,
            cleanup_status=cleanup_status,
        )
        self._metrics.inc_probe(
            domain=target.domain,
            platform=self.platform,
            status=result.probe_status.value,
        )
        return result


class _Classified:
    def __init__(self, kind: str, qty: int | None = None) -> None:
        self.kind = kind
        self.qty = qty


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("target.url must be absolute http(s)")
    return f"{parsed.scheme}://{parsed.netloc}"


def _product_id(target: ProbeTarget) -> str | None:
    if target.variant_id and str(target.variant_id).isdigit():
        return str(target.variant_id)
    parsed = urlparse(target.url)
    match = _PRODUCT_ID_RE.search(parsed.path)
    if match is None:
        return None
    return match.group(1)


def _block_reason(resp: ProbeResponse) -> str | None:
    if resp.is_challenge:
        return "challenge"
    if resp.status_code == 403:
        return "403"
    if resp.status_code == 429:
        return "429"
    if resp.status_code == 503:
        return "503"
    return None


def _classify(resp: ProbeResponse) -> _Classified:
    if resp.status_code != 200:
        return _Classified("unexpected")
    text = (resp.text or "").lower()
    match = _LIMIT_RE.search(text)
    if match is not None:
        return _Classified("limit", int(match.group(1)))
    if any(marker in text for marker in _ADDED_MARKERS):
        return _Classified("added")
    if any(marker in text for marker in _SOLD_OUT_MARKERS):
        return _Classified("sold_out")
    return _Classified("unexpected")


__all__ = [
    "AirsoftQuimeraProber",
    "PLATFORM",
    "APPROVED_DOMAIN",
    "DEFAULT_MAX_QTY",
]
