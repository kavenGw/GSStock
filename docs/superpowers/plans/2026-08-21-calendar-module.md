# 事件日历模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/calendar` 双月日历页，聚合盯盘池股票的财报日、除权除息日与宏观事件，并在每日 8:00 推送中新增「未来 7 天事件」段落。

**Architecture:** 四类事件由四个 collector 采集（巨潮预约披露 / yfinance calendar / akshare 分红送配 / 本地宏观日程表），统一 upsert 进新表 `stock_event`，由 `calendar_event` 策略每日 7:30 物化。页面与推送均只读该表，毫秒响应。唯一约束用业务键 `(event_type, stock_code, source, period_key)` 而非日期，使得财报改期是 update 而非新增行。

**Tech Stack:** Flask + SQLAlchemy + SQLite、akshare 1.18.35、yfinance 0.2.66、APScheduler、原生 CSS Grid（不引入日历库）

**Spec:** `docs/superpowers/specs/2026-08-21-calendar-module-design.md`

## 对 Spec 的一处修正（实施前必读）

Spec §四 写「`format_earnings_alerts` 去掉 `non_a_codes` 过滤（A 股现已有巨潮数据）」——**这一步单独做是无效的**。该函数取数走 `EarningsService.get_earnings_dates()`，而 A 股分支 `_fetch_earnings_akshare`（`app/services/earnings.py:198`）仍是空壳，去掉过滤后 A 股照样拿不到日期。

因此本计划把巨潮取数下沉为 `EarningsService.fetch_disclosure_map(period)`，**同时**用它实现 `_fetch_earnings_akshare`（Task 2），日历 collector 复用同一个函数。这样只有一处 cninfo 取数逻辑，A 股财报预警是真的被修好，而不是看起来被修好。

## Global Constraints

- 所有 `git` / `pytest` 命令前加 `rtk`，链式 `&&` 中也要。
- 单测命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`（env 赋值必须在 `rtk` 之前）。
- 单测平铺在 `tests/test_*.py`，不建子目录。
- 写含中文的文件必须显式 `encoding='utf-8'`（`PYTHONIOENCODING` 只管 stdout）。
- `git add` 与 `git commit` 必须放进**同一条**命令链（并行 session 会抢 index）。多行中文 commit message 走 `.git/MSG.txt` 文件，不用 heredoc。
- 时间戳统一用 `datetime.now()`（本地时区），**不要用 `datetime.utcnow`**。`earnings_snapshot.py` 用的是 `utcnow`，本模块的 `updated_at` 会参与「N 小时未更新」计算，混用会在 CST 下产生 8 小时误差。
- 事件范围仅取 `WATCH_CODES` 的**顶层条目**，不展开条目内的 `ah` 子代码（否则 A+H 同一家公司会出现两条同样的财报事件）。
- 本模块改动 `app/` 代码，属功能开发 → 按 `.claude/rules/dev-environment.md` 先建独立 git worktree，不在 main 上进行。

## File Structure

| 文件 | 责任 |
|---|---|
| `app/models/stock_event.py` | 新建。`StockEvent` 模型，业务键唯一约束 |
| `app/models/__init__.py` | 修改。导入并导出 `StockEvent` |
| `app/services/earnings.py` | 修改。新增 `fetch_disclosure_map()`，用它实现 `_fetch_earnings_akshare` |
| `app/config/macro_calendar.py` | 新建。FOMC / CPI / 非农日程常量 |
| `app/services/calendar_event.py` | 新建。`CalendarEventService`（DB 层 + 四个 collector + `refresh_all`） |
| `app/strategies/calendar_event/__init__.py` | 新建。7:30 采集策略 |
| `app/routes/calendar.py` | 新建。页面 + 两个 API 端点 |
| `app/routes/__init__.py` | 修改。声明 `calendar_bp` |
| `app/__init__.py` | 修改。注册 blueprint |
| `app/templates/calendar.html` | 新建。双月日历骨架 |
| `app/templates/base.html` | 修改。导航入口 |
| `app/static/js/calendar.js` | 新建。渲染 + 交互 |
| `app/static/css/calendar.css` | 新建。Grid 布局 + chip 配色（CSS 变量，跟随深色主题） |
| `app/services/notification.py` | 修改。`format_calendar_events()`、`format_earnings_alerts` 降级为补集、`build_market_blocks` 收 `calendar_text` |
| `app/llm/prompts/daily_briefing.py` | 修改。`label_map` 加 `calendar_events` |

---

### Task 1: `StockEvent` 模型与 DB 层

**Files:**
- Create: `app/models/stock_event.py`
- Modify: `app/models/__init__.py`
- Create: `app/services/calendar_event.py`
- Test: `tests/test_calendar_event_model.py`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `StockEvent` 模型，字段见下方代码，`to_dict() -> dict`
  - `CalendarEventService.upsert_events(events: list[dict]) -> list[int]` — 返回被写入/更新的行 id 列表
  - `CalendarEventService.prune_stale(start: date, end: date, keep_ids: list[int], sources: list[str]) -> int` — 返回删除行数
  - `CalendarEventService.get_events(start: date, end: date) -> list[dict]`
  - `CalendarEventService.hours_since_refresh() -> float | None`
  - 事件 dict 的约定键：`event_date`(date), `event_type`(str), `stock_code`(str, 宏观为 `''`), `stock_name`(str|None), `market`(str), `title`(str), `detail`(str|None), `priority`(str), `source`(str), `status`(str), `period_key`(str), `extra`(dict|None)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_calendar_event_model.py`：

```python
from datetime import date, datetime, timedelta

import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    """独立 sqlite Flask app，含 stock_event 表，隔离于 data/stock.db。"""
    from app import db
    import app.models.stock_event  # noqa: F401  注册模型到 metadata
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _ev(**kw):
    base = {
        'event_date': date(2026, 8, 26),
        'event_type': 'earnings',
        'stock_code': '002156',
        'stock_name': '通富微电',
        'market': 'A',
        'title': '中报披露',
        'detail': None,
        'priority': 'MEDIUM',
        'source': 'cninfo',
        'status': 'scheduled',
        'period_key': '2026H1',
        'extra': None,
    }
    base.update(kw)
    return base


def test_upsert_same_business_key_updates_in_place(app_ctx):
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    ids1 = CalendarEventService.upsert_events([_ev()])
    ids2 = CalendarEventService.upsert_events([
        _ev(event_date=date(2026, 8, 29), status='changed',
            detail='预约 2026-08-26 → 2026-08-29')
    ])

    rows = StockEvent.query.all()
    assert len(rows) == 1, '改期必须 update 而非新增行'
    assert ids1 == ids2
    assert rows[0].event_date == date(2026, 8, 29)
    assert rows[0].status == 'changed'
    assert rows[0].detail == '预约 2026-08-26 → 2026-08-29'


def test_macro_event_uses_empty_stock_code_not_null(app_ctx):
    """SQLite 唯一索引里 NULL 互不相等，宏观事件必须存空串才能去重。"""
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    macro = _ev(event_type='macro', stock_code='', stock_name=None,
                market='US', title='FOMC 议息', source='fomc',
                period_key='2026-09-16', event_date=date(2026, 9, 16),
                priority='HIGH')
    CalendarEventService.upsert_events([macro])
    CalendarEventService.upsert_events([macro])

    rows = StockEvent.query.filter_by(event_type='macro').all()
    assert len(rows) == 1
    assert rows[0].stock_code == ''


def test_prune_stale_removes_unmatched_but_keeps_manual(app_ctx):
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(stock_code='002156', period_key='2026H1'),
        _ev(stock_code='300223', stock_name='君正股份', period_key='2026H1',
            event_date=date(2026, 8, 29)),
        _ev(stock_code='603986', stock_name='兆易创新', source='manual',
            period_key='M1', event_date=date(2026, 8, 27)),
    ])
    keep = CalendarEventService.upsert_events([_ev(stock_code='002156', period_key='2026H1')])

    removed = CalendarEventService.prune_stale(
        date(2026, 8, 1), date(2026, 8, 31), keep, ['cninfo'])

    codes = {r.stock_code for r in StockEvent.query.all()}
    assert removed == 1
    assert codes == {'002156', '603986'}, 'manual 行不可被清理'


def test_prune_stale_only_touches_given_sources(app_ctx):
    """某个 collector 挂了时，不能连带删掉它那一类的历史事件。"""
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(source='cninfo', stock_code='002156', period_key='2026H1'),
        _ev(source='yfinance', stock_code='0700.HK', stock_name='腾讯控股',
            market='HK', period_key='2026Q3', event_date=date(2026, 8, 20)),
    ])

    removed = CalendarEventService.prune_stale(
        date(2026, 8, 1), date(2026, 8, 31), [], ['cninfo'])

    sources = {r.source for r in StockEvent.query.all()}
    assert removed == 1
    assert sources == {'yfinance'}


def test_get_events_sorted_by_date_then_priority(app_ctx):
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([
        _ev(stock_code='300223', period_key='A', event_date=date(2026, 8, 26),
            priority='LOW', title='除息'),
        _ev(stock_code='002156', period_key='B', event_date=date(2026, 8, 26),
            priority='HIGH', title='中报披露'),
        _ev(stock_code='603986', period_key='C', event_date=date(2026, 8, 25),
            priority='MEDIUM', title='中报披露'),
    ])

    out = CalendarEventService.get_events(date(2026, 8, 1), date(2026, 8, 31))

    assert [e['title'] for e in out] == ['中报披露', '中报披露', '除息']
    assert out[0]['event_date'] == '2026-08-25'
    assert out[1]['stock_code'] == '002156'


def test_hours_since_refresh_none_when_empty(app_ctx):
    from app.services.calendar_event import CalendarEventService
    assert CalendarEventService.hours_since_refresh() is None


def test_hours_since_refresh_reads_max_updated_at(app_ctx):
    from app import db
    from app.models.stock_event import StockEvent
    from app.services.calendar_event import CalendarEventService

    CalendarEventService.upsert_events([_ev()])
    row = StockEvent.query.first()
    row.updated_at = datetime.now() - timedelta(hours=30)
    db.session.commit()

    hours = CalendarEventService.hours_since_refresh()
    assert 29 < hours < 31
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_event_model.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.models.stock_event'`

- [ ] **Step 3: 写模型**

创建 `app/models/stock_event.py`：

```python
from datetime import datetime

from app import db


class StockEvent(db.Model):
    """盯盘股/宏观重要事件 — 由 calendar_event 策略每日物化"""
    __tablename__ = 'stock_event'
    __table_args__ = (
        db.UniqueConstraint('event_type', 'stock_code', 'source', 'period_key',
                            name='uq_stock_event_business_key'),
        db.Index('idx_stock_event_date', 'event_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_date = db.Column(db.Date, nullable=False)
    event_type = db.Column(db.String(20), nullable=False)
    # 宏观事件存空串而非 NULL：SQLite 唯一索引中 NULL 互不相等，会导致去重失效
    stock_code = db.Column(db.String(20), nullable=False, default='')
    stock_name = db.Column(db.String(50))
    market = db.Column(db.String(10))
    title = db.Column(db.String(200), nullable=False)
    detail = db.Column(db.String(500))
    priority = db.Column(db.String(10), nullable=False, default='MEDIUM')
    source = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='scheduled')
    period_key = db.Column(db.String(20), nullable=False)
    extra = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'event_date': self.event_date.isoformat() if self.event_date else None,
            'event_type': self.event_type,
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market': self.market,
            'title': self.title,
            'detail': self.detail,
            'priority': self.priority,
            'source': self.source,
            'status': self.status,
        }
```

在 `app/models/__init__.py` 末尾（`EarningsSnapshot` 那行之后）加导入，并把 `'StockEvent'` 追加进 `__all__`：

```python
from app.models.stock_event import StockEvent
```

- [ ] **Step 4: 写 DB 层**

创建 `app/services/calendar_event.py`：

```python
"""事件日历服务 — 采集并物化盯盘股/宏观重要事件"""
import json
import logging
from datetime import date, datetime

from app import db
from app.models.stock_event import StockEvent

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}

_WRITABLE_FIELDS = ('event_date', 'stock_name', 'market', 'title',
                    'detail', 'priority', 'status')


class CalendarEventService:
    """事件日历服务"""

    @staticmethod
    def upsert_events(events: list[dict]) -> list[int]:
        """按业务键 (event_type, stock_code, source, period_key) upsert，返回命中行 id"""
        ids = []
        for e in events:
            key = {
                'event_type': e['event_type'],
                'stock_code': e.get('stock_code') or '',
                'source': e['source'],
                'period_key': e['period_key'],
            }
            row = StockEvent.query.filter_by(**key).first()
            if row is None:
                row = StockEvent(**key)
                db.session.add(row)

            for f in _WRITABLE_FIELDS:
                if f in e:
                    setattr(row, f, e[f])
            extra = e.get('extra')
            row.extra = json.dumps(extra, ensure_ascii=False) if extra else None
            row.updated_at = datetime.now()

            db.session.flush()
            ids.append(row.id)

        db.session.commit()
        return ids

    @staticmethod
    def prune_stale(start: date, end: date, keep_ids: list[int],
                    sources: list[str]) -> int:
        """删除窗口内、属于 sources、且本轮未命中的行。manual 永不删除。"""
        if not sources:
            return 0

        q = StockEvent.query.filter(
            StockEvent.source.in_(sources),
            StockEvent.source != 'manual',
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        )
        if keep_ids:
            q = q.filter(~StockEvent.id.in_(keep_ids))

        n = q.delete(synchronize_session=False)
        db.session.commit()
        return n

    @staticmethod
    def get_events(start: date, end: date) -> list[dict]:
        rows = StockEvent.query.filter(
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        ).all()
        rows.sort(key=lambda r: (r.event_date,
                                 PRIORITY_ORDER.get(r.priority, 1),
                                 r.stock_code or ''))
        return [r.to_dict() for r in rows]

    @staticmethod
    def hours_since_refresh() -> float | None:
        """距最近一次采集的小时数；表为空返回 None"""
        latest = db.session.query(db.func.max(StockEvent.updated_at)).scalar()
        if not latest:
            return None
        return (datetime.now() - latest).total_seconds() / 3600
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_event_model.py -v`
Expected: 7 passed

- [ ] **Step 6: 提交**

```bash
printf '%s\n' "feat(calendar): 新增 stock_event 模型与事件日历 DB 层" "" "业务键 (event_type, stock_code, source, period_key) 做唯一约束，财报改期为 update 而非新增行。" "宏观事件 stock_code 存空串——SQLite 唯一索引中 NULL 互不相等，存 NULL 会让去重失效。" "prune 按 source 分域，单个 collector 失败不会连带清空其他类事件。" > .git/MSG.txt && rtk git add app/models/stock_event.py app/models/__init__.py app/services/calendar_event.py tests/test_calendar_event_model.py && rtk git commit -F .git/MSG.txt
```

---

### Task 2: 巨潮预约披露取数（并修复 A 股财报空壳）

**Files:**
- Modify: `app/services/earnings.py:198`（`_fetch_earnings_akshare`）
- Test: `tests/test_earnings_disclosure_map.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `EarningsService.fetch_disclosure_map(period: str) -> dict[str, dict]`
    返回 `{股票代码: {'date': date, 'status': str, 'detail': str | None}}`；`status` ∈ `scheduled`/`changed`/`confirmed`。数据源异常或期次未发布时返回 `{}`。
  - `EarningsService._fetch_earnings_akshare(stock_code)` 改为真实实现，返回值结构不变（`last_earnings_date` / `next_earnings_date` / `market` / `fetch_time`）
  - `app.services.earnings.period_keys_for_window(today: date) -> list[tuple[str, str]]`
    返回 `[(akshare 期次参数, period_key)]`，如 `[('2026半年报', '2026H1')]`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_earnings_disclosure_map.py`：

```python
from datetime import date

import pandas as pd
import pytest


def _df(rows):
    return pd.DataFrame(rows, columns=[
        '股票代码', '股票简称', '首次预约', '初次变更', '二次变更', '三次变更', '实际披露'])


def test_period_keys_for_window_august_covers_h1():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 8, 21))
    assert ('2026半年报', '2026H1') in out


def test_period_keys_for_window_september_covers_h1_and_q3():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 9, 10))
    keys = [k for _, k in out]
    assert '2026H1' in keys and '2026Q3' in keys


def test_period_keys_for_window_deduplicates():
    from app.services.earnings import period_keys_for_window
    out = period_keys_for_window(date(2026, 7, 1))
    assert len(out) == len(set(out))


def test_fetch_disclosure_map_picks_actual_over_scheduled(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', lambda market, period: _df([
        ['603986', '兆易创新', pd.Timestamp('2026-08-19'), pd.NaT, pd.NaT, pd.NaT,
         pd.Timestamp('2026-08-19')],
    ]))

    out = mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert out['603986']['date'] == date(2026, 8, 19)
    assert out['603986']['status'] == 'confirmed'


def test_fetch_disclosure_map_marks_changed_and_records_original(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', lambda market, period: _df([
        ['002156', '通富微电', pd.Timestamp('2026-08-26'), pd.Timestamp('2026-08-29'),
         pd.NaT, pd.NaT, pd.NaT],
    ]))

    out = mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert out['002156']['date'] == date(2026, 8, 29)
    assert out['002156']['status'] == 'changed'
    assert '2026-08-26' in out['002156']['detail']
    assert '2026-08-29' in out['002156']['detail']


def test_fetch_disclosure_map_swallows_unpublished_period(monkeypatch):
    """未发布期次时 akshare 内部抛 ValueError，必须吞掉返回空 dict。"""
    from app.services import earnings as mod

    def _boom(market, period):
        raise ValueError('Length mismatch: Expected axis has 0 elements, '
                         'new values have 10 elements')

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _boom)

    assert mod.EarningsService.fetch_disclosure_map('2026三季') == {}


def test_fetch_disclosure_map_caches_per_period(monkeypatch):
    from app.services import earnings as mod

    calls = []

    def _spy(market, period):
        calls.append(period)
        return _df([['603986', '兆易创新', pd.Timestamp('2026-08-19'),
                     pd.NaT, pd.NaT, pd.NaT, pd.NaT]])

    monkeypatch.setattr(mod, '_disclosure_cache', {})
    monkeypatch.setattr(mod.ak, 'stock_report_disclosure', _spy)

    mod.EarningsService.fetch_disclosure_map('2026半年报')
    mod.EarningsService.fetch_disclosure_map('2026半年报')

    assert calls == ['2026半年报'], '同一期次同一天只应取一次'


def test_fetch_earnings_akshare_now_returns_real_dates(monkeypatch):
    """回归：该函数曾是空壳，A股财报预警长期失效。"""
    from app.services import earnings as mod

    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '000725': {'date': date(2026, 8, 29), 'status': 'scheduled', 'detail': None}
        }))
    monkeypatch.setattr(mod, '_today', lambda: date(2026, 8, 21))

    out = mod.EarningsService._fetch_earnings_akshare('000725')

    assert out['next_earnings_date'] == '2026-08-29'
    assert out['market'] == 'A'


def test_fetch_earnings_akshare_past_date_goes_to_last(monkeypatch):
    from app.services import earnings as mod

    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '603986': {'date': date(2026, 8, 19), 'status': 'confirmed', 'detail': None}
        }))
    monkeypatch.setattr(mod, '_today', lambda: date(2026, 8, 21))

    out = mod.EarningsService._fetch_earnings_akshare('603986')

    assert out['last_earnings_date'] == '2026-08-19'
    assert out['next_earnings_date'] is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_earnings_disclosure_map.py -v`
Expected: FAIL，`AttributeError: module 'app.services.earnings' has no attribute 'ak'`

- [ ] **Step 3: 实现**

在 `app/services/earnings.py` 顶部 import 区加：

```python
import akshare as ak
import pandas as pd
```

在 `logger = logging.getLogger(__name__)` 之后加模块级常量与缓存：

```python
# 巨潮预约披露：(period, 取数日) -> {code: {...}}，进程内每期次每天只取一次
_disclosure_cache: dict = {}

_DISCLOSURE_PICK_ORDER = ['实际披露', '三次变更', '二次变更', '初次变更', '首次预约']
_DISCLOSURE_CHANGE_COLS = ['三次变更', '二次变更', '初次变更']

# 月份 -> [(报告期中文, 年份偏移)]，覆盖该月可能发生的财报披露
_MONTH_REPORT_PERIODS = {
    1: [('年报', -1)],
    2: [('年报', -1)],
    3: [('年报', -1)],
    4: [('年报', -1), ('一季', 0)],
    5: [('一季', 0)],
    6: [],
    7: [('半年报', 0)],
    8: [('半年报', 0)],
    9: [('半年报', 0), ('三季', 0)],
    10: [('三季', 0)],
    11: [],
    12: [],
}

_PERIOD_KEY_SUFFIX = {'年报': 'A', '一季': 'Q1', '半年报': 'H1', '三季': 'Q3'}


def _today() -> date:
    """便于测试注入"""
    return date.today()


def period_keys_for_window(today: date = None) -> list[tuple[str, str]]:
    """当月与下月覆盖到的报告期，返回 [(akshare 期次参数, period_key)]"""
    if today is None:
        today = _today()

    months = [(today.year, today.month)]
    if today.month == 12:
        months.append((today.year + 1, 1))
    else:
        months.append((today.year, today.month + 1))

    out = []
    for y, m in months:
        for label, offset in _MONTH_REPORT_PERIODS.get(m, []):
            year = y + offset
            pair = (f'{year}{label}', f'{year}{_PERIOD_KEY_SUFFIX[label]}')
            if pair not in out:
                out.append(pair)
    return out


def _cell_date(row, col):
    """把 pandas 单元格转成 date，NaT/NaN/空串一律 None"""
    if col not in row:
        return None
    v = row[col]
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    ts = pd.to_datetime(v, errors='coerce')
    if ts is None or pd.isna(ts):
        return None
    return ts.date()
```

在 `EarningsService` 类里加 `fetch_disclosure_map`：

```python
    @staticmethod
    def fetch_disclosure_map(period: str) -> dict:
        """巨潮预约披露 -> {股票代码: {'date', 'status', 'detail'}}

        期次未发布时 akshare 对空 DataFrame 硬赋列名会抛 ValueError，此处吞掉返回 {}。
        """
        cache_key = (period, _today())
        if cache_key in _disclosure_cache:
            return _disclosure_cache[cache_key]

        try:
            df = ak.stock_report_disclosure(market='沪深京', period=period)
        except Exception as e:
            logger.info(f'[财报.预约披露] 期次 {period} 暂无数据: {e}')
            _disclosure_cache[cache_key] = {}
            return {}

        result = {}
        for _, row in df.iterrows():
            code = str(row.get('股票代码', '')).strip()
            if not code:
                continue

            picked = None
            for col in _DISCLOSURE_PICK_ORDER:
                picked = _cell_date(row, col)
                if picked:
                    break
            if not picked:
                continue

            actual = _cell_date(row, '实际披露')
            changed = any(_cell_date(row, c) for c in _DISCLOSURE_CHANGE_COLS)
            if actual:
                status = 'confirmed'
            elif changed:
                status = 'changed'
            else:
                status = 'scheduled'

            detail = None
            first = _cell_date(row, '首次预约')
            if changed and first and first != picked:
                detail = f'预约 {first.isoformat()} → {picked.isoformat()}'

            result[code] = {'date': picked, 'status': status, 'detail': detail}

        _disclosure_cache[cache_key] = result
        return result
```

把 `_fetch_earnings_akshare`（原 `app/services/earnings.py:198` 的空壳）整体替换为：

```python
    @staticmethod
    def _fetch_earnings_akshare(stock_code: str) -> dict | None:
        """从巨潮预约披露获取A股财报日期"""
        try:
            today = _today()
            last_d, next_d = None, None

            for period, _ in period_keys_for_window(today):
                hit = EarningsService.fetch_disclosure_map(period).get(stock_code)
                if not hit:
                    continue
                d = hit['date']
                if d < today:
                    if last_d is None or d > last_d:
                        last_d = d
                elif next_d is None or d < next_d:
                    next_d = d

            return {
                'last_earnings_date': last_d.isoformat() if last_d else None,
                'next_earnings_date': next_d.isoformat() if next_d else None,
                'market': 'A',
                'fetch_time': datetime.now().isoformat()
            }
        except Exception as e:
            logger.warning(f"[财报] {stock_code} 获取A股数据失败: {e}")
            return None
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_earnings_disclosure_map.py -v`
Expected: 9 passed

- [ ] **Step 5: 联网实跑核对**

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0,'.')
from app.services.earnings import EarningsService, period_keys_for_window
from datetime import date
print(period_keys_for_window(date.today()))
m = EarningsService.fetch_disclosure_map('2026半年报')
for c in ['000725','002156','603986','600584']:
    print(c, m.get(c))
"
```
Expected: 打印出真实日期，`002156` 的 `status` 为 `changed`、`detail` 含「预约 2026-08-26 → 2026-08-29」，`603986` 为 `confirmed`。若巨潮当日不可达则重试；**不要**因此改测试。

- [ ] **Step 6: 提交**

```bash
printf '%s\n' "feat(earnings): 接入巨潮预约披露，修复 A 股财报日期空壳" "" "_fetch_earnings_akshare 此前直接返回 None，A 股财报预警长期失效。" "新增 fetch_disclosure_map(period) 统一取数（进程内按期次+日期缓存），" "取值优先级 实际披露>三次变更>二次变更>初次变更>首次预约，并据此判定 scheduled/changed/confirmed。" "未发布期次 akshare 会对空 DataFrame 抛 ValueError，已吞掉返回空 dict。" > .git/MSG.txt && rtk git add app/services/earnings.py tests/test_earnings_disclosure_map.py && rtk git commit -F .git/MSG.txt
```

---

### Task 3: 个股事件 collector（财报 + 除权除息）

**Files:**
- Modify: `app/services/calendar_event.py`
- Test: `tests/test_calendar_collectors.py`

**Interfaces:**
- Consumes: `EarningsService.fetch_disclosure_map`、`period_keys_for_window`（Task 2）；事件 dict 约定（Task 1）
- Produces:
  - `collect_earnings_a(today: date = None) -> list[dict]` — source `cninfo`
  - `collect_calendar_yf(today: date = None) -> list[dict]` — source `yfinance`，同时产出 `earnings` 与 `ex_dividend`
  - `collect_dividend_a(today: date = None) -> list[dict]` — source `akshare`
  - 三者均为 `app/services/calendar_event.py` 的模块级函数

- [ ] **Step 1: 写失败测试**

创建 `tests/test_calendar_collectors.py`：

```python
from datetime import date

import pandas as pd
import pytest


WATCH_STUB = [
    {'code': '002156', 'name': '通富微电', 'market': 'A'},
    {'code': '603986', 'name': '兆易创新', 'market': 'A'},
    {'code': '0700.HK', 'name': '腾讯控股', 'market': 'HK',
     'ah': {'code': '000001', 'market': 'A', 'name': '不应被采集'}},
    {'code': '000660.KS', 'name': 'SK海力士', 'market': 'KR'},
]


@pytest.fixture
def patched_watch(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'WATCH_CODES', WATCH_STUB)
    return mod


def test_collect_earnings_a_maps_disclosure_to_events(patched_watch, monkeypatch):
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '002156': {'date': date(2026, 8, 29), 'status': 'changed',
                       'detail': '预约 2026-08-26 → 2026-08-29'},
            '603986': {'date': date(2026, 8, 19), 'status': 'confirmed', 'detail': None},
            '999999': {'date': date(2026, 8, 20), 'status': 'scheduled', 'detail': None},
        }))

    out = mod.collect_earnings_a(date(2026, 8, 21))

    codes = {e['stock_code'] for e in out}
    assert codes == {'002156', '603986'}, '非盯盘股不得进入日历'
    by_code = {e['stock_code']: e for e in out}
    assert by_code['002156']['event_date'] == date(2026, 8, 29)
    assert by_code['002156']['period_key'] == '2026H1'
    assert by_code['002156']['source'] == 'cninfo'
    assert by_code['002156']['event_type'] == 'earnings'
    assert by_code['002156']['priority'] == 'HIGH'
    assert by_code['002156']['title'] == '中报披露'


def test_collect_earnings_a_scheduled_is_medium_priority(patched_watch, monkeypatch):
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '002156': {'date': date(2026, 8, 29), 'status': 'scheduled', 'detail': None},
        }))

    out = mod.collect_earnings_a(date(2026, 8, 21))
    assert out[0]['priority'] == 'MEDIUM'


def test_collect_earnings_a_skips_ah_subcodes(patched_watch, monkeypatch):
    """WATCH_CODES 条目内的 ah 子代码不展开，否则 A+H 同公司会重复两条。"""
    mod = patched_watch
    monkeypatch.setattr(mod, 'period_keys_for_window',
                        lambda today=None: [('2026半年报', '2026H1')])
    monkeypatch.setattr(
        mod.EarningsService, 'fetch_disclosure_map',
        staticmethod(lambda period: {
            '000001': {'date': date(2026, 8, 25), 'status': 'scheduled', 'detail': None},
        }))

    assert mod.collect_earnings_a(date(2026, 8, 21)) == []


class _FakeTicker:
    def __init__(self, cal):
        self._cal = cal

    @property
    def calendar(self):
        return self._cal


def test_collect_calendar_yf_yields_earnings_and_ex_dividend(patched_watch, monkeypatch):
    mod = patched_watch
    cals = {
        '0700.HK': {'Earnings Date': [date(2026, 11, 12)],
                    'Ex-Dividend Date': date(2026, 9, 10)},
        '000660.KS': {'Earnings Date': [date(2026, 10, 24)]},
    }
    monkeypatch.setattr(mod, '_yf_ticker', lambda code: _FakeTicker(cals[code]))
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)

    out = mod.collect_calendar_yf(date(2026, 8, 21))

    types = sorted((e['stock_code'], e['event_type']) for e in out)
    assert types == [('000660.KS', 'earnings'),
                     ('0700.HK', 'earnings'),
                     ('0700.HK', 'ex_dividend')]
    xd = [e for e in out if e['event_type'] == 'ex_dividend'][0]
    assert xd['priority'] == 'LOW'
    assert xd['period_key'] == 'XD202609'
    er = [e for e in out if e['stock_code'] == '0700.HK'
          and e['event_type'] == 'earnings'][0]
    assert er['period_key'] == '2026Q4'
    assert er['source'] == 'yfinance'


def test_collect_calendar_yf_drops_past_ex_dividend(patched_watch, monkeypatch):
    """yfinance 的 Ex-Dividend Date 是「最近一次」，常常已是过去日期。"""
    mod = patched_watch
    cals = {
        '0700.HK': {'Ex-Dividend Date': date(2026, 5, 15)},
        '000660.KS': {},
    }
    monkeypatch.setattr(mod, '_yf_ticker', lambda code: _FakeTicker(cals[code]))
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == []


def test_collect_calendar_yf_returns_empty_when_circuit_open(patched_watch, monkeypatch):
    mod = patched_watch

    def _boom(code):
        raise AssertionError('熔断时不应发起请求')

    monkeypatch.setattr(mod, '_yf_ticker', _boom)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: False)

    assert mod.collect_calendar_yf(date(2026, 8, 21)) == []


def test_collect_calendar_yf_one_bad_ticker_does_not_kill_rest(patched_watch, monkeypatch):
    mod = patched_watch

    def _tk(code):
        if code == '0700.HK':
            raise RuntimeError('delisted')
        return _FakeTicker({'Earnings Date': [date(2026, 10, 24)]})

    monkeypatch.setattr(mod, '_yf_ticker', _tk)
    monkeypatch.setattr(mod.circuit_breaker, 'is_available', lambda name: True)
    monkeypatch.setattr(mod.time, 'sleep', lambda s: None)

    out = mod.collect_calendar_yf(date(2026, 8, 21))
    assert [e['stock_code'] for e in out] == ['000660.KS']


def test_collect_dividend_a_maps_ex_date(patched_watch, monkeypatch):
    mod = patched_watch
    df = pd.DataFrame([
        {'代码': '002156', '名称': '通富微电', '除权除息日': pd.Timestamp('2026-09-05'),
         '现金分红-现金分红比例': 1.5, '方案进度': '实施方案'},
        {'代码': '603986', '名称': '兆易创新', '除权除息日': pd.NaT,
         '现金分红-现金分红比例': 2.0, '方案进度': '预披露'},
        {'代码': '999999', '名称': '别人家', '除权除息日': pd.Timestamp('2026-09-06'),
         '现金分红-现金分红比例': 1.0, '方案进度': '实施方案'},
    ])
    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', lambda date: df)

    out = mod.collect_dividend_a(date(2026, 8, 21))

    assert len(out) == 1
    e = out[0]
    assert e['stock_code'] == '002156'
    assert e['event_date'] == date(2026, 9, 5)
    assert e['event_type'] == 'ex_dividend'
    assert e['source'] == 'akshare'
    assert e['period_key'] == 'FH20251231'
    assert '实施方案' in e['detail']


def test_collect_dividend_a_swallows_source_error(patched_watch, monkeypatch):
    mod = patched_watch

    def _boom(date):
        raise RuntimeError('akshare down')

    monkeypatch.setattr(mod, '_fhps_report_dates', lambda today: ['20251231'])
    monkeypatch.setattr(mod.ak, 'stock_fhps_em', _boom)

    assert mod.collect_dividend_a(date(2026, 8, 21)) == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_collectors.py -v`
Expected: FAIL，`AttributeError: module 'app.services.calendar_event' has no attribute 'WATCH_CODES'`

- [ ] **Step 3: 实现**

在 `app/services/calendar_event.py` 的 import 区补：

```python
import time

import akshare as ak
import pandas as pd

from app.config.stock_codes import WATCH_CODES
from app.services.circuit_breaker import circuit_breaker
from app.services.earnings import (
    EarningsService, period_keys_for_window, _cell_date,
)
from app.utils.market_identifier import MarketIdentifier
```

在 `PRIORITY_ORDER` 附近补常量：

```python
YF_MAX_RETRIES = 3
YF_RETRY_DELAY = 1.0

# period_key 后缀 -> 财报中文标题
_REPORT_TITLE = {'A': '年报披露', 'Q1': '一季报披露', 'H1': '中报披露', 'Q3': '三季报披露'}
```

在文件末尾（`CalendarEventService` 类之后）加 collector：

```python
def _watch_entries(markets: set[str] = None) -> list[dict]:
    """WATCH_CODES 顶层条目；不展开 ah 子代码（否则 A+H 同公司会重复）"""
    return [e for e in WATCH_CODES if markets is None or e.get('market') in markets]


def _yf_ticker(yf_code: str):
    """便于测试注入"""
    import yfinance as yf
    return yf.Ticker(yf_code)


def collect_earnings_a(today: date = None) -> list[dict]:
    """A股财报日 — 巨潮预约披露"""
    if today is None:
        today = date.today()

    watch = {e['code']: e['name'] for e in _watch_entries({'A'})}
    if not watch:
        return []

    out = []
    for period, period_key in period_keys_for_window(today):
        title = _REPORT_TITLE.get(period_key[4:], '财报披露')
        hits = EarningsService.fetch_disclosure_map(period)
        for code, name in watch.items():
            hit = hits.get(code)
            if not hit:
                continue
            out.append({
                'event_date': hit['date'],
                'event_type': 'earnings',
                'stock_code': code,
                'stock_name': name,
                'market': 'A',
                'title': title,
                'detail': hit.get('detail'),
                'priority': 'MEDIUM' if hit['status'] == 'scheduled' else 'HIGH',
                'source': 'cninfo',
                'status': hit['status'],
                'period_key': period_key,
                'extra': None,
            })
    return out


def _yf_dates(value) -> list:
    """calendar 里的日期字段可能是 date 或 [date, ...]"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    out = []
    for v in items:
        d = _cell_date({'v': v}, 'v')
        if d:
            out.append(d)
    return out


def collect_calendar_yf(today: date = None) -> list[dict]:
    """非A股财报日 + 除权日 — yfinance calendar 一次调用产出两类"""
    if today is None:
        today = date.today()

    if not circuit_breaker.is_available('yfinance'):
        logger.info('[事件日历] yfinance 已熔断，跳过')
        return []

    out = []
    ok = False
    for entry in _watch_entries():
        if entry.get('market') == 'A':
            continue

        code = entry['code']
        yf_code = MarketIdentifier.to_yfinance(code)
        cal = None
        for attempt in range(YF_MAX_RETRIES):
            try:
                cal = _yf_ticker(yf_code).calendar
                break
            except Exception as e:
                if attempt < YF_MAX_RETRIES - 1:
                    time.sleep(YF_RETRY_DELAY)
                else:
                    logger.debug(f'[事件日历] {code} calendar 取数失败: {e}')

        if not hasattr(cal, 'get'):
            continue
        ok = True

        base = {
            'stock_code': code,
            'stock_name': entry.get('name'),
            'market': entry.get('market'),
            'source': 'yfinance',
            'status': 'scheduled',
            'detail': None,
            'extra': None,
        }

        for d in _yf_dates(cal.get('Earnings Date')):
            if d < today:
                continue
            out.append({**base, 'event_date': d, 'event_type': 'earnings',
                        'title': '财报披露', 'priority': 'MEDIUM',
                        'period_key': f'{d.year}Q{(d.month - 1) // 3 + 1}'})

        for d in _yf_dates(cal.get('Ex-Dividend Date')):
            if d < today:
                continue
            out.append({**base, 'event_date': d, 'event_type': 'ex_dividend',
                        'title': '除权除息', 'priority': 'LOW',
                        'period_key': f'XD{d.year}{d.month:02d}'})

    if ok:
        circuit_breaker.record_success('yfinance')
    return out


def _fhps_report_dates(today: date) -> list[str]:
    """最近 4 个已结束的报告期末，格式 YYYYMMDD"""
    ends = []
    year = today.year
    for y in (year, year - 1):
        for mm, dd in ((12, 31), (9, 30), (6, 30), (3, 31)):
            d = date(y, mm, dd)
            if d <= today:
                ends.append(d.strftime('%Y%m%d'))
    return ends[:4]


def collect_dividend_a(today: date = None) -> list[dict]:
    """A股除权除息日 — akshare 分红送配"""
    if today is None:
        today = date.today()

    watch = {e['code']: e['name'] for e in _watch_entries({'A'})}
    if not watch:
        return []

    out = []
    for report_date in _fhps_report_dates(today):
        try:
            df = ak.stock_fhps_em(date=report_date)
        except Exception as e:
            logger.info(f'[事件日历] 分红送配 {report_date} 取数失败: {e}')
            continue

        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip()
            if code not in watch:
                continue
            ex_date = _cell_date(row, '除权除息日')
            if not ex_date:
                continue

            ratio = row.get('现金分红-现金分红比例')
            progress = str(row.get('方案进度', '') or '').strip()
            bits = [b for b in (progress, f'每10股派 {ratio} 元'
                                if pd.notna(ratio) else '') if b]

            out.append({
                'event_date': ex_date,
                'event_type': 'ex_dividend',
                'stock_code': code,
                'stock_name': watch[code],
                'market': 'A',
                'title': '除权除息',
                'detail': ' · '.join(bits) or None,
                'priority': 'LOW',
                'source': 'akshare',
                'status': 'scheduled',
                'period_key': f'FH{report_date}',
                'extra': None,
            })
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_collectors.py -v`
Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
printf '%s\n' "feat(calendar): 个股事件 collector（A股财报/非A股财报+除权/A股除权）" "" "collector 只产出候选事件不碰 DB，便于单测。" "yfinance calendar 一次调用同时产出 earnings 与 ex_dividend；" "Ex-Dividend Date 是「最近一次」可能已过期，过滤 < today。" "不展开 WATCH_CODES 条目内的 ah 子代码，避免 A+H 同公司重复两条。" > .git/MSG.txt && rtk git add app/services/calendar_event.py tests/test_calendar_collectors.py && rtk git commit -F .git/MSG.txt
```

---

### Task 4: 宏观日程与 `collect_macro`

**Files:**
- Create: `app/config/macro_calendar.py`
- Modify: `app/services/calendar_event.py`
- Test: `tests/test_macro_calendar.py`

**Interfaces:**
- Consumes: 事件 dict 约定（Task 1）
- Produces:
  - `app.config.macro_calendar.MACRO_EVENTS: list[dict]` — 每项 `{'date': date, 'type': str, 'title': str}`，`type` ∈ `fomc` / `cpi` / `nfp`
  - `collect_macro(today: date = None) -> list[dict]`（`app/services/calendar_event.py` 模块级函数）

**FOMC 日期已从美联储官网核实**（`federalreserve.gov/monetarypolicy/fomccalendars.htm`，2026-08-21 取）。会议为两天，**取第二天**（决议日）：
2026: 1/27-28、3/17-18、4/28-29、6/16-17、7/28-29、9/15-16、10/27-28、12/8-9
2027: 1/28-29、3/18-19、5/6-7、6/17-18、7/29-30、9/16-17、10/28-29、12/9-10

- [ ] **Step 1: 写失败测试**

创建 `tests/test_macro_calendar.py`：

```python
from datetime import date

import pytest


def test_macro_events_sorted_and_unique():
    from app.config.macro_calendar import MACRO_EVENTS
    dates = [(e['date'], e['type']) for e in MACRO_EVENTS]
    assert dates == sorted(dates), 'MACRO_EVENTS 必须按日期升序'
    assert len(dates) == len(set(dates)), '同日同类型不可重复'


def test_macro_events_all_real_dates():
    from app.config.macro_calendar import MACRO_EVENTS
    for e in MACRO_EVENTS:
        assert isinstance(e['date'], date)
        assert e['type'] in ('fomc', 'cpi', 'nfp')
        assert e['title']


def test_fomc_2026_matches_official_schedule():
    from app.config.macro_calendar import MACRO_EVENTS
    got = [e['date'] for e in MACRO_EVENTS
           if e['type'] == 'fomc' and e['date'].year == 2026]
    assert got == [date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
                   date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
                   date(2026, 10, 28), date(2026, 12, 9)]


def test_fomc_2027_matches_official_schedule():
    from app.config.macro_calendar import MACRO_EVENTS
    got = [e['date'] for e in MACRO_EVENTS
           if e['type'] == 'fomc' and e['date'].year == 2027]
    assert got == [date(2027, 1, 29), date(2027, 3, 19), date(2027, 5, 7),
                   date(2027, 6, 18), date(2027, 7, 30), date(2027, 9, 17),
                   date(2027, 10, 29), date(2027, 12, 10)]


@pytest.mark.parametrize('kind', ['cpi', 'nfp'])
def test_cpi_and_nfp_cover_full_year_2026(kind):
    """每月一次，缺一个月就说明日程没填全。"""
    from app.config.macro_calendar import MACRO_EVENTS
    months = sorted(e['date'].month for e in MACRO_EVENTS
                    if e['type'] == kind and e['date'].year == 2026)
    assert months == list(range(1, 13))


def test_collect_macro_filters_window_and_uses_empty_stock_code(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'MACRO_EVENTS', [
        {'date': date(2026, 7, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
        {'date': date(2026, 9, 16), 'type': 'fomc', 'title': 'FOMC 议息'},
        {'date': date(2027, 1, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    ])

    out = mod.collect_macro_range(date(2026, 8, 1), date(2026, 10, 31))

    assert len(out) == 1
    e = out[0]
    assert e['event_date'] == date(2026, 9, 16)
    assert e['stock_code'] == ''
    assert e['event_type'] == 'macro'
    assert e['priority'] == 'HIGH'
    assert e['period_key'] == '2026-09-16'
    assert e['source'] == 'fomc'


def test_collect_macro_source_per_type(monkeypatch):
    from app.services import calendar_event as mod
    monkeypatch.setattr(mod, 'MACRO_EVENTS', [
        {'date': date(2026, 9, 11), 'type': 'cpi', 'title': '美国 8 月 CPI'},
        {'date': date(2026, 9, 4), 'type': 'nfp', 'title': '美国 8 月非农'},
    ])

    out = mod.collect_macro_range(date(2026, 9, 1), date(2026, 9, 30))

    assert {e['source'] for e in out} == {'bls'}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_macro_calendar.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.config.macro_calendar'`

- [ ] **Step 3: 取 BLS 的 CPI / 非农发布日**

CPI 与非农的 2026 发布日必须来自 BLS 官方日程，**不得凭规律推算**（节假日会挪期）。

Run:
```bash
PYTHONIOENCODING=utf-8 python -c "
import re, requests
for name, u in [('CPI','https://www.bls.gov/schedule/news_release/cpi.htm'),
                ('NFP','https://www.bls.gov/schedule/news_release/empsit.htm')]:
    r = requests.get(u, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
    t = re.sub(r'<[^>]+>', ' ', r.text); t = re.sub(r'\s+', ' ', t)
    print(name, re.findall(r'(\w+ \d{4})\s+(\d{2}/\d{2}/\d{4})', t))
"
```

若本机 DNS 解析 `www.bls.gov` 失败（实测本环境会 `NameResolutionError`），改用以下任一途径取同一份日程，**不要跳过本步**：
- 浏览器打开 `https://www.bls.gov/schedule/2026/home.htm`，按 `Consumer Price Index` 与 `Employment Situation` 两行抄录 12 个发布日；
- 或在有网络的机器上跑上面的脚本，把结果拷过来。

- [ ] **Step 4: 写宏观日程常量**

创建 `app/config/macro_calendar.py`。FOMC 段按下方原样写入（已核实）；CPI / NFP 段用 Step 3 取到的真实日期填满 2026 年 12 个月，**按日期升序排列全表**：

```python
"""宏观事件日程 — 事件日历模块专用

FOMC 日期取自 federalreserve.gov/monetarypolicy/fomccalendars.htm，
会议为两天，此处记决议日（第二天）。

CPI / 非农日期取自 BLS 发布日程 bls.gov/schedule/2026/home.htm。

注意：app/services/fed_rate.py 的 FOMC_MEETINGS 是利率概率服务自用的历史决议表，
与本文件各自独立维护，不要互相引用。
"""
from datetime import date

MACRO_EVENTS = [
    {'date': date(2026, 1, 28), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 3, 18), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 4, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 6, 17), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 7, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 9, 16), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 10, 28), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2026, 12, 9), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 1, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 3, 19), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 5, 7), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 6, 18), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 7, 30), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 9, 17), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 10, 29), 'type': 'fomc', 'title': 'FOMC 议息'},
    {'date': date(2027, 12, 10), 'type': 'fomc', 'title': 'FOMC 议息'},
    # ↓ CPI / 非农：用 Step 3 取到的 BLS 官方发布日填满 2026 全年各 12 条
    #   title 格式：'美国 {统计月} CPI' / '美国 {统计月} 非农'
]

MACRO_EVENTS.sort(key=lambda e: (e['date'], e['type']))
```

填完后把整表按日期升序整理好（末尾的 `sort` 是兜底，但源码本身也应保持有序，便于人工核对）。

- [ ] **Step 5: 写 `collect_macro_range`**

在 `app/services/calendar_event.py` import 区补：

```python
from app.config.macro_calendar import MACRO_EVENTS
```

常量区补：

```python
_MACRO_SOURCE = {'fomc': 'fomc', 'cpi': 'bls', 'nfp': 'bls'}
_MACRO_MARKET = {'fomc': 'US', 'cpi': 'US', 'nfp': 'US'}
```

在文件末尾加：

```python
def collect_macro_range(start: date, end: date) -> list[dict]:
    """宏观事件 — 纯本地表，不联网"""
    out = []
    for e in MACRO_EVENTS:
        d = e['date']
        if d < start or d > end:
            continue
        out.append({
            'event_date': d,
            'event_type': 'macro',
            'stock_code': '',
            'stock_name': None,
            'market': _MACRO_MARKET.get(e['type'], 'US'),
            'title': e['title'],
            'detail': None,
            'priority': 'HIGH',
            'source': _MACRO_SOURCE.get(e['type'], 'fomc'),
            'status': 'scheduled',
            'period_key': d.isoformat(),
            'extra': None,
        })
    return out
```

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_macro_calendar.py -v`
Expected: 8 passed（`test_cpi_and_nfp_cover_full_year_2026` 会在日程没填满时失败——这是刻意的闸门，别改测试去迁就）

- [ ] **Step 7: 提交**

```bash
printf '%s\n' "feat(calendar): 新增宏观日程配置与 collect_macro_range" "" "FOMC 2026/2027 决议日取自美联储官网并有测试锁定；CPI/非农取自 BLS 发布日程。" "独立于 fed_rate.py 的 FOMC_MEETINGS（那是利率概率服务自用的历史决议表）。" > .git/MSG.txt && rtk git add app/config/macro_calendar.py app/services/calendar_event.py tests/test_macro_calendar.py && rtk git commit -F .git/MSG.txt
```

---

### Task 5: `refresh_all` 编排与 7:30 定时策略

**Files:**
- Modify: `app/services/calendar_event.py`
- Create: `app/strategies/calendar_event/__init__.py`
- Test: `tests/test_calendar_refresh.py`

**Interfaces:**
- Consumes: Task 1 的 DB 层、Task 3 的三个 collector、Task 4 的 `collect_macro_range`
- Produces:
  - `CalendarEventService.window(today: date = None) -> tuple[date, date]` — 上月初 ~ 下下月末
  - `CalendarEventService.refresh_all(today: date = None) -> dict` — `{'collected', 'upserted', 'removed', 'errors'}`
  - `CalendarEventStrategy`，`name='calendar_event'`，`schedule='30 7 * * *'`

**注意**：`app/scheduler/engine.py:23` 读的是策略**类属性** `schedule`，不是 `config.yaml`。本策略不放 `config.yaml`，避免出现一份不生效的重复配置。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_calendar_refresh.py`：

```python
from datetime import date

import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    from app import db
    import app.models.stock_event  # noqa: F401
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def _ev(code, d, source, period_key, etype='earnings'):
    return {
        'event_date': d, 'event_type': etype, 'stock_code': code,
        'stock_name': code, 'market': 'A', 'title': 't', 'detail': None,
        'priority': 'MEDIUM', 'source': source, 'status': 'scheduled',
        'period_key': period_key, 'extra': None,
    }


def test_window_spans_prev_month_to_two_months_ahead():
    from app.services.calendar_event import CalendarEventService
    start, end = CalendarEventService.window(date(2026, 8, 21))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 10, 31)


def test_window_handles_year_boundary():
    from app.services.calendar_event import CalendarEventService
    start, end = CalendarEventService.window(date(2026, 12, 15))
    assert start == date(2026, 11, 1)
    assert end == date(2027, 2, 28)


def test_refresh_all_drops_events_outside_window(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    monkeypatch.setattr(mod, 'collect_earnings_a', lambda today: [
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2027, 3, 1), 'cninfo', '2027A'),
    ])
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['upserted'] == 1
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_refresh_all_one_collector_failure_does_not_block_others(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    def _boom(today):
        raise RuntimeError('cninfo down')

    monkeypatch.setattr(mod, 'collect_earnings_a', _boom)
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [
        _ev('0700.HK', date(2026, 9, 3), 'yfinance', '2026Q3')])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['errors'] and 'cninfo down' in stats['errors'][0]
    assert [r.stock_code for r in StockEvent.query.all()] == ['0700.HK']


def test_refresh_all_failed_collector_does_not_prune_its_own_rows(app_ctx, monkeypatch):
    """cninfo 挂掉时，昨天采到的 cninfo 事件必须原样保留。"""
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')])

    def _boom(today):
        raise RuntimeError('cninfo down')

    monkeypatch.setattr(mod, 'collect_earnings_a', _boom)
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert StockEvent.query.count() == 1


def test_refresh_all_prunes_withdrawn_event(app_ctx, monkeypatch):
    from app.models.stock_event import StockEvent
    from app.services import calendar_event as mod

    mod.CalendarEventService.upsert_events([
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1'),
        _ev('300223', date(2026, 8, 28), 'cninfo', '2026H1'),
    ])

    monkeypatch.setattr(mod, 'collect_earnings_a', lambda today: [
        _ev('002156', date(2026, 8, 29), 'cninfo', '2026H1')])
    monkeypatch.setattr(mod, 'collect_calendar_yf', lambda today: [])
    monkeypatch.setattr(mod, 'collect_dividend_a', lambda today: [])
    monkeypatch.setattr(mod, 'collect_macro_range', lambda s, e: [])

    stats = mod.CalendarEventService.refresh_all(date(2026, 8, 21))

    assert stats['removed'] == 1
    assert [r.stock_code for r in StockEvent.query.all()] == ['002156']


def test_strategy_schedule_is_before_daily_briefing():
    from app.strategies.calendar_event import CalendarEventStrategy
    s = CalendarEventStrategy()
    assert s.name == 'calendar_event'
    assert s.schedule == '30 7 * * *'
    assert s.needs_llm is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_refresh.py -v`
Expected: FAIL，`AttributeError: type object 'CalendarEventService' has no attribute 'window'`

- [ ] **Step 3: 实现 `window` 与 `refresh_all`**

在 `app/services/calendar_event.py` import 区补 `import calendar as _calmod`，常量区补：

```python
# collector -> 它负责的 source 集合（决定 prune 的作用域）
_COLLECTOR_SOURCES = {
    'earnings_a': ['cninfo'],
    'calendar_yf': ['yfinance'],
    'dividend_a': ['akshare'],
    'macro': ['fomc', 'bls'],
}
```

在 `CalendarEventService` 类里加：

```python
    @staticmethod
    def window(today: date = None) -> tuple[date, date]:
        """采集窗口：上月初 ~ 下下月末（比页面展示的双月略宽，避免边界反复增删）"""
        if today is None:
            today = date.today()

        y, m = today.year, today.month
        sy, sm = (y - 1, 12) if m == 1 else (y, m - 1)
        start = date(sy, sm, 1)

        em = m + 2
        ey = y + (em - 1) // 12
        em = (em - 1) % 12 + 1
        end = date(ey, em, _calmod.monthrange(ey, em)[1])

        return start, end

    @staticmethod
    def refresh_all(today: date = None) -> dict:
        """跑全部 collector 并物化。单个 collector 失败不阻断其余，也不清理它自己那类事件。"""
        if today is None:
            today = date.today()

        start, end = CalendarEventService.window(today)

        jobs = [
            ('earnings_a', lambda: collect_earnings_a(today)),
            ('calendar_yf', lambda: collect_calendar_yf(today)),
            ('dividend_a', lambda: collect_dividend_a(today)),
            ('macro', lambda: collect_macro_range(start, end)),
        ]

        events, ok_sources, errors = [], [], []
        for key, fn in jobs:
            try:
                events.extend(fn())
                ok_sources.extend(_COLLECTOR_SOURCES[key])
            except Exception as e:
                errors.append(f'{key}: {e}')
                logger.error(f'[事件日历] collector {key} 失败: {e}')

        in_window = [e for e in events if start <= e['event_date'] <= end]
        ids = CalendarEventService.upsert_events(in_window)
        removed = CalendarEventService.prune_stale(start, end, ids, ok_sources)

        stats = {'collected': len(events), 'upserted': len(ids),
                 'removed': removed, 'errors': errors}
        logger.info(f'[事件日历] 刷新完成: {stats}')
        return stats
```

- [ ] **Step 4: 写策略**

创建 `app/strategies/calendar_event/__init__.py`：

```python
"""事件日历采集策略 — 每日 7:30 物化盯盘股与宏观事件"""
import logging

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class CalendarEventStrategy(Strategy):
    name = "calendar_event"
    description = "事件日历采集（财报/除权/宏观）"
    schedule = "30 7 * * *"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.calendar_event import CalendarEventService

        try:
            stats = CalendarEventService.refresh_all()
            if stats['errors']:
                logger.warning(f'[事件日历] 部分采集失败: {stats["errors"]}')
        except Exception as e:
            logger.error(f'[事件日历] 刷新失败: {e}')

        return []
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_refresh.py -v`
Expected: 7 passed

- [ ] **Step 6: 端到端实跑，直查真实库**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "
import sys; sys.path.insert(0,'.')
from app import create_app
from app.services.calendar_event import CalendarEventService
app = create_app()
with app.app_context():
    print(CalendarEventService.refresh_all())
" > .omc/artifacts/calendar_refresh.log 2>&1; tail -3 .omc/artifacts/calendar_refresh.log
```

再直查库核对（不走 `create_app`）：
```bash
PYTHONIOENCODING=utf-8 python -c "
import sqlite3
c = sqlite3.connect('data/stock.db').cursor()
c.execute('SELECT event_date, event_type, stock_code, stock_name, title, status, source FROM stock_event ORDER BY event_date LIMIT 40')
for r in c.fetchall(): print(r)
c.execute('SELECT source, COUNT(*) FROM stock_event GROUP BY source')
print(dict(c.fetchall()))
"
```
Expected: 至少能看到盯盘 A 股的中报事件（如 `000725` 京东方 2026-08-29、`002156` 通富微电 2026-08-29 且 `status='changed'`），`source` 分布里 `cninfo` 与 `fomc` 均非零。

- [ ] **Step 7: 提交**

```bash
printf '%s\n' "feat(calendar): refresh_all 编排 + 7:30 采集策略" "" "prune 按成功的 collector 的 source 分域执行——某个数据源挂掉时不会连带清空它那类历史事件。" "engine 读的是策略类属性 schedule 而非 config.yaml，故本策略不放 config.yaml。" > .git/MSG.txt && rtk git add app/services/calendar_event.py app/strategies/calendar_event/__init__.py tests/test_calendar_refresh.py && rtk git commit -F .git/MSG.txt
```

---

### Task 6: 路由与 API

**Files:**
- Create: `app/routes/calendar.py`
- Modify: `app/routes/__init__.py`
- Modify: `app/__init__.py:292`
- Test: `tests/test_calendar_api.py`

**Interfaces:**
- Consumes: `CalendarEventService.get_events` / `refresh_all` / `hours_since_refresh`（Task 1、5）
- Produces:
  - `calendar_bp`（`url_prefix='/calendar'`）
  - `GET /calendar/` → `calendar.html`，模板变量 `initial_months: list[dict]`（`{'year', 'month', 'label'}`）
  - `GET /calendar/api/events` → `{'events': [...], 'start': str, 'end': str, 'stale_hours': float | None}`
  - `POST /calendar/api/refresh` → 202 `{'message': str}`
  - `app.routes.calendar.default_range(today: date) -> tuple[date, date]` — 当月 1 号 ~ 下月末

- [ ] **Step 1: 写失败测试**

创建 `tests/test_calendar_api.py`：

```python
from datetime import date

import pytest
from flask import Flask


@pytest.fixture
def client(monkeypatch):
    """只注入 calendar_bp，避免 create_app 拉起 17 个调度任务 + crawl4ai。"""
    from app.routes import calendar_bp
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(calendar_bp)
    with app.test_client() as c:
        yield c


def test_default_range_is_this_month_to_next_month_end():
    from app.routes.calendar import default_range
    start, end = default_range(date(2026, 8, 21))
    assert start == date(2026, 8, 1)
    assert end == date(2026, 9, 30)


def test_default_range_crosses_year():
    from app.routes.calendar import default_range
    start, end = default_range(date(2026, 12, 5))
    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 31)


def test_events_api_uses_default_range_when_no_params(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    seen = {}

    def _fake(start, end):
        seen['range'] = (start, end)
        return []

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_fake))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.5))

    r = client.get('/calendar/api/events')

    assert r.status_code == 200
    body = r.get_json()
    assert body['events'] == []
    assert body['stale_hours'] == 1.5
    assert seen['range'][0].day == 1


def test_events_api_honors_explicit_range(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    seen = {}

    def _fake(start, end):
        seen['range'] = (start, end)
        return [{'event_date': '2026-09-16', 'title': 'FOMC 议息'}]

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_fake))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=2026-09-01&end=2026-09-30')

    assert r.status_code == 200
    assert seen['range'] == (date(2026, 9, 1), date(2026, 9, 30))
    assert r.get_json()['events'][0]['title'] == 'FOMC 议息'


def test_events_api_falls_back_on_bad_date(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=not-a-date&end=2026-09-30')

    assert r.status_code == 200
    assert r.get_json()['start'].endswith('-01')


def test_events_api_rejects_oversized_range(client, monkeypatch):
    from app.services.calendar_event import CalendarEventService
    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: None))

    r = client.get('/calendar/api/events?start=2020-01-01&end=2030-01-01')

    assert r.status_code == 400


def test_refresh_api_returns_202(client, monkeypatch):
    r = client.post('/calendar/api/refresh')
    assert r.status_code == 202
    assert '刷新' in r.get_json()['message']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_api.py -v`
Expected: FAIL，`ImportError: cannot import name 'calendar_bp' from 'app.routes'`

- [ ] **Step 3: 声明 blueprint**

`app/routes/__init__.py`：在 `minerals_bp` 那行之后加

```python
calendar_bp = Blueprint('calendar', __name__, url_prefix='/calendar')
```

并把 `calendar` 追加到文件末尾那条 `from app.routes import ...` 的模块列表里。

- [ ] **Step 4: 写路由**

创建 `app/routes/calendar.py`：

```python
import calendar as _calmod
import logging
from datetime import date, datetime
from threading import Thread

from flask import render_template, request, jsonify, current_app

from app.routes import calendar_bp
from app.services.calendar_event import CalendarEventService

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 200


def default_range(today: date = None) -> tuple[date, date]:
    """当月 1 号 ~ 下月末"""
    if today is None:
        today = date.today()

    start = date(today.year, today.month, 1)
    ey, em = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    end = date(ey, em, _calmod.monthrange(ey, em)[1])
    return start, end


def _parse(value: str):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


@calendar_bp.route('/')
def index():
    start, end = default_range()
    months = [
        {'year': start.year, 'month': start.month,
         'label': f'{start.year}年{start.month}月'},
        {'year': end.year, 'month': end.month,
         'label': f'{end.year}年{end.month}月'},
    ]
    return render_template('calendar.html', initial_months=months)


@calendar_bp.route('/api/events')
def get_events():
    d_start, d_end = default_range()
    start = _parse(request.args.get('start', '')) or d_start
    end = _parse(request.args.get('end', '')) or d_end

    if end < start:
        start, end = d_start, d_end
    if (end - start).days > MAX_RANGE_DAYS:
        return jsonify({'error': f'日期跨度不得超过 {MAX_RANGE_DAYS} 天'}), 400

    try:
        events = CalendarEventService.get_events(start, end)
        stale_hours = CalendarEventService.hours_since_refresh()
    except Exception as e:
        logger.warning(f'[事件日历] 读取失败: {e}')
        events, stale_hours = [], None

    return jsonify({
        'events': events,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'stale_hours': stale_hours,
    })


@calendar_bp.route('/api/refresh', methods=['POST'])
def refresh():
    """异步触发采集"""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            CalendarEventService.refresh_all()

    Thread(target=_run, daemon=True).start()
    return jsonify({'message': '正在刷新，请稍后刷新页面查看'}), 202
```

- [ ] **Step 5: 注册 blueprint**

`app/__init__.py`，在 `app.register_blueprint(minerals_bp)`（第 292 行）之后加：

```python
    app.register_blueprint(calendar_bp)
```

同时把 `calendar_bp` 加进该文件上方从 `app.routes` 导入 bp 的那条 import 列表。

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_api.py -v`
Expected: 7 passed

- [ ] **Step 7: 提交**

```bash
printf '%s\n' "feat(calendar): 新增 /calendar 路由与事件 API" "" "GET /calendar/api/events 默认返回当月+下月，跨度上限 200 天；" "POST /calendar/api/refresh 异步触发采集返回 202。" > .git/MSG.txt && rtk git add app/routes/calendar.py app/routes/__init__.py app/__init__.py tests/test_calendar_api.py && rtk git commit -F .git/MSG.txt
```

---

### Task 7: 双月日历前端

**Files:**
- Create: `app/templates/calendar.html`
- Create: `app/static/js/calendar.js`
- Create: `app/static/css/calendar.css`
- Modify: `app/templates/base.html:25`
- Test: `tests/test_calendar_page_render.py`

**Interfaces:**
- Consumes: `GET /calendar/api/events` 的响应结构（Task 6）；模板变量 `initial_months`
- Produces: 页面本身，无供其他任务调用的接口

- [ ] **Step 1: 写失败测试**

创建 `tests/test_calendar_page_render.py`：

```python
import pytest


def test_calendar_page_renders_two_months(app_client, monkeypatch):
    """渲染 HTML 必须走 create_app —— base.html 跨 blueprint url_for 会 BuildError。"""
    r = app_client.get('/calendar/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert html.count('cal-month') >= 2
    assert 'calendar.js' in html
    assert 'calendar.css' in html


def test_nav_has_calendar_entry(app_client):
    r = app_client.get('/calendar/')
    html = r.get_data(as_text=True)
    assert '/calendar/' in html
    assert '日历' in html
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_page_render.py -v`
Expected: FAIL，404 或 `TemplateNotFound: calendar.html`

- [ ] **Step 3: 写模板**

创建 `app/templates/calendar.html`：

```html
{% extends 'base.html' %}

{% block title %}事件日历{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/calendar.css') }}">
{% endblock %}

{% block content %}
<div class="page-header mb-4">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <h4 class="mb-1"><i class="bi bi-calendar-event"></i> 事件日历</h4>
            <small class="text-muted" id="calStaleInfo">加载中...</small>
        </div>
        <div class="header-actions">
            <button class="btn btn-outline-primary btn-sm" id="calRefreshBtn">
                <i class="bi bi-arrow-clockwise"></i> 刷新数据
            </button>
        </div>
    </div>
</div>

<div class="cal-filters mb-3" id="calTypeFilter">
    <button class="cal-chip is-on" data-type="earnings">财报</button>
    <button class="cal-chip is-on" data-type="ex_dividend">除权除息</button>
    <button class="cal-chip is-on" data-type="macro">宏观</button>
    <button class="cal-chip is-on" data-type="manual">手工</button>
</div>

<div id="calLoading" class="cal-grid">
    {% for m in initial_months %}
    <div class="cal-month">
        <div class="cal-month-title">{{ m.label }}</div>
        <div class="cal-days">
            {% for _ in range(42) %}
            <div class="cal-cell"><div class="skeleton skeleton-text"></div></div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>

<div id="calContainer" class="cal-grid d-none"></div>

<div class="cal-drawer" id="calDrawer">
    <div class="cal-drawer-head">
        <span id="calDrawerTitle"></span>
        <button class="btn-close" id="calDrawerClose" aria-label="关闭"></button>
    </div>
    <div class="cal-drawer-body" id="calDrawerBody"></div>
</div>

<script>
    const INITIAL_MONTHS = {{ initial_months | tojson }};
</script>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/calendar.js') }}"></script>
{% endblock %}
```

- [ ] **Step 4: 写 JS**

创建 `app/static/js/calendar.js`：

```javascript
const CalendarPage = {
    data: { events: [], staleHours: null },
    config: { enabledTypes: new Set(['earnings', 'ex_dividend', 'macro', 'manual']) },

    TYPE_LABEL: {
        earnings: '财报',
        ex_dividend: '除权',
        macro: '宏观',
        manual: '手工',
    },

    init() {
        this.loadConfig();
        this.bindEvents();
        this.fetchData();
    },

    loadConfig() {
        try {
            const saved = JSON.parse(localStorage.getItem('calendarPageConfig'));
            if (saved && Array.isArray(saved.enabledTypes)) {
                this.config.enabledTypes = new Set(saved.enabledTypes);
            }
        } catch (e) { /* ignore */ }
        this.syncChips();
    },

    saveConfig() {
        localStorage.setItem('calendarPageConfig', JSON.stringify({
            enabledTypes: [...this.config.enabledTypes],
        }));
    },

    syncChips() {
        document.querySelectorAll('#calTypeFilter .cal-chip').forEach(btn => {
            btn.classList.toggle('is-on', this.config.enabledTypes.has(btn.dataset.type));
        });
    },

    bindEvents() {
        document.getElementById('calTypeFilter').addEventListener('click', e => {
            const btn = e.target.closest('.cal-chip');
            if (!btn) return;
            const t = btn.dataset.type;
            if (this.config.enabledTypes.has(t)) {
                this.config.enabledTypes.delete(t);
            } else {
                this.config.enabledTypes.add(t);
            }
            this.saveConfig();
            this.syncChips();
            this.render();
        });

        document.getElementById('calRefreshBtn').addEventListener('click', () => {
            fetch('/calendar/api/refresh', { method: 'POST' })
                .then(r => r.json())
                .then(d => { alert(d.message); });
        });

        document.getElementById('calDrawerClose').addEventListener('click', () => {
            document.getElementById('calDrawer').classList.remove('is-open');
        });

        document.getElementById('calContainer').addEventListener('click', e => {
            const cell = e.target.closest('.cal-cell[data-date]');
            if (cell) this.openDrawer(cell.dataset.date);
        });
    },

    fetchData() {
        fetch('/calendar/api/events')
            .then(r => r.json())
            .then(d => {
                this.data.events = d.events || [];
                this.data.staleHours = d.stale_hours;
                this.render();
            })
            .catch(() => {
                document.getElementById('calStaleInfo').textContent = '事件数据加载失败';
            });
    },

    visibleEvents() {
        return this.data.events.filter(e => this.config.enabledTypes.has(e.event_type));
    },

    groupByDate() {
        const map = {};
        this.visibleEvents().forEach(e => {
            (map[e.event_date] = map[e.event_date] || []).push(e);
        });
        return map;
    },

    render() {
        const byDate = this.groupByDate();
        const container = document.getElementById('calContainer');
        container.innerHTML = INITIAL_MONTHS
            .map(m => this.renderMonth(m, byDate)).join('');

        document.getElementById('calLoading').classList.add('d-none');
        container.classList.remove('d-none');
        this.renderStaleInfo();
    },

    renderStaleInfo() {
        const el = document.getElementById('calStaleInfo');
        const h = this.data.staleHours;
        if (h === null || h === undefined) {
            el.textContent = '暂无事件数据，请点击「刷新数据」';
            return;
        }
        el.textContent = h >= 24
            ? `⚠️ 事件数据 ${Math.floor(h)} 小时未更新`
            : `事件数据 ${Math.floor(h)} 小时前更新`;
    },

    renderMonth(m, byDate) {
        const first = new Date(m.year, m.month - 1, 1);
        const daysInMonth = new Date(m.year, m.month, 0).getDate();
        // 周一起始：JS getDay() 周日=0，转成周一=0
        const lead = (first.getDay() + 6) % 7;
        const todayIso = new Date().toLocaleDateString('sv-SE');

        const cells = [];
        for (let i = 0; i < lead; i++) {
            cells.push('<div class="cal-cell is-blank"></div>');
        }
        for (let d = 1; d <= daysInMonth; d++) {
            const iso = `${m.year}-${String(m.month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const evts = byDate[iso] || [];
            cells.push(`
                <div class="cal-cell${iso === todayIso ? ' is-today' : ''}" data-date="${iso}">
                    <div class="cal-daynum">${d}</div>
                    <div class="cal-chips">${this.renderChips(evts)}</div>
                </div>`);
        }

        const heads = ['一', '二', '三', '四', '五', '六', '日']
            .map(w => `<div class="cal-weekhead">${w}</div>`).join('');

        return `
            <div class="cal-month">
                <div class="cal-month-title">${m.label}</div>
                <div class="cal-days">${heads}${cells.join('')}</div>
            </div>`;
    },

    renderChips(evts) {
        const shown = evts.slice(0, 3).map(e => {
            const label = e.stock_name
                ? `${e.stock_name.slice(0, 4)} ${this.TYPE_LABEL[e.event_type] || ''}`
                : e.title;
            const hi = e.priority === 'HIGH' ? ' is-high' : '';
            const tip = this.escape(`${e.title}${e.detail ? ' · ' + e.detail : ''}`);
            return `<span class="cal-ev type-${e.event_type}${hi}" title="${tip}">${this.escape(label)}</span>`;
        }).join('');
        const more = evts.length > 3
            ? `<span class="cal-ev is-more">+${evts.length - 3}</span>` : '';
        return shown + more;
    },

    openDrawer(iso) {
        const evts = this.groupByDate()[iso] || [];
        document.getElementById('calDrawerTitle').textContent = iso;
        document.getElementById('calDrawerBody').innerHTML = evts.length
            ? evts.map(e => `
                <div class="cal-drawer-item type-${e.event_type}">
                    <div class="cal-drawer-item-head">
                        ${e.stock_code
                            ? `<a href="/stocks/${encodeURIComponent(e.stock_code)}">${this.escape(e.stock_name || e.stock_code)} (${this.escape(e.stock_code)})</a>`
                            : this.escape(e.title)}
                    </div>
                    <div class="cal-drawer-item-body">
                        ${this.escape(e.title)}${e.detail ? ' · ' + this.escape(e.detail) : ''}
                    </div>
                </div>`).join('')
            : '<div class="text-muted">当日无事件</div>';
        document.getElementById('calDrawer').classList.add('is-open');
    },

    escape(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g,
            c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },
};

document.addEventListener('DOMContentLoaded', () => CalendarPage.init());
```

- [ ] **Step 5: 写 CSS**

创建 `app/static/css/calendar.css`：

```css
:root {
    --cal-border: rgba(128, 128, 128, 0.25);
    --cal-cell-bg: transparent;
    --cal-today: rgba(13, 110, 253, 0.55);
    --cal-earnings: #3b82f6;
    --cal-dividend: #10b981;
    --cal-macro: #f59e0b;
    --cal-manual: #9ca3af;
}

.cal-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.25rem;
}

@media (max-width: 991.98px) {
    .cal-grid { grid-template-columns: 1fr; }
}

.cal-month-title {
    font-weight: 600;
    margin-bottom: .5rem;
}

.cal-days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
}

.cal-weekhead {
    text-align: center;
    font-size: .75rem;
    opacity: .6;
    padding: 2px 0;
}

.cal-cell {
    min-height: 84px;
    border: 1px solid var(--cal-border);
    border-radius: 4px;
    background: var(--cal-cell-bg);
    padding: 2px 3px;
    cursor: pointer;
    overflow: hidden;
}

.cal-cell.is-blank {
    border: none;
    cursor: default;
}

.cal-cell.is-today {
    border-color: var(--cal-today);
    border-width: 2px;
}

.cal-daynum {
    font-size: .75rem;
    opacity: .7;
}

.cal-chips {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.cal-ev {
    display: block;
    font-size: .7rem;
    line-height: 1.25;
    padding: 1px 4px;
    border-radius: 3px;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.cal-ev.type-earnings { background: var(--cal-earnings); }
.cal-ev.type-ex_dividend { background: var(--cal-dividend); }
.cal-ev.type-macro { background: var(--cal-macro); }
.cal-ev.type-manual { background: var(--cal-manual); }
.cal-ev.is-more { background: transparent; color: inherit; opacity: .6; }
.cal-ev.is-high { border-left: 3px solid rgba(255, 255, 255, .85); }

.cal-filters { display: flex; gap: .5rem; flex-wrap: wrap; }

.cal-chip {
    border: 1px solid var(--cal-border);
    background: transparent;
    color: inherit;
    border-radius: 999px;
    padding: 2px 12px;
    font-size: .8rem;
    opacity: .45;
}

.cal-chip.is-on { opacity: 1; }

.cal-drawer {
    position: fixed;
    top: 0;
    right: 0;
    width: min(360px, 90vw);
    height: 100%;
    background: var(--bs-body-bg, #fff);
    border-left: 1px solid var(--cal-border);
    transform: translateX(100%);
    transition: transform .18s ease;
    z-index: 1050;
    padding: 1rem;
    overflow-y: auto;
}

.cal-drawer.is-open { transform: translateX(0); }

.cal-drawer-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    margin-bottom: .75rem;
}

.cal-drawer-item {
    border-left: 3px solid var(--cal-border);
    padding: .35rem .6rem;
    margin-bottom: .5rem;
}

.cal-drawer-item.type-earnings { border-left-color: var(--cal-earnings); }
.cal-drawer-item.type-ex_dividend { border-left-color: var(--cal-dividend); }
.cal-drawer-item.type-macro { border-left-color: var(--cal-macro); }
.cal-drawer-item.type-manual { border-left-color: var(--cal-manual); }

.cal-drawer-item-body { font-size: .85rem; opacity: .8; }
```

- [ ] **Step 6: 加导航入口**

`app/templates/base.html`，在第 25 行「盯盘」那条 `<a>` 之后插入：

```html
<a class="nav-link" href="{{ url_for('calendar.index') }}">日历</a>
```

- [ ] **Step 7: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_calendar_page_render.py -v > /tmp/cal_render.log 2>&1; grep -E "passed|failed" /tmp/cal_render.log`

（crawl4ai 的进度条走 stdout，直接看输出会被顶掉，所以重定向到文件再 grep。）
Expected: 2 passed

- [ ] **Step 8: 肉眼验一次**

Run: `python run.py`，浏览器打开 `http://127.0.0.1:5000/calendar`
确认：两个月并排；今天的格子有高亮边框；盯盘 A 股的中报事件出现在对应日期；点格子右侧抽屉弹出；关掉「财报」chip 后蓝色 chip 消失；窄化窗口后两个月堆叠为上下。

- [ ] **Step 9: 提交**

```bash
printf '%s\n' "feat(calendar): 双月日历页面（CSS Grid 自研，无新依赖）" "" "周一起始，事件 chip 按类型着色、HIGH 加左侧色条，单格超 3 条折叠为 +N。" "点格子出右侧抽屉；类型过滤存 localStorage。配色走 CSS 变量跟随深色主题。" > .git/MSG.txt && rtk git add app/templates/calendar.html app/static/js/calendar.js app/static/css/calendar.css app/templates/base.html tests/test_calendar_page_render.py && rtk git commit -F .git/MSG.txt
```

---

### Task 8: 每日推送段落

**Files:**
- Modify: `app/services/notification.py:237`（`format_earnings_alerts`）
- Modify: `app/services/notification.py:935`（`build_market_blocks`）
- Modify: `app/services/notification.py:1077`（数据段 blocks 拼装）
- Modify: `app/services/notification.py:1093`（`push_daily_report`）
- Modify: `app/llm/prompts/daily_briefing.py`
- Test: `tests/test_notification_calendar_section.py`

**Interfaces:**
- Consumes: `CalendarEventService.get_events` / `hours_since_refresh`（Task 1）；`WatchService.get_watch_codes()`
- Produces:
  - `NotificationService.format_calendar_events() -> str`（纯文本，空表返回 `''`；与 `format_indices_summary` 等同风格返回 str，不是 dict）
  - `build_market_blocks(..., calendar_text: str = '')`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_notification_calendar_section.py`：

```python
from datetime import date

import pytest


def test_format_calendar_events_empty_returns_blank(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    monkeypatch.setattr(CalendarEventService, 'get_events',
                        staticmethod(lambda start, end: []))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 1.0))

    assert mod.NotificationService.format_calendar_events() == ''


def test_format_calendar_events_db_error_returns_blank(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    def _boom(start, end):
        raise RuntimeError('no such table')

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(_boom))
    assert mod.NotificationService.format_calendar_events() == ''


def test_format_calendar_events_groups_by_date(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    today = date.today()
    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': today.isoformat(), 'event_type': 'earnings',
         'stock_code': '603986', 'stock_name': '兆易创新', 'title': '中报披露',
         'detail': None, 'priority': 'HIGH', 'status': 'confirmed'},
        {'event_date': today.isoformat(), 'event_type': 'ex_dividend',
         'stock_code': '0700.HK', 'stock_name': '腾讯控股', 'title': '除权除息',
         'detail': None, 'priority': 'LOW', 'status': 'scheduled'},
        {'event_date': '2026-09-16', 'event_type': 'macro', 'stock_code': '',
         'stock_name': None, 'title': 'FOMC 议息', 'detail': None,
         'priority': 'HIGH', 'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 2.0))

    text = mod.NotificationService.format_calendar_events()

    assert '📅 未来7天事件' in text
    assert '今天' in text
    assert '兆易创新(603986)' in text
    assert '腾讯控股(0700.HK)' in text
    assert 'FOMC 议息' in text
    assert '未更新' not in text


def test_format_calendar_events_flags_stale_data(monkeypatch):
    from app.services import notification as mod
    from app.services.calendar_event import CalendarEventService

    monkeypatch.setattr(CalendarEventService, 'get_events', staticmethod(lambda s, e: [
        {'event_date': date.today().isoformat(), 'event_type': 'macro',
         'stock_code': '', 'stock_name': None, 'title': 'FOMC 议息',
         'detail': None, 'priority': 'HIGH', 'status': 'scheduled'},
    ]))
    monkeypatch.setattr(CalendarEventService, 'hours_since_refresh',
                        staticmethod(lambda: 30.0))

    text = mod.NotificationService.format_calendar_events()
    assert '⚠️ 事件数据 30 小时未更新' in text


def test_earnings_alerts_excludes_watch_codes(monkeypatch):
    """盯盘股已由日历段覆盖，财报段只报补集，避免同一条消息里重复。"""
    from app.services import notification as mod
    from app.services.earnings import EarningsService
    from app.services.watch_service import WatchService

    monkeypatch.setattr(WatchService, 'get_watch_codes',
                        staticmethod(lambda: ['603986', '0700.HK']))

    seen = {}

    def _fake(codes, days=7):
        seen['codes'] = sorted(codes)
        return []

    monkeypatch.setattr(EarningsService, 'get_upcoming_earnings', staticmethod(_fake))

    mod.NotificationService.format_earnings_alerts(
        codes=['603986', '0700.HK', '600519', '000725'],
        name_map={'603986': '兆易创新', '0700.HK': '腾讯控股',
                  '600519': '贵州茅台', '000725': '京东方A'})

    assert seen['codes'] == ['000725', '600519']


def test_earnings_alerts_no_longer_filters_a_shares(monkeypatch):
    """回归：旧实现用 non_a_codes 剔掉全部 A 股，A 股财报预警长期缺失。"""
    from app.services import notification as mod
    from app.services.earnings import EarningsService
    from app.services.watch_service import WatchService

    monkeypatch.setattr(WatchService, 'get_watch_codes', staticmethod(lambda: []))
    monkeypatch.setattr(EarningsService, 'get_upcoming_earnings',
                        staticmethod(lambda codes, days=7: [
                            {'code': '600519', 'name': '贵州茅台',
                             'earnings_date': '2026-08-25', 'days_until': 4,
                             'is_today': False}]))

    out = mod.NotificationService.format_earnings_alerts(
        codes=['600519'], name_map={'600519': '贵州茅台'})

    assert '贵州茅台(600519)' in out['text']


def test_daily_briefing_prompt_includes_calendar_label():
    from app.llm.prompts.daily_briefing import build_daily_briefing_prompt

    prompt = build_daily_briefing_prompt({
        'calendar_events': '📅 未来7天事件\n  今天  兆易创新(603986) 中报披露',
        'earnings_alerts': '📅 财报提醒（未来7天）\n  贵州茅台(600519) - 4天后',
    })

    assert '【近期事件日历】' in prompt
    assert prompt.index('【近期事件日历】') < prompt.index('【财报提醒】')


def test_build_market_blocks_accepts_calendar_text():
    from app.services.notification import NotificationService

    blocks = NotificationService.build_market_blocks(
        indices_text='', futures_text='', etf_text='', sectors_text='',
        technical_text='', dram_text='', earnings_text='', ai_text='',
        adr_text='', calendar_text='📅 未来7天事件\n  今天  兆易创新(603986) 中报披露')

    dumped = str(blocks)
    assert '未来7天事件' in dumped
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_notification_calendar_section.py -v > /tmp/cal_notify.log 2>&1; grep -E "passed|failed|Error" /tmp/cal_notify.log`
Expected: FAIL，`AttributeError: type object 'NotificationService' has no attribute 'format_calendar_events'`

- [ ] **Step 3: 新增 `format_calendar_events`**

在 `app/services/notification.py` 的 `format_earnings_alerts` 之前插入：

```python
    @staticmethod
    def format_calendar_events(days: int = 7) -> str:
        """未来 N 天事件（读 stock_event 表，采集已由 calendar_event 策略在 7:30 完成）"""
        from datetime import timedelta
        from app.services.calendar_event import CalendarEventService

        try:
            today = date.today()
            events = CalendarEventService.get_events(today, today + timedelta(days=days))
            stale_hours = CalendarEventService.hours_since_refresh()
        except Exception as e:
            logger.warning(f'[通知.事件日历] 读取失败: {e}')
            return ''

        if not events:
            return ''

        header = f'📅 未来{days}天事件'
        if stale_hours is not None and stale_hours >= 24:
            header += f'（⚠️ 事件数据 {int(stale_hours)} 小时未更新）'

        lines = [header]
        last_date = None
        for e in events:
            iso = e['event_date']
            if iso == last_date:
                label = ' ' * 6
            else:
                label = '今天  ' if iso == today.isoformat() else f'{iso[5:]} '
                last_date = iso

            if e['stock_code']:
                subject = f"{e['stock_name'] or e['stock_code']}({e['stock_code']})"
                body = f"{subject} {e['title']}"
            else:
                body = e['title']

            if e.get('detail'):
                body += f" · {e['detail']}"
            elif e.get('status') == 'confirmed':
                body += ' · 已确认'

            lines.append(f'  {label}{body}')

        return '\n'.join(lines)
```

- [ ] **Step 4: 把 `format_earnings_alerts` 降级为补集**

把 `app/services/notification.py:237` 起的函数体前半段替换：

```python
    @staticmethod
    def format_earnings_alerts(codes: list[str] = None, name_map: dict[str, str] = None) -> dict:
        """生成财报日期提醒（未来7天）

        盯盘池的事件已由 format_calendar_events 覆盖，此处只报补集，避免同条消息重复。
        """
        from app.services.earnings import EarningsService
        from app.services.watch_service import WatchService

        if codes is None or name_map is None:
            codes, name_map = NotificationService._get_all_watched_codes()

        watch_codes = set(WatchService.get_watch_codes())
        target_codes = [c for c in codes if c not in watch_codes]

        if not target_codes:
            return {'text': ''}

        upcoming = EarningsService.get_upcoming_earnings(target_codes, days=7)
        if not upcoming:
            return {'text': ''}
        ...
```

（`text = "📅 财报提醒（未来7天）\n"` 及其后的循环原样保留。同时删掉原来的 `from app.utils.market_identifier import MarketIdentifier` 导入与 `non_a_codes` 那两行。）

- [ ] **Step 5: 接入 blocks 与推送链路**

`app/services/notification.py:935` 的 `build_market_blocks` 签名末尾加参数：

```python
                            adr_text: str = '', calendar_text: str = '') -> list:
```

`app/services/notification.py:1077` 那行改为把日历排在最前：

```python
        # 日历 / DRAM / 财报
        extra_texts = [t for t in [calendar_text, dram_text, earnings_text] if t]
```

`push_daily_report` 内，在 `technical_text = ...`（第 1118 行）之后加：

```python
        calendar_text = NotificationService.format_calendar_events()
```

`all_data` 字典（第 1164 行起）里，在 `'earnings_alerts'` 之前加：

```python
                    'calendar_events': calendar_text,
```

msg3 的 `data_lines` 拼装（第 1233 行附近）改为日历在前：

```python
        data_lines = []
        if calendar_text:
            data_lines.append(calendar_text)
        if dram_text:
            data_lines.append(dram_text)
        if earnings.get('text'):
            data_lines.append(earnings['text'])
```

`build_market_blocks` 的调用处（第 1243 行附近）改成关键字传参并补上日历：

```python
        msg3_blocks = NotificationService.build_market_blocks(
            indices_text=indices_text, futures_text=futures_text, etf_text=etf_text,
            sectors_text=sectors_text, technical_text=technical_text,
            dram_text=dram_text, earnings_text=earnings.get('text', ''),
            ai_text=ai_text, adr_text=adr_text, calendar_text=calendar_text)
```

- [ ] **Step 6: 改 GLM prompt**

`app/llm/prompts/daily_briefing.py` 的 `label_map` 中，在 `'earnings_alerts': '财报提醒',` 之前插入：

```python
        'calendar_events': '近期事件日历',
```

并在函数 docstring 的参数列表里补一行 `- calendar_events: 近期事件日历`。

- [ ] **Step 7: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_notification_calendar_section.py tests/test_briefing_earnings_alert.py -v > /tmp/cal_notify.log 2>&1; grep -E "passed|failed" /tmp/cal_notify.log`
Expected: 8 passed（`test_briefing_earnings_alert.py` 若因口径变化而失败，按新语义更新它，并在 commit message 里写明改动理由）

- [ ] **Step 8: 全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/cal_full.log 2>&1; grep -E "passed|failed|ModuleNotFoundError" /tmp/cal_full.log | tail -20`
Expected: 无 failed、无新增 `ModuleNotFoundError`

- [ ] **Step 9: 干跑一次推送文本（不真发）**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "
import sys; sys.path.insert(0,'.')
from app import create_app
from app.services.notification import NotificationService
app = create_app()
with app.app_context():
    open('.omc/artifacts/calendar_push.txt','w',encoding='utf-8').write(
        NotificationService.format_calendar_events() + '\n\n---\n\n' +
        NotificationService.format_earnings_alerts()['text'])
" > /dev/null 2>&1; cat .omc/artifacts/calendar_push.txt
```
Expected: 日历段列出未来 7 天盯盘事件；财报段里**不含**任何 `WATCH_CODES` 里的代码。

- [ ] **Step 10: 提交**

```bash
printf '%s\n' "feat(notification): 每日简报新增「未来7天事件」段落" "" "format_calendar_events 读 stock_event 表（纯读，采集由 7:30 策略完成），" "进 msg3 数据段并作为 calendar_events 喂给 GLM 综合分析。" "" "format_earnings_alerts 降级为补集：排除 WATCH_CODES（已由日历段覆盖），" "并去掉 non_a_codes 过滤——A 股财报日期已在 Task 2 接入巨潮预约披露。" "build_market_blocks 新增 calendar_text 参数，调用处改关键字传参。" > .git/MSG.txt && rtk git add app/services/notification.py app/llm/prompts/daily_briefing.py tests/test_notification_calendar_section.py tests/test_briefing_earnings_alert.py && rtk git commit -F .git/MSG.txt
```

---

## 自查记录

**Spec 覆盖**：§一数据模型→Task 1；§二采集层四个 collector→Task 3、4，`refresh_all`/调度→Task 5；§三页面与 API→Task 6、7；§四推送→Task 8；§五测试→分散在各 Task 的测试文件，与 spec 表格一一对应（`test_calendar_event_model` / `test_calendar_collectors` / `test_calendar_refresh`（对应 spec 的 `test_calendar_refresh_cleanup`）/ `test_calendar_api` / `test_notification_calendar_section`）；§六落地顺序→Task 1-8 顺序一致。

**新增于 spec 之外的两项**（均已在正文说明理由）：
- Task 2（巨潮取数下沉 + 修 `_fetch_earnings_akshare`）——spec 假定「去掉 `non_a_codes` 过滤」即可修好 A 股财报，实际不成立。
- `prune_stale` 增加 `sources` 参数——spec 只说「未命中即删」，但某个 collector 失败时该策略会清空它那一整类历史事件。按成功的 source 分域清理。

**命名一致性**：`period_keys_for_window` / `fetch_disclosure_map` / `_cell_date` 在 Task 2 定义，Task 3 按同名导入；`collect_macro_range(start, end)` 取两个日期参数（不同于其他三个 collector 的 `today`），`refresh_all` 的 jobs 表已按此适配；`format_calendar_events` 返回 str（非 dict），推送链路按 str 使用。
