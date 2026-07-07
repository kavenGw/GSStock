# watch_alert 港股午休修复 + watch_preload 限流退避 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复港股午休（12:00–13:00）期间 watch_alert 仍推送告警的 bug，并给 watch_preload 增加按市场的限流退避。

**Architecture:** 在 `TradingCalendarService` 引入 `MARKET_SESSIONS` 作为分时段交易时间的单一权威源，`is_market_open` 与 `watch_alert._calc_trading_minutes` 都消费它；`watch_preload` 价格预取改为按市场分组调用，失败时该市场指数退避（1→2→4→8 tick 封顶），成功即恢复。

**Tech Stack:** Python / Flask 策略插件（APScheduler 调度）、exchange_calendars、pytest。

## Global Constraints

- 所有 git / pytest 命令加 `rtk` 前缀；env 赋值必须在 `rtk` 之前（如 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`）
- 单测平铺在 `tests/test_*.py`，不建子目录；测试不走 `create_app()`（本计划的测试均不需要）
- 不写多余注释；不写 backup 文件
- commit：`git add <精确路径> && git commit` 放同一条命令链；message 末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 本计划改 `app/` 代码 → 按仓库分支策略在独立 git worktree 中执行（superpowers:using-git-worktrees）
- 无新增环境变量，无需同步 CLAUDE.md / README / .env.sample

---

### Task 1: TradingCalendarService.MARKET_SESSIONS + is_market_open 港股午休

**Files:**
- Modify: `app/services/trading_calendar.py`（类常量区 ~L46 后新增；`is_market_open` L203-242 改写）
- Test: `tests/test_trading_calendar_sessions.py`（新建）

**Interfaces:**
- Produces: 类常量 `TradingCalendarService.MARKET_SESSIONS: dict[str, list[tuple[time, time]]]`，含 `'A'` / `'HK'` / `'JP'` 三键，值为 `[(开盘time, 收盘time), ...]` 两段时段列表。Task 2 依赖此常量。
- `is_market_open(market: str, dt: datetime = None) -> bool` 签名不变，行为变化仅：HK 在 12:00–13:00 返回 False。

- [ ] **Step 1: Write the failing tests**

新建 `tests/test_trading_calendar_sessions.py`：

```python
"""交易时段判断：港股/A股/日股午休，美股连续时段"""
from datetime import datetime

from app.services.trading_calendar import TradingCalendarService


def _dt(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm)


# 2026-07-06 周一，沪/港/东京/纽约均为交易日
class TestHKLunchBreak:
    def test_hk_lunch_1211_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 12, 11)) is False

    def test_hk_1159_open(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 11, 59)) is True

    def test_hk_1301_open(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 13, 1)) is True

    def test_hk_0929_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 9, 29)) is False

    def test_hk_1601_closed(self):
        assert TradingCalendarService.is_market_open('HK', _dt(2026, 7, 6, 16, 1)) is False


class TestExistingMarketsRegression:
    def test_a_share_lunch_closed(self):
        assert TradingCalendarService.is_market_open('A', _dt(2026, 7, 6, 12, 0)) is False

    def test_a_share_morning_open(self):
        assert TradingCalendarService.is_market_open('A', _dt(2026, 7, 6, 10, 0)) is True

    def test_jp_lunch_closed(self):
        assert TradingCalendarService.is_market_open('JP', _dt(2026, 7, 6, 12, 0)) is False

    def test_jp_afternoon_open(self):
        assert TradingCalendarService.is_market_open('JP', _dt(2026, 7, 6, 13, 0)) is True

    def test_us_midday_open(self):
        assert TradingCalendarService.is_market_open('US', _dt(2026, 7, 6, 12, 0)) is True


def test_market_sessions_constant_shape():
    sessions = TradingCalendarService.MARKET_SESSIONS
    assert set(sessions) == {'A', 'HK', 'JP'}
    for market, pairs in sessions.items():
        assert len(pairs) == 2
        for s_open, s_close in pairs:
            assert s_open < s_close
```

说明：`is_market_open` 对 naive datetime 会 `tz.localize` 到市场本地时区，直接传 naive 时间即表示该市场本地时间。

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_trading_calendar_sessions.py -v`
Expected: `test_hk_lunch_1211_closed` FAIL（当前返回 True）、`test_market_sessions_constant_shape` FAIL（AttributeError: MARKET_SESSIONS）；其余回归用例 PASS。

- [ ] **Step 3: Implement MARKET_SESSIONS and rewrite is_market_open**

`app/services/trading_calendar.py`，在 `MARKET_TIMEZONES` 定义之后（L46 附近）新增类常量：

```python
    # 分时段交易市场（含午休）；不在此表的市场用 MARKET_HOURS 单一时段
    MARKET_SESSIONS = {
        'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
        'HK': [(time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))],
        'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
    }
```

`is_market_open`（L203-242）中删除 A/JP 两段硬编码 if，改为：

```python
        current_time = dt.time()

        sessions = cls.MARKET_SESSIONS.get(market)
        if sessions:
            return any(s_open <= current_time <= s_close for s_open, s_close in sessions)

        return open_time <= current_time <= close_time
```

（`open_time, close_time = cls.get_market_hours(...)` 与 `if open_time is None: return False` 保留原样，位于上述代码之前。）

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_trading_calendar_sessions.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/trading_calendar.py tests/test_trading_calendar_sessions.py && rtk git commit -m "fix(watch): 港股午休 12:00-13:00 判为休市，MARKET_SESSIONS 收敛分时段权威源

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: watch_alert._calc_trading_minutes 复用 MARKET_SESSIONS

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py:157-161`（删除本地 `SESSIONS` 字典）
- Test: `tests/test_watch_alert_trading_minutes.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `TradingCalendarService.MARKET_SESSIONS`（`_calc_trading_minutes` 的 `calendar_service` 参数即 `TradingCalendarService` 类，直接取其属性）。
- `_calc_trading_minutes(codes, market_map, calendar_service) -> dict[str, dict]` 签名与返回结构 `{code: {'elapsed': int, 'total': int}}` 不变。

- [ ] **Step 1: Write the failing test**

新建 `tests/test_watch_alert_trading_minutes.py`：

```python
"""_calc_trading_minutes 复用 TradingCalendarService.MARKET_SESSIONS"""
from datetime import datetime, time

from app.strategies.watch_alert import WatchAlertStrategy


class FakeCalendar:
    MARKET_SESSIONS = {
        'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
        'HK': [(time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))],
        'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
    }

    def __init__(self, now):
        self._now = now

    def get_market_now(self, market):
        return self._now

    def get_market_hours(self, market, dt):
        return (time(9, 30), time(16, 0))


def _calc(now, code, market):
    cal = FakeCalendar(now)
    return WatchAlertStrategy._calc_trading_minutes([code], {code: market}, cal)[code]


def test_hk_lunch_elapsed_frozen_at_150():
    assert _calc(datetime(2026, 7, 6, 12, 11), '2476.HK', 'HK') == {'elapsed': 150, 'total': 330}


def test_hk_afternoon_1330_elapsed_180():
    assert _calc(datetime(2026, 7, 6, 13, 30), '2476.HK', 'HK') == {'elapsed': 180, 'total': 330}


def test_a_share_lunch_elapsed_frozen_at_120():
    assert _calc(datetime(2026, 7, 6, 12, 30), '600519', 'A') == {'elapsed': 120, 'total': 240}


def test_no_local_sessions_dict():
    import inspect
    src = inspect.getsource(WatchAlertStrategy._calc_trading_minutes)
    assert 'SESSIONS = {' not in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_trading_minutes.py -v`
Expected: `test_no_local_sessions_dict` FAIL（当前源码含本地 `SESSIONS = {`）；前三个用例 PASS（现有逻辑正确，此处是回归护栏）。

- [ ] **Step 3: Remove the local SESSIONS dict**

`app/strategies/watch_alert/__init__.py` `_calc_trading_minutes` 内，删除：

```python
        SESSIONS = {
            'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
            'HK': [(time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))],
            'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
        }
```

并把 `sessions = SESSIONS.get(market)` 改为：

```python
            sessions = calendar_service.MARKET_SESSIONS.get(market)
```

删除 SESSIONS 后 `time` 在该文件无其他引用（`now_dt.time()` 是方法调用，不是 `datetime.time` 类），把顶部 `from datetime import datetime, time` 改为 `from datetime import datetime`。

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_trading_minutes.py tests/test_trading_calendar_sessions.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
rtk git add app/strategies/watch_alert/__init__.py tests/test_watch_alert_trading_minutes.py && rtk git commit -m "refactor(watch): _calc_trading_minutes 复用 MARKET_SESSIONS，消除双份时段表

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: watch_preload 按市场限流退避

**Files:**
- Modify: `app/strategies/watch_preload/__init__.py`
- Test: `tests/test_watch_preload_backoff.py`（新建）

**Interfaces:**
- Produces（策略内部方法，测试直接消费）：
  - `WatchPreloadStrategy._should_skip(market: str) -> bool` — 该市场处于退避剩余 tick 时返回 True 并递减
  - `WatchPreloadStrategy._record_result(market: str, ok: bool) -> None` — 成功清退避；失败 skip 翻倍（初始 1，封顶 8）
  - `WatchPreloadStrategy._prices_ok(prices: dict, codes: list[str]) -> bool` — 有效价（`current_price` 非 None 非 0）占比 ≥ 50%
  - 类属性 `_backoff: dict[str, dict]`，条目 `{'skip': int, 'remaining': int}`

- [ ] **Step 1: Write the failing tests**

新建 `tests/test_watch_preload_backoff.py`：

```python
"""watch_preload 按市场限流退避状态机"""
import pytest

from app.strategies.watch_preload import WatchPreloadStrategy


@pytest.fixture
def strategy():
    WatchPreloadStrategy._backoff = {}
    return WatchPreloadStrategy()


def test_no_backoff_initially(strategy):
    assert strategy._should_skip('HK') is False


def test_first_failure_skips_one_tick(strategy):
    strategy._record_result('HK', ok=False)
    assert strategy._should_skip('HK') is True
    assert strategy._should_skip('HK') is False


def test_consecutive_failures_double_capped_at_8(strategy):
    for expected_skip in (1, 2, 4, 8, 8):
        strategy._record_result('HK', ok=False)
        assert strategy._backoff['HK']['skip'] == expected_skip
        strategy._backoff['HK']['remaining'] = 0


def test_success_clears_backoff(strategy):
    strategy._record_result('HK', ok=False)
    strategy._record_result('HK', ok=True)
    assert 'HK' not in strategy._backoff
    assert strategy._should_skip('HK') is False


def test_markets_independent(strategy):
    strategy._record_result('HK', ok=False)
    assert strategy._should_skip('A') is False
    assert strategy._should_skip('HK') is True


def test_prices_ok_threshold():
    codes = ['a', 'b', 'c', 'd']
    good = {'current_price': 10.0}
    assert WatchPreloadStrategy._prices_ok({'a': good, 'b': good}, codes) is True
    assert WatchPreloadStrategy._prices_ok({'a': good}, codes) is False
    assert WatchPreloadStrategy._prices_ok(
        {'a': good, 'b': {'current_price': None}, 'c': {'current_price': 0}}, codes) is False


def test_prices_ok_empty_codes():
    assert WatchPreloadStrategy._prices_ok({}, []) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_backoff.py -v`
Expected: FAIL，`AttributeError: ... has no attribute '_should_skip'` 等。

- [ ] **Step 3: Implement backoff in watch_preload**

`app/strategies/watch_preload/__init__.py`：类属性区加 `_backoff`，新增三个方法，并把 scan 中价格预取段改为按市场分组：

```python
BACKOFF_CAP = 8


class WatchPreloadStrategy(Strategy):
    name = "watch_preload"
    description = "盯盘数据预取（每分钟价格+分时，每15分钟走势）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _tick_count = 0
    _backoff = {}

    def _should_skip(self, market: str) -> bool:
        state = self._backoff.get(market)
        if state and state['remaining'] > 0:
            state['remaining'] -= 1
            return True
        return False

    def _record_result(self, market: str, ok: bool):
        if ok:
            if self._backoff.pop(market, None):
                logger.info(f'[盯盘预取] {market} 取价恢复，退避清零')
            return
        prev = self._backoff.get(market)
        skip = min(prev['skip'] * 2, BACKOFF_CAP) if prev else 1
        self._backoff[market] = {'skip': skip, 'remaining': skip}
        logger.warning(f'[盯盘预取] {market} 取价失败，退避 {skip} tick')

    @staticmethod
    def _prices_ok(prices: dict, codes: list[str]) -> bool:
        if not codes:
            return True
        valid = sum(1 for c in codes if (prices.get(c) or {}).get('current_price'))
        return valid >= len(codes) * 0.5
```

scan 中把原来的整体价格预取：

```python
        # 每次预取价格
        try:
            unified_stock_data_service.get_realtime_prices(active_codes, force_refresh=True)
            logger.debug(f'[盯盘预取] 价格预取完成: {len(active_codes)}只')
        except Exception as e:
            logger.error(f'[盯盘预取] 价格预取失败: {e}')
```

替换为按市场分组 + 退避：

```python
        # 每次按市场预取价格，失败市场指数退避（yfinance 限流不连累腾讯源）
        for market, m_codes in market_codes.items():
            if self._should_skip(market):
                continue
            try:
                prices = unified_stock_data_service.get_realtime_prices(m_codes, force_refresh=True)
                ok = self._prices_ok(prices, m_codes)
                if ok:
                    logger.debug(f'[盯盘预取] {market} 价格预取完成: {len(m_codes)}只')
            except Exception as e:
                logger.error(f'[盯盘预取] {market} 价格预取失败: {e}')
                ok = False
            self._record_result(market, ok)
```

A 股分时预取与走势预取两段保持不变。

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_backoff.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
rtk git add app/strategies/watch_preload/__init__.py tests/test_watch_preload_backoff.py && rtk git commit -m "feat(watch): watch_preload 按市场限流退避（1→2→4→8 tick 封顶，成功即恢复）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 全量回归

**Files:**
- 无新改动；只跑全量测试确认无回归。

- [ ] **Step 1: Run full test suite**

Run:

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ > .omc/artifacts/pytest_watch_lunch.txt 2>&1; grep -E "passed|failed|error" .omc/artifacts/pytest_watch_lunch.txt
```

（crawl4ai 进度条走 stdout，必须重定向到文件再 grep，勿用管道 tail。）
Expected: 输出含 `N passed`，无 `failed` / `error`。若有失败：仅修复由本计划引入的失败；与本计划无关的既有失败记录并汇报，不擅自修。

- [ ] **Step 2: 汇报结果**

无需 commit（Task 1–3 已各自提交）。汇报全量测试结果与三个 commit SHA。
