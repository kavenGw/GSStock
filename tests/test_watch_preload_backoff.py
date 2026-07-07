"""watch_preload 按市场限流退避状态机"""
import pytest

from app.strategies.watch_preload import WatchPreloadStrategy


@pytest.fixture
def strategy():
    WatchPreloadStrategy._backoff = {}
    return WatchPreloadStrategy()


def test_no_backoff_initially(strategy):
    assert strategy._should_skip('HK') is False


def test_first_failure_skips_one_tick(strategy):
    strategy._record_result('HK', ok=False)
    assert strategy._should_skip('HK') is True
    assert strategy._should_skip('HK') is False


def test_consecutive_failures_double_capped_at_8(strategy):
    for expected_skip in (1, 2, 4, 8, 8):
        strategy._record_result('HK', ok=False)
        assert strategy._backoff['HK']['skip'] == expected_skip
        strategy._backoff['HK']['remaining'] = 0


def test_success_clears_backoff(strategy):
    strategy._record_result('HK', ok=False)
    strategy._record_result('HK', ok=True)
    assert 'HK' not in strategy._backoff
    assert strategy._should_skip('HK') is False


def test_markets_independent(strategy):
    strategy._record_result('HK', ok=False)
    assert strategy._should_skip('A') is False
    assert strategy._should_skip('HK') is True


def test_prices_ok_threshold():
    codes = ['a', 'b', 'c', 'd']
    good = {'current_price': 10.0}
    assert WatchPreloadStrategy._prices_ok({'a': good, 'b': good}, codes) is True
    assert WatchPreloadStrategy._prices_ok({'a': good}, codes) is False
    assert WatchPreloadStrategy._prices_ok(
        {'a': good, 'b': {'current_price': None}, 'c': {'current_price': 0}}, codes) is False


def test_prices_ok_empty_codes():
    assert WatchPreloadStrategy._prices_ok({}, []) is True
