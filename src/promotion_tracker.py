"""Detect promotions in scraped product data.

Pure-function port of the brain's PromotionTracker. Drops the PG
PriceSnapshot/PriceAlert sides — those live in the brain. We just
flag `is_promotion` + `promo_text` so the brain's product_matcher /
pricing_context can surface them downstream.
"""
import re
from typing import Optional

PROMO_PATTERNS = [
    # ES
    r'oferta', r'descuento', r'rebajas?', r'liquidaci[oó]n', r'outlet',
    r'black\s*friday', r'cyber\s*monday', r'navidad', r'especial',
    r'ahorra', r'gratis', r'regalo',
    # EN
    r'sale', r'clearance', r'discount', r'deal', r'special\s+offer',
    r'limited\s+time', r'flash\s+sale', r'bundle', r'save\s+\d+',
    r'free\s+shipping', r'bogo', r'was\s+[\d€$]',
    # universal
    r'-\s*\d+\s*%',
]
PROMO_RE = re.compile("|".join(PROMO_PATTERNS), re.IGNORECASE)


def detect_promotion(product: dict) -> Optional[dict]:
    """Return promo info dict or None."""
    title = product.get("title", "")
    description = product.get("description", "")
    price = product.get("price")
    original = (product.get("compare_at_price") or product.get("original_price")
                or product.get("compareAtPrice"))
    text = f"{title} {description}".lower()

    # Method 1: explicit compare-at price
    if price and original:
        try:
            cur = float(price)
            orig = float(original)
            if orig > cur > 0:
                pct = round((orig - cur) / orig * 100, 1)
                return {
                    "is_promotion": True,
                    "promo_type": "sale",
                    "original_price": orig,
                    "sale_price": cur,
                    "discount_pct": pct,
                    "promo_text": f"-{pct}% off (was €{orig:.2f})",
                }
        except (ValueError, TypeError):
            pass

    # Method 2: keyword detection in title/description
    m = PROMO_RE.search(text)
    if m:
        return {
            "is_promotion": True,
            "promo_type": "keyword",
            "promo_text": m.group(0)[:50],
        }
    return None
