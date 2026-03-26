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


def _format_capital_flow(content: str) -> str:
    """资金流向日报格式化"""
    title_match = re.match(r'(.+?资金流向[^：]*日报)[：:](.*?)(\d{6})', content)
    if not title_match:
        return content
    title = title_match.group(1)
    subtitle = title_match.group(2).strip()

    rows = re.findall(r'(\d{6})\s+(\S+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)', content)
    if not rows:
        return content

    lines = [title]
    if subtitle:
        lines.append(subtitle)
    lines.append('')

    name_width = max(len(r[1]) for r in rows)
    name_width = max(name_width, 2)

    header = f"{'代码':<8}{'名称':<{name_width + 2}}{'涨跌%':>8}{'换手%':>8}{'主力净流入':>12}"
    lines.append(header)

    for code, name, chg, turnover, net_flow in rows:
        net_val = int(float(net_flow))
        net_str = f"{net_val:,}"
        line = f"{code:<8}{name:<{name_width + 2}}{chg:>8}{turnover:>8}{net_str:>12}"
        lines.append(line)

    return '\n'.join(lines)


def _format_institution_research(content: str) -> str:
    """机构调研名单格式化"""
    title_match = re.match(r'(.+?调研[^：]*名单)[：:]', content)
    title = title_match.group(1) if title_match else '机构调研名单'

    rows = re.findall(r'(\d{6})\s+(\S+)\s+(\d+)\s+(\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(\S+)', content)
    if not rows:
        return content

    lines = [title, '']

    name_width = max(len(r[1]) for r in rows)
    name_width = max(name_width, 2)
    industry_width = max(len(r[5]) for r in rows)
    industry_width = max(industry_width, 2)

    header = f"{'代码':<8}{'名称':<{name_width + 2}}{'机构数':>6}{'收盘价':>8}{'涨跌%':>8}  {'行业'}"
    lines.append(header)

    for code, name, count, price, chg, industry in rows:
        line = f"{code:<8}{name:<{name_width + 2}}{count:>6}{price:>8}{chg:>8}  {industry}"
        lines.append(line)

    return '\n'.join(lines)


def _format_stock_ranking(content: str) -> str:
    """通用股票排名表格格式化（特大单/主力资金/排名等）"""
    # 先尝试5字段格式：代码 名称 价格 涨跌幅 行业（如"收盘价创历史新高股一览"）
    result = _format_stock_ranking_5col(content)
    if result != content:
        return result

    row_pattern = re.compile(
        r'(\d{6})\s+(\S+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(\S{2,})'
    )
    rows = row_pattern.findall(content)
    if len(rows) < 2:
        return content

    first_match = row_pattern.search(content)
    raw_before = content[:first_match.start()].strip()
    title = re.split(r'\s*(?:代码|简称|证券代码|证券简称)\s', raw_before)[0].strip()
    title = title.rstrip('：: ')
    title = re.sub(r'[：:]\s*\d+\.?\d*(?:\s+-?\d+\.?\d*)+\s+\S+', '', title, count=1).strip()
    if not title:
        title = '股票排名'

    col3 = '收盘价' if '收盘价' in content else '价格'
    col4 = '换手%' if '换手' in content else '涨跌%'
    if '特大单净流入' in content:
        col5 = '净流入(亿)'
    elif '特大单净流出' in content:
        col5 = '净流出(亿)'
    elif '主力净流入' in content:
        col5 = '主力净入(亿)'
    else:
        col5 = '净额(亿)'

    lines = [title, '']
    name_w = max(max(len(r[1]) for r in rows), 2)

    header = f"{'代码':<8}{'名称':<{name_w + 2}}{col3:>8}{col4:>8}{col5:>12}  {'行业'}"
    lines.append(header)

    for code, name, v1, v2, v3, industry in rows:
        line = f"{code:<8}{name:<{name_w + 2}}{v1:>8}{v2:>8}{v3:>12}  {industry}"
        lines.append(line)

    return '\n'.join(lines)


def _format_stock_ranking_5col(content: str) -> str:
    """5字段股票表格：代码 名称 价格 涨跌幅 行业"""
    row_pattern = re.compile(r'(\d{6})\s+(\S+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+([\u4e00-\u9fff]{2,})')
    rows = row_pattern.findall(content)
    if len(rows) < 2:
        return content

    first_match = row_pattern.search(content)
    raw_before = content[:first_match.start()].strip()
    title = re.split(r'\s*(?:代码|简称|证券代码|证券简称)\s', raw_before)[0].strip()
    title = title.rstrip('：: ')
    if not title:
        title = '股票排名'

    col3 = '收盘价' if '收盘价' in content else '价格'

    lines = [title, '']
    name_w = max(max(len(r[1]) for r in rows), 2)
    ind_w = max(max(len(r[4]) for r in rows), 2)

    header = f"{'代码':<8}{'名称':<{name_w + 2}}{col3:>8}{'涨跌%':>8}  {'行业'}"
    lines.append(header)

    for code, name, price, chg, industry in rows:
        line = f"{code:<8}{name:<{name_w + 2}}{price:>8}{chg:>8}  {industry}"
        lines.append(line)

    return '\n'.join(lines)


def _format_table_content(content: str) -> str:
    """检测并格式化表格类新闻内容，不匹配则原样返回"""
    if '资金流向' in content:
        return _format_capital_flow(content)
    if '调研' in content:
        return _format_institution_research(content)
    # 通用股票排名表格（特大单/净流入/净流出/排名/龙虎榜等）
    return _format_stock_ranking(content)


class CompanyNewsService:

    @staticmethod
    def fetch_company_news(app=None):
        if app is None:
            from flask import current_app
            app = current_app._get_current_object()
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
        all_results = []
        crawler = None
        crawler_ctx = None
        try:
            from crawl4ai import AsyncWebCrawler
            crawler_ctx = AsyncWebCrawler()
            crawler = await crawler_ctx.__aenter__()
        except Exception as e:
            logger.warning(f'[公司新闻] Playwright不可用，Google News降级关闭: {e}')
            crawler_ctx = None

        try:
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
        finally:
            if crawler_ctx:
                try:
                    await crawler_ctx.__aexit__(None, None, None)
                except Exception:
                    pass
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
            from app.services.akshare_client import ak
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

        if not crawler:
            return []
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
        from app.llm.router import FallbackProvider

        provider = llm_router.route('news_classify')
        new_items = []

        # 需要 LLM 处理的条目
        need_llm = []
        for item in results:
            source_id = hashlib.md5(item['url'].encode()).hexdigest()[:16]
            source_name = item['source_name']

            existing = NewsItem.query.filter_by(
                source_id=source_id, source_name=source_name
            ).first()
            if existing:
                continue
            item['_source_id'] = source_id
            needs_ai = provider and source_name != 'eastmoney_stock'
            item['_needs_ai'] = needs_ai
            need_llm.append(item)

        # 本地模型只处理第1条需要AI的，其余走云端
        local_used = False
        for item in need_llm:
            content = item['content']
            if item['_needs_ai']:
                if not local_used:
                    prov = provider
                    local_used = True
                elif isinstance(provider, FallbackProvider):
                    prov = provider.fallback
                else:
                    prov = provider

                sys_prompt = TRANSLATE_PROMPT if item['source_name'] == 'yahoo_finance' else SUMMARY_PROMPT
                max_tok = 500 if item['source_name'] == 'yahoo_finance' else 200
                try:
                    content = prov.chat([
                        {'role': 'system', 'content': sys_prompt},
                        {'role': 'user', 'content': item['content']},
                    ], temperature=0.1, max_tokens=max_tok).strip()
                except Exception as e:
                    logger.error(f'[公司新闻] AI处理失败: {e}')

            news = NewsItem(
                source_id=item['_source_id'],
                source_name=item['source_name'],
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
        from app.services.news_dedup import news_deduplicator
        try:
            items = news_deduplicator.filter_duplicates(items, content_key=lambda t: t[1])
            if not items:
                return

            for company, content in items:
                formatted = _format_table_content(content)
                if formatted != content:
                    msg = f"🏢 [{company}] {formatted.split(chr(10), 1)[0]}\n```\n{chr(10).join(formatted.split(chr(10))[1:])}\n```"
                else:
                    msg = f"🏢 [{company}] {content}"
                NotificationService.send_slack(msg)
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
