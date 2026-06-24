"""GenericHtmlAdapter - scrape any site via direct public GET + structured extractor."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from src.extractor import extract_products as _extract_products
from .base import BaseSiteAdapter

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "SkirmshopCrawler/1.0 (+https://skirmshop.es)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es,en;q=0.5",
}


class GenericHtmlAdapter(BaseSiteAdapter):
    """Adapter for sites without a dedicated integration.

    F1 mode: direct httpx GET only -- no Firecrawl, no JS rendering.
    Uses the structured-data extractor (JSON-LD -> OG -> microdata).
    """

    name: str = "generic_html"

    def __init__(self, domain: str, source_url: str) -> None:
        super().__init__(domain, source_url)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=_HEADERS,
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    async def fetch_page(self, url: str) -> Optional[str]:
        """Direct public GET -- no Firecrawl fallback."""
        client = await self._get_client()
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning("fetch_page %s -> HTTP %s", url, resp.status_code)
        except Exception as exc:
            logger.warning("fetch_page %s failed: %s", url, exc)
        return None

    def extract_products(self, html: str, url: str) -> list[dict]:
        return _extract_products(html, url, self.domain)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
