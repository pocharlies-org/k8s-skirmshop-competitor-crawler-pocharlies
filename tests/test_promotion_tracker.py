import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.promotion_tracker import detect_promotion


def test_compare_at_price():
    p = detect_promotion({"price": 80.0, "compare_at_price": 100.0})
    assert p["is_promotion"] is True
    assert p["discount_pct"] == 20.0
    assert "20.0%" in p["promo_text"]


def test_es_keyword():
    p = detect_promotion({"title": "Oferta especial Marui MWS"})
    assert p["is_promotion"] is True
    assert p["promo_type"] == "keyword"


def test_en_keyword():
    p = detect_promotion({"title": "Limited time sale", "description": "Save 30%"})
    assert p is not None
    assert p["is_promotion"] is True


def test_no_promo():
    p = detect_promotion({"title": "Standard product", "description": "Just a description"})
    assert p is None


def test_compare_at_no_discount():
    # Same price → no promo
    p = detect_promotion({"price": 100.0, "compare_at_price": 100.0})
    assert p is None
