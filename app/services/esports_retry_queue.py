"""赛事推送调度层重试队列

5min × 3 轮挂起重试。状态进程内字典 + APScheduler 一次性 job。
设计文档：docs/plans/2026-05-07-esports-retry-queue-design.md
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))
_RETRY_INTERVAL_MINUTES = 5
_MAX_ATTEMPTS = 3


@dataclass
class _PendingUnit:
    date: date
    kind: str  # 'lol' | 'nba'
    name: str
    attempts: int = 1


_pending: dict[str, _PendingUnit] = {}


def _key(date_, kind, name):
    return f"{date_.isoformat()}:{kind}:{name}"


def _schedule_retry(key):
    """挂一次性 job，在 now + 5min 触发 _retry_one(key)。被测试 monkeypatch 替换。"""
    from app.scheduler.engine import scheduler_engine
    from apscheduler.triggers.date import DateTrigger

    run_at = datetime.now(_CST) + timedelta(minutes=_RETRY_INTERVAL_MINUTES)

    def _job():
        with scheduler_engine.app.app_context():
            _retry_one(key)

    scheduler_engine.scheduler.add_job(
        _job,
        trigger=DateTrigger(run_date=run_at),
        id=f"esports_retry:{key}",
        replace_existing=True,
    )


def enqueue(date_, kind, name):
    """首轮失败入口。同 key 已 pending 时幂等。"""
    key = _key(date_, kind, name)
    if key in _pending:
        return
    _pending[key] = _PendingUnit(date=date_, kind=kind, name=name, attempts=1)
    _schedule_retry(key)
    logger.info(f'[赛事重试] enqueue {key}')


def _retry_one(key):
    unit = _pending.get(key)
    if unit is None:
        return

    today = datetime.now(_CST).date()
    if unit.date != today:
        _pending.pop(key, None)
        logger.info(f'[赛事重试] 跨日丢弃 {key}')
        return

    matches = _refetch(unit)
    if matches is not None:
        _push_supplement(unit, matches)
        _pending.pop(key, None)
        logger.info(f'[赛事重试] 补推成功 {key}')
        return

    unit.attempts += 1
    if unit.attempts <= _MAX_ATTEMPTS:
        _schedule_retry(key)
        logger.info(f'[赛事重试] 第 {unit.attempts - 1} 轮失败 {key}，已挂下轮')
        return

    raise NotImplementedError  # Task 5 填充


def _refetch(unit):
    raise NotImplementedError  # Task 6 填充


def _push_supplement(unit, matches):
    raise NotImplementedError  # Task 6 填充


def _push_failed(unit):
    raise NotImplementedError  # Task 6 填充
