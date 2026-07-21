from app.strategies.base import Signal
from app.services.watch_signal_pipeline import (
    WatchSignalPipeline, ConsolidatedAlert, SIGNAL_WEIGHTS,
)


def _sig(code, alert_type, direction='', title='X'):
    return Signal(strategy='watch_alert', priority='HIGH',
                  title=f'测试({code}) {title}', detail='',
                  data={'stock_code': code, 'alert_type': alert_type, 'direction': direction})


def test_group_one_alert_per_stock():
    raw = [
        _sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05'),
        _sig('603626', 'ma_crossover', 'up', '上穿 MA5'),
        _sig('600519', 'td_sequential', 'buy', 'TD九转买入'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'603626': '科森科技', '600519': '茅台'})
    assert len(alerts) == 2
    by_code = {a.code: a for a in alerts}
    assert by_code['603626'].primary_line == '突破阻力 30.0 | 当前 30.05'
    assert '上穿 MA5' in by_code['603626'].secondary_lines
    assert by_code['603626'].name == '科森科技'


def test_priority_high_on_confluence():
    # 破位(4) + 同向下穿MA(3×0.5=1.5) + 放量(+1) = 6.5 → HIGH
    raw = [
        _sig('603626', 'support_break', 'support_break', '跌破支撑'),
        _sig('603626', 'ma_crossover', 'down', '下穿 MA5'),
        _sig('603626', 'volume_anomaly', '', '放量'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'HIGH'


def test_priority_low_on_weak_single():
    # 单条 intraday_extreme(2) < 3 → LOW
    raw = [_sig('603626', 'intraday_extreme', 'high', '刷新前高')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'LOW'


def test_opposite_direction_not_stacked():
    # 破位(4) + 反向上穿MA(不叠加) → agg=4 → MID（非 HIGH）
    raw = [
        _sig('603626', 'support_break', 'support_break', '跌破支撑'),
        _sig('603626', 'ma_crossover', 'up', '上穿 MA5'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'MID'


def test_ignores_signal_without_stock_code():
    raw = [Signal(strategy='watch_alert', priority='HIGH', title='x', detail='', data={})]
    assert WatchSignalPipeline.process(raw, {}, {}, {}) == []


def test_context_change_volume_range():
    prices = {'603626': {'current_price': 30.05, 'change_percent': 2.30, 'volume': 1200}}
    params = {'603626': {'volume_baseline': 1000, 'resistance_levels': [32.0, 35.0], 'support_levels': [28.0]}}
    tm = {'603626': {'elapsed': 120, 'total': 240}}  # 半天 → 归一化 ×2 → 量比 2.4x
    ctx = WatchSignalPipeline._build_context('603626', prices, params, tm)
    assert '涨幅 +2.30%' in ctx
    assert '量比 2.4x' in ctx
    assert '距上方阻力 32.0(+6.5%)' in ctx


def test_context_uses_support_when_no_resistance_above():
    prices = {'600519': {'current_price': 100.0, 'change_percent': -1.0, 'volume': 0}}
    params = {'600519': {'resistance_levels': [90.0], 'support_levels': [95.0, 80.0]}}
    ctx = WatchSignalPipeline._build_context('600519', prices, params, {})
    assert '距下方支撑 95.0(-5.0%)' in ctx


def test_context_skips_volume_ratio_on_unit_glitch():
    prices = {'603626': {'current_price': 30.0, 'change_percent': 0, 'volume': 999999}}
    params = {'603626': {'volume_baseline': 100}}
    tm = {'603626': {'elapsed': 240, 'total': 240}}  # 比率>50 → 跳过量比
    ctx = WatchSignalPipeline._build_context('603626', prices, params, tm)
    assert '量比' not in ctx


def test_push_skips_low_and_formats_high():
    from unittest.mock import patch
    from app.services.notification import NotificationService

    high = ConsolidatedAlert(
        code='603626', name='科森科技', priority='HIGH', direction='resistance_break',
        primary_line='突破阻力 30.00 | 当前 30.05',
        secondary_lines=['下穿 MA5 20.50', '放量 1.8x'],
        context_line='涨幅 +2.30% | 量比 1.8x | 距上方阻力 32.00(+6.5%)',
    )
    low = ConsolidatedAlert(code='600519', name='茅台', priority='LOW', direction='high',
                            primary_line='刷新前高')
    sent = []
    with patch.object(NotificationService, 'send_slack', side_effect=lambda t, c: sent.append((t, c)) or True):
        ok = NotificationService.push_watch_alerts([high, low])
    assert ok is True
    assert len(sent) == 1  # LOW 被跳过
    text, _ = sent[0]
    assert '🔴 *科森科技(603626)*' in text
    assert '[HIGH]' in text
    assert '突破阻力 30.00 | 当前 30.05' in text
    assert '  · 下穿 MA5 20.50' in text
    assert '涨幅 +2.30%' in text


def test_process_populates_change_percent():
    raw = [_sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05')]
    prices = {'603626': {'current_price': 30.05, 'change_percent': 2.35, 'volume': 1200}}
    alerts = WatchSignalPipeline.process(raw, prices, {}, {'603626': '科森科技'})
    assert len(alerts) == 1
    assert alerts[0].change_percent == 2.35


def test_process_change_percent_defaults_none_when_missing():
    raw = [_sig('600519', 'td_sequential', 'buy', 'TD九转买入')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'600519': '茅台'})
    assert alerts[0].change_percent is None
