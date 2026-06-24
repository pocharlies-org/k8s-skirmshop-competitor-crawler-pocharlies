"""BaseSiteAdapter - minimal contract every adapter must implement."""
from __future__ import annotations

import abc
import dataclasses
from typing import Optional


@dataclasses.dataclass
class AdapterResult:
    domain: str
    source_url: str
    adapter: str
    candidates: int = 0
    success: int = 0
    discarded: int = 0
    failures: int = 0
    products: list[dict] = dataclasses.field(default_factory=list)

    @property
    def discard_ratio(self) -> float:
        total = self.candidates
        return round(self.discarded / total, 4) if total else 0.0


class BaseSiteAdapter(abc.ABC):
    """Adapter skeleton - subclasses implement fetch + extract."""

    name: str = "base"

    def __init__(self, domain: str, source_url: str) -> None:
        self.domain = domain
        self.source_url = source_url

    @abc.abstractmethod
    async def fetch_page(self, url: str) -> Optional[str]:
        """Return raw HTML or None."""

    @abc.abstractmethod
    def extract_products(self, html: str, url: str) -> list[dict]:
        """Return list of raw product dicts from a page."""

    # F1 = catalog + price only. Stock/availability is F2 scope.
    _F1_STOCK_FIELDS: frozenset = frozenset({
        "availability", "stock", "stock_status", "quantity", "qty",
        "in_stock", "out_of_stock",
    })

    def _normalize(self, raw: dict, page_url: str) -> dict:
        """Attach mandatory fields, compute source_id, and strip F2 stock fields."""
        product_url = raw.get("url") or page_url
        source_id = f"competitor:{self.domain}:{product_url}"
        filtered = {k: v for k, v in raw.items() if k not in self._F1_STOCK_FIELDS}
        return {
            **filtered,
            "domain": self.domain,
            "url": product_url,
            "source_id": source_id,
        }

    async def run(self, limit: int = 50) -> AdapterResult:
        result = AdapterResult(
            domain=self.domain,
            source_url=self.source_url,
            adapter=self.name,
        )
        html = await self.fetch_page(self.source_url)
        if html is None:
            result.failures += 1
            return result
        raw_products = self.extract_products(html, self.source_url)
        result.candidates = len(raw_products)
        for raw in raw_products[:limit]:
            if not raw.get("title"):
                result.discarded += 1
                continue
            if raw.get("price") is None:
                result.discarded += 1
                continue
            result.products.append(self._normalize(raw, self.source_url))
            result.success += 1
        # Products beyond limit are not attempted; they are NOT counted as discarded.
        # discarded reflects only attempted candidates that fail title/price validation.
        return result
