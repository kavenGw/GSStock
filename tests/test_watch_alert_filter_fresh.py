"""_filter_fresh 剔除降级/超龄旧价与未命中条目"""
from datetime import datetime, timedelta

from app.strategies.watch_alert import WatchAlertStrategy

MM = {'a': 'A', 'b': 'A', 'h': 'HK'}


def _p(age_seconds=0, **overrides):
    data = {'current_price': 10.0,
            'last_fetch_time': (datetime.now() - timedelta(seconds=age_seconds)).isoformat()}
    data.update(overrides)
    return data


def test_drops_degraded_entry():
    prices = {'a': _p(), 'b': _p(_is_degraded=True)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)) == {'a'}


def test_drops_stale_a_share_beyond_2min():
    prices = {'a': _p(), 'b': _p(age_seconds=180)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)) == {'a'}


def test_keeps_hk_within_2min():
    prices = {'h': _p(age_seconds=100)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['h'], MM)) == {'h'}


def test_drops_entry_without_fetch_time():
    prices = {'a': {'current_price': 10.0}}
    assert WatchAlertStrategy._filter_fresh(prices, ['a'], MM) == {}


def test_drops_missing_code_and_ignores_inactive():
    prices = {'a': _p(), 'x': _p()}
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)
    assert set(result) == {'a'}
