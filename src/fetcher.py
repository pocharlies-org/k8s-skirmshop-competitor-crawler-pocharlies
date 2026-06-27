"""HTTP fetcher with Firecrawl fallback for JS-rendered pages.

Direct httpx.get is tried first (fast, no Firecrawl resource cost). If
the response looks like a SPA shell or is below the size threshold, we
fall back to Firecrawl `/v1/scrape` to get the rendered HTML.

Domain egress is enforced here when ``domain`` is supplied: a forbidden URL
is never requested directly *and* never handed to Firecrawl, and a request
that redirects off-domain has its (off-domain) body discarded.
"""
import logging
import os
from typing import Optional

import httpx

from src.egress_guard import is_allowed_url

logger = logging.getLogger(__name__)

FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://172.18.0.1:3003")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY", "fc-skirmshop-local")


async def fetch_page(
    client: httpx.AsyncClient, url: str, domain: Optional[str] = None
) -> Optional[str]:
    """Return rendered HTML or None on failure.

    When ``domain`` is provided, the URL is gated by :func:`is_allowed_url`
    *before* any network call, so a forbidden URL triggers neither a direct
    request nor a Firecrawl scrape. After a successful direct fetch the final
    (post-redirect) URL is re-checked so a redirect that lands off-domain is
    rejected instead of being scraped/returned.
    """
    # Egress guard: never touch a forbidden URL (direct or via Firecrawl).
    if domain is not None and not is_allowed_url(url, domain):
        logger.warning("egress blocked (pre-fetch): %s is off-domain for %s", url, domain)
        return None

    # Try direct fetch first
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            # Redirect guard: the final URL must stay on-domain, otherwise we
            # have followed a competitor-controlled redirect off-site. Discard
            # the body and do NOT fall through to Firecrawl for this URL.
            if domain is not None and not is_allowed_url(str(resp.url), domain):
                logger.warning(
                    "egress blocked (redirect): %s -> %s is off-domain for %s",
                    url,
                    resp.url,
                    domain,
                )
                return None
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
