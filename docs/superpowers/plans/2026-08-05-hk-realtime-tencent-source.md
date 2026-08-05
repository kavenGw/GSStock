# 港股实时价切腾讯源 + 盯盘提频 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 港股实时价从 yfinance 日线口径切换到腾讯 `qt.gtimg.cn` 实时批量接口，盯盘预取港股提频到每分钟，新鲜度闸门收紧到 120s，消除急拉推送 3 个点的价格滞后。

**Architecture:** `UnifiedStockDataService._fetch_realtime_from_api` 市场分组从二分（A/其他）改三分（A/HK/其他），港股复用现有 `_fetch_from_tencent`（字段索引实测与 A 股一致），失败并入 yfinance 兜底。`watch_preload` 与 `price_freshness` 各改一处市场分档常量。

**Tech Stack:** Python / Flask 服务层、pytest、腾讯 HTTP 行情接口（GBK、`~` 分隔、78 字段）。

**Spec:** `docs/superpowers/specs/2026-08-05-hk-realtime-tencent-source-design.md`

## Global Constraints

- 所有 git/pytest 命令前加 `rtk`；env 赋值必须在 `rtk` 之前（`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`）。
- `git add` 与 `git commit` 必须放同一条命令链（并行 session 抢 index），commit message 走 `.git/MSG.txt` 文件。
- 本计划改 `app/` 代码，执行时须在**独立 git worktree** 中进行（superpowers:using-git-worktrees），不在 main 直接改。
- 测试平铺在 `tests/test_*.py`，不建子目录。
- 不写多余注释；不留 backup 文件。
- Volume 单位契约：**A 股为"手"（/100），港股保持"股"**（与原 yfinance 口径一致）。
- 腾讯港股代码格式：`hk` + 5 位补零（`1888.HK` → `hk01888`）。
- 实测字段参照（2026-08-05 抓取 `q=hk01888`）：`[1]`名称 `[3]`现价 `[4]`昨收 `[5]`开盘 `[6]`成交量(股) `[30]`行情时间戳 `[31]`涨跌 `[32]`涨幅 `[33]`最高 `[34]`最低，共 78 字段。

---

### Task 1: `_tencent_code` 支持港股格式

**Files:**
- Modify: `app/services/unified_stock_data.py:37-46`（`_tencent_code` 函数）
- Test: `tests/test_tencent_index_code.py`（扩展现有文件）

**Interfaces:**
- Produces: `_tencent_code('1888.HK') == 'hk01888'`（后续 Task 2/3 依赖此转换）。A 股行为不变。

- [ ] **Step 1: 写失败测试**

在 `tests/test_tencent_index_code.py` 末尾追加：

```python
def test_hk_codes_zero_padded():
    assert _tencent_code('1888.HK') == 'hk01888'
    assert _tencent_code('700.HK') == 'hk00700'
    assert _tencent_code('03690.HK') == 'hk03690'
    assert _tencent_code('9992.hk') == 'hk09992'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_index_code.py -v`
Expected: `test_hk_codes_zero_padded` FAIL（`1888.HK` 会走裸代码回退返回 `sz1888.HK` 之类错误值）

- [ ] **Step 3: 实现**

`app/services/unified_stock_data.py` 的 `_tencent_code`，在 `.SZ` 分支后追加 `.HK` 分支：

```python
def _tencent_code(code: str) -> str:
    """腾讯行情代码前缀：优先 .SS/.SH→sh、.SZ→sz（指数权威口径），
    .HK→hk+5位补零，裸代码回退 6/5 开头→sh、其余→sz。"""
    c = code.strip()
    up = c.upper()
    if up.endswith('.SS') or up.endswith('.SH'):
        return f"sh{c[:-3]}"
    if up.endswith('.SZ'):
        return f"sz{c[:-3]}"
    if up.endswith('.HK'):
        return f"hk{int(c[:-3]):05d}"
    return f"sh{c}" if c.startswith(('6', '5')) else f"sz{c}"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_index_code.py -v`
Expected: 全部 PASS（含原有 A 股/指数用例）

- [ ] **Step 5: Commit**

```bash
printf '%s\n' "feat(stock-data): _tencent_code 支持港股 hk+5位补零格式" > .git/MSG.txt && rtk git add app/services/unified_stock_data.py tests/test_tencent_index_code.py && rtk git commit -F .git/MSG.txt
```

---

### Task 2: `_fetch_from_tencent` 按市场区分 volume 单位与 market 标记

**Files:**
- Modify: `app/services/unified_stock_data.py:919-983`（`_fetch_from_tencent` 方法）
- Test: `tests/test_tencent_hk_parse.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `_tencent_code`（`.HK` → `hk01888`）。
- Produces: `_fetch_from_tencent(stock_codes: list, now_str: str) -> dict` 签名不变；返回 dict 中港股条目 `market='HK'`、`volume` 为股数（不 /100），A 股条目行为不变（`market='A'`、volume 为手）。Task 3 直接以港股代码列表调用它。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_tencent_hk_parse.py`。fixture 取自 2026-08-05 实测响应（截取关键字段、保持 78 字段结构）：

```python
"""腾讯港股行情解析单测 — mock HTTP，验字段映射/volume单位/market标记"""
from unittest.mock import patch, MagicMock

from app.services.unified_stock_data import unified_stock_data_service


def _tencent_resp(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _build_line(prefix: str, fields: dict, n=78) -> str:
    arr = ['0'] * n
    for i, v in fields.items():
        arr[i] = v
    return f'v_{prefix}="' + '~'.join(arr) + '";'


HK_FIELDS = {0: '100', 1: '建滔积层板', 2: '01888', 3: '34.600', 4: '31.120',
             5: '31.120', 6: '118191487.0', 30: '2026/08/05 13:16:48',
             31: '3.480', 32: '11.18', 33: '34.760', 34: '30.500'}
A_FIELDS = {0: '1', 1: '贵州茅台', 2: '600519', 3: '1800.00', 4: '1790.00',
            5: '1795.00', 6: '1234500', 31: '10.00', 32: '0.56',
            33: '1810.00', 34: '1785.00'}


def test_hk_parse_fields_and_market():
    text = _build_line('hk01888', HK_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['1888.HK'], '2026-08-05T13:20:00')
    data = result['1888.HK']
    assert data['name'] == '建滔积层板'
    assert data['current_price'] == 34.600
    assert data['prev_close'] == 31.120
    assert data['change'] == 3.480
    assert data['change_percent'] == 11.18
    assert data['high'] == 34.760
    assert data['low'] == 30.500
    assert data['market'] == 'HK'


def test_hk_volume_stays_in_shares():
    text = _build_line('hk01888', HK_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['1888.HK'], '2026-08-05T13:20:00')
    assert result['1888.HK']['volume'] == 118191487


def test_a_share_volume_still_converted_to_lots():
    text = _build_line('sh600519', A_FIELDS)
    with patch('requests.get', return_value=_tencent_resp(text)):
        result = unified_stock_data_service._fetch_from_tencent(['600519'], '2026-08-05T13:20:00')
    assert result['600519']['volume'] == 12345
    assert result['600519']['market'] == 'A'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_hk_parse.py -v`
Expected: 港股两条 FAIL（volume 被 /100、market 写死 'A'），A 股用例 PASS

- [ ] **Step 3: 实现**

修改 `_fetch_from_tencent` 解析段（原 966-978 行的 result 赋值），按市场区分：

```python
                try:
                    market = self._identify_market(original_code) or 'A'
                    raw_vol = float(fields[6]) if fields[6] else None
                    result[original_code] = {
                        'code': original_code,
                        'name': fields[1],
                        'current_price': float(fields[3]) if fields[3] else None,
                        'prev_close': float(fields[4]) if fields[4] else None,
                        'open': float(fields[5]) if fields[5] else None,
                        # A股 股→手 归一；港股保持股数（与 yfinance 口径一致）
                        'volume': int(raw_vol / 100) if raw_vol and market == 'A' else (int(raw_vol) if raw_vol else None),
                        'high': float(fields[33]) if fields[33] else None,
                        'low': float(fields[34]) if fields[34] else None,
                        'change': float(fields[31]) if fields[31] else None,
                        'change_percent': float(fields[32]) if fields[32] else None,
                        'last_fetch_time': now_str,
                        'market': market,
                    }
                except (ValueError, IndexError) as e:
                    logger.debug(f"[数据服务.获取] 腾讯数据解析失败 {original_code}: {e}")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_tencent_hk_parse.py tests/test_tencent_index_code.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
printf '%s\n' "feat(stock-data): _fetch_from_tencent 按市场区分 volume 单位与 market 标记" > .git/MSG.txt && rtk git add app/services/unified_stock_data.py tests/test_tencent_hk_parse.py && rtk git commit -F .git/MSG.txt
```

---

### Task 3: `_fetch_realtime_from_api` 港股走腾讯优先 + yfinance 兜底

**Files:**
- Modify: `app/services/unified_stock_data.py:613-723`（`_fetch_realtime_from_api` 方法）
- Test: `tests/test_realtime_hk_tencent_routing.py`（新建）

**Interfaces:**
- Consumes: Task 2 的 `_fetch_from_tencent`（港股返回 `market='HK'` 条目）。
- Produces: `_fetch_realtime_from_api(stock_codes) -> dict` 对外行为不变（返回 `{code: price_dict}`）；内部港股优先腾讯、腾讯缺失/失败的港股代码自动并入 yfinance 路径。上层 `get_realtime_prices` 无需改动。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_realtime_hk_tencent_routing.py`。Mock 掉腾讯取数、DB 缓存写入与 yfinance，验证路由：

```python
"""港股实时价路由单测：腾讯优先，缺失并入 yfinance 兜底"""
from unittest.mock import patch

from app.services.unified_stock_data import unified_stock_data_service as svc


HK_OK = {'1888.HK': {
    'code': '1888.HK', 'name': '建滔积层板', 'current_price': 34.6,
    'prev_close': 31.12, 'open': 31.12, 'volume': 118191487,
    'high': 34.76, 'low': 30.5, 'change': 3.48, 'change_percent': 11.18,
    'last_fetch_time': '2026-08-05T13:20:00', 'market': 'HK',
}}


def _no_cache(*args, **kwargs):
    return None


def test_hk_served_by_tencent_without_yfinance():
    with patch.object(svc, '_fetch_from_tencent', return_value=HK_OK) as mock_tc, \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        result = svc._fetch_realtime_from_api(['1888.HK'])
    mock_tc.assert_called_once()
    assert mock_tc.call_args[0][0] == ['1888.HK']
    mock_yf.assert_not_called()
    assert result['1888.HK']['current_price'] == 34.6
    assert result['1888.HK']['market'] == 'HK'


def test_hk_falls_back_to_yfinance_when_tencent_empty():
    with patch.object(svc, '_fetch_from_tencent', return_value={}), \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        mock_yf.return_value.history.return_value.empty = True
        svc._fetch_realtime_from_api(['1888.HK'])
    mock_yf.assert_called_once()


def test_hk_falls_back_when_tencent_raises():
    with patch.object(svc, '_fetch_from_tencent', side_effect=OSError('timeout')), \
         patch('app.services.unified_stock_data.UnifiedStockCache.set_cached_data', _no_cache), \
         patch('yfinance.Ticker') as mock_yf:
        mock_yf.return_value.history.return_value.empty = True
        svc._fetch_realtime_from_api(['1888.HK'])
    mock_yf.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_realtime_hk_tencent_routing.py -v`
Expected: `test_hk_served_by_tencent_without_yfinance` FAIL（现状港股直接走 yfinance，`_fetch_from_tencent` 未被调用）

- [ ] **Step 3: 实现**

`_fetch_realtime_from_api` 改动三处：

3a. 市场分离段（原 621-631 行）二分改三分：

```python
        # 分离A股、港股和其他（港股腾讯优先，其余 yfinance）
        a_share_codes = []
        hk_codes = []
        other_codes = []
        for code in stock_codes:
            market = self._identify_market(code)
            if market == 'A':
                a_share_codes.append(code)
            elif market == 'HK':
                hk_codes.append(code)
            else:
                other_codes.append(code)

        logger.debug(f"[数据服务.实时价格] 分离股票: A股 {len(a_share_codes)}只, 港股 {len(hk_codes)}只, 其他 {len(other_codes)}只")
```

3b. A 股块之后、yfinance 块之前插入港股腾讯段。`fetched_other` 的初始化从 yfinance 块内**上移到此段之前**（两段共用，统一走块尾的缓存保存循环）：

```python
        fetched_other = []

        # 港股：腾讯批量优先（实时、免限流），失败/缺失并入 yfinance 兜底
        if hk_codes:
            try:
                hk_fetched = self._fetch_from_tencent(hk_codes, now_str)
            except Exception as e:
                logger.warning(f"[数据服务.实时价格] 腾讯港股获取失败: {e}")
                hk_fetched = {}
            hk_ok = {c: d for c, d in hk_fetched.items() if d.get('current_price')}
            for code, data in hk_ok.items():
                result[code] = data
                fetched_other.append((code, data))
            if hk_ok:
                names = ', '.join(d['name'] for d in hk_ok.values())
                logger.info(f"[数据服务.实时价格] 腾讯(港股) → {names} ({len(hk_ok)}只)")
            other_codes.extend(c for c in hk_codes if c not in hk_ok)
```

3c. yfinance 块（原 648-722 行）：删掉块内原 `fetched_other = []` 一行（已上移）；把块尾的缓存保存循环（原 714-722 行 `for code, data in fetched_other:`）**移出 `if other_codes:` 块**，与其平级，保证纯港股场景（other_codes 为空）也写缓存。其余逻辑不动。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_realtime_hk_tencent_routing.py tests/test_tencent_hk_parse.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
printf '%s\n' "feat(stock-data): 港股实时价切腾讯批量优先，yfinance 降级为兜底" > .git/MSG.txt && rtk git add app/services/unified_stock_data.py tests/test_realtime_hk_tencent_routing.py && rtk git commit -F .git/MSG.txt
```

---

### Task 4: `watch_preload` 港股提频到每 tick

**Files:**
- Modify: `app/strategies/watch_preload/__init__.py:53-57`（`_should_refresh_market`）及文件头/`description` 文案
- Test: `tests/test_watch_preload_cadence.py`（扩展现有文件）

**Interfaces:**
- Consumes: 无（纯分档函数）。
- Produces: `_should_refresh_market(market, tick, non_a_every=3) -> bool`：`'A'`/`'HK'` 恒 True，其余 `tick % 3 == 0`。

- [ ] **Step 1: 改写测试**

`tests/test_watch_preload_cadence.py` 全文改为：

```python
from app.strategies.watch_preload import WatchPreloadStrategy


def test_a_share_refreshes_every_tick():
    assert all(WatchPreloadStrategy._should_refresh_market('A', t) for t in range(6))


def test_hk_refreshes_every_tick():
    assert all(WatchPreloadStrategy._should_refresh_market('HK', t) for t in range(6))


def test_us_refreshes_every_third_tick():
    assert WatchPreloadStrategy._should_refresh_market('US', 0) is True
    assert WatchPreloadStrategy._should_refresh_market('US', 1) is False
    assert WatchPreloadStrategy._should_refresh_market('US', 2) is False
    assert WatchPreloadStrategy._should_refresh_market('US', 3) is True


def test_schedule_is_one_minute():
    assert WatchPreloadStrategy.schedule == 'interval_minutes:1'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_cadence.py -v`
Expected: `test_hk_refreshes_every_tick` FAIL（tick 1/2 返回 False）

- [ ] **Step 3: 实现**

`app/strategies/watch_preload/__init__.py`：

```python
    @staticmethod
    def _should_refresh_market(market: str, tick: int, non_a_every: int = NON_A_REFRESH_EVERY) -> bool:
        if market in ('A', 'HK'):
            return True
        return tick % non_a_every == 0
```

同步文案（文件头 docstring、常量注释、`description`）：

```python
"""盯盘数据预取策略 — A股/港股每分钟（腾讯源），美股每3分钟"""
...
NON_A_REFRESH_EVERY = 3   # 美股等 yfinance 市场每 3 tick(≈3min)刷新
...
    description = "盯盘数据预取（A股/港股1min，美股3min，趋势分档）"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_cadence.py tests/test_watch_preload_backoff.py -v`
Expected: 全部 PASS（backoff 机制不受影响）

- [ ] **Step 5: Commit**

```bash
printf '%s\n' "feat(watch): 港股盯盘预取提频到每分钟（腾讯源无限流压力）" > .git/MSG.txt && rtk git add app/strategies/watch_preload/__init__.py tests/test_watch_preload_cadence.py && rtk git commit -F .git/MSG.txt
```

---

### Task 5: `price_freshness` 港股阈值收紧到 120s

**Files:**
- Modify: `app/services/price_freshness.py:5`（`PRELOAD_INTERVAL_MINUTES`）
- Test: `tests/test_price_freshness.py`（更新现有断言 + 新增用例）

**Interfaces:**
- Consumes: 无（纯函数常量）。
- Produces: `max_age_seconds('HK') == 120`；`'US'`/未知市场仍 360。三处消费点（watch_alert / WatchAnalysisService / push_realtime_analysis）自动生效，无需改动。

- [ ] **Step 1: 更新测试**

`tests/test_price_freshness.py` 改动三处：

```python
def test_max_age_by_market():
    assert max_age_seconds('A') == 120
    assert max_age_seconds('HK') == 120
    assert max_age_seconds('US') == 360
    assert max_age_seconds('') == 360


def test_hk_fresh_within_2min():
    assert is_fresh(_p(age_seconds=119), 'HK')


def test_hk_stale_beyond_2min():
    assert not is_fresh(_p(age_seconds=121), 'HK')


def test_non_a_stale_beyond_6min():
    assert not is_fresh(_p(age_seconds=370), 'US')
```

（`test_max_age_by_market` 原 `HK == 360` 断言改为 120；`test_non_a_stale_beyond_6min` 原用 `'HK'` 改用 `'US'`；`test_hk_fresh_within_2min` / `test_hk_stale_beyond_2min` 为新增。其余用例不动。）

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_price_freshness.py -v`
Expected: `test_max_age_by_market` / `test_hk_stale_beyond_2min` FAIL

- [ ] **Step 3: 实现**

`app/services/price_freshness.py` 第 5 行：

```python
PRELOAD_INTERVAL_MINUTES = {'A': 1, 'HK': 1}   # 其余市场默认 3，对应 watch_preload NON_A_REFRESH_EVERY
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_price_freshness.py tests/test_watch_alert_filter_fresh.py tests/test_push_realtime_freshness.py tests/test_watch_realtime_freshness_gate.py -v`
Expected: 全部 PASS（消费点测试若有硬编码 360s 的港股假设需同步修正——预期没有，A 股/US 为主）

- [ ] **Step 5: Commit**

```bash
printf '%s\n' "feat(watch): 新鲜度闸门港股阈值收紧到 120s（对应预取提频）" > .git/MSG.txt && rtk git add app/services/price_freshness.py tests/test_price_freshness.py && rtk git commit -F .git/MSG.txt
```

---

### Task 6: 全量回归 + 文档同步

**Files:**
- Modify: `.claude/rules/stock-data-cache.md`（「数据源」节与 `get_realtime_prices` 描述）
- Modify: `.claude/rules/watch.md`（预取频率描述）
- Modify: `.claude/rules/data-fetch-conventions.md`（港股 `q=hk` 节补充实时价字段结论）

**Interfaces:**
- Consumes: Task 1-5 全部完成。
- Produces: 文档与实现一致；全量测试绿。

- [ ] **Step 1: 全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > pytest_out.txt 2>&1; grep -E "passed|failed" pytest_out.txt; rm pytest_out.txt`
Expected: 全部 PASS，无新增 failure（crawl4ai 进度条走 stdout，必须重定向文件再 grep）

- [ ] **Step 2: 文档同步**

三处最小改动：

`.claude/rules/stock-data-cache.md`「数据源」节：

> A股实时价/分时K线优先腾讯 `qt.gtimg.cn`（并发安全、无需限速），**港股实时价腾讯 `q=hk<code>` 优先、yfinance 兜底**，美股走 yfinance；……

同文件 `get_realtime_prices` 条目：

> `get_realtime_prices(stock_codes, force_refresh)` - A股用腾讯HTTP批量+akshare负载均衡，**港股腾讯批量优先（yfinance兜底）**，美股用yfinance

`.claude/rules/watch.md` 第 20 行数据流描述：

> 后端 A股/港股每分钟 force_refresh，美股每3分钟（差异化提频，见 watch_preload）

同文件「价格新鲜度闸门」节阈值描述：

> 阈值 = 2×preload 刷新周期（A股/港股 120s / 美股 360s）

`.claude/rules/data-fetch-conventions.md`「港股取数字段不同」条目开头补充：

> `q=hk03690`（GBK/`~`分隔，78 字段）**实时价字段与 A 股一致**（`[1]`名称 `[3]`价 `[4]`昨收 `[5]`开 `[6]`量(股，无手概念) `[31]`涨跌 `[32]`涨幅 `[33]`高 `[34]`低 `[30]`行情时间戳），已接入 `get_realtime_prices` 主链路；但估值字段索引与 A 股不一致，**勿照搬 A 股 [39]PE/[45]市值/[46]PB**；……（后接原文）

- [ ] **Step 3: Commit**

```bash
printf '%s\n' "docs(rules): 港股实时价腾讯源切换后的数据源/盯盘频率文档同步" > .git/MSG.txt && rtk git add .claude/rules/stock-data-cache.md .claude/rules/watch.md .claude/rules/data-fetch-conventions.md && rtk git commit -F .git/MSG.txt
```

- [ ] **Step 4: 盘中实测抽查（港股交易时段执行）**

在 worktree 内临时跑（跑完即弃，不入库）：

```bash
PYTHONIOENCODING=utf-8 rtk python -c "import urllib.request; r=urllib.request.urlopen(urllib.request.Request('http://qt.gtimg.cn/q=hk01888', headers={'User-Agent':'Mozilla/5.0'}), timeout=10).read().decode('gbk'); f=r.split('~'); print(f[3], f[32], f[30])"
```

对照行情软件当前价：价差应 <0.5%、`[30]` 时间戳应在 1 分钟内。若偏差大（延迟源），回报用户重新评估。

---

## Self-Review 结果

- **Spec 覆盖**：spec §1 取数层 → Task 1/2/3；§2 预取提频 → Task 4；§3 闸门 → Task 5；§5 测试 → 各 task Step 1；§7 实测验证 → Task 6 Step 4；文档同步（配置变更同步约定）→ Task 6 Step 2。无缺口。
- **占位符扫描**：无 TBD/TODO；所有测试与实现均给出完整代码。
- **类型一致性**：`_fetch_from_tencent(stock_codes, now_str)` 签名 Task 2/3 一致；`_should_refresh_market(market, tick, non_a_every)` 与现有签名一致；`PRELOAD_INTERVAL_MINUTES` 键值与 price_freshness 消费逻辑一致。
