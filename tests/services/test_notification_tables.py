from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from app.scheduler.event_bus import event_bus
from app.services.notification import NotificationService, CHANNEL_DAILY
from app.services.notification_tables import format_volume, format_volume_alerts
from app.services.watch_range_stats import format_range_stats
from app.strategies.base import Signal, Strategy
from app.strategies.volume_alert import VolumeAlertStrategy


def signal(index, change):
    return Signal('volume_alert', 'HIGH', 'unused', 'unused', {
        'stock_code': f'{index:04d}.HK', 'stock_name': f'Stock {index}',
        'volume_change_pct': change, 'today_volume': 207860564,
        'previous_volume': 88051477, 'volume_unit': '股', 'price_change_pct': -3.12,
    })


@pytest.mark.parametrize('value, unit, expected', [
    (None, '股', '—'), (1234, '手', '1,234手'),
    (648816, '手', '64.88万手'), (207860564, '股', '2.08亿股'),
])
def test_volume_units(value, unit, expected):
    assert format_volume(value, unit) == expected


def test_volume_pages_sort_globally_and_keep_shrinkage():
    alerts = [dict(signal(i, i / 10).data, priority='HIGH') for i in range(41)]
    alerts[0]['volume_change_pct'] = -0.9
    messages = format_volume_alerts(alerts, '成交量异动')
    tables = [m['blocks'][1] for m in messages]
    assert [len(t['rows']) for t in tables] == [21, 21, 2]
    rows = [r for t in tables for r in t['rows'][1:]]
    assert len({r[1]['text'] for r in rows}) == 41
    assert rows[0][2]['text'] == '+400%'
    assert any(r[2]['text'] == '-90%' for r in rows)
    assert all(r[4]['text'] == '2.08亿股' for r in rows)
    assert all(t['rows'][0] == tables[0]['rows'][0] for t in tables)
    assert format_volume_alerts([], 'empty') == []


def test_range_pages_keep_every_stock_and_sort_before_paging():
    entries = [{
        'code': str(i), 'name': f'Stock {i}', 'market': 'A',
        'expected_date': '2026-10-30',
        'stats': {'7d': {'position': i, 'high': 10, 'low': 1, 'current': 5,
                          'vwap': None, 'days': 3, 'end_date': '2026-10-29'}},
    } for i in reversed(range(41))]
    messages = format_range_stats(entries)
    assert len(messages) == 3
    rows = [r for m in messages for r in m['blocks'][1]['rows'][1:]]
    assert [r[-1]['text'] for r in rows] == [f'{i}%' for i in range(41)]
    assert all('仅 3 个交易日；截至 2026-10-29' in r[0]['text'] for r in rows)
    assert all(r[-2]['text'] == '—' for r in rows)


@pytest.mark.parametrize('retry', [False, True])
def test_scan_and_retry_send_one_table_per_batch(monkeypatch, retry):
    from app.scheduler.engine import SchedulerEngine, scheduler_engine
    from app.strategies.registry import registry

    strategy = VolumeAlertStrategy()
    signals = [signal(1, 0.7), signal(2, -0.8)]
    scan = Mock(return_value=signals)
    monkeypatch.setattr(strategy, 'scan', scan)
    monkeypatch.setattr(event_bus, '_handlers', [NotificationService.dispatch_signal])
    monkeypatch.setattr(NotificationService, '_signal_state', {})
    send = Mock(return_value=True)
    monkeypatch.setattr(NotificationService, 'send_slack', send)
    app = Flask(__name__)
    if retry:
        scheduler = SimpleNamespace(add_job=Mock())
        monkeypatch.setattr(scheduler_engine, 'scheduler', scheduler)
        monkeypatch.setattr(scheduler_engine, 'app', app)
        strategy._schedule_retry(['0001.HK', '0002.HK'])
        scheduler.add_job.call_args.args[0]()
        scan.assert_called_once_with(retry_codes=['0001.HK', '0002.HK'])
    else:
        engine = SchedulerEngine()
        monkeypatch.setattr(engine, 'app', app)
        monkeypatch.setattr(registry, 'get', lambda name: strategy)
        engine._run_strategy('volume_alert')
        scan.assert_called_once_with()
    send.assert_called_once()
    args, kwargs = send.call_args
    assert args[1] == CHANNEL_DAILY
    assert ('补数据重试' in args[0]) is retry
    rows = kwargs['blocks'][1]['rows']
    assert len(rows) == 3
    assert rows[1][2]['text'] == '-80%'


def test_empty_and_low_volume_batches_do_not_send(monkeypatch):
    publish = Mock()
    monkeypatch.setattr(event_bus, 'publish', publish)
    strategy = VolumeAlertStrategy()
    strategy.publish_signals([])
    low = signal(1, 0.1)
    low.priority = 'LOW'
    strategy.publish_signals([low])
    publish.assert_not_called()


def test_other_strategies_still_publish_individual_signals(monkeypatch):
    publish = Mock()
    monkeypatch.setattr(event_bus, 'publish', publish)
    signals = [Signal('other', 'MEDIUM', 'title', 'detail') for _ in range(2)]
    Strategy.publish_signals(None, signals)
    assert [call.args[0] for call in publish.call_args_list] == signals
