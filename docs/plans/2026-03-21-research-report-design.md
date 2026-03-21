# 持仓股票研报推送机制设计

## 概述

每天自动搜索持仓股票（ETF除外）的最新研报和分析师观点，通过 GLM Premium 整理关键信息，独立 Slack 推送完整分析，同时在每日简报中嵌入摘要。

## 架构与数据流

```
每日定时触发 (ResearchReportStrategy, schedule: "0 9 * * 1-5")
  │
  ▼
ResearchReportService.run_daily_report()
  │
  ├─ 1. 获取持仓股票列表（排除 ETF）
  │     PositionService.get_snapshot(latest_date)
  │     过滤：名称包含 "ETF/基金/LOF" 的排除
  │
  ├─ 2. 逐只股票搜索研报（并行，ThreadPoolExecutor）
  │     每只股票 → 搜索计划：
  │       中文（所有市场）："{股票名} 研报" + "{股票名} 分析师"
  │       英文（仅美股/港股）："{代码} analyst report" + "{代码} target price"
  │     每个 query 取前5条，去重后每只股票最多15条
  │
  ├─ 3. 分层内容提取
  │     搜索结果（标题+摘要+URL）
  │     → GLM(Premium) 相关性评分(1-5)
  │     → 评分≥4：尝试爬取全文（超时10s，失败降级用摘要）
  │     → 评分=3：只用标题+摘要
  │     → 评分≤2：丢弃
  │
  ├─ 4. GLM(Premium) 逐只分析
  │     提取：评级变动、目标价、核心逻辑、关键事件、风险提示
  │
  ├─ 5. 独立 Slack 推送（完整研报）
  │
  └─ 6. 缓存分析结果供日报调用
        → 日报(8:30)引用前一天的缓存结果
```

## 搜索策略

### 搜索关键词

```python
def _build_search_queries(stock_code, stock_name):
    queries = []
    market = MarketIdentifier.identify(stock_code)

    # 中文搜索（所有市场）
    queries.append(f"{stock_name} 研报")
    queries.append(f"{stock_name} 分析师")

    # 英文搜索（仅美股/港股）
    if market in ('US', 'HK'):
        queries.append(f"{stock_code} analyst report")
        queries.append(f"{stock_code} target price")

    return queries
```

### 搜索引擎

分市场搜索策略：
- **A股中文搜索**：通过 Google News 搜索（`https://www.google.com/search?q={query}&tbm=nws`），使用 crawl4ai（Playwright）爬取搜索结果页，正则提取结果链接
- **美股/港股英文搜索**：同样通过 Google News 英文搜索
- crawl4ai 已是项目依赖（`crawl4ai>=0.8.0`），复用现有基础设施
- Playwright 不可用时自动降级跳过，记录 warn 日志

搜索方法为 async（crawl4ai 的 `AsyncWebCrawler`），在 `ThreadPoolExecutor` 中通过 `asyncio.run()` 桥接同步调用。

并发控制：
- `max_workers=3`，避免搜索引擎封 IP
- 每个 query 间隔 1-2 秒
- 单只股票搜索失败不影响其他股票，记录异常后继续

### 全文爬取

高相关性结果（评分≥4）尝试用 crawl4ai 爬取全文：
- 超时 10s，失败降级用摘要（付费墙、反爬等场景为预期失败）
- 全文截断上限 3000 字符，避免 LLM context 溢出
- 使用 crawl4ai 的 markdown 输出模式提取正文

### 去重

按 URL 去重（`source_id = md5(url)[:16]`），复用 CompanyNewsService 的去重模式。每天全量刷新，无需跨天持久化。

## 分层内容提取

```
搜索结果（标题+摘要+URL）
  │
  ▼
GLM(Premium) 相关性评估
  prompt: "为每条搜索结果评分(1-5)，
           5=专业研报/评级，4=深度分析，3=一般分析，2=相关新闻，1=无关"
  │
  ├─ 评分 ≥ 4 → 尝试爬取全文（超时10s，失败降级用摘要）
  ├─ 评分 = 3 → 只用标题+摘要
  └─ 评分 ≤ 2 → 丢弃
```

## GLM 分析

### Prompt 模板

```
你是专业的证券分析师。以下是关于 {stock_name}({stock_code}) 的最新研报和分析师观点。
请整理出以下关键信息：

1. **评级变动**：近期是否有机构上调/下调/维持评级
2. **目标价**：各机构给出的目标价区间
3. **核心逻辑**：看多/看空的主要理由
4. **关键事件**：影响股价的近期事件（财报、产品、政策等）
5. **风险提示**：主要风险因素

如果某项信息搜索结果中没有，直接省略该项，不要编造。
```

### LLM 配置

- 任务类型：`research_report` → `LLMLayer.PREMIUM`
- 相关性评估：`research_relevance` → `LLMLayer.FLASH`（只需评分，不需深度理解）
- temperature: 0.3
- max_tokens: 1500（每只股票分析），500（相关性评估）

### 成本估算

假设 20 只股票，每只 15 条搜索结果：
- 相关性评估（Flash）：20 次调用 × ~1000 tokens ≈ 20K tokens（约 $0.002）
- 深度分析（Premium）：20 次调用 × ~3000 tokens ≈ 60K tokens（约 $0.60）
- 单次运行总成本约 $0.60，不会对 `LLM_DAILY_BUDGET` 造成显著冲击

## 输出格式

### 独立 Slack 推送

```
📊 持仓研报日报 (2026-03-21)

━━━━━━━━━━━━━━━━
🔹 贵州茅台 (600519)
评级：中信维持"买入"，目标价2200
核心逻辑：Q1批价企稳，直营占比提升利好毛利率
风险：消费复苏力度不及预期

🔹 NVIDIA (NVDA)
评级：Morgan Stanley 上调至"Overweight"，目标价$180
核心逻辑：Blackwell架构需求强劲，数据中心收入超预期
关键事件：GTC大会发布新产品路线图
风险：中国出口限制政策收紧
━━━━━━━━━━━━━━━━

共分析 8 只持仓股票，3 只有新研报动态
```

### 日报摘要板块

嵌入 `NotificationService.push_daily_report()` 中：

```
📋 研报动态
• 茅台：中信维持"买入"，目标价2200
• NVDA：大摩上调至"Overweight"，目标价$180
• TSLA：高盛下调至"Neutral"，关注交付量下滑
（完整研报已于 9:00 独立推送）
```

日报引用前一天的缓存结果（周一日报引用周五结果，周末无研报更新是预期行为）。首次运行时日报中无此板块。

## 代码结构

### 新增文件

```
app/services/research_report_service.py        # 核心逻辑
app/strategies/research_report/__init__.py     # 调度策略（子包结构，匹配自动发现机制）
app/llm/prompts/research_report.py             # Prompt 模板（含 relevance + analysis 两个 prompt）
```

### 修改文件

```
app/services/notification.py
  + format_research_summary()             # 日报研报摘要
  + push_daily_report() 增加调用

app/llm/router.py
  + TASK_LAYER_MAP['research_report'] = LLMLayer.PREMIUM
  + TASK_LAYER_MAP['research_relevance'] = LLMLayer.FLASH
```

### 核心类

```python
class ResearchReportService:
    # 入口
    def run_daily_report() -> dict

    # 搜索
    def _build_search_queries(code, name) -> list[str]
    def _search_and_collect(code, name) -> list[dict]

    # 提取
    def _evaluate_relevance(code, name, results) -> list[dict]
    def _fetch_full_content(url) -> str | None

    # 分析
    def _analyze_stock_reports(code, name, results) -> str

    # 输出
    def _format_slack_message(analyses: dict) -> str
    def get_today_summary() -> dict | None       # 从文件缓存读取，进程重启后可恢复

    # 工具
    def _is_etf(stock_name) -> bool
    def _get_position_stocks() -> list[tuple[str, str]]

    # 缓存
    def _save_result_cache(analyses: dict)       # 保存到 data/research_report_cache/{date}.json
    def _load_result_cache(date) -> dict | None  # 读取缓存
```

### 策略

```python
class ResearchReportStrategy(Strategy):
    name = "research_report"
    description = "持仓股票研报搜索与分析"
    schedule = "0 9 * * 1-5"
    enabled = True
    needs_llm = True
```

## 环境变量

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `RESEARCH_REPORT_ENABLED` | 是否启用研报推送 | `true` |
| `RESEARCH_REPORT_MAX_STOCKS` | 每次最多处理股票数 | `20` |
| `RESEARCH_REPORT_SEARCH_RESULTS` | 每个 query 取前N条 | `5` |
| `RESEARCH_REPORT_FETCH_TIMEOUT` | 全文爬取超时（秒） | `10` |

## 缓存持久化

分析结果保存到 `data/research_report_cache/{date}.json`，确保：
- 进程重启后 `get_today_summary()` 仍可恢复
- 日报补发机制可获取研报数据
- 按日期文件管理，自动清理 7 天前的缓存文件

## ETF 排除规则

按名称匹配排除，股票名称包含以下关键词则视为 ETF：
- "ETF"
- "基金"
- "LOF"
- "联接"
- "QDII"
