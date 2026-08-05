"""港股实时价路由单测：腾讯优先，缺失并入 yfinance 兜底"""
from unittest.mock import patch

from app.services.unified_stock_data import unified_stock_data_service as svc


HK_OK = {'1888.HK': {
    'code': '1888.HK', 'name': '建滔积层板', 'current_price': 34.6,
    'prev_close': 31.12, 'open': 31.12, 'volume': 118191487,
    'high': 34.76, 'low': 30.5, 'change': 3.48, 'change_percent': 11.18,
    'last_fetch_time': '2026-08-05T13:20:00', 'market': 'HK',
}}


def _no_cache(*args, **kwargs):
    return None


def test_hk_served_by_tencent_without_yfinance():
    with patch.object(svc, '_fetch_from_tencent', return_value=HK_OK) as mock_tc, \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        result = svc._fetch_realtime_prices(['1888.HK'])
    mock_tc.assert_called_once()
    assert mock_tc.call_args[0][0] == ['1888.HK']
    mock_yf.assert_not_called()
    assert result['1888.HK']['current_price'] == 34.6
    assert result['1888.HK']['market'] == 'HK'


def test_hk_falls_back_to_yfinance_when_tencent_empty():
    with patch.object(svc, '_fetch_from_tencent', return_value={}), \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        mock_yf.return_value.history.return_value.empty = True
        svc._fetch_realtime_prices(['1888.HK'])
    mock_yf.assert_called_once()


def test_hk_falls_back_when_tencent_raises():
    with patch.object(svc, '_fetch_from_tencent', side_effect=OSError('timeout')), \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        mock_yf.return_value.history.return_value.empty = True
        svc._fetch_realtime_prices(['1888.HK'])
    mock_yf.assert_called_once()
