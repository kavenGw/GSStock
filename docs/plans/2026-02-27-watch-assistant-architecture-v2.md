# 盯盘助手架构重整设计 v2

## 概述

在现有架构上增量改造，实现6个核心需求：两阶段初始化、缓存优先加载、休市显示上一交易日分时线、自动AI分析、15分钟定时分析、按市场分组显示。

## 架构方案：增量改造（方案A）

复用现有三层缓存体系和API，最小化改动量。

## 后端变更

### 1. `/watch/prices` 增加 `cache_only` 参数

```
GET /watch/prices?cache_only=true
```

- `cache_only=true`：只读 memory_cache + DB，不触发外部 API，缺失数据返回 null
- `cache_only=false`（默认）：正常走三层缓存 → API

实现：`unified_stock_data_service.get_realtime_prices()` 增加 `cache_only` 参数，为 true 时跳过 API 层。

### 2. `/watch/chart-data` 休市自动返回上一交易日

```
GET /watch/chart-data?code=600519&period=intraday
```

逻辑：
1. 判断该股票市场是否在交易中
2. 交易中 → 返回今日分时数据
3. 休市 → 用 TradingCalendarService 找到上一交易日 → 返回该日完整分时线

响应增加字段：
```json
{
  "success": true,
  "code": "600519",
  "trading_date": "2026-02-26",
  "is_trading": false,
  "data": [...]
}
```

## 前端变更

### 3. 两阶段初始化

```
Watch.init()
  ├─ 阶段1：快速加载（缓存优先）
  │  ├─ /watch/list
  │  ├─ /watch/market-status
  │  ├─ /watch/prices?cache_only=true
  │  └─ /watch/chart-data (每只股票)
  │  → 立即渲染，缓存中没数据的字段显示"--"
  │
  ├─ 阶段2：自动触发分析
  │  ├─ /watch/analyze {period:'7d', force:false}
  │  └─ /watch/analyze {period:'30d', force:false}
  │
  └─ 阶段3：启动定时器
     ├─ 价格刷新定时器（ENV间隔，默认1分钟）
     └─ AI分析定时器（15分钟，仅开市中）
```

### 4. 按市场分组渲染

```
┌─ 市场状态栏
├─ A股分组
│  ├─ 分组标题：🇨🇳 A股 · 交易中
│  └─ 股票卡片...
├─ 美股分组
│  ├─ 分组标题：🇺🇸 美股 · 未开盘
│  └─ 股票卡片...
└─ 港股分组
   └─ ...
```

分组逻辑：stocks 按 market 字段 group by，顺序按 marketStatus 优先级。

### 5. AI 分析触发规则

| 场景 | 触发时机 | period | force |
|------|---------|--------|-------|
| 每天首次加载 | 初始化阶段2 | 7d, 30d | false |
| 开市中定时 | 每15分钟 | realtime | true |
| 用户手动点击 | 按钮触发 | realtime, 7d, 30d | true |

### 6. 定时器管理

```javascript
priceTimer: {
    interval: WATCH_INTERVAL_MINUTES * 60 * 1000,
    condition: hasActiveMarket,
    action: refreshPrices + refreshCharts(增量)
}

analysisTimer: {
    interval: 15 * 60 * 1000,
    condition: hasActiveMarket,
    action: analyze(realtime, force=true)
}
```

市场状态检查：每次价格刷新时同时检查 market-status，所有市场休市则停止定时器。

### 7. 休市后行为

- 停止价格刷新和 AI 分析定时器
- 图表显示上一交易日分时线（后端自动返回）
- 分析面板保持最后一次结果
- 用户仍可手动点击 AI 分析按钮

## 涉及文件

| 文件 | 变更 |
|------|------|
| `app/routes/watch.py` | prices 增加 cache_only，chart-data 休市逻辑 |
| `app/services/unified_stock_data.py` | get_realtime_prices 增加 cache_only 参数 |
| `app/static/js/watch.js` | 两阶段初始化、分组渲染、15分钟分析定时器 |
| `app/templates/watch.html` | 分组容器结构 |
