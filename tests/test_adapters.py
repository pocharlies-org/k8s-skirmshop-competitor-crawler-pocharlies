"""Tests for adapters: microdata URL extraction and adapter normalization/counts."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extractor import extract_products
from src.adapters.base import AdapterResult, BaseSiteAdapter
from src.adapters.generic_html import GenericHtmlAdapter


# ---------------------------------------------------------------------------
# Microdata URL extraction
# ---------------------------------------------------------------------------

_MICRODATA_HTML = """<html><body>
<div itemscope itemtype="https://schema.org/Product">
  <span itemprop="name">Test Rifle</span>
  <link itemprop="url" href="https://example.com/products/test-rifle"/>
  <span itemprop="price" content="199.95">199.95</span>
  <span itemprop="brand">TestBrand</span>
</div>
</body></html>"""


def test_microdata_product_url_extracted():
    """Microdata itemprop=url must be preserved in the extracted product."""
    products = extract_products(_MICRODATA_HTML, "https://example.com/catalog", "example.com")
    assert len(products) == 1
    assert products[0]["url"] == "https://example.com/products/test-rifle"


def test_microdata_url_falls_back_to_page_url():
    """When itemprop=url is absent, product url == page url."""
    html = """<html><body>
    <div itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Pistol</span>
      <span itemprop="price" content="89.00">89.00</span>
    </div>
    </body></html>"""
    products = extract_products(html, "https://example.com/p/pistol", "example.com")
    assert len(products) == 1
    assert products[0]["url"] == "https://example.com/p/pistol"


# ---------------------------------------------------------------------------
# Adapter normalization and counts
# ---------------------------------------------------------------------------

class _StubAdapter(BaseSiteAdapter):
    name = "stub"

    def __init__(self, domain, source_url, raw_products):
        super().__init__(domain, source_url)
        self._raw = raw_products

    async def fetch_page(self, url):
        return "<html/>"

    def extract_products(self, html, url):
        return self._raw


def _run(coro):
    return asyncio.run(coro)


def test_adapter_counts_success_and_discard():
    """Products missing title or price must be discarded; good ones counted."""
    raw = [
        {"title": "Product A", "price": 50.0, "url": "https://x.com/a"},
        {"title": "", "price": 10.0},          # no title -> discard
        {"title": "Product B", "price": None},  # no price -> discard
        {"title": "Product C", "price": 30.0, "url": "https://x.com/c"},
    ]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.candidates == 4
    assert result.success == 2
    assert result.discarded == 2
    assert result.failures == 0
    assert result.discard_ratio == 0.5


def test_adapter_limit_caps_success_not_discard():
    """Products beyond the limit are not attempted; discarded stays at 0."""
    raw = [{"title": f"P{i}", "price": float(i)} for i in range(10)]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=3))
    assert result.candidates == 10
    assert result.success == 3
    # beyond-limit products are simply not attempted; discard = 0
    assert result.discarded == 0


def test_adapter_normalize_attaches_domain_and_source_id():
    """_normalize must attach domain and source_id."""
    raw = [{"title": "Gun", "price": 100.0, "url": "https://y.com/p/gun"}]
    adapter = _StubAdapter("y.com", "https://y.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.success == 1
    p = result.products[0]
    assert p["domain"] == "y.com"
    assert p["source_id"] == "competitor:y.com:https://y.com/p/gun"


def test_normalize_strips_raw_stock_fields_and_exposes_f2_contract():
    """_normalize must strip raw stock/availability fields and expose F2 contract fields.

    Raw fields (availability, stock, quantity, qty, in_stock, out_of_stock) must be absent.
    F2 fields (stock_status, stock_method) must be present with correct values.
    """
    raw = [
        {
            "title": "Rifle X",
            "price": 199.0,
            "url": "https://x.com/rifle",
            "availability": "http://schema.org/InStock",
            "stock": 5,
            "stock_status": "instock",   # raw value — must be replaced by normalized
            "quantity": 10,
            "qty": 10,
            "in_stock": True,
            "out_of_stock": False,
        }
    ]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.success == 1
    p = result.products[0]
    # Raw fields must not be present
    for field in ("availability", "stock", "quantity", "qty", "in_stock", "out_of_stock"):
        assert field not in p, f"Raw field '{field}' must not be in normalized output"
    # F2 contract fields must be present and correct
    assert p["stock_status"] == "in_stock", f"Expected in_stock, got {p['stock_status']!r}"
    assert p["stock_method"] == "visible", f"Expected visible, got {p['stock_method']!r}"
    # Catalog fields still present
    assert p["title"] == "Rifle X"
    assert p["price"] == 199.0
    assert p["domain"] == "x.com"


def test_normalize_unknown_when_no_availability():
    """When availability is absent, stock_status/stock_method must be unknown."""
    raw = [{"title": "Pistol", "price": 89.0, "url": "https://x.com/pistol"}]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.success == 1
    p = result.products[0]
    assert p["stock_status"] == "unknown"
    assert p["stock_method"] == "unknown"
    # Must not expose numeric stock
    assert "stock_qty" not in p
    assert "quantity" not in p
    assert "qty" not in p


def test_normalize_out_of_stock_from_availability():
    """OutOfStock availability must produce stock_status=out_of_stock."""
    raw = [{
        "title": "Sold Out Gun",
        "price": 150.0,
        "url": "https://x.com/sold",
        "availability": "http://schema.org/OutOfStock",
    }]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    p = result.products[0]
    assert p["stock_status"] == "out_of_stock"
    assert p["stock_method"] == "visible"


def test_normalize_strips_extended_raw_stock_aliases():
    """F2 patch: stock_qty, stock_method (raw), qty_available, units_left, units,
    count, stock_count must not appear in output; F2 fields must be correct.
    """
    raw = [
        {
            "title": "Carbine Z",
            "price": 299.0,
            "url": "https://x.com/carbine",
            "availability": "http://schema.org/InStock",
            # raw aliases that must be stripped
            "stock_qty": 3,
            "stock_count": 3,
            "stock_method": "numeric",  # raw — must be replaced
            "qty_available": 3,
            "units_left": 3,
            "units": 3,
            "count": 3,
            # already-covered fields still included for regression
            "stock": 3,
            "quantity": 3,
            "qty": 3,
            "in_stock": True,
            "out_of_stock": False,
            "stock_status": "InStock",  # raw — must be replaced
        }
    ]
    adapter = _StubAdapter("x.com", "https://x.com/shop", raw)
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.success == 1
    p = result.products[0]
    _FORBIDDEN = (
        "availability", "stock", "stock_qty", "stock_count",
        "quantity", "qty", "qty_available", "units_left", "units", "count",
        "in_stock", "out_of_stock",
    )
    for field in _FORBIDDEN:
        assert field not in p, f"Forbidden raw field '{field}' leaked into normalized output"
    # stock_method must be the F2-computed value, not the raw "numeric"
    assert p["stock_status"] == "in_stock", f"Got {p['stock_status']!r}"
    assert p["stock_method"] == "visible", f"Got {p['stock_method']!r}"
    assert p["title"] == "Carbine Z"


def test_adapter_fetch_failure_increments_failures():
    """If fetch_page returns None, failures must be 1 and products empty."""
    class _FailAdapter(_StubAdapter):
        async def fetch_page(self, url):
            return None
    adapter = _FailAdapter("z.com", "https://z.com/shop", [])
    result: AdapterResult = _run(adapter.run(limit=50))
    assert result.failures == 1
    assert result.success == 0
    assert result.products == []
