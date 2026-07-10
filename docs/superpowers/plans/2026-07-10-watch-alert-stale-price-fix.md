# 盯盘告警旧价误报修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 watch_alert 把 yfinance 失败后降级的过期旧价当"当前价"导致的误报（天岳先进 2631.HK "当前 81.50 > 前高 81.40"），并降低取价频率减少失败。

**Architecture:** 两处改动。① `watch_preload` 取价间隔 1→3 分钟，yfinance 调用量降 2/3。② `watch_alert` 改为纯缓存读取（`cache_only=True`，绝不触发 API），并在组装价格时用新静态助手 `_filter_fresh` 过滤掉 `_is_degraded=True` 的降级旧价条目 —— 该股在失败窗口内完全不参与检测、不污染盘中极值，待下次 preload 取到当前时刻真实价才恢复。顺带删除 watch_alert 中从不被消费的 `BENCHMARK_CODES` 死代码。

**Tech Stack:** Python 3.10 / Flask / APScheduler；测试 pytest（`tests/test_*.py` 平铺）。

## Global Constraints

- 所有 git/pytest 命令前加 `rtk`；`git add` 与 `git commit` 放同一条 Bash 命令链（并行 session 抢 index）。
- 单测运行：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <path> -v`。
- 本计划改 `app/` 代码，须在独立 git worktree 内执行（见 Execution Handoff），不直接污染 main。
- 不写多余注释、不写 backup 文件、响应中文。
- `get_realtime_prices` 签名为 `(stock_codes, force_refresh=False, cache_only=False)`；`cache_only=True` 只读内存+DB 缓存、未命中 code 不在返回里、降级过期缓存仍会返回并标 `_is_degraded=True`。

---

### Task 1: watch_preload 降频至 3 分钟

**Files:**
- Modify: `app/strategies/watch_preload/__init__.py:13`
- Test: `tests/test_watch_preload_schedule.py`

**Interfaces:**
- Consumes: 无
- Produces: 无（仅改类属性 `WatchPreloadStrategy.schedule`）

- [ ] **Step 1: 写失败测试**

新建 `tests/test_watch_preload_schedule.py`：

```python
"""watch_preload 取价间隔降频至 3 分钟"""
from app.strategies.watch_preload import WatchPreloadStrategy


def test_preload_schedule_is_3_minutes():
    assert WatchPreloadStrategy.schedule == 'interval_minutes:3'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_schedule.py -v`
Expected: FAIL — `assert 'interval_minutes:1' == 'interval_minutes:3'`

- [ ] **Step 3: 改 schedule**

`app/strategies/watch_preload/__init__.py` 第 13 行：

```python
    schedule = "interval_minutes:3"
```

（原为 `"interval_minutes:1"`）

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_schedule.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
rtk git add app/strategies/watch_preload/__init__.py tests/test_watch_preload_schedule.py && rtk git commit -m "perf(watch_preload): 取价间隔1→3分钟降低yfinance失败率

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 新增 `_filter_fresh` 静态助手过滤降级旧价

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py`（在 `WatchAlertStrategy` 类内新增静态方法）
- Test: `tests/test_watch_alert_filter_fresh.py`

**Interfaces:**
- Consumes: 无
- Produces: `WatchAlertStrategy._filter_fresh(prices: dict, active_codes: list[str]) -> dict` —— 返回 `{code: price_dict}`，仅含 active_codes 中命中 prices 且 `price_dict.get('_is_degraded')` 为假的条目。Task 3 消费它。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_watch_alert_filter_fresh.py`：

```python
"""_filter_fresh 剔除降级旧价(_is_degraded)与未命中条目"""
from app.strategies.watch_alert import WatchAlertStrategy


def test_drops_degraded_entry():
    prices = {
        'a': {'current_price': 10.0},
        'b': {'current_price': 81.5, '_is_degraded': True},
    }
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'])
    assert result == {'a': {'current_price': 10.0}}


def test_drops_missing_code():
    result = WatchAlertStrategy._filter_fresh({'a': {'current_price': 10.0}}, ['a', 'b'])
    assert set(result) == {'a'}


def test_ignores_inactive_codes():
    prices = {'a': {'current_price': 10.0}, 'x': {'current_price': 5.0}}
    result = WatchAlertStrategy._filter_fresh(prices, ['a'])
    assert set(result) == {'a'}


def test_keeps_all_fresh():
    prices = {'a': {'current_price': 10.0}, 'b': {'current_price': 20.0}}
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'])
    assert result == prices
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_filter_fresh.py -v`
Expected: FAIL — `AttributeError: type object 'WatchAlertStrategy' has no attribute '_filter_fresh'`

- [ ] **Step 3: 新增静态方法**

在 `app/strategies/watch_alert/__init__.py` 的 `WatchAlertStrategy` 类内（放在 `_load_alert_params` 方法之前、`scan` 方法之后即可）新增：

```python
    @staticmethod
    def _filter_fresh(prices: dict, active_codes: list[str]) -> dict:
        """只保留活跃股中命中缓存且非降级(_is_degraded)的实时价"""
        return {c: prices[c] for c in active_codes
                if c in prices and not prices[c].get('_is_degraded')}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_filter_fresh.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 提交**

```bash
rtk git add app/strategies/watch_alert/__init__.py tests/test_watch_alert_filter_fresh.py && rtk git commit -m "feat(watch_alert): _filter_fresh 静态助手剔除降级旧价条目

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: scan() 接线 —— cache_only 读价 + 过滤降级 + 删 BENCHMARK 死代码

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py:28`（删 import）、`:45-61`（scan 取价段）
- Test: `tests/test_watch_alert_scan_wiring.py`

**Interfaces:**
- Consumes: `WatchAlertStrategy._filter_fresh`（Task 2）
- Produces: 无

- [ ] **Step 1: 写失败测试**

新建 `tests/test_watch_alert_scan_wiring.py`（沿用 `test_watch_alert_trading_minutes.py` 的 `inspect.getsource` 源码断言模式，避免 create_app 副作用）：

```python
"""scan() 用 cache_only 读价、过滤降级、删除 BENCHMARK 死代码"""
import inspect

from app.strategies.watch_alert import WatchAlertStrategy


def test_scan_uses_cache_only():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert 'cache_only=True' in src


def test_scan_calls_filter_fresh():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert '_filter_fresh' in src


def test_scan_has_no_benchmark_dead_code():
    src = inspect.getsource(WatchAlertStrategy.scan)
    assert 'BENCHMARK_CODES' not in src
    assert 'bench_codes' not in src


def test_module_no_benchmark_import():
    import app.strategies.watch_alert as mod
    src = inspect.getsource(mod)
    assert 'BENCHMARK_CODES' not in src
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_scan_wiring.py -v`
Expected: FAIL — `cache_only=True` / `_filter_fresh` 不在源码，且 `BENCHMARK_CODES` 仍在

- [ ] **Step 3a: 删除 BENCHMARK_CODES import（第 28 行）**

删掉 `scan()` 内这一行：

```python
        from app.config.stock_codes import BENCHMARK_CODES
```

- [ ] **Step 3b: 改写 scan 取价段（原 45-61 行）**

将原代码：

```python
        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()

        bench_codes = [b['code'] for b in BENCHMARK_CODES]
        all_codes = list(set(active_codes + bench_codes))

        a_codes = [c for c in all_codes if MarketIdentifier.is_a_share(c)]
        other_codes = [c for c in all_codes if c not in a_codes]

        # 价格由 watch_preload 每分钟 force_refresh 预取，这里直接读缓存
        prices = {}
        if a_codes:
            prices.update(data_service.get_realtime_prices(a_codes))
        if other_codes:
            prices.update(data_service.get_realtime_prices(other_codes))

        watch_prices = {c: prices[c] for c in active_codes if c in prices}
```

替换为：

```python
        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()

        a_codes = [c for c in active_codes if MarketIdentifier.is_a_share(c)]
        other_codes = [c for c in active_codes if c not in a_codes]

        # 价格由 watch_preload 每3分钟 force_refresh 预取，这里只读缓存(cache_only，绝不触发API)
        prices = {}
        if a_codes:
            prices.update(data_service.get_realtime_prices(a_codes, cache_only=True))
        if other_codes:
            prices.update(data_service.get_realtime_prices(other_codes, cache_only=True))

        # 取价失败降级返回的过期旧价(_is_degraded)会污染极值并误报，直接跳过该股
        watch_prices = self._filter_fresh(prices, active_codes)
        skipped = [c for c in active_codes if c in prices and c not in watch_prices]
        if skipped:
            logger.info(f'[盯盘告警] 跳过{len(skipped)}只降级旧价: {skipped}')
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_scan_wiring.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > .omc/artifacts/pytest_watch_alert.txt 2>&1; rtk grep -E "passed|failed|error" .omc/artifacts/pytest_watch_alert.txt | tail -5`
Expected: 全绿，无新增 failed/error（crawl4ai 进度条走 stdout，故重定向到文件再 grep）

- [ ] **Step 6: 提交**

```bash
rtk git add app/strategies/watch_alert/__init__.py tests/test_watch_alert_scan_wiring.py && rtk git commit -m "fix(watch_alert): cache_only读价+跳过降级旧价，删BENCHMARK死代码

失败降级旧价不再当当前价比对/污染盘中极值(天岳2631.HK误报根因)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage：**
- 改动 1（preload 1→3min）→ Task 1 ✅
- 改动 2a（cache_only 读价）→ Task 3 Step 3b ✅
- 改动 2b（过滤 `_is_degraded`）→ Task 2（助手）+ Task 3（接线）✅
- 删 BENCHMARK 死代码 → Task 3 ✅
- 验证（降级跳过 / 正常检测 / preload schedule 值 / 回归）→ Task 1/2/3 测试 ✅
- 不改 `check_alerts` 检测逻辑、保留退避/冷却/去重/TD 节流 → 三个 Task 均未触及这些 ✅

**Placeholder scan：** 无 TBD/TODO；所有代码步骤含完整代码。

**Type consistency：** `_filter_fresh(prices, active_codes)` 签名在 Task 2 定义、Task 3 以 `self._filter_fresh(prices, active_codes)` 调用，一致。`cache_only=True` 与 Global Constraints 中 `get_realtime_prices` 签名一致。
