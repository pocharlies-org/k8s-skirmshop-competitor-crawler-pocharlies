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

from src.extractor import extract_page_title, extract_products, is_product_url
from src.fetcher import fetch_page
from src.promotion_tracker import detect_promotion

logger = logging.getLogger(__name__)


async def crawl_store(store: dict) -> list[dict]:
    """Crawl one store config, return list of push-ingest documents.

    Store config keys: domain, url, depth (default 2), platform (info)."""
    domain = store["domain"]
    start_url = store["url"]
    max_depth = int(store.get("depth", 2))
    platform = store.get("platform", "custom")

    visited: set[str] = set()
    to_visit: list[tuple[str, int]] = [(start_url, 0)]
    product_urls: set[str] = set()
    docs: list[dict] = []

    logger.info(f"[{domain}] crawl start (depth={max_depth}, platform={platform})")

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        headers={"User-Agent": "skirmshop-competitor-crawler/1.0 (+research)"},
    ) as client:
        while to_visit:
            url, depth = to_visit.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)

            html = await fetch_page(client, url)
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
                    parsed = urlparse(full)
                    if parsed.netloc and domain in parsed.netloc:
                        clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                        if clean not in visited and is_product_url(clean):
                            to_visit.append((clean, depth + 1))

            # Polite delay
            await asyncio.sleep(0.5)

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
