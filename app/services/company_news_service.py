"""公司新闻爬取服务：针对用户配置的公司主动搜索新闻"""
import asyncio
import hashlib
import logging
import re
from datetime import datetime
from urllib.parse import quote

from app import db
from app.models.news import NewsItem, CompanyKeyword
from app.models.stock import Stock
from app.utils.market_identifier import MarketIdentifier
from app.config.news_config import (
    COMPANY_NEWS_MAX_COMPANIES, COMPANY_NEWS_MAX_ARTICLES,
    COMPANY_NEWS_CRAWL_TIMEOUT, COMPANY_NEWS_TOTAL_TIMEOUT,
)

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = "将以下新闻文章压缩为50-100字的中文摘要，保留核心事实。直接返回摘要文本。"
TRANSLATE_PROMPT = "将以下英文财经新闻翻译为中文，保持简洁专业，保留关键数据和公司名称。直接返回翻译文本。"


class CompanyNewsService:

    @staticmethod
    def fetch_company_news():
        from app import create_app
        app = create_app()
        with app.app_context():
            companies = CompanyKeyword.query.filter_by(is_active=True).order_by(
                CompanyKeyword.last_fetched_at.asc().nullsfirst()
            ).limit(COMPANY_NEWS_MAX_COMPANIES).all()
            if not companies:
                return

            company_names = [c.name for c in companies]
            logger.info(f'[公司新闻] 开始爬取: {company_names}')

            for c in companies:
                c.last_fetched_at = datetime.now()
            db.session.commit()

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
    def _resolve_market(company_name: str) -> tuple:
        stock = Stock.query.filter_by(stock_name=company_name).first()
        if not stock:
            return (None, None)
        market = MarketIdentifier.identify(stock.stock_code)
        return (market, stock.stock_code)

    @staticmethod
    def _fetch_eastmoney_news(stock_code: str, company_name: str) -> list[dict]:
        try:
            import akshare as ak
            symbol = stock_code.split('.')[0]
            df = ak.stock_news_em(symbol=symbol)
            articles = []
            for _, row in df.head(COMPANY_NEWS_MAX_ARTICLES).iterrows():
                articles.append({
                    'url': row['新闻链接'],
                    'content': f"{row['新闻标题']}：{row['新闻内容']}",
                    'source_name': 'eastmoney_stock',
                    'company': company_name,
                })
            return articles
        except Exception as e:
            logger.error(f'[公司新闻] 东方财富获取失败 {company_name}: {e}')
            return []

    @staticmethod
    def _fetch_yahoo_news(stock_code: str, company_name: str) -> list[dict]:
        try:
            import yfinance as yf
            ticker_symbol = MarketIdentifier.to_yfinance(stock_code)
            ticker = yf.Ticker(ticker_symbol)
            news = ticker.news
            if not news:
                return []
            articles = []
            for item in news[:COMPANY_NEWS_MAX_ARTICLES]:
                content = item.get('content') or {}
                if not isinstance(content, dict):
                    continue
                title = content.get('title', '')
                summary = content.get('summary', '')
                canonical = content.get('canonicalUrl') or {}
                url = canonical.get('url', '') if isinstance(canonical, dict) else ''
                if not title or not url:
                    continue
                text = f"{title}：{summary}" if summary else title
                articles.append({
                    'url': url,
                    'content': text,
                    'source_name': 'yahoo_finance',
                    'company': company_name,
                })
            return articles
        except Exception as e:
            logger.error(f'[公司新闻] Yahoo Finance获取失败 {company_name}: {e}')
            return []

    @staticmethod
    async def _fetch_single_company(crawler, company_name: str) -> list[dict]:
        market, stock_code = CompanyNewsService._resolve_market(company_name)

        if market == 'A' and stock_code:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, CompanyNewsService._fetch_eastmoney_news, stock_code, company_name
            )
            if results:
                return results
            logger.info(f'[公司新闻] {company_name} 东方财富无结果，降级到 Google News')

        elif market and stock_code:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None, CompanyNewsService._fetch_yahoo_news, stock_code, company_name
            )
            if results:
                return results
            logger.info(f'[公司新闻] {company_name} Yahoo Finance无结果，降级到 Google News')

        return await CompanyNewsService._search_google_news(crawler, company_name)

    @staticmethod
    async def _search_google_news(crawler, company_name: str) -> list[dict]:
        search_url = f"https://www.google.com/search?q={quote(company_name)}+新闻&tbm=nws"
        search_result = await crawler.arun(url=search_url, timeout=COMPANY_NEWS_CRAWL_TIMEOUT)
        if not search_result or not search_result.markdown:
            logger.warning(f'[公司新闻] {company_name} Google搜索无结果')
            return []

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
    def _save_results(results: list[dict]):
        from app.llm.router import llm_router

        provider = llm_router.route('news_classify')
        new_items = []

        for item in results:
            source_id = hashlib.md5(item['url'].encode()).hexdigest()[:16]
            source_name = item['source_name']

            existing = NewsItem.query.filter_by(
                source_id=source_id, source_name=source_name
            ).first()
            if existing:
                continue

            content = item['content']
            if provider and item['source_name'] == 'yahoo_finance':
                try:
                    content = provider.chat([
                        {'role': 'system', 'content': TRANSLATE_PROMPT},
                        {'role': 'user', 'content': item['content']},
                    ], temperature=0.1, max_tokens=500).strip()
                except Exception as e:
                    logger.error(f'[公司新闻] AI翻译失败: {e}')
            elif provider and item['source_name'] not in ('eastmoney_stock',):
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
            new_items.append((item['company'], content))

        try:
            db.session.commit()
            if new_items:
                CompanyNewsService._notify_company_slack(new_items)
        except Exception as e:
            db.session.rollback()
            logger.error(f'[公司新闻] 保存失败: {e}')

    @staticmethod
    def _notify_company_slack(items: list[tuple[str, str]]):
        from app.services.notification import NotificationService
        try:
            for company, content in items:
                NotificationService.send_slack(f"🏢 [{company}] {content}")
        except Exception as e:
            logger.error(f'[公司新闻] Slack通知失败: {e}')

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
