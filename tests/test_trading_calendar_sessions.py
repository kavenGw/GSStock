"""交易时段判断：港股/A股/日股午休，美股连续时段"""
from datetime import datetime

from app.services.trading_calendar import TradingCalendarService


def _dt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)


# 2026-07-06 周一，沪/港/东京/纽约均为交易日
class TestHKLunchBreak:
    def test_hk_lunch_1211_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 12, 11)) is False

    def test_hk_1159_open(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 11, 59)) is True

    def test_hk_1301_open(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 13, 1)) is True

    def test_hk_0929_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 9, 29)) is False

    def test_hk_1601_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 16, 1)) is False


class TestExistingMarketsRegression:
    def test_a_share_lunch_closed(self):
        assert TradingCalendarService.is_market_open('A', _dt(2026, 7, 6, 12, 0)) is False

    def test_a_share_morning_open(self):
        assert TradingCalendarService.is_market_open('A', _dt(2026, 7, 6, 10, 0)) is True

    def test_jp_lunch_closed(self):
        assert TradingCalendarService.is_market_open('JP', _dt(2026, 7, 6, 12, 0)) is False

    def test_jp_afternoon_open(self):
        assert TradingCalendarService.is_market_open('JP', _dt(2026, 7, 6, 13, 0)) is True

    def test_us_midday_open(self):
        assert TradingCalendarService.is_market_open('US', _dt(2026, 7, 6, 12, 0)) is True


def test_market_sessions_constant_shape():
    sessions = TradingCalendarService.MARKET_SESSIONS
    assert set(sessions) == {'A', 'HK', 'JP'}
    for market, pairs in sessions.items():
        assert len(pairs) == 2
        for s_open, s_close in pairs:
            assert s_open < s_close
