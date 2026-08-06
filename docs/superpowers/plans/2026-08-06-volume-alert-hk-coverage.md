# volume_alert 扩展至港股 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让收盘成交量异动策略覆盖盯盘池里的 12 只港股（当前只扫 8 只 A 股），并在推送中标注成交量单位、显示中文名。

**Architecture:** 把 `VolumeAlertStrategy._do_scan` 里写死的 `is_a_share` 过滤改为基于 `WatchService.get_market_map()` 的按市场分组，并对每个市场独立调用 `TradingCalendarService.is_trading_day`。展示层从 `unified_stock_data` 导入新增的 `CONTRACT_VOLUME_UNIT` 常量拼单位后缀，股票名走 `WATCH_CODES` 兜底。取数仍是单次批量调用，`UnifiedStockDataService` 内部已按市场路由数据源。

**Tech Stack:** Python 3.10 / Flask / APScheduler / pytest（纯 mock，无联网）

## Global Constraints

- 设计文档：`docs/superpowers/specs/2026-08-06-volume-alert-hk-coverage-design.md`
- 覆盖市场仅 `A` 与 `HK`，不含 US/KR/JP/TW
- 阈值 `VOLUME_CHANGE_THRESHOLD = 0.3` 两市场共用，不引入分市场参数
- 两道 sanity gate（`ratio > 30 or ratio < 1/30`、`today_vol < avg_5d * 0.01`）逻辑一字不改
- cron 维持 `30 16 * * 1-5`，不新增 job
- 契约单位：A 股「手」、港股「股」、美股「股」
- 单位事实只允许在 `app/services/unified_stock_data.py` 定义一处，策略层 import 使用，禁止另写字典
- 所有测试走 mock，不得联网
- 改的是 `app/` 代码，按 `.claude/rules/dev-environment.md` 分支策略必须在独立 git worktree 中进行，不在 main 直接改
- **worktree 中 `.git` 是文件不是目录**，`git commit -F .git/MSG.txt` 必然失败，commit message 用多个 `-m` 参数
- 测试命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`
- 所有 git/pytest 命令前加 `rtk`

## 前置：worktree

开工前用 `superpowers:using-git-worktrees` 从 main 创建隔离 worktree（分支名建议 `volume-alert-hk`）。下文 git 命令中的 `<worktree路径>` 一律替换为该 worktree 的绝对路径。

创建后立即执行 `git -C <worktree路径> merge --ff-only main`——`EnterWorktree` 从 origin 分叉，不做这步会缺少 main 上的最新 commit。

## 与设计文档的两处偏离

**其一：市场判定用 `get_market_map()` 而非 `MarketIdentifier`。**

Spec 第一节写的是用 `MarketIdentifier.identify(c)` 判市场。实施改用 `WatchService.get_market_map()`：

- `WATCH_CODES` 里每条都显式写死 `market` 字段，是权威源
- `.claude/rules/watch.md` 明确警告 `MarketIdentifier` 不认 `.KS` 等后缀会误判，盯盘池才要显式写 market
- 少一个 import，且与 `WatchService` 已有 API 对齐

行为在 A/HK 上完全等价（两者对 `600584` / `9992.HK` 判断一致），但对未来新增市场更稳。

**其二：`missing_codes` 错误推送的取名方式一并改掉。**

Spec 第六节写「`missing_codes` 的错误推送文案不变」。文案格式确实不变（仍是 `重试仍缺失今日数据: A, B`），但取名逻辑必须改：原实现从 `trend['stocks']` 反查 `stock_name`，港股场景下拿到的仍是代码。改为直接用 `name_map` 映射（见 Task 3 Step 3 其五）。

## File Structure

| 文件 | 责任 | 改动 |
|---|---|---|
| `app/services/unified_stock_data.py` | volume 单位事实的唯一定义处 | 新增 `CONTRACT_VOLUME_UNIT` 常量（约 10 行，紧邻 `VOLUME_SOURCE_UNITS`） |
| `app/strategies/volume_alert/__init__.py` | 收盘成交量异动扫描与信号构造 | 改 `_do_scan` 的市场过滤、交易日判断、name/unit 拼装 |
| `tests/test_volume_alert_unit_consistency.py` | 单位契约 + 策略行为回归 | 改造 `strategy_deps` fixture，新增第 7 节测试 |

无新建文件。三个任务共 3 次 commit。

---

### Task 1: 新增 CONTRACT_VOLUME_UNIT 契约单位常量

**Files:**
- Modify: `app/services/unified_stock_data.py`（在 `VOLUME_SOURCE_UNITS` 字典定义结束后、`def _normalize_volume` 之前插入）
- Test: `tests/test_volume_alert_unit_consistency.py`（第 1 节「单位归一化源码契约锁定」末尾，`test_all_registered_units_are_valid` 之后追加）

**Interfaces:**
- Consumes: 无
- Produces: `CONTRACT_VOLUME_UNIT: dict[str, str]`，从 `app.services.unified_stock_data` 导出。键为市场代码字符串（`'A'` / `'HK'` / `'US'`），值为中文单位标签（`'手'` / `'股'`）。Task 3 会 import 它。

- [ ] **Step 1: 写失败的测试**

在 `tests/test_volume_alert_unit_consistency.py` 中，把第 21 行的 import 改为：

```python
from app.services.unified_stock_data import (
    VOLUME_SOURCE_UNITS,
    CONTRACT_VOLUME_UNIT,
    _normalize_volume,
)
```

然后在 `test_all_registered_units_are_valid` 函数之后追加：

```python
def test_contract_volume_unit_labels():
    """契约单位标签：A 股为「手」，港美股为「股」"""
    assert CONTRACT_VOLUME_UNIT['A'] == '手'
    assert CONTRACT_VOLUME_UNIT['HK'] == '股'
    assert CONTRACT_VOLUME_UNIT['US'] == '股'


def test_contract_unit_matches_normalize_semantics():
    """契约标签与 _normalize_volume 的行为必须自洽：
    标「手」的市场，shares 源要被 //100；标「股」的市场，任何源都原样。
    这条防止日后有人只改标签不改归一逻辑（或反之）。
    """
    for market, label in CONTRACT_VOLUME_UNIT.items():
        raw = 1234567
        normalized = _normalize_volume(raw, 'sina_daily', market)
        if label == '手':
            assert normalized == raw // 100, f'{market} 标「手」但 shares 源未 //100'
        else:
            assert normalized == raw, f'{market} 标「股」但 shares 源被转换了'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: 收集阶段就 FAIL —— `ImportError: cannot import name 'CONTRACT_VOLUME_UNIT' from 'app.services.unified_stock_data'`（整个文件的测试都会报错，这是预期的）

- [ ] **Step 3: 写实现**

在 `app/services/unified_stock_data.py` 中，`VOLUME_SOURCE_UNITS` 字典的闭合大括号之后、`def _normalize_volume(...)` 之前插入：

```python
# 各市场 volume 契约单位的展示标签。
# 与 _normalize_volume 的转换规则同源：标「手」的市场，shares 源会被 //100。
# 展示层（如 volume_alert 推送）必须 import 此表，禁止自行硬编码单位字符串。
CONTRACT_VOLUME_UNIT = {
    'A': '手',
    'HK': '股',
    'US': '股',
}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: 全部 PASS（含原有 16 个测试 + 新增 2 个）

- [ ] **Step 5: Commit**

```bash
git -C <worktree路径> add app/services/unified_stock_data.py tests/test_volume_alert_unit_consistency.py
git -C <worktree路径> commit -m "feat(volume): 新增 CONTRACT_VOLUME_UNIT 契约单位标签表" -m "展示层需要的「手/股」标签与归一层同源，避免二源分歧。" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 按市场分组扫描 + 逐市场判交易日

**Files:**
- Modify: `app/strategies/volume_alert/__init__.py`（模块常量区、`VolumeAlertStrategy.description`、`_do_scan` 开头至取数调用）
- Test: `tests/test_volume_alert_unit_consistency.py`（改造 `strategy_deps` fixture；在第 3 节末尾、`test_sanity_gate_accepts_normal_anomaly` 之后追加新测试）

**Interfaces:**
- Consumes: 无（不依赖 Task 1）
- Produces: `_do_scan` 内部产生局部变量 `codes`（`list[str]`，含 A 股与港股代码）、`market_map`（`dict[str, str]`，代码到市场）。Task 3 会复用 `market_map` 拼单位后缀。模块级新增常量 `SUPPORTED_MARKETS: set[str] = {'A', 'HK'}`。

- [ ] **Step 1: 改造 fixture 支持多市场**

现有 `strategy_deps` fixture 的 `FakeMI` 只有 `is_a_share`，且 `FakeCal.is_trading_day` 恒为 True，无法表达市场分组与交易日分歧。把 `tests/test_volume_alert_unit_consistency.py` 中整个 `strategy_deps` fixture（第 150-188 行）替换为：

```python
@pytest.fixture
def strategy_deps(monkeypatch):
    """通用 mock 工厂：可配置 trend/realtime/市场归属/各市场交易日开关"""

    class _Stub:
        trend = {'stocks': []}
        realtime = {}
        markets = None          # {code: 'A'|'HK'}，None 时全部按 'A'
        names = None            # {code: name}，None 时从 trend 的 stock_name 推
        trading_days = None     # {'A': True, 'HK': True}，None 时全部 True
        requested_codes = []    # 记录实际传给取数层的代码，供断言

    stub = _Stub()

    def _codes():
        return [s['stock_code'] for s in stub.trend.get('stocks', [])]

    def _market_map():
        if stub.markets is not None:
            return dict(stub.markets)
        return {c: 'A' for c in _codes()}

    def fake_get_watch_codes():
        return _codes()

    def fake_get_watch_list():
        names = stub.names or {}
        mm = _market_map()
        out = []
        for i, s in enumerate(stub.trend.get('stocks', []), 1):
            code = s['stock_code']
            out.append({
                'id': i,
                'stock_code': code,
                'stock_name': names.get(code, s.get('stock_name', code)),
                'market': mm.get(code, 'A'),
                'added_at': None,
            })
        return out

    class FakeUSD:
        def __init__(self):
            pass

        def get_trend_data(self, codes, days=5, force_refresh=False):
            stub.requested_codes = list(codes)
            wanted = set(codes)
            return {'stocks': [s for s in stub.trend.get('stocks', [])
                               if s['stock_code'] in wanted]}

        def get_realtime_prices(self, codes, force_refresh=False):
            wanted = set(codes)
            return {k: v for k, v in stub.realtime.items() if k in wanted}

    class FakeCal:
        @staticmethod
        def is_trading_day(market, today):
            if stub.trading_days is None:
                return True
            return stub.trading_days.get(market, False)

    monkeypatch.setattr('app.services.watch_service.WatchService.get_watch_codes',
                        fake_get_watch_codes, raising=False)
    monkeypatch.setattr('app.services.watch_service.WatchService.get_watch_list',
                        fake_get_watch_list, raising=False)
    monkeypatch.setattr('app.services.watch_service.WatchService.get_market_map',
                        _market_map, raising=False)
    monkeypatch.setattr('app.services.trading_calendar.TradingCalendarService',
                        FakeCal, raising=False)
    monkeypatch.setattr('app.services.unified_stock_data.UnifiedStockDataService',
                        FakeUSD, raising=False)

    return stub
```

注意：`FakeMI` 已删除——新实现不再依赖 `MarketIdentifier`。`get_trend_data` / `get_realtime_prices` 现在按传入的 codes 过滤，这样「某市场被交易日闸拦掉」才能在结果里体现出来。

- [ ] **Step 2: 写失败的测试**

在 `tests/test_volume_alert_unit_consistency.py` 的 `test_sanity_gate_accepts_normal_anomaly` 之后追加：

```python
# ============ 7. 多市场覆盖 ============

def test_hk_stock_produces_signal(strategy_deps):
    """回归本次缺陷：港股此前被 is_a_share 过滤，从未产出过信号。
    数值取自 2026-08-06 泡泡玛特真实行情。
    """
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('9992.HK', '9992.HK',
                              [7000000, 6500000, 8381789, 6638049, 19505349], today_str)]
    }
    strategy_deps.realtime = {'9992.HK': {'volume': 19505149, 'change_pct': -2.54}}
    strategy_deps.markets = {'9992.HK': 'HK'}
    strategy_deps.names = {'9992.HK': '泡泡玛特'}

    signals = VolumeAlertStrategy()._do_scan()

    assert len(signals) == 1
    assert signals[0].data['stock_code'] == '9992.HK'
    assert signals[0].data['volume_change_pct'] > 1.9      # (19505349-6638049)/6638049 ≈ 1.94


def test_both_markets_scanned_together(strategy_deps):
    """A 股与港股在同一次扫描中各自产出信号"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [
            _make_ohlc('600584', '长电科技', [1400000, 1500000, 1435993, 1761053, 2359071], today_str),
            _make_ohlc('9992.HK', '9992.HK', [7000000, 6500000, 8381789, 6638049, 19505349], today_str),
        ]
    }
    strategy_deps.realtime = {
        '600584': {'volume': 2359071, 'change_pct': 10.0},
        '9992.HK': {'volume': 19505149, 'change_pct': -2.54},
    }
    strategy_deps.markets = {'600584': 'A', '9992.HK': 'HK'}
    strategy_deps.names = {'600584': '长电科技', '9992.HK': '泡泡玛特'}

    signals = VolumeAlertStrategy()._do_scan()

    assert {s.data['stock_code'] for s in signals} == {'600584', '9992.HK'}


def test_hk_survives_a_share_holiday(strategy_deps):
    """A 股休市但港股开市时，港股仍被扫描——修复原先 is_trading_day('A') 提前 return 的连坐"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [
            _make_ohlc('600584', '长电科技', [1400000, 1500000, 1435993, 1761053, 2359071], today_str),
            _make_ohlc('9992.HK', '9992.HK', [7000000, 6500000, 8381789, 6638049, 19505349], today_str),
        ]
    }
    strategy_deps.realtime = {
        '600584': {'volume': 2359071, 'change_pct': 10.0},
        '9992.HK': {'volume': 19505149, 'change_pct': -2.54},
    }
    strategy_deps.markets = {'600584': 'A', '9992.HK': 'HK'}
    strategy_deps.names = {'600584': '长电科技', '9992.HK': '泡泡玛特'}
    strategy_deps.trading_days = {'A': False, 'HK': True}

    signals = VolumeAlertStrategy()._do_scan()

    assert [s.data['stock_code'] for s in signals] == ['9992.HK']
    assert strategy_deps.requested_codes == ['9992.HK'], \
        'A 股休市时不应把 A 股代码送进取数层'


def test_a_survives_hk_holiday(strategy_deps):
    """反向：港股休市（如佛诞）时 A 股照常扫描"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [
            _make_ohlc('600584', '长电科技', [1400000, 1500000, 1435993, 1761053, 2359071], today_str),
            _make_ohlc('9992.HK', '9992.HK', [7000000, 6500000, 8381789, 6638049, 19505349], today_str),
        ]
    }
    strategy_deps.realtime = {
        '600584': {'volume': 2359071, 'change_pct': 10.0},
        '9992.HK': {'volume': 19505149, 'change_pct': -2.54},
    }
    strategy_deps.markets = {'600584': 'A', '9992.HK': 'HK'}
    strategy_deps.trading_days = {'A': True, 'HK': False}

    signals = VolumeAlertStrategy()._do_scan()

    assert [s.data['stock_code'] for s in signals] == ['600584']


def test_all_markets_closed_returns_empty_without_fetching(strategy_deps):
    """两市场均休市：返回空且不发起任何取数"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600584', '长电科技',
                              [1400000, 1500000, 1435993, 1761053, 2359071], today_str)]
    }
    strategy_deps.realtime = {'600584': {'volume': 2359071, 'change_pct': 10.0}}
    strategy_deps.markets = {'600584': 'A'}
    strategy_deps.trading_days = {'A': False, 'HK': False}
    strategy_deps.requested_codes = ['sentinel']

    signals = VolumeAlertStrategy()._do_scan()

    assert signals == []
    assert strategy_deps.requested_codes == ['sentinel'], '休市日不应调用取数层'


def test_unsupported_market_excluded(strategy_deps):
    """美股/韩股在盯盘池里但不在覆盖范围内，不得进入扫描"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [
            _make_ohlc('600584', '长电科技', [1400000, 1500000, 1435993, 1761053, 2359071], today_str),
            _make_ohlc('005930.KS', '三星电子', [1000, 1000, 1000, 1000, 5000], today_str),
        ]
    }
    strategy_deps.realtime = {
        '600584': {'volume': 2359071, 'change_pct': 10.0},
        '005930.KS': {'volume': 5000, 'change_pct': 3.0},
    }
    strategy_deps.markets = {'600584': 'A', '005930.KS': 'KR'}

    signals = VolumeAlertStrategy()._do_scan()

    assert [s.data['stock_code'] for s in signals] == ['600584']
    assert '005930.KS' not in strategy_deps.requested_codes
```

- [ ] **Step 3: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: **3 FAIL / 3 PASS**，逐个核对：

| 测试 | 结果 | 原因 |
|---|---|---|
| `test_hk_stock_produces_signal` | FAIL | `is_a_share('9992.HK')` 为 False → `signals == []`，断言 `len == 1` 失败 |
| `test_both_markets_scanned_together` | FAIL | 只产出 `{'600584'}`，缺 `9992.HK` |
| `test_hk_survives_a_share_holiday` | FAIL | 原实现 `is_trading_day('A')` 为 False 即提前 `return []` |
| `test_a_survives_hk_holiday` | PASS | 原实现本就只扫 A 股，行为巧合一致 |
| `test_all_markets_closed_returns_empty_without_fetching` | PASS | 原实现判 `'A'` 休市也提前 return，不取数 |
| `test_unsupported_market_excluded` | PASS | `is_a_share('005930.KS')` 为 False，原实现已排除 |

后 3 个是**锁定既有行为的回归测试**，不是 TDD 意义上的新行为——它们的价值在 Step 4 改完之后：确保新的分组逻辑没把这些正确行为弄丢。开工前先 PASS 是正常的，不要因此删掉它们或改写实现去凑失败。

原有 3 个 sanity gate 测试也应仍 PASS（fixture 向后兼容：`markets=None` 时全按 `'A'`，`trading_days=None` 时全为交易日）。

- [ ] **Step 4: 写实现**

修改 `app/strategies/volume_alert/__init__.py`。

其一，模块顶部常量区（`RETRY_DELAY_MINUTES = 10` 之后）追加：

```python
SUPPORTED_MARKETS = {'A', 'HK'}
```

其二，`VolumeAlertStrategy.description` 由 `"A股收盘成交量异动推送"` 改为 `"A股/港股收盘成交量异动推送"`，模块 docstring 第一行由 `"""A股收盘成交量异动策略 — 盯盘股票量比超30%时推送"""` 改为 `"""A股/港股收盘成交量异动策略 — 盯盘股票量比超30%时推送"""`。

其三，`_do_scan` 的开头（原第 27-47 行，从 import 块到 `realtime = ...`）整体替换为：

```python
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import UnifiedStockDataService

        market_map = WatchService.get_market_map()

        if retry_codes:
            codes = retry_codes
            logger.info(f'[成交量异动] 重试 {len(codes)} 只: {codes}')
        else:
            today = date.today()
            open_markets = {
                m for m in SUPPORTED_MARKETS
                if m in set(market_map.values())
                and TradingCalendarService.is_trading_day(m, today)
            }
            if not open_markets:
                logger.info(f'[成交量异动] {today} A股/港股均非交易日，跳过扫描')
                return []
            codes = [c for c, m in market_map.items() if m in open_markets]

        if not codes:
            return []

        data_service = UnifiedStockDataService()
        trend = data_service.get_trend_data(codes, days=5, force_refresh=True)
        realtime = data_service.get_realtime_prices(codes, force_refresh=True)
```

注意 `MarketIdentifier` 的 import 整行删除——不再使用。

其四，函数末尾的日志行由 `f'[成交量异动] 扫描 {len(a_codes)} 只, 产出 {len(signals)} 个信号'` 改为 `f'[成交量异动] 扫描 {len(codes)} 只, 产出 {len(signals)} 个信号'`。

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: 全部 PASS（Task 1 的 18 个 + 本任务 6 个 = 24 个）

- [ ] **Step 6: Commit**

```bash
git -C <worktree路径> add app/strategies/volume_alert/__init__.py tests/test_volume_alert_unit_consistency.py
git -C <worktree路径> commit -m "feat(volume_alert): 覆盖港股，按市场分组并逐市场判交易日" -m "原 is_a_share 过滤把盯盘池 21 只中的 12 只港股全部排除。改用 WatchService.get_market_map() 按市场分组，各市场独立判交易日——顺带修掉 A 股休市连坐港股的隐性缺陷。" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 推送单位后缀与中文名兜底

**Files:**
- Modify: `app/strategies/volume_alert/__init__.py`（`_do_scan` 的信号构造循环与 `missing_codes` 错误推送分支）
- Test: `tests/test_volume_alert_unit_consistency.py`（第 7 节末尾追加）

**Interfaces:**
- Consumes: Task 1 的 `CONTRACT_VOLUME_UNIT`（`dict[str, str]`，从 `app.services.unified_stock_data` 导入）；Task 2 的局部变量 `market_map`（`dict[str, str]`）
- Produces: 无（终态任务）

- [ ] **Step 1: 写失败的测试**

在 `tests/test_volume_alert_unit_consistency.py` 第 7 节末尾（`test_unsupported_market_excluded` 之后）追加：

```python
def test_a_share_detail_uses_lots_unit(strategy_deps):
    """A 股 detail 的成交量带「手」后缀"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600584', '长电科技',
                              [1400000, 1500000, 1435993, 1761053, 2359071], today_str)]
    }
    strategy_deps.realtime = {'600584': {'volume': 2359071, 'change_pct': 10.0}}
    strategy_deps.markets = {'600584': 'A'}
    strategy_deps.names = {'600584': '长电科技'}

    signals = VolumeAlertStrategy()._do_scan()

    assert len(signals) == 1
    assert signals[0].detail == '今日 2,359,071 手 > 昨日 1,761,053 手 | 涨跌 +10.00%'


def test_hk_detail_uses_shares_unit(strategy_deps):
    """港股 detail 的成交量带「股」后缀"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('9992.HK', '9992.HK',
                              [7000000, 6500000, 8381789, 6638049, 19505349], today_str)]
    }
    strategy_deps.realtime = {'9992.HK': {'volume': 19505149, 'change_pct': -2.54}}
    strategy_deps.markets = {'9992.HK': 'HK'}
    strategy_deps.names = {'9992.HK': '泡泡玛特'}

    signals = VolumeAlertStrategy()._do_scan()

    assert len(signals) == 1
    assert signals[0].detail == '今日 19,505,349 股 > 昨日 6,638,049 股 | 涨跌 -2.54%'


def test_hk_title_uses_chinese_name_from_watch_codes(strategy_deps):
    """港股 trend 返回的 stock_name 是代码本身，标题必须走 WATCH_CODES 中文名"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('9992.HK', '9992.HK',
                              [7000000, 6500000, 8381789, 6638049, 19505349], today_str)]
    }
    strategy_deps.realtime = {'9992.HK': {'volume': 19505149, 'change_pct': -2.54}}
    strategy_deps.markets = {'9992.HK': 'HK'}
    strategy_deps.names = {'9992.HK': '泡泡玛特'}

    signals = VolumeAlertStrategy()._do_scan()

    assert signals[0].title.startswith('泡泡玛特(9992.HK) 放量')
    assert '9992.HK(9992.HK)' not in signals[0].title


def test_name_falls_back_to_trend_then_code(strategy_deps):
    """WATCH_CODES 无该名时退回 trend 的 stock_name"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600584', '长电科技',
                              [1400000, 1500000, 1435993, 1761053, 2359071], today_str)]
    }
    strategy_deps.realtime = {'600584': {'volume': 2359071, 'change_pct': 10.0}}
    strategy_deps.markets = {'600584': 'A'}
    strategy_deps.names = {'600584': ''}      # 模拟 WATCH_CODES 名为空

    signals = VolumeAlertStrategy()._do_scan()

    assert signals[0].title.startswith('长电科技(600584) 放量')


def test_shrink_direction_keeps_unit_suffix(strategy_deps):
    """缩量方向（vol_cmp 为 <）同样带单位后缀"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    strategy_deps.trend = {
        'stocks': [_make_ohlc('9992.HK', '9992.HK',
                              [8000000, 8000000, 8000000, 10000000, 5000000], today_str)]
    }
    strategy_deps.realtime = {'9992.HK': {'volume': 5000000, 'change_pct': -3.5}}
    strategy_deps.markets = {'9992.HK': 'HK'}
    strategy_deps.names = {'9992.HK': '泡泡玛特'}

    signals = VolumeAlertStrategy()._do_scan()

    assert len(signals) == 1
    assert signals[0].title.startswith('泡泡玛特(9992.HK) 缩量50%')
    assert signals[0].detail == '今日 5,000,000 股 < 昨日 10,000,000 股 | 涨跌 -3.50%'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: 5 个新测试 FAIL。detail 类断言实际得到 `今日 2,359,071 > 昨日 1,761,053 | 涨跌 +10.00%`（无单位后缀）；title 类断言实际得到 `9992.HK(9992.HK) 放量194%`。

- [ ] **Step 3: 写实现**

修改 `app/strategies/volume_alert/__init__.py`。

其一，`_do_scan` 的 import 块中，`UnifiedStockDataService` 那行改为同时导入常量：

```python
        from app.services.unified_stock_data import UnifiedStockDataService, CONTRACT_VOLUME_UNIT
```

其二，在 `market_map = WatchService.get_market_map()` 之后追加一行：

```python
        name_map = {e['stock_code']: e['stock_name'] for e in WatchService.get_watch_list()}
```

其三，信号构造循环里，取名那行由

```python
            name = stock.get('stock_name', code)
```

改为

```python
            name = name_map.get(code) or stock.get('stock_name') or code
```

（用 `or` 而非 `.get(code, ...)`：`WATCH_CODES` 里名为空字符串时也要退回下一级。）

其四，构造 Signal 的 detail 那段，由

```python
            vol_cmp = '>' if change_pct > 0 else '<'
            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if abs(change_pct) >= 0.5 else 'MEDIUM',
                title=f'{name}({code}) {direction}{pct_str}',
                detail=f"今日 {today_vol:,.0f} {vol_cmp} 昨日 {prev_vol:,.0f} | 涨跌 {price_str}",
                data={'stock_code': code, 'volume_change_pct': round(change_pct, 4)},
            ))
```

改为

```python
            vol_cmp = '>' if change_pct > 0 else '<'
            unit = CONTRACT_VOLUME_UNIT.get(market_map.get(code))
            u = f' {unit}' if unit else ''
            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if abs(change_pct) >= 0.5 else 'MEDIUM',
                title=f'{name}({code}) {direction}{pct_str}',
                detail=f"今日 {today_vol:,.0f}{u} {vol_cmp} 昨日 {prev_vol:,.0f}{u} | 涨跌 {price_str}",
                data={'stock_code': code, 'volume_change_pct': round(change_pct, 4)},
            ))
```

其五，`missing_codes` 的错误推送分支同样用 `name_map` 兜底，由

```python
            names = [s.get('stock_name', s.get('stock_code'))
                     for s in trend.get('stocks', [])
                     if s.get('stock_code') in missing_codes]
```

改为

```python
            names = [name_map.get(c) or c for c in missing_codes]
```

（原实现从 `trend['stocks']` 反查，港股场景下拿到的仍是代码；且 `missing_codes` 本身就是代码列表，直接映射更直接。）

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`

Expected: 全部 PASS（24 + 5 = 29 个）

- [ ] **Step 5: 跑全量测试确认无回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ > /tmp/pytest_out.txt 2>&1; grep -E "passed|failed|error" /tmp/pytest_out.txt | tail -5`

（`create_app` 触发的 crawl4ai 进度条走 stdout，`2>/dev/null | tail` 挡不住，必须重定向到文件再 grep——见 `.claude/rules/dev-environment.md`。）

Expected: 无 failed / error，passed 数量不低于改动前

- [ ] **Step 6: Commit**

```bash
git -C <worktree路径> add app/strategies/volume_alert/__init__.py tests/test_volume_alert_unit_consistency.py
git -C <worktree路径> commit -m "feat(volume_alert): 推送标注成交量单位并用 WATCH_CODES 中文名" -m "A/港股混在同一频道且量级差 100 倍，detail 补「手/股」后缀（单位取自 CONTRACT_VOLUME_UNIT）。港股 trend 的 stock_name 是代码本身，标题改走 WATCH_CODES 中文名兜底。" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## 收尾

三个任务完成后，按 `superpowers:finishing-a-development-branch` 把 worktree 分支并回 main。

上线后验收（下一个 A+港股共同交易日 16:30）：

- 推送中出现港股条目，标题为中文名而非代码
- A 股 detail 后缀为「手」，港股为「股」
- 日志 `[成交量异动] 扫描 N 只` 中 N 为 20（8 A + 12 HK），而非改动前的 8
