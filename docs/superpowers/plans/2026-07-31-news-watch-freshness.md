# news_watch 价格新鲜度闸门 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 盯盘链路（告警 / AI 实时分析 / 实时推送）宁可不推送也不推非实时价格：超过 2 倍 preload 刷新周期（A 股 2 分钟、非 A 6 分钟）或降级的价一律拦下只记日志。

**Architecture:** 新增纯函数模块 `app/services/price_freshness.py` 作为唯一闸门定义（基于价格 dict 自带的 `last_fetch_time` ISO 时间戳判年龄），三个消费点各自调用：`watch_alert._filter_fresh`、`WatchAnalysisService.analyze_stocks` 的 realtime 分支、`NotificationService.push_realtime_analysis`。数据层 `UnifiedStockDataService` 语义不动。

**Tech Stack:** Python / Flask 服务层纯函数 + pytest（平铺 `tests/test_*.py`，不走 `create_app`）。

**Spec:** `docs/superpowers/specs/2026-07-31-news-watch-freshness-design.md`

## Global Constraints

- **执行前先建独立 git worktree**（本计划改 `app/` 代码，按仓库分支策略不得直接在 main 动手）；worktree 内 git 命令必须 `git -C <worktree路径>` 或确认 cwd
- 所有 git / pytest 命令前加 `rtk`；env 赋值必须在 `rtk` 之前：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`
- `git add` 与 `git commit` 放同一条命令链（并行 session 抢 index）；中文多行 commit message 写入文件后 `git commit -F`，不用 heredoc
- 不留 backup 文件、不留兼容 shim；删除的 helper 先全仓 grep importer
- `last_fetch_time` 为 `datetime.now().isoformat()` 产生的 naive local 时间戳，比较一律用 naive `datetime.now()`，不引入时区
- 阈值为写死常量（A 股 120s、其余 360s = 2 × preload 周期），不做环境变量
- 7d/30d 分析与每日简报**不加门**（范围外）
- 闸门纯函数本身不 log，被拦日志由调用方记；不向 Slack 频道推降级提醒

---

### Task 1: `price_freshness` 纯函数模块（含 `_price_age_seconds` 迁移收编）

**Files:**
- Create: `app/services/price_freshness.py`
- Create: `tests/test_price_freshness.py`
- Modify: `app/routes/watch.py:11-18`（删本地 `_price_age_seconds`，改 import）、`app/routes/watch.py:59`（调用点）
- Delete: `tests/test_watch_prices_age.py`（被新测试完全覆盖）

**Interfaces:**
- Consumes: 价格 dict 约定字段 `current_price` / `last_fetch_time`(ISO str) / `_is_degraded`(bool, 可缺失)
- Produces（后续 Task 2/3/4 依赖，签名以此为准）:
  - `max_age_seconds(market: str) -> int` — `'A'` → 120，其余（含空串）→ 360
  - `price_age_seconds(data: dict, now: datetime = None) -> int | None` — 缺失/乱格式返回 None
  - `is_fresh(price_data: dict, market: str, now: datetime = None) -> bool` — fail-closed：无 `current_price` / `_is_degraded` / 无法算年龄 / 超龄 均为 False
  - `filter_fresh_prices(prices: dict, market_map: dict, now: datetime = None) -> dict` — 返回只含新鲜价的子集；market_map 缺 code 按非 A 兜底

- [ ] **Step 1: 写失败测试**

创建 `tests/test_price_freshness.py`：

```python
"""价格新鲜度闸门纯函数单测"""
from datetime import datetime, timedelta

from app.services.price_freshness import (
    max_age_seconds, price_age_seconds, is_fresh, filter_fresh_prices,
)


def _p(age_seconds=0, **overrides):
    data = {
        'current_price': 10.0,
        'last_fetch_time': (datetime.now() - timedelta(seconds=age_seconds)).isoformat(),
    }
    data.update(overrides)
    return data


def test_max_age_by_market():
    assert max_age_seconds('A') == 120
    assert max_age_seconds('US') == 360
    assert max_age_seconds('HK') == 360
    assert max_age_seconds('') == 360


def test_a_share_fresh_within_2min():
    assert is_fresh(_p(age_seconds=110), 'A')


def test_a_share_stale_beyond_2min():
    assert not is_fresh(_p(age_seconds=130), 'A')


def test_non_a_fresh_within_6min():
    assert is_fresh(_p(age_seconds=350), 'US')


def test_non_a_stale_beyond_6min():
    assert not is_fresh(_p(age_seconds=370), 'HK')


def test_degraded_rejected_even_if_recent():
    assert not is_fresh(_p(age_seconds=5, _is_degraded=True), 'A')


def test_missing_fetch_time_rejected():
    assert not is_fresh({'current_price': 10.0}, 'A')


def test_garbage_fetch_time_rejected():
    assert not is_fresh({'current_price': 10.0, 'last_fetch_time': 'not-a-date'}, 'A')


def test_missing_price_rejected():
    assert not is_fresh(_p(age_seconds=5, current_price=None), 'A')


def test_filter_mixed_markets():
    prices = {
        'a_fresh': _p(100), 'a_stale': _p(180),
        'us_fresh': _p(180), 'us_stale': _p(400),
    }
    market_map = {'a_fresh': 'A', 'a_stale': 'A', 'us_fresh': 'US', 'us_stale': 'US'}
    assert set(filter_fresh_prices(prices, market_map)) == {'a_fresh', 'us_fresh'}


def test_filter_unknown_market_uses_non_a_default():
    assert set(filter_fresh_prices({'x': _p(300)}, {})) == {'x'}
    assert set(filter_fresh_prices({'x': _p(400)}, {})) == set()


def test_price_age_seconds():
    ts = (datetime.now() - timedelta(seconds=90)).isoformat()
    assert 85 <= price_age_seconds({'last_fetch_time': ts}) <= 95
    assert price_age_seconds({}) is None
    assert price_age_seconds({'last_fetch_time': 'garbage'}) is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_price_freshness.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.price_freshness'`

- [ ] **Step 3: 实现模块**

创建 `app/services/price_freshness.py`：

```python
"""盯盘价格新鲜度闸门 — 纯函数，宁可不推也不推旧价"""
from datetime import datetime

FRESHNESS_MULTIPLIER = 2
PRELOAD_INTERVAL_MINUTES = {'A': 1}   # 其余市场默认 3，对应 watch_preload NON_A_REFRESH_EVERY
DEFAULT_INTERVAL_MINUTES = 3


def max_age_seconds(market: str) -> int:
    interval = PRELOAD_INTERVAL_MINUTES.get(market, DEFAULT_INTERVAL_MINUTES)
    return interval * FRESHNESS_MULTIPLIER * 60


def price_age_seconds(data: dict, now: datetime = None):
    ts = data.get('last_fetch_time')
    if not ts:
        return None
    try:
        fetched = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    return int(((now or datetime.now()) - fetched).total_seconds())


def is_fresh(price_data: dict, market: str, now: datetime = None) -> bool:
    if not price_data or not price_data.get('current_price'):
        return False
    if price_data.get('_is_degraded'):
        return False
    age = price_age_seconds(price_data, now)
    if age is None:
        return False
    return age <= max_age_seconds(market)


def filter_fresh_prices(prices: dict, market_map: dict, now: datetime = None) -> dict:
    now = now or datetime.now()
    return {c: d for c, d in prices.items() if is_fresh(d, market_map.get(c, ''), now)}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_price_freshness.py -v`
Expected: 12 passed

- [ ] **Step 5: 迁移收编 routes 里的重复 helper**

先确认 `_price_age_seconds` 无其他 importer：

```bash
rtk grep -rn "_price_age_seconds" app/ tests/
```

Expected: 仅 `app/routes/watch.py`（定义 + 1 处调用）与 `tests/test_watch_prices_age.py`。

修改 `app/routes/watch.py`：删除第 11-18 行的 `_price_age_seconds` 函数定义，第 6 行 import 区加：

```python
from app.services.price_freshness import price_age_seconds
```

第 59 行调用点 `'age_seconds': _price_age_seconds(data),` 改为：

```python
                'age_seconds': price_age_seconds(data),
```

（`datetime` import 若仅被该 helper 使用则一并清理；`watch.py` 其他地方若仍用则保留。）

- [ ] **Step 6: 跑全量测试确认无回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > pytest_out.txt 2>&1; rtk grep -E "passed|failed|error" pytest_out.txt; rm pytest_out.txt`
Expected: 除 `tests/test_watch_prices_age.py` 因旧 import 失败外无新增失败（baseline 39 failed 既有，与本改动无关；下一步删除该文件）

- [ ] **Step 7: 删除冗余测试并提交**

写 commit message 到 `.git/MSG.txt`（内容如下），然后同一条链提交：

```
feat(watch): 新增价格新鲜度闸门纯函数模块

price_freshness.py：基于 last_fetch_time 判年龄（A股120s/非A 360s
= 2倍preload周期），_is_degraded/缺时间戳/无价 fail-closed。
收编 routes/watch.py 的 _price_age_seconds，删除被覆盖的旧测试。
```

```bash
rtk git rm -q tests/test_watch_prices_age.py && rtk git add app/services/price_freshness.py tests/test_price_freshness.py app/routes/watch.py && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

---

### Task 2: `watch_alert` 告警层接入

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py:56-61`（scan 内过滤与日志）、`:88-92`（`_filter_fresh`）
- Modify: `tests/test_watch_alert_filter_fresh.py`（整文件重写，适配三参签名 + 年龄判定）
- Modify: `tests/test_watch_alert_scan_wiring.py:29-46`（`test_degraded_price_excluded_end_to_end` 适配新签名）

**Interfaces:**
- Consumes: Task 1 的 `filter_fresh_prices(prices, market_map)` / `price_age_seconds(data)`
- Produces: `WatchAlertStrategy._filter_fresh(prices: dict, active_codes: list[str], market_map: dict) -> dict`（签名从两参改三参）

- [ ] **Step 1: 重写失败测试**

`tests/test_watch_alert_filter_fresh.py` 整文件替换为：

```python
"""_filter_fresh 剔除降级/超龄旧价与未命中条目"""
from datetime import datetime, timedelta

from app.strategies.watch_alert import WatchAlertStrategy

MM = {'a': 'A', 'b': 'A', 'h': 'HK'}


def _p(age_seconds=0, **overrides):
    data = {'current_price': 10.0,
            'last_fetch_time': (datetime.now() - timedelta(seconds=age_seconds)).isoformat()}
    data.update(overrides)
    return data


def test_drops_degraded_entry():
    prices = {'a': _p(), 'b': _p(_is_degraded=True)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)) == {'a'}


def test_drops_stale_a_share_beyond_2min():
    prices = {'a': _p(), 'b': _p(age_seconds=180)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)) == {'a'}


def test_keeps_hk_within_6min():
    prices = {'h': _p(age_seconds=180)}
    assert set(WatchAlertStrategy._filter_fresh(prices, ['h'], MM)) == {'h'}


def test_drops_entry_without_fetch_time():
    prices = {'a': {'current_price': 10.0}}
    assert WatchAlertStrategy._filter_fresh(prices, ['a'], MM) == {}


def test_drops_missing_code_and_ignores_inactive():
    prices = {'a': _p(), 'x': _p()}
    result = WatchAlertStrategy._filter_fresh(prices, ['a', 'b'], MM)
    assert set(result) == {'a'}
```

同时改 `tests/test_watch_alert_scan_wiring.py` 的 `test_degraded_price_excluded_end_to_end`（其余 4 个测试不动）：

```python
def test_degraded_price_excluded_end_to_end():
    """降级旧价(_is_degraded)经 _filter_fresh 后既不产生信号也不污染盘中极值"""
    from datetime import datetime
    from app.strategies.watch_alert import WatchAlertStrategy
    from app.services.watch_alert_service import WatchAlertService

    prices = {
        'FRESH': {'current_price': 10.0, 'last_fetch_time': datetime.now().isoformat()},
        '2631.HK': {'current_price': 81.5, '_is_degraded': True,
                    'last_fetch_time': datetime.now().isoformat()},
    }
    watch_prices = WatchAlertStrategy._filter_fresh(
        prices, ['FRESH', '2631.HK'], {'FRESH': 'A', '2631.HK': 'HK'})

    service = WatchAlertService()
    service._intraday_extremes = {}
    service._last_trading_date = None
    signals = service.check_alerts(watch_prices, {'FRESH': 'Fresh', '2631.HK': '天岳'})

    assert '2631.HK' not in service._intraday_extremes
    assert all(s.data.get('stock_code') != '2631.HK' for s in signals)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_filter_fresh.py tests/test_watch_alert_scan_wiring.py -v`
Expected: FAIL — `TypeError: _filter_fresh() takes 2 positional arguments but 3 were given`

- [ ] **Step 3: 实现**

`app/strategies/watch_alert/__init__.py` 第 56-61 行改为：

```python
        # 取价失败降级(_is_degraded)或超龄(2倍preload周期)的旧价会污染极值并误报，直接跳过该股
        watch_prices = self._filter_fresh(prices, active_codes, market_map)
        skipped = [c for c in active_codes if c in prices and c not in watch_prices]
        if skipped:
            from app.services.price_freshness import price_age_seconds
            detail = [f"{c}(age={price_age_seconds(prices[c])}s)" for c in skipped]
            logger.info(f'[盯盘告警] 跳过{len(skipped)}只降级/超龄旧价: {detail}')
```

第 88-92 行 `_filter_fresh` 改为：

```python
    @staticmethod
    def _filter_fresh(prices: dict, active_codes: list[str], market_map: dict) -> dict:
        """只保留活跃股中命中缓存、非降级且未超龄(2倍preload周期)的实时价"""
        from app.services.price_freshness import filter_fresh_prices
        return filter_fresh_prices(
            {c: prices[c] for c in active_codes if c in prices}, market_map)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_filter_fresh.py tests/test_watch_alert_scan_wiring.py -v`
Expected: 10 passed

- [ ] **Step 5: 提交**

`.git/MSG.txt`：

```
feat(watch): watch_alert 告警接入价格新鲜度闸门

_filter_fresh 从只查 _is_degraded 升级为降级+超龄双检查（三参
签名含 market_map），preload 挂掉/退避期间告警自动静默，恢复
刷新后自动复活。被拦股票记日志含数据年龄。
```

```bash
rtk git add app/strategies/watch_alert/__init__.py tests/test_watch_alert_filter_fresh.py tests/test_watch_alert_scan_wiring.py && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

---

### Task 3: `analyze_stocks` realtime 分析层接入

**Files:**
- Modify: `app/services/watch_analysis_service.py:77`（取价后加门）
- Create: `tests/test_watch_realtime_freshness_gate.py`

**Interfaces:**
- Consumes: Task 1 的 `filter_fresh_prices` / `price_age_seconds`；`WatchService.get_market_map() -> dict`（已存在）
- Produces: 无新接口。行为变更：realtime 分支中超龄/降级价的股不进 LLM 分析，落入既有 `if not current_price` 跳过分支 → `failed_codes`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_watch_realtime_freshness_gate.py`：

```python
"""analyze_stocks realtime 分支：超龄旧价的股跳过 LLM 分析不入库"""
from datetime import datetime, timedelta

from app.services.watch_analysis_service import WatchAnalysisService
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service
from app.llm.router import llm_router


class FakeProvider:
    def __init__(self):
        self.called_for = []

    def chat(self, messages, max_tokens=500):
        self.called_for.append(max_tokens)
        return '{"signal": "hold", "summary": "s", "support_levels": [], "resistance_levels": []}'


def _run(monkeypatch, prices):
    codes = list(prices)
    intraday = {'stocks': [{'stock_code': c, 'data': [{'time': '09:30', 'price': 1.0}]}
                           for c in codes]}
    monkeypatch.setattr(WatchService, 'get_watch_codes', staticmethod(lambda: codes))
    monkeypatch.setattr(WatchService, 'get_market_map',
                        staticmethod(lambda: {c: 'A' for c in codes}))
    monkeypatch.setattr(WatchService, 'get_all_today_analyses', staticmethod(lambda: {}))
    saved = []
    monkeypatch.setattr(WatchService, 'save_analysis',
                        staticmethod(lambda **kw: saved.append(kw['stock_code'])))
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                        lambda c, **kw: prices)
    monkeypatch.setattr(unified_stock_data_service, 'get_trend_data',
                        lambda c, days: {'stocks': []})
    monkeypatch.setattr(unified_stock_data_service, 'get_intraday_data',
                        lambda c, **kw: intraday)
    monkeypatch.setattr(llm_router, 'route', lambda name: FakeProvider())
    WatchAnalysisService.analyze_stocks('realtime')
    return saved


def test_stale_price_skips_llm_analysis(monkeypatch):
    prices = {
        'FRESH': {'current_price': 10.0, 'name': 'F',
                  'last_fetch_time': datetime.now().isoformat()},
        'STALE': {'current_price': 20.0, 'name': 'S',
                  'last_fetch_time': (datetime.now() - timedelta(minutes=10)).isoformat()},
    }
    assert _run(monkeypatch, prices) == ['FRESH']


def test_degraded_price_skips_llm_analysis(monkeypatch):
    prices = {
        'FRESH': {'current_price': 10.0, 'name': 'F',
                  'last_fetch_time': datetime.now().isoformat()},
        'DEGRADED': {'current_price': 20.0, 'name': 'D', '_is_degraded': True,
                     'last_fetch_time': datetime.now().isoformat()},
    }
    assert _run(monkeypatch, prices) == ['FRESH']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_realtime_freshness_gate.py -v`
Expected: FAIL — `saved == ['FRESH', 'STALE']`（旧代码不拦超龄价）

- [ ] **Step 3: 实现**

`app/services/watch_analysis_service.py` 第 77 行 `raw_prices = ...` 之后插入：

```python
        if is_realtime:
            from app.services.price_freshness import filter_fresh_prices, price_age_seconds
            fresh_prices = filter_fresh_prices(raw_prices, WatchService.get_market_map())
            stale = [c for c in raw_prices if c not in fresh_prices]
            if stale:
                detail = [f"{c}(age={price_age_seconds(raw_prices[c])}s)" for c in stale]
                logger.warning(f'[盯盘AI] realtime 跳过{len(stale)}只降级/超龄旧价: {detail}')
            raw_prices = fresh_prices
```

被拦的 code 在后续循环里 `raw_prices.get(code, {})` 得空 dict → 落入既有 `if not current_price` 分支 → `failed_codes`，无需其他改动。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_realtime_freshness_gate.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

`.git/MSG.txt`：

```
feat(watch): watch_realtime AI 分析接入价格新鲜度闸门

realtime 分支取价后过滤降级/超龄旧价（force_refresh 失败降级
返回的昨日价被拦），该股跳过 LLM 分析省调用；7d/30d 日级分析
不加门。
```

```bash
rtk git add app/services/watch_analysis_service.py tests/test_watch_realtime_freshness_gate.py && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

---

### Task 4: `push_realtime_analysis` 推送层接入

**Files:**
- Modify: `app/services/notification.py:460-462`（取价改 cache_only + 过滤）、`:479-536`（循环内跳过无新鲜价的股、简化现价行）
- Create: `tests/test_push_realtime_freshness.py`

**Interfaces:**
- Consumes: Task 1 的 `filter_fresh_prices`；`WatchService.get_watch_list()` 每条含 `market` 字段（已存在）
- Produces: 无新接口。行为变更：推送块仅由"有新鲜价"的股组成；现价行必现（不再有无价分支）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_push_realtime_freshness.py`：

```python
"""push_realtime_analysis：cache_only 取价 + 无新鲜价的股整块不推"""
from datetime import datetime, timedelta

from app.services.notification import NotificationService
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service

ANALYSES = {
    '600519': {'realtime': {'signal': 'buy', 'summary': 'sum-fresh',
                            'support_levels': [10.0], 'resistance_levels': [20.0]}},
    '0700.HK': {'realtime': {'signal': 'sell', 'summary': 'sum-stale',
                             'support_levels': [1.0], 'resistance_levels': [2.0]}},
}
WATCH_LIST = [
    {'stock_code': '600519', 'stock_name': '茅台', 'market': 'A'},
    {'stock_code': '0700.HK', 'stock_name': '腾讯', 'market': 'HK'},
]


def _setup(monkeypatch, prices):
    NotificationService._realtime_push_state = {'date': None, 'stocks': {}}
    monkeypatch.setattr(WatchService, 'get_watch_list', staticmethod(lambda: WATCH_LIST))
    calls = {}

    def fake_prices(codes, **kwargs):
        calls['kwargs'] = kwargs
        return prices

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    sent = []
    monkeypatch.setattr(NotificationService, 'send_slack',
                        staticmethod(lambda msg, channel=None, blocks=None:
                                     sent.append(msg) or True))
    return calls, sent


def test_stale_stock_block_not_pushed(monkeypatch):
    prices = {
        '600519': {'current_price': 1800.0, 'change_percent': 1.2,
                   'last_fetch_time': datetime.now().isoformat()},
        '0700.HK': {'current_price': 500.0, 'change_percent': -0.5,
                    'last_fetch_time': (datetime.now() - timedelta(minutes=10)).isoformat()},
    }
    calls, sent = _setup(monkeypatch, prices)
    NotificationService.push_realtime_analysis(ANALYSES)
    joined = '\n'.join(sent)
    assert '600519' in joined and '1800.0' in joined
    assert '0700.HK' not in joined and 'sum-stale' not in joined


def test_uses_cache_only_read(monkeypatch):
    prices = {'600519': {'current_price': 1800.0, 'change_percent': 1.2,
                         'last_fetch_time': datetime.now().isoformat()}}
    calls, sent = _setup(monkeypatch, prices)
    NotificationService.push_realtime_analysis(ANALYSES)
    assert calls['kwargs'].get('cache_only') is True


def test_all_stale_pushes_nothing(monkeypatch):
    old = (datetime.now() - timedelta(minutes=30)).isoformat()
    prices = {
        '600519': {'current_price': 1800.0, 'last_fetch_time': old},
        '0700.HK': {'current_price': 500.0, 'last_fetch_time': old},
    }
    calls, sent = _setup(monkeypatch, prices)
    result = NotificationService.push_realtime_analysis(ANALYSES)
    assert sent == []
    assert result is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_push_realtime_freshness.py -v`
Expected: FAIL — 旧代码超龄股照推（`'0700.HK' in joined`）、`cache_only` 未传

- [ ] **Step 3: 实现**

`app/services/notification.py` `push_realtime_analysis` 内，第 460-462 行改为：

```python
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.price_freshness import filter_fresh_prices
        all_codes = [c for c, p in analyses.items() if p.get('realtime')]
        raw_prices = unified_stock_data_service.get_realtime_prices(
            all_codes, cache_only=True) if all_codes else {}
        market_map = {w['stock_code']: w['market'] for w in watch_list}
        raw_prices = filter_fresh_prices(raw_prices, market_map)
```

循环前（`full_blocks = []` 处）加 `stale_skipped = []`；循环内 `if not data: continue` 之后插入：

```python
            if code not in raw_prices:
                stale_skipped.append(code)
                continue
```

`price_data = raw_prices.get(code, {})` 改为 `price_data = raw_prices[code]`（闸门保证存在且 `current_price` 真值）。首推块第 509-518 行的无价 `else` 分支删除、`if current_price is not None:` 守卫去掉（`change_pct` 的 None 判断保留）：

```python
            if is_first:
                lines = [f"{signal} {name}({code})"]
                arrow = '▲' if (change_pct or 0) >= 0 else '▼'
                pct_str = f"({change_pct:+.2f}%)" if change_pct is not None else ''
                lines.append(f"  现价 {current_price} {arrow}{pct_str} | 支撑 {sup_str} | 压力 {res_str}")
                lines.append(f"  💡 {summary}")
                full_blocks.append("\n".join(lines))
```

更新块第 526-529 行同理去掉 `if current_price is not None:` 守卫（内容行保留）。循环结束后、`sent = False` 之前加：

```python
        if stale_skipped:
            logger.info(f'[盯盘实时] 推送跳过{len(stale_skipped)}只降级/超龄旧价: {stale_skipped}')
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_push_realtime_freshness.py -v`
Expected: 3 passed

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > pytest_out.txt 2>&1; rtk grep -E "passed|failed|error" pytest_out.txt; rm pytest_out.txt`
Expected: 无新增 failed/error（baseline 39 failed 既有，与本改动无关）

- [ ] **Step 6: 提交**

`.git/MSG.txt`：

```
feat(watch): push_realtime_analysis 推送层接入价格新鲜度闸门

取价改 cache_only（内存读，preload 持续刷新期间拿到的即最新价）
+ 同一闸门过滤；无新鲜价的股整块不推（原先无价也照推支撑/压力
行）。现价行改为必现，删除无价分支死代码。
```

```bash
rtk git add app/services/notification.py tests/test_push_realtime_freshness.py && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

---

## 完成定义

- 4 个 commit 全部落地，全量 pytest 无新增失败
- 人工验证（可选）：盘中观察 `news_watch` 频道，preload 正常时推送照常；手动停掉 preload（或断网）2 分钟后告警/分析/推送静默，日志出现 `跳过N只降级/超龄旧价`
- 更新 `.claude/rules/notifications.md` 与 `watch.md` 不在本计划内——实现合并后按 docs 约定由维护者决定是否补充（闸门行为已有 spec 留痕）
