"""WooProber - numeric stock via the WooCommerce Store API cart (mock-only).

WooCommerce storefronts expose the Store API ``POST /wp-json/wc/store/v1/
cart/add-item`` which accepts a product/variation ``id`` and a ``quantity``.
Unlike Shopify's ``add.js`` (which leaks the cap in a 422 message), the Store
API returns a structured cart body whose ``quantity_limits.maximum`` is the
remaining purchasable inventory, so a single ``quantity=1`` add is enough to
read it - no exponential/binary search is needed:

  * a ``200`` whose body carries ``quantity_limits.maximum`` (int) reports that
    exact remaining stock;
  * a ``200`` without a ``maximum`` proves the variant is in stock with an
    unknown finite cap (``stock_qty=None``);
  * a ``400``/``409``/``422`` whose error code/message reads *out of stock* /
    *not purchasable* / *sold out* proves the variant is out of stock;
  * an anti-bot ``403``/``429``/challenge trips the per-domain kill-switch.

Every ``200`` add puts one item in the cart, so it is followed by a verified
remove-item cleanup; a failed cleanup demotes the result to ERROR/DIRTY so a
dirty cart is never silently reported as clean.

This prober is transport-agnostic: it issues no live HTTP and depends only on
the :class:`ProbeTransport` Protocol, so tests drive it with a scripted fake.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

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

ADD_PATH = "/wp-json/wc/store/v1/cart/add-item"
# Store API mock cleanup endpoint: remove the just-added item from the cart.
REMOVE_PATH = "/wp-json/wc/store/v1/cart/remove-item"

# Store API statuses that may carry an out-of-stock / not-purchasable error.
_OOS_STATUSES = frozenset({400, 409, 422})
# Substrings in a Store API error code/message that prove the variant is out
# of stock or otherwise not purchasable.
_OOS_MARKERS = (
    "out_of_stock",
    "out of stock",
    "product_not_purchasable",
    "not purchasable",
    "sold out",
    "sold_out",
)

ERROR_TRANSPORT = "transport_error"
ERROR_CLEANUP_FAILED = "cart_cleanup_failed"


class WooProber:
    platform = "woocommerce"

    def __init__(
        self,
        transport: ProbeTransport,
        guard: DomainGuard,
        metrics: Metrics,
    ) -> None:
        self._transport = transport
        self._guard = guard
        self._metrics = metrics

    # -- public API --------------------------------------------------------
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

        base = target.url.rstrip("/")
        add_url = base + ADD_PATH
        remove_url = base + REMOVE_PATH

        # Whether the add returned 200 (an item is now in the cart).
        added = False
        core: dict
        try:
            resp = self._transport.request(
                "POST",
                add_url,
                json={"id": target.variant_id, "quantity": 1},
            )
            reason = _block_reason(resp)
            if reason is not None:
                self._guard.record_block(target.domain, reason, observed_at)
                core = {
                    "probe_status": ProbeStatus.BLOCKED,
                    "stock_status": StockStatus.UNKNOWN.value,
                    "stock_qty": None,
                    "block_reason": reason,
                }
            elif resp.status_code == 200:
                added = True
                core = _probed(_max_from_body(resp))
            elif resp.status_code in _OOS_STATUSES and _is_out_of_stock(resp):
                core = _unavailable()
            else:
                core = {
                    "probe_status": ProbeStatus.ERROR,
                    "stock_status": StockStatus.UNKNOWN.value,
                    "stock_qty": None,
                    "error_code": f"unexpected_status_{resp.status_code}",
                }
        except TransportError:
            core = {
                "probe_status": ProbeStatus.ERROR,
                "stock_status": StockStatus.UNKNOWN.value,
                "stock_qty": None,
                "error_code": ERROR_TRANSPORT,
            }

        cleanup_status = CleanupStatus.NOT_NEEDED
        if added:
            if self._cleanup(remove_url, target):
                cleanup_status = CleanupStatus.CLEAN
            else:
                cleanup_status = CleanupStatus.DIRTY
                core = {
                    "probe_status": ProbeStatus.ERROR,
                    "stock_status": StockStatus.UNKNOWN.value,
                    "stock_qty": None,
                    "error_code": ERROR_CLEANUP_FAILED,
                }

        result = ProbeResult(
            domain=target.domain,
            product_key=target.product_key,
            url=target.url,
            platform=target.platform,
            observed_at=observed_at,
            variant_id=target.variant_id,
            cleanup_status=cleanup_status,
            **core,
        )
        self._metrics.inc_probe(
            domain=target.domain,
            platform=self.platform,
            status=result.probe_status.value,
        )
        return result

    # -- cleanup -----------------------------------------------------------
    def _cleanup(self, remove_url: str, target: ProbeTarget) -> bool:
        """Remove the added item; return True only on a verified 200."""
        try:
            resp = self._transport.request(
                "POST", remove_url, json={"id": target.variant_id}
            )
        except TransportError:
            return False
        return resp.status_code == 200


# -- module helpers --------------------------------------------------------
def _block_reason(resp: ProbeResponse) -> Optional[str]:
    if resp.is_challenge:
        return "challenge"
    if resp.status_code == 403:
        return "403"
    if resp.status_code == 429:
        return "429"
    return None


def _max_from_body(resp: ProbeResponse) -> Optional[int]:
    """Read ``quantity_limits.maximum`` (int) from a 200 cart body, else None."""
    body = resp.json()
    limits = body.get("quantity_limits")
    if isinstance(limits, dict):
        maximum = limits.get("maximum")
        if isinstance(maximum, int) and not isinstance(maximum, bool):
            return maximum
    return None


def _is_out_of_stock(resp: ProbeResponse) -> bool:
    body = resp.json()
    text = " ".join(
        str(body.get(field, "")) for field in ("code", "message")
    ).lower()
    return any(marker in text for marker in _OOS_MARKERS)


def _unavailable() -> dict:
    return {
        "probe_status": ProbeStatus.UNAVAILABLE,
        "stock_status": StockStatus.OUT_OF_STOCK.value,
        "stock_qty": 0,
    }


def _probed(qty: Optional[int]) -> dict:
    return {
        "probe_status": ProbeStatus.PROBED,
        "stock_status": StockStatus.IN_STOCK.value,
        "stock_qty": qty,
    }


__all__ = ["WooProber", "ADD_PATH", "REMOVE_PATH"]
