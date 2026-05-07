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
