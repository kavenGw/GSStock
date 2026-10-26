from unittest.mock import Mock

import pandas as pd
import pytest

from app.services.oil_quotes import fetch_oil_quote


def daily_bars():
    return pd.DataFrame({'Close': [100, 102], 'Open': [100, 100],
                         'High': [101, 103], 'Low': [99, 99], 'Volume': [1000, 2000]},
                        index=pd.to_datetime(['2026-10-23', '2026-10-26']).tz_localize('America/New_York'))


def minute_bars(timestamp='2026-10-26T08:00:00Z'):
    return pd.DataFrame({'Close': [98]}, index=pd.to_datetime([timestamp]))


def test_uses_source_minute_time_and_prior_daily_close():
    ticker = Mock()
    ticker.history.return_value = minute_bars()
    result = fetch_oil_quote(ticker, 'CL=F', daily_bars(), '2026-10-26T16:01:00')
    assert result['change_percent'] == pytest.approx(-2)
    assert result['prev_close'] == 100
    assert result['quote_time'] == '2026-10-26T08:00:00+00:00'
    assert result['trading_date'] == '2026-10-26'


def test_evening_quote_uses_just_completed_trading_days_close():
    ticker = Mock()
    ticker.history.return_value = minute_bars('2026-10-26T22:01:00Z')
    result = fetch_oil_quote(ticker, 'CL=F', daily_bars(), '2026-10-27T06:02:00')
    assert result['prev_close'] == 102
    assert result['trading_date'] == '2026-10-27'


@pytest.mark.parametrize('missing', [True, False])
def test_missing_or_timezone_unknown_minute_data_rejected(missing):
    ticker = Mock()
    data = minute_bars()
    data.index = data.index.tz_localize(None)
    ticker.history.return_value = pd.DataFrame() if missing else data
    assert fetch_oil_quote(ticker, 'CL=F', daily_bars(), 'now') is None


@pytest.mark.parametrize('minute_available', [True, False])
def test_unified_fetch_wires_minute_quotes_and_marks_daily_fallback(monkeypatch, minute_available):
    from app.services.unified_stock_data import unified_stock_data_service as service
    ticker = Mock()
    ticker.history.side_effect = [daily_bars(), minute_bars() if minute_available else pd.DataFrame()]
    monkeypatch.setattr('yfinance.Ticker', lambda code: ticker)
    monkeypatch.setattr('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', lambda *a, **kw: None)
    result = service._fetch_realtime_prices(['CL=F'])['CL=F']
    assert result['_is_degraded'] is not minute_available
    assert ('quote_time' in result) is minute_available
