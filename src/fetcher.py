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
from urllib.parse import urlparse

import httpx

from src.egress_guard import is_allowed_url

logger = logging.getLogger(__name__)

FIRECRAWL_URL = os.getenv("FIRECRAWL_URL", "http://172.18.0.1:3003")
FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY", "fc-skirmshop-local")

_CHALLENGE_MARKERS = (
    "captcha",
    "g-recaptcha",
    "hcaptcha",
    "cf-chl",
    "cloudflare ray id",
    "attention required! | cloudflare",
    "cf-browser-verification",
    "just a moment",
    "checking your browser",
)
_CHALLENGE_PATH_MARKERS = ("captcha", "challenge", "cf-chl")


class FetchBlockedError(RuntimeError):
    """Raised when a competitor page presents anti-bot/blocking signals."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"blocked fetch {url!r}: {reason}")
        self.url = url
        self.reason = reason


def _detect_block_reason(status_code: int, body: str, final_url: str) -> str | None:
    """Return a fail-closed block reason for anti-bot/challenge responses."""
    if status_code == 403:
        return "http_403"
    if status_code == 429:
        return "http_429"

    path = urlparse(final_url).path.lower()
    if any(marker in path for marker in _CHALLENGE_PATH_MARKERS):
        return "challenge_path"

    text = (body or "").lower()
    if any(marker in text for marker in _CHALLENGE_MARKERS):
        return "challenge_body"

    if status_code == 503:
        return "http_503"
    return None


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
        reason = _detect_block_reason(resp.status_code, resp.text, str(resp.url))
        if reason is not None:
            logger.warning(
                "fetch blocked: %s returned status=%s final_url=%s reason=%s",
                url,
                resp.status_code,
                resp.url,
                reason,
            )
            raise FetchBlockedError(str(resp.url), reason)
        if resp.status_code == 200:
            html = resp.text
            # Looks like rendered content?
            if len(html) > 5000 and ("<product" in html.lower() or "price" in html.lower()):
                return html
            if len(html) > 2000:
                return html
    except FetchBlockedError:
        raise
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
                    html = (data.get("data") or {}).get("html", "")
                    reason = _detect_block_reason(200, html, url)
                    if reason is not None:
                        logger.warning(
                            "firecrawl result blocked: %s reason=%s",
                            url,
                            reason,
                        )
                        raise FetchBlockedError(url, reason)
                    return html
    except FetchBlockedError:
        raise
    except Exception as e:
        logger.debug(f"Firecrawl fetch failed for {url}: {e}")
    return None
