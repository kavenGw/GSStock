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
