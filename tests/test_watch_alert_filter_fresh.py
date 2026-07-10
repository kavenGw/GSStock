"""_filter_fresh 剔除降级旧价(_is_degraded)与未命中条目"""
from app.strategies.watch_alert import WatchAlertStrategy


def test_drops_degraded_entry():
    prices = {
        'a': {'current_price': 10.0},
        'b': {'current_price': 81.5, '_is_degraded': True},
    }
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'])
    assert result == {'a': {'current_price': 10.0}}


def test_drops_missing_code():
    result = WatchAlertStrategy._filter_fresh({'a': {'current_price': 10.0}}, ['a', 'b'])
    assert set(result) == {'a'}


def test_ignores_inactive_codes():
    prices = {'a': {'current_price': 10.0}, 'x': {'current_price': 5.0}}
    result = WatchAlertStrategy._filter_fresh(prices, ['a'])
    assert set(result) == {'a'}


def test_keeps_all_fresh():
    prices = {'a': {'current_price': 10.0}, 'b': {'current_price': 20.0}}
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'])
    assert result == prices
