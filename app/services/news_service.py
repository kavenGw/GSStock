import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app import db
from app.models.news import NewsItem
from app.services.news_sources import ALL_SOURCES

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4)


class NewsService:

    @staticmethod
    def fetch_all_sources() -> list[dict]:
        """并行获取所有新闻源"""
        all_items = []
        futures = {_executor.submit(src.fetch_latest): src.name for src in ALL_SOURCES}
        for future in as_completed(futures, timeout=15):
            source_name = futures[future]
            try:
                items = future.result()
                all_items.extend(items)
                logger.info(f'[新闻] {source_name} 获取 {len(items)} 条')
            except Exception as e:
                logger.error(f'[新闻] {source_name} 获取失败: {e}')
        return all_items

    @staticmethod
    def save_news_items(items: list[dict]) -> list[NewsItem]:
        """批量存储，按 (source_id, source_name) 去重"""
        new_items = []
        for item in items:
            source_id = item.get('source_id')
            source_name = item.get('source_name', 'unknown')
            if not source_id:
                continue
            existing = NewsItem.query.filter_by(
                source_id=str(source_id), source_name=source_name
            ).first()
            if existing:
                continue
            display_time = item.get('display_time', 0)
            if isinstance(display_time, (int, float)):
                display_time = datetime.fromtimestamp(display_time)
            news = NewsItem(
                source_id=str(source_id),
                source_name=source_name,
                content=item.get('content', ''),
                display_time=display_time,
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
            query = query.filter(NewsItem.is_interest == True)
        if before_id:
            query = query.filter(NewsItem.id < before_id)
        items = query.order_by(NewsItem.display_time.desc()).limit(limit).all()
        return [NewsService._item_to_dict(n) for n in items]

    @staticmethod
    def _item_to_dict(n: NewsItem) -> dict:
        return {
            'id': n.id,
            'source_id': n.source_id,
            'source_name': n.source_name or 'wallstreetcn',
            'content': n.content,
            'display_time': n.display_time.strftime('%H:%M') if n.display_time else '',
            'display_date': n.display_time.strftime('%Y-%m-%d') if n.display_time else '',
            'score': n.score,
            'category': n.category or 'other',
            'importance': n.importance,
            'is_interest': n.is_interest,
            'matched_keywords': n.matched_keywords or '',
        }

    @staticmethod
    def summarize_items(item_ids: list[int]) -> str | None:
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
        """拉取所有源最新快讯并返回新增条目"""
        raw_items = NewsService.fetch_all_sources()
        if not raw_items:
            return [], 0

        new_items = NewsService.save_news_items(raw_items)
        if not new_items:
            return [], 0

        # 异步执行分类流水线（不阻塞返回）
        from app.services.interest_pipeline import InterestPipeline
        item_ids = [n.id for n in new_items]
        _executor.submit(InterestPipeline.process_new_items, item_ids)

        try:
            from app.services.notification import NotificationService
            titles = [n.content[:50] for n in new_items[:3]]
            msg = f"📰 新增 {len(new_items)} 条快讯\n" + "\n".join(f"• {t}" for t in titles)
            if len(new_items) > 3:
                msg += f"\n...等{len(new_items) - 3}条"
            NotificationService.send_slack(msg)
        except Exception:
            pass

        items_data = [NewsService._item_to_dict(n) for n in new_items]
        return items_data, len(new_items)
