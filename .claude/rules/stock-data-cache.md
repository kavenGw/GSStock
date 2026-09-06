---
paths:
  - "app/services/**"
  - "app/utils/**"
---
# 数据架构与缓存

> **何时读**：改 app/services/ 下 fetcher、写涉及 UnifiedStockCache 的 SQL、调缓存命中/TTL、新增市场或数据源、改 Volume 单位

## 统一入口

所有持仓/期货/盯盘/预加载/季报/TD九转服务统一走 `UnifiedStockDataService`（单例）的 `get_realtime_prices` / `get_trend_data` / `get_indices_data` / `get_intraday_data`；`WatchAnalysisService` 是聚合层不直连数据源。`_SafeJsonProvider`（`app/__init__.py`）全局把 NaN/Infinity 转 null。

**市场识别** `app/utils/market_identifier.py`：`identify(code)` 返回 `'A'`（6 位数字，6 开头 `.SS`、0/3 开头 `.SZ`）/ `'US'`（字母）/ `'HK'`（`.HK` 后缀）/ `'KR'`（`^KS11` 特判）；`to_yfinance` / `is_a_share` / `is_index`。

**数据源**：A 股实时价/分时优先腾讯 `qt.gtimg.cn`；港股腾讯 `q=r_hk<code>` 优先、yfinance 兜底（裸 `hk` 前缀是 15 分钟延迟，实时价勿用）；美股 yfinance。字段索引与取数坑见 data-fetch-conventions.md。

## 缓存

```
内存缓存 MemoryCache（data/memory_cache/{code}/{cache_type}.pkl，延迟 5s flush，启动恢复）
  ↓ miss
数据库缓存 UnifiedStockCache（唯一约束 (stock_code, cache_type, cache_date)，JSON 列名 data_json）
  ↓ miss/expired
API（akshare / yfinance / 腾讯）
```

| cache_type | TTL |
|------------|-----|
| `price` / `ohlc_{days}` / `index` | 交易时段 30 分钟 / 收盘后 8 小时 |
| `quarterly_earnings` | 7 天 |

- 实时价非交易时间跳过 API；OHLC 非交易时间仍可取，但要检查 `data_end_date` 含最近交易日。
- **缓存日期统一走 `SmartCacheStrategy.get_effective_cache_date(code)`**（批量 `_get_effective_cache_dates(codes)`）而非 `date.today()`，让「今日」跟随该股市场的有效交易日；API 查询区间仍用 `date.today()`。
- `get_realtime_prices(..., cache_only=True)` 只读内存+DB、未命中 code 不在返回里（前端显「—」），首屏/只读渲染用它；要最新价才 `force_refresh=True`。内存缓存可能存 `price=None` 的失败条目，「全部命中」不等于数据可用。
- `_retry_fetch()` 3 次间隔 1 秒；`_get_expired_cache()` 降级返回过期缓存；`CacheValidator.should_refresh()` 返回需刷新列表。
- 直连查缓存：`SELECT data_json FROM unified_stock_cache WHERE stock_code=? AND cache_type='price' ORDER BY cache_date DESC LIMIT 1`。
- **策略协作**：`watch_preload`（A/港每分钟、美股每 3 分钟）负责 `force_refresh` 写缓存，`watch_alert` 等只读缓存。

## 返回结构契约

- 实时价 `PriceData`：`{code, name, price, change, change_pct, volume, high, low, open, prev_close, last_fetch_time, market}`（键是 `price` 不是 `current_price`；`IndexData` 才用 `current_price`/`change_percent`）。yfinance A 股兜底 `name=stock_code`，需 fallback 到调用方的 stock_name。
- `get_trend_data()` / `get_indices_data()` 返回 `{'stocks': [{stock_code, stock_name, data: [OHLC...]}], 'date_range': {start, end}}`，是 **list**，按 code 访问先 `{s['stock_code']: s for s in result['stocks']}`。OHLC 行 `{date, open, high, low, close, volume, change_pct}`。

## Volume 单位契约

A 股 `volume` 统一为**手**（100 股）；港股、美股为股。各源原生单位登记在 `unified_stock_data.py:VOLUME_SOURCE_UNITS`（腾讯 qt/fqkline/mkline=手；新浪=股；东财 hist/push2his/spot_em/hist_min/intraday_em/fund_etf_hist_em=手；yfinance=股），所有落点调 `_normalize_volume(raw, source, market)`，**禁止内联 `//100`**；source 未登记抛 KeyError。`tests/test_volume_alert_unit_consistency.py` 用 AST 守住。单位契约变更时 bump `VOLUME_UNIT_SCHEMA_VERSION`，启动时与 `data/memory_cache/.schema_version` 不匹配自动清空内存与 DB 缓存。

## A 股行情特征

- 节假日（五一/国庆/春节）OHLC 缺日期，跨市场事件分析要识别假期错位，节后首日是情绪集中释放点。
- 一字涨停：O=H=L=C + 量比 < 1，不可当正常 K 线算技术指标。
