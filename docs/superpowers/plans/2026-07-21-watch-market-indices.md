# 盯盘各市场分区加指数条 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 盯盘页 A 股分区顶部加上证/创业板/科创50 指数条，韩股分区加 KOSPI，每条 chip 展示现价+当日涨跌幅，点击可展开分时图。

**Architecture:** 新增 `MARKET_INDICES` 独立配置（不进 `WATCH_CODES`，不进信号/告警链路）。A 指数实时价走已有的 `get_a_share_index_quotes`（东财/新浪，正确处理 `.SS/.SZ`），KOSPI 走 yfinance。分时图复用 `/watch/chart-data`（需先修腾讯指数代码映射 + KOSPI 市场识别）。前端在每个市场分区卡片内、大图上方渲染 chip 行 + 可折叠分时 mini 面板。

**Tech Stack:** Flask（`app/routes/watch.py`）、`UnifiedStockDataService`（`app/services/unified_stock_data.py`）、`MarketIdentifier`（`app/utils/market_identifier.py`）、ECharts + 原生 JS（`app/static/js/watch.js`）、pytest。

## Global Constraints

- 响应/注释/commit message 用中文；不写多余注释；不写 backup 文件。
- 所有 `git`/`pytest` 命令前加 `rtk`；env 赋值在 `rtk` 之前：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`。
- 指数**只做行情参照**：不进 `watch_alert` / 信号检测 / AI 分析 / `WATCH_CODES`。
- 只做 A 和 KR 两个市场。US 已有纳指100 在全局基准 bar；HK 不做。
- A 指数代码：上证 `000001.SS`、创业板 `399006.SZ`、科创50 `000688.SS`；韩股：KOSPI `^KS11`。
- 单测平铺放 `tests/test_*.py`，不建子目录。
- 一次性验证脚本放 `scripts/_*.py`，任务结束 `rm`，不入库；`scripts/_*.py` 内 `import app` 前加 `sys.path.insert(0, repo_root)`。

---

## File Structure

- `app/config/stock_codes.py` — 新增 `MARKET_INDICES` 常量（改）
- `app/utils/market_identifier.py` — `identify` 特判 KOSPI/KOSDAQ → 'KR'（改）
- `app/services/unified_stock_data.py` — 提取腾讯代码 helper 修指数 sh/sz 映射；`get_a_share_index_quotes` 加 `cache_only`（改）
- `app/routes/watch.py` — `/watch/prices` 返回 `indices`（改）
- `app/strategies/watch_preload/__init__.py` — 预热指数缓存（改）
- `app/static/js/watch.js` — state.indices + chip 渲染 + 点击展开分时（改）
- `.claude/rules/watch.md` — 补文档（改）
- `tests/test_market_indices_config.py`、`tests/test_market_identifier_kospi.py`、`tests/test_tencent_index_code.py`、`tests/test_watch_prices_indices.py`（新增）

---

## Task 1: 验证 spike（确认 4 个指数代码取数可用，不 commit）

**Files:**
- Create（临时，任务末 `rm`）: `scripts/_verify_market_indices.py`

**目的**：在动 UI/路由前，用真实服务方法确认 4 个指数的实时价与分时数据都能取到，锁定后续任务的数据形状假设。此任务无单测，只产出事实记录。

- [ ] **Step 1: 写验证脚本**

```python
# scripts/_verify_market_indices.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
from app.services.unified_stock_data import unified_stock_data_service as svc

app = create_app()
lines = []
with app.app_context():
    a_codes = ['000001.SS', '399006.SZ', '000688.SS']
    q = svc.get_a_share_index_quotes(a_codes, force_refresh=True)
    for c in a_codes:
        d = q.get(c) or {}
        lines.append(f"A实时 {c}: close={d.get('close')} pct={d.get('change_percent')} name={d.get('name')}")

    kr = svc.get_realtime_prices(['^KS11'], force_refresh=True)
    d = kr.get('^KS11') or {}
    lines.append(f"KR实时 ^KS11: price={d.get('current_price')} pct={d.get('change_percent')} name={d.get('name')}")

    for c in ['000001.SS', '399006.SZ', '000688.SS', '^KS11']:
        intr = svc.get_intraday_data([c], force_refresh=True)
        stocks = intr.get('stocks', [])
        n = len(stocks[0].get('data', [])) if stocks else 0
        lines.append(f"分时 {c}: 点数={n}")

Path('scripts/_verify_out.txt').write_text('\n'.join(lines), encoding='utf-8')
```

- [ ] **Step 2: 运行并读结果**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python scripts/_verify_market_indices.py`
然后用 Read 工具读 `scripts/_verify_out.txt`。

Expected（预期，Task 1 前的分时对 A 指数会失败——这正是 Task 3 要修的）：
- A 实时 3 条都有 `close` 值（非 None）。
- KR 实时 `^KS11` 有 `price` 值（非 None）。
- 分时：A 指数此时**可能 0 点数**（腾讯代码映射未修）；`^KS11` 分时点数 > 0（yfinance）。

记录实际结果。**若 `^KS11` 实时或分时返回 None/0 点**，说明 yfinance 不支持，需在 Task 7/8 把 KR 指数降级为「仅 chip 无分时」并在计划末记 log——但先继续，多数情况 `^KS11` 可用。

- [ ] **Step 3: 删除临时脚本**

```bash
rm scripts/_verify_market_indices.py scripts/_verify_out.txt
```

不 commit。

---

## Task 2: MarketIdentifier 特判 KOSPI → 'KR'

**Files:**
- Modify: `app/utils/market_identifier.py`（`identify` 方法，`^` 通配前插入）
- Test: `tests/test_market_identifier_kospi.py`

**Interfaces:**
- Produces: `MarketIdentifier.identify('^KS11') == 'KR'`（供 Task 8 的 chart_data 交易时段、`get_intraday_data` 路由使用）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_market_identifier_kospi.py
from app.utils.market_identifier import MarketIdentifier


def test_kospi_index_identified_as_kr():
    assert MarketIdentifier.identify('^KS11') == 'KR'
    assert MarketIdentifier.identify('^KQ11') == 'KR'


def test_us_index_still_us():
    assert MarketIdentifier.identify('^GSPC') == 'US'
    assert MarketIdentifier.identify('^NDX') == 'US'


def test_kospi_to_yfinance_unchanged():
    assert MarketIdentifier.to_yfinance('^KS11') == '^KS11'
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_market_identifier_kospi.py -v`
Expected: `test_kospi_index_identified_as_kr` FAIL（当前 `^KS11` 返回 'US'）。

- [ ] **Step 3: 实现**

在 `app/utils/market_identifier.py` 的 `identify` 中，**在** `# 美股指数：以^开头` 那段（`if code.startswith('^'): return 'US'`）**之前**插入：

```python
        # 韩股指数：^KS11 (KOSPI), ^KQ11 (KOSDAQ) —— 早于通用 ^ 判美股
        if code.upper() in ('^KS11', '^KQ11'):
            return 'KR'
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_market_identifier_kospi.py -v`
Expected: 3 passed。

- [ ] **Step 5: commit**

```bash
rtk git add app/utils/market_identifier.py tests/test_market_identifier_kospi.py && rtk git commit -m "feat(watch): MarketIdentifier 特判 KOSPI/KOSDAQ 指数为 KR"
```

---

## Task 3: 修腾讯指数代码映射（A 指数分时可取）

**Files:**
- Modify: `app/services/unified_stock_data.py`（新增模块级 helper；改 `_fetch_from_tencent` 行 918-922 与 `_fetch_intraday_a_share_tencent` 行 1346）
- Test: `tests/test_tencent_index_code.py`

**背景**：当前两处都用 `f'sh{code}' if code.startswith(('6','5')) else f'sz{code}'`——对 `000001.SS`（上证，0 开头但在 sh）拼成 `sz000001.SS`（后缀没剥 + 交易所错），科创50 `000688.SS` 同理。`.SS`/`.SZ` 后缀是权威交易所标识：`.SS→sh`、`.SZ→sz`。

**Interfaces:**
- Produces: 模块级 `_tencent_code(code: str) -> str`；`_tencent_code('000001.SS')=='sh000001'`、`_tencent_code('399006.SZ')=='sz399006'`、`_tencent_code('000688.SS')=='sh000688'`、`_tencent_code('600519')=='sh600519'`、`_tencent_code('300223')=='sz300223'`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tencent_index_code.py
from app.services.unified_stock_data import _tencent_code


def test_bare_stock_codes():
    assert _tencent_code('600519') == 'sh600519'
    assert _tencent_code('300223') == 'sz300223'
    assert _tencent_code('510300') == 'sh510300'


def test_index_codes_respect_suffix():
    assert _tencent_code('000001.SS') == 'sh000001'   # 上证：0开头但在沪
    assert _tencent_code('000688.SS') == 'sh000688'   # 科创50：0开头但在沪
    assert _tencent_code('399006.SZ') == 'sz399006'   # 创业板指
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_index_code.py -v`
Expected: FAIL with `ImportError: cannot import name '_tencent_code'`。

- [ ] **Step 3: 实现 helper**

在 `app/services/unified_stock_data.py` 模块顶层（import 之后、类定义之前）加：

```python
def _tencent_code(code: str) -> str:
    """腾讯行情代码前缀：优先 .SS/.SH→sh、.SZ→sz（指数权威口径），
    裸代码回退 6/5 开头→sh、其余→sz。"""
    c = code.strip()
    up = c.upper()
    if up.endswith('.SS') or up.endswith('.SH'):
        return f"sh{c[:-3]}"
    if up.endswith('.SZ'):
        return f"sz{c[:-3]}"
    return f"sh{c}" if c.startswith(('6', '5')) else f"sz{c}"
```

- [ ] **Step 4: 在两处消费 helper**

`_fetch_from_tencent`（约行 918-922）把：

```python
        for code in stock_codes:
            if code.startswith(('6', '5')):
                tc = f'sh{code}'
            else:
                tc = f'sz{code}'
            tencent_codes.append(tc)
            code_map[tc] = code
```

改为：

```python
        for code in stock_codes:
            tc = _tencent_code(code)
            tencent_codes.append(tc)
            code_map[tc] = code
```

`_fetch_intraday_a_share_tencent`（约行 1346）把：

```python
            tc = f'sh{code}' if code.startswith(('6', '5')) else f'sz{code}'
```

改为：

```python
            tc = _tencent_code(code)
```

- [ ] **Step 5: 运行单测确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_index_code.py -v`
Expected: 2 passed。

- [ ] **Step 6: 联网验证 A 指数分时（临时脚本，不 commit）**

Write `scripts/_verify_a_index_intraday.py`：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
from app.services.unified_stock_data import unified_stock_data_service as svc
app = create_app()
out = []
with app.app_context():
    for c in ['000001.SS', '399006.SZ', '000688.SS']:
        r = svc.get_intraday_data([c], force_refresh=True)
        s = r.get('stocks', [])
        out.append(f"{c}: {len(s[0]['data']) if s else 0} 点")
Path('scripts/_a_index_out.txt').write_text('\n'.join(out), encoding='utf-8')
```

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python scripts/_verify_a_index_intraday.py`，Read `scripts/_a_index_out.txt`。
Expected: 交易日 3 条点数 > 0（非交易日腾讯返回上一交易日，仍应 > 0）。然后 `rm scripts/_verify_a_index_intraday.py scripts/_a_index_out.txt`。

- [ ] **Step 7: commit**

```bash
rtk git add app/services/unified_stock_data.py tests/test_tencent_index_code.py && rtk git commit -m "fix(watch): 腾讯指数代码映射按 .SS/.SZ 后缀定 sh/sz，修上证/科创50分时"
```

---

## Task 4: 新增 MARKET_INDICES 配置

**Files:**
- Modify: `app/config/stock_codes.py`（`BENCHMARK_CODES` 之后追加）
- Test: `tests/test_market_indices_config.py`

**Interfaces:**
- Produces: `MARKET_INDICES: dict[str, list[dict]]`，键为市场，值为 `[{'code','name'}, ...]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_market_indices_config.py
from app.config.stock_codes import MARKET_INDICES


def test_a_market_has_three_indices():
    a = MARKET_INDICES['A']
    codes = [i['code'] for i in a]
    assert codes == ['000001.SS', '399006.SZ', '000688.SS']
    assert [i['name'] for i in a] == ['上证', '创业板', '科创50']


def test_kr_market_has_kospi():
    kr = MARKET_INDICES['KR']
    assert kr == [{'code': '^KS11', 'name': 'KOSPI'}]


def test_only_a_and_kr():
    assert set(MARKET_INDICES.keys()) == {'A', 'KR'}
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_market_indices_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'MARKET_INDICES'`。

- [ ] **Step 3: 实现**

在 `app/config/stock_codes.py` 的 `BENCHMARK_CODES = [...]` 之后追加：

```python
# 盯盘各市场分区的指数条（仅行情参照，不进 WATCH_CODES/告警/信号）
MARKET_INDICES = {
    'A': [
        {'code': '000001.SS', 'name': '上证'},
        {'code': '399006.SZ', 'name': '创业板'},
        {'code': '000688.SS', 'name': '科创50'},
    ],
    'KR': [
        {'code': '^KS11', 'name': 'KOSPI'},
    ],
}
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_market_indices_config.py -v`
Expected: 3 passed。

- [ ] **Step 5: commit**

```bash
rtk git add app/config/stock_codes.py tests/test_market_indices_config.py && rtk git commit -m "feat(watch): 新增 MARKET_INDICES 配置（A股上证/创业板/科创50，韩股KOSPI）"
```

---

## Task 5: get_a_share_index_quotes 加 cache_only + /watch/prices 返回 indices

**Files:**
- Modify: `app/services/unified_stock_data.py`（`get_a_share_index_quotes` 加 `cache_only`）
- Modify: `app/routes/watch.py`（`prices()` 增 `indices`）
- Test: `tests/test_watch_prices_indices.py`

**Interfaces:**
- Consumes: `MARKET_INDICES`（Task 4）、`get_a_share_index_quotes`、`get_prices_cached_only`
- Produces: `/watch/prices` JSON 增字段 `indices: {market: [{code, name, price, change_pct}]}`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_prices_indices.py
from flask import Flask
from app.routes import watch_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(watch_bp, url_prefix='/watch')
    return app


def test_prices_returns_indices(monkeypatch):
    from app.services import unified_stock_data as usd

    def fake_cached_only(codes):
        return {c: {'current_price': 2500.0, 'change_percent': 0.3,
                    'name': 'KOSPI', 'market': 'KR'} for c in codes}

    def fake_a_index(codes, force_refresh=False, cache_only=False):
        return {c: {'close': 3400.0, 'change_percent': 0.5, 'name': c}
                for c in codes}

    monkeypatch.setattr(usd.unified_stock_data_service,
                        'get_prices_cached_only', fake_cached_only)
    monkeypatch.setattr(usd.unified_stock_data_service,
                        'get_a_share_index_quotes', fake_a_index)

    client = _make_app().test_client()
    resp = client.get('/watch/prices').get_json()

    assert 'indices' in resp
    assert set(resp['indices'].keys()) == {'A', 'KR'}
    a = resp['indices']['A']
    assert [i['code'] for i in a] == ['000001.SS', '399006.SZ', '000688.SS']
    assert a[0]['price'] == 3400.0 and a[0]['change_pct'] == 0.5
    assert a[0]['name'] == '上证'
    kr = resp['indices']['KR']
    assert kr[0]['code'] == '^KS11' and kr[0]['price'] == 2500.0
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_prices_indices.py -v`
Expected: FAIL（`'indices' not in resp` 或 `get_a_share_index_quotes` 无 `cache_only` 参数报 TypeError）。

- [ ] **Step 3: get_a_share_index_quotes 加 cache_only**

在 `app/services/unified_stock_data.py` 把签名 `def get_a_share_index_quotes(self, index_codes: list, force_refresh: bool = False) -> dict:` 改为：

```python
    def get_a_share_index_quotes(self, index_codes: list,
                                  force_refresh: bool = False,
                                  cache_only: bool = False) -> dict:
```

在缓存检查块之后、`if not need_fetch: return result` 之后紧接着加（`self._miss_count += len(need_fetch)` 之前）：

```python
        if cache_only:
            return result
```

- [ ] **Step 4: prices() 增 indices**

在 `app/routes/watch.py` 的 `prices()` 里，`benchmark_list` 构建之后、`return jsonify(...)` 之前插入：

```python
    from app.config.stock_codes import MARKET_INDICES

    indices_out = {}
    a_index_defs = MARKET_INDICES.get('A', [])
    a_index_codes = [i['code'] for i in a_index_defs]
    a_quotes = (unified_stock_data_service.get_a_share_index_quotes(
        a_index_codes, cache_only=True) if a_index_codes else {})
    if a_index_defs:
        indices_out['A'] = [{
            'code': i['code'], 'name': i['name'],
            'price': (a_quotes.get(i['code']) or {}).get('close'),
            'change_pct': (a_quotes.get(i['code']) or {}).get('change_percent'),
        } for i in a_index_defs]

    for mkt, defs in MARKET_INDICES.items():
        if mkt == 'A':
            continue
        mcodes = [i['code'] for i in defs]
        mraw = _read_cached_prices(mcodes)
        indices_out[mkt] = [{
            'code': i['code'], 'name': i['name'],
            'price': (mraw.get(i['code']) or {}).get('current_price'),
            'change_pct': (mraw.get(i['code']) or {}).get('change_percent'),
        } for i in defs]
```

并把 `return jsonify({'success': True, 'prices': price_list, 'benchmarks': benchmark_list})` 改为：

```python
    return jsonify({'success': True, 'prices': price_list,
                    'benchmarks': benchmark_list, 'indices': indices_out})
```

- [ ] **Step 5: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_prices_indices.py -v`
Expected: 1 passed。

- [ ] **Step 6: commit**

```bash
rtk git add app/services/unified_stock_data.py app/routes/watch.py tests/test_watch_prices_indices.py && rtk git commit -m "feat(watch): /watch/prices 返回各市场指数条数据（A股缓存只读，KR走yfinance缓存）"
```

---

## Task 6: watch_preload 预热指数缓存

**Files:**
- Modify: `app/strategies/watch_preload/__init__.py`
- Test: `tests/test_watch_preload_indices.py`

**背景**：`/watch/prices` 对指数走 cache_only，需 preload 每分钟预热。A 指数 → `get_a_share_index_quotes(force_refresh=True)`；KR 指数 → `get_realtime_prices(force_refresh=True)`。仅在对应市场开盘时预热。指数分时也预热（A 用 tencent、KR 用 yfinance）。指数预热独立于现有 per-market 价格 backoff 逻辑（`_prices_ok` 校验 `current_price`，与指数 `close` 字段不兼容），不复用那条循环。

**Interfaces:**
- Consumes: `MARKET_INDICES`、`get_a_share_index_quotes`、`get_realtime_prices`、`get_intraday_data`
- Produces: `WatchPreloadStrategy._index_codes_for_markets(open_markets) -> dict[str, list[str]]`（返回开盘市场的指数代码，供测试）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_preload_indices.py
from app.strategies.watch_preload import WatchPreloadStrategy


def test_index_codes_for_open_markets():
    s = WatchPreloadStrategy()
    got = s._index_codes_for_markets({'A'})
    assert got == {'A': ['000001.SS', '399006.SZ', '000688.SS']}


def test_index_codes_kr_open():
    s = WatchPreloadStrategy()
    got = s._index_codes_for_markets({'A', 'KR'})
    assert got['KR'] == ['^KS11']


def test_index_codes_none_open():
    s = WatchPreloadStrategy()
    assert s._index_codes_for_markets({'US', 'HK'}) == {}
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_indices.py -v`
Expected: FAIL with `AttributeError: ... '_index_codes_for_markets'`。

- [ ] **Step 3: 实现 helper**

在 `WatchPreloadStrategy` 类内加：

```python
    @staticmethod
    def _index_codes_for_markets(open_markets: set) -> dict:
        from app.config.stock_codes import MARKET_INDICES
        out = {}
        for mkt, defs in MARKET_INDICES.items():
            if mkt in open_markets:
                out[mkt] = [i['code'] for i in defs]
        return out
```

- [ ] **Step 4: 接入 scan（预热指数价格 + 分时）**

在 `scan()` 里，A 股分时预取块（`a_codes = market_codes.get('A', [])` 那段）**之后**插入：

```python
        # 指数条预热（价格 + 分时），独立于个股 backoff
        index_codes_by_market = self._index_codes_for_markets(open_markets)
        for mkt, idx_codes in index_codes_by_market.items():
            if not idx_codes:
                continue
            try:
                if mkt == 'A':
                    unified_stock_data_service.get_a_share_index_quotes(
                        idx_codes, force_refresh=True)
                else:
                    unified_stock_data_service.get_realtime_prices(
                        idx_codes, force_refresh=True)
                unified_stock_data_service.get_intraday_data(idx_codes)
                logger.debug(f'[盯盘预取] {mkt} 指数预热完成: {len(idx_codes)}只')
            except Exception as e:
                logger.error(f'[盯盘预取] {mkt} 指数预热失败: {e}')
```

（`open_markets` 已在 scan 上文定义，行 61。）

- [ ] **Step 5: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_indices.py -v`
Expected: 3 passed。

- [ ] **Step 6: 跑现有 preload 测试确认没回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_cadence.py tests/test_watch_preload_backoff.py -v`
Expected: 全 passed。

- [ ] **Step 7: commit**

```bash
rtk git add app/strategies/watch_preload/__init__.py tests/test_watch_preload_indices.py && rtk git commit -m "feat(watch): watch_preload 预热各市场指数条价格与分时缓存"
```

---

## Task 7: 前端渲染各市场指数 chip 行

**Files:**
- Modify: `app/static/js/watch.js`（`WatchState`/`init` 缓存恢复、`load`、`renderCards` 模板、新增 `renderIndexStrips`）

**说明**：前端无 JS 单测框架，本任务用手动 smoke 验证 + 具体代码。指数 chip 复用 benchmark chip 样式。

**Interfaces:**
- Consumes: `/watch/prices` 的 `indices` 字段（Task 5）
- Produces: 每个 A/KR 分区卡片内、大图上方一条 `#index-strip-${market}` chip 行

- [ ] **Step 1: state 增 indices 字段**

在 `watch.js` 顶部 state 对象（含 `benchmarks: []` 处，约行 87）加：

```javascript
    indices: {},
```

- [ ] **Step 2: load 落存 indices**

在 `load()` 里 `this.benchmarks = priceData.benchmarks || [];`（约行 212）后加：

```javascript
            this.indices = priceData.indices || {};
```

在缓存持久化处（`WatchStore.set('benchmarks', null, this.benchmarks);`，约行 192）后加：

```javascript
        WatchStore.set('indices', null, this.indices);
```

在缓存恢复处（`const benchData = WatchStore.get('benchmarks');`，约行 152）后加：

```javascript
        const idxData = WatchStore.get('indices');
        if (idxData && idxData.data) this.indices = idxData.data;
```

- [ ] **Step 3: renderCards 模板插入指数容器**

在 `renderCards()` 的市场卡片模板里，把 `<div class="market-chart" id="chart-market-${market}">` **之前**插入两行：

```javascript
                    <div class="watch-index-strip d-flex gap-2 flex-wrap mb-2" id="index-strip-${market}"></div>
                    <div class="watch-index-chart mb-2" id="index-chart-${market}" style="display:none;height:180px;"></div>
```

在 `container.innerHTML = html;` 之后、`this._updateAllSummaryTables();` 之前加：

```javascript
        this.renderIndexStrips();
```

- [ ] **Step 4: 新增 renderIndexStrips（复用 benchmark chip 样式 + HTML 转义）**

在 `renderBenchmarks()` 方法之后加：

```javascript
    _escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => (
            { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
        ));
    },

    renderIndexStrips() {
        for (const [market, items] of Object.entries(this.indices || {})) {
            const el = document.getElementById(`index-strip-${market}`);
            if (!el || !items || !items.length) continue;
            el.innerHTML = items.map(idx => {
                const price = idx.price != null ? idx.price.toFixed(2) : '--';
                const pctClass = idx.change_pct > 0 ? 'price-up' : idx.change_pct < 0 ? 'price-down' : 'price-flat';
                const sign = idx.change_pct > 0 ? '+' : '';
                const pct = idx.change_pct != null ? `${sign}${idx.change_pct.toFixed(2)}%` : '--';
                const code = this._escapeHtml(idx.code);
                const name = this._escapeHtml(idx.name);
                return `<div class="card px-2 py-1" style="min-width:120px;cursor:pointer;"
                            onclick="Watch.toggleIndexChart('${market}','${code}','${name}')">
                    <div class="d-flex align-items-center gap-2">
                        <span class="fw-bold small">${name}</span>
                        <span class="small">${price}</span>
                        <span class="${pctClass} small fw-bold">${pct}</span>
                    </div>
                </div>`;
            }).join('');
        }
    },
```

- [ ] **Step 5: 加占位 toggleIndexChart（Task 8 填充）**

先加一个空实现，避免点击报错（Task 8 替换）：

```javascript
    toggleIndexChart(market, code, name) { /* Task 8 实现 */ },
```

- [ ] **Step 6: 手动 smoke**

Run: `python run.py`，浏览器开 `http://127.0.0.1:5000/watch`。
Expected: A 股分区大图上方出现「上证/创业板/科创50」三个 chip（价+涨跌幅，涨绿跌红）；韩股分区出现「KOSPI」chip；全局基准 bar（金/银/纳指）不变；US/HK 分区无指数条。点击 chip 暂无反应（Task 8 补）。

- [ ] **Step 7: commit**

```bash
rtk git add app/static/js/watch.js && rtk git commit -m "feat(watch): 各市场分区渲染指数 chip 行（上证/创业板/科创50、KOSPI）"
```

---

## Task 8: 点击指数 chip 展开分时 mini 面板

**Files:**
- Modify: `app/static/js/watch.js`（实现 `toggleIndexChart`）

**说明**：复用 `/watch/chart-data?code=<code>&period=intraday`。单开语义：点已展开的同一指数收起；点另一指数切换。渲染到 `#index-chart-${market}` ECharts 实例。

**Interfaces:**
- Consumes: `/watch/chart-data`（已存在）、`this.chartInstances`（复用 dispose 约定）

- [ ] **Step 1: 实现 toggleIndexChart**

把 Task 7 的占位 `toggleIndexChart` 替换为：

```javascript
    async toggleIndexChart(market, code, name) {
        const el = document.getElementById(`index-chart-${market}`);
        if (!el) return;
        const key = `index-${market}`;
        // 已展开且是同一指数 → 收起
        if (el.style.display !== 'none' && el.dataset.code === code) {
            el.style.display = 'none';
            if (this.chartInstances[key]) { this.chartInstances[key].dispose(); delete this.chartInstances[key]; }
            return;
        }
        el.style.display = 'block';
        el.dataset.code = code;
        try {
            const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=intraday`);
            const d = await resp.json();
            if (!d.success || !d.data || !d.data.length) {
                el.innerHTML = `<div class="text-muted small p-2">${this._escapeHtml(name)} 暂无分时数据</div>`;
                return;
            }
            el.innerHTML = '';
            if (this.chartInstances[key]) this.chartInstances[key].dispose();
            const chart = echarts.init(el);
            this.chartInstances[key] = chart;
            const times = d.data.map(p => p.time);
            const closes = d.data.map(p => p.close);
            const prev = d.prev_close;
            const up = closes.length && closes[closes.length - 1] >= (prev ?? closes[0]);
            chart.setOption({
                grid: { left: 48, right: 12, top: 24, bottom: 24 },
                tooltip: { trigger: 'axis' },
                title: { text: `${name} 分时`, textStyle: { fontSize: 12 }, left: 8, top: 4 },
                xAxis: { type: 'category', data: times, boundaryGap: false,
                         axisLabel: { fontSize: 10 } },
                yAxis: { type: 'value', scale: true, axisLabel: { fontSize: 10 },
                         splitLine: { show: true } },
                series: [{
                    type: 'line', data: closes, showSymbol: false, smooth: false,
                    lineStyle: { width: 1.5, color: up ? '#e34d59' : '#00a870' },
                    markLine: prev != null ? {
                        symbol: 'none', silent: true,
                        data: [{ yAxis: prev }],
                        lineStyle: { type: 'dashed', color: '#999', width: 1 },
                        label: { formatter: `昨收 ${prev}`, fontSize: 10 }
                    } : undefined,
                }],
            });
        } catch (e) {
            el.innerHTML = `<div class="text-muted small p-2">分时加载失败</div>`;
        }
    },
```

- [ ] **Step 2: renderCards dispose 兼容指数图**

`renderCards()` 开头 `Object.values(this.chartInstances).forEach(c => c.dispose()); this.chartInstances = {};` 已会清理所有实例（含 `index-*`），无需额外改动。确认该行存在即可。

- [ ] **Step 3: 手动 smoke**

Run: `python run.py`，开 `/watch`。
Expected:
- 点 A 股「上证」chip → 下方展开分时折线（含昨收虚线）；再点收起。
- 点「创业板」→ 切换到创业板分时（上证收起）。
- 点韩股「KOSPI」→ 展开 KOSPI 分时（若 Task 1 验证 `^KS11` 分时可用；不可用则显示「暂无分时数据」，可接受）。
- 切换市场「实时/7日」大图不受指数 mini 面板影响。

- [ ] **Step 4: commit**

```bash
rtk git add app/static/js/watch.js && rtk git commit -m "feat(watch): 点击指数 chip 展开分时 mini 面板（复用 /watch/chart-data，单开切换）"
```

---

## Task 9: 全量回归 + 文档

**Files:**
- Modify: `.claude/rules/watch.md`

- [ ] **Step 1: 跑全量单测**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -q > scratch_test_out.txt 2>&1; rtk python -c "import re;print([l for l in open('scratch_test_out.txt',encoding='utf-8') if re.search(r'passed|failed|error',l)][-3:])"`
Expected: 无新增 failed/error（注意 Windows 下 crawl4ai 进度条会污染 stdout，用文件重定向再 grep，见 dev-environment 约定）。跑完 `rm scratch_test_out.txt`。

- [ ] **Step 2: 更新 watch.md**

在 `.claude/rules/watch.md` 的「盯盘股票池（代码配置，非 DB）」小节之后加一段：

```markdown
## 盯盘各市场分区指数条

各市场分区大图上方的指数 chip 由 `app/config/stock_codes.py` 的 `MARKET_INDICES`（按市场键）决定，仅做行情参照——**不进** `WATCH_CODES`/告警/信号/AI 分析。当前：A 股=上证`000001.SS`/创业板`399006.SZ`/科创50`000688.SS`，韩股=KOSPI`^KS11`。数据经 `/watch/prices` 的 `indices` 字段下发：A 指数走 `get_a_share_index_quotes(cache_only=True)`（东财/新浪，正确处理 `.SS/.SZ`），KR 走 `get_realtime_prices` 缓存；`watch_preload` 每分钟按开盘市场预热价格+分时。点击 chip 复用 `/watch/chart-data?period=intraday` 展开分时 mini 面板（单开切换）。

**关键坑**：腾讯行情代码由 `_tencent_code()`（`unified_stock_data.py`）按 `.SS→sh`/`.SZ→sz` 定交易所——上证/科创50 是 `0` 开头但在沪，不能用「6/5→sh 其余→sz」裸启发式。KOSPI `^KS11` 由 `MarketIdentifier.identify` 特判为 `KR`（否则 `^` 通配落 US，交易时段/取数源错）。
```

- [ ] **Step 3: commit**

```bash
rtk git add .claude/rules/watch.md && rtk git commit -m "docs(watch): 补各市场分区指数条设计与取数坑"
```

---

## Self-Review 记录

- **Spec 覆盖**：MARKET_INDICES 配置(T4) / 后端取价 indices(T5) / 前端 chip(T7) / 分时展开(T8) / preload 预热(T6) / MarketIdentifier+腾讯映射风险(T2,T3) / 文档(T9) —— spec 各节均有对应任务。
- **数据形状一致**：`get_a_share_index_quotes` 返回 `close`/`change_percent`（T1 确认、T5 消费）；`get_prices_cached_only` 返回 `current_price`/`change_percent`（T5 消费）；两者在路由统一映射为 `price`/`change_pct`（T5→T7 前端消费一致）。
- **命名一致**：`_tencent_code`(T3)、`MARKET_INDICES`(T4)、`_index_codes_for_markets`(T6)、`renderIndexStrips`/`toggleIndexChart`/`_escapeHtml`(T7,T8) 前后引用一致。
- **契约风险**：KOSPI `^KS11` 实时/分时可用性由 T1 联网确认；若不可用，chip 仍显示（价来自 yfinance 若有）、分时降级为「暂无数据」，不阻塞交付。
