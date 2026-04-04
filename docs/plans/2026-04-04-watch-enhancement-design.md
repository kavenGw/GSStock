# 盯盘功能增强设计

## 目标

1. 后端调度器主动预取所有盯盘数据，前端只读缓存不触发API
2. 修复7日tab卡死问题（渐进渲染 + 超时兜底）
3. 前端缓存从 sessionStorage 迁移到 localStorage，按市场分key存储

## 方案概述

调度器预取 + 端点瘦身。新增 `watch_preload` 调度策略预取数据，现有端点改为只读缓存。

---

## 一、后端调度预取

### 新增策略 `watch_preload`

位置：`app/strategies/watch_preload/`

| 任务 | 调度规则 | 说明 |
|-----|---------|------|
| 价格预取 | `*/1 9-15 * * 1-5`（A股）/ 按市场开盘时段 | 每分钟，仅开盘市场 |
| 7d/30d走势 | `*/15 9-15 * * 1-5` | 每15分钟 |
| AI分析(realtime) | 复用现有 `watch_realtime` | 每15分钟 |

单个策略，`scan()` 内部按频率分支：每次调用都预取价格，每15次（约15分钟）预取走势数据。通过实例变量 `_tick_count` 计数。

预取逻辑：
1. `WatchService.get_watch_codes()` 获取盯盘列表
2. 按市场分组，检查开盘状态（`MarketSession`），仅处理开盘市场
3. 价格：每次 `scan()` 调用 `get_realtime_prices(codes, force_refresh=True)`
4. 走势：`_tick_count % 15 == 0` 时调用 `get_trend_data(codes, days=7/30)`

### TTL 调整

`market_session.py` 中 `TTL_TRADING` 从30分钟降为1分钟。

### 端点改为只读

| 端点 | 现行为 | 新行为 |
|------|-------|--------|
| `GET /watch/prices` | 缓存miss → 调API | 只读缓存，miss返回空 + `stale: true` |
| `GET /watch/chart-data` | 缓存miss → 调API | 只读缓存，miss返回空 + `stale: true` |
| `POST /watch/analyze` | 触发LLM | 改GET，只读 WatchAnalysis 表 |
| `GET /watch/analysis` | 读今日分析 | 不变 |

---

## 二、前端缓存重构

### localStorage 分key存储

替换 `WatchCache`（sessionStorage 单key）为 `WatchStore`。

Key 命名：`watch_{dataType}_{market}`

| Key 示例 | 内容 |
|---------|------|
| `watch_prices_A` | A股实时价格 |
| `watch_prices_US` | 美股实时价格 |
| `watch_chart7d_A` | A股7日走势 |
| `watch_chart30d_A` | A股30日走势 |
| `watch_analysis_A` | A股AI分析 |
| `watch_meta` | 元数据（日期） |

过期策略：
- `watch_meta.date !== today` → 清除所有 `watch_*` key
- 价格数据带 `timestamp`，超2分钟标记 stale（UI显示灰色）

### WatchStore API

```javascript
WatchStore.get(type, market)         // 读取
WatchStore.set(type, market, data)   // 写入 + timestamp
WatchStore.isStale(type, market)     // 过期检查
WatchStore.clearAll()                // 日期切换清空
```

---

## 三、7日tab渐进渲染

### 渲染流程

1. 先从 localStorage 读取已有7日数据，立即渲染
2. 缺失股票逐只请求 `/watch/chart-data?period=7d`
3. 每只返回后立即 `addSeries` 追加到图表
4. 全部完成后更新 localStorage

### 超时策略

- 单只股票：5秒超时，超时显示"暂无数据"占位
- 整体：15秒总超时，未完成全部标记"暂无数据"
- 显示加载进度（如 "3/5"）

### 错误处理

| 场景 | 显示 |
|------|------|
| 后端返回 `stale: true` | 正常渲染 + 角标"数据较旧" |
| 后端返回空 | "暂无数据，后台正在获取" |
| 网络错误 | "网络异常，请稍后重试" |

---

## 四、数据流全景

### 后端

```
调度器
  ├── watch_preload (每1分钟) → 价格缓存
  ├── watch_preload (每15分钟) → 7d/30d走势缓存
  └── watch_realtime (每15分钟) → AI分析 → WatchAnalysis表
```

### 前端

```
页面加载
  ├── WatchStore 恢复缓存 → 立即渲染
  ├── 价格轮询 (60s) → GET /watch/prices → 增量更新
  ├── 分析轮询 (15min) → GET /watch/analysis → 更新
  └── 切换tab → WatchStore有数据立即渲染 → 缺失逐只加载
```

### 降级策略

| 场景 | 行为 |
|------|------|
| 调度器挂了 | 前端读过期缓存，UI提示"数据较旧" |
| API数据源全挂 | 调度器用过期缓存降级 |
| LLM不可用 | 分析为空，显示"分析暂不可用" |
| localStorage满 | catch错误，降级为内存变量 |
