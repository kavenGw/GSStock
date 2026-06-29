# 价值洼地页改用盯盘股（扁平化）— 设计

- 日期：2026-06-30
- 状态：已批准，待实现

## 背景

导航项「价值洼地」指向 `/value-dip`（`value_dip` 模块），当前选股源是硬编码的 `VALUE_DIP_SECTORS`（5 个板块：韩国存储 / A股存储主控 / A股存储 / A股PCB / A股CCL）。其引擎按板块聚合：算每个板块 7d/30d/90d 平均涨幅，标出跑输跨板块均值 >50% 的板块为「洼地」，并提供逐股「高点回退」排行。两者都喂每日 Slack 简报。

盯盘池 `WATCH_CODES`（`app/config/stock_codes.py`，12 只）是单一权威源，仅含 `code/name/market`，**无板块归属**。近期盯盘页、新闻「我的公司」等已陆续收敛到 `WATCH_CODES`，本次让「价值洼地」页也改用盯盘股。

> 注意：`/valuations`（导航「Claude估值」，数据源 `valuations.yaml`）是另一个页面，**不在本次范围内**。

## 目标

把 `/value-dip` 选股源从 `VALUE_DIP_SECTORS` 换成 `WATCH_CODES`，**去掉板块对比维度**，页面变成一张扁平表。

## 关键决策（已与用户确认）

1. **板块归属**：扁平化，去掉板块对比。盯盘股当成一个扁平列表。
2. **板块洼地 Slack 推送**：直接删除（`detect_value_dips` / `_push_value_dip_alert` / `_format_value_dip_message`）。高点回退推送保留。
3. **页面呈现**：纯表格，去掉所有图表。

## 设计

### 数据层（`app/services/value_dip.py`）

- 选股源：`WatchService.get_watch_list()` → `[{code, name, market}]`（与盯盘页一致的单一权威源）。
- 新增扁平方法 `get_watch_performance()`：对 12 只调一次 `get_trend_data(codes, days=90)`，逐股算 `price / change_7d / change_30d / change_90d / high_* / pullback_*`。复用现有 `_calc_stock_changes` 的逐股计算逻辑，去掉外层板块循环。
- `get_pullback_ranking(days)` 改为消费扁平列表；输出里 `sector` 字段换成 `market`（A/HK/KR/US）。
- **删除** `get_sector_performance()` 和 `detect_value_dips()`。

### 路由层（`app/routes/value_dip.py`）

- `/api/sectors` → 改名 `/api/stocks`，返回 `{stocks: [...]}` 扁平结构（每股含 7d/30d/90d 涨幅 + 高点回退）。
- `/api/pullback` 保留，内部走新扁平方法。

### 前端（`app/templates/value_dip.html` + `app/static/js/value_dip.js`）

- 一张表，列：`股票(名+代码) | 市场 | 现价 | 7d | 30d | 90d | 高点回退`。
- 保留顶部 7d/30d/90d 周期切换 → 控制「高点回退」列取哪个周期的高点；7d/30d/90d **三档涨幅同时显示**。
- 默认按**高点回退升序**（回退最深在前 = 「洼地」语义）。
- 配色沿用现有：涨幅红绿，回退 <-10% 加粗、<-5% 红色。
- **删除**：板块卡片（`#sector-cards`）、板块走势对比图（`#compare-container` + echarts compare 逻辑）、点击板块展开的个股走势图（`#trend-container` + `renderTrend`）。本页不再依赖 echarts。

### 每日简报（`app/strategies/daily_briefing/__init__.py`）

- **删除** `_push_value_dip_alert()` + `_format_value_dip_message()`，并移除其调用点。
- **保留** `_push_pullback_alert()`（逐股回退 ≤ -5% 才推），`_format_pullback_message` 里 `s['sector']` 改成 `s['market']`。

### 清理

- 从 `app/config/stock_codes.py` 删除 `VALUE_DIP_SECTORS`（grep 确认仅 `value_dip.py` 引用，已核实）。

## 改动文件清单

- `app/config/stock_codes.py` — 删 `VALUE_DIP_SECTORS`
- `app/services/value_dip.py` — 重构为扁平选股 + 计算，删板块/洼地方法
- `app/routes/value_dip.py` — `/api/sectors` → `/api/stocks`
- `app/static/js/value_dip.js` — 重写为扁平表渲染，去图表
- `app/templates/value_dip.html` — 重写为单表，去图表容器
- `app/strategies/daily_briefing/__init__.py` — 删洼地推送，回退推送 sector→market

## 风险点

- `WATCH_CODES` 含港股（`2631.HK`）、韩股（`000660.KS`），`get_trend_data` 走 yfinance —— 盯盘页已用同一批代码取数，路径已验证可用。
- 韩股/港股冷缓存逐只串行可能略慢，但只 12 只、日级页面，可接受。

## 验证

- `/value-dip` 页加载渲染 12 只盯盘股扁平表，周期切换与排序正常。
- 每日简报高点回退推送仍可生成（market 字段替换 sector 不报错）。
- grep 全仓确认无残留 `VALUE_DIP_SECTORS` / `detect_value_dips` / `get_sector_performance` 引用。
- 全量 pytest 无新增 `ModuleNotFoundError` / `AttributeError`。
