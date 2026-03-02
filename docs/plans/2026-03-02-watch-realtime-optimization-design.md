# 盯盘助手实时走势优化设计

**日期**: 2026-03-02
**状态**: 已批准

## 目标

优化盯盘助手的数据获取和走势图更新机制：
1. 前端本地缓存（sessionStorage），页面刷新零等待恢复
2. 走势图通过追加报价数据点实时动态更新，消除定时全量重获取
3. 减少后端请求量，合并接口、降频非关键请求

## 方案选择

**方案 A：增量 API + 前端累积缓存**（已选定）

后端提供增量分时数据支持，前端维护 sessionStorage 缓存层，走势图通过追加新数据点更新而非全量重绘。

## 设计详情

### 1. 前端本地缓存层

存储方式：`sessionStorage`（标签页关闭自动清除）

```javascript
// key: "watch_cache"
{
  date: "2026-03-02",           // 缓存日期，跨日自动失效
  prices: {                      // 实时报价
    "600519": { price: 1850, change: 20, change_pct: 1.09, ... }
  },
  benchmarks: [                  // 基准标的报价
    { code: "GC=F", price: 2850, ... }
  ],
  intradayData: {                // 分时数据
    "600519": [
      { time: "09:30", close: 1830 },
      { time: "09:31", close: 1832 }
    ]
  },
  analyses: {                    // AI分析结果
    "600519": {
      "realtime": { support_levels: [...], resistance_levels: [...], summary: "..." },
      "7d": { ... },
      "30d": { ... }
    }
  },
  marketStatus: { ... }
}
```

缓存策略：
- 页面加载时先从 sessionStorage 读取，立即渲染
- 然后后台发请求更新数据
- 跨日自动清空（`date` 不匹配时丢弃全部缓存）
- 写入节流：500ms 内合并写入，避免频繁 IO

### 2. 走势图实时动态更新

消除定时调用 `/chart-data`，改为从报价数据追加走势图数据点：

```
初始加载: GET /chart-data?period=intraday → 完整分时数据 → 存入缓存 + 渲染
每60秒:   GET /prices → 报价 → 提取 (时间, price) → 追加到本地 intradayData → ECharts 增量更新
```

去重逻辑：时间精确到分钟作为 key，同一分钟覆盖而非追加。

### 3. 减少后端请求量

| 请求 | 优化前 | 优化后 |
|------|--------|--------|
| `/watch/prices` | 每60秒 | 每60秒（保持，合并基准标的） |
| `/watch/chart-data` × N | 每60秒 × N只股票 | 仅初始加载 × N |
| `/watch/benchmarks` | 每60秒 | 消除（合并到 /prices） |
| `/watch/market-status` | 每60秒 | 每5分钟 |

`/watch/prices` 合并返回基准标的：
```json
{
  "success": true,
  "prices": { "600519": {...} },
  "benchmarks": [{ "code": "GC=F", "name": "COMEX黄金", "price": 2850, ... }]
}
```

### 4. 整体刷新流程

**初始化**：
1. 读取 sessionStorage → 有缓存且同日则立即渲染，否则骨架屏
2. 并行请求：/watch/list, /watch/prices, /watch/market-status, /watch/analysis
3. 响应后更新缓存+渲染
4. 逐只股票加载分时数据（/chart-data?period=intraday × N）
5. 启动定时器

**定时器**：
- 价格刷新：60秒（/prices，追加走势图数据点）
- 市场状态：5分钟
- AI分析：15分钟（仅开市中）

**60秒刷新周期**：
1. GET /watch/prices → 响应
2. 更新价格 DOM（卡片价格、涨跌幅、基准标的）
3. 对每只开市中的股票：提取 (分钟时间, price) → 追加到 intradayData → ECharts setOption 增量更新
4. 写入 sessionStorage（节流）

## 涉及文件

- `app/routes/watch.py` — 合并 benchmarks 到 /prices 接口
- `app/static/js/watch.js` — 本地缓存层、走势图增量更新、刷新流程重构
