"""Per-domain kill-switch / cooldown for the cart-probe.

First sustained 403/429/challenge on a domain trips the guard: the domain is
put into cooldown (default 36h) and every subsequent probe of that domain is
refused without touching the network. Each trip increments
``competitor_crawl_block_total{domain,reason}`` with the trip reason; each
cooldown refusal increments it with reason ``cooldown_active``.

The guard is clock-free: the caller passes ``now`` / ``observed_at`` explicitly
so tests stay deterministic.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, NamedTuple, Optional

from .contract import (
    ANTIBOT_REASONS,
    COOLDOWN_REASON,
    CleanupStatus,
    ProbeResult,
    ProbeStatus,
    StockStatus,
)
from .metrics import Metrics

DEFAULT_COOLDOWN = timedelta(hours=36)


class DomainBlocked(Exception):
    """Raised/queried when a domain is in cooldown."""

    def __init__(self, domain: str, reason: str, until: datetime) -> None:
        super().__init__(
            f"domain {domain!r} blocked ({reason}) until {until.isoformat()}"
        )
        self.domain = domain
        self.reason = reason
        self.until = until


class DomainStatus(NamedTuple):
    reason: str
    until: datetime


class DomainGuard:
    """Tracks tripped domains and their cooldown windows.

    ``reason`` for a trip is one of ``ANTIBOT_REASONS`` (403/429/challenge);
    cooldown refusals are recorded with reason ``cooldown_active``.
    """

    def __init__(
        self,
        metrics: Metrics,
        *,
        cooldown: timedelta = DEFAULT_COOLDOWN,
    ) -> None:
        self._metrics = metrics
        self._cooldown = cooldown
        self._tripped: Dict[str, DomainStatus] = {}

    def record_block(self, domain: str, reason: str, now: datetime) -> DomainStatus:
        """Trip the kill-switch for ``domain`` and start a cooldown from ``now``."""
        if reason not in ANTIBOT_REASONS:
            raise ValueError(
                f"invalid block reason {reason!r}; "
                f"expected one of {sorted(ANTIBOT_REASONS)}"
            )
        if not isinstance(now, datetime):
            raise ValueError("record_block requires a datetime 'now'")
        status = DomainStatus(reason=reason, until=now + self._cooldown)
        self._tripped[domain] = status
        self._metrics.inc_block(domain=domain, reason=reason)
        return status

    def domain_status(self, domain: str, now: datetime) -> Optional[DomainStatus]:
        """Return the active cooldown for ``domain`` at ``now``, else None.

        Expired cooldowns are cleared lazily so probing resumes automatically.
        """
        status = self._tripped.get(domain)
        if status is None:
            return None
        if now >= status.until:
            del self._tripped[domain]
            return None
        return status

    def is_blocked(self, domain: str, now: datetime) -> bool:
        return self.domain_status(domain, now) is not None

    def guard_result(
        self,
        domain: str,
        product_key: str,
        url: str,
        platform: str,
        observed_at: datetime,
    ) -> Optional[ProbeResult]:
        """If ``domain`` is in cooldown, return a BLOCKED ProbeResult.

        Returns None when the domain is clear (the caller may then probe).
        Each refusal increments ``competitor_crawl_block_total`` with reason
        ``cooldown_active``.
        """
        status = self.domain_status(domain, observed_at)
        if status is None:
            return None
        self._metrics.inc_block(domain=domain, reason=COOLDOWN_REASON)
        return ProbeResult(
            domain=domain,
            product_key=product_key,
            url=url,
            platform=platform,
            observed_at=observed_at,
            probe_status=ProbeStatus.BLOCKED,
            stock_status=StockStatus.UNKNOWN.value,
            stock_qty=None,
            block_reason=COOLDOWN_REASON,
            cleanup_status=CleanupStatus.NOT_NEEDED,
        )


__all__ = ["DomainGuard", "DomainBlocked", "DomainStatus", "DEFAULT_COOLDOWN"]
