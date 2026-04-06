"""野村证券研报爬虫服务"""

import asyncio
import hashlib
import json
import logging
import os
import re
from datetime import date, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

NOMURA_RESEARCH_ENABLED = os.getenv('NOMURA_RESEARCH_ENABLED', 'true').lower() == 'true'
NOMURA_FETCH_TIMEOUT = int(os.getenv('WALLSTREET_NEWS_FETCH_TIMEOUT', '10'))

BASE_URL = 'https://www.nomuraconnects.com'
CATEGORY_PATHS = ['/economics/', '/central-banks/']

ASIA_KEYWORDS = re.compile(
    r'china|asia|japan|korea|india|asean|cny|jpy|'
    r'hong\s*kong|taiwan|singapore|emerging|apac|'
    r'boj|pboc|rba|rbi|bse|nifty|hang\s*seng|shanghai|shenzhen',
    re.IGNORECASE,
)

CACHE_DIR = Path('data/nomura_research_cache')
USER_AGENT = 'Mozilla/5.0 (compatible; stock-bot/1.0)'


class NomuraResearchService:
    """野村证券研报爬取与分析"""

    # ── 列表页解析 ──

    @staticmethod
    def _fetch_article_list() -> list[dict]:
        """爬取分类列表页，提取文章链接和标题"""
        from bs4 import BeautifulSoup

        articles = []
        seen_urls = set()

        for path in CATEGORY_PATHS:
            url = f'{BASE_URL}{path}'
            try:
                resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
                resp.raise_for_status()
            except Exception as e:
                logger.warning(f'[野村研报] 列表页请求失败 {path}: {e}')
                continue

            soup = BeautifulSoup(resp.text, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/focused-thinking-posts/' not in href:
                    continue

                article_url = href if href.startswith('http') else f'{BASE_URL}{href}'
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                title = link.get_text(strip=True)
                if not title:
                    h_tag = link.find(['h2', 'h3', 'h4'])
                    title = h_tag.get_text(strip=True) if h_tag else ''
                if not title:
                    continue

                articles.append({
                    'title': title,
                    'url': article_url,
                    'category': path.strip('/'),
                })

        logger.info(f'[野村研报] 列表页共发现 {len(articles)} 篇文章')
        return articles

    # ── 关键词过滤 ──

    @staticmethod
    def _filter_asia(articles: list[dict]) -> list[dict]:
        return [a for a in articles if ASIA_KEYWORDS.search(a['title'])]

    # ── 全文爬取 ──

    @staticmethod
    def _fetch_full_content(url: str) -> str:
        try:
            from crawl4ai import AsyncWebCrawler

            async def _fetch():
                async with AsyncWebCrawler() as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url),
                        timeout=NOMURA_FETCH_TIMEOUT,
                    )
                    if result and result.markdown:
                        return result.markdown[:4000]
                return ''

            return asyncio.run(_fetch())
        except ImportError:
            logger.warning('[野村研报] crawl4ai 不可用')
            return ''
        except Exception as e:
            logger.warning(f'[野村研报] 全文爬取失败 {url}: {e}')
            return ''

    # ── 去重 ──

    @staticmethod
    def _load_pushed_hashes() -> set[str]:
        hashes = set()
        for days_ago in range(3):
            target = date.today() - timedelta(days=days_ago)
            cache_file = CACHE_DIR / f"{target.isoformat()}.json"
            if cache_file.exists():
                try:
                    data = json.loads(cache_file.read_text(encoding='utf-8'))
                    for item in data.get('items', []):
                        hashes.add(item.get('content_hash', ''))
                except Exception:
                    pass
        return hashes

    @staticmethod
    def _dedup(articles: list[dict]) -> list[dict]:
        pushed = NomuraResearchService._load_pushed_hashes()
        seen = set()
        result = []
        for a in articles:
            h = hashlib.md5(a['title'].encode()).hexdigest()[:16]
            a['content_hash'] = h
            if h in pushed or h in seen:
                continue
            seen.add(h)
            result.append(a)
        return result

    # ── 缓存 ──

    @staticmethod
    def _save_cache(items: list[dict], analysis: str):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{date.today().isoformat()}.json"
        try:
            cache_file.write_text(json.dumps({
                'items': items,
                'analysis': analysis,
            }, ensure_ascii=False, indent=2), encoding='utf-8')
            NomuraResearchService._cleanup_old_cache()
        except Exception as e:
            logger.error(f'[野村研报] 缓存保存失败: {e}')

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

    # ── LLM 分析 ──

    @staticmethod
    def _analyze(items: list[dict]) -> str:
        if not items:
            return ''
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.nomura_research import (
                NOMURA_SYSTEM_PROMPT, build_nomura_prompt,
            )

            provider = llm_router.route('nomura_research')
            if not provider:
                return ''

            prompt = build_nomura_prompt(items)
            response = provider.chat(
                [
                    {'role': 'system', 'content': NOMURA_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.strip()
        except Exception as e:
            logger.error(f'[野村研报] LLM 分析失败: {e}')
            return ''

    # ── 输出 ──

    @staticmethod
    def _format_slack_message(analysis: str, count: int) -> str:
        today_str = date.today().isoformat()
        return (
            f'📊 *野村研报精选* ({today_str})\n\n'
            f'━━━━━━━━━━━━━━━━\n'
            f'{analysis}\n'
            f'━━━━━━━━━━━━━━━━\n\n'
            f'来源：Nomura Connects | {count} 篇文章'
        )

    # ── 主流程 ──

    @staticmethod
    def run_daily() -> dict:
        if not NOMURA_RESEARCH_ENABLED:
            logger.info('[野村研报] 功能未启用')
            return {'enabled': False}

        logger.info('[野村研报] 开始抓取')

        articles = NomuraResearchService._fetch_article_list()
        filtered = NomuraResearchService._filter_asia(articles)
        logger.info(f'[野村研报] 亚洲相关: {len(filtered)}/{len(articles)} 篇')

        deduped = NomuraResearchService._dedup(filtered)
        if not deduped:
            logger.info('[野村研报] 无新内容')
            return {'total': len(articles), 'filtered': len(filtered), 'new': 0}

        for item in deduped:
            full_text = NomuraResearchService._fetch_full_content(item['url'])
            if full_text:
                item['text'] = full_text
            else:
                item['text'] = item['title']

        analysis = NomuraResearchService._analyze(deduped)
        NomuraResearchService._save_cache(deduped, analysis)

        if analysis:
            try:
                from app.services.notification import NotificationService
                from app.config.notification_config import CHANNEL_RESEARCH
                message = NomuraResearchService._format_slack_message(analysis, len(deduped))
                NotificationService.send_slack(message, CHANNEL_RESEARCH)
                logger.info('[野村研报] Slack 推送成功')
            except Exception as e:
                logger.error(f'[野村研报] Slack 推送失败: {e}')

        logger.info(f'[野村研报] 完成: {len(deduped)} 篇新文章')
        return {'total': len(articles), 'filtered': len(filtered), 'new': len(deduped)}

    # ── 推送测试 ──

    @staticmethod
    def test_push() -> bool:
        """测试推送到 Slack（使用模拟数据）"""
        try:
            from app.services.notification import NotificationService
            from app.config.notification_config import CHANNEL_RESEARCH

            test_msg = (
                '📊 *野村研报精选* (测试)\n\n'
                '━━━━━━━━━━━━━━━━\n'
                '*亚洲宏观展望*\n'
                '  · 野村首席中国经济学家陆挺：预计Q2 GDP增速5.2%\n'
                '  · 亚洲央行政策分化，印度RBI可能降息\n\n'
                '*风险提示*\n'
                '  · 地缘政治不确定性上升\n'
                '━━━━━━━━━━━━━━━━\n\n'
                '来源：Nomura Connects | 测试推送'
            )
            success = NotificationService.send_slack(test_msg, CHANNEL_RESEARCH)
            logger.info(f'[野村研报] 测试推送: {"成功" if success else "失败"}')
            return success
        except Exception as e:
            logger.error(f'[野村研报] 测试推送异常: {e}')
            return False
