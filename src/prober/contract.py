"""F4 cart-probe data contract.

Defines the probe target, the probe result with an explicit state-legality
matrix, and the one-way mapper to the F3 append-only ``Observation``.

The validation matrix mirrors the architect report (``architect.report.md``):
the only legal field combinations are encoded here so an illegal result can
never be constructed and silently written.
"""
from __future__ import annotations

import dataclasses
import enum
from datetime import datetime
from typing import Optional

from src.history_writer import Observation

# Stock method for every F4 result (F3 accepts this value).
STOCK_METHOD_CART_PROBE = "cart_probe"

# Valid stock_status values (mirror F3 CHECK constraints).
VALID_STOCK_STATUS = frozenset({"in_stock", "out_of_stock", "unknown"})

# Anti-bot / challenge reasons that trip the per-domain kill-switch.
ANTIBOT_REASONS = frozenset({"403", "429", "503", "challenge"})
# Block reason recorded when a probe is refused because the domain is in
# cooldown after a previous trip.
COOLDOWN_REASON = "cooldown_active"


class StockStatus(str, enum.Enum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


class ProbeStatus(str, enum.Enum):
    PROBED = "probed"          # cart-probe succeeded; in_stock (qty or uncapped)
    UNAVAILABLE = "unavailable"  # cart-probe proved out_of_stock
    SKIPPED = "skipped"        # default-deny / no safe pattern; no network
    BLOCKED = "blocked"        # anti-bot kill-switch (403/429/challenge/cooldown)
    ERROR = "error"            # transport/parse/cleanup failure


class CleanupStatus(str, enum.Enum):
    NOT_NEEDED = "not_needed"  # nothing was added to the cart
    CLEAN = "clean"            # cart cleared and verified
    DIRTY = "dirty"            # cleanup failed -> cart may be left dirty


@dataclasses.dataclass(frozen=True)
class ProbeTarget:
    """A single product/variant to probe."""

    domain: str
    product_key: str
    url: str
    platform: str
    variant_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("ProbeTarget.domain is required")
        if not self.product_key:
            raise ValueError("ProbeTarget.product_key is required")
        if not self.url:
            raise ValueError("ProbeTarget.url is required")
        if not self.platform:
            raise ValueError("ProbeTarget.platform is required")


@dataclasses.dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single cart-probe.

    State legality (enforced in ``__post_init__``):

      * PROBED      -> stock_status == in_stock; stock_qty is an int >= 0 OR
                       None (None == uncapped inventory, explicitly allowed).
      * UNAVAILABLE -> stock_status == out_of_stock; stock_qty None or 0.
      * SKIPPED     -> stock_status == unknown; stock_qty None; no block_reason.
      * BLOCKED     -> stock_status == unknown; stock_qty None; block_reason set.
      * ERROR       -> stock_status == unknown; stock_qty None; error_code set.

    ``block_reason`` may only be set for BLOCKED. ``stock_method`` is always
    ``cart_probe``.
    """

    domain: str
    product_key: str
    url: str
    platform: str
    observed_at: datetime
    probe_status: ProbeStatus
    stock_status: str = StockStatus.UNKNOWN.value
    stock_qty: Optional[int] = None
    stock_method: str = STOCK_METHOD_CART_PROBE
    variant_id: Optional[str] = None
    block_reason: Optional[str] = None
    cleanup_status: CleanupStatus = CleanupStatus.NOT_NEEDED
    error_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.domain:
            raise ValueError("ProbeResult.domain is required")
        if not self.product_key:
            raise ValueError("ProbeResult.product_key is required")
        if not self.url:
            raise ValueError("ProbeResult.url is required")
        if not self.platform:
            raise ValueError("ProbeResult.platform is required")
        if not isinstance(self.observed_at, datetime):
            raise ValueError("ProbeResult.observed_at must be a datetime")
        if not isinstance(self.probe_status, ProbeStatus):
            raise ValueError("ProbeResult.probe_status must be a ProbeStatus")
        if not isinstance(self.cleanup_status, CleanupStatus):
            raise ValueError("ProbeResult.cleanup_status must be a CleanupStatus")
        if self.stock_method != STOCK_METHOD_CART_PROBE:
            raise ValueError(
                f"ProbeResult.stock_method must be {STOCK_METHOD_CART_PROBE!r}"
            )
        if self.stock_status not in VALID_STOCK_STATUS:
            raise ValueError(
                f"invalid stock_status {self.stock_status!r}; "
                f"expected one of {sorted(VALID_STOCK_STATUS)}"
            )
        if self.stock_qty is not None and self.stock_qty < 0:
            raise ValueError(f"stock_qty must be >= 0, got {self.stock_qty}")

        # block_reason only legal for BLOCKED.
        if self.block_reason is not None and self.probe_status is not ProbeStatus.BLOCKED:
            raise ValueError(
                "block_reason is only allowed when probe_status is BLOCKED"
            )

        status = self.probe_status
        if status is ProbeStatus.PROBED:
            if self.stock_status != StockStatus.IN_STOCK.value:
                raise ValueError("PROBED requires stock_status == in_stock")
            # stock_qty None == uncapped inventory (explicitly allowed).
        elif status is ProbeStatus.UNAVAILABLE:
            if self.stock_status != StockStatus.OUT_OF_STOCK.value:
                raise ValueError("UNAVAILABLE requires stock_status == out_of_stock")
            if self.stock_qty not in (None, 0):
                raise ValueError("UNAVAILABLE requires stock_qty in {None, 0}")
        elif status is ProbeStatus.SKIPPED:
            if self.stock_status != StockStatus.UNKNOWN.value:
                raise ValueError("SKIPPED requires stock_status == unknown")
            if self.stock_qty is not None:
                raise ValueError("SKIPPED requires stock_qty is None")
        elif status is ProbeStatus.BLOCKED:
            if not self.block_reason:
                raise ValueError("BLOCKED requires block_reason")
            if self.stock_status != StockStatus.UNKNOWN.value:
                raise ValueError("BLOCKED requires stock_status == unknown")
            if self.stock_qty is not None:
                raise ValueError("BLOCKED requires stock_qty is None")
        elif status is ProbeStatus.ERROR:
            if not self.error_code:
                raise ValueError("ERROR requires error_code")
            if self.stock_status != StockStatus.UNKNOWN.value:
                raise ValueError("ERROR requires stock_status == unknown")
            if self.stock_qty is not None:
                raise ValueError("ERROR requires stock_qty is None")
        else:  # pragma: no cover - defensive
            raise ValueError(f"unhandled probe_status {status!r}")


def probe_result_to_observation(result: ProbeResult, run_id: str) -> Observation:
    """Map a :class:`ProbeResult` one-way into the F3 ``Observation``.

    ``crawl_success`` is True only when the probe actually determined stock
    (PROBED / UNAVAILABLE). For BLOCKED / SKIPPED / ERROR the observation is a
    failed crawl with an explicit ``error_code`` (F3 requires one when
    ``crawl_success`` is False). F4 contributes only stock fields; price stays
    None here.
    """
    if not run_id:
        raise ValueError("run_id is required")

    success = result.probe_status in (ProbeStatus.PROBED, ProbeStatus.UNAVAILABLE)
    error_code = result.error_code or result.block_reason
    if not success and not error_code:
        error_code = result.probe_status.value

    return Observation(
        domain=result.domain,
        product_key=result.product_key,
        run_id=run_id,
        observed_at=result.observed_at,
        stock_qty=result.stock_qty,
        stock_status=result.stock_status,
        stock_method=STOCK_METHOD_CART_PROBE,
        crawl_success=success,
        error_code=error_code,
    )


__all__ = [
    "STOCK_METHOD_CART_PROBE",
    "VALID_STOCK_STATUS",
    "ANTIBOT_REASONS",
    "COOLDOWN_REASON",
    "StockStatus",
    "ProbeStatus",
    "CleanupStatus",
    "ProbeTarget",
    "ProbeResult",
    "probe_result_to_observation",
]
