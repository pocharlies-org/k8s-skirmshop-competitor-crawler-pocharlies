"""F4 Cart-Probe package (mock-only).

Aggressive-but-bounded cart-probe to derive numeric stock for competitor
products, with verified cart cleanup and a per-domain kill-switch
(403/429/challenge -> cooldown). This subtask ships the data contract, the
kill-switch/cooldown and the in-memory metrics only; the platform probers and
the service loop arrive in later F4 subtasks.

F4 boundaries (see ``rso/F4-cart-probe/``):
  * No checkout, login, accounts, CAPTCHA solving, or anti-bot bypass.
  * Default-deny for generic platforms.
  * Results map one-way into the F3 append-only ``Observation`` with
    ``stock_method="cart_probe"``; F4 never mutates the F3 schema.
"""
from __future__ import annotations

from .contract import (
    ANTIBOT_REASONS,
    COOLDOWN_REASON,
    STOCK_METHOD_CART_PROBE,
    CleanupStatus,
    ProbeResult,
    ProbeStatus,
    ProbeTarget,
    StockStatus,
    probe_result_to_observation,
)
from .generic import NO_SAFE_PATTERN, GenericProber
from .killswitch import DEFAULT_COOLDOWN, DomainBlocked, DomainGuard, DomainStatus
from .metrics import CRAWL_BLOCK_TOTAL, PROBE_TOTAL, Metrics
from .shopify import ADD_PATH, CLEAR_PATH, ShopifyProber
from .transport import ProbeResponse, ProbeTransport, TransportError
from .woo import ADD_PATH as WOO_ADD_PATH
from .woo import REMOVE_PATH as WOO_REMOVE_PATH
from .woo import WooProber

__all__ = [
    "ANTIBOT_REASONS",
    "COOLDOWN_REASON",
    "STOCK_METHOD_CART_PROBE",
    "CleanupStatus",
    "ProbeResult",
    "ProbeStatus",
    "ProbeTarget",
    "StockStatus",
    "probe_result_to_observation",
    "DEFAULT_COOLDOWN",
    "DomainBlocked",
    "DomainGuard",
    "DomainStatus",
    "CRAWL_BLOCK_TOTAL",
    "PROBE_TOTAL",
    "Metrics",
    "ProbeResponse",
    "ProbeTransport",
    "TransportError",
    "GenericProber",
    "NO_SAFE_PATTERN",
    "ShopifyProber",
    "ADD_PATH",
    "CLEAR_PATH",
    "WooProber",
    "WOO_ADD_PATH",
    "WOO_REMOVE_PATH",
]
