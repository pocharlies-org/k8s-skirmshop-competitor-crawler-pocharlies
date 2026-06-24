"""In-memory Prometheus-style counters for the cart-probe.

Dependency-free (stdlib only). The probers and the kill-switch increment
labelled counters; a scraper/exporter can later read them via :meth:`snapshot`.
This avoids pulling ``prometheus_client`` into F4 while keeping the metric
names/labels the architect specified:

  * ``competitor_crawl_block_total{domain,reason}``
  * ``competitor_probe_total{domain,platform,status}``
"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Tuple

CRAWL_BLOCK_TOTAL = "competitor_crawl_block_total"
PROBE_TOTAL = "competitor_probe_total"

# A label set is a sorted tuple of (key, value) pairs so it is hashable and
# order-independent.
_LabelKey = Tuple[str, Tuple[Tuple[str, str], ...]]


class Metrics:
    """Thread-unsafe in-memory counter registry (single-worker probe loop).

    Public API is intentionally minimal: ``inc`` / ``get`` / ``snapshot`` plus
    typed convenience wrappers for the two F4 counters.
    """

    def __init__(self) -> None:
        self._counters: Dict[_LabelKey, int] = defaultdict(int)

    @staticmethod
    def _key(name: str, labels: Dict[str, str]) -> _LabelKey:
        return (name, tuple(sorted(labels.items())))

    def inc(self, name: str, *, amount: int = 1, **labels: str) -> None:
        if amount < 0:
            raise ValueError("counter increment must be >= 0")
        self._counters[self._key(name, labels)] += amount

    def get(self, name: str, **labels: str) -> int:
        return self._counters.get(self._key(name, labels), 0)

    def snapshot(self) -> List[Tuple[str, Dict[str, str], int]]:
        """Return a stable, sorted list of ``(name, labels, value)`` samples."""
        out = [
            (name, dict(labels), count)
            for (name, labels), count in self._counters.items()
        ]
        out.sort(key=lambda s: (s[0], sorted(s[1].items())))
        return out

    # --- typed convenience wrappers --------------------------------------
    def inc_block(self, *, domain: str, reason: str) -> None:
        self.inc(CRAWL_BLOCK_TOTAL, domain=domain, reason=reason)

    def inc_probe(self, *, domain: str, platform: str, status: str) -> None:
        self.inc(PROBE_TOTAL, domain=domain, platform=platform, status=status)

    def block_value(self, *, domain: str, reason: str) -> int:
        return self.get(CRAWL_BLOCK_TOTAL, domain=domain, reason=reason)

    def probe_value(self, *, domain: str, platform: str, status: str) -> int:
        return self.get(PROBE_TOTAL, domain=domain, platform=platform, status=status)


__all__ = ["Metrics", "CRAWL_BLOCK_TOTAL", "PROBE_TOTAL"]
