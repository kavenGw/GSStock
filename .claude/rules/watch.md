---
paths:
  - "app/templates/watch.html"
  - "app/static/**"
  - "app/services/watch*"
  - "app/strategies/**"
  - "app/config/stock_codes.py"
---
# 盯盘助手

> **何时读**：改 watch.html / 盯盘 JS、调 watch_realtime / watch_alert 策略、改 WatchAnalysisService、调 AI 分析调度

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |
| `WATCH_ALERT_COOLDOWN_MINUTES` | 极值告警冷却（分钟） | `5` |

## 前端与数据流

- ECharts 分时图（支撑/阻力标线、九转标注）；下方左=AI 分析（realtime/7d/30d），右=季度财报。
- `WatchStore` 用 localStorage 按市场分 key，每日自动清理。数据流：init → 缓存恢复 → API 刷新 → 轮询（价格 60s / 分析 15min / 市场状态 5min）；后端 `watch_preload` A/港每分钟、美股每 3 分钟 `force_refresh`。
- **盯盘池是代码配置**：`stock_codes.py:WATCH_CODES`（每条 `{'code','name','market'}`，`market` 显式写死，`MarketIdentifier` 不认 `.KS` 等后缀）是唯一权威源，无 `watch_list` 表/增删 UI。`WatchAnalysis` 表只存 AI 结果。
- **分区指数条**：`MARKET_INDICES`（A=上证 `000001.SS`/创业板 `399006.SZ`/科创50 `000688.SS`，KR=`^KS11`）仅作参照，不进告警/信号/AI。A 指数走 `get_a_share_index_quotes(cache_only=True)`，点击 chip 复用 `/watch/chart-data?period=intraday`。坑：腾讯代码由 `_tencent_code()` 按 `.SS→sh`/`.SZ→sz` 定交易所，上证/科创50 是 0 开头但在沪，不能用裸启发式；`^KS11` 由 `identify` 特判 `KR`。
- **summary 表信号列**：`watch.js` 拉 `GET /watch/signals`（60 日 OHLC）后用 `signal-detector.js`（与 heavy_metals 共享，勿删）算 RSI/MACD/布林/量/均线 + 形态。阈值存 localStorage `watchSignalThresholds`（不带 `watch_` 前缀，避开每日清空）。徽标文案须 HTML 转义。独立 `/alert` 页已删。

## AI 分析调度

- realtime：`watch_realtime` 策略 `*/15 9-23 * * 1-5`，内部查市场状态；`_realtime_push_state` 追踪每股当日已推，首次全推、后续仅推变化。
- 7d/30d：每日简报 8:00 计算并随 Slack 推送。入口 `WatchAnalysisService.analyze_stocks(period, force)`。

## 告警信号管线

`watch_alert.scan`：`check_alerts` 产原始信号 → `WatchSignalPipeline.process`（`watch_signal_pipeline.py`，纯函数）按股合并、加权分级 HIGH/MID/LOW、上下文增强（涨幅/量比/区间位置）→ `push_watch_alerts` 一股一条直推，`scan` 返回 `[]`。跨 tick 去重归 `WatchAlertService._fired`。第 8 检测器 `_check_intraday_momentum`（≤3min ±1.5%，`_price_ring`）。**已知限制**：`_fired`/`_price_ring`/极值/`_momentum_cooldown` 均为进程内状态，盘中重启会重报或漏报。

**价格新鲜度闸门** `price_freshness.py`（纯函数）：阈值 = 2× preload 周期（A/港 120s，美 360s），在 `watch_alert.scan`、`analyze_stocks('realtime')`（7d/30d 不加门）、`push_realtime_analysis` 三处拦截。**盘中突然静默是期望行为**（preload 退避、午休首 tick），排障看日志「跳过N只降级/超龄旧价」。
