# 估值页首屏秒开（cache-first）设计

- 日期：2026-06-20
- 范围：`/valuations`（价值洼地）页首屏加载性能

## 问题

点击「价值洼地」估值页需等待很久（几十秒白屏）。

根因在 `app/routes/valuations.py` 的 `index()`：渲染前**同步**调用
`get_realtime_prices()` 拉取全部 157 只标的实时价，**拉完才返回 HTML**。
其中 116 只 A 股走腾讯批量接口（快），但 33 只港股 + 8 只美股走 yfinance
逐只串行，缓存冷时每只 1~3 秒并叠加重试 → 首屏阻塞数十秒。

页面其实已有 `/valuations/api/prices` 异步接口与前端填充逻辑（刷新按钮用），
但首屏未用它，而是走了阻塞式服务端渲染。

## 目标

- 首屏秒开。
- 缓存优先：首屏只读缓存、不触发任何外部 API。
- 取最新价为纯手动：点「刷新」按钮（force）。

## 方案

服务端首屏取价改为 `cache_only=True`。该参数已在
`app/services/unified_stock_data.py:576` 实现：只读内存 + DB 缓存、跳过第三层
API 获取，未命中的 code 直接不在返回字典里（前端单元格显示「—」）。
取价耗时从几十秒降至毫秒级。

### 改动清单（共 2 处）

1. `app/routes/valuations.py` 的 `index()`：取价调用加 `cache_only=True`

   ```python
   raw = unified_stock_data_service.get_realtime_prices(
       list(fetch_map.values()), cache_only=True)
   ```

2. `tests/test_valuations.py:85`：`app_client` fixture 的取价桩
   `lambda codes, force_refresh=False: {}` 不接受 `cache_only`，不改会
   `TypeError`。改为：

   ```python
   lambda codes, force_refresh=False, cache_only=False: {}
   ```

### 不改动

- `/valuations/api/prices`（刷新按钮路径）保持 `force` 透传，是用户主动取最新价的唯一入口。
- 前端 JS、排序、分组、降级逻辑全不动。`_enrich` 对无价 code 已按
  `margin_base is None` 排末位。

## 行为变化

- 缓存热（多数情况，A 股有 `watch_preload` 每分钟写缓存）→ 首屏即显缓存价，秒开。
- 缓存冷的港股/美股 → 首屏显「—」，点刷新后填入（用户选定的"纯手动"取舍）。

## 验证

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_valuations.py -v
```

全部用例通过。
