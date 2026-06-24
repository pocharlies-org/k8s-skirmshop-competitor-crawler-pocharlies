"""F4 cart-probe service facade (mock-only).

A single ``probe_stock`` entry point that dispatches a :class:`ProbeTarget` to
the right platform prober by ``target.platform`` and returns its
:class:`ProbeResult`. The facade owns no network logic of its own: each prober
already consults the :class:`DomainGuard` cooldown and increments the probe
metric exactly once, so the service never duplicates either. Unknown platforms
fall through to the default-deny :class:`GenericProber`, which makes zero
transport calls and returns a SKIPPED ``no_safe_pattern`` result.
"""
from __future__ import annotations

from datetime import datetime

from .contract import ProbeResult, ProbeTarget
from .generic import GenericProber
from .killswitch import DomainGuard
from .metrics import Metrics
from .shopify import ShopifyProber
from .transport import ProbeTransport
from .woo import WooProber

# Platform aliases -> canonical prober selector.
_SHOPIFY = frozenset({"shopify"})
_WOO = frozenset({"woocommerce", "woo"})
_GENERIC = frozenset({"generic_html", "generic"})


def probe_stock(
    target: ProbeTarget,
    transport: ProbeTransport,
    guard: DomainGuard,
    metrics: Metrics,
    observed_at: datetime,
) -> ProbeResult:
    """Dispatch ``target`` to its platform prober and return the result.

    Selection is by ``target.platform``: ``shopify`` -> :class:`ShopifyProber`,
    ``woocommerce``/``woo`` -> :class:`WooProber`, ``generic_html``/``generic``
    and any unrecognised platform -> default-deny :class:`GenericProber` (no
    network). The chosen prober handles its own cooldown check and metric
    increment; the service adds neither.
    """
    platform = target.platform.strip().lower()

    if platform in _SHOPIFY:
        prober = ShopifyProber(transport, guard, metrics)
    elif platform in _WOO:
        prober = WooProber(transport, guard, metrics)
    else:
        # generic_html / generic and every unknown platform: default-deny.
        prober = GenericProber(transport, metrics)

    return prober.probe(target, observed_at)


__all__ = ["probe_stock"]
