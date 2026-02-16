# 系统架构

## 分层架构

```mermaid
graph TB
    subgraph 前端层
        Templates[Jinja2 模板]
        JS[JS 模块<br/>briefing.js / stock-detail.js / charts.js]
        Skeleton[骨架屏系统<br/>skeleton.css + Skeleton工具]
    end

    subgraph 路由层
        Blueprints[14个 Blueprint<br/>briefing / heavy_metals / position<br/>advice / alert / stock_detail / ...]
    end

    subgraph 服务层
        BizServices[业务服务<br/>BriefingService / PositionService<br/>WyckoffAutoService / FuturesService<br/>TechnicalIndicatorService / ...]
        USD[UnifiedStockDataService<br/>统一数据入口 · 单例]
    end

    subgraph 缓存层
        MC[MemoryCache<br/>内存缓存 · pkl持久化]
        DB[UnifiedStockCache<br/>SQLite缓存]
        CV[CacheValidator<br/>TTL验证]
    end

    subgraph 数据源层
        LB[LoadBalancer<br/>负载均衡器]
        CB[CircuitBreaker<br/>熔断器]
        subgraph 数据源
            Tencent[腾讯财经]
            Sina[新浪财经]
            East[东方财富]
            YF[yfinance]
        end
    end

    subgraph 存储层
        StockDB[(stock.db<br/>公共数据)]
        PrivateDB[(private.db<br/>私有数据)]
        PKL[memory_cache/<br/>pkl文件]
    end

    Templates --> Blueprints
    JS --> Blueprints
    Blueprints --> BizServices
    BizServices --> USD
    USD --> MC
    MC --> DB
    DB --> LB
    USD --> CV
    LB --> CB
    CB --> Tencent & Sina & East & YF
    MC -.-> PKL
    DB -.-> StockDB
    BizServices -.-> PrivateDB
```

## 核心服务依赖

```mermaid
graph LR
    subgraph 业务服务
        Briefing[BriefingService]
        Position[PositionService]
        Wyckoff[WyckoffAutoService]
        Futures[FuturesService]
        Preload[PreloadService]
        Signal[SignalDetectorService]
    end

    subgraph 数据核心
        USD[UnifiedStockDataService<br/>单例入口]
    end

    subgraph 缓存组件
        MC[MemoryCache]
        CV[CacheValidator]
        SCS[SmartCacheStrategy]
    end

    subgraph 数据获取
        LB[LoadBalancer]
        CB[CircuitBreaker]
        DSP[DataSourceProviders<br/>腾讯/新浪/东方财富/yfinance]
    end

    subgraph 工具
        MI[MarketIdentifier]
        TC[TradingCalendarService]
        MS[MarketSessionService]
    end

    Briefing --> USD
    Position --> USD
    Wyckoff --> USD
    Futures --> USD
    Preload --> USD
    Signal --> USD

    USD --> MC
    USD --> CV
    USD --> LB
    CV --> SCS
    SCS --> TC
    SCS --> MS
    LB --> CB
    LB --> DSP
    USD --> MI
```

## 双库设计

| 数据库 | 用途 | 核心表 |
|--------|------|--------|
| `stock.db` | 公共数据，可共享 | Stock, Category, StockCategory, UnifiedStockCache, SignalCache, WyckoffAnalysis |
| `private.db` | 私有数据，不入Git | Position, Trade, Settlement, DailySnapshot, Advice, Config |

## 设计模式

| 模式 | 应用 |
|------|------|
| 单例 | UnifiedStockDataService, LoadBalancer, MemoryCache |
| 工厂 | Flask `create_app()` |
| 策略 | SmartCacheStrategy, BatchCacheStrategy |
| 熔断 | CircuitBreaker 监控数据源健康 |
