from app.strategies.daily_briefing import DailyBriefingStrategy


def test_value_dip_push_removed():
    assert not hasattr(DailyBriefingStrategy, '_push_value_dip_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_value_dip_message')


def test_pullback_push_removed():
    """高点回退提醒已下线（信息与盯盘告警重复），value_dip 页面仍保留。"""
    assert not hasattr(DailyBriefingStrategy, '_push_pullback_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_pullback_message')


def test_value_dip_service_kept():
    """ValueDipService 仍服务 /value_dip 页面，不随推送一起下线。"""
    from app.services.value_dip import ValueDipService
    assert hasattr(ValueDipService, 'get_pullback_ranking')
