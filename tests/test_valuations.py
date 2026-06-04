"""估值汇总页测试"""
import pytest

from app.routes.valuations import compute_margin, _extract_price


def test_compute_margin_normal():
    assert compute_margin(7.78, 17.90) == pytest.approx(7.78 / 17.90 - 1)


def test_compute_margin_upside():
    assert compute_margin(20.0, 10.0) == pytest.approx(1.0)


def test_compute_margin_price_none():
    assert compute_margin(7.78, None) is None


def test_compute_margin_price_zero():
    assert compute_margin(7.78, 0) is None


def test_compute_margin_value_none():
    assert compute_margin(None, 17.90) is None


def test_extract_price_prefers_price_key():
    assert _extract_price({'price': 17.9, 'current_price': 99}) == 17.9


def test_extract_price_falls_back_to_current_price():
    assert _extract_price({'current_price': 12.3}) == 12.3


def test_extract_price_missing():
    assert _extract_price({}) is None


def test_extract_price_zero_is_none():
    assert _extract_price({'price': 0}) is None
