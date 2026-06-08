# 估值汇总页港股实时价刷新失败 — 设计

日期：2026-06-08
方案：B（路由层归一）

## 问题

估值汇总页（`/valuations`）的港股行实时价列恒为「—」，无法刷新。
截图：01810 小米集团-W、02643 曹操出行、03690 美团、06862 海底捞 全部无价。

## 根因

`docs/stock-analytics/valuations.yaml` 把港股 `stock_code` 存成 **5 位补零纯数字**
（`01810` / `02643` / `03690` / `06862`），而全项目港股的规范格式是 `<数字>.HK`
（如 `app/config/supply_chain.py` 里的 `1810.HK`、`3690.HK`）。

取价链路 `unified_stock_data_service.get_realtime_prices([...])` 只看 code 字符串：

- `MarketIdentifier.identify('01810')` → 非 6 位（A 股）、非字母开头（美股）→ 返回 `None` → 落到 yfinance 分支当美股处理
- `to_yfinance('01810')` 原样返回 `01810` → yfinance 用无效 ticker 查询 → 无价 → 表格「—」

实测验证：

```
01810   -> identify=None  yfinance: KeyError 'currentTradingPeriod'（无价）
1810.HK -> identify=HK    yfinance: last_price=27.32 ✓
```

注意：yaml 行里 `market: HK` 字段**本就存在**，只是实时价链路没消费它——仅凭 code 本身判市场。

## 方案对比

| 方案 | 做法 | 显示代码 | 改动面 | 取舍 |
|------|------|---------|--------|------|
| A 改数据 | yaml 4 行港股 code 改成 `1810.HK` | 变 `1810.HK` | 仅数据 | 显示风格变了 |
| **B 路由层归一**（选定） | valuations.py 取价前用 `market:HK` 把 `01810`→`1810.HK` 查，结果映射回原 code | 保 `01810` | 仅 valuations.py | 局部、保显示、不动全局 |
| C 改全局识别器 | 让 `MarketIdentifier` 把 5 位纯数字认成港股 | 保 `01810` | 全局 | 5 位纯数字全局当港股，误伤风险大 |

选 B：改动局部，复用 yaml 已有的 `market` 权威字段，保留港股 5 位补零显示习惯，且不触全局识别器（避免影响持仓 / 盯盘等所有 `get_realtime_prices` 调用方）。

## 实现设计

**改动文件**：`app/routes/valuations.py`（+ `tests/test_valuations.py` 一条测试）。`MarketIdentifier`、模板、前端 JS 均不动。

### 1. 取价代码归一函数

```python
def _fetch_code(row: dict) -> str:
    """港股 yaml 存 5 位补零纯数字（01810），实时价需 yfinance 的 .HK 格式。
    用 row 已有的 market 字段判断，转 1810.HK；其余原样。"""
    code = row['stock_code']
    if row.get('market') == 'HK' and code.isdigit():
        return f"{int(code):04d}.HK"
    return code
```

转换样例（与全项目 config 里 `.HK` 写法一致）：

- `01810` → `1810.HK`
- `02643` → `2643.HK`
- `03690` → `3690.HK`
- `06862` → `6862.HK`

### 2. 两处路由统一改法（`index` 与 `api_prices`）

取价前建「原 code → 取价 code」映射，用取价 code 调服务，结果**键映射回原 code** 再交给下游，
`_enrich` / `api_prices` 内部按 `r['stock_code']` 取价的逻辑保持不动：

```python
fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}      # 01810 -> 1810.HK
prices = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()), ...)
prices = {orig: prices.get(fc) for orig, fc in fetch_map.items()}  # 键映回 01810
```

`index` 路由保留既有 try/except 降级渲染。`api_prices` 保留 `force` 透传。

## 不变量

- 表格显示、`<tr data-code>`、`/api/prices` 返回的 key 全部保持 `01810`（前端 `cell-price` 按 `data-code` 更新照常对号）
- A 股（6 位纯数字，`market != 'HK'`）、美股（字母开头）完全不受影响——仅 `market == 'HK'` 且纯数字才转
- `MarketIdentifier` 全局识别器零改动，无外溢
- yaml 若已是规范 `XXXX.HK`（含点，`isdigit()` False）原样透传，不二次加 `.HK`

## 测试

`tests/test_valuations.py` 新增一条（沿用现有 `monkeypatch get_realtime_prices` 模式）：

- 构造含 HK 行（`stock_code='01810'`, `market='HK'`, 含 bear/base/bull）的 yaml
- monkeypatch 捕获传入 `get_realtime_prices` 的 codes，断言含 `1810.HK`
- 桩返回 `{'1810.HK': {'price': 27.32}}`
- 断言 `/api/prices` 输出按 `01810` 回填 `current_price=27.32` 及 `margin_*`

回归确认：A 股 / 美股行的取价 code 不变（已有 smoke / structure 测试覆盖）。

## 验证命令

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v
```
