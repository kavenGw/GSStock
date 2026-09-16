# 美股四态会话模型与夜盘（暗盘）行情接入设计

- 日期：2026-09-16
- 状态：设计已确认，待实现
- 触发：现有「暗盘」一词被误用于指代盘前/盘后；需引入真正的夜盘时段（ET 20:00–04:00）
- 新增外部源：Webull 公开行情接口（无需 key）

## 1. 背景与目标

现有美股盯盘只认盘前（ET 04:00–09:30）与盘后（16:00–20:00）两态，代码与文档中统称「暗盘」。该措辞有误：暗盘特指港股新股上市前的场外灰市交易，美股 04:00–20:00 的正确叫法是盘前/盘后（extended hours）。

同时存在一个真实缺口与一个真实缺陷：

- **缺口**：ET 20:00–04:00（北京 08:00–16:00）的夜盘时段完全未覆盖。该窗口正是国内用户的白天，是盯盘价值最高的时段。
- **缺陷**：`UnifiedStockDataService._parse_extended_quote` 把 `marketState == 'CLOSED'` 归为盘后。Yahoo 在 ET 20:00 后转入 CLOSED 但仍返回停更的 `postMarketPrice`，导致北京 08:00–16:00 页面显示「盘后 $xxx」，实为停在 ET 20:00 的陈价。该缺陷的发作窗口与待补的夜盘窗口完全重合。

**目标**：将美股时段体系重构为盘前 / 盘中 / 盘后 / 暗盘四态；接入夜盘行情；把「暗盘」一词从盘前盘后的误用中腾出，专指夜盘。

## 2. 数据源选型（2026-09-16 实测）

| 源 | 夜盘覆盖 | 实测证据 |
|---|---|---|
| Polygon（已配 key） | 无 | NVDA/TSLA/AAPL 在 2026-09-15 20:00 → 09-16 04:00 窗口均 0 根 1min bar（盘前 317 / 盘中 390 / 盘后 234，仅覆盖 04:00–20:00）；免费档 `status=DELAYED`，snapshot 返回 403 NOT_AUTHORIZED |
| Twelve Data（已配 key） | 无 | `403 Pre-market and post-market data are available on the Pro plan` —— 连盘前盘后都不可用 |
| 东方财富 push2his | 无 | 美股 1min kline 返回 0 根 |
| 富途 futunn 网页 API | 不可用 | 行情端点 404 |
| **Webull** | **有** | 见下 |

**选定 Webull**，依据：

- `GET https://quotes-gw.webullfintech.com/api/stock/tickerRealTime/getQuote` 无需 key、无需认证、国内直连
- 返回 76 字段，含专用的 `overnight` 标志位与 `greyTradeFlag`，接口本身是夜盘感知的
- 盯盘池 6 只美股（NVDA / AMD / XPEV / LITE / WOLF / SOXX）全部解析到 tickerId
- 盘前价与 yfinance 逐分钱对齐（NVDA 213.48 vs 213.50；AMD / LITE / WOLF / SOXX 完全一致）
- 比现有 `yf.Ticker().info`（拉取 76 字段的重调用）轻量

**风险**：非官方接口，无 SLA，可能变更。缓解：保留 yfinance 作为盘前/盘后兜底。

**未验项**：`overnight == 1` 时 `pPrice` 是否即夜盘价，只能在真实窗口验证（见 §8）。

## 3. 四态会话模型

落位 `app/services/trading_calendar.py` 的 `TradingCalendarService`。
（`app/services/market_session.py` 名称相近但实为 `SmartCacheStrategy` 缓存策略，不涉及。）

新增 `get_us_session(dt=None) -> 'pre' | 'regular' | 'post' | 'overnight' | None`，**直接替换** `get_us_extended_session()`。调用点仅两处（`app/routes/watch.py:163`、`app/strategies/watch_preload/__init__.py:70`），按项目约定不保留兼容壳。

判定规则（ET）：

| 条件 | 结果 |
|---|---|
| `t >= 20:00` 且下一个交易日即次日 | `overnight` |
| `t < 04:00` 且当日为交易日 | `overnight` |
| `04:00 <= t < open` 且当日为交易日 | `pre` |
| `open <= t < close` | `regular` |
| `close <= t < 20:00` 且当日为交易日 | `post` |
| 其余 | `None` |

两个跨日边界是本设计最易错处：

- 周五 ET 20:00 之后**不是**夜盘 —— 下一个交易日是周一而非次日，条件不成立
- 周日 ET 20:00 起**是**夜盘 —— 下一个交易日为周一（次日），归属周一这个交易日

`open` / `close` 取自 `get_market_hours()` 而非硬编码 09:30 / 16:00：半日市（如感恩节次日 13:00 收盘）时 post 窗口须从 13:00 起算。现有代码已是此写法，保留。

**现状说明（与上述设计意图不符）**：`get_market_hours()` 目前对 `'US'` 返回硬编码字面量 `(9:30, 16:00)`，仅用 `exchange_calendars` 判 `is_trading_day`，从不查 `early_closes`。因此半日市当天 `close` 仍取到 16:00，13:00–16:00 会被误判为 `regular` 而非 `post`。这是历史欠债，未在本次改动范围内修复。

## 4. 数据层

### 4.1 新模块 `app/services/webull_quote.py`

- `resolve_ticker_id(symbol) -> int | None`
  - `GET /api/search/pc/tickers`，取 `regionId == 6` 且 symbol 精确匹配
  - tickerId 稳定，进程内 dict + memory_cache 长 TTL 缓存，正常每进程每票解析一次
- `get_extended_quotes(symbols) -> {symbol: {session, price, change_pct, time, source}}`
  - `getQuote` 为单票接口，用 `ThreadPoolExecutor(max_workers=3)` 并发，与现有 `get_us_extended_quotes` 写法一致
  - 字段映射：`pPrice` → `price`；`pChRatio * 100` → `change_pct`（原值为小数比率，0.0061 表示 0.61%）；`tradeTime` → `time`

### 4.2 session 判定权威

session 一律以 `TradingCalendarService.get_us_session()`（本地时钟 + 交易日历）为准；Webull 的 `overnight` 字段仅用于校验与日志，不参与判定。

理由：页面状态条、`ext` 标签、Slack 推送标题必须同源。两套判定并存会出现「状态条显示盘后、价格标注暗盘」的错位。

### 4.3 兜底

Webull 请求失败或 `pPrice` 为空时，回落现有 yfinance `_parse_extended_quote`。兜底仅覆盖盘前/盘后；夜盘无兜底，返回 `None`。

### 4.4 出口与缓存

`unified_stock_data.get_us_extended_quotes()` 保留为唯一出口，内部换源，调用方无感。

**不纳入 `DataSourceProvider` ABC**：该接口为 `get_realtime_price` / `get_historical_data` 服务于负载均衡轮询；扩展时段报价带 session 语义、仅在特定窗口有值、不参与轮询，纳入会污染双方。

缓存沿用 `cache_type='extended'`、TTL 600s，但**缓存值须带 session**，读取时 `quote['session'] != 当前 session` 即判失效。现状不带 session，盘前切盘中时旧盘前价会滞留 10 分钟。

## 5. API 契约

- `/watch/prices` 每条的 `ext` 结构不变，`session` 枚举扩充 `overnight`。向后兼容的扩展，非破坏性改动。
- `/watch/market-status` 的 `status` 新增 `overnight`，`status_text` 为 `暗盘`；美股 `regular` 态的 `status_text` 由 `交易中` 改为 `盘中`。
- 「盘中」不进 `ext`：盘中价即主价格列，`ext` 仅在非盘中时段有值。

**状态文案范围**：仅美股改用「盘中」，A 股 / 港股保持「交易中」（该市场无盘前盘后，不产生歧义）。

## 6. 前端 `app/static/js/watch.js`

- `isActiveStatus`（1261 行）加入 `overnight` —— 否则北京 08:00–16:00 页面停止轮询
- `getStatusIcon` 加 `overnight: '🌑'`（盘前/盘后现为 🔵）
- `_renderExtQuote` 的 label 由三元表达式改为 map：`pre → 盘前`、`post → 盘后`、`overnight → 暗盘`

## 7. 推送与调度

**`app/services/notification.py`**：`push_extended_alerts` 标题改为 map —— `🌙 *美股盘前异动*` / `🌙 *美股盘后异动*` / `🌑 *美股暗盘异动*`。

**阈值不分段**（YAGNI）：夜盘流动性低、跳价可能刷屏，但当前无实测噪音数据。先复用 `threshold_pct: 3`，§8 实测后再决定是否引入 `overnight_threshold_pct`。

**`watch_preload` / `watch_extended_alert`**：时段判定改为 `get_us_session() in ('pre', 'post', 'overnight')`；频率（3 tick）与退避键（`US_EXT`）不变。`watch_extended_alert._pushed` 随 session 变化清空的现有逻辑天然覆盖新增的 overnight 段，无需改动。

## 8. 夜盘语义验证（北京 08:00 后执行）

唯一必须在真实窗口完成的验证：确认 `overnight == 1` 时 `pPrice` 为夜盘实时价。

判据：对照该票 ET 20:00 收盘价，`pPrice` 应随时间变化并产生偏离。

若不符（`pPrice` 在夜盘停更），夜盘一态降级为「仅显示时段标签、价格留空、不推 Slack」，§3 / §5 / §6 的其余设计不受影响。

## 9. 术语清理

以下文件中指代盘前/盘后的「暗盘」一律改为「盘前/盘后」，该词腾出专指夜盘：

`app/services/unified_stock_data.py`（含日志前缀 `[数据服务.暗盘]` → `[数据服务.盘前盘后]`）、`app/services/trading_calendar.py`、`app/services/notification.py`、`app/strategies/watch_extended_alert/__init__.py`、`app/strategies/watch_preload/__init__.py`、`app/static/js/watch.js`、`tests/test_watch_extended_alert.py`、`tests/test_watch_us_extended.py`、`.claude/rules/watch.md`、`.claude/rules/notifications.md`。

标识符保持不变：`extended`、`get_us_extended_quotes`、`cache_type='extended'`、`watch_extended_alert`、`US_EXT`、`ext`。英文 extended hours 语义准确，改名需动策略目录名、config.yaml、DB 策略记录与 API 契约，收益为负。

`docs/stock-analytics/sectors/ai-application/software/2026-08-03-迅策科技-buffett分析.md` 中的「暗盘」指港股新股暗盘，用法正确，不动。

## 10. 测试

全部 mock HTTP，不打真实网络。

- `tests/test_watch_us_extended.py` 扩四态边界，重点覆盖：周五 20:00 非夜盘、周日 20:00 是夜盘、半日市 13:00 收盘后为 post
- 新增 `tests/test_webull_quote.py`：字段映射（`pChRatio * 100`）、tickerId 解析与缓存、Webull 失败回落 yfinance、session 以时钟为准而非 Webull `overnight` 字段
- 缓存 session 失效（盘前价不串入盘中）
- `tests/test_watch_extended_alert.py` 补 overnight 用例

## 11. 文档同步

- `.claude/rules/watch.md`、`.claude/rules/notifications.md` 更新为四态模型
- `CLAUDE.md` 项目概述的数据源清单补入 Webull
- 无新增环境变量（Webull 不需要 key），`.env.sample` 不动
