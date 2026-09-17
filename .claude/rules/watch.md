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
- **美股扩展时段（盘前/盘中/盘后/暗盘）**：`TradingCalendarService.get_us_session()` 判 ET 四态，边界左闭右开：`[04:00, open)` pre、`[open, close)` regular、`[close, 20:00)` post、`[20:00, 04:00)` overnight（暗盘/夜盘）。夜盘归属其结束日的交易日——周五 20:00 后无夜盘，周日 20:00 起有。post 起算取 `get_market_hours` 的 close；**该函数当前硬编码 US 为 (9:30, 16:00)、不查 `early_closes`**，故半日市（如感恩节次日 13:00 收盘）实际仍按 16:00 起算 post，13:00–16:00 会被误判为 regular（此为历史欠债，未在本次范围内修复）。取价主源 **Webull**（`app/services/webull_quote.py`，无需 key，`pPrice`/`pChRatio×100`，tickerId 进程内永久缓存），缺口由 yfinance `Ticker.info` 的 `preMarket*`/`postMarket*` 兜底，**夜盘无兜底**（Yahoo 在 ET 20:00 后 `marketState=CLOSED` 但 `postMarketPrice` 已停更，拿来冒充即陈价）。**夜盘另有一道闸：须 Webull 自报 `overnight=1` 才采用 `pPrice`，否则不给价**——2026-09-17 实测（ET 20:35 夜盘窗口内，6 只票）Webull 仍报 `overnight=0`/`status=A`，`pPrice` 60s 未变且 `pChRatio` 以 `close`(ET 20:00 收盘价) 为基准，即供的是冻结盘后价；不设此闸会把盘后陈价标成「暗盘」显示、并在 20:00 换段（`_pushed` 清空）时把盘后涨跌榜顶着「🌑 暗盘异动」重推一遍。该闸自动恢复：Webull 一旦真供夜盘数据即照常出价。**连带效应**：夜盘因此每晚稳定「取到 0 只」，`US_EXT` 会一路退避到 `BACKOFF_CAP=8`（约 24min 一轮）——这是预期节流不是故障，日志走 debug「无可用报价」而非 warning「取价失败」；且 `_preload_us_extended` 在**换段时清零 `US_EXT` 退避**（`_ext_session` 记录上一段），否则残留计数会跨过 ET 04:00 把盘前前 24 分钟白白跳过。仅内存缓存 `cache_type='extended'` TTL 10min，**缓存值带 session，读取时与当前时段不符即失效**；退避键 `US_EXT`。`watch_preload` 在非盘中扩展时段每 3 tick 调 `get_us_extended_quotes(force_refresh=True)`。`/watch/prices` 每条带 `ext`（非美股为 null），`/watch/market-status` 美股返回 `pre_market`「盘前」/`trading`「盘中」/`post_market`「盘后」/`overnight`「暗盘」（A股港股 `trading` 仍为「交易中」），前端 `isActiveStatus` 把四者视为活跃继续 60s 轮询，summary 表涨跌% 下一行小字显示。扩展时段价不进 `watch_alert` 告警/信号/AI；唯一推送口是 `watch_extended_alert` 策略（每分钟只读 `extended` 缓存，`|change_pct| ≥ threshold_pct`(3) 首推、再走 `restep_pct`(2) 才复推，一 tick 合并一条到 `news_watch`，进程内 `_pushed` 状态随时段切换清空、重启可能重推一次）。SK 海力士无美股行情（OTC HXSCL 在 Yahoo 404），只用 000660.KS。
- **分区指数条**：`MARKET_INDICES`（A=上证 `000001.SS`/创业板 `399006.SZ`/科创50 `000688.SS`，KR=`^KS11`）仅作参照，不进告警/信号/AI。A 指数走 `get_a_share_index_quotes(cache_only=True)`，点击 chip 复用 `/watch/chart-data?period=intraday`。坑：腾讯代码由 `_tencent_code()` 按 `.SS→sh`/`.SZ→sz` 定交易所，上证/科创50 是 0 开头但在沪，不能用裸启发式；`^KS11` 由 `identify` 特判 `KR`。
- **summary 表信号列**：`watch.js` 拉 `GET /watch/signals`（60 日 OHLC）后用 `signal-detector.js`（与 heavy_metals 共享，勿删）算 RSI/MACD/布林/量/均线 + 形态。阈值存 localStorage `watchSignalThresholds`（不带 `watch_` 前缀，避开每日清空）。徽标文案须 HTML 转义。独立 `/alert` 页已删。

## AI 分析调度

- realtime：`watch_realtime` 策略 `*/15 9-23 * * 1-5`，内部查市场状态；`_realtime_push_state` 追踪每股当日已推，首次全推、后续仅推变化。
- 7d/30d：每日简报 8:00 计算并随 Slack 推送。入口 `WatchAnalysisService.analyze_stocks(period, force)`。

## 告警信号管线

`watch_alert.scan`：`check_alerts` 产原始信号 → `WatchSignalPipeline.process`（`watch_signal_pipeline.py`，纯函数）按股合并、加权分级 HIGH/MID/LOW、上下文增强（涨幅/量比/区间位置）→ `push_watch_alerts` 一股一条直推，`scan` 返回 `[]`。跨 tick 去重归 `WatchAlertService._fired`。支撑/阻力**突破类信号须跨越**（`_prev_prices` 上一 tick 在另一侧），仅靠近不报；7d/30d/realtime 入库前 `_sanitize_levels` 剔除错边的位（支撑≥现价、阻力≤现价），防 LLM 把前高当支撑导致创新高时报「跌破支撑」。第 8 检测器 `_check_intraday_momentum`（≤3min ±1.5%，`_price_ring`）。**已知限制**：`_fired`/`_price_ring`/极值/`_momentum_cooldown` 均为进程内状态，盘中重启会重报或漏报。

**价格新鲜度闸门** `price_freshness.py`（纯函数）：阈值 = 2× preload 周期（A/港 120s，美 360s），在 `watch_alert.scan`、`analyze_stocks('realtime')`（7d/30d 不加门）、`push_realtime_analysis` 三处拦截。**盘中突然静默是期望行为**（preload 退避、午休首 tick），排障看日志「跳过N只降级/超龄旧价」。

## 表格排序（通用约定）

- **新增/改动任何数据表格都必须支持点击表头排序**，不允许只留一个写死的默认排序。参考实现：`value_dip.js` 的 `compare()` / `updateHeadIndicator()` + `watch.html` 的 `th.sortable[data-sort]`。
- 三条硬要求：① N/A / null **恒沉底**，不随升降序翻转（否则升序时满屏空值）② 表头带箭头指示当前排序列与方向（未排序列 ↕）③ 中文列用 `localeCompare(..., 'zh-CN')`，不要按码点排。
- 列 key 随状态变化时（如价值洼地的「高点回退」列随 7d/30d/90d 切换 `pullback_*`），`sortKey` 存**逻辑名**（`pullback`），渲染时再映射到实际字段，否则切周期后排序静默失效。
