"""Unit tests for F2 stock normalization (src/stock.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.stock import normalize_availability


# ---------------------------------------------------------------------------
# in_stock cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "http://schema.org/InStock",
    "https://schema.org/InStock",
    "https://www.schema.org/InStock",
    "InStock",
    "instock",
    "http://schema.org/LimitedAvailability",
    "LimitedAvailability",
    "http://schema.org/InStoreOnly",
    "InStoreOnly",
    "http://schema.org/OnlineOnly",
    "OnlineOnly",
])
def test_in_stock_variants(raw):
    status, method = normalize_availability(raw)
    assert status == "in_stock", f"Expected in_stock for {raw!r}, got {status!r}"
    assert method == "visible"


# ---------------------------------------------------------------------------
# out_of_stock cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "http://schema.org/OutOfStock",
    "https://schema.org/OutOfStock",
    "OutOfStock",
    "outofstock",
    "http://schema.org/SoldOut",
    "SoldOut",
    "http://schema.org/Discontinued",
    "Discontinued",
])
def test_out_of_stock_variants(raw):
    status, method = normalize_availability(raw)
    assert status == "out_of_stock", f"Expected out_of_stock for {raw!r}, got {status!r}"
    assert method == "visible"


# ---------------------------------------------------------------------------
# unknown cases — never infer from absence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    None,
    "",
    "http://schema.org/PreOrder",
    "PreOrder",
    "preorder",
    "http://schema.org/PreSale",
    "PreSale",
    "http://schema.org/BackOrder",
    "BackOrder",
    "SomeCustomValue",
    "5",          # numeric quantity string must not become in_stock
    "true",
])
def test_unknown_variants(raw):
    status, method = normalize_availability(raw)
    assert status == "unknown", f"Expected unknown for {raw!r}, got {status!r}"
    assert method == "unknown"


# ---------------------------------------------------------------------------
# Absence must not infer out_of_stock
# ---------------------------------------------------------------------------

def test_absence_is_not_out_of_stock():
    status, _ = normalize_availability(None)
    assert status != "out_of_stock"
    status, _ = normalize_availability("")
    assert status != "out_of_stock"
