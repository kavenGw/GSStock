# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人股票管理工具，用于管理多个证券账户的持仓情况。支持上传持仓截图自动识别、多账户合并、操作建议记录。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python run.py

# 一键启动（启动并打开浏览器）
start.bat
```

访问地址：http://127.0.0.1:5000

## 架构概览

```
app/
├── __init__.py        # Flask 工厂模式 create_app()
├── config/            # 配置模块（股票代码、数据源、通知）
├── models/            # SQLAlchemy 模型
├── routes/            # Flask Blueprint 路由（14 个模块）
├── services/          # 业务逻辑层（数据、分析、交易等）
├── llm/               # LLM 路由和提供者（智谱 GLM）
├── notifications/     # 通知系统（Slack）
├── strategies/        # 策略插件系统（自动发现注册）
├── scheduler/         # APScheduler 后台调度 + 事件总线
├── middleware/        # Flask 中间件
├── utils/             # 工具函数
├── templates/         # Jinja2 模板
└── static/            # CSS/JS 静态资源
```

## 核心设计

**数据模型**：按日期保存持仓快照，`(date, stock_code)` 为唯一约束

**多账户合并**：同一股票多次出现时，数量相加，成本按加权平均计算

**OCR 流程**：图片上传 → Pillow 预处理 → Tesseract 识别 → 正则解析提取股票代码/名称/数量/价格

**服务层模式**：业务逻辑放在 `services/`，路由保持简洁

## 统一股票数据API

所有股票数据获取通过 `UnifiedStockDataService` 统一入口，根据股票代码自动识别市场类型并从对应数据源获取数据。

### 市场识别 (MarketIdentifier)

`app/utils/market_identifier.py` 提供统一的市场识别和代码转换：

```python
MarketIdentifier.identify(code)      # 返回 'A', 'US', 'HK' 或 None
MarketIdentifier.to_yfinance(code)   # 转换为 yfinance 格式
MarketIdentifier.is_a_share(code)    # 判断是否 A 股
MarketIdentifier.is_index(code)      # 判断是否指数
```

识别规则：
- A股：6位纯数字（6开头→.SS，0/3开头→.SZ）
- 美股：字母开头
- 港股：.HK 后缀

### 缓存架构

两层本地缓存，零外部依赖：

```
第1层：内存缓存 (MemoryCache) — 按股票分目录持久化
   ↓ miss
第2层：数据库缓存 (UnifiedStockCache) — SQLite 持久化
   ↓ miss/expired
第3层：API 获取 (akshare/yfinance)
```

- **内存缓存**：按股票分目录存储（`data/memory_cache/{stock_code}/{cache_type}.pkl`），延迟flush（变更后5秒批量持久化），启动时自动恢复
- **数据库缓存**：SQLite 存储，完整性标记，支持过期缓存降级

| 数据类型 | 缓存类型 | TTL |
|---------|---------|-----|
| 实时价格 | `price` | 交易时段30分钟 / 收盘后8小时 |
| OHLC走势 | `ohlc_{days}` | 交易时段30分钟 / 收盘后8小时 |
| 指数数据 | `index` | 交易时段30分钟 / 收盘后8小时 |

### 核心组件

- **UnifiedStockDataService** - 统一数据获取入口（单例模式）
  - `get_realtime_prices(stock_codes, force_refresh)` - A股用akshare，美股/港股用yfinance
  - `get_trend_data(stock_codes, days)` - OHLC走势数据
  - `get_indices_data(target_date)` - 指数数据
  - `get_cache_stats()` - 缓存命中率统计
  - `clear_cache()` - 清除缓存
  - `_retry_fetch()` - 带重试的数据获取（3次，间隔1秒）
  - `_get_expired_cache()` - 降级返回过期缓存

- **CacheValidator** - 缓存有效期验证
  - `is_cache_valid()` - 检查是否在8小时有效期内
  - `should_refresh()` - 返回需要刷新的股票列表

- **UnifiedStockCache** - 数据库缓存模型
  - 唯一约束：`(stock_code, cache_type, cache_date)`
  - JSON存储缓存数据

### 统一数据格式

**实时价格**：
```json
{
  "code": "600519",
  "name": "贵州茅台",
  "price": 1800.0,
  "change": 15.0,
  "change_pct": 0.84,
  "volume": 1234567,
  "market": "A"
}
```

**OHLC走势**：
```json
{
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "data": [
    {"date": "2024-01-01", "open": 1780, "high": 1810, "low": 1775, "close": 1800, "volume": 123456, "change_pct": 1.5}
  ]
}
```

### 调用链路

所有服务统一通过 UnifiedStockDataService 获取数据：

```
PositionService.get_stock_history()
    └── UnifiedStockDataService.get_trend_data()

PositionService.get_trend_data()
    └── UnifiedStockDataService.get_trend_data()

WyckoffAutoService._fetch_ohlcv()
    └── UnifiedStockDataService.get_trend_data()

FuturesService._fetch_from_api()
    └── UnifiedStockDataService.get_trend_data()

FuturesService.get_custom_trend_data()
    └── UnifiedStockDataService.get_trend_data()

PreloadService.preload_indices()
    └── UnifiedStockDataService.get_indices_data()

PreloadService.preload_metals()
    └── UnifiedStockDataService.get_trend_data()

PreloadService.get_indices_data()
    └── UnifiedStockDataService.get_indices_data()
```

## 盯盘助手配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |

## 新闻轮询配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NEWS_INTERVAL_MINUTES` | 新闻后台轮询间隔（分钟） | `3` |

## 公司新闻配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `COMPANY_NEWS_MAX_COMPANIES` | 每次轮询最多处理的公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每个公司最多爬取文章数 | `5` |
| `COMPANY_NEWS_INTERVAL_MINUTES` | 公司新闻获取间隔（分钟） | `30` |
| `NEWS_FETCH_TIMEOUT` | 新闻源获取超时（秒） | `15` |

## LLM 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ZHIPU_API_KEY` | 智谱 GLM API 密钥 | 空 |
| `LLM_DAILY_BUDGET` | 日预算上限（美元） | 无上限 |
| `LLM_REQUEST_TIMEOUT` | API 请求超时（秒） | `300` |
| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |

## 技术栈

- Flask + SQLAlchemy + SQLite
- RapidOCR (ONNX Runtime)
- Bootstrap 5 + 原生 JavaScript
- akshare（A股数据）+ yfinance（美股/港股/期货数据）+ Twelve Data + Polygon
- 智谱 GLM（AI 分析，Flash/Premium 分层路由）
- APScheduler（策略调度）

## 股票代码配置

期货、指数代码配置在 `app/config/stock_codes.py`，股票代码从数据库 `Stock` 和 `StockCategory` 表获取。

**配置项**：
- `FUTURES_CODES` - 期货代码映射（yfinance格式）
- `INDEX_CODES` - 指数代码映射
- `CATEGORY_CODES` - 分类代码列表
- `CATEGORY_NAMES` - 分类显示名称

**股票代码管理**：
- 股票代码存储在 `Stock` 表，可通过界面编辑
- 股票分类存储在 `StockCategory` 表，关联 `Category` 表

## 数据存储

- 数据库：`data/stock.db`
- 内存缓存持久化：`data/memory_cache/{stock_code}/{cache_type}.pkl`
- 上传图片：`uploads/`

## 开发规范

**配置变更同步**：新增/修改环境变量配置时，需同步更新 `CLAUDE.md`、`README.md`、`.env.sample` 三处
