"""ShopifyProber - numeric stock via the ``/cart/add.js`` endpoint (mock-only).

Shopify storefronts expose ``POST /cart/add.js`` which accepts a variant id and
a quantity. The endpoint is the F4 oracle for numeric stock:

  * a ``422`` whose message says *"You can only add N of this item"* leaks the
    exact remaining inventory ``N`` without ever adding to the cart;
  * a ``422`` that reads *sold out* proves the variant is out of stock;
  * a ``200`` for a large quantity proves stock ``>= quantity`` and is refined
    by a bounded exponential+binary search up to ``max_qty`` (uncapped above);
  * an anti-bot ``403``/``429``/challenge trips the per-domain kill-switch.

Every probe that actually adds to the cart (any ``200`` add) is followed by a
verified ``POST /cart/clear.js`` in the cleanup step; a failed cleanup demotes
the result to ERROR/DIRTY so a dirty cart is never silently reported as clean.

This prober is transport-agnostic: it issues no live HTTP and depends only on
the :class:`ProbeTransport` Protocol, so tests drive it with a scripted fake.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Tuple

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

# Phrases in a 422 body that prove the variant is out of stock.
_SOLD_OUT_MARKERS = ("sold out", "out of stock", "unavailable", "no longer available")
# First run of digits in a 422 message == the max addable == remaining stock.
_INT_RE = re.compile(r"\d+")

ADD_PATH = "/cart/add.js"
CLEAR_PATH = "/cart/clear.js"

ERROR_TRANSPORT = "transport_error"
ERROR_CLEANUP_FAILED = "cart_cleanup_failed"


class _Blocked(Exception):
    """Internal signal: an add hit an anti-bot wall (403/429/challenge)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Unexpected(Exception):
    """Internal signal: an add returned a status that is neither 200 nor 422.

    Such a status carries no inventory meaning, so it must never be silently
    treated as capped/unavailable; the caller maps it onto an ERROR result.
    """

    def __init__(self, code: int) -> None:
        super().__init__(str(code))
        self.code = code


class ShopifyProber:
    platform = "shopify"

    def __init__(
        self,
        transport: ProbeTransport,
        guard: DomainGuard,
        metrics: Metrics,
        *,
        high_qty: int = 99,
        max_qty: int = 10000,
    ) -> None:
        if high_qty < 1:
            raise ValueError("high_qty must be >= 1")
        if max_qty < high_qty:
            raise ValueError("max_qty must be >= high_qty")
        self._transport = transport
        self._guard = guard
        self._metrics = metrics
        self._high_qty = high_qty
        self._max_qty = max_qty

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
        clear_url = base + CLEAR_PATH

        # Whether any add returned 200 (cart is now dirty and must be cleared).
        added = [False]

        def add(qty: int) -> ProbeResponse:
            resp = self._transport.request(
                "POST", add_url, json={"id": target.variant_id, "quantity": qty}
            )
            reason = _block_reason(resp)
            if reason is not None:
                raise _Blocked(reason)
            if resp.status_code == 200:
                added[0] = True
            elif resp.status_code != 422:
                # Neither addable (200) nor an inventory oracle (422): the
                # status is unexpected and carries no stock meaning.
                raise _Unexpected(resp.status_code)
            return resp

        core: dict
        try:
            core = self._determine(target, add)
        except _Blocked as blocked:
            self._guard.record_block(target.domain, blocked.reason, observed_at)
            core = {
                "probe_status": ProbeStatus.BLOCKED,
                "stock_status": StockStatus.UNKNOWN.value,
                "stock_qty": None,
                "block_reason": blocked.reason,
            }
        except _Unexpected as unexpected:
            core = {
                "probe_status": ProbeStatus.ERROR,
                "stock_status": StockStatus.UNKNOWN.value,
                "stock_qty": None,
                "error_code": f"unexpected_status_{unexpected.code}",
            }
        except TransportError:
            core = {
                "probe_status": ProbeStatus.ERROR,
                "stock_status": StockStatus.UNKNOWN.value,
                "stock_qty": None,
                "error_code": ERROR_TRANSPORT,
            }

        cleanup_status = CleanupStatus.NOT_NEEDED
        if added[0]:
            if self._cleanup(clear_url):
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

    # -- core state machine ------------------------------------------------
    def _determine(self, target: ProbeTarget, add) -> dict:
        """Run the add/search flow and return the core result fields.

        May raise :class:`_Blocked` (anti-bot) or :class:`TransportError`,
        which the caller maps onto BLOCKED / ERROR results.
        """
        resp = add(self._high_qty)
        code = resp.status_code

        if code == 422:
            parsed = _parse_422(resp)
            if parsed == "sold_out":
                return _unavailable()
            if isinstance(parsed, int):
                # The 422 leaked exact stock; nothing was added to the cart.
                return _probed(parsed)
            # Unparseable 422: fall back to probing from qty=1 upward.
            if add(1).status_code != 200:
                return _unavailable()
            return _probed(self._find_max(1, add))

        # code == 200: stock >= high_qty; refine the ceiling (or prove uncapped).
        # The add() helper guarantees code is 200 or 422 (others raise
        # _Unexpected), so no other branch is reachable here.
        return _probed(self._find_max(self._high_qty, add))

    def _find_max(self, good: int, add) -> Optional[int]:
        """Find the largest addable quantity, given ``good`` already added 200.

        Returns the exact max, or ``None`` when stock is uncapped (still 200 at
        ``max_qty``). Exponential probe to bracket a failing upper bound, then
        binary search down to the boundary.
        """
        if good >= self._max_qty:
            return None

        bad: Optional[int] = None
        while True:
            nxt = good * 2
            if nxt >= self._max_qty:
                if add(self._max_qty).status_code == 200:
                    return None  # uncapped
                bad = self._max_qty
                break
            if add(nxt).status_code == 200:
                good = nxt
                continue
            bad = nxt
            break

        lo, hi = good, bad
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if add(mid).status_code == 200:
                lo = mid
            else:
                hi = mid
        return lo

    def _cleanup(self, clear_url: str) -> bool:
        """POST ``/cart/clear.js``; return True only on a verified 200."""
        try:
            resp = self._transport.request("POST", clear_url)
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


def _parse_422(resp: ProbeResponse):
    """Classify a 422 body -> ``"sold_out"`` | int stock | None (unparseable)."""
    body = resp.json()
    text = " ".join(
        str(body.get(field, "")) for field in ("description", "message")
    ).lower()
    if any(marker in text for marker in _SOLD_OUT_MARKERS):
        return "sold_out"
    match = _INT_RE.search(text)
    if match is not None:
        return int(match.group())
    return None


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


__all__ = ["ShopifyProber", "ADD_PATH", "CLEAR_PATH"]
