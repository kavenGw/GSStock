# 盯盘助手走势图设计

## 概述

在盯盘卡片内嵌入迷你走势图，支持分时图和日K线，叠加支撑位/阻力位/布林带标注。

## 技术方案

使用 ECharts（项目已引入），原生支持K线、markLine标注、布林带叠加。

## 数据层

### 新增分时数据接口

`UnifiedStockDataService.get_intraday_data(stock_codes, interval='1m')`

- A股：akshare `stock_zh_a_hist_min_em`（东方财富分时数据）
- 美股/港股：yfinance `download(interval='1m')`

### 缓存策略

复用现有两层缓存架构（内存 + DB持久化）：

| 数据类型 | cache_type | TTL |
|---------|-----------|-----|
| 分时数据 | `intraday_{interval}` | 交易时段1分钟 / 收盘后8小时 |
| 日K数据 | `ohlc_{days}` | 现有策略不变 |

### 新增API端点

`GET /watch/chart-data?code={code}&period={period}`

- period: `intraday` / `7d` / `30d` / `90d`
- 返回: `{ohlc/price, bollinger, support, resistance}`

## 前端设计

### 布局

盯盘卡片内嵌图表容器（高度150-180px），默认折叠，点击展开。

### 工具栏

`分时 | 7天 | 30天 | 90天` pill按钮组切换周期。

### 图表内容

- **分时模式**：折线图 + 半透明面积填充
- **日K模式**：K线蜡烛图（红涨绿跌）
- **叠加标注**：
  - 支撑位：绿色虚线水平线 + 价格标签
  - 阻力位：红色虚线水平线 + 价格标签
  - 布林带：上/中/下轨 + 半透明区域（仅日K模式）

### 交互

- 鼠标悬停tooltip
- 展开时按需加载，骨架屏过渡

## 数据流

```
点击卡片展开 → GET /watch/chart-data
  → get_intraday_data() 或 get_trend_data()
  → TechnicalIndicatorService 计算布林带
  → WatchAnalysis 查询支撑/阻力位
  → JSON响应 → ECharts渲染
```

## 修改文件

- `app/services/unified_stock_data.py` — 新增 `get_intraday_data()`
- `app/routes/watch.py` — 新增 `/watch/chart-data`
- `app/templates/watch.html` — 卡片内图表容器+切换按钮
- `app/static/js/watch.js` — ECharts图表渲染逻辑
