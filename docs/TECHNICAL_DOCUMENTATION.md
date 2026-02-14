# GSStock 技术文档

> 版本: 1.0
> 最后更新: 2026-02-14

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [数据库模型](#4-数据库模型)
5. [服务层架构](#5-服务层架构)
6. [路由与API端点](#6-路由与api端点)
7. [前端架构](#7-前端架构)
8. [配置系统](#8-配置系统)
9. [缓存架构](#9-缓存架构)
10. [数据流程](#10-数据流程)
11. [设计模式](#11-设计模式)
12. [错误处理](#12-错误处理)
13. [性能优化](#13-性能优化)
14. [部署指南](#14-部署指南)

---

## 1. 项目概述

GSStock 是一个功能完善的个人股票投资组合管理系统，基于 Flask + SQLAlchemy + SQLite 构建。支持多市场（A股、美股、港股）、OCR 持仓识别、高级缓存策略和技术分析工具。

### 1.1 核心指标

| 指标 | 数值 |
|------|------|
| Python 代码行数 | ~20,500 行 |
| 数据库模型 | 21 个 |
| 路由蓝图 | 15 个 |
| 服务模块 | 40+ 个 |
| HTML 模板 | 19 个 |
| JavaScript 模块 | 14 个 |
| CSS 文件 | 5 个 |
| 总代码文件 | 126 个 |

### 1.2 核心功能

- **持仓管理**: 多账户持仓快照、OCR 自动识别、数量合并与成本均价计算
- **交易记录**: 买卖交易追踪、手续费计算、已结算持仓统计
- **盈亏分析**: 日盈亏、持仓盈亏、分类盈亏统计
- **技术分析**: 威科夫分析、支撑阻力位、买卖信号检测
- **市场简报**: 每日市场概览、重点股票追踪、板块评级
- **组合再平衡**: 目标权重设置、再平衡建议生成

---

## 2. 技术栈

### 2.1 后端技术

| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| **Web 框架** | Flask | 3.0+ |
| **ORM** | Flask-SQLAlchemy | 3.1+ |
| **数据库** | SQLite (本地) / CockroachDB (云端) | - |
| **OCR 引擎** | RapidOCR (ONNX Runtime) | 1.3-1.4.x |
| **A股数据** | akshare | 最新版 |
| **美股/港股数据** | yfinance | 最新版 |
| **交易日历** | exchange-calendars | 4.5+ |
| **并发处理** | ThreadPoolExecutor | 内置 |

### 2.2 前端技术

| 组件 | 技术选型 | 版本 |
|------|----------|------|
| **UI 框架** | Bootstrap | 5.3 |
| **图表库** | Chart.js | 4.4 |
| **JavaScript** | 原生 ES6+ | - |

### 2.3 GPU 支持

| 平台 | 运行时 |
|------|--------|
| NVIDIA | onnxruntime-gpu (CUDA) |
| Windows | onnxruntime-directml |
| CPU 回退 | onnxruntime |

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        前端 (Browser)                           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │ Bootstrap 5 │ │  Chart.js   │ │  主 JS 模块  │ │  CSS 样式  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Flask 应用层 (app/)                          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    路由层 (routes/)                        │  │
│  │  main │ position │ trade │ briefing │ alert │ ...        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   服务层 (services/)                       │  │
│  │  UnifiedStockDataService │ PositionService │ TradeService │  │
│  │  CacheValidator │ MemoryCache │ CircuitBreaker │ ...      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   模型层 (models/)                         │  │
│  │  Position │ Trade │ Stock │ UnifiedStockCache │ ...       │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        数据层                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  stock.db    │  │  private.db  │  │  memory_cache/     │   │
│  │  (共享数据)   │  │  (用户数据)   │  │  (内存缓存持久化)   │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      外部数据源                                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│  │ akshare │  │ yfinance│  │ Tencent │  │  Sina   │           │
│  │ (A股)   │  │(美/港股) │  │  API    │  │  API    │           │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构

```
/home/user/GSStock/
├── app/
│   ├── __init__.py                 # Flask 工厂函数、数据库迁移
│   ├── config/                     # 配置模块
│   │   ├── stock_codes.py         # 期货/指数/分类代码
│   │   ├── data_sources.py        # 数据源优先级配置
│   │   └── sector_ratings.py      # 板块评级配置
│   ├── models/                     # SQLAlchemy ORM 模型 (21个)
│   │   ├── position.py            # 持仓模型
│   │   ├── trade.py               # 交易模型
│   │   ├── unified_cache.py       # 核心缓存模型
│   │   ├── wyckoff.py             # 威科夫分析模型
│   │   ├── trading_strategy.py    # 交易策略模型
│   │   └── ...
│   ├── routes/                     # Flask 蓝图 (15个)
│   │   ├── main.py                # 首页路由
│   │   ├── position.py            # 持仓管理路由
│   │   ├── briefing.py            # 市场简报路由
│   │   └── ...
│   ├── services/                   # 业务逻辑层 (40+模块)
│   │   ├── unified_stock_data.py  # 统一数据服务
│   │   ├── position.py            # 持仓处理服务
│   │   ├── cache_validator.py     # 缓存验证服务
│   │   ├── memory_cache.py        # L1 内存缓存
│   │   ├── circuit_breaker.py     # 熔断器
│   │   ├── load_balancer.py       # 负载均衡
│   │   ├── market_session.py      # 智能 TTL
│   │   ├── trading_calendar.py    # 交易日历
│   │   └── ...
│   ├── utils/                      # 工具模块
│   │   ├── market_identifier.py   # 市场识别
│   │   ├── db_retry.py            # 数据库重试
│   │   └── readonly_mode.py       # 只读模式
│   ├── templates/                  # Jinja2 模板 (19个)
│   └── static/                     # 静态资源
│       ├── js/                     # JavaScript 模块 (14个)
│       └── css/                    # CSS 文件 (5个)
├── config.py                       # 应用配置
├── run.py                          # 入口文件
├── requirements.txt                # 依赖列表
├── CLAUDE.md                       # 开发指南
└── data/
    ├── stock.db                    # 共享数据库
    ├── private.db                  # 私有数据库
    ├── memory_cache/               # L1 缓存持久化
    │   └── {stock_code}/
    │       ├── price.pkl
    │       ├── ohlc_30.pkl
    │       └── ...
    └── logs/
        ├── app.log
        └── error.log
```

---

## 4. 数据库模型

### 4.1 双数据库架构

系统采用双数据库策略，分离共享数据和用户私有数据：

| 数据库 | 绑定键 | 用途 |
|--------|--------|------|
| **stock.db** | 默认 | 股票代码、分类、指数、参考数据 |
| **private.db** | `private` | 持仓、交易、设置、用户偏好 |

### 4.2 核心数据模型

#### Position (持仓模型)

```python
# __bind_key__ = 'private'
class Position(db.Model):
    id: int                 # 主键
    date: date              # 快照日期
    stock_code: str         # 股票代码
    stock_name: str         # 股票名称
    quantity: int           # 持仓数量
    total_amount: float     # 总金额
    current_price: float    # 当前价格

    # 计算属性
    @property
    def cost_price(self):
        return self.total_amount / self.quantity

    # 唯一约束: (date, stock_code)
```

#### Stock (股票模型)

```python
# 共享数据库
class Stock(db.Model):
    stock_code: str         # 主键
    stock_name: str         # 股票名称
    investment_advice: str  # 投资建议
```

#### Trade (交易模型)

```python
# __bind_key__ = 'private'
class Trade(db.Model):
    id: int
    trade_date: date        # 交易日期
    trade_time: time        # 交易时间
    stock_code: str         # 股票代码
    stock_name: str         # 股票名称
    trade_type: str         # 交易类型 (buy/sell)
    quantity: int           # 数量
    price: float            # 价格
    amount: float           # 金额
    fee: float              # 手续费

    # 索引: stock_code, trade_date
```

#### UnifiedStockCache (统一缓存模型)

```python
# 共享数据库
class UnifiedStockCache(db.Model):
    id: int
    stock_code: str         # 股票代码
    cache_type: str         # 缓存类型: 'price', 'ohlc_30', 'ohlc_60', 'index'
    cache_date: date        # 缓存日期
    data_json: text         # JSON 序列化数据
    is_complete: bool       # 收盘后完整数据标记
    data_end_date: date     # 数据截止日期
    last_fetch_time: datetime  # 最后获取时间（用于 TTL 验证）

    # 唯一约束: (stock_code, cache_type, cache_date)
```

### 4.3 完整模型列表

| 模型 | 数据库 | 用途 |
|------|--------|------|
| Position | private | 持仓快照 |
| Trade | private | 交易记录 |
| Stock | shared | 股票代码映射 |
| StockAlias | shared | 股票别名（多券商） |
| Category | shared | 股票分类 |
| StockCategory | shared | 股票-分类关联 |
| StockWeight | private | 目标权重 |
| Advice | private | 操作建议 |
| DailySnapshot | private | 每日快照 |
| UnifiedStockCache | shared | 统一缓存 |
| MetalTrendCache | shared | 贵金属缓存 |
| IndexTrendCache | shared | 指数缓存 |
| SignalCache | shared | 信号缓存 |
| WyckoffReference | shared | 威科夫参考图 |
| WyckoffAnalysis | private | 威科夫分析记录 |
| TradingStrategy | private | 交易策略 |
| StrategyExecution | private | 策略执行记录 |
| Settlement | private | 结算记录 |
| PositionPlan | private | 再平衡计划 |
| RebalanceConfig | private | 再平衡配置 |
| BankTransfer | private | 资金转入转出 |
| Config | private | 键值配置 |
| PreloadStatus | shared | 预加载状态 |

---

## 5. 服务层架构

### 5.1 数据获取服务

#### UnifiedStockDataService (统一数据服务)

**设计模式**: 单例模式

**职责**: 所有股票数据获取的统一入口，智能缓存，多源回退

```python
class UnifiedStockDataService:
    # 实时价格获取
    def get_realtime_prices(
        stock_codes: List[str],
        force_refresh: bool = False
    ) -> Dict[str, PriceData]:
        """
        A股: akshare | 美股/港股: yfinance
        返回: {code: PriceData}
        """

    # OHLC 走势数据
    def get_trend_data(
        stock_codes: List[str],
        days: int = 30
    ) -> Dict[str, List[OHLCData]]:
        """返回: {code: [OHLCData, ...]}"""

    # 指数数据
    def get_indices_data(
        target_date: date
    ) -> Dict[str, IndexData]:
        """返回: {index_code: IndexData}"""

    # 缓存管理
    def get_cache_stats() -> CacheStats
    def clear_cache(stock_codes, cache_type, cache_date)

    # 内部方法
    def _retry_fetch() -> Any  # 3次重试，间隔1秒
    def _get_expired_cache() -> Any  # 降级返回过期缓存
```

#### 数据类定义

```python
@dataclass
class PriceData:
    code: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: int
    high: float
    low: float
    open: float
    prev_close: float
    market: str  # 'A', 'US', 'HK'

@dataclass
class OHLCData:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    change_pct: float

@dataclass
class IndexData:
    index_code: str
    name: str
    current_price: float
    change_percent: float
    change: float
```

### 5.2 缓存服务

#### CacheValidator (缓存验证器)

**智能 TTL 逻辑**:
- 交易时段: 30 分钟 TTL
- 收盘后: 8 小时 TTL
- 非交易日: 下一交易日开盘

```python
class CacheValidator:
    CACHE_TTL_HOURS = 8

    def is_cache_valid(
        stock_code: str,
        cache_date: date,
        last_fetch_time: datetime
    ) -> bool:
        """检查缓存是否在 TTL 内"""

    def get_cache_age(
        last_fetch_time: datetime
    ) -> timedelta:
        """返回缓存年龄"""

    def should_refresh(
        stock_codes: List[str]
    ) -> List[str]:
        """返回需要刷新的股票代码列表"""

    def get_cache_status(
        stock_codes: List[str]
    ) -> Dict[str, str]:
        """返回每个代码的缓存状态 (valid/expired/missing)"""
```

#### MemoryCache (内存缓存)

**架构特点**:
- 内存 + 磁盘持久化
- 按股票分目录: `data/memory_cache/{stock_code}/{cache_type}.pkl`
- 延迟刷新: 变更后 5 秒批量持久化
- 启动时自动恢复

```python
class MemoryCache:
    def get(key: str) -> Any
    def set(key: str, value: Any, ttl: int = None)
    def clear(key: str = None)
    def get_stats() -> Dict[str, int]

    # 内部方法
    def _load_from_disk()
    def _flush_to_disk()
```

### 5.3 容错服务

#### CircuitBreaker (熔断器)

**状态机**:
```
CLOSED (正常) → OPEN (熔断) → HALF_OPEN (恢复中)
```

**配置**:
- 失败阈值: 3 次连续失败
- 冷却时间: 30 分钟
- HALF_OPEN 状态自动测试恢复

```python
class CircuitBreaker:
    def is_available(service: str) -> bool
    def record_success(service: str)
    def record_failure(service: str)
    def get_state(service: str) -> str
```

#### LoadBalancer (负载均衡器)

**市场路由配置**:
```python
MARKET_WEIGHTS = {
    'A': {'tencent': 50, 'sina': 50, 'eastmoney': 0},
    'US': {'yfinance': 70, 'twelvedata': 20, 'polygon': 10}
}
```

**特性**:
- 基于成功率的权重自适应调整
- 失败时自动回退到备用源
- 集成熔断器

### 5.4 业务逻辑服务

#### PositionService (持仓服务)

```python
class PositionService:
    def merge_positions(
        positions: List[Dict]
    ) -> List[Position]:
        """
        合并重复持仓
        - 数量相加
        - 成本加权平均
        - 支持 Stock 表查找
        - 回退到 StockAlias 别名查找
        """

    def save_snapshot(date: date, positions: List[Position])
    def get_snapshot(date: date) -> List[Position]
    def get_latest_date() -> date
    def get_all_dates() -> List[date]
    def get_stock_history(code: str) -> List[Dict]
    def calculate_position_stats() -> Dict
    def calculate_category_profit() -> Dict
```

#### TradeService (交易服务)

```python
class TradeService:
    def create_trade(trade_data: Dict) -> Trade
    def get_trades(
        date_from: date = None,
        date_to: date = None,
        stock_code: str = None,
        trade_type: str = None
    ) -> List[Trade]
    def calculate_fees(trades: List[Trade]) -> float
    def get_settled_stocks() -> List[Settlement]
```

#### DailyRecordService (日盈亏服务)

```python
class DailyRecordService:
    def get_daily_profit(date: date) -> Dict:
        """
        日盈亏 = 今日总资产 - 昨日总资产 - 净转账
        日手续费 = 理论盈亏 - 实际盈亏
        """

    def get_profit_breakdown(date: date) -> List[Dict]
    def get_daily_profit_history() -> List[Dict]
    def get_previous_trading_date(date: date) -> date
```

### 5.5 技术分析服务

#### TradingCalendarService (交易日历服务)

```python
MARKET_CALENDARS = {
    'A': 'XSHG',      # 上海
    'US': 'XNYS',     # 纽约
    'HK': 'XHKG',     # 香港
    'KR': 'XKRX',     # 韩国
    'TW': 'XTAI',     # 台湾
    'COMEX': 'XCME'   # 芝加哥
}

class TradingCalendarService:
    def is_trading_day(date: date, market: str) -> bool
    def is_market_open(market: str) -> bool
    def is_after_close(market: str) -> bool
    def get_market_hours(market: str) -> Tuple[time, time]
    def get_next_trading_day(date: date, market: str) -> date
    def get_market_now(market: str) -> datetime
```

#### SignalDetectorService (信号检测服务)

```python
class SignalDetectorService:
    def detect_signals(
        stock_codes: List[str]
    ) -> Dict[str, List[Signal]]:
        """
        检测买卖信号:
        - 动量指标
        - 支撑阻力位
        - 形态识别
        """

    def get_cached_signals(
        stock_code: str,
        signal_type: str = None
    ) -> List[SignalCache]
```

---

## 6. 路由与API端点

### 6.1 蓝图列表

| 蓝图 | 前缀 | 用途 |
|------|------|------|
| main | / | 首页、仪表盘 |
| position | /positions | 持仓上传、快照管理 |
| advice | /advices | 操作建议 |
| category | /categories | 分类管理 |
| trade | /trades | 交易记录 |
| wyckoff | /wyckoff | 威科夫分析 |
| stock | /stocks | 股票代码管理 |
| daily_record | /daily-record | 日盈亏录入 |
| profit | /profit | 盈亏分析 |
| rebalance | /rebalance | 组合再平衡 |
| heavy_metals | /heavy-metals | 贵金属仪表盘 |
| preload | / | 后台数据预加载 |
| alert | /alert | 价格/信号预警 |
| briefing | /briefing | 每日市场简报 |
| strategy | /strategies | 交易策略 |

### 6.2 主要API端点

#### 持仓管理

```
GET  /positions/<date>
     获取指定日期的持仓快照
     响应: {positions: [...], total_asset: float}

POST /positions/save
     保存持仓快照
     请求: {date: str, positions: [...]}
     响应: {success: bool, message: str}

GET  /positions/stock-history/<code>
     获取股票历史价格
     响应: {history: [...]}

POST /positions/upload
     上传持仓截图进行 OCR 识别
     请求: FormData (file)
     响应: {positions: [...]}
```

#### 交易记录

```
POST /trades
     创建交易记录
     请求: {trade_date, stock_code, trade_type, quantity, price, ...}
     响应: {success: bool, trade: {...}}

GET  /trades
     查询交易记录
     参数: date_from, date_to, stock_code, trade_type
     响应: {trades: [...]}
```

#### 市场简报

```
GET  /briefing/
     获取每日市场简报
     响应: HTML 页面

GET  /briefing/api/summary
     获取简报数据
     响应: {stocks: {...}, indices: {...}, sectors: {...}}

GET  /briefing/api/futures
     获取期货数据
     响应: {futures: {...}}
```

#### 预警系统

```
GET  /alert/signals
     获取活跃信号
     参数: signal_type, stock_code
     响应: {signals: [...]}

POST /alert/refresh
     刷新信号缓存
     响应: {success: bool, count: int}
```

#### 再平衡

```
GET  /rebalance/
     获取再平衡建议
     响应: HTML 页面

POST /rebalance/calculate
     计算再平衡操作
     请求: {target_weights: {...}}
     响应: {operations: [...]}
```

---

## 7. 前端架构

### 7.1 模板结构

| 模板 | 用途 |
|------|------|
| base.html | 主布局，导航栏 |
| index.html | 持仓上传 (OCR) |
| briefing.html | 每日市场简报 |
| alert.html | 价格与信号预警 |
| heavy_metals.html | 贵金属仪表盘 |
| daily_record.html | 日交易记录 |
| trade_list.html | 交易历史 |
| profit/*.html | 日盈亏/总盈亏图表 |
| rebalance.html | 组合再平衡 |
| stock_manage.html | 股票代码 CRUD |
| trading_strategy.html | 策略管理 |
| wyckoff_*.html | 威科夫分析 |
| category.html | 分类管理 |

### 7.2 JavaScript 模块

| 文件 | 功能 | 大小 |
|------|------|------|
| main.js | 核心工具、API 封装 | 22KB |
| charts.js | Chart.js 集成 | 105KB |
| briefing.js | 市场简报 UI | 33KB |
| alert-page.js | 预警系统 | 59KB |
| signal-detector.js | 信号检测 UI | 37KB |
| signal-alert.js | 信号通知 | 20KB |
| daily_record.js | 交易录入 | 33KB |
| trade_list.js | 交易表格 UI | 33KB |
| profit_charts.js | 盈亏可视化 | 12KB |
| rebalance.js | 再平衡计算器 | 9.5KB |
| wyckoff.js | 形态图表 UI | - |
| trading_strategy.js | 策略管理 | 13KB |
| relative.js | 比较分析 | 12KB |
| trade_stats.js | 交易统计 | 15KB |

### 7.3 CSS 模块

| 文件 | 用途 |
|------|------|
| style.css | 全局样式 |
| skeleton.css | 骨架屏加载 |
| alert.css | 预警样式 |
| index.css | 上传界面 |
| wyckoff.css | 形态分析样式 |

---

## 8. 配置系统

### 8.1 核心配置 (config.py)

```python
class Config:
    # 密钥
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

    # 数据库配置
    # 优先级: CockroachDB (COCKROACH_URL) → SQLite (本地)
    SQLALCHEMY_DATABASE_URI = get_database_uri()
    SQLALCHEMY_BINDS = {
        'private': 'sqlite:///data/private.db'
    }

    # 路径配置
    UPLOAD_FOLDER = 'uploads'
    LOG_DIR = 'data/logs'
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB

    # OCR 配置
    OCR_MAX_SIZE = 2048      # 最大像素
    OCR_TIMEOUT = 60         # 超时秒数
    OCR_USE_GPU = True

    # 只读模式
    READONLY_MODE = False
```

### 8.2 股票代码配置 (app/config/stock_codes.py)

```python
# 期货代码
FUTURES_CODES = {
    'GC=F': 'COMEX 黄金',
    'SI=F': 'COMEX 白银',
    'HG=F': 'COMEX 铜',
    # ... 20+ 期货代码
}

# 指数代码
INDEX_CODES = {
    '000001.SS': '上证指数',
    '^GSPC': '标普500',
    '^NDX': '纳斯达克100',
    # ... 更多指数
}

# 分类代码
CATEGORY_CODES = {
    'heavy_metals': ['GC=F', 'SI=F', ...],
    'cpu': ['AMD', 'INTC'],
}
```

### 8.3 数据源配置 (app/config/data_sources.py)

```python
MARKET_DATA_SOURCES = {
    'A': {  # A股
        'sources': ['sina', 'tencent', 'eastmoney'],
        'fallback': 'yfinance',
        'weights': {'sina': 35, 'tencent': 45, 'eastmoney': 20}
    },
    'US': {  # 美股
        'sources': ['yfinance', 'twelvedata', 'polygon'],
        'weights': {'yfinance': 70, 'twelvedata': 20, 'polygon': 10}
    },
    'HK': {  # 港股
        'sources': ['yfinance'],
        'weights': {'yfinance': 100}
    }
}
```

### 8.4 环境变量

```bash
# 数据库 (可选)
COCKROACH_URL=<云数据库URL>
PRIVATE_DATABASE_URL=<私有数据库URL>

# 应用配置
SECRET_KEY=<随机密钥>
READONLY_MODE=false

# 通知配置
SLACK_WEBHOOK_URL=<Slack Webhook>
SMTP_HOST=<SMTP服务器>
SMTP_PORT=587
SMTP_USER=<邮箱>
SMTP_PASSWORD=<密码>
NOTIFY_EMAIL_TO=<收件人>

# 数据源 API (可选)
TWELVE_DATA_API_KEY=<API密钥>
POLYGON_API_KEY=<API密钥>

# OCR 配置
OCR_USE_GPU=true
OCR_GPU_BACKEND=auto  # auto, cuda, directml, cpu
```

---

## 9. 缓存架构

### 9.1 三层缓存架构

```
┌─────────────────────────────────────────────────────────────┐
│ L1: MemoryCache (内存缓存)                                   │
│ • 按股票分目录存储                                            │
│ • 5秒延迟批量持久化                                           │
│ • 交易时段30分钟 / 收盘后8小时 TTL                            │
└────────────────────────┬────────────────────────────────────┘
                         │ (未命中或过期)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ L2: UnifiedStockCache (数据库缓存)                           │
│ • JSON 存储                                                  │
│ • 收盘后完整数据标记                                          │
│ • 支持过期缓存降级返回                                        │
└────────────────────────┬────────────────────────────────────┘
                         │ (未命中或强制刷新)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ L3: Live API Fetch (实时API获取)                             │
│ • 3次重试，指数退避                                          │
│ • 熔断器保护                                                 │
│ • 负载均衡路由                                               │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 缓存类型与 TTL

| 数据类型 | 缓存类型 | 交易时段 TTL | 收盘后 TTL |
|----------|----------|--------------|------------|
| 实时价格 | `price` | 30 分钟 | 8 小时 |
| 30日走势 | `ohlc_30` | 30 分钟 | 8 小时 |
| 60日走势 | `ohlc_60` | 30 分钟 | 8 小时 |
| 120日走势 | `ohlc_120` | 30 分钟 | 8 小时 |
| 指数数据 | `index` | 30 分钟 | 8 小时 |

### 9.3 缓存持久化结构

```
data/memory_cache/
├── 600519/              # 贵州茅台
│   ├── price.pkl        # 实时价格缓存
│   ├── ohlc_30.pkl      # 30日走势缓存
│   └── ohlc_60.pkl      # 60日走势缓存
├── AAPL/                # 苹果
│   ├── price.pkl
│   └── ohlc_30.pkl
└── ...
```

---

## 10. 数据流程

### 10.1 持仓上传流程

```
┌───────────────┐
│  截图上传      │
└───────┬───────┘
        ▼
┌───────────────┐
│  OCR 服务     │ ← RapidOCR
│  图像预处理   │ ← Pillow
└───────┬───────┘
        ▼
┌───────────────┐
│  文本提取     │ ← 正则表达式
│  代码/名称/   │
│  数量/价格    │
└───────┬───────┘
        ▼
┌───────────────┐
│  股票服务     │ ← 自动创建股票记录
│  别名查找     │ ← StockAlias 回退
└───────┬───────┘
        ▼
┌───────────────┐
│  持仓服务     │ ← 合并重复持仓
│  加权成本计算 │ ← total_amount / quantity
└───────┬───────┘
        ▼
┌───────────────┐
│  数据库存储   │ ← date+stock_code 唯一约束
└───────────────┘
```

### 10.2 实时价格获取流程

```
请求: get_realtime_prices(['600519', 'AAPL'])
        │
        ▼
┌───────────────────┐
│ UnifiedStockData  │
│ Service           │
│ • 按市场分组      │ ← 600519→A, AAPL→US
│ • 检查 L1 缓存    │
│ • 检查 L2 缓存    │
│ • 验证 TTL        │
└─────────┬─────────┘
          │ (过期/未命中)
          ▼
┌───────────────────┐
│ LoadBalancer      │
│ • A股→腾讯/新浪   │
│ • 美股→yfinance   │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ CircuitBreaker    │
│ • 检查可用性      │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ API 获取          │
│ • 3次重试         │
│ • 1秒间隔         │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 缓存更新          │
│ • L1 + L2 写入    │
│ • 时间戳记录      │
└─────────┬─────────┘
          │
          ▼
返回: {code: PriceData}
```

### 10.3 每日简报生成流程

```
定时触发: 每日 9:30
        │
        ▼
┌───────────────────┐
│ BriefingService   │
│ .generate()       │
│ • 获取重点股票    │ ← TSLA, GOOG, NVDA, ...
│ • 获取主要指数    │ ← ^GSPC, ^NDX, 000001.SS
│ • 获取ETF溢价     │
│ • 获取板块评级    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ UnifiedStockData  │
│ Service           │
│ • 批量获取价格    │
│ • 计算涨跌幅      │
│ • 存入缓存        │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ 后台预加载        │
│ • 优先简报股票    │
│ • 批量请求        │
│ • 更新进度状态    │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ HTML 模板渲染     │
│ • 价格颜色编码    │
│ • 24小时变化      │
│ • 预警显示        │
└───────────────────┘
```

---

## 11. 设计模式

### 11.1 单例模式

**使用场景**:
- `UnifiedStockDataService` - 集中数据获取
- `MemoryCache` - 共享内存存储
- `CircuitBreaker` - 熔断状态管理
- `LoadBalancer` - 请求路由
- `TradingCalendarService` - 交易日历缓存

```python
class UnifiedStockDataService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

### 11.2 策略模式

**使用场景**:
- `CacheValidator` - 多种 TTL 策略
- `MarketSession.SmartCacheStrategy` - 自适应 TTL
- `DataSourceProviders` - 多数据源
- `TechnicalIndicatorsService` - 多指标计算

### 11.3 工厂模式

**使用场景**:
- `create_app()` - Flask 应用创建
- 模型序列化: `.to_dict()` 方法

```python
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # 注册蓝图
    app.register_blueprint(main_bp)
    app.register_blueprint(position_bp)
    # ...

    return app
```

### 11.4 仓库模式

**使用场景**:
- `Position`, `Trade`, `Advice` - 数据访问层
- 服务层查询构建器
- SQLAlchemy 关系管理

### 11.5 装饰器模式

**使用场景**:
- `@with_db_retry` - CockroachDB 重试逻辑
- `@circuit_breaker` - 熔断保护
- `@lru_cache` - 查询结果缓存

```python
@with_db_retry(max_retries=3)
def save_position(position):
    db.session.add(position)
    db.session.commit()
```

---

## 12. 错误处理

### 12.1 数据库错误 (CockroachDB)

```python
@with_db_retry(max_retries=3)
def database_operation():
    """
    自动检测序列化失败
    指数退避重试
    最多3次尝试
    """
    try:
        # 数据库操作
        db.session.commit()
    except SerializationError:
        db.session.rollback()
        raise  # 触发重试
```

### 12.2 API 错误

```python
def fetch_with_fallback(stock_code):
    # 熔断器检查
    if not circuit_breaker.is_available('akshare'):
        return get_expired_cache(stock_code)

    try:
        # 3次重试
        for attempt in range(3):
            try:
                return fetch_from_api(stock_code)
            except APIError:
                if attempt < 2:
                    time.sleep(1)
                    continue
                raise
    except Exception:
        # 回退到过期缓存
        circuit_breaker.record_failure('akshare')
        return get_expired_cache(stock_code)
```

### 12.3 OCR 错误

```python
def process_image(file):
    # 文件大小验证
    if file.size > 10 * 1024 * 1024:
        raise FileTooLargeError()

    # 格式验证
    if not allowed_extension(file.filename):
        raise InvalidFormatError()

    # 超时处理
    try:
        with timeout(60):
            result = ocr_engine.recognize(file)
    except TimeoutError:
        raise OCRTimeoutError()

    # 结果格式兼容 (1.3.x vs 1.4.x)
    return parse_ocr_result(result)
```

---

## 13. 性能优化

### 13.1 批量操作

```python
# 批量缓存获取
def get_batch_cached_data(stock_codes, cache_type):
    """单次查询获取多个代码的缓存"""
    return UnifiedStockCache.query.filter(
        UnifiedStockCache.stock_code.in_(stock_codes),
        UnifiedStockCache.cache_type == cache_type
    ).all()

# 批量缓存写入
def set_batch_cached_data(data_list):
    """批量插入优化"""
    db.session.bulk_insert_mappings(UnifiedStockCache, data_list)
    db.session.commit()
```

### 13.2 缓存策略

- **三层缓存**: 内存 → 数据库 → API
- **延迟刷新**: 5秒批量持久化
- **自适应 TTL**: 基于市场状态

### 13.3 并发获取

```python
def fetch_multiple_stocks(stock_codes):
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_single, code): code
            for code in stock_codes
        }
        results = {}
        for future in as_completed(futures):
            code = futures[future]
            results[code] = future.result()
    return results
```

### 13.4 索引优化

```python
class Position(db.Model):
    __table_args__ = (
        Index('idx_position_date', 'date'),
        Index('idx_position_stock', 'stock_code'),
        UniqueConstraint('date', 'stock_code', name='uq_position_date_stock'),
    )
```

### 13.5 查询优化

```python
# 延迟加载关系
class Stock(db.Model):
    categories = db.relationship('Category', lazy='dynamic')

# 批量预加载
def get_positions_with_stocks(date):
    return Position.query.options(
        joinedload(Position.stock)
    ).filter_by(date=date).all()
```

---

## 14. 部署指南

### 14.1 系统要求

| 组件 | 要求 |
|------|------|
| Python | 3.8+ |
| 内存 | 2GB (内存缓存) |
| 磁盘 | 500MB (数据库+缓存) |
| OCR 模型 | 1GB (RapidOCR) |
| GPU | 可选 (加速 OCR) |

### 14.2 安装步骤

```bash
# 克隆项目
git clone <repository_url>
cd GSStock

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# 启动应用
python run.py
```

### 14.3 生产部署

#### 使用 Gunicorn (Linux)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

#### 使用 Waitress (Windows)

```bash
pip install waitress
waitress-serve --host=0.0.0.0 --port=5000 app:create_app
```

### 14.4 Docker 部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:create_app()"]
```

### 14.5 日志配置

```
data/logs/
├── app.log      # 所有日志 (DEBUG级别)
└── error.log    # 错误日志 (ERROR级别)
```

日志格式:
```
[2026-02-14 10:30:00] [INFO] [app.services.position] 保存持仓快照: 2026-02-14, 10只股票
```

---

## 附录

### A. 外部数据源

| 数据源 | 市场 | 数据类型 | 频率限制 |
|--------|------|----------|----------|
| akshare | A股 | 实时、OHLC | 无 |
| yfinance | 美股/港股/期货 | 实时、OHLC | 无 |
| Tencent API | A股 | 实时 | 无 |
| Sina API | A股 | 实时 | 无 |
| Eastmoney | A股 | 实时、OHLC | 无 |
| Twelve Data | 美股/港股 | 实时、OHLC | 8次/分钟, 800次/天 |
| Polygon.io | 美股 | 实时、OHLC | 5次/分钟 |

### B. 市场代码格式

| 市场 | 格式 | 示例 |
|------|------|------|
| A股 (上海) | 6位数字 + .SS | 600519.SS |
| A股 (深圳) | 6位数字 + .SZ | 000001.SZ |
| 美股 | 字母代码 | AAPL, TSLA |
| 港股 | 数字 + .HK | 0700.HK |
| 期货 | 代码 + =F | GC=F, SI=F |

### C. 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| OCR 识别失败 | 图片过大/格式不支持 | 压缩图片/转换格式 |
| 数据获取超时 | API 服务不可用 | 检查网络/等待熔断恢复 |
| 缓存未命中 | 首次访问/缓存过期 | 等待数据加载/强制刷新 |
| 数据库锁定 | 并发写入冲突 | 重试/使用 CockroachDB |

---

*文档生成时间: 2026-02-14*
