"""HK 午休窗口回归测试：/watch/market-status 不应把 HK 午休误判为未开盘"""
from datetime import datetime, time as dtime

import pytz
from flask import Flask

from app.routes import watch_bp
from app.services.trading_calendar import TradingCalendarService
from app.services.watch_service import WatchService


def _make_client():
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


def _patch_market_now(monkeypatch, market_times: dict):
    original = TradingCalendarService.get_market_now.__func__

    def fake_get_market_now(cls, market):
        if market in market_times:
            tz = pytz.timezone(cls.MARKET_TIMEZONES[market])
            return tz.localize(market_times[market])
        return original(cls, market)

    monkeypatch.setattr(TradingCalendarService, 'get_market_now', classmethod(fake_get_market_now))
    monkeypatch.setattr(TradingCalendarService, 'is_trading_day', classmethod(lambda cls, market, dt=None: True))


def test_hk_lunch_reports_lunch_status(monkeypatch):
    monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['A', 'HK']))
    _patch_market_now(monkeypatch, {
        'A': datetime(2026, 7, 6, 12, 15),
        'HK': datetime(2026, 7, 6, 12, 30),
    })

    client = _make_client()
    resp = client.get('/watch/market-status')
    data = resp.get_json()['data']

    assert data['A']['status'] == 'lunch'
    assert data['HK']['status'] == 'lunch'
    assert data['HK']['status_text'] == '午休'
    assert 'seconds_to_open' in data['HK']
