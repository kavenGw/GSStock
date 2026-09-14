"""美股暗盘（盘前/盘后）：时段判断、yfinance 解析、/prices ext 字段、市场状态文案、预取调度"""
from datetime import datetime

import pytz
from flask import Flask

from app.routes import watch_bp
from app.services.trading_calendar import TradingCalendarService
from app.services.unified_stock_data import (
    UnifiedStockDataService, unified_stock_data_service)
from app.services.watch_service import WatchService
from app.strategies.watch_preload import WatchPreloadStrategy


# 2026-07-06 周一为纽约交易日；2026-07-11 周六
def _et(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)


class TestUsExtendedSession:
    def test_before_0400_is_none(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 3, 59)) is None

    def test_0400_is_pre(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 4, 0)) == 'pre'

    def test_0929_is_pre(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 9, 29)) == 'pre'

    def test_regular_hours_is_none(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 9, 30)) is None
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 16, 0)) is None

    def test_1601_is_post(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 16, 1)) == 'post'

    def test_2000_is_post_2001_is_none(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 20, 0)) == 'post'
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 6, 20, 1)) is None

    def test_weekend_is_none(self):
        assert TradingCalendarService.get_us_extended_session(_et(2026, 7, 11, 8, 0)) is None


class TestParseExtendedQuote:
    def test_pre_market(self):
        info = {'marketState': 'PRE', 'preMarketPrice': 212.5175,
                'preMarketChangePercent': -2.6444142, 'preMarketTime': 1789389705,
                'postMarketPrice': None}
        q = UnifiedStockDataService._parse_extended_quote(info)
        assert q['session'] == 'pre'
        assert q['price'] == 212.52
        assert q['change_pct'] == -2.64
        assert q['time'] == '2026-09-14T08:41:45-04:00'

    def test_post_market(self):
        info = {'marketState': 'POST', 'postMarketPrice': 100.123,
                'postMarketChangePercent': 1.234, 'postMarketTime': 1789430400}
        q = UnifiedStockDataService._parse_extended_quote(info)
        assert q['session'] == 'post'
        assert q['price'] == 100.12 and q['change_pct'] == 1.23

    def test_closed_with_post_price_still_post(self):
        info = {'marketState': 'CLOSED', 'postMarketPrice': 50.0,
                'postMarketChangePercent': -0.5, 'postMarketTime': 1789430400}
        assert UnifiedStockDataService._parse_extended_quote(info)['session'] == 'post'

    def test_regular_or_missing_returns_none(self):
        assert UnifiedStockDataService._parse_extended_quote({'marketState': 'REGULAR'}) is None
        assert UnifiedStockDataService._parse_extended_quote({'marketState': 'PRE'}) is None
        assert UnifiedStockDataService._parse_extended_quote({}) is None


class TestGetUsExtendedQuotes:
    def test_fetch_parse_and_cache(self, monkeypatch):
        from app.services import memory_cache as mc
        svc = unified_stock_data_service
        calls = []

        def fake_info(yf_code):
            calls.append(yf_code)
            return {'marketState': 'PRE', 'preMarketPrice': 10.0,
                    'preMarketChangePercent': 2.0, 'preMarketTime': 1789389600}

        monkeypatch.setattr(svc, '_fetch_yf_info', fake_info)
        mc.memory_cache.invalidate(cache_type='extended')

        out = svc.get_us_extended_quotes(['NVDA', 'AMD'], force_refresh=True)
        assert set(out) == {'NVDA', 'AMD'}
        assert out['NVDA']['session'] == 'pre' and out['NVDA']['price'] == 10.0
        assert sorted(calls) == ['AMD', 'NVDA']

        cached = svc.get_us_extended_cached(['NVDA', 'AMD', 'LITE'])
        assert cached['NVDA']['price'] == 10.0
        assert 'LITE' not in cached

    def test_failed_ticker_skipped(self, monkeypatch):
        svc = unified_stock_data_service

        def fake_info(yf_code):
            if yf_code == 'WOLF':
                raise RuntimeError('boom')
            return {'marketState': 'POST', 'postMarketPrice': 1.0,
                    'postMarketChangePercent': 0.0, 'postMarketTime': 1789430400}

        monkeypatch.setattr(svc, '_fetch_yf_info', fake_info)
        out = svc.get_us_extended_quotes(['WOLF', 'SOXX'], force_refresh=True)
        assert set(out) == {'SOXX'}


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(watch_bp, url_prefix='/watch')
    return app.test_client()


def test_prices_attaches_ext_for_us_only(monkeypatch):
    from app.services import unified_stock_data as usd
    svc = usd.unified_stock_data_service
    monkeypatch.setattr(WatchService, 'get_watch_codes',
                        staticmethod(lambda: ['NVDA', '0700.HK']))
    monkeypatch.setattr(svc, 'get_prices_cached_only',
                        lambda codes: ({c: {'current_price': 1.0, 'change_percent': 0.1,
                                            'name': c, 'market': 'X'} for c in codes}, []))
    monkeypatch.setattr(svc, 'get_a_share_index_quotes',
                        lambda codes, force_refresh=False, cache_only=False: {})
    ext = {'NVDA': {'session': 'pre', 'price': 212.52, 'change_pct': -2.64,
                    'time': '2026-09-14T08:41:45-04:00'}}
    monkeypatch.setattr(svc, 'get_us_extended_cached', lambda codes: ext)

    resp = _make_client().get('/watch/prices').get_json()
    by_code = {p['code']: p for p in resp['prices']}
    assert by_code['NVDA']['ext'] == ext['NVDA']
    assert by_code['0700.HK']['ext'] is None


class TestMarketStatusExtended:
    def _patch(self, monkeypatch, et_time):
        monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['US']))
        tz = pytz.timezone('America/New_York')
        monkeypatch.setattr(TradingCalendarService, 'get_market_now',
                            classmethod(lambda cls, market: tz.localize(et_time)))
        monkeypatch.setattr(TradingCalendarService, 'is_trading_day',
                            classmethod(lambda cls, market, dt=None: True))

    def test_pre_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 8, 0))
        us = _make_client().get('/watch/market-status').get_json()['data']['US']
        assert us['status'] == 'pre_market' and us['status_text'] == '盘前'

    def test_post_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 17, 0))
        us = _make_client().get('/watch/market-status').get_json()['data']['US']
        assert us['status'] == 'post_market' and us['status_text'] == '盘后'

    def test_late_night_closed(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 21, 0))
        us = _make_client().get('/watch/market-status').get_json()['data']['US']
        assert us['status'] == 'closed'

    def test_early_morning_pre_open(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 3, 0))
        us = _make_client().get('/watch/market-status').get_json()['data']['US']
        assert us['status'] == 'pre_open'


class TestPreloadExtended:
    def _setup(self, monkeypatch, session, tick=0):
        from app.services import unified_stock_data as usd
        svc = usd.unified_stock_data_service
        monkeypatch.setattr(WatchService, 'get_watch_codes',
                            staticmethod(lambda: ['NVDA', 'AMD', '0700.HK']))
        monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['US', 'HK']))
        monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                            classmethod(lambda cls, market, dt=None: False))
        monkeypatch.setattr(TradingCalendarService, 'get_us_extended_session',
                            classmethod(lambda cls, dt=None: session))
        called = []
        monkeypatch.setattr(svc, 'get_us_extended_quotes',
                            lambda codes, force_refresh=False: called.append((sorted(codes), force_refresh)) or {})
        monkeypatch.setattr(svc, 'get_realtime_prices',
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError('盘外不应取正股价')))
        strat = WatchPreloadStrategy()
        strat._tick_count = tick
        return strat, called

    def test_pre_session_fetches_us_codes(self, monkeypatch):
        strat, called = self._setup(monkeypatch, 'pre')
        strat.scan()
        assert called == [(['AMD', 'NVDA'], True)]

    def test_no_session_skips(self, monkeypatch):
        strat, called = self._setup(monkeypatch, None)
        strat.scan()
        assert called == []

    def test_respects_three_tick_cadence(self, monkeypatch):
        strat, called = self._setup(monkeypatch, 'post', tick=1)
        strat.scan()
        assert called == []
