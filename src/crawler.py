"""BFS crawler that walks a competitor store + emits push-ingest payloads.

Port of the deleted brain-side `core/adapters/competitor_crawler.py`.
Differences:
- Output is a list of `dict` payloads ready for push-ingest, not
  RawDocument/Chunk pairs.
- No PostgreSQL coupling; PromotionTracker port is in
  `promotion_tracker.py` and only flags `is_promotion`/`promo_text`.
"""
import asyncio
import logging
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx

from src.egress_guard import is_allowed_url
from src.extractor import extract_page_title, extract_products, is_product_url
from src.fetcher import FetchBlockedError, fetch_page
from src.promotion_tracker import detect_promotion
from src.robots import CRAWLER_USER_AGENT_HEADER, load_robots_policy

logger = logging.getLogger(__name__)

DEFAULT_MAX_PAGES = 25
DEFAULT_DELAY_SECONDS = 0.5


def _positive_int(raw: object, *, default: int, name: str) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer > 0") from exc
    if value <= 0:
        raise ValueError(f"{name} must be an integer > 0")
    return value


def _nonnegative_float(raw: object, *, default: float, name: str) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number >= 0") from exc
    if value < 0:
        raise ValueError(f"{name} must be a number >= 0")
    return value


async def crawl_store(store: dict) -> list[dict]:
    """Crawl one store config, return list of push-ingest documents.

    Store config keys: domain, url, depth (default 2), platform (info),
    max_pages (default 25), delay_seconds (default 0.5).
    """
    domain = store["domain"]
    start_url = store["url"]
    max_depth = int(store.get("depth", 2))
    max_pages = _positive_int(
        store.get("max_pages"),
        default=DEFAULT_MAX_PAGES,
        name="max_pages",
    )
    delay_seconds = _nonnegative_float(
        store.get("delay_seconds"),
        default=DEFAULT_DELAY_SECONDS,
        name="delay_seconds",
    )
    platform = store.get("platform", "custom")

    visited: set[str] = set()
    to_visit: list[tuple[str, int]] = [(start_url, 0)]
    product_urls: set[str] = set()
    docs: list[dict] = []

    logger.info(
        f"[{domain}] crawl start (depth={max_depth}, max_pages={max_pages}, "
        f"delay_seconds={delay_seconds}, platform={platform})"
    )

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": CRAWLER_USER_AGENT_HEADER},
    ) as client:
        robots_policy = await load_robots_policy(client, start_url, domain)
        effective_delay_seconds = max(
            delay_seconds,
            robots_policy.crawl_delay_seconds or 0.0,
        )
        while to_visit and len(visited) < max_pages:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            if not robots_policy.can_fetch(url):
                logger.warning("[%s] robots disallow: %s", domain, url)
                continue

            try:
                html = await fetch_page(client, url, domain)
            except FetchBlockedError as e:
                logger.error(
                    "[%s] blocked by anti-bot/challenge at %s reason=%s; "
                    "aborting store",
                    domain,
                    e.url,
                    e.reason,
                )
                raise
            if not html:
                continue

            # Product extraction
            products = extract_products(html, url, domain)
            for p in products:
                if p.get("url") in product_urls:
                    continue
                product_urls.add(p.get("url") or url)
                promo = detect_promotion(p) or {}
                docs.append({
                    "source_id": f"competitor:{domain}:{p.get('url') or url}",
                    "content": _render_product_content(p),
                    "metadata": {
                        "type": "competitor_product",
                        "domain": domain,
                        "platform": platform,
                        "url": p.get("url") or url,
                        "title": p.get("title", ""),
                        "brand": p.get("brand", ""),
                        "price": p.get("price"),
                        "original_price": promo.get("original_price"),
                        "sku_raw": p.get("sku_raw") or p.get("sku", ""),
                        "is_promotion": bool(promo),
                        "promo_text": promo.get("promo_text", ""),
                        "image": p.get("image", ""),
                        "availability": p.get("availability", ""),
                        "crawled_at": datetime.now(UTC).isoformat(),
                    },
                })

            # BFS — follow same-domain product-looking links
            if depth < max_depth:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                for link in soup.find_all("a", href=True):
                    full = urljoin(url, link["href"])
                    # Egress guard: exact host or subdomain of the store domain,
                    # http(s) only. Replaces the exploitable ``domain in netloc``
                    # substring check (which let ``evilgunfire.com`` and
                    # ``gunfire.com@evil.com`` through).
                    if not is_allowed_url(full, domain):
                        continue
                    parsed = urlparse(full)
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                    if not robots_policy.can_fetch(clean):
                        logger.warning("[%s] robots disallow: %s", domain, clean)
                        continue
                    if clean not in visited and is_product_url(clean):
                        to_visit.append((clean, depth + 1))

            # Polite delay
            if effective_delay_seconds > 0:
                await asyncio.sleep(effective_delay_seconds)

        if to_visit:
            logger.warning(
                "[%s] max_pages=%d reached; queued URLs left=%d",
                domain,
                max_pages,
                len(to_visit),
            )

    logger.info(
        f"[{domain}] crawl done — visited={len(visited)} products={len(docs)}"
    )
    return docs


def _render_product_content(p: dict) -> str:
    """Render a small markdown card for the document body."""
    parts = [
        f"# {p.get('title', 'Product')}",
        f"**Brand:** {p.get('brand', '?')}",
    ]
    if p.get("price") is not None:
        parts.append(f"**Price:** €{p['price']}")
    if p.get("sku_raw"):
        parts.append(f"**SKU:** {p['sku_raw']}")
    if p.get("description"):
        parts += ["", p["description"]]
    if p.get("url"):
        parts += ["", f"<{p['url']}>"]
    return "\n".join(parts)
