# 数据流与缓存架构

## 三层缓存流程

```mermaid
flowchart TD
    Request[数据请求] --> MC{内存缓存<br/>MemoryCache}
    MC -->|命中| Return[返回数据]
    MC -->|miss| DBC{DB缓存<br/>UnifiedStockCache}
    DBC -->|命中且未过期| WriteM1[回写内存缓存] --> Return
    DBC -->|过期| API1[调用API获取]
    DBC -->|miss| API2[调用API获取]

    API1 -->|成功| WriteAll[回写DB + 内存缓存] --> Return
    API1 -->|失败| Degrade[降级：返回过期缓存<br/>标记 _is_degraded=True] --> Return
    API2 -->|成功| WriteAll
    API2 -->|失败| Empty[返回空数据]

    style MC fill:#4CAF50,color:#fff
    style DBC fill:#2196F3,color:#fff
    style API1 fill:#FF9800,color:#fff
    style API2 fill:#FF9800,color:#fff
    style Degrade fill:#f44336,color:#fff
```

### TTL 策略

| 场景 | TTL | 说明 |
|------|-----|------|
| 交易时段内 | 30分钟 | 盘中数据持续变化 |
| 收盘后 | 次日开盘前 | 数据标记 `is_complete`，不再刷新 |
| 非交易日 | 下个交易日开盘前 | 周末/节假日复用收盘数据 |

### 内存缓存持久化

```
data/memory_cache/
├── 600519/          # 按股票代码分目录
│   ├── price.pkl
│   └── ohlc_30.pkl
├── AAPL/
│   ├── price.pkl
│   └── ohlc_60.pkl
└── ...
```

延迟 flush：变更后 5 秒批量写盘，启动时自动恢复。

## A股数据源负载均衡

```mermaid
flowchart TD
    Req[A股数据请求] --> LB[LoadBalancer<br/>优先级模式]

    LB --> Primary[主数据源 · 并行]
    Primary --> Tencent[腾讯财经]
    Primary --> Sina[新浪财经]

    Tencent -->|成功| Merge[合并结果]
    Sina -->|成功| Merge
    Tencent -->|失败| CB1{熔断器检查}
    Sina -->|失败| CB2{熔断器检查}

    CB1 -->|未熔断| Retry1[重试]
    CB1 -->|已熔断| Fallback
    CB2 -->|未熔断| Retry2[重试]
    CB2 -->|已熔断| Fallback

    Primary -->|全部失败| Fallback[备用：东方财富]
    Fallback -->|成功| Merge
    Fallback -->|失败| Last[兜底：yfinance]
    Last -->|成功| Merge
    Last -->|失败| CacheDegrade[降级到过期缓存]

    Merge --> Return[返回数据]

    style Primary fill:#4CAF50,color:#fff
    style Fallback fill:#FF9800,color:#fff
    style Last fill:#f44336,color:#fff
```

### 熔断器参数

| 参数 | 值 |
|------|-----|
| 失败阈值 | 5次/分钟 |
| 熔断时长 | 5分钟 |
| 恢复 | 自动半开探测 |

### 数据源快照缓存

避免重复拉取全量行情，东方财富/新浪在实例级缓存全量快照：

| 快照Key | 内容 | TTL |
|---------|------|-----|
| `eastmoney_stock` | A股全量行情 | 2分钟 |
| `eastmoney_etf` | ETF全量行情 | 2分钟 |
| `sina_stock` | A股全量行情 | 2分钟 |

## 核心请求链路（实时价格获取）

```mermaid
sequenceDiagram
    participant Route as 路由层
    participant Svc as PositionService
    participant USD as UnifiedStockDataService
    participant MC as MemoryCache
    participant DB as UnifiedStockCache
    participant LB as LoadBalancer
    participant DS as 数据源

    Route->>Svc: get_snapshot(date)
    Svc->>USD: get_realtime_prices(codes)

    USD->>MC: get_batch(codes, 'price')
    alt 全部命中
        MC-->>USD: 缓存数据
        USD-->>Svc: 返回价格
    else 部分miss
        MC-->>USD: 命中部分 + miss列表
        USD->>DB: 查询miss的codes
        alt DB命中且未过期
            DB-->>USD: 缓存数据
            USD->>MC: 回写内存
            USD-->>Svc: 返回价格
        else DB miss或过期
            DB-->>USD: miss列表
            USD->>LB: fetch_with_priority_balancing(codes)
            LB->>DS: 腾讯+新浪并行获取
            DS-->>LB: 行情数据
            LB-->>USD: 合并结果
            USD->>DB: 写入DB缓存
            USD->>MC: 写入内存缓存
            USD-->>Svc: 返回价格
        end
    end

    Svc-->>Route: 持仓快照 + 实时价格
```
