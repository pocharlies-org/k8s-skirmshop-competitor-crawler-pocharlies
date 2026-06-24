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


def test_normalize_strips_f1_stock_fields():
    """_normalize must remove stock/availability fields (F1 scope = catalog+price only)."""
    raw = [
        {
            "title": "Rifle X",
            "price": 199.0,
            "url": "https://x.com/rifle",
            "availability": "http://schema.org/InStock",
            "stock": 5,
            "stock_status": "instock",
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
    for field in ("availability", "stock", "stock_status", "quantity", "qty",
                  "in_stock", "out_of_stock"):
        assert field not in p, f"F1 must not expose '{field}'"
    # Catalog fields still present
    assert p["title"] == "Rifle X"
    assert p["price"] == 199.0
    assert p["domain"] == "x.com"


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
