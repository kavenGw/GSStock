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
