import inspect

from app.services.notification import NotificationService
from app.llm.prompts.daily_briefing import build_daily_briefing_prompt


def test_format_alert_signals_removed():
    """关键信号已下线：盘中 price_alert 策略已推同一份 signal_cache。"""
    assert not hasattr(NotificationService, 'format_alert_signals')


def test_build_briefing_blocks_signature():
    params = list(inspect.signature(NotificationService.build_briefing_blocks).parameters)
    assert params == ['briefing_text', 'core_insights', 'action_suggestions']


def test_build_briefing_blocks_renders_without_alerts():
    blocks = NotificationService.build_briefing_blocks(
        '📊 持仓 (2026-08-08) | ¥100,000 | +1.2%\n🔴甲 +3.0% | 🟢乙 -1.0%',
        core_insights='市场情绪回暖',
        action_suggestions='关注半导体',
    )
    dumped = str(blocks)
    assert '今日核心观点' in dumped
    assert '持仓' in dumped
    assert '关键信号' not in dumped


def test_prompt_drops_alert_signals():
    prompt = build_daily_briefing_prompt({
        'position_summary': '持仓文本',
        'alert_signals': '不该出现的预警信号文本',
    })
    assert '持仓文本' in prompt
    assert '不该出现的预警信号文本' not in prompt
    assert '预警信号' not in prompt


def test_price_alert_strategy_kept():
    """signal_cache 的盘中消费者仍在，_refresh_signal_cache 因此必须保留。"""
    from app.strategies.price_alert import PriceAlertStrategy
    from app.strategies.daily_briefing import DailyBriefingStrategy
    assert PriceAlertStrategy.name == 'price_alert'
    assert hasattr(DailyBriefingStrategy, '_refresh_signal_cache')
