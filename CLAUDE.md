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

# Windows 下 python -c 打印含 emoji 的对象，需指定 UTF-8 避免 cp950 编码错误
PYTHONIOENCODING=utf-8 python -c "..."

# Windows bash 管道（| grep）或 PowerShell Select-String 可能静默吞掉 python 脚本 stdout；
# 验证脚本直接 open(path, 'w').write(...) 再用 Read 读取，稳过管道。

# create_app() 即便带 SCHEDULER_ENABLED=0 仍会启动调度器（17 任务）+ OCR + crawl4ai + LLM；
# 只测路由/配置层时跳过 create_app：Flask() + register_blueprint(<bp>) 直接注入，秒级、零副作用。
# 例外：渲染 HTML 的路由会因 base.html 跨 blueprint url_for（briefing.index 等）抛 BuildError → HTML 测试必须走 create_app()。

# 只读 DB 巡检不需要 create_app，直接 sqlite3 最快：
# PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT ...'); ..."

# 运行单测（禁用调度器 + UTF-8 编码）
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v

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

**Stock 表约定**：PK 是 `stock_code` 字符串（非自增 id），列 `(stock_code, stock_name, investment_advice, created_at, updated_at, tags)`；库只存用户关注池（~50 条），不是全 A 股。新标的通过 `app/seeds/` 幂等注入。

**多账户合并**：同一股票多次出现时，数量相加，成本按加权平均计算

**OCR 流程**：图片上传 → Pillow 预处理 → Tesseract 识别 → 正则解析提取股票代码/名称/数量/价格

**服务层模式**：业务逻辑放在 `services/`，路由保持简洁

**模块级单例的 Flask context 陷阱**：`app/services/__init__.py` 的 `unified_stock_data_service = UnifiedStockDataService()` 在 import 期就会触发 `__init__`，此时无 Flask app context；任何访问 `db.session` 或 `<Model>.query` 的 init 期代码必须用 `has_app_context()` 守卫

**数据获取服务失败语义二分**：`_fetch_*` 类方法返回 `None` 表示异常/获取失败（已重试耗尽），返回空数据字典如 `{'today': [], 'yesterday': []}` 表示 API 成功但当下无数据。推送/聚合层据此区分"数据获取失败" vs "今日无赛事"。涉及该约定的服务异常分支必须 `logger.warning(... exc_info=True)` + 含 `type(e).__name__` + 关键上下文（如 league_id / HTTP status / 响应体片段），否则吞异常会让两种场景在日志中无法区分。参考 `app/services/esports_service.py:_fetch_lol_esports_schedule`。

**启动数据种子**：`app/seeds/` 放幂等数据 seed（区别于 `migrate_*` 改 schema），在 `create_app()` 里紧跟迁移调用。铁律：已存在的 `Stock.stock_name` / `investment_advice` / `StockCategory` 归属**一律不覆盖**，失败只记 warning 不抛出。`StockCategory.stock_code` 唯一约束 → 一只股票只能归属一个分类；跨板块引用（如 002916 深南电路在 PCB 同时被 CPU 产业链引用）只能保留现状并在 advice 文案里描述关联。

**产业链图谱约定**：配置在 `app/config/supply_chain.py` 的 `SUPPLY_CHAIN_GRAPHS` 字典，渲染路由 `/supply-chain/api/<name>`。`upstream/midstream/downstream` 三层均支持 `companies` 字段；公司条目可带 `tag` 承载非产业链语义，约定取值 `frontEC` / `don_buy` / `keep_watching` / `not_analyzed`，前端 `supply_chain.html` 的 `TAG_LABELS` 映射显示文案。主题型图谱（如赛事）的 `competitors` 可留 `{}`，`core.code` 用虚拟 slug（如 `WC2026`）。新增图谱只需在 `SUPPLY_CHAIN_GRAPHS` 加 dict key 即自动注册（路由按 dict 遍历），零路由/模板/seed 改动；跨链复用标的在 `role` 末尾标注「（同属 X 产业链）」与既有图谱保持一致。

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

### Volume 单位契约

所有 A 股 OHLC/realtime 的 `volume` 字段统一为**"手"** 单位（1手=100股）。

- 腾讯 `qt.gtimg.cn` / `fqkline` 日K原生返回"股"，解析时 `/100` 归一
- 新浪 `stock_zh_a_spot` / `stock_zh_a_daily` 原生返回"股"，解析时 `//100` 归一
- 东财 akshare `stock_zh_a_hist` / `stock_zh_a_spot_em` 原生是"手"，保持不变
- 东财直连 push2his、ETF `fund_etf_hist_em` 原生是"手"，保持不变

**VOLUME_UNIT_SCHEMA_VERSION 机制**：`app/services/unified_stock_data.py` 顶部定义版本常量，启动时校验 `data/memory_cache/.schema_version`。版本不匹配则自动清理内存缓存（`ohlc_*/price/index` pkl）和数据库缓存（`UnifiedStockCache` 对应 `cache_type` 行）。单位契约变更时 bump 该常量触发全量清理。

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

## GitHub Release 监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `CLAUDE_PLUGINS_DIR` | Claude Code 插件目录（动态发现本地已装插件所属仓库） | `~/.claude/plugins` |

监控仓库列表 = 静态配置（`app/config/github_releases.py` 的 `GITHUB_RELEASE_REPOS`） ∪ 本地已装 Claude Code 插件对应 marketplace 仓库，按 `repo` 去重（静态优先保留自定义 `name`/`emoji`/`key`）。

动态发现逻辑（`app/services/plugin_discovery.py`）：
- 读取 `$CLAUDE_PLUGINS_DIR/installed_plugins.json` 提取已装插件所属的 marketplace 名
- 在 `known_marketplaces.json` 查每个 marketplace 的 `source`，支持 `{source: 'github', repo: ...}` 和 `{source: 'git', url: 'https://github.com/.../.git'}`
- 非 github.com 源、目录不存在、JSON 损坏均安全降级为空列表（只用静态配置）
- 动态条目 `key` 统一加 `marketplace_` 前缀避免与静态 key 冲突

注意：不使用 GitHub Releases 发版的仓库（仅 commit 或 tag，如 `anthropics/claude-plugins-official`、`supabase/agent-skills`）纳入监控后不会产生推送，直到其首次发 Release。

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
- 每日赛程预告：`esports_daily_schedule` 策略 07:00 推送当日 NBA/LoL 赛程到 `news_nba` / `news_lol`（NBA 按 `NBA_TEAM_MONITOR` 过滤关注球队；LoL 覆盖 LPL/LCK/先锋赛/Worlds/MSI）
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

## akshare 财务取数接口约定

- **多年财务时序首选**：`ak.stock_financial_abstract_ths(symbol, indicator="按年度")` — 唯一对全市场（主板/创业板/科创板）稳定返回的接口，含 ROE/毛利率/净利率/营收/净利/现金流/周转/负债率
- **PE/PB 5 年历史分位**：`ak.stock_zh_valuation_baidu(symbol, indicator="市盈率(TTM)"|"市净率", period="近5年")`
- **避坑**：
  - `ak.stock_financial_analysis_indicator(symbol)` 对部分主板代码（如 603986）返回空，不可作默认
  - `ak.stock_a_indicator_lg` 已从 akshare 移除，AttributeError
  - `ak.stock_zh_a_spot_em` / `stock_individual_info_em` 频繁被东财限流（RemoteDisconnected）；实时价改用 `UnifiedStockDataService.get_realtime_prices()`

## 文档目录约定

- `docs/plans/` — 设计与实施计划，格式 `YYYY-MM-DD-<topic>-design.md`
- `docs/analysis/` — 个股 buffett 风格深度分析，格式 `YYYY-MM-DD-<股票名>-buffett分析.md`
- `docs/analysis/<NNqN>/` — 季报点评归档，格式 `YYYY-MM-DD-<股票名>-NNQN季报点评.md`（如 `docs/analysis/26q1/`）
- `docs/financial-analysis/` — 多股横向对比 / comps / 估值，格式 `YYYY-MM-DD-<主题>-<细分>.md`
- `docs/financial-analysis/<NNqN>/` — 该季度 comps / 横向对比归档，命名同上
- **跨目录引用惯例**：季报点评 / buffett 分析头部常见 `> 配套 comps：[..](../financial-analysis/...)` 相对链接互引；调整目录结构前先 `Grep "\.\./financial-analysis"` 和 `Grep "\.\./analysis"` 找出所有引用并同步修复，否则静默断链

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

**测试目录布局**：单测放 `tests/test_*.py` 平铺，不用 `tests/services/` 等子目录（仅存空 `__pycache__`）

**配置变更同步**：新增/修改环境变量配置时，需同步更新 `CLAUDE.md`、`README.md`、`.env.sample` 三处

**安装第三方仓库时**：无论是 Claude Code skill/plugin 还是其他工具仓库，完成安装后需同步添加到 `app/config/github_releases.py` 的 `GITHUB_RELEASE_REPOS`，以便监控新版本

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
