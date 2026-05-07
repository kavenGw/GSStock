"""赛事调度层重试队列单测

设计文档：docs/plans/2026-05-07-esports-retry-queue-design.md
"""
from datetime import date, datetime, timedelta, timezone

import pytest

import app.services.esports_retry_queue as rq


_CST = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    rq._pending.clear()
    calls = []
    monkeypatch.setattr(rq, '_schedule_retry', lambda key: calls.append(key))
    yield calls
    rq._pending.clear()


def test_enqueue_idempotent(_reset_state):
    today = date(2026, 5, 7)
    rq.enqueue(today, 'lol', 'LCK')
    rq.enqueue(today, 'lol', 'LCK')

    assert len(rq._pending) == 1
    assert _reset_state == [rq._key(today, 'lol', 'LCK')]
    assert rq._pending[rq._key(today, 'lol', 'LCK')].attempts == 1


def test_retry_cross_day_discards(_reset_state, monkeypatch):
    refetch_calls = []
    push_calls = []
    monkeypatch.setattr(rq, '_refetch', lambda u: refetch_calls.append(u.name) or 'should_not_use')
    monkeypatch.setattr(rq, '_push_supplement', lambda u, m: push_calls.append('sup'))
    monkeypatch.setattr(rq, '_push_failed', lambda u: push_calls.append('fail'))

    yesterday = datetime.now(_CST).date() - timedelta(days=1)
    rq.enqueue(yesterday, 'lol', 'LCK')
    key = rq._key(yesterday, 'lol', 'LCK')

    rq._retry_one(key)

    assert key not in rq._pending
    assert refetch_calls == []
    assert push_calls == []


def test_retry_success_pushes_supplement_and_pops(_reset_state, monkeypatch):
    today = datetime.now(_CST).date()
    rq.enqueue(today, 'lol', 'LCK')
    key = rq._key(today, 'lol', 'LCK')

    fake_matches = {
        'today': [{'team1': 'T1', 'team2': 'Gen.G', 'start_time': '17:00'}],
        'yesterday': [],
    }
    push_calls = []
    monkeypatch.setattr(rq, '_refetch', lambda u: fake_matches)
    monkeypatch.setattr(rq, '_push_supplement', lambda u, m: push_calls.append((u.name, m)))
    monkeypatch.setattr(rq, '_push_failed', lambda u: push_calls.append(('failed', u.name)))

    rq._retry_one(key)

    assert key not in rq._pending
    assert push_calls == [('LCK', fake_matches)]


def test_retry_failure_under_max_reschedules(_reset_state, monkeypatch):
    today = datetime.now(_CST).date()
    rq.enqueue(today, 'lol', 'LCK')
    key = rq._key(today, 'lol', 'LCK')

    monkeypatch.setattr(rq, '_refetch', lambda u: None)
    monkeypatch.setattr(rq, '_push_failed', lambda u: pytest.fail('should not push failed yet'))

    rq._retry_one(key)

    assert key in rq._pending
    assert rq._pending[key].attempts == 2
    # _schedule_retry 调用 2 次：enqueue 一次，_retry_one 重新挂一次
    assert _reset_state == [key, key]


def test_retry_failure_at_max_pushes_failed(_reset_state, monkeypatch):
    today = datetime.now(_CST).date()
    rq.enqueue(today, 'lol', 'LCK')
    key = rq._key(today, 'lol', 'LCK')
    rq._pending[key].attempts = rq._MAX_ATTEMPTS  # 当前 attempts=3，本次拉取失败后 attempts→4 超 _MAX_ATTEMPTS 触发终告

    monkeypatch.setattr(rq, '_refetch', lambda u: None)
    failed_calls = []
    monkeypatch.setattr(rq, '_push_failed', lambda u: failed_calls.append(u.name))

    rq._retry_one(key)

    assert key not in rq._pending
    assert failed_calls == ['LCK']


class _SlackCapture:
    def __init__(self):
        self.calls = []

    def __call__(self, message, channel, blocks=None):
        self.calls.append((message, channel))
        return True


def _patch_slack(monkeypatch):
    cap = _SlackCapture()
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack', staticmethod(cap))
    return cap


def test_push_lol_supplement_with_matches(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='lol', name='LCK', attempts=2)
    matches = {
        'today': [
            {'team1': 'T1', 'team2': 'Gen.G', 'start_time': '17:00'},
            {'team1': 'KT', 'team2': 'DK', 'start_time': '20:00'},
        ],
        'yesterday': [],
    }

    rq._push_supplement(unit, matches)

    assert len(cap.calls) == 1
    text, channel = cap.calls[0]
    assert 'LoL 补充' in text and 'LCK' in text and '(2场)' in text
    assert 'T1 vs Gen.G' in text and '17:00' in text
    from app.config.notification_config import CHANNEL_LOL
    assert channel == CHANNEL_LOL


def test_push_lol_supplement_empty_data_for_always_show(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='lol', name='LCK', attempts=2)

    rq._push_supplement(unit, {'today': [], 'yesterday': []})

    assert len(cap.calls) == 1
    assert '今日无赛事' in cap.calls[0][0] and 'LCK' in cap.calls[0][0]


def test_push_lol_supplement_empty_data_for_non_always_show(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='lol', name='Worlds', attempts=2)

    rq._push_supplement(unit, {'today': [], 'yesterday': []})

    assert cap.calls == []


def test_push_nba_supplement_unfiltered_when_monitor_empty(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr('app.config.esports_config.NBA_TEAM_MONITOR', {})
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='nba', name='NBA', attempts=2)
    games = {
        'today': [{'home': '湖人', 'away': '勇士', 'start_time': '09:00'}],
        'yesterday': [],
    }

    rq._push_supplement(unit, games)

    assert len(cap.calls) == 1
    assert 'NBA 补充' in cap.calls[0][0] and '勇士 vs 湖人' in cap.calls[0][0]


def test_push_failed_lol(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='lol', name='LCK', attempts=4)

    rq._push_failed(unit)

    assert len(cap.calls) == 1
    assert 'LoL' in cap.calls[0][0] and 'LCK' in cap.calls[0][0] and '数据获取失败' in cap.calls[0][0]


def test_push_failed_nba(_reset_state, monkeypatch):
    cap = _patch_slack(monkeypatch)
    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='nba', name='NBA', attempts=4)

    rq._push_failed(unit)

    assert len(cap.calls) == 1
    assert '今日 NBA 赛程' in cap.calls[0][0] and '数据获取失败' in cap.calls[0][0]


def test_refetch_lol_dispatches_to_fetch_lol(_reset_state, monkeypatch):
    captured = {}
    def fake_fetch(league_id, today, yesterday):
        captured['args'] = (league_id, today, yesterday)
        return {'today': [], 'yesterday': []}
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService._fetch_lol_esports_schedule',
        staticmethod(fake_fetch),
    )

    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='lol', name='LPL', attempts=2)
    result = rq._refetch(unit)

    assert result == {'today': [], 'yesterday': []}
    from app.config.esports_config import LOL_LEAGUES
    assert captured['args'] == (LOL_LEAGUES['LPL'], date(2026, 5, 7), date(2026, 5, 6))


def test_refetch_nba_dispatches_to_get_nba_schedule(_reset_state, monkeypatch):
    captured = {}
    def fake_get(today=None):
        captured['today'] = today
        return {'today': [], 'yesterday': []}
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_nba_schedule',
        staticmethod(fake_get),
    )

    unit = rq._PendingUnit(date=date(2026, 5, 7), kind='nba', name='NBA', attempts=2)
    result = rq._refetch(unit)

    assert result == {'today': [], 'yesterday': []}
    assert captured['today'] == date(2026, 5, 7)
