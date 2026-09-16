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


class TestUsSession:
    def test_0359_is_overnight(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 3, 59)) == 'overnight'

    def test_0400_is_pre(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 4, 0)) == 'pre'

    def test_0929_is_pre(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 9, 29)) == 'pre'

    def test_0930_to_1559_is_regular(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 9, 30)) == 'regular'
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 15, 59)) == 'regular'

    def test_1600_is_post(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 16, 0)) == 'post'

    def test_1959_is_post(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 19, 59)) == 'post'

    def test_2000_is_overnight(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 20, 0)) == 'overnight'

    def test_friday_night_is_not_overnight(self):
        # 周五 20:00 后次日为周六，非交易日 → 无夜盘
        assert TradingCalendarService.get_us_session(_et(2026, 7, 10, 20, 0)) is None
        assert TradingCalendarService.get_us_session(_et(2026, 7, 10, 23, 0)) is None

    def test_sunday_night_is_overnight(self):
        # 周日 20:00 后次日为周一，归属周一的夜盘
        assert TradingCalendarService.get_us_session(_et(2026, 7, 12, 20, 0)) == 'overnight'

    def test_saturday_is_none(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 11, 2, 0)) is None
        assert TradingCalendarService.get_us_session(_et(2026, 7, 11, 8, 0)) is None

    def test_half_day_post_starts_at_close(self, monkeypatch):
        # 半日市 13:00 收盘：13:00 起即为 post，而非 regular
        from datetime import time as _time
        monkeypatch.setattr(TradingCalendarService, 'get_market_hours',
                            classmethod(lambda cls, market, dt=None: (_time(9, 30), _time(13, 0))))
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 12, 59)) == 'regular'
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 13, 0)) == 'post'


class TestParseExtendedQuote:
    def test_pre_market(self):
        info = {'preMarketPrice': 212.5175, 'preMarketChangePercent': -2.6444142,
                'preMarketTime': 1789389705}
        q = UnifiedStockDataService._parse_extended_quote(info, 'pre')
        assert q['session'] == 'pre'
        assert q['price'] == 212.52
        assert q['change_pct'] == -2.64
        assert q['time'] == '2026-09-14T08:41:45-04:00'
        assert q['source'] == 'yfinance'

    def test_post_market(self):
        info = {'postMarketPrice': 100.123, 'postMarketChangePercent': 1.234,
                'postMarketTime': 1789430400}
        q = UnifiedStockDataService._parse_extended_quote(info, 'post')
        assert q['price'] == 100.12 and q['change_pct'] == 1.23

    def test_overnight_has_no_yfinance_fallback(self):
        # 修掉旧的 CLOSED→post 误判：夜盘不得再拿停更的 postMarketPrice 冒充
        info = {'marketState': 'CLOSED', 'postMarketPrice': 50.0,
                'postMarketChangePercent': -0.5, 'postMarketTime': 1789430400}
        assert UnifiedStockDataService._parse_extended_quote(info, 'overnight') is None

    def test_regular_and_missing_return_none(self):
        assert UnifiedStockDataService._parse_extended_quote({'preMarketPrice': 1.0}, 'regular') is None
        assert UnifiedStockDataService._parse_extended_quote({}, 'pre') is None
        assert UnifiedStockDataService._parse_extended_quote({'preMarketPrice': None}, 'pre') is None


class TestGetUsExtendedQuotes:
    def _patch_session(self, monkeypatch, session):
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: session))

    def test_webull_is_primary(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'pre')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {
                                c: {'session': session, 'price': 10.0, 'change_pct': 2.0,
                                    'time': 't', 'source': 'webull'} for c in symbols})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: (_ for _ in ()).throw(AssertionError('不应回落 yfinance')))

        out = svc.get_us_extended_quotes(['NVDA', 'AMD'], force_refresh=True)
        assert set(out) == {'NVDA', 'AMD'}
        assert out['NVDA']['source'] == 'webull' and out['NVDA']['session'] == 'pre'

    def test_falls_back_to_yfinance_for_missing(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'post')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {'NVDA': {
                                'session': session, 'price': 10.0, 'change_pct': 1.0,
                                'time': 't', 'source': 'webull'}})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: {'postMarketPrice': 5.0,
                                             'postMarketChangePercent': -1.0,
                                             'postMarketTime': 1789430400})

        out = svc.get_us_extended_quotes(['NVDA', 'AMD'], force_refresh=True)
        assert out['NVDA']['source'] == 'webull'
        assert out['AMD']['source'] == 'yfinance' and out['AMD']['price'] == 5.0

    def test_overnight_does_not_fall_back(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'overnight')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes', lambda symbols, session: {})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: (_ for _ in ()).throw(AssertionError('夜盘无兜底')))
        assert svc.get_us_extended_quotes(['NVDA'], force_refresh=True) == {}

    def test_regular_session_returns_empty(self, monkeypatch):
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'regular')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: (_ for _ in ()).throw(AssertionError('盘中不取')))
        assert svc.get_us_extended_quotes(['NVDA'], force_refresh=True) == {}

    def test_cache_isolated_by_session(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        mc.memory_cache.invalidate(cache_type='extended')
        self._patch_session(monkeypatch, 'pre')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {'NVDA': {
                                'session': session, 'price': 10.0, 'change_pct': 1.0,
                                'time': 't', 'source': 'webull'}})
        svc.get_us_extended_quotes(['NVDA'], force_refresh=True)
        assert svc.get_us_extended_cached(['NVDA'])['NVDA']['price'] == 10.0

        # 切到盘中：盘前价不得串场
        self._patch_session(monkeypatch, 'regular')
        assert svc.get_us_extended_cached(['NVDA']) == {}

        # 切到盘后：缓存里那条是 pre，同样失效
        self._patch_session(monkeypatch, 'post')
        assert svc.get_us_extended_cached(['NVDA']) == {}


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
    def _patch(self, monkeypatch, et_time, is_trading_day=True, is_open=False):
        monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['US']))
        tz = pytz.timezone('America/New_York')
        monkeypatch.setattr(TradingCalendarService, 'get_market_now',
                            classmethod(lambda cls, market: tz.localize(et_time)))
        monkeypatch.setattr(TradingCalendarService, 'is_trading_day',
                            classmethod(lambda cls, market, dt=None: is_trading_day))
        monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                            classmethod(lambda cls, market, dt=None: is_open))

    def _us(self):
        return _make_client().get('/watch/market-status').get_json()['data']['US']

    def test_pre_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 8, 0))
        us = self._us()
        assert us['status'] == 'pre_market' and us['status_text'] == '盘前'

    def test_regular_says_pan_zhong(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 11, 0), is_open=True)
        us = self._us()
        assert us['status'] == 'trading' and us['status_text'] == '盘中'

    def test_post_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 17, 0))
        us = self._us()
        assert us['status'] == 'post_market' and us['status_text'] == '盘后'

    def test_late_night_is_overnight(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 21, 0))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_early_morning_is_overnight(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 3, 0))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_sunday_night_overnight_beats_holiday(self, monkeypatch):
        # 周日非交易日，但 20:00 后属周一夜盘，不得显示休市
        self._patch(monkeypatch, _et(2026, 7, 12, 21, 0), is_trading_day=False)
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: 'overnight'))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_saturday_is_holiday(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 11, 8, 0), is_trading_day=False)
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: None))
        assert self._us()['status'] == 'holiday'


def test_non_us_market_keeps_jiao_yi_zhong(monkeypatch):
    import datetime as dt_module
    monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['A']))
    tz = pytz.timezone('Asia/Shanghai')
    now = tz.localize(datetime(2026, 7, 6, 11, 0))
    monkeypatch.setattr(TradingCalendarService, 'get_market_now',
                        classmethod(lambda cls, market: now))
    monkeypatch.setattr(TradingCalendarService, 'is_trading_day',
                        classmethod(lambda cls, market, dt=None: True))
    monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                        classmethod(lambda cls, market, dt=None: True))
    a = _make_client().get('/watch/market-status').get_json()['data']['A']
    assert a['status'] == 'trading' and a['status_text'] == '交易中'


class TestPreloadExtended:
    def _setup(self, monkeypatch, session, tick=0):
        from app.services import unified_stock_data as usd
        svc = usd.unified_stock_data_service
        monkeypatch.setattr(WatchService, 'get_watch_codes',
                            staticmethod(lambda: ['NVDA', 'AMD', '0700.HK']))
        monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['US', 'HK']))
        monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                            classmethod(lambda cls, market, dt=None: False))
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
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
