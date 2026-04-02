"""华尔街见闻投行观点抓取与分析服务"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

WALLSTREET_NEWS_ENABLED = os.getenv('WALLSTREET_NEWS_ENABLED', 'true').lower() == 'true'
WALLSTREET_NEWS_FETCH_TIMEOUT = int(os.getenv('WALLSTREET_NEWS_FETCH_TIMEOUT', '10'))

LIVES_API = 'https://api-prod.wallstreetcn.com/apiv1/content/lives'
ARTICLES_API = 'https://api-one.wallstcn.com/apiv1/content/information-flow'

ARTICLE_CHANNELS = ['global-channel', 'us-stock-channel']

KEYWORDS = [
    '高盛', '摩根', '花旗', '瑞银', '大摩', '小摩', '摩根大通',
    '美银', '巴克莱', '野村', '瑞信', '汇丰', '德银',
    '目标价', '评级', '上调', '下调',
]

CACHE_DIR = Path('data/wallstreet_news_cache')

USER_AGENT = 'Mozilla/5.0 (compatible; stock-bot/1.0)'


class WallstreetNewsService:
    """华尔街见闻投行观点抓取与分析"""

    # ── 关键词匹配 ──

    @staticmethod
    def _match_keywords(text: str) -> bool:
        return any(kw in text for kw in KEYWORDS)

    # ── 快讯流 ──

    @staticmethod
    def _fetch_lives() -> list[dict]:
        """抓取快讯流（最多2页），过滤24h内的投行相关内容"""
        cutoff = time.time() - 86400
        matched = []
        cursor = None

        for _ in range(2):
            params = {
                'channel': 'global-channel',
                'client': 'pc',
                'limit': 100,
            }
            if cursor:
                params['cursor'] = cursor

            try:
                resp = requests.get(LIVES_API, params=params,
                                    headers={'User-Agent': USER_AGENT}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f'[华尔街见闻] 快讯API请求失败: {e}')
                break

            items = data.get('data', {}).get('items', [])
            if not items:
                break

            for item in items:
                display_time = item.get('display_time', 0)
                if display_time < cutoff:
                    return matched

                content_text = item.get('content_text', '')
                if WallstreetNewsService._match_keywords(content_text):
                    matched.append({
                        'type': '快讯',
                        'title': '',
                        'text': content_text,
                        'time': display_time,
                        'content_hash': hashlib.md5(content_text.encode()).hexdigest()[:16],
                    })

            cursor = data.get('data', {}).get('next_cursor')
            if not cursor:
                break

        return matched

    # ── 文章列表 ──

    @staticmethod
    def _fetch_articles() -> list[dict]:
        """抓取文章列表（全球+美股频道），过滤投行相关内容"""
        matched = []

        for channel in ARTICLE_CHANNELS:
            params = {
                'channel': channel,
                'accept': 'article',
                'limit': 25,
            }
            try:
                resp = requests.get(ARTICLES_API, params=params,
                                    headers={'User-Agent': USER_AGENT}, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f'[华尔街见闻] 文章API请求失败 ({channel}): {e}')
                continue

            items = data.get('data', {}).get('items', [])
            for item in items:
                resource = item.get('resource', {})
                title = resource.get('title', '')
                content_short = resource.get('content_short', '')
                match_text = f"{title} {content_short}"

                if WallstreetNewsService._match_keywords(match_text):
                    uri = resource.get('uri', '')
                    content_hash = hashlib.md5(title.encode()).hexdigest()[:16]
                    matched.append({
                        'type': '文章',
                        'title': title,
                        'text': content_short,
                        'uri': uri,
                        'content_hash': content_hash,
                    })

        return matched

    # ── 全文爬取 ──

    @staticmethod
    def _fetch_full_content(url: str) -> str:
        """crawl4ai 抓取文章全文"""
        try:
            from crawl4ai import AsyncWebCrawler

            async def _fetch():
                async with AsyncWebCrawler() as crawler:
                    result = await asyncio.wait_for(
                        crawler.arun(url=url),
                        timeout=WALLSTREET_NEWS_FETCH_TIMEOUT,
                    )
                    if result and result.markdown:
                        return result.markdown[:3000]
                return ''

            return asyncio.run(_fetch())
        except ImportError:
            logger.warning('[华尔街见闻] crawl4ai 不可用')
            return ''
        except Exception as e:
            logger.warning(f'[华尔街见闻] 全文爬取失败 {url}: {e}')
            return ''

    @staticmethod
    def _enrich_articles(articles: list[dict]):
        """为匹配到的文章爬取全文，原地更新 text 字段"""
        for article in articles:
            uri = article.get('uri', '')
            if not uri:
                continue
            full_text = WallstreetNewsService._fetch_full_content(uri)
            if full_text:
                article['text'] = full_text

    # ── 去重 ──

    @staticmethod
    def _load_pushed_hashes() -> set[str]:
        """加载近3天的已推送内容 hash"""
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
    def _dedup(items: list[dict]) -> list[dict]:
        """按 content_hash 去重（同批次内 + 跨天）"""
        pushed = WallstreetNewsService._load_pushed_hashes()
        seen = set()
        result = []
        for item in items:
            h = item['content_hash']
            if h in pushed or h in seen:
                continue
            seen.add(h)
            result.append(item)
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
            WallstreetNewsService._cleanup_old_cache()
        except Exception as e:
            logger.error(f'[华尔街见闻] 缓存保存失败: {e}')

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
            from app.llm.prompts.wallstreet_news import (
                WALLSTREET_NEWS_SYSTEM_PROMPT, build_wallstreet_news_prompt,
            )

            provider = llm_router.route('wallstreet_news')
            if not provider:
                return ''

            prompt = build_wallstreet_news_prompt(items)
            response = provider.chat(
                [
                    {'role': 'system', 'content': WALLSTREET_NEWS_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.strip()
        except Exception as e:
            logger.error(f'[华尔街见闻] LLM 分析失败: {e}')
            return ''

    # ── 输出 ──

    @staticmethod
    def _format_slack_message(analysis: str, live_count: int, article_count: int) -> str:
        today_str = date.today().isoformat()
        return (
            f'🏦 投行观点日报 ({today_str})\n\n'
            f'━━━━━━━━━━━━━━━━\n'
            f'{analysis}\n'
            f'━━━━━━━━━━━━━━━━\n\n'
            f'来源：华尔街见闻 | 快讯 {live_count} 条，文章 {article_count} 篇'
        )

    # ── 主流程 ──

    @staticmethod
    def run_daily() -> dict:
        """每日投行观点抓取主流程"""
        if not WALLSTREET_NEWS_ENABLED:
            logger.info('[华尔街见闻] 功能未启用')
            return {'enabled': False}

        logger.info('[华尔街见闻] 开始抓取')

        lives = WallstreetNewsService._fetch_lives()
        articles = WallstreetNewsService._fetch_articles()

        logger.info(f'[华尔街见闻] 关键词匹配: 快讯 {len(lives)} 条, 文章 {len(articles)} 篇')

        all_items = lives + articles
        all_items = WallstreetNewsService._dedup(all_items)

        if not all_items:
            logger.info('[华尔街见闻] 无匹配内容')
            return {'lives': 0, 'articles': 0, 'matched': 0}

        live_count = sum(1 for i in all_items if i['type'] == '快讯')
        article_count = sum(1 for i in all_items if i['type'] == '文章')

        article_items = [i for i in all_items if i['type'] == '文章']
        WallstreetNewsService._enrich_articles(article_items)

        analysis = WallstreetNewsService._analyze(all_items)

        WallstreetNewsService._save_cache(all_items, analysis)

        if analysis:
            try:
                from app.services.notification import NotificationService
                from app.config.notification_config import CHANNEL_RESEARCH
                message = WallstreetNewsService._format_slack_message(
                    analysis, live_count, article_count)
                NotificationService.send_slack(message, CHANNEL_RESEARCH)
                logger.info('[华尔街见闻] Slack 推送成功')
            except Exception as e:
                logger.error(f'[华尔街见闻] Slack 推送失败: {e}')

        logger.info(f'[华尔街见闻] 完成: 快讯 {live_count}, 文章 {article_count}')
        return {
            'lives': live_count,
            'articles': article_count,
            'matched': len(all_items),
        }
