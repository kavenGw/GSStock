# watch_alert 港股午休修复 + watch_preload 限流退避 — 设计

日期：2026-07-07

## 背景

2026-07-07 12:11（港股午休时段），`watch_alert` 仍推送「胜宏科技(2476.HK) 当前 253.20 < 前低 254.00」。根因：`TradingCalendarService.is_market_open`（`app/services/trading_calendar.py`）只硬编码了 A 股与日股午休，港股被当作 9:30–16:00 连续交易，午休期间 `watch_preload` 继续预取、`watch_alert` 用午休冻结价反复触发告警。

`watch_alert._calc_trading_minutes` 里另有一份 `SESSIONS` 字典已正确写了港股午休 `(9:30–12:00, 13:00–16:00)`，与 `is_market_open` 不一致——本次 bug 正是两处不一致造成。

附带需求：港股/美股实时价走 yfinance（有限流风险），若 API 限流，预取应自动降频。

## 变更 1：交易时段单一权威源（根因修复）

文件：`app/services/trading_calendar.py`

- 新增类常量 `MARKET_SESSIONS`，分时段市场：
  - `A`: `[(9:30, 11:30), (13:00, 15:00)]`
  - `HK`: `[(9:30, 12:00), (13:00, 16:00)]`（新增午休）
  - `JP`: `[(9:00, 11:30), (12:30, 15:00)]`
  - 其余市场（US/KR/TW/COMEX）不在该字典，沿用 `MARKET_HOURS` 单一时段
- `is_market_open` 改为：市场在 `MARKET_SESSIONS` 中则遍历 sessions 判断当前时间是否落在任一时段内；否则用 `MARKET_HOURS` 区间判断。删除现有 A/JP 两段硬编码 if。
- `app/strategies/watch_alert/__init__.py` 的 `_calc_trading_minutes` 删除本地 `SESSIONS` 字典，改引用 `TradingCalendarService.MARKET_SESSIONS`。

效果：港股午休 12:00–13:00，`is_market_open('HK')` 返回 False → `watch_preload` / `watch_alert` 自动过滤港股 codes（与 A 股午休行为一致），零预取、零告警；冷却期告警不再在午休期间重复触发。

## 变更 2：watch_preload 按市场限流退避

文件：`app/strategies/watch_preload/__init__.py`

- 类级状态 `_backoff: dict[str, dict]`，形如 `{market: {'skip': N, 'remaining': M}}`（进程内，重启丢失，可接受）。
- 每 tick 流程：
  1. 对 `remaining > 0` 的市场：本轮跳过该市场预取，`remaining -= 1`。
  2. 其余市场正常按市场分组调 `get_realtime_prices(codes, force_refresh=True)`。
  3. 失败判定（按市场）：调用抛异常，或返回结果中有效条目（`current_price` 非 None 且非 0）占该市场请求 codes 比例 < 50%。
  4. 失败 → `skip = min(skip * 2, 8)`（初始 1），`remaining = skip`，记 `logger.warning`（含 market、有效占比）。
  5. 成功 → 清除该市场退避状态；若此前处于退避中，记 `logger.info` 恢复。
- 退避只作用于价格预取；A 股分时预取与走势预取逻辑不变（走势 15 分钟一次，频率本身低）。
- `watch_alert` 不改：读 preload 写的缓存，退避期间价格最多旧几分钟，盘中据此告警可接受。

注意：为按市场判定失败，价格预取需改为按 `market_codes` 分组逐市场调用（现为一次性混合调用 `active_codes`）。A 股与港美股本就走不同数据源，分组调用无额外 API 成本。

## 测试

新增 `tests/test_trading_calendar_sessions.py`（或并入现有 calendar 测试）：

- HK 交易日 12:11 → `is_market_open('HK') is False`
- HK 11:59 / 13:01 → True；9:29 / 16:01 → False
- A 股 12:00 → False，JP 12:00 → False（回归）
- US 12:00（当地）→ True（无午休回归）

`watch_preload` 退避测试（mock `get_realtime_prices`）：

- 某市场返回大面积 None → 该市场进入退避，下一 tick 跳过；其他市场正常预取
- 退避到期后重试成功 → 状态清零，恢复每分钟
- 连续失败 → skip 1→2→4→8 封顶

## 不做的事

- 不在 `UnifiedStockDataService` 层做全链路限流感知（本次范围外）
- `watch_alert` 不加价格新鲜度门槛
- 不持久化退避状态
