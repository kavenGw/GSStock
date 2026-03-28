"""技术博客监控服务 — 检测新文章并生成中文摘要"""
import asyncio
import json
import logging
import os
import re

import feedparser
import requests

from app.config.blog_monitor import BLOG_SOURCES, BLOG_MONITOR_ENABLED

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
FETCH_TIMEOUT = 15


class BlogMonitorService:

    @staticmethod
    def _get_pushed(key: str) -> set[str]:
        """读取已推送 URL 集合"""
        filepath = os.path.join(DATA_DIR, f'blog_monitor_{key}_pushed.json')
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f'[博客监控] 读取 {key} 已推送记录失败: {e}')
        return set()

    @staticmethod
    def _mark_pushed(key: str, urls: list[str]):
        """追加写入已推送记录"""
        filepath = os.path.join(DATA_DIR, f'blog_monitor_{key}_pushed.json')
        existing = BlogMonitorService._get_pushed(key)
        existing.update(urls)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(list(existing), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f'[博客监控] 写入 {key} 已推送记录失败: {e}')

    @staticmethod
    def _fetch_rss(source: dict) -> list[dict]:
        """feedparser 解析 RSS，返回文章列表"""
        try:
            feed = feedparser.parse(source['feed_url'])
            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    'title': entry.get('title', ''),
                    'url': entry.get('link', ''),
                    'summary': entry.get('summary', '')[:200] if entry.get('summary') else '',
                })
            return articles
        except Exception as e:
            logger.warning(f"[博客监控] RSS 获取失败 {source['name']}: {e}")
            return []

    @staticmethod
    def _fetch_html_anthropic(source: dict) -> list[dict]:
        """requests + 正则解析 Anthropic Engineering 页面"""
        try:
            resp = requests.get(
                source['list_url'],
                headers={'User-Agent': 'Mozilla/5.0 (compatible; stock-bot/1.0)'},
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            html = resp.text

            articles = []
            pattern = r'href="(/engineering/[a-z0-9-]+)"[^>]*>([^<]+)<'
            seen_urls = set()
            for match in re.finditer(pattern, html):
                path, title = match.group(1), match.group(2).strip()
                if not title or path in seen_urls:
                    continue
                seen_urls.add(path)
                url = source['base_url'] + path
                articles.append({
                    'title': title,
                    'url': url,
                    'summary': '',
                })

            return articles
        except Exception as e:
            logger.warning(f"[博客监控] HTML 获取失败 {source['name']}: {e}")
            return []

    @staticmethod
    def _fetch_full_content(url: str) -> str:
        """crawl4ai 抓取文章全文"""
        try:
            from crawl4ai import AsyncWebCrawler

            async def _fetch():
                async with AsyncWebCrawler() as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url),
                        timeout=FETCH_TIMEOUT,
                    )
                    if result and result.markdown:
                        return result.markdown[:3000]
                return ''

            return asyncio.run(_fetch())
        except ImportError:
            logger.warning('[博客监控] crawl4ai 不可用')
            return ''
        except Exception as e:
            logger.warning(f'[博客监控] 全文抓取失败 {url}: {e}')
            return ''

    @staticmethod
    def _summarize(title: str, content: str) -> str:
        """GLM Flash 生成中文摘要"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.blog_summary import (
                BLOG_SUMMARY_SYSTEM_PROMPT, build_blog_summary_prompt,
            )

            provider = llm_router.route('blog_summary')
            if not provider:
                return ''

            prompt = build_blog_summary_prompt(title, content)
            summary = provider.chat(
                [
                    {'role': 'system', 'content': BLOG_SUMMARY_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f'[博客监控] LLM 摘要失败: {e}')
            return ''

    @staticmethod
    def check_all_blogs() -> list[dict]:
        """遍历所有博客源，返回新文章列表（含摘要）"""
        if not BLOG_MONITOR_ENABLED:
            return []

        all_new = []
        for source in BLOG_SOURCES:
            if not source.get('enabled'):
                continue

            key = source['key']
            source_type = source['type']

            if source_type == 'rss':
                articles = BlogMonitorService._fetch_rss(source)
            elif source_type == 'html':
                articles = BlogMonitorService._fetch_html_anthropic(source)
            else:
                logger.warning(f"[博客监控] 未知类型 {source_type}")
                continue

            if not articles:
                continue

            pushed = BlogMonitorService._get_pushed(key)
            article_urls = [a['url'] for a in articles]

            if not pushed:
                logger.info(f"[博客监控] {source['name']} 首次运行，记录 {len(article_urls)} 篇文章")
                BlogMonitorService._mark_pushed(key, article_urls)
                continue

            new_articles = [a for a in articles if a['url'] not in pushed]
            if not new_articles:
                continue

            logger.info(f"[博客监控] {source['name']} 发现 {len(new_articles)} 篇新文章")

            for article in new_articles:
                content = BlogMonitorService._fetch_full_content(article['url'])
                if content:
                    summary = BlogMonitorService._summarize(article['title'], content)
                    article['summary'] = summary or article.get('summary', '')
                all_new.append({
                    'source_name': source['name'],
                    'title': article['title'],
                    'url': article['url'],
                    'summary': article.get('summary', ''),
                })

            BlogMonitorService._mark_pushed(key, [a['url'] for a in new_articles])

        return all_new
