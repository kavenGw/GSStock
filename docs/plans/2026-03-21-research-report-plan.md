# 持仓股票研报推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 每天自动搜索持仓股票的最新研报，GLM 整理关键信息后独立 Slack 推送，并在每日简报中嵌入摘要。

**Architecture:** 新建 `ResearchReportService`（搜索+提取+分析）+ `ResearchReportStrategy`（调度），通过 Google News 搜索研报、crawl4ai 爬取内容、GLM Flash 评估相关性、GLM Premium 深度分析，结果缓存到 JSON 文件供日报引用。

**Tech Stack:** crawl4ai (AsyncWebCrawler), 智谱 GLM (Flash/Premium), APScheduler, ThreadPoolExecutor

**Spec:** `docs/plans/2026-03-21-research-report-design.md`

---

## File Map

### 新增文件

| 文件 | 职责 |
|-----|------|
| `app/llm/prompts/research_report.py` | 相关性评估 + 研报分析两个 prompt 模板 |
| `app/services/research_report_service.py` | 核心逻辑：搜索、评估、爬取、分析、缓存、推送 |
| `app/strategies/research_report/__init__.py` | 调度策略，工作日 9:00 触发 |

### 修改文件

| 文件 | 变更 |
|-----|------|
| `app/llm/router.py` | TASK_LAYER_MAP 新增 `research_report` 和 `research_relevance` |
| `app/services/notification.py` | 新增 `format_research_summary()`，`push_daily_report()` 中调用 |
| `.env.sample` | 新增研报相关环境变量 |
| `CLAUDE.md` | 新增研报配置说明 |
| `README.md` | 新增研报配置说明 |

---

## Task 1: LLM Prompt 模板

**Files:**
- Create: `app/llm/prompts/research_report.py`

- [ ] **Step 1: 创建 prompt 文件**

```python
"""持仓股票研报分析 Prompt 模板"""

# ── 相关性评估 ──

RESEARCH_RELEVANCE_SYSTEM_PROMPT = (
    "你是证券研报筛选助手。根据搜索结果判断每条内容与指定股票研报的相关性。"
    "返回JSON数组，每个元素包含 index(序号) 和 score(1-5分)。"
)


def build_relevance_prompt(stock_name: str, stock_code: str,
                           results: list[dict]) -> str:
    """构建相关性评估 prompt

    Args:
        stock_name: 股票名称
        stock_code: 股票代码
        results: 搜索结果列表，每项含 title, snippet
    """
    items = []
    for i, r in enumerate(results):
        items.append(f"{i+1}. 标题: {r['title']}\n   摘要: {r.get('snippet', '无')}")
    items_text = '\n'.join(items)

    return f"""目标股票：{stock_name}（{stock_code}）

以下是搜索结果，请为每条评分：
5=专业研报/评级变动  4=深度分析文章  3=一般分析  2=相关新闻  1=无关内容

{items_text}

返回JSON数组（不要markdown代码块包裹）：
[{{"index": 1, "score": 5}}, {{"index": 2, "score": 3}}, ...]"""


# ── 研报分析 ──

RESEARCH_ANALYSIS_SYSTEM_PROMPT = (
    "你是专业的证券分析师。根据提供的研报和分析师观点，整理关键信息。"
    "用简洁中文输出，不要编造信息。"
)


def build_analysis_prompt(stock_name: str, stock_code: str,
                          materials: list[dict]) -> str:
    """构建研报分析 prompt

    Args:
        stock_name: 股票名称
        stock_code: 股票代码
        materials: 筛选后的研报材料，每项含 title, content
    """
    parts = []
    for i, m in enumerate(materials):
        content = m.get('content') or m.get('snippet', '')
        parts.append(f"--- 材料{i+1} ---\n标题: {m['title']}\n{content}")
    materials_text = '\n\n'.join(parts)

    return f"""目标股票：{stock_name}（{stock_code}）

以下是最新的研报和分析师观点：

{materials_text}

请整理出以下关键信息（没有的项直接省略，不要编造）：

1. **评级变动**：近期是否有机构上调/下调/维持评级
2. **目标价**：各机构给出的目标价区间
3. **核心逻辑**：看多/看空的主要理由
4. **关键事件**：影响股价的近期事件（财报、产品、政策等）
5. **风险提示**：主要风险因素

直接返回分析文本，不要JSON格式。"""
```

- [ ] **Step 2: 验证 prompt 文件可导入**

Run: `cd D:/Git/stock && python -c "from app.llm.prompts.research_report import build_relevance_prompt, build_analysis_prompt; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/llm/prompts/research_report.py
git commit -m "feat: 添加研报分析 prompt 模板（相关性评估+深度分析）"
```

---

## Task 2: LLM 路由注册

**Files:**
- Modify: `app/llm/router.py` (TASK_LAYER_MAP, 约第9-26行)

- [ ] **Step 1: 在 TASK_LAYER_MAP 中添加两个新任务类型**

在 `TASK_LAYER_MAP` 字典末尾添加：

```python
    'research_report': LLMLayer.PREMIUM,
    'research_relevance': LLMLayer.FLASH,
```

- [ ] **Step 2: 验证路由可用**

Run: `cd D:/Git/stock && python -c "from app.llm.router import TASK_LAYER_MAP; print('research_report' in TASK_LAYER_MAP, 'research_relevance' in TASK_LAYER_MAP)"`
Expected: `True True`

- [ ] **Step 3: Commit**

```bash
git add app/llm/router.py
git commit -m "feat: LLM 路由注册 research_report(Premium) 和 research_relevance(Flash)"
```

---

## Task 3: ResearchReportService 核心服务

**Files:**
- Create: `app/services/research_report_service.py`

这是最核心的文件，包含搜索、评估、爬取、分析、缓存、推送全流程。

- [ ] **Step 1: 创建服务文件 — 配置和工具方法**

```python
"""持仓股票研报搜索与分析服务"""

import asyncio
import hashlib
import json
import logging
import os
import random
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)

# 配置
RESEARCH_REPORT_ENABLED = os.getenv('RESEARCH_REPORT_ENABLED', 'true').lower() == 'true'
RESEARCH_REPORT_MAX_STOCKS = int(os.getenv('RESEARCH_REPORT_MAX_STOCKS', '20'))
RESEARCH_REPORT_SEARCH_RESULTS = int(os.getenv('RESEARCH_REPORT_SEARCH_RESULTS', '5'))
RESEARCH_REPORT_FETCH_TIMEOUT = int(os.getenv('RESEARCH_REPORT_FETCH_TIMEOUT', '10'))

# ETF 排除关键词
ETF_KEYWORDS = ['ETF', 'etf', '基金', 'LOF', 'lof', '联接', 'QDII', 'qdii']

# 缓存目录
CACHE_DIR = Path('data/research_report_cache')


class ResearchReportService:
    """持仓股票研报搜索与分析"""

    @staticmethod
    def _is_etf(stock_name: str) -> bool:
        """判断是否为 ETF/基金"""
        return any(kw in stock_name for kw in ETF_KEYWORDS)

    @staticmethod
    def _get_position_stocks() -> list[tuple[str, str]]:
        """获取持仓股票列表（排除 ETF），返回 [(code, name), ...]"""
        from app.services.position import PositionService

        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return []

        positions = PositionService.get_snapshot(latest_date)
        stocks = []
        seen = set()
        for p in positions:
            if p.stock_code in seen:
                continue
            if ResearchReportService._is_etf(p.stock_name):
                continue
            seen.add(p.stock_code)
            stocks.append((p.stock_code, p.stock_name))

        return stocks[:RESEARCH_REPORT_MAX_STOCKS]

    @staticmethod
    def _build_search_queries(stock_code: str, stock_name: str) -> list[str]:
        """构建搜索关键词列表"""
        from app.utils.market_identifier import MarketIdentifier

        queries = [
            f"{stock_name} 研报",
            f"{stock_name} 分析师",
        ]

        market = MarketIdentifier.identify(stock_code)
        if market in ('US', 'HK'):
            queries.append(f"{stock_code} analyst report")
            queries.append(f"{stock_code} target price")

        return queries

    # ── 缓存 ──

    @staticmethod
    def _save_result_cache(analyses: dict):
        """保存分析结果到 JSON 文件"""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{date.today().isoformat()}.json"
        try:
            cache_file.write_text(json.dumps(analyses, ensure_ascii=False, indent=2),
                                  encoding='utf-8')
            ResearchReportService._cleanup_old_cache()
        except Exception as e:
            logger.error(f'[研报] 缓存保存失败: {e}')

    @staticmethod
    def _load_result_cache(target_date: date) -> dict | None:
        """读取指定日期的缓存"""
        cache_file = CACHE_DIR / f"{target_date.isoformat()}.json"
        if not cache_file.exists():
            return None
        try:
            return json.loads(cache_file.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f'[研报] 缓存读取失败: {e}')
            return None

    @staticmethod
    def _cleanup_old_cache():
        """清理 7 天前的缓存文件"""
        if not CACHE_DIR.exists():
            return
        cutoff = date.today() - timedelta(days=7)
        for f in CACHE_DIR.glob('*.json'):
            try:
                file_date = date.fromisoformat(f.stem)
                if file_date < cutoff:
                    f.unlink()
            except (ValueError, OSError):
                pass
```

- [ ] **Step 2: 添加搜索和爬取方法**

注意：所有异步操作共享同一个 `AsyncWebCrawler` 实例（单次 `asyncio.run()`），避免重复创建 Playwright 浏览器。

在 `ResearchReportService` 类中继续添加：

```python
    # ── 搜索 ──

    @staticmethod
    async def _async_search_stock(crawler, stock_code: str, stock_name: str) -> list[dict]:
        """异步搜索单只股票的研报（复用传入的 crawler 实例）"""
        queries = ResearchReportService._build_search_queries(stock_code, stock_name)
        all_results = []
        seen_urls = set()

        for query in queries:
            try:
                search_url = f"https://www.google.com/search?q={quote(query)}&tbm=nws"
                result = await asyncio.wait_for(
                    crawler.arun(url=search_url),
                    timeout=30,
                )
                if not result or not result.markdown:
                    continue

                items = ResearchReportService._parse_search_results(
                    result.markdown, RESEARCH_REPORT_SEARCH_RESULTS,
                )
                for item in items:
                    url_hash = hashlib.md5(item['url'].encode()).hexdigest()[:16]
                    if url_hash not in seen_urls:
                        seen_urls.add(url_hash)
                        item['query'] = query
                        all_results.append(item)

                await asyncio.sleep(random.uniform(1.0, 2.0))
            except asyncio.TimeoutError:
                logger.warning(f'[研报] 搜索超时: {query}')
            except Exception as e:
                logger.error(f'[研报] 搜索失败 {query}: {e}')

        return all_results[:15]

    @staticmethod
    def _parse_search_results(markdown: str, max_results: int) -> list[dict]:
        """从 Google News 搜索结果的 markdown 中提取链接和摘要"""
        results = []
        links = re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)', markdown)
        skip_domains = ['google.com', 'youtube.com', 'accounts.google']

        for title, url in links:
            if any(d in url for d in skip_domains):
                continue
            if len(results) >= max_results:
                break
            snippet = ''
            url_pos = markdown.find(url)
            if url_pos > 0:
                after = markdown[url_pos + len(url):url_pos + len(url) + 300]
                snippet = re.sub(r'\[.*?\]\(.*?\)', '', after)
                snippet = re.sub(r'[#*_\[\]()]', '', snippet).strip()
                snippet = snippet[:200]

            results.append({
                'title': title.strip(),
                'url': url,
                'snippet': snippet,
            })

        return results

    @staticmethod
    async def _async_fetch_full_content(crawler, url: str) -> str | None:
        """异步爬取全文内容（复用传入的 crawler 实例）"""
        try:
            result = await asyncio.wait_for(
                crawler.arun(url=url),
                timeout=RESEARCH_REPORT_FETCH_TIMEOUT,
            )
            if result and result.markdown:
                return result.markdown[:3000]
        except asyncio.TimeoutError:
            logger.debug(f'[研报] 全文爬取超时: {url}')
        except Exception as e:
            logger.debug(f'[研报] 全文爬取失败 {url}: {e}')
        return None

    @staticmethod
    async def _async_process_all_stocks(stocks: list[tuple[str, str]]) -> dict:
        """在单个 asyncio.run() 中处理所有股票，共享一个 crawler 实例"""
        results = {}
        crawler_ctx = None
        crawler = None

        try:
            from crawl4ai import AsyncWebCrawler
            crawler_ctx = AsyncWebCrawler()
            crawler = await crawler_ctx.__aenter__()
        except ImportError:
            logger.warning('[研报] crawl4ai 不可用，跳过搜索')
            return {}
        except Exception as e:
            logger.warning(f'[研报] Playwright 不可用: {e}')
            return {}

        try:
            for code, name in stocks:
                try:
                    search_results = await asyncio.wait_for(
                        ResearchReportService._async_search_stock(crawler, code, name),
                        timeout=120,
                    )
                    results[(code, name)] = search_results
                except asyncio.TimeoutError:
                    logger.warning(f'[研报] {name}({code}) 搜索总超时')
                    results[(code, name)] = []
                except Exception as e:
                    logger.error(f'[研报] {name}({code}) 搜索异常: {e}')
                    results[(code, name)] = []
        finally:
            if crawler_ctx:
                try:
                    await crawler_ctx.__aexit__(None, None, None)
                except Exception:
                    pass

        return results

    @staticmethod
    async def _async_fetch_full_batch(crawler_needed: list[dict]) -> None:
        """批量爬取高相关性结果的全文，共享 crawler"""
        if not crawler_needed:
            return
        try:
            from crawl4ai import AsyncWebCrawler
            async with AsyncWebCrawler() as crawler:
                for r in crawler_needed:
                    content = await ResearchReportService._async_fetch_full_content(
                        crawler, r['url'],
                    )
                    if content:
                        r['content'] = content
        except Exception as e:
            logger.warning(f'[研报] 全文爬取批量失败: {e}')
```

- [ ] **Step 3: 添加 LLM 评估和分析方法**

```python
    # ── LLM 评估与分析 ──

    @staticmethod
    def _search_all_stocks(stocks: list[tuple[str, str]]) -> dict:
        """同步入口：搜索所有股票（单次 asyncio.run，共享 crawler）"""
        try:
            return asyncio.run(
                ResearchReportService._async_process_all_stocks(stocks)
            )
        except Exception as e:
            logger.error(f'[研报] 批量搜索失败: {e}')
            return {}

    @staticmethod
    def _evaluate_relevance(stock_code: str, stock_name: str,
                            results: list[dict]) -> list[dict]:
        """用 GLM Flash 评估搜索结果相关性，返回评分≥3的结果"""
        if not results:
            return []

        try:
            from app.llm.router import llm_router
            from app.llm.prompts.research_report import (
                RESEARCH_RELEVANCE_SYSTEM_PROMPT, build_relevance_prompt,
            )

            provider = llm_router.route('research_relevance')
            if not provider:
                return results

            prompt = build_relevance_prompt(stock_name, stock_code, results)
            response = provider.chat(
                [
                    {'role': 'system', 'content': RESEARCH_RELEVANCE_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.1,
                max_tokens=500,
            )

            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            scores = json.loads(cleaned)

            score_map = {s['index']: s['score'] for s in scores}
            filtered = []
            for i, r in enumerate(results):
                score = score_map.get(i + 1, 0)
                r['relevance_score'] = score
                if score >= 3:
                    filtered.append(r)

            return filtered
        except Exception as e:
            logger.warning(f'[研报] 相关性评估失败: {e}，使用全部结果')
            return results

    @staticmethod
    def _fetch_full_for_high_relevance(results: list[dict]) -> list[dict]:
        """对高相关性结果（≥4）尝试爬取全文"""
        high_relevance = [r for r in results if r.get('relevance_score', 0) >= 4]
        if not high_relevance:
            return results

        try:
            asyncio.run(ResearchReportService._async_fetch_full_batch(high_relevance))
        except Exception as e:
            logger.warning(f'[研报] 全文爬取批量失败: {e}')

        return results

    @staticmethod
    def _analyze_stock_reports(stock_code: str, stock_name: str,
                               materials: list[dict]) -> str:
        """用 GLM Premium 分析单只股票的研报"""
        if not materials:
            return ''

        try:
            from app.llm.router import llm_router
            from app.llm.prompts.research_report import (
                RESEARCH_ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt,
            )

            provider = llm_router.route('research_report')
            if not provider:
                return ''

            prompt = build_analysis_prompt(stock_name, stock_code, materials)
            response = provider.chat(
                [
                    {'role': 'system', 'content': RESEARCH_ANALYSIS_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
            )

            return response.strip()
        except Exception as e:
            logger.error(f'[研报] 分析 {stock_name}({stock_code}) 失败: {e}')
            return ''
```

- [ ] **Step 4: 添加推送和主流程**

```python
    # ── 输出 ──

    @staticmethod
    def _format_slack_message(analyses: dict) -> str:
        """格式化完整 Slack 推送消息"""
        today_str = date.today().isoformat()
        lines = [f'📊 持仓研报日报 ({today_str})', '', '━━━━━━━━━━━━━━━━']

        has_report_count = 0
        for code, info in analyses.items():
            analysis = info.get('analysis', '')
            if not analysis:
                continue
            has_report_count += 1
            name = info.get('name', code)
            lines.append(f'🔹 {name} ({code})')
            lines.append(analysis)
            lines.append('')

        lines.append('━━━━━━━━━━━━━━━━')
        total = len(analyses)
        lines.append(f'共分析 {total} 只持仓股票，{has_report_count} 只有新研报动态')

        return '\n'.join(lines)

    @staticmethod
    def get_today_summary() -> dict | None:
        """获取今日（或最近一个工作日的）研报摘要，供日报引用"""
        # 尝试昨天的缓存（日报 8:30 调用时，当天 9:00 的研报还未生成）
        for days_ago in range(1, 4):
            target = date.today() - timedelta(days=days_ago)
            cache = ResearchReportService._load_result_cache(target)
            if cache:
                return cache
        return None

    # ── 主流程 ──

    @staticmethod
    def run_daily_report() -> dict:
        """每日研报分析主流程

        流程：
        1. 获取持仓（同步，DB查询在主线程）
        2. 批量搜索（单次 asyncio.run，共享 crawler）
        3. 逐只：相关性评估 + 全文爬取 + GLM 分析（顺序执行，LLM 调用无需并行）
        4. 缓存 + Slack 推送

        注意：研报 9:00 运行，日报 8:30 引用前一天缓存。
        """
        if not RESEARCH_REPORT_ENABLED:
            logger.info('[研报] 功能未启用')
            return {'enabled': False}

        stocks = ResearchReportService._get_position_stocks()
        if not stocks:
            logger.info('[研报] 无持仓股票')
            return {'stocks': 0}

        logger.info(f'[研报] 开始分析 {len(stocks)} 只持仓股票')

        # Phase 1: 批量搜索（共享单个 crawler 实例）
        search_results = ResearchReportService._search_all_stocks(stocks)

        # Phase 2: 逐只评估 + 分析
        analyses = {}
        for code, name in stocks:
            try:
                results = search_results.get((code, name), [])
                if not results:
                    analyses[code] = {'name': name, 'analysis': '', 'results_count': 0}
                    continue

                filtered = ResearchReportService._evaluate_relevance(code, name, results)
                if not filtered:
                    analyses[code] = {'name': name, 'analysis': '', 'results_count': len(results)}
                    continue

                enriched = ResearchReportService._fetch_full_for_high_relevance(filtered)
                analysis = ResearchReportService._analyze_stock_reports(code, name, enriched)

                analyses[code] = {
                    'name': name,
                    'analysis': analysis,
                    'results_count': len(results),
                    'filtered_count': len(filtered),
                }
            except Exception as e:
                logger.error(f'[研报] 处理 {name}({code}) 异常: {e}')
                analyses[code] = {'name': name, 'analysis': '', 'error': str(e)}

        # Phase 3: 缓存 + 推送
        ResearchReportService._save_result_cache(analyses)

        has_reports = any(a.get('analysis') for a in analyses.values())
        if has_reports:
            try:
                from app.services.notification import NotificationService
                from app.config.notification_config import CHANNEL_NEWS
                message = ResearchReportService._format_slack_message(analyses)
                NotificationService.send_slack(message, CHANNEL_NEWS)
                logger.info('[研报] Slack 推送成功')
            except Exception as e:
                logger.error(f'[研报] Slack 推送失败: {e}')

        report_count = sum(1 for a in analyses.values() if a.get('analysis'))
        logger.info(f'[研报] 完成：{len(stocks)} 只股票，{report_count} 只有研报动态')

        return {
            'stocks': len(stocks),
            'reports': report_count,
            'analyses': analyses,
        }
```

- [ ] **Step 5: 验证服务文件可导入**

Run: `cd D:/Git/stock && python -c "from app.services.research_report_service import ResearchReportService; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/services/research_report_service.py
git commit -m "feat: 研报搜索与分析服务（搜索+评估+爬取+分析+缓存+推送）"
```

---

## Task 4: 调度策略

**Files:**
- Create: `app/strategies/research_report/__init__.py`

- [ ] **Step 1: 创建策略子包目录和文件**

```bash
mkdir -p app/strategies/research_report
```

```python
"""持仓股票研报推送策略"""

import logging

from app.strategies.base import Signal, Strategy

logger = logging.getLogger(__name__)


class ResearchReportStrategy(Strategy):
    """每日持仓股票研报搜索与分析"""

    name = "research_report"
    description = "持仓股票研报搜索与分析"
    schedule = "0 9 * * 1-5"
    enabled = True
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.research_report_service import (
            RESEARCH_REPORT_ENABLED,
            ResearchReportService,
        )

        if not RESEARCH_REPORT_ENABLED:
            return []

        try:
            results = ResearchReportService.run_daily_report()
            report_count = results.get('reports', 0)
            stock_count = results.get('stocks', 0)
            logger.info(f'[研报策略] 完成：{stock_count} 只股票，{report_count} 只有研报')
        except Exception as e:
            logger.error(f'[研报策略] 执行失败: {e}')

        return []
```

- [ ] **Step 2: 验证策略可被自动发现**

Run: `cd D:/Git/stock && python -c "from app.strategies.research_report import ResearchReportStrategy; s = ResearchReportStrategy(); print(s.name, s.schedule, s.enabled)"`
Expected: `research_report 0 9 * * 1-5 True`

- [ ] **Step 3: Commit**

```bash
git add app/strategies/research_report/__init__.py
git commit -m "feat: 研报推送调度策略（工作日 9:00）"
```

---

## Task 5: 日报集成

**Files:**
- Modify: `app/services/notification.py`

需要在 `NotificationService` 中添加 `format_research_summary()` 方法，并在 `push_daily_report()` 中调用。

- [ ] **Step 1: 添加 format_research_summary() 方法**

在 `NotificationService` 类中（在 `format_esports_summary()` 方法之后）添加：

```python
    @staticmethod
    def format_research_summary() -> str:
        """格式化研报摘要用于日报推送"""
        try:
            from app.services.research_report_service import (
                RESEARCH_REPORT_ENABLED,
                ResearchReportService,
            )

            if not RESEARCH_REPORT_ENABLED:
                return ''

            cache = ResearchReportService.get_today_summary()
            if not cache:
                return ''

            lines = ['📋 研报动态']
            has_report = False
            for code, info in cache.items():
                analysis = info.get('analysis', '')
                if not analysis:
                    continue
                has_report = True
                name = info.get('name', code)
                # 取分析文本的第一行作为摘要
                first_line = analysis.split('\n')[0].strip()
                # 去掉 markdown 格式标记
                first_line = first_line.lstrip('#*- ').strip()
                if len(first_line) > 80:
                    first_line = first_line[:80] + '...'
                lines.append(f'• {name}: {first_line}')

            if not has_report:
                return ''

            lines.append('（完整研报已于 9:00 独立推送）')
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f'[通知.研报] 格式化失败: {e}')
            return ''
```

- [ ] **Step 2: 在 push_daily_report() 中调用**

在 `push_daily_report()` 方法中做两处修改：

**2a. 数据收集**（约在 `ai_text = ...` 赋值附近，`msg1_parts` 之前）添加：

```python
        research_text = NotificationService.format_research_summary()
```

**2b. 消息组装**（在 `msg3_parts` 组装末尾，`if ai_text:` 之后）添加：

```python
        if research_text:
            msg3_parts.append(research_text)
```

研报摘要追加到 msg3（市场与数据消息段）的末尾。现有消息组装循环 `for parts in (msg1_parts, msg2_parts, msg3_parts):` 无需修改。

- [ ] **Step 3: 验证方法可调用**

Run: `cd D:/Git/stock && python -c "from app.services.notification import NotificationService; r = NotificationService.format_research_summary(); print(type(r))"`
Expected: `<class 'str'>`

- [ ] **Step 4: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: 日报集成研报摘要板块"
```

---

## Task 6: 环境变量配置同步

**Files:**
- Modify: `.env.sample`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: 更新 .env.sample**

在公司新闻配置段之后添加：

```ini
# ============ 研报推送配置 ============
# RESEARCH_REPORT_ENABLED=true
# RESEARCH_REPORT_MAX_STOCKS=20
# RESEARCH_REPORT_SEARCH_RESULTS=5
# RESEARCH_REPORT_FETCH_TIMEOUT=10
```

- [ ] **Step 2: 更新 CLAUDE.md**

在"公司新闻配置"表格之后添加研报推送配置段：

```markdown
## 研报推送配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `RESEARCH_REPORT_ENABLED` | 是否启用研报推送 | `true` |
| `RESEARCH_REPORT_MAX_STOCKS` | 每次最多处理股票数 | `20` |
| `RESEARCH_REPORT_SEARCH_RESULTS` | 每个 query 取前N条 | `5` |
| `RESEARCH_REPORT_FETCH_TIMEOUT` | 全文爬取超时（秒） | `10` |

每日 9:00（工作日）自动搜索持仓股票的最新研报（ETF 除外），通过 Google News 搜索 + crawl4ai 爬取，GLM 整理关键信息后 Slack 独立推送。每日简报（8:30）中包含前一天的研报摘要。
```

- [ ] **Step 3: 更新 README.md**

在 README 的配置表格中添加同样的研报推送配置信息（格式与 CLAUDE.md 一致）。

- [ ] **Step 4: Commit**

```bash
git add .env.sample CLAUDE.md README.md
git commit -m "docs: 同步研报推送配置到 .env.sample、CLAUDE.md 和 README.md"
```

---

## Task 7: 集成验证

- [ ] **Step 1: 验证策略注册**

Run: `cd D:/Git/stock && python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.strategies.registry import StrategyRegistry
    registry = StrategyRegistry()
    registry.discover()
    names = [s.name for s in registry.active]
    print('research_report' in names, names)
"`
Expected: `True` 且列表中包含 `research_report`

- [ ] **Step 2: 验证完整导入链**

Run: `cd D:/Git/stock && python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.research_report_service import ResearchReportService
    stocks = ResearchReportService._get_position_stocks()
    print(f'持仓股票（排除ETF）: {len(stocks)} 只')
    for code, name in stocks[:5]:
        queries = ResearchReportService._build_search_queries(code, name)
        print(f'  {name}({code}): {len(queries)} 个搜索词')
"`
Expected: 打印持仓股票数量和搜索词计划

- [ ] **Step 3: 验证缓存读写**

Run: `cd D:/Git/stock && python -c "
from app.services.research_report_service import ResearchReportService
from datetime import date
test_data = {'600519': {'name': '贵州茅台', 'analysis': '测试分析'}}
ResearchReportService._save_result_cache(test_data)
loaded = ResearchReportService._load_result_cache(date.today())
print(loaded == test_data)
"`
Expected: `True`

- [ ] **Step 4: 清理测试缓存**

```bash
rm -f data/research_report_cache/*.json
```
