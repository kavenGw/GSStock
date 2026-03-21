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

RESEARCH_REPORT_ENABLED = os.getenv('RESEARCH_REPORT_ENABLED', 'true').lower() == 'true'
RESEARCH_REPORT_MAX_STOCKS = int(os.getenv('RESEARCH_REPORT_MAX_STOCKS', '20'))
RESEARCH_REPORT_SEARCH_RESULTS = int(os.getenv('RESEARCH_REPORT_SEARCH_RESULTS', '5'))
RESEARCH_REPORT_FETCH_TIMEOUT = int(os.getenv('RESEARCH_REPORT_FETCH_TIMEOUT', '10'))

ETF_KEYWORDS = ['ETF', 'etf', '基金', 'LOF', 'lof', '联接', 'QDII', 'qdii']

CACHE_DIR = Path('data/research_report_cache')


class ResearchReportService:
    """持仓股票研报搜索与分析"""

    @staticmethod
    def _is_etf(stock_name: str) -> bool:
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

    # ── 搜索 ──

    @staticmethod
    async def _async_search_stock(crawler, stock_code: str, stock_name: str) -> list[dict]:
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
            if url_pos >= 0:
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
    async def _async_fetch_full_batch(items: list[dict]) -> None:
        if not items:
            return
        try:
            from crawl4ai import AsyncWebCrawler
            async with AsyncWebCrawler() as crawler:
                for r in items:
                    content = await ResearchReportService._async_fetch_full_content(
                        crawler, r['url'],
                    )
                    if content:
                        r['content'] = content
        except Exception as e:
            logger.warning(f'[研报] 全文爬取批量失败: {e}')

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

    # ── LLM 评估与分析 ──

    @staticmethod
    def _evaluate_relevance(stock_code: str, stock_name: str,
                            results: list[dict]) -> list[dict]:
        """用 GLM Flash 评估搜索结果相关性，返回评分>=3的结果"""
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

    # ── 输出 ──

    @staticmethod
    def _format_slack_message(analyses: dict) -> str:
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
    def get_latest_cached_summary() -> dict | None:
        """获取最近的研报缓存，供日报引用（日报 8:30 先于研报 9:00，所以取前1-3天缓存）"""
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
        3. 逐只：相关性评估 + 全文爬取 + GLM 分析
        4. 缓存 + Slack 推送
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
