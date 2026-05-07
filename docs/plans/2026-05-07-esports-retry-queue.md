# 赛事获取调度层重试队列 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 07:00 LoL/NBA 赛程推送遇到部分联赛失败时，不立刻推 "数据获取失败"；改为将失败联赛挂起，5min × 3 轮调度层重试，期间任意一轮成功立即补推该联赛，3 轮全失败才推终告。

**Architecture:** 进程内字典 `_pending` 维护待重试 unit 状态；APScheduler 一次性 `DateTrigger` job 在 `now + 5min` 触发 `_retry_one`；每 unit 最多 3 次 attempt。LoL 每联赛各为独立 unit，NBA 整体为单 unit。

**Tech Stack:** APScheduler（项目已用，`scheduler_engine.scheduler.add_job(... DateTrigger)`）、httpx（已用）、pytest + monkeypatch。

**Spec：** `docs/plans/2026-05-07-esports-retry-queue-design.md`

---

## 文件结构

| 文件 | 创建/修改 | 责任 |
|------|----------|------|
| `app/services/esports_retry_queue.py` | 创建 | `_PendingUnit` / `_pending` 状态 / `enqueue` / `_retry_one` / `clear_for_date` / 内部 push 辅助 |
| `app/strategies/esports_daily_schedule/__init__.py` | 修改 | 失败联赛改为 `enqueue()` 而非直接推 "数据获取失败" |
| `tests/test_esports_retry_queue.py` | 创建 | 队列状态机 + push 路由单测 |
| `tests/test_esports_daily_schedule_routing.py` | 创建 | 策略层路由单测（首轮成功推 / 失败 enqueue） |
| `CLAUDE.md` | 修改 | "赛事推送配置" 节追加重试队列说明 |

---

## Task 1: 模块骨架 + `enqueue` 幂等

**Files:**
- Create: `app/services/esports_retry_queue.py`
- Create: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 写第一个失败测试**

`tests/test_esports_retry_queue.py`:

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：`ModuleNotFoundError: No module named 'app.services.esports_retry_queue'`

- [ ] **Step 3: 写最小模块骨架通过测试**

`app/services/esports_retry_queue.py`:

```python
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
    raise NotImplementedError  # Task 2-5 填充
```

- [ ] **Step 4: 跑测试确认通过**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：`test_enqueue_idempotent PASSED`

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): 模块骨架 + enqueue 幂等"
```

---

## Task 2: `_retry_one` 跨日丢弃

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Modify: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 追加失败测试**

在 `tests/test_esports_retry_queue.py` 末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py::test_retry_cross_day_discards -v
```

预期：`NotImplementedError` 或 `AttributeError: ... _refetch`（取决于实现进度）

- [ ] **Step 3: 实现 `_retry_one` 跨日分支 + `_refetch` 占位**

替换 `_retry_one`，并新增 `_refetch` / `_push_supplement` / `_push_failed` 占位：

```python
def _retry_one(key):
    unit = _pending.get(key)
    if unit is None:
        return

    today = datetime.now(_CST).date()
    if unit.date != today:
        _pending.pop(key, None)
        logger.info(f'[赛事重试] 跨日丢弃 {key}')
        return

    raise NotImplementedError  # Task 3-5 填充


def _refetch(unit):
    raise NotImplementedError  # Task 6 填充


def _push_supplement(unit, matches):
    raise NotImplementedError  # Task 6 填充


def _push_failed(unit):
    raise NotImplementedError  # Task 6 填充
```

- [ ] **Step 4: 跑测试确认通过**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：2 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): _retry_one 跨日丢弃分支"
```

---

## Task 3: `_retry_one` 成功补推路径

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Modify: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 追加测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py::test_retry_success_pushes_supplement_and_pops -v
```

预期：`NotImplementedError`

- [ ] **Step 3: 在 `_retry_one` 加成功分支**

把 `_retry_one` 替换为：

```python
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

    raise NotImplementedError  # Task 4-5 填充
```

- [ ] **Step 4: 跑测试确认通过**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): _retry_one 成功补推分支"
```

---

## Task 4: `_retry_one` 失败-未到上限 重新挂任务

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Modify: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 追加测试**

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

预期：`NotImplementedError`

- [ ] **Step 3: 在 `_retry_one` 加失败-未到上限分支**

更新失败分支：

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

预期：4 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): _retry_one 失败-未到上限重挂"
```

---

## Task 5: `_retry_one` 失败-到达上限 推终告

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Modify: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 追加测试**

```python
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
```

注：spec 语义"3 轮全失败"= 首轮失败 (attempts=1) + 第 2 轮失败 (attempts=2) + 第 3 轮失败 (attempts=3)。第 3 轮失败后 attempts 自增到 4，超 `_MAX_ATTEMPTS=3` 触发终告。设置 `attempts=3` 模拟"第 3 轮即将开始时的状态"，本次拉取失败即终告。

- [ ] **Step 2: 跑测试确认失败**

预期：`NotImplementedError`

- [ ] **Step 3: 在 `_retry_one` 加终告分支**

把 `_retry_one` 末尾的 `raise NotImplementedError` 换成：

```python
    _push_failed(unit)
    _pending.pop(key, None)
    logger.warning(f'[赛事重试] 终告失败 {key}')
```

完整 `_retry_one`：

```python
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

    _push_failed(unit)
    _pending.pop(key, None)
    logger.warning(f'[赛事重试] 终告失败 {key}')
```

- [ ] **Step 4: 跑测试确认通过**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：5 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): _retry_one 终告失败分支"
```

---

## Task 6: `_refetch` / `_push_supplement` / `_push_failed` 实现 + clear_for_date

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Modify: `tests/test_esports_retry_queue.py`

- [ ] **Step 1: 写测试**

追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：新加的 8 个用例 `NotImplementedError` 失败

- [ ] **Step 3: 实现 helper**

替换 `app/services/esports_retry_queue.py` 末尾三个占位为：

```python
def _refetch(unit):
    from app.services.esports_service import EsportsService
    from app.config.esports_config import LOL_LEAGUES
    yesterday = unit.date - timedelta(days=1)
    if unit.kind == 'lol':
        league_id = LOL_LEAGUES.get(unit.name)
        if league_id is None:
            return None
        return EsportsService._fetch_lol_esports_schedule(league_id, unit.date, yesterday)
    if unit.kind == 'nba':
        return EsportsService.get_nba_schedule(today=unit.date)
    return None


def _push_supplement(unit, matches):
    if unit.kind == 'lol':
        _push_lol_supplement(unit.name, matches)
    elif unit.kind == 'nba':
        _push_nba_supplement(matches)


def _push_lol_supplement(league, matches):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_LOL
    from app.config.esports_config import LOL_ALWAYS_SHOW

    today_matches = matches.get('today') or []
    if not today_matches:
        if league in LOL_ALWAYS_SHOW:
            NotificationService.send_slack(
                f'🎮 *LoL 补充* — *{league}*\n今日无赛事',
                CHANNEL_LOL,
            )
        return

    lines = [f'🎮 *LoL 补充* — *{league}* ({len(today_matches)}场)']
    for m in sorted(today_matches, key=lambda x: x.get('start_time') or '99:99'):
        t = m.get('start_time') or '--:--'
        lines.append(f'  · {t}  {m["team1"]} vs {m["team2"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_LOL)


def _push_nba_supplement(nba):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_NBA
    from app.config.esports_config import NBA_TEAM_MONITOR, NBA_TEAM_NAMES

    games = nba.get('today') or []
    monitored_cn = {NBA_TEAM_NAMES.get(k, k) for k, v in NBA_TEAM_MONITOR.items() if v}
    if monitored_cn:
        games = [g for g in games if g['home'] in monitored_cn or g['away'] in monitored_cn]

    if not games:
        NotificationService.send_slack('🏀 *NBA 补充*\n无关注球队比赛', CHANNEL_NBA)
        return

    lines = [f'🏀 *NBA 补充* ({len(games)}场)']
    for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
        t = g.get('start_time') or '--:--'
        lines.append(f'  · {t}  {g["away"]} vs {g["home"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_NBA)


def _push_failed(unit):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_LOL, CHANNEL_NBA

    if unit.kind == 'lol':
        NotificationService.send_slack(
            f'🎮 *LoL — {unit.name}* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_LOL,
        )
    elif unit.kind == 'nba':
        NotificationService.send_slack(
            f'🏀 *今日 NBA 赛程* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_NBA,
        )


def clear_for_date(date_):
    """测试 / 运维清理用，移除指定日期的所有挂起 unit 与对应 APScheduler job。"""
    from app.scheduler.engine import scheduler_engine

    keys = [k for k, u in _pending.items() if u.date == date_]
    for k in keys:
        _pending.pop(k, None)
        try:
            scheduler_engine.scheduler.remove_job(f"esports_retry:{k}")
        except Exception:
            pass
```

- [ ] **Step 4: 跑测试确认通过**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py -v
```

预期：13 passed（5 + 8 新加）

- [ ] **Step 5: Commit**

```bash
git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py
git commit -m "feat(esports-retry): _refetch / 补推 / 终告 helper 实现"
```

---

## Task 7: 改造策略文件，失败联赛改为 enqueue

**Files:**
- Modify: `app/strategies/esports_daily_schedule/__init__.py`
- Create: `tests/test_esports_daily_schedule_routing.py`

- [ ] **Step 1: 写策略层路由测试**

`tests/test_esports_daily_schedule_routing.py`:

```python
"""每日赛事推送策略 — 路由层单测

验证：
1. 首轮全成功：仅推 Slack，不 enqueue
2. 部分联赛失败：成功联赛进入首推消息，失败联赛 enqueue
3. 全部 LoL 联赛失败（get_lol_schedule 返回 None）：不发首推，对所有 LOL_ALWAYS_SHOW 联赛 enqueue
4. NBA 失败：不推首条 NBA 消息，enqueue NBA
"""
from datetime import date, datetime, timedelta, timezone

import pytest

import app.services.esports_retry_queue as rq
from app.strategies.esports_daily_schedule import EsportsDailyScheduleStrategy


_CST = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    rq._pending.clear()
    monkeypatch.setattr(rq, '_schedule_retry', lambda key: None)
    yield
    rq._pending.clear()


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


def test_lol_partial_success_pushes_first_and_enqueues_failures(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake_lol = {
        'LPL': {'today': [{'team1': 'WBG', 'team2': 'WE', 'start_time': '17:00'}], 'yesterday': []},
        'LCK': None,
        '先锋赛': None,
    }
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: fake_lol),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    # 首推只含 LPL
    assert len(cap.calls) == 1
    text = cap.calls[0][0]
    assert 'LPL' in text and 'WBG vs WE' in text
    assert 'LCK' not in text and '先锋赛' not in text
    assert '数据获取失败' not in text

    # LCK / 先锋赛 进入挂起队列
    today = datetime.now(_CST).date()
    assert rq._key(today, 'lol', 'LCK') in rq._pending
    assert rq._key(today, 'lol', '先锋赛') in rq._pending


def test_lol_all_failed_no_first_push_enqueues_always_show(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: None),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    assert cap.calls == []
    today = datetime.now(_CST).date()
    from app.config.esports_config import LOL_ALWAYS_SHOW
    for league in LOL_ALWAYS_SHOW:
        assert rq._key(today, 'lol', league) in rq._pending


def test_lol_all_success_pushes_first_no_enqueue(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake_lol = {
        'LPL': {'today': [{'team1': 'A', 'team2': 'B', 'start_time': '17:00'}], 'yesterday': []},
        'LCK': {'today': [{'team1': 'T1', 'team2': 'GEN', 'start_time': '20:00'}], 'yesterday': []},
        '先锋赛': {'today': [], 'yesterday': []},
    }
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: fake_lol),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    assert len(cap.calls) == 1
    text = cap.calls[0][0]
    assert 'LPL' in text and 'LCK' in text and '先锋赛' in text and '今日无赛事' in text
    assert rq._pending == {}


def test_nba_failure_enqueues(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_nba_schedule',
        staticmethod(lambda today=None: None),
    )

    EsportsDailyScheduleStrategy._push_nba_today()

    assert cap.calls == []
    today = datetime.now(_CST).date()
    assert rq._key(today, 'nba', 'NBA') in rq._pending
```

- [ ] **Step 2: 跑测试确认失败**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_daily_schedule_routing.py -v
```

预期：4 个用例都 FAIL（旧策略仍然推 "数据获取失败"，未 enqueue）

- [ ] **Step 3: 改造策略**

替换 `app/strategies/esports_daily_schedule/__init__.py` 整文件：

```python
"""每日赛事安排推送 — 每天 07:00 推送今日 NBA 和 LoL 赛程

失败联赛不直接推 "数据获取失败"，而是挂起 5min × 3 轮重试。
详见 docs/plans/2026-05-07-esports-retry-queue-design.md
"""
import logging
from datetime import datetime, timedelta, timezone

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))


class EsportsDailyScheduleStrategy(Strategy):
    name = "esports_daily_schedule"
    description = "每日赛事安排（07:00 今日 NBA/LoL 赛程）"
    schedule = "0 7 * * *"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.config.esports_config import ESPORTS_ENABLED
        if not ESPORTS_ENABLED:
            return []

        self._push_nba_today()
        self._push_lol_today()
        return []

    @staticmethod
    def _push_nba_today():
        from app.services.esports_service import EsportsService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_NBA
        from app.config.esports_config import NBA_TEAM_MONITOR, NBA_TEAM_NAMES
        from app.services.esports_retry_queue import enqueue

        try:
            nba = EsportsService.get_nba_schedule()
            if nba is None:
                today = datetime.now(_CST).date()
                enqueue(today, 'nba', 'NBA')
                return

            games = nba.get('today') or []
            monitored_cn = {NBA_TEAM_NAMES.get(k, k) for k, v in NBA_TEAM_MONITOR.items() if v}
            if monitored_cn:
                games = [g for g in games if g['home'] in monitored_cn or g['away'] in monitored_cn]

            if not games:
                NotificationService.send_slack('🏀 *今日 NBA 赛程*\n无关注球队比赛', CHANNEL_NBA)
                return

            lines = [f'🏀 *今日 NBA 赛程* ({len(games)}场)', '']
            for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
                t = g.get('start_time') or '--:--'
                lines.append(f'  · {t}  {g["away"]} vs {g["home"]}')
            NotificationService.send_slack('\n'.join(lines), CHANNEL_NBA)
            logger.info(f'[赛事安排] NBA 推送 {len(games)} 场')
        except Exception as e:
            logger.error(f'[赛事安排] NBA 推送失败: {type(e).__name__}: {e}', exc_info=True)

    @staticmethod
    def _push_lol_today():
        from app.services.esports_service import EsportsService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_LOL
        from app.config.esports_config import LOL_ALWAYS_SHOW
        from app.services.esports_retry_queue import enqueue

        try:
            lol = EsportsService.get_lol_schedule()
            today = datetime.now(_CST).date()
            if lol is None:
                for league in LOL_ALWAYS_SHOW:
                    enqueue(today, 'lol', league)
                return

            sections = []
            total = 0
            for league in ['LPL', 'LCK', '先锋赛', 'Worlds', 'MSI']:
                if league not in lol:
                    continue
                data = lol[league]
                if data is None:
                    enqueue(today, 'lol', league)
                    continue
                matches = data.get('today') or []
                if not matches and league not in LOL_ALWAYS_SHOW:
                    continue
                if not matches:
                    sections.append(f'*{league}*\n今日无赛事')
                    continue
                total += len(matches)
                lines = [f'*{league}* ({len(matches)}场)']
                for m in sorted(matches, key=lambda x: x.get('start_time') or '99:99'):
                    t = m.get('start_time') or '--:--'
                    lines.append(f'  · {t}  {m["team1"]} vs {m["team2"]}')
                sections.append('\n'.join(lines))

            if not sections:
                return
            header = f'🎮 *今日 LoL 赛程* ({total}场)' if total else '🎮 *今日 LoL 赛程*'
            NotificationService.send_slack(header + '\n\n' + '\n\n'.join(sections), CHANNEL_LOL)
            logger.info(f'[赛事安排] LoL 推送 {total} 场')
        except Exception as e:
            logger.error(f'[赛事安排] LoL 推送失败: {type(e).__name__}: {e}', exc_info=True)
```

- [ ] **Step 4: 跑全部相关测试**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_esports_retry_queue.py tests/test_esports_daily_schedule_routing.py tests/test_esports_lol_fetch.py -v
```

预期：全部 passed（13 队列单测 + 4 策略路由 + 既有 LoL fetch 测试）

- [ ] **Step 5: Commit**

```bash
git add app/strategies/esports_daily_schedule/__init__.py tests/test_esports_daily_schedule_routing.py
git commit -m "feat(esports-retry): 策略层失败联赛改为 enqueue 挂起"
```

---

## Task 8: CLAUDE.md 文档同步 + 全量测试

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 在 "赛事推送配置" 节追加说明**

定位 `## 赛事推送配置` 段落（约在 NBA 晚间调度说明的后面），在 "推送逻辑" 列表末尾追加一条：

```markdown
- 失败重试：单联赛 / 整 NBA 拉取失败时，挂起 5min × 3 轮调度层重试，期间任意一轮成功立即"补推"该联赛，3 轮全失败才推"数据获取失败（已重试 3 次）"。状态进程内 `app/services/esports_retry_queue.py` 维护，进程重启丢失（接受最多漏一次补推）。
```

- [ ] **Step 2: 跑全量单测确保零回归**

```
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v
```

预期：全部 passed。重点关注既有 `test_esports_lol_fetch.py` 全部 9 用例与新 17 用例。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude.md): 赛事推送失败重试队列说明"
```

---

## Self-Review Checklist

- [x] **Spec 覆盖**：状态机三态 / 5min×3 轮 / LoL+NBA 双 unit / 跨日丢弃 / 空数据分支 / 进程内字典 — 任务 1-7 覆盖；CLAUDE.md 同步在任务 8
- [x] **无占位符**：所有步骤含完整代码块或具体命令；唯一 NotImplementedError 是 TDD 中间态（Task 1-5 故意留作"红"）
- [x] **类型/方法名一致**：`_PendingUnit` / `_pending` / `_key()` / `_schedule_retry()` / `_retry_one()` / `_refetch()` / `_push_supplement()` / `_push_failed()` / `_push_lol_supplement()` / `_push_nba_supplement()` / `clear_for_date()` 在所有任务一致
- [x] **API 契约对齐**：`NotificationService.send_slack(message, channel)` 顺序正确；`scheduler_engine.scheduler.add_job(... DateTrigger(run_date=...))` 与项目现有 `volume_alert` 模式一致
- [x] **frequency**：每个 Task 末尾都有 commit

## 不引入的复杂度（YAGNI）

- 持久化（DB / 文件）— 进程重启丢失可接受
- 跨进程协调（Redis / 锁）— 单 worker 部署
- 可配置环境变量（重试次数 / 间隔）— 5min×3 够用，需要时再加
