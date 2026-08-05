# Volume 单位归一集中化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把散落在 `unified_stock_data.py` 约 20 个 fetch 落点的 volume 单位转换收敛到单个 `_normalize_volume()` helper，修掉新浪批量走势与 yfinance A 股兜底的漏归一缺陷。

**Architecture:** 新增 `VOLUME_SOURCE_UNITS` 映射（源 → 原生单位）与 `_normalize_volume(raw, source, market)` 纯函数；所有落点改为显式声明数据源名；用 AST 静态断言禁止绕过 helper 直接给 `'volume'` 赋值，保证新增数据源必须登记单位。

**Tech Stack:** Python 3 / Flask / pytest / `ast` 标准库

## Global Constraints

- 单位契约不变：**A 股 volume = 手，港股 / 美股 volume = 股**
- `market != 'A'` 时 `_normalize_volume` **一律原样返回**，不做任何转换
- `source` 未在 `VOLUME_SOURCE_UNITS` 中登记时抛 `KeyError`，不设默认分支
- 改动落在 `app/` 代码，按 `.claude/rules/dev-environment.md` 分支策略必须开**独立 git worktree**，不在 main 直接改
- 所有 git 命令前加 `rtk`；`git add` 与 `git commit` 必须在同一条命令链里（并行 session 会抢 index）
- 测试命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`（env 赋值必须在 `rtk` 之前）
- 本计划中的行号是撰写时快照，实施时**一律按函数名定位**，不要按行号跳转

---

### Task 0: 建立隔离 worktree

**Files:**
- 无代码改动

- [ ] **Step 1: 从 main 建 worktree**

```bash
rtk git -C D:/Git/stock worktree add ../stock-volume-unit -b fix/volume-unit-normalization main
```

- [ ] **Step 2: 确认分支起点正确**

```bash
rtk git -C D:/Git/stock-volume-unit log --oneline -1
```

Expected: 输出 main 的最新 commit（含 `4015d5c docs(spec): volume 单位归一集中化设计...` 或更新）。

后续所有任务的路径均以 `D:/Git/stock-volume-unit` 为根。worktree 里 `.git` 是文件不是目录，`git commit -F .git/MSG.txt` 会失败——本计划的 commit 全部用 `-m`。

---

### Task 1: `_normalize_volume` helper 与单元测试

**Files:**
- Modify: `app/services/unified_stock_data.py`（文件顶部，`VOLUME_UNIT_SCHEMA_VERSION` 附近）
- Test: `tests/test_volume_alert_unit_consistency.py`

**Interfaces:**
- Produces: 模块级常量 `VOLUME_SOURCE_UNITS: dict[str, str]`；模块级函数 `_normalize_volume(raw, source: str, market: str) -> int | None`。后续 Task 2–5 全部调用这两个符号。

- [ ] **Step 1: 删除被取代的正则契约测试**

`tests/test_volume_alert_unit_consistency.py` 中删除这 5 个函数（它们断言的是行内 `// 100` 写法，helper 上线后这些写法不再存在）：

- `test_sina_daily_hist_volume_divides_100`
- `test_tencent_fqkline_volume_not_divided`
- `test_sina_spot_volume_divides_100`
- `test_tencent_realtime_volume_not_divided`
- `test_eastmoney_hist_volume_not_divided`

保留 `# ============ 1. 单位归一化源码契约锁定 ============` 分节标题，下一步在其下写新测试。

- [ ] **Step 2: 写失败的 helper 单元测试**

在该分节下加入：

```python
import math

from app.services.unified_stock_data import VOLUME_SOURCE_UNITS, _normalize_volume


def test_lots_source_passthrough_for_a_share():
    """原生「手」的源，A 股不做转换"""
    assert _normalize_volume(25060238, 'tencent_qt', 'A') == 25060238
    assert _normalize_volume('17534731', 'tencent_fqkline', 'A') == 17534731
    assert _normalize_volume(12345, 'eastmoney_ak_hist', 'A') == 12345


def test_shares_source_divides_100_for_a_share():
    """原生「股」的源，A 股必须 // 100 归一到「手」"""
    assert _normalize_volume(2506023803, 'sina_daily', 'A') == 25060238
    assert _normalize_volume(1753473070, 'sina_daily', 'A') == 17534730
    assert _normalize_volume(2506023803, 'yfinance', 'A') == 25060238
    assert _normalize_volume(1234567, 'sina_spot', 'A') == 12345


def test_non_a_market_always_passthrough():
    """港股/美股契约就是「股」，任何源都原样返回"""
    assert _normalize_volume(2506023803, 'yfinance', 'US') == 2506023803
    assert _normalize_volume(2506023803, 'yfinance', 'HK') == 2506023803
    assert _normalize_volume(9876543, 'tencent_qt', 'HK') == 9876543


def test_empty_values_return_none():
    """空值语义：调用点自行决定填 0 还是 None"""
    assert _normalize_volume(None, 'sina_daily', 'A') is None
    assert _normalize_volume('', 'sina_daily', 'A') is None
    assert _normalize_volume(float('nan'), 'yfinance', 'A') is None
    assert _normalize_volume('abc', 'yfinance', 'A') is None


def test_zero_is_preserved_not_none():
    """0 是合法成交量（停牌/一字板），不能被当成空值"""
    assert _normalize_volume(0, 'sina_daily', 'A') == 0
    assert _normalize_volume(0.0, 'tencent_qt', 'A') == 0


def test_unregistered_source_raises_keyerror():
    """未登记的源必须炸，不允许静默走默认单位"""
    with pytest.raises(KeyError):
        _normalize_volume(100, 'some_new_source', 'A')


def test_all_registered_units_are_valid():
    """映射表只允许 lots / shares 两种取值"""
    assert set(VOLUME_SOURCE_UNITS.values()) <= {'lots', 'shares'}
    assert len(VOLUME_SOURCE_UNITS) == 12
```

- [ ] **Step 3: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`
Expected: 收集阶段 `ImportError: cannot import name 'VOLUME_SOURCE_UNITS'`

- [ ] **Step 4: 实现 helper**

在 `app/services/unified_stock_data.py` 中，把第 33-34 行

```python
# 缓存 volume 单位契约版本；变更契约时 bump 触发启动时全量清理
VOLUME_UNIT_SCHEMA_VERSION = 3
```

替换为：

```python
# 缓存 volume 单位契约版本；变更契约时 bump 触发启动时全量清理
VOLUME_UNIT_SCHEMA_VERSION = 4


# 各数据源 volume 原生单位（'lots'=手 / 'shares'=股）。
# 单位标注以 A 股口径为准——港股/美股契约本就是「股」，_normalize_volume 对非 A 市场一律原样返回，
# 故 tencent_qt 之类「A 股为手、港股为股」的源在此登记为 'lots' 不会影响港股。
VOLUME_SOURCE_UNITS = {
    'tencent_qt': 'lots',           # qt.gtimg.cn q= 接口 [6]
    'tencent_fqkline': 'lots',      # appstock fqkline 日K row[5]
    'tencent_mkline': 'lots',       # appstock mkline 分钟K row[5]
    'sina_spot': 'shares',          # ak.stock_zh_a_spot
    'sina_daily': 'shares',         # ak.stock_zh_a_daily
    'eastmoney_ak_hist': 'lots',    # ak.stock_zh_a_hist
    'eastmoney_push2his': 'lots',   # push2his.eastmoney.com kline
    'eastmoney_spot': 'lots',       # ak.stock_zh_a_spot_em
    'eastmoney_hist_min': 'lots',   # ak.stock_zh_a_hist_min_em
    'eastmoney_intraday': 'lots',   # ak.stock_intraday_em 的「手数」列
    'etf_fund_hist': 'lots',        # ak.fund_etf_hist_em
    'yfinance': 'shares',           # yfinance Volume
}


def _normalize_volume(raw, source: str, market: str):
    """把各源的 volume 归一到契约单位：A 股=手，港股/美股=股。

    source 未登记时抛 KeyError —— 宁可启动即失败，也不静默按错误单位入库。
    raw 为空/非数值时返回 None，由调用点决定填 0 还是 None。
    """
    unit = VOLUME_SOURCE_UNITS[source]
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if math.isnan(val):
        return None
    if market == 'A' and unit == 'shares':
        return int(val) // 100
    return int(val)
```

同时在文件顶部 import 区加入 `import math`（`import logging` 之后），并把模块 docstring 第 9 行

```
单位契约：所有 A 股 OHLC/realtime volume 字段统一为"手"（腾讯/新浪源解析时 /100 归一）。
```

改为

```
单位契约：A 股 OHLC/realtime volume 统一为"手"，港股/美股为"股"。
各源原生单位登记在 VOLUME_SOURCE_UNITS，转换一律走 _normalize_volume()，禁止在落点内联换算。
```

- [ ] **Step 5: 更新 schema version 断言**

把 `test_schema_version_constant_defined` 中的 `assert VOLUME_UNIT_SCHEMA_VERSION == 3` 改为 `== 4`。

- [ ] **Step 6: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/unified_stock_data.py tests/test_volume_alert_unit_consistency.py && rtk git commit -m "feat(stock-data): 新增 VOLUME_SOURCE_UNITS + _normalize_volume 单点归一,bump SCHEMA_VERSION=4"
```

---

### Task 2: 接入实时价格落点（5 处，含 1 处缺陷）

**Files:**
- Modify: `app/services/unified_stock_data.py` — `_fetch_realtime_prices.fetch_single`、`_fetch_a_share_prices.fetch_from_eastmoney` / `.fetch_from_sina` / `.fetch_from_yfinance`、`_fetch_from_tencent`
- Test: `tests/test_volume_alert_unit_consistency.py`

**Interfaces:**
- Consumes: `_normalize_volume(raw, source, market)`（Task 1）

- [ ] **Step 1: 写失败的回归测试**

在 `tests/test_volume_alert_unit_consistency.py` 末尾新增分节：

```python
# ============ 4. 落点接入回归 ============

def test_tencent_qt_parse_returns_lots(monkeypatch):
    """腾讯 q= 接口解析后 A 股 volume 为「手」（原值即手，不得再除）"""
    from app.services import unified_stock_data as usd

    raw_line = 'v_sz000725="51~京东方A~000725~5.97~5.63~5.59~25060238~0~0~5.97~' + '~'.join(['0'] * 60) + '";'

    class FakeResp:
        text = raw_line
        encoding = 'gbk'
        status_code = 200

    # requests 在 unified_stock_data 中是函数内 import（无模块级属性），
    # 必须 patch requests 模块本身，不能 patch usd.requests
    monkeypatch.setattr('requests.get', lambda *a, **k: FakeResp())

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    result = service._fetch_from_tencent(['000725'], '2026-08-05 16:30:00')

    assert result['000725']['volume'] == 25060238
```

若 `_fetch_from_tencent` 的字段索引要求与上述构造串不符（字段数不足 35 会被跳过），按实际实现调整占位字段数量，保持 `fields[6] == '25060238'`。

- [ ] **Step 2: 运行确认当前行为**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py::test_tencent_qt_parse_returns_lots -v`
Expected: PASS（腾讯这条本来就对，此测试是接入后的防退化基线；若 FAIL 说明构造串字段布局不对，先修测试）

- [ ] **Step 3: 改写 5 个落点**

① `_fetch_realtime_prices.fetch_single`（`market` 变量已在函数内定义）：

```python
                        'volume': int(latest['Volume']) if not pd.isna(latest['Volume']) else None,
```
→
```python
                        'volume': _normalize_volume(latest['Volume'], 'yfinance', market),
```

② `_fetch_a_share_prices.fetch_from_eastmoney`（A 股专用）：

```python
                            'volume': int(row['成交量']) if row.get('成交量') else None,
```
→
```python
                            'volume': _normalize_volume(row.get('成交量'), 'eastmoney_spot', 'A'),
```

③ `_fetch_a_share_prices.fetch_from_sina`（A 股专用，删掉上方那行单位注释）：

```python
                            # 新浪 stock_zh_a_spot 返回"股"，/100 归一到"手"（与腾讯/东财对齐）
                            'volume': int(row['成交量']) // 100 if row.get('成交量') else None,
```
→
```python
                            'volume': _normalize_volume(row.get('成交量'), 'sina_spot', 'A'),
```

④ `_fetch_a_share_prices.fetch_from_yfinance.fetch_single`（**缺陷点**，A 股专用）：

```python
                        'volume': int(latest['Volume']) if not pd.isna(latest['Volume']) else None,
```
→
```python
                        'volume': _normalize_volume(latest['Volume'], 'yfinance', 'A'),
```

⑤ `_fetch_from_tencent`——把中间变量 `raw_vol` / `vol` 整体去掉（保留 `market` 那行），使 `'volume'` 的值就是 helper 调用本身（Task 6 的 AST 断言要求如此）：

```python
                    market = self._identify_market(original_code) or 'A'
                    raw_vol = float(fields[6]) if fields[6] else None
                    # 腾讯 [6] A股原生"手"、港股原生"股"（成交额[37]交叉验证），均原样保留
                    vol = int(raw_vol) if raw_vol is not None else None
                    result[original_code] = {
                        'code': original_code,
                        'name': fields[1],
                        'current_price': float(fields[3]) if fields[3] else None,
                        'prev_close': float(fields[4]) if fields[4] else None,
                        'open': float(fields[5]) if fields[5] else None,
                        'volume': vol,
```
→
```python
                    market = self._identify_market(original_code) or 'A'
                    result[original_code] = {
                        'code': original_code,
                        'name': fields[1],
                        'current_price': float(fields[3]) if fields[3] else None,
                        'prev_close': float(fields[4]) if fields[4] else None,
                        'open': float(fields[5]) if fields[5] else None,
                        'volume': _normalize_volume(fields[6], 'tencent_qt', market),
```

- [ ] **Step 4: 运行全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/pytest_t2.txt 2>&1; grep -E "passed|failed" /tmp/pytest_t2.txt`
Expected: 无 failed（crawl4ai 进度条走 stdout，必须重定向到文件再 grep，否则摘要会被顶掉）

- [ ] **Step 5: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/unified_stock_data.py tests/test_volume_alert_unit_consistency.py && rtk git commit -m "fix(stock-data): 实时价格 5 个落点接入 _normalize_volume,修 yfinance A 股兜底漏归一"
```

---

### Task 3: 接入分时数据落点（4 处）

**Files:**
- Modify: `app/services/unified_stock_data.py` — `_fetch_intraday_a_share_tencent`、`_fetch_intraday_a_share_hist`、`_fetch_intraday_a_share_tick`、`_fetch_intraday_yfinance`

**Interfaces:**
- Consumes: `_normalize_volume`（Task 1）

- [ ] **Step 1: 改写 4 个落点**

① `_fetch_intraday_a_share_tencent`（A 股专用）：

```python
                    'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0,
```
→
```python
                    'volume': (_normalize_volume(row[5] if len(row) > 5 else None, 'tencent_mkline', 'A') or 0),
```

② `_fetch_intraday_a_share_hist`（A 股专用）：

```python
                    'volume': int(row['成交量'])
```
→
```python
                    'volume': (_normalize_volume(row.get('成交量'), 'eastmoney_hist_min', 'A') or 0)
```

③ `_fetch_intraday_a_share_tick`（A 股专用，源列名是「手数」）：

```python
                    'volume': int(row['volume'])
```
→
```python
                    'volume': (_normalize_volume(row.get('volume'), 'eastmoney_intraday', 'A') or 0)
```

④ `_fetch_intraday_yfinance`（跨市场）：

```python
                    'volume': int(row['Volume'])
```
→
```python
                    'volume': (_normalize_volume(row.get('Volume'), 'yfinance', self._identify_market(code)) or 0)
```

- [ ] **Step 2: 运行全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/pytest_t3.txt 2>&1; grep -E "passed|failed" /tmp/pytest_t3.txt`
Expected: 无 failed

- [ ] **Step 3: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/unified_stock_data.py && rtk git commit -m "refactor(stock-data): 分时数据 4 个落点接入 _normalize_volume"
```

---

### Task 4: 接入增量走势落点（5 处，含 1 处缺陷）

**Files:**
- Modify: `app/services/unified_stock_data.py` — `_fetch_incremental_trend_data`（ETF 分支 / `fetch_from_eastmoney` / `fetch_from_sina` / `fetch_from_tencent` / yfinance 分支）

**Interfaces:**
- Consumes: `_normalize_volume`（Task 1）

该函数内 `market = self._identify_market(stock_code)` 已在开头定义，5 处全部直接用 `market`。

- [ ] **Step 1: 改写 5 个落点**

① ETF 分支：

```python
                            'volume': int(row['成交量']) if row.get('成交量') else 0
```
→
```python
                            'volume': (_normalize_volume(row.get('成交量'), 'etf_fund_hist', market) or 0)
```

② `fetch_from_eastmoney`：

```python
                        'volume': int(row['成交量']) if row.get('成交量') else 0
```
→
```python
                        'volume': (_normalize_volume(row.get('成交量'), 'eastmoney_ak_hist', market) or 0)
```

③ `fetch_from_sina`（删掉上方单位注释）：

```python
                        # 新浪 stock_zh_a_daily 返回"股"，/100 归一到"手"
                        'volume': int(row['volume']) // 100 if row.get('volume') else 0
```
→
```python
                        'volume': (_normalize_volume(row.get('volume'), 'sina_daily', market) or 0)
```

④ `fetch_from_tencent`（删掉上方单位注释）：

```python
                        # 腾讯 fqkline 日K row[5] 原生"手"（与东财逐日相等），原样保留
                        'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0
```
→
```python
                        'volume': (_normalize_volume(row[5] if len(row) > 5 else None, 'tencent_fqkline', market) or 0)
```

⑤ yfinance 分支（**缺陷点**）：

```python
                    'volume': int(volume) if not pd.isna(volume) else 0
```
→
```python
                    'volume': (_normalize_volume(volume, 'yfinance', market) or 0)
```

- [ ] **Step 2: 运行全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/pytest_t4.txt 2>&1; grep -E "passed|failed" /tmp/pytest_t4.txt`
Expected: 无 failed

- [ ] **Step 3: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/unified_stock_data.py && rtk git commit -m "fix(stock-data): 增量走势 5 个落点接入 _normalize_volume,修 yfinance 分支漏归一"
```

---

### Task 5: 接入批量走势落点（7 处，含本次事故点）

**Files:**
- Modify: `app/services/unified_stock_data.py` — `_fetch_trend_from_etf`、`_fetch_trend_from_eastmoney`、`_fetch_trend_from_sina`、`_fetch_trend_from_tencent`、`_fetch_trend_from_eastmoney_direct`、`_fetch_trend_from_yfinance`、`_parse_yf_dataframe`
- Test: `tests/test_volume_alert_unit_consistency.py`

**Interfaces:**
- Consumes: `_normalize_volume`（Task 1）

- [ ] **Step 1: 写失败的事故回归测试**

在 `# ============ 4. 落点接入回归 ============` 分节内追加。这条锁定本次线上事故：新浪批量走势必须归一到「手」。

```python
def test_sina_batch_trend_normalizes_shares_to_lots(monkeypatch):
    """回归 2026-08-05 事故：_fetch_trend_from_sina 曾漏 //100，
    京东方A 被推成 2,506,023,803（股）而非 25,060,238（手）"""
    import pandas as pd
    from datetime import date
    from app.services import unified_stock_data as usd

    df = pd.DataFrame(
        {
            'open': [5.46, 5.59],
            'high': [5.66, 6.03],
            'low': [5.43, 5.58],
            'close': [5.63, 5.97],
            'volume': [1753473070.0, 2506023803.0],
        },
        index=pd.to_datetime(['2026-08-04', '2026-08-05']),
    )

    class FakeAk:
        @staticmethod
        def stock_zh_a_daily(**kwargs):
            return df

    monkeypatch.setattr('app.services.akshare_client.ak', FakeAk, raising=False)

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    results = service._fetch_trend_from_sina(
        ['000725'], 5, date(2026, 7, 30), date(2026, 8, 5),
        {'000725': '京东方A'}, {},
    )

    vols = [p['volume'] for p in results[0]['data']]
    assert vols == [17534730, 25060238], f"新浪批量走势未归一到手: {vols}"
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py::test_sina_batch_trend_normalizes_shares_to_lots -v`
Expected: FAIL，断言消息显示 `[1753473070, 2506023803]`

- [ ] **Step 3: 改写 7 个落点**

① `_fetch_trend_from_etf._fetch_single_etf`（ETF 均为 A 股）：

```python
                            'volume': int(row['成交量']) if row.get('成交量') else 0
```
→
```python
                            'volume': (_normalize_volume(row.get('成交量'), 'etf_fund_hist', 'A') or 0)
```

② `_fetch_trend_from_eastmoney`（A 股专用）：

```python
                        'volume': int(row['成交量']) if row.get('成交量') else 0
```
→
```python
                        'volume': (_normalize_volume(row.get('成交量'), 'eastmoney_ak_hist', 'A') or 0)
```

③ `_fetch_trend_from_sina`（**本次事故点**，A 股专用）：

```python
                        'volume': int(row['volume']) if row.get('volume') else 0
```
→
```python
                        'volume': (_normalize_volume(row.get('volume'), 'sina_daily', 'A') or 0)
```

④ `_fetch_trend_from_tencent`（`_tencent_code` 支持港股，用运行时市场判定）：

```python
                        # 腾讯 fqkline 日K row[5] 原生"手"（与东财逐日相等），原样保留
                        'volume': int(float(row[5])) if len(row) > 5 and row[5] else 0
```
→
```python
                        'volume': (_normalize_volume(row[5] if len(row) > 5 else None,
                                                     'tencent_fqkline',
                                                     self._identify_market(stock_code)) or 0)
```

⑤ `_fetch_trend_from_eastmoney_direct`（push2his，A 股专用）：

```python
                        'volume': int(float(parts[5])) if parts[5] else 0,
```
→
```python
                        'volume': (_normalize_volume(parts[5], 'eastmoney_push2his', 'A') or 0),
```

⑥ `_fetch_trend_from_yfinance.fetch_single`（**缺陷点**，跨市场）：

```python
                        'volume': int(volume) if not pd.isna(volume) else 0
```
→
```python
                        'volume': (_normalize_volume(volume, 'yfinance',
                                                     self._identify_market(stock_code)) or 0)
```

⑦ `_parse_yf_dataframe`（**缺陷点**，跨市场）：

```python
                'volume': int(volume) if not pd.isna(volume) else 0
```
→
```python
                'volume': (_normalize_volume(volume, 'yfinance',
                                             self._identify_market(stock_code)) or 0)
```

- [ ] **Step 4: 运行全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/pytest_t5.txt 2>&1; grep -E "passed|failed" /tmp/pytest_t5.txt`
Expected: 无 failed，新增的事故回归测试 PASS

- [ ] **Step 5: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/unified_stock_data.py tests/test_volume_alert_unit_consistency.py && rtk git commit -m "fix(stock-data): 批量走势 7 个落点接入 _normalize_volume,修复新浪日K漏 //100 导致的 volume_alert 百倍量纲错误"
```

---

### Task 6: AST 静态断言 — 禁止绕过 helper

**Files:**
- Test: `tests/test_volume_alert_unit_consistency.py`

**Interfaces:**
- Consumes: `VOLUME_SOURCE_UNITS`（Task 1）；Task 2–5 完成后 `unified_stock_data.py` 内所有 `'volume'` 字典项的值都必须是 `_normalize_volume(...)` 调用（可外层包 `or 0`）

这是整个改造的防回归核心：保证下次新增数据源必须登记单位，否则测试红。

- [ ] **Step 1: 写测试**

在 `tests/test_volume_alert_unit_consistency.py` 顶部 import 区加 `import ast`，然后新增分节：

```python
# ============ 5. AST 静态断言：禁止绕过归一 helper ============

def _unwrap_volume_expr(node):
    """剥掉 `X or 0` / 三元表达式外壳，取出真正的取值表达式列表"""
    if isinstance(node, ast.BoolOp):
        out = []
        for v in node.values:
            out.extend(_unwrap_volume_expr(v))
        return out
    if isinstance(node, ast.IfExp):
        return _unwrap_volume_expr(node.body) + _unwrap_volume_expr(node.orelse)
    return [node]


def _volume_dict_values(tree):
    """收集 unified_stock_data.py 中所有 {'volume': <expr>} 的 <expr>"""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value == 'volume':
                found.append((key.lineno, value))
    return found


def test_all_volume_assignments_go_through_normalize_helper():
    """任何 'volume' 赋值都必须来自 _normalize_volume()，不得内联换算"""
    tree = ast.parse(SERVICE_FILE.read_text(encoding='utf-8'))
    offenders = []
    for lineno, value in _volume_dict_values(tree):
        for expr in _unwrap_volume_expr(value):
            if isinstance(expr, ast.Constant):  # `'volume': 0` / None 占位允许
                continue
            is_helper_call = (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Name)
                and expr.func.id == '_normalize_volume'
            )
            if not is_helper_call:
                offenders.append(lineno)
    assert not offenders, (
        f"unified_stock_data.py 第 {sorted(set(offenders))} 行的 volume 绕过了 _normalize_volume()，"
        f"新增数据源必须在 VOLUME_SOURCE_UNITS 登记单位后走 helper"
    )


def test_all_used_source_keys_are_registered():
    """所有 _normalize_volume 调用点用到的 source 字面量都已登记"""
    tree = ast.parse(SERVICE_FILE.read_text(encoding='utf-8'))
    used = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == '_normalize_volume' and len(node.args) >= 2):
            src = node.args[1]
            assert isinstance(src, ast.Constant), (
                f"第 {node.lineno} 行 _normalize_volume 的 source 必须是字面量，不能是变量"
            )
            used.add(src.value)

    unknown = used - set(VOLUME_SOURCE_UNITS)
    assert not unknown, f"未登记的数据源: {unknown}"
    assert len(used) >= 10, f"调用点覆盖的源过少（{len(used)}），疑有落点未接入"
```

- [ ] **Step 2: 运行测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_volume_alert_unit_consistency.py -v`
Expected: 全部 PASS。若 `test_all_volume_assignments_go_through_normalize_helper` 报出行号，说明 Task 2–5 有落点漏改——回去补齐该行，不要放宽断言。

- [ ] **Step 3: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add tests/test_volume_alert_unit_consistency.py && rtk git commit -m "test(stock-data): AST 断言禁止绕过 _normalize_volume,防新增源漏登记单位"
```

---

### Task 7: `data_source_providers` 核查 + 联网一致性测试 + 文档同步

**Files:**
- Modify（条件性）: `app/services/data_source_providers.py`
- Test: `tests/test_volume_alert_unit_consistency.py`
- Modify: `.claude/rules/stock-data-cache.md`

- [ ] **Step 1: 核查 data_source_providers 是否服务 A 股**

```bash
cd D:/Git/stock-volume-unit && rtk grep -rn "DataSourceProvider\|get_historical_data\|data_source_providers" app/ --include=*.py
```

判定：找到所有调用方，确认传入的 `symbol` 是否可能是 A 股（`.SS` / `.SZ` 后缀或 6 位数字）。

- 若**会**被 A 股调用：把 `YFinanceProvider.get_realtime_price`（`'volume': int(last['Volume']) ...`）与 `.get_historical_data`（`'volume': int(row['Volume']) ...`）改为 `from app.services.unified_stock_data import _normalize_volume` 后调用 `_normalize_volume(last['Volume'], 'yfinance', MarketIdentifier.identify(symbol) or 'US')`。注意循环 import 风险——若 `unified_stock_data` 反向依赖本模块，改为函数内惰性 import。
- 若**不会**（只服务美股）：在两个方法的 docstring 各加一行 `仅美股，volume 单位为股，不参与 A 股「手」归一。`，代码不动。

两种结果都要在 commit message 里写明判定依据（哪些调用方、传什么 symbol）。

- [ ] **Step 2: 加联网跨源一致性测试**

在 `tests/test_volume_alert_unit_consistency.py` 末尾追加：

```python
# ============ 6. 跨源真值一致性（联网，默认跳过）============

@pytest.mark.network
@pytest.mark.skipif(not os.environ.get('RUN_NETWORK_TESTS'), reason='需 RUN_NETWORK_TESTS=1 且联网')
def test_cross_source_volume_agreement():
    """同一 A 股同一交易日，各源归一后互差 < 1%。排查量纲问题的现场工具。"""
    from datetime import date, timedelta
    from app.services import unified_stock_data as usd

    code = '000725'
    today = date.today()
    start = today - timedelta(days=15)

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)

    per_source = {}
    for name, fn in [
        ('tencent', service._fetch_trend_from_tencent),
        ('sina', service._fetch_trend_from_sina),
        ('eastmoney', service._fetch_trend_from_eastmoney),
        ('em_direct', service._fetch_trend_from_eastmoney_direct),
    ]:
        try:
            res = fn([code], 10, start, today, {code: code}, {})
        except Exception:
            continue
        if res:
            per_source[name] = {p['date']: p['volume'] for p in res[0]['data']}

    assert len(per_source) >= 2, f'可用源不足，无法交叉验证: {list(per_source)}'

    common = set.intersection(*(set(v) for v in per_source.values()))
    assert common, '各源无共同交易日'

    for d in sorted(common):
        vals = [per_source[s][d] for s in per_source if per_source[s][d]]
        if len(vals) < 2:
            continue
        assert max(vals) / min(vals) < 1.01, f'{d} 各源 volume 不一致: ' + str(
            {s: per_source[s][d] for s in per_source}
        )
```

若 `pytest.ini` / `setup.cfg` 未注册 `network` marker，在项目 pytest 配置中加 `markers = network: 需要联网的测试`，避免 `PytestUnknownMarkWarning`。

- [ ] **Step 3: 运行联网测试验证真值**

```bash
cd D:/Git/stock-volume-unit && PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 RUN_NETWORK_TESTS=1 rtk python -m pytest tests/test_volume_alert_unit_consistency.py::test_cross_source_volume_agreement -v > /tmp/pytest_net.txt 2>&1; grep -E "passed|failed|不一致" /tmp/pytest_net.txt
```

Expected: PASS。若 FAIL 并打印出某源偏差 100 倍，说明该源的 `VOLUME_SOURCE_UNITS` 登记错了——改映射表，不要改断言阈值。

- [ ] **Step 4: 同步数据契约文档**

`.claude/rules/stock-data-cache.md` 的「Volume 单位契约」小节，把逐源的 bullet 列表替换为：

```markdown
所有 A 股 OHLC/realtime 的 `volume` 字段统一为**"手"**（1手=100股）。港股（腾讯 r_hk realtime / yfinance）、美股 volume 一律为股数，不做 /100。

**转换收敛在单点**：各源原生单位登记在 `app/services/unified_stock_data.py` 的 `VOLUME_SOURCE_UNITS`，所有 fetch 落点一律调 `_normalize_volume(raw, source, market)`，**禁止在落点内联 `//100`**。`market != 'A'` 时 helper 原样返回；source 未登记直接抛 `KeyError`。`tests/test_volume_alert_unit_consistency.py` 用 AST 断言守住这条（新增数据源不登记单位 = 测试红）。

已登记单位：腾讯 `qt`/`fqkline`/`mkline` = 手；新浪 `stock_zh_a_spot`/`stock_zh_a_daily` = 股；东财 `stock_zh_a_hist`/`push2his`/`stock_zh_a_spot_em`/`hist_min`/`intraday_em`/`fund_etf_hist_em` = 手；yfinance = 股。

（2026-08-05 事故：`_fetch_trend_from_sina` 与 yfinance A 股兜底漏 `//100`，volume_alert 推出 100 倍量纲，已修并 bump `VOLUME_UNIT_SCHEMA_VERSION=4`。）
```

- [ ] **Step 5: 运行全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > /tmp/pytest_t7.txt 2>&1; grep -E "passed|failed" /tmp/pytest_t7.txt`
Expected: 无 failed

- [ ] **Step 6: 提交**

```bash
cd D:/Git/stock-volume-unit && rtk git add app/services/data_source_providers.py tests/test_volume_alert_unit_consistency.py .claude/rules/stock-data-cache.md && rtk git commit -m "test(stock-data): 跨源 volume 一致性联网测试 + 契约文档同步 + data_source_providers 单位核查"
```

---

### Task 8: 端到端验收与合并

**Files:**
- 无代码改动

- [ ] **Step 1: 确认缓存清理机制会触发**

```bash
cd D:/Git/stock-volume-unit && PYTHONIOENCODING=utf-8 python -c "from pathlib import Path; p=Path('data/memory_cache/.schema_version'); print(p.read_text().strip() if p.exists() else 'missing')"
```

Expected: 输出 `3` 或 `missing` —— 与代码里的 `4` 不匹配，下次启动会触发全量清理。若已是 `4`，说明有其他进程抢先启动过，手动删掉该文件。

- [ ] **Step 2: 真源端到端验证归一结果**

```bash
cd D:/Git/stock-volume-unit && PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -c "
import sys; sys.path.insert(0, '.')
from app.services import unified_stock_data as usd
from datetime import date, timedelta
s = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
t = date.today(); st = t - timedelta(days=15)
for n, f in [('sina', s._fetch_trend_from_sina), ('tencent', s._fetch_trend_from_tencent), ('eastmoney', s._fetch_trend_from_eastmoney)]:
    r = f(['000725'], 5, st, t, {'000725': 'BOE'}, {})
    print(n, [(p['date'], p['volume']) for p in r[0]['data'][-2:]] if r else 'EMPTY')
"
```

Expected: 三源最后两日 volume 互相一致且为**千万级**（如 `17534731` / `25060238`），不是十亿级。

- [ ] **Step 3: 合并回 main**

```bash
cd D:/Git/stock && rtk git merge --no-ff fix/volume-unit-normalization -m "merge: volume 单位归一集中化" && rtk git log --oneline -1
```

- [ ] **Step 4: 清理 worktree**

```bash
cd D:/Git/stock && rtk git worktree remove ../stock-volume-unit && rtk git branch -d fix/volume-unit-normalization
```

- [ ] **Step 5: 下一交易日盯推送**

重启应用，确认启动日志出现 `[数据服务.缓存] volume 相关缓存已清理`。下一个交易日 16:30 的 `volume_alert` 推送中，京东方 A 这类大盘股的 volume 应为千万级「手」而非十亿级「股」。
