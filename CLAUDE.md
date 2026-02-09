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
├── __init__.py      # Flask 工厂模式 create_app()
├── config/          # 配置模块
│   └── stock_codes.py  # 统一股票代码配置
├── models/          # SQLAlchemy 模型
│   ├── position.py  # 持仓模型 (date+stock_code 唯一)
│   ├── advice.py    # 操作建议模型
│   └── unified_cache.py  # 统一缓存模型
├── routes/          # Flask Blueprint
│   ├── main.py      # 首页 /
│   ├── position.py  # 持仓管理 /positions/*
│   ├── advice.py    # 操作建议 /advices/*
│   └── alert.py     # 预警 /alert/*
├── services/        # 业务逻辑层
│   ├── ocr.py       # Tesseract OCR 识别
│   ├── position.py  # 持仓数据处理、合并
│   ├── unified_stock_data.py  # 统一数据服务（唯一数据入口）
│   ├── cache_validator.py     # 缓存有效期验证
│   ├── wyckoff.py   # 威科夫分析服务
│   ├── futures.py   # 期货/指数/走势数据服务
│   └── preload.py   # 数据预加载服务
├── utils/           # 工具类
│   └── market_identifier.py  # 市场识别工具
├── templates/       # Jinja2 模板
└── static/          # CSS/JS 静态资源
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

## 技术栈

- Flask + SQLAlchemy + SQLite
- Tesseract OCR（可选，不安装则手动输入）
- Bootstrap 5 + 原生 JavaScript
- akshare（A股数据）+ yfinance（美股/港股/期货数据）

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
