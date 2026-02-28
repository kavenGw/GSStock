"""公司新闻爬取服务：针对用户配置的公司主动搜索新闻"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import quote

from app import db
from app.models.news import NewsItem, CompanyKeyword
from app.config.news_config import (
    COMPANY_NEWS_MAX_COMPANIES, COMPANY_NEWS_MAX_ARTICLES,
    COMPANY_NEWS_CRAWL_TIMEOUT, COMPANY_NEWS_TOTAL_TIMEOUT,
)

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = "将以下新闻文章压缩为50-100字的中文摘要，保留核心事实。直接返回摘要文本。"


class CompanyNewsService:

    @staticmethod
    def fetch_company_news():
        """批量爬取公司新闻（后台线程调用）"""
        from app import create_app
        app = create_app()
        with app.app_context():
            companies = CompanyKeyword.query.filter_by(is_active=True).limit(
                COMPANY_NEWS_MAX_COMPANIES
            ).all()
            if not companies:
                return

            company_names = [c.name for c in companies]
            logger.info(f'[公司新闻] 开始爬取: {company_names}')

            try:
                results = asyncio.run(CompanyNewsService._fetch_all(company_names))
                if results:
                    CompanyNewsService._save_results(results)
                    logger.info(f'[公司新闻] 完成，共 {len(results)} 条')
            except Exception as e:
                logger.error(f'[公司新闻] 爬取失败: {e}')

    @staticmethod
    async def _fetch_all(company_names: list[str]) -> list[dict]:
        from crawl4ai import AsyncWebCrawler

        all_results = []
        async with AsyncWebCrawler() as crawler:
            for name in company_names:
                try:
                    results = await asyncio.wait_for(
                        CompanyNewsService._fetch_single_company(crawler, name),
                        timeout=COMPANY_NEWS_TOTAL_TIMEOUT,
                    )
                    all_results.extend(results)
                except asyncio.TimeoutError:
                    logger.warning(f'[公司新闻] {name} 爬取超时')
                except Exception as e:
                    logger.error(f'[公司新闻] {name} 爬取失败: {e}')
        return all_results

    @staticmethod
    async def _fetch_single_company(crawler, company_name: str) -> list[dict]:
        google_task = CompanyNewsService._search_google_news(crawler, company_name)
        xueqiu_task = CompanyNewsService._search_xueqiu(crawler, company_name)
        google_results, xueqiu_results = await asyncio.gather(
            google_task, xueqiu_task, return_exceptions=True,
        )

        combined = []
        for r in (google_results, xueqiu_results):
            if isinstance(r, list):
                combined.extend(r)

        return combined[:COMPANY_NEWS_MAX_ARTICLES]

    @staticmethod
    async def _search_google_news(crawler, company_name: str) -> list[dict]:
        search_url = f"https://www.google.com/search?q={quote(company_name)}+新闻&tbm=nws"
        search_result = await crawler.arun(url=search_url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)

        urls = CompanyNewsService._extract_urls(search_result.markdown, 3)
        articles = []
        for url in urls:
            try:
                result = await crawler.arun(url=url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
                if result.markdown:
                    articles.append({
                        'url': url,
                        'content': result.markdown[:2000],
                        'source_name': 'google_news',
                        'company': company_name,
                    })
            except Exception:
                continue
        return articles

    @staticmethod
    async def _search_xueqiu(crawler, company_name: str) -> list[dict]:
        search_url = f"https://xueqiu.com/k?q={company_name}"
        search_result = await crawler.arun(url=search_url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)

        xueqiu_pattern = re.compile(r'https://xueqiu\.com/\d+/\d+')
        urls = list(dict.fromkeys(xueqiu_pattern.findall(search_result.markdown)))[:3]

        articles = []
        for url in urls:
            try:
                result = await crawler.arun(url=url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
                if result.markdown:
                    articles.append({
                        'url': url,
                        'content': result.markdown[:2000],
                        'source_name': 'xueqiu',
                        'company': company_name,
                    })
            except Exception:
                continue
        return articles

    @staticmethod
    def _save_results(results: list[dict]):
        from app.llm.router import llm_router

        provider = llm_router.route('news_classify')

        for item in results:
            source_id = hashlib.md5(item['url'].encode()).hexdigest()[:16]
            source_name = item['source_name']

            existing = NewsItem.query.filter_by(
                source_id=source_id, source_name=source_name
            ).first()
            if existing:
                continue

            content = item['content']
            if provider:
                try:
                    content = provider.chat([
                        {'role': 'system', 'content': SUMMARY_PROMPT},
                        {'role': 'user', 'content': item['content']},
                    ], temperature=0.1, max_tokens=200).strip()
                except Exception as e:
                    logger.error(f'[公司新闻] AI摘要失败: {e}')

            news = NewsItem(
                source_id=source_id,
                source_name=source_name,
                content=content,
                display_time=datetime.now(),
                score=1,
                is_interest=True,
                matched_keywords=item['company'],
            )
            db.session.add(news)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f'[公司新闻] 保存失败: {e}')

    @staticmethod
    def _extract_urls(markdown: str, max_count: int) -> list[str]:
        url_pattern = re.compile(r'\[.*?\]\((https?://[^)]+)\)')
        urls = []
        skip_domains = {'google.com', 'youtube.com', 'accounts.google'}
        for match in url_pattern.finditer(markdown):
            url = match.group(1)
            if any(d in url for d in skip_domains):
                continue
            urls.append(url)
            if len(urls) >= max_count:
                break
        return urls
