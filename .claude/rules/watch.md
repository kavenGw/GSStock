# 盯盘助手

> **何时读**：改 app/templates/watch.html、修改盯盘前端 JS、调整 watch_realtime / watch_alert 策略、改 WatchAnalysisService、调整 AI 分析调度（realtime/7d/30d）
> **不必读**：通知格式（见 notifications.md）/ 数据获取主链路

## 盯盘助手配置

**盯盘助手前端架构**：
- 图表：ECharts 分时线图，全宽，支撑/阻力标线，九转信号浮动标注
- 下方双栏：左=AI分析（realtime/7d/30d标签页），右=季度财报表格
- 缓存：localStorage（WatchStore），按市场分key持久化，每日自动清理
- 数据流：init→缓存恢复→API刷新→定时轮询（价格60s/分析15min/市场状态5min）

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |
| `WATCH_ALERT_COOLDOWN_MINUTES` | 盘中极值告警冷却时间（分钟） | `5` |

**AI分析调度**：
- realtime：`watch_realtime` 策略，开盘时段每15分钟（`*/15 9-23 * * 1-5`，内部检查市场状态）
- realtime 增量推送：`_realtime_push_state` 追踪每股当日已推状态，首次完整推送，后续仅推变化（信号/支撑阻力/摘要），无变化跳过
- 7d/30d：每日简报推送时自动计算（8:00am），结果包含在 Slack 消息中
- 分析入口：`WatchAnalysisService.analyze_stocks(period, force)`

## 盯盘股票池（代码配置，非 DB）

盯盘要盯哪些股票由 `app/config/stock_codes.py` 的 `WATCH_CODES` 常量决定（唯一权威源），不再有 `watch_list` 表/增删 UI/`/watch/add`/`/watch/remove`。改盯盘池=改 WATCH_CODES（每条 `{'code','name','market'}`，`market` 显式写死——`MarketIdentifier` 不认 `.KS` 等后缀会误判）。`WatchService` 的 `get_watch_codes/get_watch_list/get_watched_markets/get_market_map` 全部读该常量。`WatchAnalysis` 表（AI 分析结果）与盯盘池无关，仍在 DB。DB 里遗留的 `watch_list` 孤立表无害，未做 drop 迁移。
