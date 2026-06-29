# 盯盘股票池迁为代码配置 — 设计

- **日期**: 2026-06-29
- **状态**: 已确认，待实现
- **触发**: 用户要求「盯盘不要手动编辑，改为代码中配置」（起因是确认天岳先进/英诺赛科两只港股已在盯盘里）

## 背景与问题

盯盘助手（watch）的股票池当前存在专用 DB 表 `WatchList`，靠前端 `/watch/add`、`/watch/remove` UI 手动维护。这是项目里唯一一个「靠手动 DB 编辑维护的列表」——`app/config/stock_codes.py` 里的 `BENCHMARK_CODES` / `VALUE_DIP_SECTORS` / `FUTURES_CODES` / `INDEX_CODES` 都已是代码配置。

用户诉求：消除这个例外，把盯盘池改为**代码配置作为唯一权威源**，杜绝手动编辑路径（git 留痕、无 DB 漂移）。

## 现状（迁移前）

`watch_list` 表当前 7 条（全部经查证正确，含沃尔核材 A+H 的 H 股 9981.HK）：

| code | 名称 | market |
|------|------|--------|
| 300223 | 北京君正 | A |
| 603986 | 兆易创新 | A |
| 600183 | 生益科技 | A |
| 000660.KS | SK海力士 | KR |
| 2631.HK | 天岳先进 | HK |
| 2577.HK | 英诺赛科 | HK |
| 9981.HK | 沃尔核材（H股） | HK |

数据流：strategies（watch_realtime / watch_preload / watch_alert）+ routes 均经 `WatchService.get_watch_codes()` 读 `WatchList.query`。

## 目标方案：配置为唯一权威源

新增 `WATCH_CODES` 常量于 `app/config/stock_codes.py`，`WatchService` 改从它读取；彻底移除增删路由与前端增删 UI；`WatchList` 模型清理删除。`WatchAnalysis`（AI 分析结果表，独立用途）**保持不动**。

### 1. `app/config/stock_codes.py` — 新增 WATCH_CODES

```python
WATCH_CODES = [
    {'code': '300223',    'name': '北京君正',  'market': 'A'},
    {'code': '603986',    'name': '兆易创新',  'market': 'A'},
    {'code': '600183',    'name': '生益科技',  'market': 'A'},
    {'code': '000660.KS', 'name': 'SK海力士',  'market': 'KR'},
    {'code': '2631.HK',   'name': '天岳先进',  'market': 'HK'},
    {'code': '2577.HK',   'name': '英诺赛科',  'market': 'HK'},
    {'code': '9981.HK',   'name': '沃尔核材',  'market': 'HK'},
]
```

`market` 显式写死，不靠 `MarketIdentifier.identify` 推断——后者不认 `.KS` 后缀，会把 SK海力士 误判为默认 'A'。

### 2. `app/services/watch_service.py`

- `get_watch_codes()` → `[e['code'] for e in WATCH_CODES]`
- `get_watch_list()` → 按 WATCH_CODES 顺序构造 `[{'id': i, 'stock_code', 'stock_name', 'market', 'added_at': None}, ...]`（保留 `id`/`added_at` 键防前端 KeyError，值用序号/None）
- `get_watched_markets()` → 从 WATCH_CODES 取 distinct market，按 `['A','US','HK','KR','TW','JP']` 优先级排序（逻辑不变，数据源换成 WATCH_CODES）
- **新增** `get_market_map()` → `{code: market}`，供 watch_alert 使用
- **删除** `add_stock()` / `remove_stock()`
- 文件顶部 import 改为只引 `WatchAnalysis`（移除 `WatchList`）
- `WatchAnalysis` 相关方法（get_today_analysis / save_analysis / get_all_today_analyses 等）全部不动

### 3. `app/routes/watch.py`

- **删除** 路由：`/add`（POST）、`/remove/<stock_code>`（DELETE）、`/stocks/search`（GET，仅服务于添加流程）
- 保留：`/`、`/list`、`/prices`、`/analyze`、`/analysis`、`/market-status`、`/chart-data`、`/earnings`

### 4. `app/strategies/watch_alert/__init__.py`

- 现 line 36-37 用 `WatchList.query.filter(...)` 建 `market_map`；改为 `WatchService.get_market_map()`，移除 `from app.models.watch_list import WatchList`

### 5. 前端 `app/templates/watch.html` + `app/static/js/watch.js`

`watch.html`：
- 删 header「添加」按钮（line 61-62）
- 删 empty state 的「添加股票」按钮（line 87-88），empty state 文案改为提示去 `app/config/stock_codes.py` 配置
- 删添加股票 Modal 整块（line 95-108 起，含 `stockSearchInput` / `searchResults`）

`watch.js`：
- 删每行「移除」按钮渲染（line 392 的 `onclick="Watch.removeStock(...)"` 单元格）
- 删方法 `addStock`（~988）、`removeStock`（~1010）、`searchStocks`（~1035）

### 6. `WatchList` 模型清理

- 删 `app/models/watch_list.py` 的 `WatchList` 类（**保留** `WatchAnalysis`）
- 从 `app/models/__init__.py` 移除 `WatchList` 导出
- 从 `app/__init__.py:276` 的批量 import 移除 `WatchList`
- DB 里 `watch_list` 表变孤立表（无害）；**不加 drop 迁移**（非破坏性优先，git + 本档留痕足够）

### 数据流（迁移后）

```
strategies / routes
   → WatchService.get_watch_codes() / get_watch_list() / get_market_map() / get_watched_markets()
   → 读 WATCH_CODES 内存常量（零 DB 访问）
前端 /watch/list → 只读渲染卡片，无任何增删交互
```

## 测试

- `tests/test_watch_config.py`：
  - `get_watch_codes()` 返回 7 个 code，顺序与 WATCH_CODES 一致
  - `get_watch_list()` 每条含 stock_code/stock_name/market，market 与配置一致
  - `get_watched_markets()` 返回 `['A','HK','KR']`（按优先级，A 在前、KR 在后）
  - `get_market_map()` 返回 `{code: market}` 全量映射，`000660.KS` → `'KR'`
- 路由层用 `Flask() + register_blueprint(watch_bp)` 注入（避开 create_app 副作用）：`/list` 返回 7 条；`/add`、`/remove`、`/stocks/search` 已删除（404）
- 既有 watch 相关单测回归通过

## 非目标（YAGNI）

- 不做盯盘分组/标签/排序等增强
- 不加 drop `watch_list` 表的破坏性迁移
- 不动 `WatchAnalysis` 表与 AI 分析链路
- 不引入「从其他配置（如 VALUE_DIP_SECTORS）自动派生盯盘池」的联动
