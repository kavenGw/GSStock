import os
from unittest.mock import patch, MagicMock

from app.services.load_balancer import MARKET_SOURCES, LoadBalancer


def test_market_sources_a_prioritizes_hithink():
    cfg = MARKET_SOURCES['A']
    assert cfg['primary_sources'] == ['hithink']
    assert cfg['secondary_sources'] == ['tencent', 'sina', 'eastmoney']
    assert cfg['fallback'] == 'yfinance'


def test_a_share_primary_constants():
    assert LoadBalancer.A_SHARE_PRIMARY == ['hithink']
    assert LoadBalancer.A_SHARE_SECONDARY == ['tencent', 'sina', 'eastmoney']


def _run_fetch(env):
    """跑 _fetch_a_share_prices，捕获传给负载均衡器的参数。"""
    from datetime import date

    from app.services.unified_stock_data import UnifiedStockDataService

    captured = {}

    def fake_balance(stock_codes, fetch_funcs, primary_sources=None,
                     secondary_sources=None, fallback_func=None):
        captured['funcs'] = sorted(fetch_funcs)
        captured['primary'] = primary_sources
        captured['secondary'] = secondary_sources
        return {}

    svc = UnifiedStockDataService.__new__(UnifiedStockDataService)
    with patch.dict(os.environ, env, clear=True):
        with patch('app.services.unified_stock_data.load_balancer') as lb:
            lb.fetch_with_priority_balancing.side_effect = fake_balance
            svc._fetch_a_share_prices(['600519'], date(2026, 9, 4), '2026-09-04 15:00:00')
    return captured


def test_hithink_registered_as_sole_primary_when_key_present():
    c = _run_fetch({'HITHINK_FINANCE_API_KEY': 'sk-test'})
    assert 'hithink' in c['funcs']
    assert c['primary'] == ['hithink']
    assert c['secondary'] == ['tencent', 'sina', 'eastmoney']


def test_safety_valve_without_key_matches_pre_integration_behavior():
    """未配 key 时调用序列必须与接入前逐字节一致。"""
    c = _run_fetch({})
    assert c['funcs'] == ['eastmoney', 'sina', 'tencent']
    assert c['primary'] == ['tencent', 'sina']
    assert c['secondary'] == ['eastmoney']
