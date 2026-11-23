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
    assert '资金费率 +0.0100%' in text
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
    assert '15分钟异动' in env['sent'][-1][0]
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
    assert '成交 103' not in env['sent'][0][0]
