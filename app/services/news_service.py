import logging
import requests
from datetime import datetime

from app import db
from app.models.news import NewsItem
from app.config.news_config import WALLSTREETCN_API, WALLSTREETCN_CHANNEL

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


class NewsService:

    @staticmethod
    def fetch_latest_news(cursor=None) -> list[dict]:
        """调用华尔街见闻API获取最新快讯"""
        params = {
            'channel': WALLSTREETCN_CHANNEL,
            'client': 'pc',
            'limit': 20,
        }
        if cursor:
            params['cursor'] = cursor
        try:
            resp = requests.get(WALLSTREETCN_API, params=params, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 20000:
                logger.warning(f'华尔街见闻API异常: {data.get("message")}')
                return []
            return data.get('data', {}).get('items', [])
        except Exception as e:
            logger.error(f'获取新闻失败: {e}')
            return []

    @staticmethod
    def save_news_items(items: list[dict]) -> list[NewsItem]:
        """批量存储快讯，返回新增条目"""
        new_items = []
        for item in items:
            source_id = item.get('id')
            if not source_id:
                continue
            existing = NewsItem.query.filter_by(source_id=source_id).first()
            if existing:
                continue
            news = NewsItem(
                source_id=source_id,
                content=item.get('content_text', ''),
                display_time=datetime.fromtimestamp(item.get('display_time', 0)),
                score=item.get('score', 1),
            )
            db.session.add(news)
            new_items.append(news)
        if new_items:
            db.session.commit()
        return new_items

    @staticmethod
    def get_news_items(tab='all', limit=30, before_id=None) -> list[dict]:
        """分页查询快讯"""
        query = NewsItem.query
        if tab == 'interest':
            query = query.filter(NewsItem.category.in_(['stock', 'metal', 'ai']))
        if before_id:
            query = query.filter(NewsItem.id < before_id)
        items = query.order_by(NewsItem.display_time.desc()).limit(limit).all()
        return [{
            'id': n.id,
            'source_id': n.source_id,
            'content': n.content,
            'display_time': n.display_time.strftime('%H:%M') if n.display_time else '',
            'display_date': n.display_time.strftime('%Y-%m-%d') if n.display_time else '',
            'score': n.score,
            'category': n.category or 'other',
        } for n in items]

    @staticmethod
    def summarize_items(item_ids: list[int]) -> str | None:
        """使用LLM整理多条快讯为一段摘要"""
        items = NewsItem.query.filter(NewsItem.id.in_(item_ids)).all()
        if not items:
            return None

        from app.llm.router import llm_router
        from app.llm.prompts.news_briefing import SUMMARIZE_SYSTEM_PROMPT, build_summarize_prompt

        provider = llm_router.route('news_briefing')
        if not provider:
            return None

        items_data = [{'content': n.content} for n in items]
        try:
            response = provider.chat([
                {'role': 'system', 'content': SUMMARIZE_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_summarize_prompt(items_data)},
            ], temperature=0.3, max_tokens=200)
            return response.strip()
        except Exception as e:
            logger.error(f'AI摘要失败: {e}')
            return None

    @staticmethod
    def poll_news() -> tuple[list[dict], int]:
        """拉取最新快讯并返回新增条目"""
        raw_items = NewsService.fetch_latest_news()
        if not raw_items:
            return [], 0

        new_items = NewsService.save_news_items(raw_items)
        if not new_items:
            return [], 0

        try:
            from app.services.notification import NotificationService
            titles = [n.content[:50] for n in new_items[:3]]
            msg = f"📰 新增 {len(new_items)} 条快讯\n" + "\n".join(f"• {t}" for t in titles)
            if len(new_items) > 3:
                msg += f"\n...等{len(new_items) - 3}条"
            NotificationService.send_slack(msg)
        except Exception:
            pass

        items_data = [{
            'id': n.id,
            'source_id': n.source_id,
            'content': n.content,
            'display_time': n.display_time.strftime('%H:%M') if n.display_time else '',
            'display_date': n.display_time.strftime('%Y-%m-%d') if n.display_time else '',
            'score': n.score,
            'category': n.category or 'other',
        } for n in new_items]

        return items_data, len(new_items)
