# 矿产看板页面 `/minerals` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建 `/minerals` 矿产看板，按「铜」「锂」两板块展示期货走势 + 相关股票走势，并按产业链位置标注每只股票对期货价格的影响是正面（🟢）还是负面（🔴）。

**Architecture:** 复用现有 `FuturesService`/`UnifiedStockDataService`（铜期货走 yfinance `HG=F`，锂期货走 akshare 碳酸锂主连 `LC0` + 代理降级）；股票池与影响标注来自 `docs/stock-analytics/valuations.yaml` 新增的 `commodity` / `commodity_impact` 字段（同步写入对应 buffett 档 frontmatter）。新增一个薄数据装配层 `app/services/minerals_data.py`、一个路由 `app/routes/minerals.py`、一个模板 `minerals.html`，并扩展 `stock-deep-redo`/`buffett` skill 让以后分析自动产出这两个字段。

**Tech Stack:** Flask Blueprint + Jinja2 + ECharts（项目既有）+ akshare（碳酸锂期货）+ yfinance（铜期货/股票）+ pytest。

## Global Constraints

- 测试/脚本命令一律 `rtk` 前缀，env 赋值在 `rtk` 之前：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -v`。
- `git add` 与 `git commit` **放进同一条命令链**（防并行 session 抢 index），commit message 用 `-m`，尾部加 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
- 不写 backup 文件，不写多余注释，响应中文。
- 一次性脚本（`scripts/_*.py`）任务结束 `rtk git`-不入库，跑完 `rm`。
- valuations.yaml / frontmatter 的 `stock_code` 必须**字符串引号**（防 YAML int 化丢前导 0）。
- `commodity` 取值枚举 `{copper, lithium}`；`commodity_impact` 取值枚举 `{positive, negative}`。两者均为**可选** frontmatter 字段。
- 港股代码喂 `get_realtime_prices` 前必须用 `_fetch_code` 归一为 4 位 `.HK`。
- `unified_stock_data_service.get_realtime_prices` 按既有调用范式：强刷用 `force_refresh=True`，首屏用 `cache_only=True`，**不要同时传两者**。
- 不动 `heavy_metals` 走势看板；不新建 DB 分类。

---

### Task 1: 板块配置 `MINERAL_BOARDS` + 碳酸锂数据源 spike

**Files:**
- Create: `app/config/minerals.py`
- Create (throwaway, rm after): `scripts/_probe_lithium.py`
- Test: `tests/test_minerals.py`

**Interfaces:**
- Produces: `MINERAL_BOARDS: dict[str, dict]`，键 `copper`/`lithium`，每板块含 `name`/`futures_code`/`futures_name`/`futures_source`（`'yfinance'`|`'akshare'`）/`futures_fallback_code`（可为 None）。

- [ ] **Step 1: spike 确认 akshare 碳酸锂主连接口**

写一次性探针确认接口名、返回列名、能否取到收盘价序列（碳酸锂在广期所，yfinance 无对应物，必须 akshare）。

Create `scripts/_probe_lithium.py`:

```python
import akshare as ak

# 候选：碳酸锂主连（新浪连续合约）
df = ak.futures_main_sina(symbol="LC0")
print("columns:", list(df.columns))
print("tail:")
print(df.tail(3).to_string())
```

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/_probe_lithium.py`

预期：打印出含「日期」「收盘价」列的 DataFrame 尾部数行。**若 `futures_main_sina(symbol="LC0")` 报错或空**：依次试 `ak.futures_zh_realtime(symbol="碳酸锂")`、`ak.futures_zh_daily_sina(symbol="lc2509")`（具体合约），把**实际可用的接口名与列名**记到本任务 Step 3 的实现里（替换 `_fetch_lithium_raw` 的 body 与列名常量）。确认后 `rm scripts/_probe_lithium.py`。

- [ ] **Step 2: 写 MINERAL_BOARDS 配置的失败测试**

Append to `tests/test_minerals.py`（新建文件，顶部加 `import pytest`）:

```python
def test_mineral_boards_has_copper_and_lithium():
    from app.config.minerals import MINERAL_BOARDS
    assert set(MINERAL_BOARDS) == {'copper', 'lithium'}
    cu = MINERAL_BOARDS['copper']
    assert cu['futures_code'] == 'HG=F'
    assert cu['futures_source'] == 'yfinance'
    li = MINERAL_BOARDS['lithium']
    assert li['futures_code'] == 'LC0'
    assert li['futures_source'] == 'akshare'
    for b in MINERAL_BOARDS.values():
        assert {'name', 'futures_code', 'futures_name', 'futures_source', 'futures_fallback_code'} <= set(b)
```

- [ ] **Step 3: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py::test_mineral_boards_has_copper_and_lithium -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.config.minerals'`。

- [ ] **Step 4: 写 MINERAL_BOARDS 配置**

Create `app/config/minerals.py`:

```python
"""矿产看板板块配置：每个板块一个期货锚 + 相关股票来自 valuations.yaml 的 commodity 字段。"""

MINERAL_BOARDS = {
    'copper': {
        'name': '铜',
        'futures_code': 'HG=F',
        'futures_name': 'COMEX铜',
        'futures_source': 'yfinance',
        'futures_fallback_code': None,
    },
    'lithium': {
        'name': '锂',
        'futures_code': 'LC0',
        'futures_name': '碳酸锂主连',
        'futures_source': 'akshare',
        'futures_fallback_code': None,  # 碳酸锂取数失败时的代理ETF/指数；spike 后如需可填
    },
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -v`
Expected: PASS。

- [ ] **Step 6: 删探针 + 提交**

```bash
rm -f scripts/_probe_lithium.py && rtk git add app/config/minerals.py tests/test_minerals.py && rtk git commit -m "feat(矿产): MINERAL_BOARDS 板块配置（铜HG=F/锂LC0）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 期货锚取数 `get_board_futures`（铜 yfinance / 锂 akshare + 降级）

**Files:**
- Create: `app/services/minerals_data.py`
- Test: `tests/test_minerals.py`

**Interfaces:**
- Consumes: `MINERAL_BOARDS`（Task 1）；`FuturesService.get_custom_trend_data(codes: list[str], days: int = 30, cached_only: bool = False) -> {'stocks': [{'stock_code','stock_name','data': [{'date','close',...}]}], 'date_range': {...}}`。
- Produces:
  - `_fetch_lithium_raw(symbol='LC0') -> pandas.DataFrame`（薄包装，便于 monkeypatch）。
  - `fetch_lithium_futures_trend(days: int = 30) -> dict | None`（成功 `{'stock_code','stock_name','data':[{'date','close'}],'source':'akshare'}`，失败 None）。
  - `get_board_futures(commodity: str, days: int = 30) -> {'stock_code','stock_name','data':[...],'futures_name','is_fallback': bool,'note': str | None}`。

- [ ] **Step 1: 写期货取数的失败测试**

Append to `tests/test_minerals.py`:

```python
def test_fetch_lithium_trend_parses_akshare(monkeypatch):
    import pandas as pd
    from app.services import minerals_data as md
    fake = pd.DataFrame({
        '日期': ['2026-06-20', '2026-06-23', '2026-06-24'],
        '开盘价': [68000, 68200, 68500],
        '最高价': [68600, 68700, 69000],
        '最低价': [67800, 68000, 68300],
        '收盘价': [68200, 68500, 68900],
    })
    monkeypatch.setattr(md, '_fetch_lithium_raw', lambda symbol='LC0': fake)
    out = md.fetch_lithium_futures_trend(days=30)
    assert out['stock_code'] == 'LC0'
    assert out['data'][-1] == {'date': '2026-06-24', 'close': 68900.0}


def test_fetch_lithium_trend_returns_none_on_error(monkeypatch):
    from app.services import minerals_data as md
    def boom(symbol='LC0'):
        raise RuntimeError('akshare down')
    monkeypatch.setattr(md, '_fetch_lithium_raw', boom)
    assert md.fetch_lithium_futures_trend() is None


def test_get_board_futures_copper_uses_futures_service(monkeypatch):
    from app.services import minerals_data as md
    monkeypatch.setattr(md.FuturesService, 'get_custom_trend_data',
                        staticmethod(lambda codes, days=30, cached_only=False: {
                            'stocks': [{'stock_code': 'HG=F', 'stock_name': 'COMEX铜',
                                        'data': [{'date': '2026-06-24', 'close': 4.82}]}],
                            'date_range': {}}))
    out = md.get_board_futures('copper', days=30)
    assert out['stock_code'] == 'HG=F'
    assert out['is_fallback'] is False
    assert out['data'][-1]['close'] == 4.82


def test_get_board_futures_lithium_degrades_when_akshare_fails(monkeypatch):
    from app.services import minerals_data as md
    monkeypatch.setattr(md, 'fetch_lithium_futures_trend', lambda days=30: None)
    out = md.get_board_futures('lithium', days=30)
    assert out['is_fallback'] is True
    assert out['data'] == []
    assert '暂缺' in out['note']
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k "lithium or board_futures" -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.minerals_data'`。

- [ ] **Step 3: 写 minerals_data 期货部分**

Create `app/services/minerals_data.py`:

```python
import logging

from app.config.minerals import MINERAL_BOARDS
from app.services.futures import FuturesService

logger = logging.getLogger(__name__)

_LITHIUM_DATE_COL = '日期'
_LITHIUM_CLOSE_COL = '收盘价'


def _fetch_lithium_raw(symbol='LC0'):
    """薄包装 akshare 碳酸锂主连，便于测试 monkeypatch。spike 确认接口名后如有调整改这里。"""
    import akshare as ak
    return ak.futures_main_sina(symbol=symbol)


def fetch_lithium_futures_trend(days=30):
    """碳酸锂期货主连走势；成功返回 dict，失败/空返回 None。"""
    try:
        df = _fetch_lithium_raw()
    except Exception as e:
        logger.warning(f'[矿产] 碳酸锂期货取数失败: {type(e).__name__}: {e}', exc_info=True)
        return None
    if df is None or getattr(df, 'empty', True):
        return None
    date_col = _LITHIUM_DATE_COL if _LITHIUM_DATE_COL in df.columns else df.columns[0]
    close_col = _LITHIUM_CLOSE_COL if _LITHIUM_CLOSE_COL in df.columns else df.columns[-1]
    data = []
    for _, row in df.tail(days + 10).iterrows():
        try:
            close = float(row[close_col])
        except (TypeError, ValueError):
            continue
        data.append({'date': str(row[date_col])[:10], 'close': close})
    if not data:
        return None
    return {'stock_code': 'LC0', 'stock_name': '碳酸锂主连', 'data': data, 'source': 'akshare'}


def _single_from_custom(code, days):
    """走 FuturesService 取单期货/代理走势的 stocks[0]，无数据返回空 data。"""
    res = FuturesService.get_custom_trend_data([code], days)
    stocks = (res or {}).get('stocks') or []
    return stocks[0] if stocks else None


def get_board_futures(commodity, days=30):
    board = MINERAL_BOARDS[commodity]
    name = board['futures_name']
    if board['futures_source'] == 'akshare':
        trend = fetch_lithium_futures_trend(days)
        if trend:
            return {**trend, 'futures_name': name, 'is_fallback': False, 'note': None}
        fb = board.get('futures_fallback_code')
        if fb:
            s = _single_from_custom(fb, days)
            if s:
                return {'stock_code': fb, 'stock_name': s.get('stock_name', fb),
                        'data': s.get('data', []), 'futures_name': name,
                        'is_fallback': True, 'note': '碳酸锂期货数据暂缺，当前为代理指数'}
        return {'stock_code': board['futures_code'], 'stock_name': name, 'data': [],
                'futures_name': name, 'is_fallback': True, 'note': '碳酸锂期货数据暂缺'}
    s = _single_from_custom(board['futures_code'], days)
    data = s.get('data', []) if s else []
    return {'stock_code': board['futures_code'], 'stock_name': name, 'data': data,
            'futures_name': name, 'is_fallback': False, 'note': None}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k "lithium or board_futures" -v`
Expected: PASS（4 个用例）。

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/minerals_data.py tests/test_minerals.py && rtk git commit -m "feat(矿产): 期货锚取数 get_board_futures（铜HG=F/锂akshare+降级）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 板块股票池装配 `get_board_data`（复用 valuations 助手）

**Files:**
- Modify: `app/services/minerals_data.py`
- Test: `tests/test_minerals.py`

**Interfaces:**
- Consumes: 从 `app.routes.valuations` 导入 `load_valuations`、`_fetch_code`、`_extract_price`、`compute_margin`（DRY，不复制实现）；`unified_stock_data_service.get_realtime_prices`。
- Produces:
  - `IMPACT_RANK: dict`（`positive`→0，`negative`→1）。
  - `load_board_stocks(commodity: str, path=None) -> list[dict]`（按 `commodity` 过滤 valuations 原始行）。
  - `get_board_data(commodity: str, days: int = 30, force_refresh: bool = False) -> {'commodity','name','futures': <get_board_futures>,'stocks': [{'stock_code','stock_name','market','impact','current_price','margin_base','trend': [...]}]}`，stocks 按 (impact positive 先, base 安全边际降序) 排序。

- [ ] **Step 1: 写股票池过滤/排序的失败测试**

Append to `tests/test_minerals.py`:

```python
def test_load_board_stocks_filters_by_commodity(tmp_path):
    from app.services.minerals_data import load_board_stocks
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '601899'\n  stock_name: 紫金矿业\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 9.7\n"
        "- stock_code: '002460'\n  stock_name: 赣锋锂业\n  market: A\n  commodity: lithium\n  commodity_impact: positive\n  base: 25.37\n"
        "- stock_code: '600519'\n  stock_name: 贵州茅台\n  market: A\n  base: 1.0\n",
        encoding='utf-8')
    rows = load_board_stocks('copper', path=p)
    assert [r['stock_code'] for r in rows] == ['601899']


def test_get_board_data_sorts_positive_first_then_margin(monkeypatch, tmp_path):
    from app.services import minerals_data as md
    p = tmp_path / 'v.yaml'
    p.write_text(
        "- stock_code: '601899'\n  stock_name: 紫金矿业\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 12.0\n"
        "- stock_code: '000630'\n  stock_name: 铜陵有色\n  market: A\n  commodity: copper\n  commodity_impact: positive\n  base: 20.0\n"
        "- stock_code: '301217'\n  stock_name: 铜冠铜箔\n  market: A\n  commodity: copper\n  commodity_impact: negative\n  base: 30.0\n",
        encoding='utf-8')
    monkeypatch.setattr(md, 'VALUATIONS_PATH', p)
    monkeypatch.setattr(md, 'get_board_futures', lambda commodity, days=30: {'data': [], 'is_fallback': False})
    monkeypatch.setattr(md.FuturesService, 'get_custom_trend_data',
                        staticmethod(lambda codes, days=30, cached_only=False: {'stocks': []}))
    monkeypatch.setattr(md.unified_stock_data_service, 'get_realtime_prices',
                        lambda codes, cache_only=False: {c: {'price': 10.0} for c in codes})
    out = md.get_board_data('copper', days=30)
    # 正面在前，正面组内 base 安全边际(=base/price-1)降序：000630(20/10-1=1.0) > 601899(0.2)，负面 301217 垫底
    assert [s['stock_code'] for s in out['stocks']] == ['000630', '601899', '301217']
    assert out['name'] == '铜'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k "board_stocks or board_data" -v`
Expected: FAIL，`ImportError`/`AttributeError`（`load_board_stocks`/`VALUATIONS_PATH` 未定义）。

- [ ] **Step 3: 给 minerals_data 加股票池装配**

在 `app/services/minerals_data.py` 顶部 import 区追加：

```python
from app.routes.valuations import (
    VALUATIONS_PATH, load_valuations, _fetch_code, _extract_price, compute_margin,
)
from app.services.unified_stock_data import unified_stock_data_service
```

文件末尾追加：

```python
IMPACT_RANK = {'positive': 0, 'negative': 1}


def load_board_stocks(commodity, path=None):
    rows = load_valuations(path or VALUATIONS_PATH)
    return [r for r in rows if r.get('commodity') == commodity]


def get_board_data(commodity, days=30, force_refresh=False):
    board = MINERAL_BOARDS[commodity]
    futures = get_board_futures(commodity, days)
    rows = load_board_stocks(commodity)
    fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}
    codes = list(fetch_map.values())

    prices = {}
    trend_map = {}
    if codes:
        try:
            if force_refresh:
                raw = unified_stock_data_service.get_realtime_prices(codes, force_refresh=True)
            else:
                raw = unified_stock_data_service.get_realtime_prices(codes, cache_only=True)
            prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
        except Exception as e:
            logger.warning(f'[矿产] 取实时价失败，降级: {type(e).__name__}: {e}', exc_info=True)
        try:
            tr = FuturesService.get_custom_trend_data(codes, days)
            trend_map = {s['stock_code']: s.get('data', []) for s in (tr or {}).get('stocks', [])}
        except Exception as e:
            logger.warning(f'[矿产] 取股票走势失败，降级: {type(e).__name__}: {e}', exc_info=True)

    stocks = []
    for r in rows:
        fc = fetch_map[r['stock_code']]
        price = _extract_price(prices.get(r['stock_code']) or {})
        stocks.append({
            'stock_code': r['stock_code'],
            'stock_name': r.get('stock_name'),
            'market': r.get('market'),
            'impact': r.get('commodity_impact'),
            'current_price': price,
            'margin_base': compute_margin(r.get('base'), price),
            'trend': trend_map.get(fc, []),
        })
    stocks.sort(key=lambda s: (IMPACT_RANK.get(s['impact'], 2),
                               s['margin_base'] is None, -(s['margin_base'] or 0)))
    return {'commodity': commodity, 'name': board['name'], 'futures': futures, 'stocks': stocks}
```

> 注：股票走势 `get_custom_trend_data` 用 `_fetch_code` 归一后的代码（港股 4 位 `.HK`），与归一化叠图/sparkline 对齐；若实测港股走势取不到，在本任务调试期确认 `get_custom_trend_data` 对 `.HK` 的解析，必要时改传原始 code 并相应改 `trend_map` 键。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -v`
Expected: 全部 PASS。

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/minerals_data.py tests/test_minerals.py && rtk git commit -m "feat(矿产): get_board_data 板块股票池装配（按 commodity 过滤+影响排序+复用 valuations 助手）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: schema 登记 `commodity` / `commodity_impact` 可选字段

**Files:**
- Modify: `scripts/_docs_schema.py:14-32`（加枚举常量 + 校验）、`scripts/_docs_schema.py:55-124`（`validate_frontmatter` 内追加校验）
- Test: `tests/test_minerals.py`

**Interfaces:**
- Consumes: `_docs_schema.validate_frontmatter(fm: dict, path: Path) -> list[str]`。
- Produces: `COMMODITIES: set`、`COMMODITY_IMPACTS: set`；`validate_frontmatter` 对非法 `commodity`/`commodity_impact` 追加 violation；合法/缺失不报错。

- [ ] **Step 1: 写 schema 校验的失败测试**

Append to `tests/test_minerals.py`:

```python
from pathlib import Path


def test_schema_accepts_valid_commodity_fields():
    import scripts._docs_schema as s
    fm = {'doc_type': 'buffett', 'stock_code': '601899', 'stock_name': '紫金矿业',
          'sector': 'materials', 'subsector': 'nonferrous', 'themes': ['copper'],
          'rating': 'core', 'conviction_date': '2026-04-24', 'thesis': 'x',
          'commodity': 'copper', 'commodity_impact': 'positive'}
    out = s.validate_frontmatter(fm, Path('x.md'))
    assert not [v for v in out if 'commodity' in v]


def test_schema_rejects_bad_commodity():
    import scripts._docs_schema as s
    fm = {'doc_type': 'buffett', 'stock_code': '601899', 'stock_name': '紫金矿业',
          'sector': 'materials', 'subsector': 'nonferrous', 'themes': ['copper'],
          'rating': 'core', 'conviction_date': '2026-04-24', 'thesis': 'x',
          'commodity': 'gold-typo', 'commodity_impact': 'up'}
    out = s.validate_frontmatter(fm, Path('x.md'))
    assert any("commodity 'gold-typo'" in v for v in out)
    assert any("commodity_impact 'up'" in v for v in out)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k schema -v`
Expected: FAIL（`test_schema_rejects_bad_commodity` 无 violation）。

- [ ] **Step 3: 加枚举常量**

在 `scripts/_docs_schema.py` 的 `VALUATION_CURRENCIES` 定义后（约 line 22 后）插入：

```python
COMMODITIES: set[str] = {'copper', 'lithium'}
COMMODITY_IMPACTS: set[str] = {'positive', 'negative'}
```

- [ ] **Step 4: 在 validate_frontmatter 加校验**

在 `scripts/_docs_schema.py` 的 `validate_frontmatter` 内、`return violations` 之前（约 line 123 后）插入：

```python
    if 'commodity' in fm and fm['commodity'] not in COMMODITIES:
        violations.append(f"{p}: commodity '{fm['commodity']}' not in {sorted(COMMODITIES)}")

    if 'commodity_impact' in fm and fm['commodity_impact'] not in COMMODITY_IMPACTS:
        violations.append(
            f"{p}: commodity_impact '{fm['commodity_impact']}' not in {sorted(COMMODITY_IMPACTS)}")
```

- [ ] **Step 5: 运行测试 + 全量 frontmatter lint 确认无回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k schema -v`
Expected: PASS。

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py`
Expected: exit 0（新增字段为可选，未引入违例）。

- [ ] **Step 6: 提交**

```bash
rtk git add scripts/_docs_schema.py tests/test_minerals.py && rtk git commit -m "feat(docs-schema): 登记 commodity/commodity_impact 可选 frontmatter 字段+枚举校验

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 回填存量 12 只锂/铜标的的 `commodity` / `commodity_impact`

**Files:**
- Modify: `docs/stock-analytics/valuations.yaml`（12 条目）
- Modify: 12 个 buffett 档 frontmatter（路径取自各 valuations 条目的 `source_doc`，前缀 `docs/stock-analytics/`）
- Create (throwaway, rm after): `scripts/_backfill_commodity.py`

**回填映射（权威清单）：**

| stock_code | 板块 commodity | commodity_impact | 产业链位置 |
|---|---|---|---|
| 601899 | copper | positive | 铜金矿（上游，铜价↑利好） |
| 00358 | copper | positive | 铜冶炼龙头（上游） |
| 000878 | copper | positive | 铜冶炼（上游） |
| 000630 | copper | positive | 铜冶炼（上游） |
| 000737 | copper | positive | 铜矿/冶炼（上游） |
| 601168 | copper | positive | 多金属矿含铜（上游） |
| 600711 | copper | positive | 铜钴矿（上游） |
| 603993 | copper | positive | 铜钴矿（上游） |
| 301217 | copper | negative | 铜箔加工（下游，铜=成本） |
| 002460 | lithium | positive | 锂盐龙头（上游，锂价↑利好） |
| 300014 | lithium | negative | 电池厂（下游，锂=成本） |
| 00666 | lithium | negative | 电池厂（下游，锂=成本） |

> 紫金/洛阳钼业/盛屯/西部矿业为多金属矿，本期按主要价格弹性归「铜」单板块（金/钴板块为未来扩展，届时再考虑多归属）。

- [ ] **Step 1: 写一次性回填脚本（幂等，双文件同步插入）**

Create `scripts/_backfill_commodity.py`:

```python
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
VAL = ROOT / 'docs' / 'stock-analytics' / 'valuations.yaml'

# stock_code -> (commodity, commodity_impact)
MAPPING = {
    '601899': ('copper', 'positive'), '00358': ('copper', 'positive'),
    '000878': ('copper', 'positive'), '000630': ('copper', 'positive'),
    '000737': ('copper', 'positive'), '601168': ('copper', 'positive'),
    '600711': ('copper', 'positive'), '603993': ('copper', 'positive'),
    '301217': ('copper', 'negative'),
    '002460': ('lithium', 'positive'), '300014': ('lithium', 'negative'),
    '00666': ('lithium', 'negative'),
}


def norm(code):
    return code.replace('.HK', '').lstrip('0') or '0'


def insert_after_sector(block_lines, commodity, impact, indent):
    """在块内第一处 `<indent>sector:` 行后插入两字段；已存在 commodity 则跳过。"""
    if any('commodity:' in ln for ln in block_lines):
        return block_lines, False
    out = []
    inserted = False
    for ln in block_lines:
        out.append(ln)
        if not inserted and re.match(rf'^{indent}sector:', ln):
            out.append(f'{indent}commodity: {commodity}')
            out.append(f'{indent}commodity_impact: {impact}')
            inserted = True
    return out, inserted


def backfill_valuations():
    text = VAL.read_text(encoding='utf-8')
    lines = text.split('\n')
    # 按 `- stock_code:` 切块
    starts = [i for i, ln in enumerate(lines) if re.match(r'^- stock_code:', ln)]
    starts.append(len(lines))
    new_lines = []
    cursor = 0
    touched = []
    for bi in range(len(starts) - 1):
        s, e = starts[bi], starts[bi + 1]
        new_lines.extend(lines[cursor:s])
        block = lines[s:e]
        m = re.match(r"^- stock_code:\s*'?([0-9A-Za-z.]+)'?", block[0])
        code = m.group(1) if m else None
        key = next((k for k in MAPPING if norm(k) == norm(code)), None) if code else None
        if key:
            commodity, impact = MAPPING[key]
            block, did = insert_after_sector(block, commodity, impact, '  ')
            if did:
                touched.append(code)
        new_lines.extend(block)
        cursor = e
    new_lines.extend(lines[cursor:])
    VAL.write_text('\n'.join(new_lines), encoding='utf-8')
    return touched


def backfill_frontmatter():
    import yaml
    text = VAL.read_text(encoding='utf-8')
    rows = yaml.safe_load(text)
    done = []
    for r in rows:
        code = str(r.get('stock_code', ''))
        key = next((k for k in MAPPING if norm(k) == norm(code)), None)
        if not key or not r.get('source_doc'):
            continue
        doc = ROOT / 'docs' / 'stock-analytics' / r['source_doc']
        if not doc.exists():
            print(f'WARN 档不存在: {doc}')
            continue
        commodity, impact = MAPPING[key]
        dt = doc.read_text(encoding='utf-8')
        if re.search(r'^commodity:', dt, re.M):
            continue
        # 在 frontmatter 第一处 `sector:` 行后插入
        def repl(m):
            return m.group(0) + f'\ncommodity: {commodity}\ncommodity_impact: {impact}'
        dt2, n = re.subn(r'^sector:.*$', repl, dt, count=1, flags=re.M)
        if n:
            doc.write_text(dt2, encoding='utf-8')
            done.append(r['source_doc'])
    return done


if __name__ == '__main__':
    print('valuations touched:', backfill_valuations())
    print('frontmatter touched:', backfill_frontmatter())
```

- [ ] **Step 2: 运行回填脚本**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/_backfill_commodity.py`
Expected: 打印 `valuations touched: [...]`（约 12 条）+ `frontmatter touched: [...]`（约 12 档）。若某 code 未命中，检查 valuations 里该 code 的引号/前导 0 形态再调 `MAPPING`。

- [ ] **Step 3: 抽查回填结果 + 跑 lint**

Run: `PYTHONIOENCODING=utf-8 rtk python -c "import yaml; rows=yaml.safe_load(open('docs/stock-analytics/valuations.yaml',encoding='utf-8')); xs=[r for r in rows if r.get('commodity')]; print(len(xs)); [print(r['stock_code'], r['commodity'], r['commodity_impact']) for r in xs]"`
Expected: 打印 12 + 每行 code/commodity/impact 与映射表一致。

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py`
Expected: exit 0。

- [ ] **Step 4: 删脚本 + 提交（精确 add，勿 -A）**

```bash
rm -f scripts/_backfill_commodity.py && rtk git add docs/stock-analytics/valuations.yaml docs/stock-analytics/sectors/materials docs/stock-analytics/sectors/energy && rtk git commit -m "data(矿产): 回填 12 只锂/铜标的 commodity/commodity_impact（valuations+frontmatter）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

> 提交前 `rtk git status` 确认只含本任务的 valuations.yaml + 12 个 buffett 档；若误带并行 session 在写档，按精确路径逐个 add。

---

### Task 6: 路由 `minerals.py` + 蓝图注册

**Files:**
- Create: `app/routes/minerals.py`
- Modify: `app/routes/__init__.py:21`（定义 `minerals_bp`）、`app/routes/__init__.py:23`（import）
- Modify: `app/__init__.py:253`（import 加 `minerals_bp`）、`app/__init__.py:272` 后（`register_blueprint(minerals_bp)`）
- Test: `tests/test_minerals.py`

**Interfaces:**
- Consumes: `app.services.minerals_data.get_board_data`、`app.config.minerals.MINERAL_BOARDS`。
- Produces:
  - `GET /minerals/` → 渲染 `minerals.html`（传 `boards=[{'commodity','name','futures_name'}...]`）。
  - `GET /minerals/api/board/<commodity>?days=30&force=0` → `jsonify(get_board_data(...))`；未知 commodity 返回 404 JSON。

- [ ] **Step 1: 定义蓝图**

Edit `app/routes/__init__.py`：在 `valuations_bp = ...`（line 21）后加：

```python
minerals_bp = Blueprint('minerals', __name__, url_prefix='/minerals')
```

把 line 23 的 import 行尾 `..., valuations` 改为 `..., valuations, minerals`。

- [ ] **Step 2: 注册蓝图**

Edit `app/__init__.py`：line 253 import 行尾 `..., valuations_bp` 改为 `..., valuations_bp, minerals_bp`；在 `app.register_blueprint(valuations_bp)`（line 272）后加：

```python
    app.register_blueprint(minerals_bp)
```

- [ ] **Step 3: 写路由的失败测试**

Append to `tests/test_minerals.py`:

```python
@pytest.fixture(scope='module')
def app_client():
    import os
    os.environ['SCHEDULER_ENABLED'] = '0'
    from app import create_app
    from app.services import unified_stock_data_service
    _orig = unified_stock_data_service.get_realtime_prices
    unified_stock_data_service.get_realtime_prices = lambda codes, force_refresh=False, cache_only=False: {}
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
    unified_stock_data_service.get_realtime_prices = _orig


def test_minerals_index_smoke(app_client):
    resp = app_client.get('/minerals/')
    assert resp.status_code == 200
    html = resp.data.decode('utf-8')
    assert '矿产' in html
    assert '铜' in html and '锂' in html


def test_minerals_api_board_returns_json(app_client, monkeypatch):
    from app.routes import minerals as mod
    monkeypatch.setattr(mod, 'get_board_data', lambda commodity, days=30, force_refresh=False: {
        'commodity': commodity, 'name': '铜',
        'futures': {'stock_code': 'HG=F', 'data': [{'date': '2026-06-24', 'close': 4.82}],
                    'is_fallback': False, 'note': None, 'futures_name': 'COMEX铜'},
        'stocks': [{'stock_code': '601899', 'stock_name': '紫金矿业', 'impact': 'positive',
                    'current_price': 18.2, 'margin_base': -0.46, 'trend': []}]})
    resp = app_client.get('/minerals/api/board/copper')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['futures']['stock_code'] == 'HG=F'
    assert body['stocks'][0]['impact'] == 'positive'


def test_minerals_api_board_unknown_404(app_client):
    resp = app_client.get('/minerals/api/board/uranium')
    assert resp.status_code == 404
```

- [ ] **Step 4: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k "index_smoke or api_board" -v`
Expected: FAIL（模板/路由不存在，index 500 或模板缺失）。

- [ ] **Step 5: 写路由**

Create `app/routes/minerals.py`:

```python
import logging

from flask import render_template, jsonify, request

from app.routes import minerals_bp
from app.config.minerals import MINERAL_BOARDS
from app.services.minerals_data import get_board_data

logger = logging.getLogger(__name__)


@minerals_bp.route('/')
def index():
    boards = [{'commodity': k, 'name': v['name'], 'futures_name': v['futures_name']}
              for k, v in MINERAL_BOARDS.items()]
    return render_template('minerals.html', boards=boards)


@minerals_bp.route('/api/board/<commodity>')
def api_board(commodity):
    if commodity not in MINERAL_BOARDS:
        return jsonify({'error': f'unknown commodity: {commodity}'}), 404
    days = request.args.get('days', '30')
    days = int(days) if days.isdigit() else 30
    force = request.args.get('force', '0') == '1'
    try:
        data = get_board_data(commodity, days=days, force_refresh=force)
    except Exception as e:
        logger.warning(f'[矿产] 板块 {commodity} 装配失败: {type(e).__name__}: {e}', exc_info=True)
        return jsonify({'commodity': commodity, 'name': MINERAL_BOARDS[commodity]['name'],
                        'futures': {'data': [], 'is_fallback': True, 'note': '数据获取失败'},
                        'stocks': []})
    return jsonify(data)
```

> Step 5 依赖 Task 7 的 `minerals.html` 才能让 `index` 渲染成功；本任务先建路由 + 一个最小占位模板让 smoke 过，Task 7 再写完整模板。最小占位：见 Step 6。

- [ ] **Step 6: 建最小占位模板让 index smoke 过**

Create `app/templates/minerals.html`（占位，Task 7 覆盖为完整版）:

```html
{% extends "base.html" %}
{% block content %}
<h2>矿产看板</h2>
{% for b in boards %}<section data-commodity="{{ b.commodity }}"><h3>{{ b.name }} · {{ b.futures_name }}</h3></section>{% endfor %}
{% endblock %}
```

- [ ] **Step 7: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -v`
Expected: 全部 PASS。

- [ ] **Step 8: 提交**

```bash
rtk git add app/routes/minerals.py app/routes/__init__.py app/__init__.py app/templates/minerals.html tests/test_minerals.py && rtk git commit -m "feat(矿产): /minerals 路由+蓝图注册+占位模板

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `minerals.html` 完整模板（ECharts 期货图 + 归一化叠图 + 影响徽章列表）

**Files:**
- Modify: `app/templates/minerals.html`（覆盖占位为完整版）
- Modify: `app/templates/base.html:33`（导航加「矿产看板」入口）
- Test: `tests/test_minerals.py`

**Interfaces:**
- Consumes: `GET /minerals/api/board/<commodity>` 的 JSON（`futures.data[].close`、`stocks[].{impact,current_price,margin_base,trend}`）。
- Produces: 每板块一个区块，含期货走势图 canvas、归一化联动图 canvas、股票列表（影响徽章 🟢/🔴 + 现价 + Base 安全边际）。

- [ ] **Step 1: 写模板结构的失败测试**

Append to `tests/test_minerals.py`:

```python
def test_minerals_template_has_charts_and_impact(app_client):
    html = app_client.get('/minerals/').data.decode('utf-8')
    assert 'echarts' in html.lower()
    assert 'id="refresh-btn"' in html
    assert 'data-commodity="copper"' in html and 'data-commodity="lithium"' in html
    assert 'futures-chart' in html          # 期货走势图容器
    assert 'overlay-chart' in html          # 归一化联动图容器
    assert 'impact-positive' in html and 'impact-negative' in html  # 徽章样式类
    assert '/minerals/api/board/' in html   # 前端按板块拉数据


def test_base_nav_has_minerals_link(app_client):
    html = app_client.get('/valuations/').data.decode('utf-8')
    assert "url_for('minerals.index')" in html or '/minerals/' in html
    assert '矿产' in html
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -k "template_has_charts or nav_has_minerals" -v`
Expected: FAIL（占位模板无 echarts/容器；nav 无矿产链接）。

- [ ] **Step 3: 加导航入口**

Edit `app/templates/base.html`：在 line 29 `走势看板` 链接后加一行（保持缩进与同级 `<a class="nav-link">` 一致）：

```html
                <a class="nav-link" href="{{ url_for('minerals.index') }}">矿产看板</a>
```

- [ ] **Step 4: 写完整模板**

覆盖 `app/templates/minerals.html`：

```html
{% extends "base.html" %}
{% block content %}
<div class="container-fluid">
  <div class="d-flex justify-content-between align-items-center my-3">
    <h2 class="mb-0">矿产看板</h2>
    <div>
      <div class="btn-group btn-group-sm me-2" role="group">
        <button type="button" class="btn btn-outline-secondary active" data-days="7">7天</button>
        <button type="button" class="btn btn-outline-secondary" data-days="30">30天</button>
      </div>
      <button id="refresh-btn" class="btn btn-sm btn-primary">刷新</button>
    </div>
  </div>

  {% for b in boards %}
  <section class="mineral-board mb-5" data-commodity="{{ b.commodity }}">
    <h4 class="board-title"><span class="badge bg-dark">{{ b.name }}</span>
      <span class="futures-head text-muted">{{ b.futures_name }}</span></h4>
    <div class="row">
      <div class="col-lg-6"><div class="futures-chart" id="futures-{{ b.commodity }}" style="height:280px;"></div></div>
      <div class="col-lg-6"><div class="overlay-chart" id="overlay-{{ b.commodity }}" style="height:280px;"></div></div>
    </div>
    <div class="table-responsive mt-2">
      <table class="table table-sm align-middle">
        <thead><tr><th>影响</th><th>股票</th><th>走势</th><th class="text-end">现价</th><th class="text-end">Base安全边际</th></tr></thead>
        <tbody id="rows-{{ b.commodity }}"></tbody>
      </table>
    </div>
  </section>
  {% endfor %}
</div>

<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
const BOARDS = {{ boards | map(attribute='commodity') | list | tojson }};
let DAYS = 7;

function fmtPct(x){ return x==null ? '—' : (x>=0?'+':'') + (x*100).toFixed(1) + '%'; }
function fmtPrice(x){ return x==null ? '—' : Number(x).toFixed(2); }

function normalize(series){  // 各序列首值=100
  if(!series.length) return [];
  const base = series[0];
  return base ? series.map(v => v/base*100) : series;
}

function impactBadge(impact){
  if(impact==='positive') return '<span class="badge impact-positive bg-success">🟢正面</span>';
  if(impact==='negative') return '<span class="badge impact-negative bg-danger">🔴负面</span>';
  return '<span class="badge bg-secondary">未标注</span>';
}

function sparkline(cell, trend){
  const closes = (trend||[]).map(d=>d.close).filter(v=>v!=null);
  if(closes.length < 2){ cell.textContent='—'; return; }
  const c = echarts.init(cell, null, {height:32, width:90});
  const up = closes[closes.length-1] >= closes[0];
  c.setOption({grid:{left:0,right:0,top:2,bottom:2}, xAxis:{show:false,type:'category'},
    yAxis:{show:false,scale:true}, series:[{type:'line',data:closes,showSymbol:false,
    lineStyle:{width:1.2,color:up?'#198754':'#dc3545'}}]});
}

async function loadBoard(commodity, force){
  const url = `/minerals/api/board/${commodity}?days=${DAYS}` + (force?'&force=1':'');
  const data = await (await fetch(url)).json();
  // 期货图
  const fEl = document.getElementById('futures-'+commodity);
  const fdata = (data.futures && data.futures.data) || [];
  const fChart = echarts.init(fEl);
  const ftitle = (data.futures && data.futures.futures_name || '') + (data.futures && data.futures.is_fallback ? '（'+(data.futures.note||'代理')+'）' : '');
  fChart.setOption({title:{text:ftitle,textStyle:{fontSize:13}}, tooltip:{trigger:'axis'},
    grid:{left:48,right:12,top:36,bottom:28},
    xAxis:{type:'category',data:fdata.map(d=>d.date)},
    yAxis:{type:'value',scale:true},
    series:[{type:'line',data:fdata.map(d=>d.close),showSymbol:false,name:data.futures.stock_code}]});
  // 归一化叠图：期货 + 正面股
  const oEl = document.getElementById('overlay-'+commodity);
  const oChart = echarts.init(oEl);
  const dates = fdata.map(d=>d.date);
  const series = [{type:'line',name:'期货',showSymbol:false,data:normalize(fdata.map(d=>d.close)),lineStyle:{width:2}}];
  (data.stocks||[]).filter(s=>s.impact==='positive').forEach(s=>{
    const closes=(s.trend||[]).map(d=>d.close);
    if(closes.length) series.push({type:'line',name:s.stock_name,showSymbol:false,data:normalize(closes)});
  });
  oChart.setOption({title:{text:'期货 vs 正面股（归一化=100）',textStyle:{fontSize:13}},
    tooltip:{trigger:'axis'}, legend:{type:'scroll',top:0,right:0},
    grid:{left:40,right:12,top:36,bottom:28}, xAxis:{type:'category',data:dates},
    yAxis:{type:'value',scale:true}, series});
  // 列表
  const tb = document.getElementById('rows-'+commodity);
  tb.innerHTML='';
  (data.stocks||[]).forEach(s=>{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td>${impactBadge(s.impact)}</td>`+
      `<td>${s.stock_name||''} <small class="text-muted">${s.stock_code}</small></td>`+
      `<td class="spark"></td>`+
      `<td class="text-end">${fmtPrice(s.current_price)}</td>`+
      `<td class="text-end">${fmtPct(s.margin_base)}</td>`;
    tb.appendChild(tr);
    sparkline(tr.querySelector('.spark'), s.trend);
  });
}

function loadAll(force){ BOARDS.forEach(c=>loadBoard(c, force)); }

document.querySelectorAll('[data-days]').forEach(btn=>btn.addEventListener('click',()=>{
  document.querySelectorAll('[data-days]').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active'); DAYS=parseInt(btn.dataset.days,10); loadAll(false);
}));
document.getElementById('refresh-btn').addEventListener('click',()=>loadAll(true));
loadAll(false);
</script>
{% endblock %}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py -v`
Expected: 全部 PASS。

- [ ] **Step 6: 人工冒烟（可选但推荐）**

Run: `SCHEDULER_ENABLED=0 rtk python run.py`，浏览器开 `http://127.0.0.1:5000/minerals/`，确认铜/锂两板块各显示期货图 + 归一化叠图 + 影响徽章列表；锂期货取不到时显「碳酸锂期货数据暂缺」标注且不报错。看完 Ctrl-C。

- [ ] **Step 7: 提交**

```bash
rtk git add app/templates/minerals.html app/templates/base.html tests/test_minerals.py && rtk git commit -m "feat(矿产): minerals.html 完整模板（期货图+归一化叠图+影响徽章）+导航入口

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 扩展 `stock-deep-redo` / `buffett` skill 产出 commodity 字段

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`（Phase B frontmatter 写入步骤 ~line 73-74、Phase C「同步 valuations.yaml」步骤 ~line 100）
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`（frontmatter 字段集说明处）
- Modify: `.claude/skills/buffett/SKILL.md`（输出约定处）

**Interfaces:**
- Produces: skill 指令——分析矿产/商品标的时，由产业链位置判定并写入 `commodity` + `commodity_impact` 到 frontmatter 与 valuations.yaml 条目。

- [ ] **Step 1: 在 stock-deep-redo SKILL.md 加产出约定**

在 `.claude/skills/stock-deep-redo/SKILL.md` 的「同步 valuations.yaml」步骤（Phase C，约 line 100）下追加一段（与既有列表风格一致）：

```markdown
- **矿产/商品标的加 `commodity` 字段**：若标的属铜/锂等矿产板块（受某商品期货价格驱动），在 frontmatter 与 valuations.yaml 条目**同步**写：
  - `commodity`: `copper` | `lithium`（枚举见 `scripts/_docs_schema.py:COMMODITIES`；非矿产标的不写）
  - `commodity_impact`: `positive`（上游资源/矿/锂盐——商品涨价利好）| `negative`（下游加工/电池/消费——商品涨价是成本）
  - 判据来自产业链位置（与 `.claude/rules/docs-and-portfolio.md`「电池厂是锂买方，锂价涨=成本压力」一致）；本字段驱动 `/minerals` 矿产看板的板块归属与影响徽章。
```

- [ ] **Step 2: 在 playbook.md frontmatter 字段集补充**

在 `.claude/skills/stock-deep-redo/references/playbook.md` 的 frontmatter 字段集说明里，于可选字段处加一行：

```markdown
- `commodity` / `commodity_impact`（可选，仅矿产/商品标的）：板块归属 `copper|lithium` + 影响方向 `positive|negative`（上游=positive，下游买方=negative），同步写 valuations.yaml，供 `/minerals` 看板使用。
```

- [ ] **Step 3: 在 buffett SKILL.md 输出约定加提示**

在 `.claude/skills/buffett/SKILL.md` 的输出/收尾约定处加一行（若该 SKILL 无明确「输出约定」节，则加在 frontmatter 相关说明附近）：

```markdown
- 矿产/商品标的（受铜/锂等商品期货价格驱动）：frontmatter 加 `commodity`（`copper|lithium`）+ `commodity_impact`（上游资源=`positive`/下游买方=`negative`），供 `/minerals` 看板使用。
```

- [ ] **Step 4: 校验 skill 文本含新字段约定**

Run: `PYTHONIOENCODING=utf-8 rtk python -c "import pathlib; t=pathlib.Path('.claude/skills/stock-deep-redo/SKILL.md').read_text(encoding='utf-8'); assert 'commodity_impact' in t and 'commodity' in t; print('ok skill')"`
Expected: 打印 `ok skill`。

- [ ] **Step 5: 提交**

```bash
rtk git add .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md .claude/skills/buffett/SKILL.md && rtk git commit -m "feat(skill): stock-deep-redo/buffett 收尾产出 commodity/commodity_impact 字段

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 全量回归 + 收尾

**Files:** 无新增（验证任务）

- [ ] **Step 1: 跑矿产测试 + 估值测试（确认未回归既有）**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_minerals.py tests/test_valuations.py -v > /tmp/mineral_test.txt 2>&1; grep -E "passed|failed|error" /tmp/mineral_test.txt`
Expected: 全 passed，无 failed/error（crawl4ai 进度条走 stdout，故重定向到文件再 grep）。

- [ ] **Step 2: 跑 frontmatter lint**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py`
Expected: exit 0。

- [ ] **Step 3: 确认无遗留一次性脚本**

Run: `rtk git status --porcelain scripts/`
Expected: 空（`_probe_lithium.py` / `_backfill_commodity.py` 已删，未入库）。

- [ ] **Step 4: 最终对账**

逐条核对验收标准（见 spec §11）：`/minerals` 两板块、影响徽章正确、铜锚 HG=F、锂锚降级不报错、现价/Base 边际与 `/valuations` 一致、skill 产出字段、测试+lint 通过。

---

## 自检记录（spec 覆盖核对）

- spec §3 新字段 → Task 4（schema）+ Task 5（回填）✓
- spec §4 期货锚 + 锂数据风险 → Task 1（spike+配置）+ Task 2（取数+降级）✓
- spec §5 路由/服务 → Task 2/3（service）+ Task 6（route）✓
- spec §6 布局（上下堆叠/期货图/叠图/列表）→ Task 7 ✓
- spec §7 影响可视化（徽章+归一化叠图）→ Task 7 ✓
- spec §8 skill 扩展 → Task 8 ✓
- spec §9 边界/错误（取数失败降级/缺字段不阻塞）→ Task 2（futures 降级）+ Task 3（price/trend try-except）+ Task 6（route try-except）+ Task 7（前端「未标注」/「暂缺」）✓
- spec §10 文件清单 → 全覆盖（minerals 配置/服务/路由/模板/注册/nav/schema/回填/skill）✓
- spec §11 验收 → Task 9 ✓
- DRY：minerals_data 复用 valuations 的 `load_valuations/_fetch_code/_extract_price/compute_margin`，不复制 ✓
