# 盯盘告警旧价误报修复 — 设计文档

- **日期**：2026-07-10
- **触发**：天岳先进(2631.HK) 推送 "当前 81.50 > 前高 81.40"，价格与实盘对不上
- **诉求**：① 减少取价频率避免失败 ② 失败时下次拿当前时刻价、而非失败时刻的旧价

## 1. 问题根因

港股 2631.HK 走 yfinance（慢、易限流）。链路：

1. `watch_preload`（每分钟）对开盘市场 `force_refresh=True` 取价 → 写缓存。
2. yfinance 失败时 `get_realtime_prices` 走 `_get_expired_cache()` **降级返回上次成功的过期旧价**（标记 `_is_degraded=True`），如 81.50。
3. `watch_alert`（每分钟）读缓存喂 `WatchAlertService.check_alerts()`。检测入口只判 `curr is None`，**完全不看 `_is_degraded`** → 把旧价 81.50 当"当前价"，与盘中前高 81.40 一比就误报"突破前高"。

旧价还会污染盘中极值 `_intraday_extremes`：一次降级读 81.50 会把 `ext['high']` 顶到 81.50，后续真实价的比对基准全部失真。

## 2. 设计

### 改动 1：降低取价频率（诉求 ①）

- 文件：`app/strategies/watch_preload/__init__.py`
- 改动：`schedule = "interval_minutes:1"` → `"interval_minutes:3"`
- yfinance 调用量降到 1/3；已有指数退避机制 `_backoff` 保留不动，叠加后失败进一步减少。
- `watch_alert` **保持每分钟**（只读缓存、不打 API）：preload 每 3 分钟刷到新价后，告警最快 1 分钟内反应，不牺牲响应速度。
- 缓存 TTL 交易时段 30 分钟 ≫ 3 分钟刷新间隔，缓存始终保持温热，watch_alert 读缓存不会因过期触发 API。

### 改动 2：失败时跳过旧价（诉求 ②）

- 文件：`app/strategies/watch_alert/__init__.py`，`scan()` 组装价格处
- 两处修改：

  **a. 改用 `cache_only=True` 读价** —— watch_alert 变纯缓存读取者，彻底不触发 yfinance，保证"打 API"只由 preload 承担（真正落实降频）。

  **b. 过滤 `_is_degraded=True` 条目** —— 降级旧价的股票不进检测：

  ```python
  watch_prices = {c: prices[c] for c in active_codes
                  if c in prices and not prices[c].get('_is_degraded')}
  ```

  被跳过时记一条 `logger.debug`/`info`（含跳过 code 列表），便于排查。

- **顺带删除死代码**：`BENCHMARK_CODES` 在 watch_alert 中只参与取价、从不被 `watch_prices` 消费（`watch_prices` 仅取 `active_codes`）。连同 `from app.config.stock_codes import BENCHMARK_CODES` 一并删除，`all_codes` 简化为 `active_codes` 分流 A 股/其他市场。

### 行为效果

取价失败的那 3 分钟窗口内，该股**完全不参与告警、不更新 `_intraday_extremes`**；等下一次 preload 取到**当前时刻真实价**（新的 `last_fetch_time`）才恢复比对。旧价 81.50 不再进入检测或污染极值，误报根除。这正对应诉求 ②"下次拿当前的时间，而不是失败的时间"。

## 3. 不改的部分

- `WatchAlertService.check_alerts` 及 7 种检测器逻辑不动 —— 脏数据在 preload/strategy 层就被挡住，服务层保持纯粹。
- 退避 `_backoff`、极值冷却 `WATCH_ALERT_COOLDOWN_MINUTES`、日级去重 `_fired`、TD 节流 `TD_CALC_INTERVAL`、参数重试 `PARAMS_RETRY_INTERVAL` 全部保留。

## 4. 验证

- 单测（`tests/test_*.py` 平铺）：
  - 降级条目（`_is_degraded=True`）被 watch_alert 跳过，不产生 Signal、不更新极值。
  - 正常条目照常检测、照常产出信号。
  - watch_preload `schedule` 值为 `interval_minutes:3`。
- 回归：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`

## 5. 涉及文件清单

| 文件 | 改动 |
|------|------|
| `app/strategies/watch_preload/__init__.py` | `schedule` 1→3 分钟 |
| `app/strategies/watch_alert/__init__.py` | `cache_only=True` 读价；过滤 `_is_degraded`；删 `BENCHMARK_CODES` 死代码 |
| `tests/test_watch_alert_*.py` | 新增/补充降级跳过用例 |
