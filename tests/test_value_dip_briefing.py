from app.strategies.daily_briefing import DailyBriefingStrategy


def test_pullback_message_uses_market():
    stocks = [{'code': '300223', 'name': '北京君正', 'market': 'A',
               'price': 30.0, 'high': 40.0, 'pullback_pct': -25.0}]
    msg = DailyBriefingStrategy._format_pullback_message(stocks)
    assert '北京君正' in msg and 'A' in msg and '-25.0%' in msg


def test_value_dip_push_removed():
    assert not hasattr(DailyBriefingStrategy, '_push_value_dip_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_value_dip_message')
