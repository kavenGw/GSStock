# 简报缓存优化设计

## 问题

第二次打开每日简报时仍在从外部API获取数据（新浪财经等），导致加载慢且出现API错误。

## 根因

1. `get_sector_ratings()` 在缓存未命中时同步调用 `get_realtime_prices()` → 触发外部API
2. 指数/期货/ETF的异步刷新 `refresh_async()` 在后台触发API调用
3. A股板块数据使用硬编码的8小时TTL判断，可能导致不必要的重新获取
4. 各子模块缓存逻辑不一致，没有统一的"当天已获取"标记

## 设计

### 缓存分层策略

| 数据类型 | 缓存策略 | 失效时间 |
|---------|---------|---------|
| 实时股价（price） | SmartCacheStrategy TTL | 交易时段30分钟，收盘后到下个开盘 |
| 指数、期货、ETF溢价、板块涨幅、板块评级 | 当天永久缓存 | 下个交易日（通过 effective_cache_date 自动切换） |

### 修改范围

1. **briefing.py** — 简化各子模块缓存逻辑
   - `get_indices_data()`: 移除异步刷新逻辑，有缓存直接返回
   - `get_futures_data()`: 同上
   - `get_etf_premium_data()`: 同上
   - `get_cn_sectors_data()`: 移除 CacheValidator.should_refresh() 检查
   - `get_sector_ratings()`: 移除 get_realtime_prices() 同步调用

2. **unified_stock_data.py** — `get_cn_sector_data()` 移除 8小时 age 判断

3. **routes/briefing.py** — 移除非股价接口的 force 参数
