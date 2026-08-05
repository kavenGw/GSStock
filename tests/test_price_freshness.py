"""价格新鲜度闸门纯函数单测"""
from datetime import datetime, timedelta

from app.services.price_freshness import (
    max_age_seconds, price_age_seconds, is_fresh, filter_fresh_prices,
)


def _p(age_seconds=0, **overrides):
    data = {
        'current_price': 10.0,
        'last_fetch_time': (datetime.now() - timedelta(seconds=age_seconds)).isoformat(),
    }
    data.update(overrides)
    return data


def test_max_age_by_market():
    assert max_age_seconds('A') == 120
    assert max_age_seconds('HK') == 120
    assert max_age_seconds('US') == 360
    assert max_age_seconds('') == 360


def test_a_share_fresh_within_2min():
    assert is_fresh(_p(age_seconds=110), 'A')


def test_a_share_stale_beyond_2min():
    assert not is_fresh(_p(age_seconds=130), 'A')


def test_non_a_fresh_within_6min():
    assert is_fresh(_p(age_seconds=350), 'US')


def test_hk_fresh_within_2min():
    assert is_fresh(_p(age_seconds=119), 'HK')


def test_hk_stale_beyond_2min():
    assert not is_fresh(_p(age_seconds=121), 'HK')


def test_non_a_stale_beyond_6min():
    assert not is_fresh(_p(age_seconds=370), 'US')


def test_degraded_rejected_even_if_recent():
    assert not is_fresh(_p(age_seconds=5, _is_degraded=True), 'A')


def test_missing_fetch_time_rejected():
    assert not is_fresh({'current_price': 10.0}, 'A')


def test_garbage_fetch_time_rejected():
    assert not is_fresh({'current_price': 10.0, 'last_fetch_time': 'not-a-date'}, 'A')


def test_missing_price_rejected():
    assert not is_fresh(_p(age_seconds=5, current_price=None), 'A')


def test_filter_mixed_markets():
    prices = {
        'a_fresh': _p(100), 'a_stale': _p(180),
        'us_fresh': _p(180), 'us_stale': _p(400),
    }
    market_map = {'a_fresh': 'A', 'a_stale': 'A', 'us_fresh': 'US', 'us_stale': 'US'}
    assert set(filter_fresh_prices(prices, market_map)) == {'a_fresh', 'us_fresh'}


def test_filter_unknown_market_uses_non_a_default():
    assert set(filter_fresh_prices({'x': _p(300)}, {})) == {'x'}
    assert set(filter_fresh_prices({'x': _p(400)}, {})) == set()


def test_price_age_seconds():
    ts = (datetime.now() - timedelta(seconds=90)).isoformat()
    assert 85 <= price_age_seconds({'last_fetch_time': ts}) <= 95
    assert price_age_seconds({}) is None
    assert price_age_seconds({'last_fetch_time': 'garbage'}) is None
