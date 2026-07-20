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
