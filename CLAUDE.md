# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人股票管理工具，用于管理多个证券账户的持仓情况。支持上传持仓截图自动识别、多账户合并、操作建议记录。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 脚本中查询数据库（禁用调度器，避免后台任务阻塞）
SCHEDULER_ENABLED=0 python -c "from app import create_app; app = create_app(); ..."

# 启动应用
python run.py

# 一键启动（启动并打开浏览器）
start.bat

# Linux 部署（拉取代码 + 更新依赖 + 重启）
./update_and_run.sh
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
├── strategies/        # 策略插件系统（自动发现注册）
├── scheduler/         # APScheduler 后台调度 + 事件总线
├── middleware/        # Flask 中间件
├── utils/             # 工具函数
├── templates/         # Jinja2 模板
└── static/            # CSS/JS 静态资源
```

## 核心设计

**JSON 安全序列化**：`_SafeJsonProvider`（`app/__init__.py`）全局将 `NaN`/`Infinity` 转 `null`，避免前端 `JSON.parse` 失败

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

**缓存刷新策略区分**：
- 实时价格：非交易时间跳过API（市场关闭无新数据）
- OHLC走势：非交易时间仍可获取（历史数据始终可用），缓存需检查 `data_end_date` 是否含最近交易日

| 数据类型 | 缓存类型 | TTL |
|---------|---------|-----|
| 实时价格 | `price` | 交易时段30分钟 / 收盘后8小时 |
| OHLC走势 | `ohlc_{days}` | 交易时段30分钟 / 收盘后8小时 |
| 指数数据 | `index` | 交易时段30分钟 / 收盘后8小时 |
| 季度财报 | `quarterly_earnings` | 7天 |

### 腾讯HTTP数据源

实时价格和分时K线优先使用腾讯HTTP接口（并发安全、无需限速）：
- 实时价格批量：`http://qt.gtimg.cn/q=sh600519,sz000001`（GBK编码，`~`分隔）
- 分钟K线：`http://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param=sh600519,m1,,240`
- 日K线：`http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600519,day,...`
- **字段顺序**：`[datetime, open, close, high, low, volume]`（close在第2位，非标准OHLC）

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

WatchAnalysisService.analyze_stocks()
    └── UnifiedStockDataService.get_trend_data() / get_intraday_data() / get_realtime_prices()

DailyBriefingStrategy.scan()
    └── NotificationService.push_daily_report()
        └── WatchAnalysisService.analyze_stocks('7d' / '30d')

WatchRealtimeStrategy.scan()
    └── WatchAnalysisService.analyze_stocks('realtime')

QuarterlyEarningsService.get_earnings()
    └── UnifiedStockDataService.get_trend_data() (季末股价)

TDSequentialService.calculate()
    ← watch.py chart-data 接口调用（复用60日趋势数据）
```

## 盯盘助手配置

**盯盘助手前端架构**：
- 图表：ECharts 分时线图，全宽，支撑/阻力标线，九转信号浮动标注
- 下方双栏：左=AI分析（realtime/7d/30d标签页），右=季度财报表格
- 缓存：localStorage（WatchStore），按市场分key持久化，每日自动清理
- 数据流：init→缓存恢复→API刷新→定时轮询（价格60s/分析15min/市场状态5min）

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |
| `WATCH_ALERT_COOLDOWN_MINUTES` | 盘中极值告警冷却时间（分钟） | `5` |

**AI分析调度**：
- realtime：`watch_realtime` 策略，开盘时段每15分钟（`*/15 9-23 * * 1-5`，内部检查市场状态）
- realtime 增量推送：`_realtime_push_state` 追踪每股当日已推状态，首次完整推送，后续仅推变化（信号/支撑阻力/摘要），无变化跳过
- 7d/30d：每日简报推送时自动计算（8:00am），结果包含在 Slack 消息中
- 分析入口：`WatchAnalysisService.analyze_stocks(period, force)`

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
| `NEWS_DEDUP_WINDOW_MINUTES` | 新闻推送去重窗口（分钟） | `1440` |

## 华尔街见闻投行观点配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WALLSTREET_NEWS_ENABLED` | 是否启用华尔街见闻策略 | `true` |
| `WALLSTREET_NEWS_FETCH_TIMEOUT` | crawl4ai 全文爬取超时（秒） | `10` |

每日 20:00（工作日）自动抓取华尔街见闻快讯流和文章列表，关键词过滤投行/机构观点（高盛、摩根、花旗等），crawl4ai 爬取全文，GLM Flash 整理关键信息后 Slack 推送到 `news_research` 频道。

## 野村证券研报配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NOMURA_RESEARCH_ENABLED` | 是否启用野村研报爬虫 | `true` |

每日 20:10（工作日）抓取 nomuraconnects.com 的 economics 和 central-banks 分类，关键词过滤亚洲/中国相关文章，crawl4ai 爬取全文，GLM Flash 整理关键观点后推送到 `news_research` 频道。

## 博客监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `BLOG_MONITOR_ENABLED` | 是否启用博客监控 | `true` |

每日 5:00 独立调度检查 Anthropic Engineering / OpenAI Blog / DeepMind Blog 新文章，crawl4ai 抓取全文 + GLM 中文摘要，推送到 `news_ai_tool` 频道。博客源配置在 `app/config/blog_monitor.py`。

## GitHub Trending 监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `GITHUB_TRENDING_ENABLED` | 是否启用 GitHub Trending 监控 | `true` |
| `GITHUB_TRENDING_TOP_N` | 取前 N 个项目 | `10` |

每日 5:00 独立调度爬取 github.com/trending 页面 Top N 项目，与已推送记录比对，仅推送新上榜的项目（含 GLM 中文摘要）到 `news_ai_tool` 频道。首次运行只记录不推送。

## Slack 推送配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `SLACK_BOT_TOKEN` | Slack Bot Token | 空 |

频道路由：

| 频道 | 内容 |
|------|------|
| `news` | 每日简报、预警、公司新闻、兴趣新闻 |
| `news_watch` | 盯盘实时分析、每日简报盯盘部分 |
| `news_ai_tool` | GitHub Release 更新 |
| `news_lol` | LoL 赛事 |
| `news_nba` | NBA 赛事 |
| `news_daily` | 每日核心观点（带日期） |
| `news_operation` | 清仓策略、操作计划 |
| `news_research` | 投行观点日报 |

## 赛事推送配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ESPORTS_ENABLED` | 是否启用赛事推送 | `true` |
| `ESPORTS_FETCH_TIMEOUT` | 赛事API请求超时（秒） | `15` |
| `ESPORTS_NBA_MONITOR_INTERVAL` | NBA 比分轮询间隔（分钟） | `15` |
| `ESPORTS_LOL_MONITOR_INTERVAL` | LoL 比分轮询间隔（分钟） | `30` |
| `ESPORTS_PRE_MATCH_MINUTES` | 赛前提醒（开赛前N分钟） | `30` |

**推送逻辑**：
- 赛前提醒：比赛开始前30分钟推送
- 比分变化：仅在比分发生变化时推送（避免重复通知）
- 比赛结束：自动检测并推送最终比分
- NBA晚间调度：每天18:00额外执行一次NBA监控设置，覆盖当晚比赛

数据源：NBA 用 ESPN API（无需认证），LoL 用 LoL Esports API（LPL/LCK/国际赛事/先锋赛）。

## LLM 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ZHIPU_API_KEY` | 智谱 GLM API 密钥（仅免费 glm-4-flash） | 空 |
| `GEMINI_API_KEY` | Google Gemini API 密钥，多个逗号分隔（FLASH/PREMIUM 主力） | 空 |
| `LLM_DAILY_BUDGET` | 日预算上限（美元） | 无上限 |
| `LLM_REQUEST_TIMEOUT` | API 请求超时（秒） | `300` |
| `LLM_RATE_LIMIT_RPM` | 智谱 API 全局限流（RPM） | `10` |
| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |
| `LLAMA_MAX_CONTEXT` | llama-server 上下文窗口大小 | `4096` |

## 技术栈

- Flask + SQLAlchemy + SQLite
- RapidOCR (ONNX Runtime)
- Bootstrap 5 + 原生 JavaScript
- akshare（A股数据）+ yfinance（美股/港股/期货数据）+ Twelve Data + Polygon
- 智谱 GLM（LITE 层免费 glm-4-flash）+ Google Gemini（FLASH/PREMIUM 层主力）
- APScheduler（策略调度）
- PyTorch（AI走势预测，可选）— `app/ml/` 模块，未安装 torch 时自动跳过

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

## 设计文档

设计和实施计划保存在 `docs/plans/` 目录，格式 `YYYY-MM-DD-<topic>-design.md`

## 盯盘告警推送格式

盯盘告警 title 一行展示核心信息，detail 补充上下文。支撑/阻力用描述性标签（跌破/突破/测试/触及），其余用 `>` `<` 直观比较。

| 告警类型 | 格式示例 |
|---------|--------|
| 盘中极值 | `当前 26.00 > 前高 25.50` |
| 目标价 | `当前 26.00 > 目标 25.50` |
| 跌破支撑 | `跌破支撑 25.00 \| 当前 24.95` + detail: `下方支撑 24.00(-3.8%)` |
| 突破阻力 | `突破阻力 30.00 \| 当前 30.05` + detail: `上方阻力 32.00(+6.5%)` |
| 测试支撑 | `测试支撑 25.00 \| 当前 25.05` + detail: `上方阻力 28.00(+11.8%)` |
| 测试阻力 | `测试阻力 30.00 \| 当前 29.95` + detail: `下方支撑 28.00(-6.5%)` |
| 均线穿越 | `上穿 当前 21.00 > MA5 20.50` |
| 成交量异动 | `成交量 100 > 日均 50 (2.0x)` |
| TD九转 | `TD九转买入信号 | 当前 26.00` |

**涉及文件**：
- `app/services/watch_alert_service.py` — 7种检测器（极值/目标价/支撑阻力/均线/成交量/TD九转）
- `app/services/notification.py` — `dispatch_signal()` direction→emoji 路由（🔴=up/buy/resistance_break, 🟢=down/sell/support_break），`push_realtime_analysis()` 实时分析推送格式
- `app/strategies/volume_alert/__init__.py` — 收盘成交量异动策略

## 开发规范

**配置变更同步**：新增/修改环境变量配置时，需同步更新 `CLAUDE.md`、`README.md`、`.env.sample` 三处

### Slack 推送排版规范

所有 `notification.py` 和策略中的 `format_*` 方法遵循以下规范（Slack mrkdwn 格式）：

**标题**：`emoji + *粗体标题*`，如 `📉 *高点回退提醒*`

**多条目列表**（每条含3行以上信息）：
- 条目间用分隔线 `'─' * 30` 隔开
- 条目名 `*粗体*`，元数据紧随其后
- 描述/正文前空一行，增加呼吸感
- 链接放最后一行

**紧凑列表**（每条仅1行信息）：
- 条目用 `  · ` 前缀，无需分隔线
- 同类数据用 ` | ` 分隔在一行内

**数字格式**：大数加千分位 `{:,}`，百分比用 `{:+.2f}%`（含正负号）

**避免**：
- 同一信息重复出现（如标题行已截断描述 + 下方再输出完整描述）
- 同一 emoji 表达不同含义（如 ⭐ 既标记标题又标记星数）

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
