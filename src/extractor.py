"""Structured product extraction from HTML.

Three methods, in order of accuracy:
  1. JSON-LD `Product` (modern Shopify, big custom stores)
  2. Open Graph product:* meta tags
  3. Microdata `schema.org/Product`

Also extracts the page title + a content snippet for the
"general knowledge" fallback document type.
"""
import json
import logging
import re
from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_price(price_str: Optional[str]) -> Optional[float]:
    """Parse '€569.00', '569,00', '$ 99.99 EUR' → 569.00.

    Strips currency symbols, whitespace, and 3-letter currency codes
    (EUR, USD, GBP, ...) so feeds that include the code as a suffix
    don't collapse to None."""
    if not price_str:
        return None
    cleaned = re.sub(r"[€$£\s]", "", str(price_str))
    cleaned = re.sub(r"(?i)(eur|usd|gbp|chf|pln)$", "", cleaned).strip()
    cleaned = cleaned.replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return None


def _meta(soup: BeautifulSoup, prop: str) -> str:
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return tag.get("content", "") if tag else ""


def _from_jsonld_product(data: dict, url: str, domain: str) -> dict:
    offers = data.get("offers", {})
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = offers.get("price") or offers.get("lowPrice")
    brand = data.get("brand", {})
    if isinstance(brand, dict):
        brand = brand.get("name", "")
    return {
        "title": data.get("name", ""),
        "price": parse_price(str(price)) if price else None,
        "brand": brand or "",
        "sku_raw": data.get("sku", ""),
        "url": data.get("url") or url,
        "domain": domain,
        "image": data.get("image", ""),
        "description": (data.get("description") or "")[:200],
        "availability": offers.get("availability", ""),
    }


def extract_products(html: str, url: str, domain: str) -> list[dict]:
    """Return zero or more product dicts from the page."""
    products: list[dict] = []
    if not html:
        return products
    soup = BeautifulSoup(html, "html.parser")

    # Method 1: JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("@type") == "Product":
                products.append(_from_jsonld_product(item, url, domain))
            elif "@graph" in item:
                for g in item["@graph"]:
                    if isinstance(g, dict) and g.get("@type") == "Product":
                        products.append(_from_jsonld_product(g, url, domain))

    # Method 2: Open Graph fallback
    if not products:
        og_title = soup.find("meta", property="og:title")
        og_price = soup.find("meta", property="product:price:amount")
        if og_title and og_price:
            products.append({
                "title": og_title.get("content", ""),
                "price": parse_price(og_price.get("content", "")),
                "brand": _meta(soup, "product:brand"),
                "sku_raw": _meta(soup, "product:retailer_item_id"),
                "url": url,
                "domain": domain,
            })

    # Method 3: Microdata
    if not products:
        for item in soup.find_all(itemtype=re.compile(r"schema\.org/Product")):
            t = item.find(itemprop="name")
            p = item.find(itemprop="price")
            b = item.find(itemprop="brand")
            if t and p:
                products.append({
                    "title": t.get_text(strip=True),
                    "price": parse_price(p.get("content", p.get_text())),
                    "brand": b.get_text(strip=True) if b else "",
                    "url": url,
                    "domain": domain,
                })

    return [p for p in products if p.get("title")]


def extract_page_title(html: str, url: str) -> str:
    if not html:
        return urlparse(url).path
    soup = BeautifulSoup(html, "html.parser")
    return (soup.title.string if soup.title else urlparse(url).path) or ""


PRODUCT_PATH_HINTS = [
    "/product/", "/products/", "/p/", "/item/",
    "/shop/", "/catalog/", "/tienda/",
    "/airsoft-", "/replica-",
]
SKIP_PATH_HINTS = [
    "/cart", "/checkout", "/account", "/login", "/register",
    "/blog", "/news", "/contact", "/about", "/faq",
    "/privacy", "/terms", "/shipping", "/returns",
    ".pdf", ".jpg", ".png", ".css", ".js",
]


def is_product_url(url: str) -> bool:
    """Heuristic for "follow this link further into the BFS"."""
    path = urlparse(url).path.lower()
    if any(p in path for p in SKIP_PATH_HINTS):
        return False
    if any(p in path for p in PRODUCT_PATH_HINTS):
        return True
    # Default: visit if not too deep
    return path.count("/") <= 3
