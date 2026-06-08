# 估值汇总页港股实时价刷新失败 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让估值汇总页（`/valuations`）的港股行能取到实时价，不再恒显「—」。

**Architecture:** 方案 B（路由层归一）。`valuations.yaml` 把港股 code 存成 5 位补零纯数字（`01810`），`MarketIdentifier` 认不出 → 当美股走 yfinance 无效 ticker → 无价。在 `app/routes/valuations.py` 取价前用 yaml 已有的 `market: HK` 字段把 code 归一为 yfinance 的 `1810.HK` 形式取价，再把价格 dict 的 key 映射回原 code 交给下游。全局 `MarketIdentifier`、模板、前端 JS 均不动。

**Tech Stack:** Flask 路由、pytest（沿用现有 `monkeypatch get_realtime_prices` 模式）。

参考 spec：`docs/superpowers/specs/2026-06-08-valuations-hk-realtime-price-design.md`

---

## File Structure

- **Modify** `app/routes/valuations.py`：新增模块级函数 `_fetch_code(row)`；改 `index()` 与 `api_prices()` 两处取价段，加 `fetch_map` 归一 + 价格 dict 键回填。
- **Modify** `tests/test_valuations.py`：新增 `_fetch_code` 纯函数测试 + 一条 api_prices 港股映射回填测试。

不变量（实现时必须保持）：
- 表格显示、`<tr data-code>`、`/api/prices` 返回的 key 全部保持原始 `01810`（前端 `cell-price` 按 `data-code` 更新照常对号）。
- 仅 `market == 'HK'` 且 code 纯数字才转；A 股（6 位数字，market≠HK）、美股（字母）原样透传。
- yaml 若已是规范 `XXXX.HK`（含点，`isdigit()` 为 False）原样透传，不二次加 `.HK`。

---

## Task 1: `_fetch_code` 归一函数（TDD）

**Files:**
- Modify: `app/routes/valuations.py`（在 `_extract_price` 之后新增 `_fetch_code`）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_valuations.py` 第 4 行把现有 import：

```python
from app.routes.valuations import compute_margin, _extract_price
```

改为：

```python
from app.routes.valuations import compute_margin, _extract_price, _fetch_code
```

然后在文件末尾追加：

```python
def test_fetch_code_hk_zero_padded_numeric():
    assert _fetch_code({'stock_code': '01810', 'market': 'HK'}) == '1810.HK'
    assert _fetch_code({'stock_code': '02643', 'market': 'HK'}) == '2643.HK'
    assert _fetch_code({'stock_code': '03690', 'market': 'HK'}) == '3690.HK'
    assert _fetch_code({'stock_code': '06862', 'market': 'HK'}) == '6862.HK'


def test_fetch_code_a_share_untouched():
    assert _fetch_code({'stock_code': '600519', 'market': 'A'}) == '600519'
    assert _fetch_code({'stock_code': '000878', 'market': 'A'}) == '000878'


def test_fetch_code_us_untouched():
    assert _fetch_code({'stock_code': 'AMD', 'market': 'US'}) == 'AMD'


def test_fetch_code_already_hk_suffixed_untouched():
    assert _fetch_code({'stock_code': '1810.HK', 'market': 'HK'}) == '1810.HK'


def test_fetch_code_missing_market_untouched():
    assert _fetch_code({'stock_code': '01810'}) == '01810'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_fetch_code_hk_zero_padded_numeric -v`
Expected: FAIL —— `ImportError: cannot import name '_fetch_code'`（import 行已加但函数未定义）。

- [ ] **Step 3: Write minimal implementation**

在 `app/routes/valuations.py` 的 `_extract_price` 函数之后插入：

```python
def _fetch_code(row: dict) -> str:
    """港股 yaml 存 5 位补零纯数字（01810），实时价需 yfinance 的 .HK 格式。
    用 row 已有的 market 字段判断，转 1810.HK；其余原样。"""
    code = row['stock_code']
    if row.get('market') == 'HK' and code.isdigit():
        return f"{int(code):04d}.HK"
    return code
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -k fetch_code -v`
Expected: 5 个 `test_fetch_code_*` 全 PASS。

- [ ] **Step 5: Commit**

```bash
cd D:/Git/stock && rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "feat: 估值页港股取价代码归一函数 _fetch_code"
```

---

## Task 2: `index()` 与 `api_prices()` 接入归一 + 键回填（TDD）

**Files:**
- Modify: `app/routes/valuations.py`（`index()` 约 96-104 行取价段；`api_prices()` 约 118-123 行取价段）
- Test: `tests/test_valuations.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_valuations.py` 末尾追加（依赖 valuations.yaml 里真实存在的港股行 `01810` 与 A 股行 `000878`）：

```python
def test_api_prices_hk_normalizes_and_maps_back(app_client, monkeypatch):
    from app.services import unified_stock_data_service

    seen = {}

    def fake_prices(codes, force_refresh=False):
        seen['codes'] = list(codes)
        return {'1810.HK': {'price': 27.32, 'name': '小米集团-W'}}

    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices', fake_prices)
    resp = app_client.get('/valuations/api/prices?force=1')
    assert resp.status_code == 200
    # 港股归一为 .HK 形式传给服务，原始 01810 不直接下发
    assert '1810.HK' in seen['codes']
    assert '01810' not in seen['codes']
    # 输出按原始 code 01810 回填价格
    body = resp.get_json()
    assert body['01810']['current_price'] == 27.32
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_api_prices_hk_normalizes_and_maps_back -v`
Expected: FAIL —— `assert '1810.HK' in seen['codes']` 失败（当前下发的是 `01810`），且 `body['01810']['current_price']` 为 None。

- [ ] **Step 3: Modify `index()` 取价段**

把 `app/routes/valuations.py` 的 `index()` 中这段：

```python
    rows = load_valuations()
    codes = [r['stock_code'] for r in rows]
    prices = {}
    if codes:
        try:
            prices = unified_stock_data_service.get_realtime_prices(codes)
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
```

替换为：

```python
    rows = load_valuations()
    fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}
    prices = {}
    if fetch_map:
        try:
            raw = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()))
            prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
```

- [ ] **Step 4: Modify `api_prices()` 取价段**

把 `api_prices()` 中这段：

```python
    rows = load_valuations()
    codes = [r['stock_code'] for r in rows]
    prices = unified_stock_data_service.get_realtime_prices(codes, force_refresh=force) if codes else {}
```

替换为：

```python
    rows = load_valuations()
    fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}
    raw = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()), force_refresh=force) if fetch_map else {}
    prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
```

下游 `_enrich(rows, prices)`（index）与 `prices.get(r['stock_code'])`（api_prices）逻辑不动 —— `prices` 已按原始 code 作 key。

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py::test_api_prices_hk_normalizes_and_maps_back -v`
Expected: PASS。

- [ ] **Step 6: Full regression**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v`
Expected: 全 PASS（含既有 `test_api_prices_structure` —— A 股 `000878` 取价 code 不变、`?force=1` 仍透传 `force_refresh=True`；`test_index_degrades_when_price_fetch_raises` —— index try/except 降级仍生效）。

- [ ] **Step 7: Commit**

```bash
cd D:/Git/stock && rtk git add app/routes/valuations.py tests/test_valuations.py && rtk git commit -m "fix: 估值页港股实时价归一取价并按原 code 回填"
```

---

## Self-Review

- **Spec coverage:** `_fetch_code` 函数（Task 1）；`index` + `api_prices` 两处接入与键回填（Task 2 Step 3/4）；不变量（保显示 / 仅 HK 纯数字转 / 已 `.HK` 不二转 / A 股美股不动）由 Task 1 的 5 个单测 + Task 2 回归覆盖；测试章节落在 Task 1/2 的 test step；验证命令落在各 Run。无遗漏。
- **Placeholder scan:** 无 TBD/TODO，每个 code step 均给出完整代码与精确替换前后文。
- **Type consistency:** 全程函数名 `_fetch_code`、变量 `fetch_map` / `raw` / `prices` 一致；`fetch_map` 为 `{原code: 取价code}`，回填 `{orig: raw.get(fc)}` 与下游按原 code 取价吻合。
