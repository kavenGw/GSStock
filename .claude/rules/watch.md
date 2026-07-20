---
paths:
  - "app/templates/watch.html"
  - "app/static/**"
  - "app/services/watch*"
  - "app/strategies/**"
  - "app/config/stock_codes.py"
---
# 盯盘助手

> **何时读**：改 app/templates/watch.html、修改盯盘前端 JS、调整 watch_realtime / watch_alert 策略、改 WatchAnalysisService、调整 AI 分析调度（realtime/7d/30d）
> **不必读**：通知格式（见 notifications.md）/ 数据获取主链路

## 盯盘助手配置

**盯盘助手前端架构**：
- 图表：ECharts 分时线图，全宽，支撑/阻力标线，九转信号浮动标注
- 下方双栏：左=AI分析（realtime/7d/30d标签页），右=季度财报表格
- 缓存：localStorage（WatchStore），按市场分key持久化，每日自动清理
- 数据流：init→缓存恢复→API刷新→定时轮询（价格60s/分析15min/市场状态5min）；后端 A股每分钟 force_refresh，美股/港股每3分钟（差异化提频，见 watch_preload）

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |
| `WATCH_ALERT_COOLDOWN_MINUTES` | 盘中极值告警冷却时间（分钟） | `5` |

**AI分析调度**：
- realtime：`watch_realtime` 策略，开盘时段每15分钟（`*/15 9-23 * * 1-5`，内部检查市场状态）
- realtime 增量推送：`_realtime_push_state` 追踪每股当日已推状态，首次完整推送，后续仅推变化（信号/支撑阻力/摘要），无变化跳过
- 7d/30d：每日简报推送时自动计算（8:00am），结果包含在 Slack 消息中
- 分析入口：`WatchAnalysisService.analyze_stocks(period, force)`

## 盯盘告警信号管线（合并/分级/上下文）

`watch_alert.scan` 不再逐条 `event_bus.publish`，而是 `check_alerts` 产原始信号 → `WatchSignalPipeline.process`（`app/services/watch_signal_pipeline.py`，纯函数）按股合并、加权共振分级（HIGH/MID/LOW）、上下文增强（涨幅/量比/区间位置）→ `NotificationService.push_watch_alerts` 一股一条直推、`scan` 返回 `[]`（复用 watch_realtime 直推先例）。跨 tick 去重仍归 `WatchAlertService._fired`；管线只做同 tick 合并。新增第 8 检测器 `_check_intraday_momentum`（≤3min ±1.5% 急拉急跌，`_price_ring` 环形缓冲）。**已知限制**：盯盘内存态（`WatchAlertService._fired`/`_price_ring`/极值/`_momentum_cooldown`）均为进程内变量，盘中重启会重置，可能导致极值重报或跨 tick 去重失效（漏报/重报），健壮性与持久化留后续 spec。

## 盯盘股票池（代码配置，非 DB）

盯盘要盯哪些股票由 `app/config/stock_codes.py` 的 `WATCH_CODES` 常量决定（唯一权威源），不再有 `watch_list` 表/增删 UI/`/watch/add`/`/watch/remove`。改盯盘池=改 WATCH_CODES（每条 `{'code','name','market'}`，`market` 显式写死——`MarketIdentifier` 不认 `.KS` 等后缀会误判）。`WatchService` 的 `get_watch_codes/get_watch_list/get_watched_markets/get_market_map` 全部读该常量。`WatchAnalysis` 表（AI 分析结果）与盯盘池无关，仍在 DB。DB 里遗留的 `watch_list` 孤立表无害，未做 drop 迁移。

## 盯盘 summary 表技术信号列（原 /alert 预警页已并入）

每市场 summary 表有「信号」列：`watch.js` 拉 `GET /watch/signals`（批量 60 日 OHLC）后复用 `signal-detector.js`（与 heavy_metals 页共享，勿删）的 `SignalDetector.detectAll` 逐股算 RSI/MACD/布林/成交量/均线 + 买卖形态（取最近 3 根 K 线内）。阈值（RSI 超买超卖/放量倍数）存独立 localStorage key `watchSignalThresholds`——**不带 `watch_` 前缀**以避开 `WatchStore.clearAll` 每日清空。徽标 `name`/`description` 须 HTML 转义。独立 `/alert` 页（alert.py/alert.html/alert-page.js/alert.css）已删除，能力收缩进此处仅覆盖 `WATCH_CODES`。
