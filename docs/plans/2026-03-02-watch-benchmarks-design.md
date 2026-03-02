# 盯盘助手 - 预置商品/指数监控区域

## 需求

在盯盘助手页面顶部新增固定的"商品/指数"区域，展示黄金、白银、纳指100的实时价格和涨跌幅。预置固定，不需要用户手动添加，与下方自选股区域独立。

## 架构

### 后端

- `stock_codes.py` 新增 `BENCHMARK_CODES` 配置
- `watch.py` 新增 `/watch/benchmarks` 端点
- 复用 `unified_stock_data_service.get_realtime_prices()`

### 前端

- `watch.html` 页面标题下方新增横向卡片区域
- 每个标的一个小卡片：名称、价格、涨跌幅（带颜色）
- 页面加载时并行请求，复用 60 秒自动刷新

### 预置代码

| 标的 | 代码 | 数据源 |
|------|------|--------|
| COMEX黄金 | GC=F | yfinance |
| COMEX白银 | SI=F | yfinance |
| 纳指100 | ^NDX | yfinance |

### 数据流

```
页面加载 → fetch('/watch/benchmarks')
         → 后端读取 BENCHMARK_CODES
         → unified_stock_data_service.get_realtime_prices()
         → 返回 JSON
         → 前端渲染横向卡片
```
