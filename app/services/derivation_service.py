"""衍生搜索服务：crawl4ai 抓取 + GLM 整理"""
import asyncio
import json
import logging
import re

from app import db
from app.models.news import NewsItem, NewsDerivation
from app.config.news_config import (
    MAX_DERIVATION_PER_POLL, DERIVATION_URL_TIMEOUT, DERIVATION_TOTAL_TIMEOUT
)

logger = logging.getLogger(__name__)

SEARCH_SYSTEM_PROMPT = """根据这条新闻，生成一组搜索关键词用于查找相关报道。
返回JSON: {"zh": "中文搜索词", "en": "English search terms"}
只返回JSON。"""

SUMMARY_LIGHT_PROMPT = """基于原始新闻和相关文章，写一段扩展摘要（100-200字），补充背景信息。
直接返回摘要文本。"""

SUMMARY_DEEP_PROMPT = """基于原始新闻和相关文章，写一份结构化专题报告（300-500字），格式：
**背景**：（事件背景）
**影响**：（市场/行业影响）
**展望**：（未来趋势）
直接返回报告文本。"""


class DerivationService:

    @staticmethod
    def process_batch(items: list[NewsItem]):
        """批量处理衍生搜索（后台线程调用）"""
        for item in items[:MAX_DERIVATION_PER_POLL]:
            existing = NewsDerivation.query.filter_by(news_item_id=item.id).first()
            if existing:
                continue
            try:
                DerivationService._derive_single(item)
            except Exception as e:
                logger.error(f'衍生搜索失败 [{item.id}]: {e}')

    @staticmethod
    def _derive_single(item: NewsItem):
        """单条新闻衍生搜索"""
        from app.llm.router import llm_router

        # Step 1: 生成搜索关键词
        provider = llm_router.route('news_classify')
        if not provider:
            return

        try:
            resp = provider.chat([
                {'role': 'system', 'content': SEARCH_SYSTEM_PROMPT},
                {'role': 'user', 'content': item.content},
            ], temperature=0.1, max_tokens=100)
            search_terms = json.loads(resp.strip())
            search_query = search_terms.get('zh', item.content[:50])
        except Exception:
            search_query = item.content[:50]

        # Step 2: crawl4ai 搜索
        max_urls = 5 if item.importance >= 5 else 2
        articles = DerivationService._crawl_search(search_query, max_urls)

        # Step 3: GLM 整合
        is_deep = item.importance >= 5
        task_type = 'news_derivation_deep' if is_deep else 'news_derivation'
        prompt_template = SUMMARY_DEEP_PROMPT if is_deep else SUMMARY_LIGHT_PROMPT
        provider = llm_router.route(task_type)

        source_urls = [a['url'] for a in articles]
        article_text = "\n\n".join(
            f"[来源: {a['url']}]\n{a['content'][:1000]}" for a in articles
        )

        summary = None
        if provider and article_text:
            try:
                user_prompt = f"原始新闻：{item.content}\n\n相关文章：\n{article_text}"
                summary = provider.chat([
                    {'role': 'system', 'content': prompt_template},
                    {'role': 'user', 'content': user_prompt},
                ], temperature=0.3, max_tokens=800).strip()
            except Exception as e:
                logger.error(f'GLM衍生整合失败: {e}')

        if not summary and articles:
            summary = articles[0]['content'][:500]

        if not summary:
            return

        derivation = NewsDerivation(
            news_item_id=item.id,
            search_query=search_query,
            sources=source_urls,
            summary=summary,
            importance=item.importance,
        )
        db.session.add(derivation)
        db.session.commit()
        logger.info(f'[衍生] 完成 news_item={item.id}, sources={len(source_urls)}')

    @staticmethod
    def _crawl_search(query: str, max_urls: int) -> list[dict]:
        """用 crawl4ai 搜索并抓取相关文章"""
        try:
            search_url = f"https://www.google.com/search?q={query}&tbm=nws"
            results = asyncio.run(DerivationService._async_crawl(search_url, max_urls))
            return results
        except Exception as e:
            logger.error(f'crawl4ai搜索失败: {e}')
            return []

    @staticmethod
    async def _async_crawl(search_url: str, max_urls: int) -> list[dict]:
        """异步爬取"""
        from crawl4ai import AsyncWebCrawler

        articles = []
        try:
            async with AsyncWebCrawler() as crawler:
                search_result = await crawler.arun(
                    url=search_url,
                    timeout=DERIVATION_URL_TIMEOUT,
                )
                urls = DerivationService._extract_urls(search_result.markdown, max_urls)

                for url in urls:
                    try:
                        result = await crawler.arun(
                            url=url,
                            timeout=DERIVATION_URL_TIMEOUT,
                        )
                        if result.markdown:
                            articles.append({
                                'url': url,
                                'content': result.markdown[:2000],
                            })
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f'async crawl失败: {e}')
        return articles

    @staticmethod
    def _extract_urls(markdown: str, max_count: int) -> list[str]:
        """从搜索结果 markdown 中提取新闻链接"""
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
