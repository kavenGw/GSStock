# 数据架构与缓存

> **何时读**：改 app/services/ 下任何 fetcher、写涉及 Stock/UnifiedStockCache 的 SQL、调试缓存命中率、新增市场支持、修改 Volume / OCR / 多账户合并 / 产业链图谱
> **不必读**：纯前端改动 / 纯通知格式 / 文档撰写 / LLM 路由

## 核心设计

**JSON 安全序列化**：`_SafeJsonProvider`（`app/__init__.py`）全局将 `NaN`/`Infinity` 转 `null`，避免前端 `JSON.parse` 失败

**数据模型**：按日期保存持仓快照，`(date, stock_code)` 为唯一约束

**Stock 表约定**：PK 是 `stock_code` 字符串（非自增 id），列 `(stock_code, stock_name, investment_advice, created_at, updated_at, tags)`；库只存用户关注池（远小于全 A 股），不是全市场快照。新标的通过 `app/seeds/` 幂等注入。

**多账户合并**：同一股票多次出现时，数量相加，成本按加权平均计算

**OCR 流程**：图片上传 → Pillow 预处理 → Tesseract 识别 → 正则解析提取股票代码/名称/数量/价格

**模块级单例的 Flask context 陷阱**：`app/services/__init__.py` 的 `unified_stock_data_service = UnifiedStockDataService()` 在 import 期就会触发 `__init__`，此时无 Flask app context；任何访问 `db.session` 或 `<Model>.query` 的 init 期代码必须用 `has_app_context()` 守卫

**数据获取服务失败语义二分**：`_fetch_*` 类方法返回 `None` 表示异常/获取失败（已重试耗尽），返回空数据字典如 `{'today': [], 'yesterday': []}` 表示 API 成功但当下无数据。推送/聚合层据此区分"数据获取失败" vs "今日无赛事"。涉及该约定的服务异常分支必须 `logger.warning(... exc_info=True)` + 含 `type(e).__name__` + 关键上下文（如 league_id / HTTP status / 响应体片段），否则吞异常会让两种场景在日志中无法区分。参考 `app/services/esports_service.py:_fetch_lol_esports_schedule`。

**新闻推送多分支去重**：`InterestPipeline.process_new_items` 有 `_identify_and_notify_companies`（🔍 AI 公司识别）和 `_notify_interest_slack`（📰 兴趣关键词）两条独立 Slack 分支，同一条 NewsItem 可同时命中。前者推送时已包含原文全文，须按 `NewsItem.id` 集合去重避免重复推送；新增第三条推送路径时也要并入该去重链。

**启动数据种子**：`app/seeds/` 放幂等数据 seed（区别于 `migrate_*` 改 schema），在 `create_app()` 里紧跟迁移调用。铁律：已存在的 `Stock.stock_name` / `investment_advice` / `StockCategory` 归属**一律不覆盖**，失败只记 warning 不抛出。`StockCategory.stock_code` 唯一约束 → 一只股票只能归属一个分类；跨板块引用（如 002916 深南电路在 PCB 同时被 CPU 产业链引用）只能保留现状并在 advice 文案里描述关联。

**产业链图谱约定**：配置在 `app/config/supply_chain.py` 的 `SUPPLY_CHAIN_GRAPHS` 字典，渲染路由 `/supply-chain/api/<name>`。`upstream/midstream/downstream` 三层均支持 `companies` 字段；公司条目可带 `tag` 承载非产业链语义，约定取值 `frontEC` / `don_buy` / `keep_watching` / `not_analyzed`，前端 `supply_chain.html` 的 `TAG_LABELS` 映射显示文案。主题型图谱（如赛事）的 `competitors` 可留 `{}`，`core.code` 用虚拟 slug（如 `WC2026`）。新增图谱只需在 `SUPPLY_CHAIN_GRAPHS` 加 dict key 即自动注册（路由按 dict 遍历），零路由/模板/seed 改动；跨链复用标的在 `role` 末尾标注「（同属 X 产业链）」与既有图谱保持一致。

**tag 与分析档同步**：标的在 supply_chain 标 `not_analyzed` 且已建 buffett/分析档时，回写 `tag` 反映结论（至少从 `not_analyzed` 改为已分析态），避免图谱与 docs/stock-analytics 评级长期脱节。stock-deep-redo / analyze-category 收尾时一并检查该股是否在 `SUPPLY_CHAIN_GRAPHS` 里、tag 是否需更新。

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

**缓存刷新策略区分**：
- 实时价格：非交易时间跳过API（市场关闭无新数据）
- OHLC走势：非交易时间仍可获取（历史数据始终可用），缓存需检查 `data_end_date` 是否含最近交易日

| 数据类型 | 缓存类型 | TTL |
|---------|---------|-----|
| 实时价格 | `price` | 交易时段30分钟 / 收盘后8小时 |
| OHLC走势 | `ohlc_{days}` | 交易时段30分钟 / 收盘后8小时 |
| 指数数据 | `index` | 交易时段30分钟 / 收盘后8小时 |
| 季度财报 | `quarterly_earnings` | 7天 |

**缓存日期统一走 SmartCacheStrategy**：所有缓存 lookup/save 用 `SmartCacheStrategy.get_effective_cache_date(code)` 替代 `date.today()`；批量场景用 `_get_effective_cache_dates(codes)` 按市场分组。理由：处理跨市场时区错位（A 股 vs 美股），让缓存"今日"语义跟随该股票所属市场的有效交易日。API 查询日期范围（start_date/end_date）仍用 `date.today()`，API 自动截断。

### Volume 单位契约

所有 A 股 OHLC/realtime 的 `volume` 字段统一为**"手"** 单位（1手=100股）。

- 腾讯 `qt.gtimg.cn` / `fqkline` 日K原生返回"股"，解析时 `/100` 归一
- 新浪 `stock_zh_a_spot` / `stock_zh_a_daily` 原生返回"股"，解析时 `//100` 归一
- 东财 akshare `stock_zh_a_hist` / `stock_zh_a_spot_em` 原生是"手"，保持不变
- 东财直连 push2his、ETF `fund_etf_hist_em` 原生是"手"，保持不变

**VOLUME_UNIT_SCHEMA_VERSION 机制**：`app/services/unified_stock_data.py` 顶部定义版本常量，启动时校验 `data/memory_cache/.schema_version`。版本不匹配则自动清理内存缓存（`ohlc_*/price/index` pkl）和数据库缓存（`UnifiedStockCache` 对应 `cache_type` 行）。单位契约变更时 bump 该常量触发全量清理。

### A 股行情数据特征

- **A 股节假日**：五一（5-1~5-5）/ 国庆（10-1~10-7）/ 春节多日连休，OHLC 序列会缺日期。跨市场事件分析（如 AMD 财报 → 002156 联动）必须识别假期错位 —— 美股仍在交易的窗口 A 股可能空白多日，节后第一日是情绪集中释放点
- **一字涨停判定**：单日 OHLC 四值合一（O=H=L=C）+ 量比 < 1（典型 0.5-0.7x），表示开盘即封板无成交，常见于节后情绪集中释放或事件驱动；分析时不可当成正常 K 线计算技术指标

### 腾讯HTTP数据源

实时价格和分时K线优先使用腾讯HTTP接口（并发安全、无需限速）：
- 实时价格批量：`http://qt.gtimg.cn/q=sh600519,sz000001`（GBK编码，`~`分隔）
  - `q=` 字段索引：`[1]=name [3]=price [4]=prev_close [5]=open [6]=volume(手) [32]=change_pct [38]=换手率 [39]=PE_TTM [41]=年高 [42]=年低 [45]=市值(亿) [46]=PB`（亏损股 PE 为负值，与 baidu 估值分位接口结合用来判当前 PB/PE 在历史分位）
- 分钟K线：`http://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600519,m1,,240`
- 日K线：`http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,...`
- **字段顺序**：`[datetime, open, close, high, low, volume]`（close在第2位，非标准OHLC）
- **XD（除息日）字段失真**：分红除息当日 `q=` 接口 name 带 `XD` 前缀，且 52 周高/低字段 `[41]/[42]` 返回失真值（如现价 51.7 却报 52.92/50.78），**不可信**；price/PE_TTM/市值/PB 仍可靠。需 52 周区间改用 baidu 估值接口。
- **只取实时价的一次性脚本直连 HTTP 优先**：`urllib.request` 拉 `qt.gtimg.cn/q=sh600519,sz000001,...` 比走 `create_app() + UnifiedStockDataService` 快 5x+ 且无副作用（即便 `SCHEDULER_ENABLED=0`，create_app 仍会启 crawl4ai 抓 google 新闻产生数十行噪音日志）；服务化路径仅在需要缓存 / 指数 / OHLC 时才走

### 策略数据协作

`watch_preload`（每分钟）负责 `force_refresh` 写缓存，`watch_alert` 和其他策略读缓存即可，避免重复API调用

### 核心组件

- **UnifiedStockDataService** - 统一数据获取入口（单例模式）
  - `get_realtime_prices(stock_codes, force_refresh)` - A股用腾讯HTTP批量+akshare负载均衡，美股/港股用yfinance
  - `get_trend_data(stock_codes, days)` - OHLC走势数据
  - `get_indices_data(target_date)` - 指数数据
  - `get_cache_stats()` - 缓存命中率统计
  - `clear_cache()` - 清除缓存
  - `_retry_fetch()` - 带重试的数据获取（3次，间隔1秒）
  - `_get_expired_cache()` - 降级返回过期缓存

**API 返回结构契约**：`get_trend_data()` / `get_indices_data()` 返回 `{'stocks': [{stock_code, stock_name, data: [...]}, ...], 'date_range': {start, end}}` —— 是 list of dict，**不是按 code 索引的 dict**。批量调用后取 `{s['stock_code']: s for s in result['stocks']}` 转 dict 再访问。

- **CacheValidator** - 缓存有效期验证
  - `is_cache_valid()` - 检查是否在8小时有效期内
  - `should_refresh()` - 返回需要刷新的股票列表

- **UnifiedStockCache** - 数据库缓存模型
  - 唯一约束：`(stock_code, cache_type, cache_date)`
  - JSON 存储缓存数据；列名 **`data_json`**（不是 `cache_data` / `cache_value`），直连 sqlite3 查缓存写 `SELECT data_json FROM unified_stock_cache WHERE stock_code=? AND cache_type='price' ORDER BY cache_date DESC LIMIT 1`

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

**实时价格返回字段实际命名**（与上方示例不一致，调用时按实际取）：`current_price`（不是 price）/ `change_percent`（不是 change_pct）/ `name`。Memory cache 可能缓存 `current_price=None` 的失败条目，"全部内存缓存命中" 不代表数据可用，新数据校验场景务必传 `force_refresh=True`。yfinance A 股兜底返回 `name=stock_code`（如 '601138' 而非 '工业富联'），需 fallback 到调用方提供的 stock_name。

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

所有持仓 / 期货 / 盯盘 / 预加载 / 季报 / TD九转服务统一走 `UnifiedStockDataService` 的 `get_trend_data` / `get_realtime_prices` / `get_indices_data` / `get_intraday_data` 入口，缓存命中率与 force_refresh 语义由该服务统一裁决。`WatchAnalysisService` 是聚合层（不直连数据源），其余服务均直接消费 unified 入口。
