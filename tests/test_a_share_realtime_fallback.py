"""A股实时价兜底链路：主源之一失败先回退到另一健康主源；yfinance 延时价标记降级，不得喂给盯盘告警"""
from unittest.mock import patch

import pandas as pd

from app.services.load_balancer import LoadBalancer
from app.services.price_freshness import is_fresh
from app.services.unified_stock_data import unified_stock_data_service as svc


def _row(code, price):
    return {code: {'code': code, 'current_price': price, 'change_percent': 0.0}}


def test_failed_primary_codes_retry_on_healthy_primary_before_secondary():
    calls = []

    def tencent(codes):
        calls.append(('tencent', list(codes)))
        out = {}
        for c in codes:
            out.update(_row(c, 6.05))
        return out

    def sina(codes):
        calls.append(('sina', list(codes)))
        raise ConnectionError('sina down')

    def eastmoney(codes):
        calls.append(('eastmoney', list(codes)))
        return {}

    def yfinance(codes):
        calls.append(('yfinance', list(codes)))
        return {}

    with patch('app.services.load_balancer.circuit_breaker.is_available', return_value=True), \
         patch('app.services.load_balancer.circuit_breaker.record_success'), \
         patch('app.services.load_balancer.circuit_breaker.record_failure'):
        result = LoadBalancer().fetch_with_priority_balancing(
            ['600519', '000725'],
            {'tencent': tencent, 'sina': sina, 'eastmoney': eastmoney},
            primary_sources=['tencent', 'sina'],
            secondary_sources=['eastmoney'],
            fallback_func=yfinance,
        )

    assert result['000725']['current_price'] == 6.05
    assert ('tencent', ['000725']) in calls
    assert not [c for c in calls if c[0] in ('eastmoney', 'yfinance')]


def test_a_share_yfinance_fallback_is_degraded_and_not_fresh():
    hist = pd.DataFrame(
        {'Open': [6.07, 5.93], 'High': [6.09, 5.98], 'Low': [5.87, 5.79],
         'Close': [5.90, 5.91], 'Volume': [1.5e9, 8.4e8]},
        index=pd.to_datetime(['2026-08-20', '2026-08-21']),
    )

    def only_fallback(codes, fetch_funcs, primary_sources=None, secondary_sources=None, fallback_func=None):
        return fallback_func(codes)

    with patch('app.services.unified_stock_data.load_balancer.fetch_with_priority_balancing', only_fallback), \
         patch('yfinance.Ticker') as mock_yf:
        mock_yf.return_value.history.return_value = hist
        result = svc._fetch_a_share_prices(['000725'], pd.Timestamp('2026-08-21').date(), '2026-08-21T13:33:00')

    data = result['000725']
    assert data['current_price'] == 5.91
    assert data['_is_degraded'] is True
    assert not is_fresh(data, 'A', now=pd.Timestamp('2026-08-21T13:33:10').to_pydatetime())
