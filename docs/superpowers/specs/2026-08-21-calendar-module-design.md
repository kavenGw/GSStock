# 事件日历模块 — 双月日历页 + 盯盘股事件聚合 + 每日推送段落

> 状态：已批准 · 日期：2026-08-21 · 页面：`/calendar` · 频道：news_daily

## 背景

盯盘池（`WATCH_CODES`，约 30 只，A/HK/KR 混合）的关键时点分散在各处，没有统一的时间维度视图：

- 财报日只在每日推送里以「未来 7 天」文本片段出现（`NotificationService.format_earnings_alerts`）。
- 除权除息日完全没有采集。
- FOMC 日期硬编码在 `app/services/fed_rate.py:63` 的 `FOMC_MEETINGS`，只到 2025-12，且仅服务于利率概率计算，不对外展示。

### 现状勘察结论（实测）

1. **A 股财报日期采集是空壳**。`app/services/earnings.py:198` 的 `_fetch_earnings_akshare` 直接返回 `{'last_earnings_date': None, 'next_earnings_date': None}`，从未接过数据源。因此 `format_earnings_alerts`（`notification.py:244`）用 `non_a_codes = [c for c in codes if not is_a_share(c)]` **显式剔除全部 A 股**——盯盘池里一半以上标的的财报提醒长期缺失。

2. **巨潮预约披露可用**。`akshare.stock_report_disclosure(market='沪深京', period='2026半年报')` 返回 5549 行，列为 `股票代码 / 股票简称 / 首次预约 / 初次变更 / 二次变更 / 三次变更 / 实际披露`，盯盘 A 股全覆盖。实测样本（2026-08-21）：京东方 08-29、通富微电 首次预约 08-26 → 初次变更 08-29、长电科技 08-21 已实际披露。三段字段天然支撑「预约 / 改期 / 已确认」三态。
   **坑**：期次参数格式为 `2026半年报` / `2026三季` / `2026年报` / `2026一季`（非 `三季报`）。尚未发布的期次返回空 DataFrame，akshare 内部硬赋 10 个列名会抛 `ValueError: Length mismatch`，必须逐期次 `try/except` 包裹。

3. **非 A 股一次调用拿两类事件**。`yfinance.Ticker(code).calendar` 同时返回 `Earnings Date` 与 `Ex-Dividend Date`。实测 `0700.HK` → `{'Ex-Dividend Date': date(2026,5,15), 'Earnings Date': [date(2026,11,12)], ...}`。
   **坑**：`Ex-Dividend Date` 是「最近一次」除权日，可能已是过去日期，须过滤 `>= today`。

4. **A 股分红除权可用**。`akshare.stock_fhps_em(date='<报告期>')` 含 `股权登记日 / 除权除息日 / 方案进度` 列。

## 目标

1. 新增 `/calendar` 页面，并排展示**当月与下月**，标出盯盘池股票的重要事件。
2. 事件覆盖四类：财报日、除权除息、宏观事件（FOMC/CPI/非农）、手工录入（本期仅预留数据结构，不做录入 UI）。
3. 每日 8:00 推送新增「未来 7 天事件」段落，并作为上下文喂给 GLM 综合分析。

## 非目标

- 月份翻页（仅当月+下月；翻页会连带要求历史月事件不被清理，属另一个量级的改动）。
- 手工录入 UI（二期；本期表结构预留 `source='manual'` 并保证采集任务不删改此类行）。
- 事件范围扩展到持仓股或全部分类股票（仅 `WATCH_CODES`）。

## 关键决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 存储 | 统一 `stock_event` 表，定时物化 | 页面/推送只读表，毫秒响应；可记录事件改期；双月跨度不依赖读时聚合 |
| 唯一键 | 业务键 `(event_type, stock_code, source, period_key)` | 财报改期时 `event_date` 会变，用日期做键会留幽灵行；业务键让采集任务可安全反复重跑 |
| 日历渲染 | 自研 CSS Grid | 只读双月视图不需要 FullCalendar 的多视图/拖拽；避免 vendor 200KB 且重写深色主题 |
| 宏观日程 | 新建 `app/config/macro_calendar.py` | `fed_rate.py` 是利率概率服务，混入 CPI/非农日程会让职责发散 |
| 采集时机 | 独立 strategy，7:30 单独跑 | 8:00 推送链路不扛 30 只股的 yfinance 串行耗时，采集失败不连累整条简报 |
| 推送去重 | 新日历段全量 + 旧财报段降级为补集 | 既不重复也不缩水，顺带修好 A 股财报预警 |

## 一、数据模型

新建 `app/models/stock_event.py` → 表 `stock_event`，走默认 bind（`stock.db` 共享库，不加 `__bind_key__`，`PRIVATE_TABLES` 不动）。建表由 `app/__init__.py:308` 的 `db.create_all()` 自动完成，只需在 `app/models/__init__.py` 导入。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | Integer PK | |
| `event_date` | Date | 事件发生日 |
| `event_type` | String | `earnings` / `ex_dividend` / `macro` / `manual` |
| `stock_code` | String, NOT NULL | `macro` 类存空串 `''`，**不可为 NULL**（见下方唯一约束说明） |
| `stock_name` | String, nullable | 冗余存名，避免渲染时 join |
| `market` | String | `A` / `HK` / `US` / `KR`；宏观事件存 `US` 或 `GLOBAL` |
| `title` | String | 展示主文案，如「中报披露」「除息 HK$4.50」「FOMC 议息」 |
| `detail` | String, nullable | 附注：分红方案、预约 vs 实际、变更历史 |
| `priority` | String | `HIGH` / `MEDIUM` / `LOW`，驱动 chip 配色与排序（见下方赋值规则） |
| `source` | String | `cninfo` / `yfinance` / `akshare` / `fomc` / `manual` |
| `status` | String | `scheduled` / `changed` / `confirmed` |
| `period_key` | String | 业务键组成部分：`2026H1` / `20260630` / `2026-09-17` |
| `extra` | Text, nullable | JSON 文本，存原始字段 |
| `updated_at` | DateTime | 采集时间戳 |

唯一约束：`UniqueConstraint(event_type, stock_code, source, period_key)`。

**`stock_code` 必须 NOT NULL**：SQLite 的唯一索引中 NULL 之间互不相等，若宏观事件的 `stock_code` 存 NULL，唯一约束对这类行完全失效——每次采集都会插入重复的 FOMC 行。因此 `macro` 类事件的 `stock_code` 存空串 `''` 而非 NULL。

**`priority` 赋值规则**：`macro` 全部 `HIGH`；`earnings` 中 `status` 为 `confirmed`/`changed` 的记 `HIGH`、`scheduled` 记 `MEDIUM`；`ex_dividend` 记 `LOW`；`manual` 由录入时指定，默认 `MEDIUM`。

改期时按业务键 upsert 覆盖 `event_date` 并将 `status` 置 `changed`，不新增行。

`source='manual'` 的行为二期录入 UI 预留，**任何采集任务不得删改**。

## 二、采集层

新建 `app/services/calendar_event.py`：`CalendarEventService` + 四个 collector。collector 只产出 `list[dict]` 候选事件、不碰 DB，统一由 `CalendarEventService.upsert_events(events)` 落库，便于单测。

### `collect_earnings_a()`

数据源 `akshare.stock_report_disclosure`。按当前日期推算当月与下月覆盖到的报告期（通常 1~2 个），逐期次 `try/except`（未发布期次会抛 `ValueError`，吞掉继续）。

`event_date` 取值优先级：`实际披露` → `三次变更` → `二次变更` → `初次变更` → `首次预约`，取第一个非空。

`status`：`实际披露` 非空 → `confirmed`；任一变更字段非空 → `changed`；否则 `scheduled`。

`period_key` 归一化为 `2026H1` 形式。仅保留 `WATCH_CODES` 中的 A 股代码。

### `collect_calendar_yf()`

港/美/韩股走 `ticker.calendar`，一次调用同时产出 `earnings` 与 `ex_dividend` 两类事件。复用 `earnings.py` 已有的熔断（`circuit_breaker.is_available('yfinance')`）与 `MarketIdentifier.to_yfinance()`。`Ex-Dividend Date` 过滤 `< today`。逐股串行，沿用现有 `MAX_RETRIES` / `RETRY_DELAY`。

### `collect_dividend_a()`

`akshare.stock_fhps_em(date='<报告期>')`，取 `除权除息日` 非空的行，`detail` 带 `方案进度` 与现金分红比例。仅保留盯盘 A 股。

### `collect_macro()`

纯本地表，不联网。新建 `app/config/macro_calendar.py` 存 2026 年起的 FOMC / CPI / 非农日程。

`fed_rate.py` 的 `FOMC_MEETINGS` 保持原样供利率概率计算使用，不改动；新配置独立维护。

### `CalendarEventService.refresh_all()`

顺序跑四个 collector，每个单独 `try/except`，单点失败不阻断其余。汇总后一次性 upsert。

清理：删除 `source != 'manual'` 且 `event_date` 落在窗口内、但本轮未被 upsert 命中的行（处理事件被撤销）。窗口取「上月初 ~ 下下月末」，比页面展示的双月略宽，避免边界日期被反复增删。

### `CalendarEventService.get_events(start, end)`

纯读表，页面与推送共用。

### 调度

新建 `app/strategies/calendar_event/`，`schedule = "30 7 * * *"`（8:00 每日简报之前跑完）。复用 `Strategy` 基类与 `StrategyRegistry` 的目录自动发现，无需改 registry。

## 三、页面与 API

### 路由

新建 `app/routes/calendar.py` + `calendar_bp`，挂 `/calendar`，形制照 `app/routes/earnings_page.py`：

- `GET /calendar/` — 渲染 `calendar.html`，服务端只传 `INITIAL_MONTHS`（当月与下月的年月），事件数据全部走 API 异步获取，配骨架屏。
- `GET /calendar/api/events?start=YYYY-MM-DD&end=YYYY-MM-DD` — 返回 `CalendarEventService.get_events()` 的 JSON。参数缺省为当月 1 号至下月末。
- `POST /calendar/api/refresh` — 照 `earnings_page.py:refresh` 的异步线程模式（`Thread(target=_run, daemon=True)` + `app.app_context()`），202 返回，手动触发 `refresh_all()`。

在 `app/routes/__init__.py` 建 bp，在 `app/__init__.py:292` 附近 `register_blueprint(calendar_bp)`。

导航栏（`app/templates/base.html:25` 附近）加入口，置于「盯盘」右侧——日历是盯盘的时间维度视图。

### 前端

新增 `app/templates/calendar.html`、`app/static/js/calendar.js`、`app/static/css/calendar.css`。

**布局**：两个月并排（`grid-template-columns: 1fr 1fr`），`<992px` 自动堆叠为上下。每月一个 7 列 CSS Grid，周一起始。今天所在格加高亮边框。

**事件 chip**：按 `event_type` 着色（财报=蓝、除权=绿、宏观=橙、手工=灰），`priority=HIGH` 加左侧色条。单格超过 3 条显示「+N」。chip 上只显示股票简称 + 极短标签（如「兆易 中报」），完整 `title` / `detail` 放 hover title 与抽屉。

**交互**（仅三项）：点格子 → 右侧抽屉列出当天全部事件（股票代码可点，跳 `stock_detail`）；顶部四类型过滤 chips；刷新按钮。

**深色主题**：chip 配色用 CSS 变量定义，跟随 `theme-dark.css`，不硬编码色值。

## 四、每日推送

### 冲突与解法

现有 `format_earnings_alerts`（`notification.py:237`）取**持仓 + 全部分类股票**（`_get_all_watched_codes`，上百只），剔除全部 A 股，报未来 7 天财报。新日历段口径为「盯盘池 30 只、四类事件」，交集是「盯盘池里的非 A 股财报」，直接新增会在同一条 Slack 消息里重复。

采用：**新日历段全量 + 旧财报段降级为补集**。

- 新增 `format_calendar_events()` 负责盯盘池四类事件。
- `format_earnings_alerts` 改为只报**不在 `WATCH_CODES` 中**的持仓/分类股财报，并**去掉 `non_a_codes` 那道 A 股过滤**（A 股现已有巨潮数据）。

结果：不重复、不缩水，并顺带修复 A 股财报预警。

### `format_calendar_events()`

读 `CalendarEventService.get_events(today, today + 7d)`，按日期分组。**不按 `priority` 过滤**——7 天窗口内事件本就不多，全量列出；`priority` 仅决定同一天内的排序（HIGH 在前）。

```
📅 未来7天事件
  今天  兆易创新(603986) 中报披露 · 已确认
        腾讯控股(0700.HK) 除息 HK$4.50
  08-26 通富微电(002156) 中报披露 · 已改期(08-26→08-29)
  09-17 FOMC 议息
```

**插入位置**：`push_daily_report` 的 msg3（市场与数据），紧邻 `earnings.get('text')` 之前。不进 msg1（msg1 为 GLM 核心观点 + 持仓，塞日历会冲淡）。

**喂给 GLM**：`all_data` 加 `'calendar_events': calendar_text`；`app/llm/prompts/daily_briefing.py` 的 `label_map` 加 `'calendar_events': '近期事件日历'`，位置置于 `earnings_alerts` 之前。

**Slack blocks**：`build_market_blocks` 增收一个 `calendar_text` 参数。该函数已有 9 个位置参数，在 `push_daily_report` 的调用处改为关键字传参形式（不改签名结构，不扩散到其他调用方）。

**失败语义**：`get_events` 为纯读表，采集已在 7:30 独立完成。读表异常时 `format_calendar_events` 返回空串，简报其余部分照发（与现有各 `format_*` 一致）。数据陈旧不静默：段落标题带 `max(updated_at)`，超过 24 小时显示「⚠️ 事件数据 N 小时未更新」。

**周末**：`_scan_weekend` 走 `push_daily_extras`，不含市场数据段，日历不进周末推送。

## 五、测试

平铺于 `tests/test_*.py`（遵循仓库约定）。

| 文件 | 覆盖 |
|---|---|
| `test_calendar_event_model.py` | upsert 幂等与业务键：同一 `(event_type, stock_code, source, period_key)` 以不同 `event_date` upsert 两次 → 只剩一行、`event_date` 为新值、`status` 变 `changed` |
| `test_calendar_collectors.py` | 四个 collector 喂 mock DataFrame 验证输出形状。必测：巨潮空返回抛 `ValueError` 时吞异常返回 `[]`；yfinance `Ex-Dividend Date` 为过去日期时被过滤 |
| `test_calendar_refresh_cleanup.py` | `refresh_all` 清理：窗口内未命中的自动行被删、`source='manual'` 的行不被删 |
| `test_calendar_api.py` | 路由层用 `Flask() + register_blueprint(calendar_bp)` 直接注入（避免 `create_app()` 拉起 17 任务 + crawl4ai）；测日期参数缺省与越界。`GET /calendar/` 因 `base.html` 跨 blueprint `url_for` 须走 `app_client` fixture |
| `test_notification_calendar_section.py` | `format_calendar_events` 空表返回空串；`format_earnings_alerts` 改造后不含 `WATCH_CODES` 代码、且 A 股不再被过滤 |

既有 `tests/test_briefing_earnings_alert.py` 需一并核对是否要更新。

## 六、落地顺序

每步可独立验证，不留半截状态：

1. 模型 + upsert + 清理 → 测试绿
2. 四个 collector + `refresh_all` → 手动跑一次，`sqlite3` 直查确认盯盘 A 股中报（京东方 08-29、通富微电 08-29 改期）真的入库
3. `app/config/macro_calendar.py` 补 2026 FOMC/CPI/非农日程
4. 定时 strategy（7:30）
5. 路由 + API → curl 验 JSON
6. 前端双月日历 + 导航入口
7. 推送段落 + `format_earnings_alerts` 降级为补集 + GLM `label_map`
8. 全量 `pytest`，确认无新增 `ModuleNotFoundError`

## 分支

按 `.claude/rules/dev-environment.md`，本项改动 `app/` 代码，属功能开发 → 开独立 git worktree 隔离，不在 main 上进行。
