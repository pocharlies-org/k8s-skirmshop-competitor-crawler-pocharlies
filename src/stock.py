"""F2 Visible Stock — availability normalization.

Maps schema.org availability URLs/short-names to normalized
stock_status and stock_method.

stock_status : in_stock | out_of_stock | unknown
stock_method : visible  | unknown

Rules (from RSO F2 spec):
  in_stock  ← InStock, LimitedAvailability, InStoreOnly, OnlineOnly
  out_of_stock ← OutOfStock, SoldOut, Discontinued
  unknown   ← PreOrder, PreSale, BackOrder, absent, ambiguous, numeric-only
"""
from __future__ import annotations

# schema.org short names (lower-cased) that map to in_stock
_IN_STOCK_VALS: frozenset[str] = frozenset({
    "instock",
    "limitedavailability",
    "instoreonly",
    "onlineonly",
})

# schema.org short names (lower-cased) that map to out_of_stock
_OUT_OF_STOCK_VALS: frozenset[str] = frozenset({
    "outofstock",
    "soldout",
    "discontinued",
})

# Everything else (PreOrder, PreSale, BackOrder, absent, custom) → unknown


_SCHEMA_PREFIXES: tuple[str, ...] = (
    "https://schema.org/",
    "http://schema.org/",
    "https://www.schema.org/",
    "http://www.schema.org/",
)


def _strip_schema_prefix(raw: str) -> str:
    """Remove schema.org URL prefix and return the short name."""
    for prefix in _SCHEMA_PREFIXES:
        if raw.startswith(prefix):
            return raw[len(prefix):]
    return raw


def normalize_availability(raw: str | None) -> tuple[str, str]:
    """Return (stock_status, stock_method) from a raw availability string.

    Args:
        raw: value from JSON-LD offers.availability, microdata itemprop=availability,
             or any plain-text availability hint.

    Returns:
        (stock_status, stock_method) — never raises.
    """
    if not raw or not isinstance(raw, str):
        return "unknown", "unknown"

    short = _strip_schema_prefix(raw.strip())
    key = short.lower()

    if key in _IN_STOCK_VALS:
        return "in_stock", "visible"
    if key in _OUT_OF_STOCK_VALS:
        return "out_of_stock", "visible"
    return "unknown", "unknown"
