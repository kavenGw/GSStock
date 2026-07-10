"""scan() 用 cache_only 读价、过滤降级、删除 BENCHMARK 死代码"""
import inspect

from app.strategies.watch_alert import WatchAlertStrategy


def test_scan_uses_cache_only():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert 'cache_only=True' in src


def test_scan_calls_filter_fresh():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert '_filter_fresh' in src


def test_scan_has_no_benchmark_dead_code():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert 'BENCHMARK_CODES' not in src
    assert 'bench_codes' not in src


def test_module_no_benchmark_import():
    import app.strategies.watch_alert as mod
    src = inspect.getsource(mod)
    assert 'BENCHMARK_CODES' not in src


def test_degraded_price_excluded_end_to_end():
    """降级旧价(_is_degraded)经 _filter_fresh 后既不产生信号也不污染盘中极值"""
    from app.strategies.watch_alert import WatchAlertStrategy
    from app.services.watch_alert_service import WatchAlertService

    prices = {
        'FRESH': {'current_price': 10.0},
        '2631.HK': {'current_price': 81.5, '_is_degraded': True},
    }
    watch_prices = WatchAlertStrategy._filter_fresh(prices, ['FRESH', '2631.HK'])

    service = WatchAlertService()
    service._intraday_extremes = {}
    service._last_trading_date = None
    signals = service.check_alerts(watch_prices, {'FRESH': 'Fresh', '2631.HK': '天岳'})

    assert '2631.HK' not in service._intraday_extremes
    assert all(s.data.get('stock_code') != '2631.HK' for s in signals)
