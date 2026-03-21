# 财报估值页面设计

## 概述

新建独立页面 `/earnings`，展示所有股票的季度财报与动态估值数据。通过板块开关筛选（默认展示有持仓的板块），两个Tab分别展示"按利润估值"和"按营收估值"的排序视图。数据由每日调度任务预计算写入缓存表，页面直接读取快照，秒开。

## 数据模型

### 新增表 `earnings_snapshot`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| stock_code | String(20) | 股票代码 |
| stock_name | String(50) | 股票名称 |
| market_cap | Float | 实时市值（元/美元） |
| q1_revenue | Float | 最近第1季度营收 |
| q2_revenue | Float | 最近第2季度营收 |
| q3_revenue | Float | 最近第3季度营收 |
| q4_revenue | Float | 最近第4季度营收 |
| q1_profit | Float | 最近第1季度利润 |
| q2_profit | Float | 最近第2季度利润 |
| q3_profit | Float | 最近第3季度利润 |
| q4_profit | Float | 最近第4季度利润 |
| q1_label | String(10) | 季度标签（如"2025Q3"） |
| q2_label | String(10) | 季度标签 |
| q3_label | String(10) | 季度标签 |
| q4_label | String(10) | 季度标签 |
| pe_dynamic | Float | 市值 / (最新季度利润×4) |
| ps_dynamic | Float | 市值 / (最新季度营收×4) |
| snapshot_date | Date | 快照日期 |
| updated_at | DateTime | 更新时间 |

唯一约束：`(stock_code, snapshot_date)`

Q1 为最近一个季度，Q4 为最早一个季度。季度标签统一格式为 `"YYYYQn"`（如 `"2025Q3"`）。注意 `QuarterlyEarningsService` 返回的 `quarter` 字段格式为 `"Q3'25"`，写入 snapshot 时需转换为 `"2025Q3"` 格式。

## 后端设计

### 路由 Blueprint

新建 `app/routes/earnings_page.py`，Blueprint `earnings_page_bp`，前缀 `/earnings`。

| 路由 | 方法 | 说明 |
|------|------|------|
| `/earnings/` | GET | 渲染页面，传入分类列表 |
| `/earnings/api/data` | GET | 查询快照数据 |
| `/earnings/api/refresh` | POST | 手动触发重新计算 |

#### `GET /earnings/api/data`

参数：
- `categories`：启用的板块ID，逗号分隔
- `sort`：排序字段，`pe_dynamic` 或 `ps_dynamic`，默认 `pe_dynamic`
- `order`：排序方向，`asc` 或 `desc`，默认 `asc`

返回：
```json
{
  "categories": [{"id": 1, "name": "科技", "count": 5}],
  "stocks": [
    {
      "stock_code": "600519",
      "stock_name": "贵州茅台",
      "market_cap": 2280000000000,
      "quarters": ["2025Q2", "2025Q3", "2025Q4", "2026Q1"],
      "revenue": [390.5, 410.2, 450.8, 480.1],
      "profit": [180.3, 195.6, 220.1, 240.5],
      "pe_dynamic": 23.7,
      "ps_dynamic": 11.9,
      "updated_at": "2026-03-21 08:00"
    }
  ],
  "snapshot_date": "2026-03-21",
  "is_today": true
}
```

逻辑：
1. 优先查当天 `earnings_snapshot`
2. 无当天数据则降级到最近一天的快照，`is_today: false`
3. 按 `categories` 参数过滤（通过 StockCategory 关联）
4. 按 `sort` + `order` 排序返回

#### `POST /earnings/api/refresh`

触发当天快照重新计算（异步，返回202）。供手动刷新使用。前端收到202后显示"正在刷新"提示，用户手动刷新页面查看最新数据。

### 市值获取

新增 `app/services/market_cap_service.py`，`MarketCapService` 类：

- `get_market_caps(stock_codes: list) -> dict`
  - A股：akshare `stock_individual_info_em(symbol)` 提取总市值
  - 美股/港股：yfinance `Ticker(code).info['marketCap']`
  - 返回 `{code: market_cap_float}`
  - 单只失败返回 None，不影响其他

### 调度任务

新增策略插件包 `app/strategies/earnings_snapshot/`，遵循项目策略自动发现机制：

```
app/strategies/earnings_snapshot/
├── __init__.py      # 定义 EarningsSnapshotStrategy(Strategy)
└── config.yaml      # 调度配置
```

`EarningsSnapshotStrategy` 继承 `Strategy` 基类（`app/strategies/base.py`），实现 `scan()` 方法：

- `name = "earnings_snapshot"`
- `schedule = "0 8 * * 1-5"`（工作日8:00）
- `scan()` 返回 `list[Signal]`（成功/失败摘要信号）
- 执行逻辑：
  1. 从 Stock 表获取所有股票（通过 `MarketIdentifier.is_etf()` 排除ETF）
  2. 调用 `MarketCapService.get_market_caps()` 批量获取市值
  3. 调用 `QuarterlyEarningsService.get_earnings()` 逐股票获取季度财报
  4. 计算 `pe_dynamic = market_cap / (q1_profit × 4)`，`ps_dynamic = market_cap / (q1_revenue × 4)`
  5. 写入 `earnings_snapshot` 表（upsert by stock_code + snapshot_date）
- 失败处理：单只股票失败记录日志，跳过继续
- 历史清理：在 `scan()` 末尾执行，保留最近7天快照，超期删除

## 前端设计

### 页面结构

新建 `app/templates/earnings_page.html`，继承 `base.html`。

```
┌─────────────────────────────────────────┐
│  财报估值                    [刷新按钮]  │
├─────────────────────────────────────────┤
│  [科技 ✓] [消费 ✓] [金融 ✗] [医药 ✗]   │  ← 板块Toggle开关
├─────────────────────────────────────────┤
│  [按利润估值] [按营收估值]               │  ← Tab切换
├─────────────────────────────────────────┤
│  代码 | 名称 | 市值 | Q1 | Q2 | Q3 | Q4 | 估值比↑ │  ← 表格
│  ...                                     │
└─────────────────────────────────────────┘
```

### 板块Toggle开关

复用预警中心的Toggle组件模式：
- 从 `/earnings/api/data` 返回的 `categories` 动态渲染
- 默认启用有持仓的板块（后端根据 StockPosition 判断）
- Toggle状态持久化到 `localStorage`（key: `earningsPageConfig`）

### Tab 切换

两个Tab：
- **按利润估值**：表格列为"代码、名称、市值、Q1利润、Q2利润、Q3利润、Q4利润、PE动态"，按 `pe_dynamic` 升序排序
- **按营收估值**：表格列为"代码、名称、市值、Q1营收、Q2营收、Q3营收、Q4营收、PS动态"，按 `ps_dynamic` 升序排序

切换Tab时重新请求API（带不同 sort 参数），或前端缓存数据直接切换列和排序。

### 加载状态

使用骨架屏（复用项目已有的 Skeleton 工具），表格行用骨架屏占位。

### 数据格式化

- 市值：自动缩放显示（亿/万亿）
- 营收/利润：自动缩放（万/亿）
- 估值比：保留1位小数
- 亏损股票：`pe_dynamic` 存储为 `None`（数据库NULL），前端显示"亏损"，排序时 NULL 排在最后（无论升序降序）
- 营收为零或负：`ps_dynamic` 同样存储为 `None`
- 无数据：显示"-"

### JavaScript

新建 `app/static/js/earnings-page.js`：
- `EarningsPage` 类，管理板块Toggle、Tab切换、表格渲染
- 配置持久化到 localStorage
- 表格支持点击列头排序（升/降切换）

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/models/earnings_snapshot.py` | 新建 | SQLAlchemy 模型 |
| `app/services/market_cap_service.py` | 新建 | 市值获取服务 |
| `app/strategies/earnings_snapshot/__init__.py` | 新建 | 每日预计算调度策略 |
| `app/strategies/earnings_snapshot/config.yaml` | 新建 | 策略配置 |
| `app/routes/earnings_page.py` | 新建 | 路由 Blueprint |
| `app/templates/earnings_page.html` | 新建 | 页面模板 |
| `app/static/js/earnings-page.js` | 新建 | 前端逻辑 |
| `app/static/css/earnings-page.css` | 新建 | 页面样式 |
| `app/routes/__init__.py` | 修改 | 注册新 Blueprint |
| `app/templates/base.html` | 修改 | 侧边栏新增入口 |
