# 估值汇总页 — 市场 Tab 设计

- 日期：2026-06-04
- 状态：设计已确认，待写实现计划
- 关联：`2026-06-04-估值汇总页-design.md`（原始页面设计）

## 目标

在现有估值汇总页（`app/routes/valuations.py` + `valuations.html`，单张表 119 行）上，按股票市场加 Tab 分组，便于按 A股 / 港股 / 美股分别查看，并消除「全部」视图下多币种价格混排的误读。

## 现状背景

- 估值汇总页已是 Flask 页面：`GET /valuations/` 缓存渲染、`GET /valuations/api/prices?force=1` 批量刷新。
- 数据源 `docs/stock-analytics/valuations.yaml`，每条已含 `market` 字段（`A` / `US` / `HK`）与 `currency`。
- 当前分布：A股 91 / 港股 18 / 美股 10，共 119。
- `_enrich()` 已按 Base 安全边际降序排好；安全边际是比例量纲，与币种无关。

## 关键决策（brainstorming 结论）

1. **Tab 集合**：`全部 + A股 + 港股 + 美股` 四个静态 tab，默认激活「全部」。
2. **切换机制**：纯前端过滤。服务端一次渲染全部行，JS 按 `market` 显隐，零请求瞬切。
3. **Tab 计数**：标签带计数（如「A股 (91)」），计数在路由层用 `Counter` 算好传入，单一来源、可测。
4. **币种列**：表格新增「币种」列，解决「全部」tab 下 CNY/USD/HKD 混排误读。
5. **排序**：不变，各 tab 共享 `_enrich` 的 Base 安全边际降序（隐藏不匹配行，不重排）。

## 1. Tab 结构

表格上方加一排 Bootstrap `nav-tabs`：

```
全部 (119) | A股 (91) | 港股 (18) | 美股 (10)
```

- 4 个 tab 静态渲染，默认 `active` 为「全部」。
- 计数由路由层 `Counter(r['market'] for r in rows)` 计算，连同总数传给模板。
- market → 中文标签映射：`A→A股`、`HK→港股`、`US→美股`；「全部」对应 `all`。

## 2. 切换机制（纯前端）

- 服务端一次渲染全部 119 行，每行加 `data-market="{{ r.market }}"`。
- JS `switchTab(market)`：
  - `market === 'all'` → 显示全部行；否则只显示 `data-market` 匹配的行。
  - 切换 `nav-link` 的 `active` 态。
- 零请求、瞬切。隐藏用 `display:none`（或 Bootstrap `d-none` class）。

## 3. 币种列

表格新增一列「币种」（`r.currency`），插在「名称」之后：

- 「全部」tab 下区分多币种价格量纲。
- 市场 tab 内币种天然统一（冗余但无害）。
- 缺 `currency` → 显示「—」。

## 4. 刷新按钮

行为不变：

- 仍一次批量拉全量价（`api/prices?force=1`），更新所有 `data-code` 行（含当前隐藏行）。
- 与 tab 状态解耦：切到任意 tab 数据都是新的。

## 5. 改动文件

- `app/routes/valuations.py`：
  - `index()` 增 `market_counts`（`Counter`）+ `total` 计数，随 `render_template` 传入。
  - `api/prices` 不动。
- `app/templates/valuations.html`：
  - 加 `nav-tabs` 标签栏（带计数）。
  - 加 `switchTab(market)` JS。
  - 表格加「币种」列。
  - 每行加 `data-market` 属性。
- `tests/test_valuations.py`：补一条 —— 断言 `GET /valuations/` 200 且响应含 4 个 tab 文案与计数。

## 6. 错误/边界处理

- 某市场 0 行 → tab 仍显示「(0)」，切过去为空表（静态 tab 选择的已知取舍，计数让其显而易见）。
- yaml 缺失/空 → 沿用现有空表提示；tab 计数全 0 或不渲染表（保持现有 `{% if not rows %}` 分支）。
- 缺 `currency` / 缺价 / 缺档 → 显示「—」，沿用现有防御。

## 7. 测试

- **路由 smoke**：`create_app()`（`SCHEDULER_ENABLED=0`）下 `GET /valuations/` 返回 200，响应文本含「A股」「港股」「美股」「全部」及对应计数。
- 现有纯函数单测（`load_valuations` / `compute_margin`）不受影响。

## 非目标（YAGNI）

- 不改 `valuations.yaml` 结构。
- 不改 `api/prices`（仍批量全量）。
- 不做服务端分市场请求 / 分页。
- 不做汇率换算（margin 为比例，币种无关）。
- 不做动态 tab（按 yaml 实际 market 生成）—— 采用固定 4 tab。
