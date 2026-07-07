"""_calc_trading_minutes 复用 TradingCalendarService.MARKET_SESSIONS"""
from datetime import datetime, time

from app.strategies.watch_alert import WatchAlertStrategy


class FakeCalendar:
    MARKET_SESSIONS = {
        'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
        'HK': [(time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))],
        'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
    }

    def __init__(self, now):
        self._now = now

    def get_market_now(self, market):
        return self._now

    def get_market_hours(self, market, dt):
        return (time(9, 30), time(16, 0))


def _calc(now, code, market):
    cal = FakeCalendar(now)
    return WatchAlertStrategy._calc_trading_minutes([code], {code: market}, cal)[code]


def test_hk_lunch_elapsed_frozen_at_150():
    assert _calc(datetime(2026, 7, 6, 12, 11), '2476.HK', 'HK') == {'elapsed': 150, 'total': 330}


def test_hk_afternoon_1330_elapsed_180():
    assert _calc(datetime(2026, 7, 6, 13, 30), '2476.HK', 'HK') == {'elapsed': 180, 'total': 330}


def test_a_share_lunch_elapsed_frozen_at_120():
    assert _calc(datetime(2026, 7, 6, 12, 30), '600519', 'A') == {'elapsed': 120, 'total': 240}


def test_no_local_sessions_dict():
    import inspect
    src = inspect.getsource(WatchAlertStrategy._calc_trading_minutes)
    assert 'SESSIONS = {' not in src
