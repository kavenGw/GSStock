from app.services.value_dip import ValueDipService
from app.strategies.daily_briefing import DailyBriefingStrategy


def _mk_ohlc(closes):
    """把收盘价序列造成 OHLC dict 列表（high=close+2, low=close-2）"""
    return [
        {'date': f'2026-06-{i + 1:02d}', 'open': c,
         'high': c + 2, 'low': c - 2, 'close': c, 'volume': 1000}
        for i, c in enumerate(closes)
    ]


# 25 日：先涨到 120 再回落到 100，制造下方支撑与上方压力
_CLOSES_25 = [95, 96, 98, 100, 103, 106, 110, 113, 116, 118, 120, 119, 117,
              115, 113, 111, 109, 107, 105, 103, 102, 101, 100, 100, 100]


def test_calc_changes_attaches_support_resistance():
    info = ValueDipService._calc_stock_changes('300223', '北京君正', _mk_ohlc(_CLOSES_25))
    assert info['support'] is not None
    assert info['resistance'] is not None
    assert info['support'] < info['price'] < info['resistance']


def test_calc_changes_sr_none_when_insufficient_data():
    info = ValueDipService._calc_stock_changes('300223', '北京君正', _mk_ohlc(_CLOSES_25[:10]))
    assert info['support'] is None
    assert info['resistance'] is None


def test_format_renders_support_and_resistance():
    stocks = [{'code': '300223', 'name': '北京君正', 'market': 'A',
               'price': 100.0, 'high': 120.0, 'pullback_pct': -16.67,
               'support': 98.2, 'resistance': 105.0}]
    msg = DailyBriefingStrategy._format_pullback_message(stocks)
    assert '下方支撑98.20(-1.80%)' in msg
    assert '上方压力105.00(+5.00%)' in msg


def test_format_omits_missing_sr():
    stocks = [{'code': '300223', 'name': '北京君正', 'market': 'A',
               'price': 100.0, 'high': 120.0, 'pullback_pct': -16.67,
               'support': None, 'resistance': None}]
    msg = DailyBriefingStrategy._format_pullback_message(stocks)
    assert '下方支撑' not in msg and '上方压力' not in msg


def test_format_renders_single_side():
    stocks = [{'code': '300223', 'name': '北京君正', 'market': 'A',
               'price': 100.0, 'high': 120.0, 'pullback_pct': -16.67,
               'support': 98.2, 'resistance': None}]
    msg = DailyBriefingStrategy._format_pullback_message(stocks)
    assert '下方支撑98.20(-1.80%)' in msg and '上方压力' not in msg
