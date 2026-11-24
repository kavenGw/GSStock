from datetime import datetime, timezone

import pytest

from app.strategies import binance_watch as module
from app.services.notification import NotificationService


@pytest.fixture
def env(monkeypatch):
    state = {'now': datetime(2026, 11, 22, 1, 0, tzinfo=timezone.utc).timestamp(),
             'ok': True, 'sent': [], 'rows': []}
    monkeypatch.setattr(module.time, 'time', lambda: state['now'])
    monkeypatch.setattr(module.binance_perpetual_service, 'refresh', lambda: None)
    monkeypatch.setattr(module.binance_perpetual_service, 'snapshot', lambda: {'data': state['rows']})

    def send(message, channel):
        state['sent'].append((message, channel))
        return state['ok']

    monkeypatch.setattr(NotificationService, 'send_slack', staticmethod(send))
    state['strategy'] = module.BinanceWatchStrategy()
    state['rows'] = [{'symbol': 'NVDAUSDT', 'name': '英伟达', 'kind': '股票/ETF永续',
                      'available': True, 'price': 103, 'price_unit': 'USDT',
                      'mark_price': 103.1, 'funding_rate_pct': 0.01,
                      'change_pct': 2, 'change_15m_pct': None}]
    return state


def test_weekend_summary_uses_beijing_time_and_success_dedup(env):
    strategy = env['strategy']
    env['ok'] = False
    strategy.scan()
    assert strategy._summary_slot is None
    env['ok'] = True
    env['now'] += 60
    strategy.scan()
    strategy.scan()
    assert len(env['sent']) == 2
    text, channel = env['sent'][-1]
    assert channel == 'news_watch'
    assert '2026-11-22 09:01 北京时间' in text
    assert '*英伟达 · NVDAUSDT*\n最新价 103 USDT ｜24小时 +2.00%' in text
    assert all(field not in text for field in ('资金费率', '标记', '股票/ETF永续', '15分钟'))
    env['now'] += 12 * 3600
    strategy.scan()
    assert len(env['sent']) == 3


@pytest.mark.parametrize('change', [3.1, -3.1])
def test_alert_cooldown_success_only_and_both_directions(env, change):
    env['now'] += 3600
    env['rows'][0]['change_15m_pct'] = change
    strategy = env['strategy']
    env['ok'] = False
    strategy.scan()
    assert not strategy._pushed
    env['ok'] = True
    strategy.scan()
    strategy.scan()
    assert len(env['sent']) == 2
    direction = '上涨' if change > 0 else '下跌'
    assert env['sent'][-1][0] == (
        f'*币安永续 · 15分钟{direction} {change:+.2f}%*\n'
        '*英伟达 · NVDAUSDT*\n最新价 103 USDT ｜24小时 +2.00%')
    env['now'] += 1799
    strategy.scan()
    assert len(env['sent']) == 2
    env['now'] += 1
    strategy.scan()
    assert len(env['sent']) == 3


def test_missing_stale_and_below_threshold_do_not_alert(env):
    env['now'] += 3600
    strategy = env['strategy']
    strategy.scan()
    env['rows'][0]['change_15m_pct'] = 2.99
    strategy.scan()
    env['rows'][0].update(available=False, change_15m_pct=30)
    strategy.scan()
    assert not env['sent']


def test_summary_marks_unavailable_quotes(env):
    env['rows'][0]['available'] = False
    env['strategy'].scan()
    assert '行情不可用' in env['sent'][0][0]
    assert '最新价' not in env['sent'][0][0]


def test_summary_separates_symbols_and_preserves_quanto_unit(env):
    env['rows'].append(dict(env['rows'][0], name='小米', symbol='HK1810USDT',
                            price=35.2, price_unit='HKD（quanto）', change_pct=-1.2))
    env['strategy'].scan()
    text = env['sent'][0][0]
    assert '24小时 +2.00%\n\n*小米 · HK1810USDT*\n最新价 35.2 HKD（quanto） ｜24小时 -1.20%' in text


def test_multiple_alerts_keep_direction_with_each_symbol(env):
    env['now'] += 3600
    env['rows'][0]['change_15m_pct'] = 3.74
    env['rows'].append(dict(env['rows'][0], name='智谱', symbol='ZHIPUSDT',
                            change_15m_pct=-4.2))
    env['strategy'].scan()
    text = env['sent'][0][0]
    assert '*币安永续 · 15分钟上涨 +3.74%*\n*英伟达 · NVDAUSDT*' in text
    assert '\n\n*币安永续 · 15分钟下跌 -4.20%*\n*智谱 · ZHIPUSDT*' in text
    assert set(env['strategy']._pushed) == {'NVDAUSDT', 'ZHIPUSDT'}
