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
            u = item.find(itemprop="url")
            img = item.find(itemprop="image")
            desc = item.find(itemprop="description")
            avail = item.find(itemprop="availability")
            if t and p:
                # Prefer content/href attributes (used by <meta>/<link> tags);
                # fall back to visible text content for <span>/<div> patterns.
                title_val = t.get("content") or t.get_text(strip=True)
                if not title_val:
                    continue
                price_val = parse_price(p.get("content") or p.get_text())
                if price_val is None:
                    continue
                product_url = url
                if u:
                    product_url = (
                        u.get("href") or u.get("content") or u.get_text(strip=True) or url
                    )
                # availability: prefer href (link tag) then content (meta tag) then text
                availability_val = ""
                if avail:
                    availability_val = (
                        avail.get("href") or avail.get("content") or avail.get_text(strip=True) or ""
                    )
                # brand: prefer content attribute over text (handles <meta itemprop="brand">)
                brand_val = ""
                if b:
                    brand_val = b.get("content") or b.get_text(strip=True) or ""
                products.append({
                    "title": title_val,
                    "price": price_val,
                    "brand": brand_val,
                    "url": product_url,
                    "domain": domain,
                    "image": (img.get("src") or img.get("content") or "") if img else "",
                    "description": (desc.get("content") or desc.get_text(strip=True)[:200]) if desc else "",
                    "availability": availability_val,
                })

    # Method 4: common PrestaShop product pages without structured metadata.
    if not products and _looks_like_prestashop_product_page(soup):
        title = soup.select_one("h1.h1") or soup.find("h1")
        price = (
            soup.select_one(".product-prices .current-price [content]")
            or soup.select_one(".product-prices .current-price .price")
            or soup.select_one(".current-price .price")
        )
        parsed_price = parse_price(
            price.get("content") if price and price.has_attr("content")
            else price.get_text(" ", strip=True) if price
            else None
        )
        if title and parsed_price is not None:
            brand = soup.select_one('a[href*="/brand/"]')
            image = (
                soup.select_one(".product-cover img")
                or soup.select_one(".product-images img")
                or soup.find("img", attrs={"data-src": True})
            )
            availability = soup.select_one("#product-availability")
            products.append({
                "title": title.get_text(" ", strip=True),
                "price": parsed_price,
                "brand": brand.get_text(" ", strip=True) if brand else "",
                "url": url,
                "domain": domain,
                "image": (
                    image.get("src") or image.get("data-src") or ""
                    if image else ""
                ),
                "availability": (
                    availability.get_text(" ", strip=True) if availability else ""
                ),
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
    "/airsoft-", "/armas-de-airsoft/", "/replica-",
]
SKIP_PATH_HINTS = [
    "/cart", "/basket", "basketedit", "/checkout", "/order",
    "/account", "/login", "/register", "/wishlist", "/compare",
    "product-compare", "/return", "/search", "searching.",
    "captcha", "challenge",
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


def _looks_like_prestashop_product_page(soup: BeautifulSoup) -> bool:
    body_classes = soup.body.get("class", []) if soup.body else []
    return (
        "page-product" in body_classes
        or any(str(cls).startswith("product-id-") for cls in body_classes)
    ) and bool(soup.select_one(".product-prices .current-price"))
