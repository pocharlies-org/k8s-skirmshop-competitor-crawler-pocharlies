"""Smoke tests for extractor — JSON-LD / OG / microdata, price parsing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.extractor import extract_products, is_product_url, parse_price


def test_parse_price_eur():
    assert parse_price("€569.00") == 569.00
    assert parse_price("569,00") == 569.00
    assert parse_price("$ 99.99 EUR") == 99.99


def test_parse_price_invalid():
    assert parse_price("") is None
    assert parse_price(None) is None
    assert parse_price("foo") is None


def test_extract_products_jsonld():
    html = """<html><body>
    <script type="application/ld+json">{
      "@type": "Product",
      "name": "Silverback SRS A2 16 Covert",
      "brand": {"name": "Silverback"},
      "sku": "SBA-COVERT-16",
      "offers": {"price": "569.00"}
    }</script></body></html>"""
    products = extract_products(html, "https://gunfire.com/p/srs", "gunfire.com")
    assert len(products) == 1
    p = products[0]
    assert p["title"] == "Silverback SRS A2 16 Covert"
    assert p["brand"] == "Silverback"
    assert p["price"] == 569.0
    assert p["sku_raw"] == "SBA-COVERT-16"


def test_extract_products_open_graph_fallback():
    html = """<html><head>
    <meta property="og:title" content="Some Product">
    <meta property="product:price:amount" content="42.50">
    <meta property="product:brand" content="ACME">
    </head></html>"""
    products = extract_products(html, "https://example.com/p/x", "example.com")
    assert len(products) == 1
    assert products[0]["price"] == 42.50
    assert products[0]["brand"] == "ACME"


def test_extract_products_prestashop_product_fallback():
    html = """<html><body class="page-product product-id-25061">
      <h1 class="h1">EC MCX AEG SPEAR-LT</h1>
      <div class="product-prices">
        <div class="current-price">
          <div class="current-price-display price">359<span>,00 EUR</span></div>
        </div>
      </div>
      <a href="https://fullmetal.es/brand/ec">E&amp;C</a>
      <span id="product-availability">En stock</span>
      <img data-src="https://fullmetal.es/product.jpg">
    </body></html>"""

    products = extract_products(
        html,
        "https://fullmetal.es/armas-de-airsoft/armas-electricas/ec-mcx",
        "fullmetal.es",
    )

    assert len(products) == 1
    assert products[0]["title"] == "EC MCX AEG SPEAR-LT"
    assert products[0]["price"] == 359.0
    assert products[0]["brand"] == "E&C"
    assert products[0]["availability"] == "En stock"


def test_prestashop_category_page_is_not_product_without_product_body_class():
    html = """<html><body class="page-category">
      <h1 class="h1">Armas Electricas</h1>
      <div class="product-prices"><div class="current-price">
        <div class="price">359,00 EUR</div>
      </div></div>
    </body></html>"""

    assert extract_products(html, "https://fullmetal.es/armas-electricas", "fullmetal.es") == []


def test_is_product_url_positive():
    assert is_product_url("https://gunfire.com/products/srs-a2-16-covert")
    assert is_product_url("https://taiwangun.com/p/replica")
    assert is_product_url("https://example.com/airsoft-rifle-12")
    assert is_product_url(
        "https://fullmetal.es/armas-de-airsoft/armas-electricas/fusiles/ec-mcx"
    )


def test_is_product_url_negative():
    assert not is_product_url("https://gunfire.com/cart")
    assert not is_product_url("https://gunfire.com/account/login")
    assert not is_product_url("https://gunfire.com/img/banner.png")
