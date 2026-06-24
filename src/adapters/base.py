"""BaseSiteAdapter - minimal contract every adapter must implement."""
from __future__ import annotations

import abc
import dataclasses
from typing import Optional

from src.stock import normalize_availability


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

    # Raw fields that must never appear in the normalized output.
    # availability is consumed here and replaced with stock_status/stock_method.
    # F2 contract forbids exposing any raw quantity or stock signal.
    _RAW_STRIP_FIELDS: frozenset = frozenset({
        # availability signals
        "availability",
        "in_stock",
        "out_of_stock",
        "stock_status",   # raw value — replaced by normalize_availability output
        "stock_method",   # raw value — replaced by normalize_availability output
        # numeric / quantity aliases
        "stock",
        "stock_qty",
        "stock_count",
        "quantity",
        "qty",
        "qty_available",
        "units_left",
        "units",
        "count",
    })

    def _normalize(self, raw: dict, page_url: str) -> dict:
        """Attach mandatory fields, compute source_id, and apply F2 stock normalization.

        F2 contract:
          stock_status : in_stock | out_of_stock | unknown
          stock_method : visible  | unknown
        Raw availability / quantity fields are stripped and replaced by these two.
        """
        product_url = raw.get("url") or page_url
        source_id = f"competitor:{self.domain}:{product_url}"

        # F2: extract raw availability before stripping raw fields
        raw_availability = raw.get("availability", "")
        stock_status, stock_method = normalize_availability(raw_availability)

        filtered = {k: v for k, v in raw.items() if k not in self._RAW_STRIP_FIELDS}

        return {
            **filtered,
            "domain": self.domain,
            "url": product_url,
            "source_id": source_id,
            "stock_status": stock_status,
            "stock_method": stock_method,
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
