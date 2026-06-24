"""HTTP fetcher with Firecrawl fallback for JS-rendered pages.

Direct httpx.get is tried first (fast, no Firecrawl resource cost). If
the response looks like a SPA shell or is below the size threshold, we
fall back to Firecrawl `/v1/scrape` to get the rendered HTML.
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://172.18.0.1:3003")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY", "fc-skirmshop-local")


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Return rendered HTML or None on failure."""
    # Try direct fetch first
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            html = resp.text
            # Looks like rendered content?
            if len(html) > 5000 and ("<product" in html.lower() or "price" in html.lower()):
                return html
            if len(html) > 2000:
                return html
    except Exception as e:
        logger.debug(f"Direct fetch failed for {url}: {e}")

    # Firecrawl fallback for JS-heavy sites
    try:
        async with httpx.AsyncClient(timeout=45) as fc:
            resp = await fc.post(
                f"{FIRECRAWL_URL}/v1/scrape",
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": url,
                    "formats": ["html", "markdown"],
                    "timeout": 30000,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    return (data.get("data") or {}).get("html", "")
    except Exception as e:
        logger.debug(f"Firecrawl fetch failed for {url}: {e}")
    return None
