import json
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class NewsMonitorStrategy(Strategy):
    name = 'news_monitor'
    description = '新闻监控：定时抓取快讯并生成AI简报'
    schedule = ''
    needs_llm = True
    enabled = True

    def __init__(self):
        super().__init__()
        self._polling_cursor = None

    def scan(self) -> list[Signal]:
        from app.services.news_service import NewsService
        from app.services.notification import NotificationService
        from app.llm.router import llm_router
        from app.llm.prompts.news_briefing import SYSTEM_PROMPT, build_news_briefing_prompt

        if not self._polling_cursor:
            self._polling_cursor = NewsService.get_polling_cursor()

        raw_items = NewsService.fetch_latest_news(cursor=self._polling_cursor)
        if not raw_items:
            return []

        new_items = NewsService.save_news_items(raw_items)
        if not new_items:
            return []

        latest_id = max(item.source_id for item in new_items)
        self._polling_cursor = str(latest_id)

        logger.info(f'[新闻监控] 新增 {len(new_items)} 条快讯')

        provider = llm_router.route('news_briefing')
        if not provider:
            return []

        items_for_llm = [{
            'source_id': str(n.source_id),
            'display_time': n.display_time.strftime('%H:%M') if n.display_time else '',
            'content': n.content,
        } for n in new_items]

        try:
            response = provider.chat([
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': build_news_briefing_prompt(items_for_llm)},
            ], temperature=0.3, max_tokens=1000)

            content = response
            if '```' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                content = content[start:end]
            result = json.loads(content)

            categories = result.get('categories', {})
            if categories:
                NewsService.update_categories(categories)

            briefing_data = result.get('briefing', {})
            summary = result.get('summary', '')
            briefing_parts = []
            if summary:
                briefing_parts.append(f"📌 {summary}")
            if briefing_data.get('stock'):
                briefing_parts.append(f"📊 股票: {briefing_data['stock']}")
            if briefing_data.get('metal'):
                briefing_parts.append(f"🤘 商品: {briefing_data['metal']}")
            if briefing_data.get('ai'):
                briefing_parts.append(f"🤖 AI: {briefing_data['ai']}")

            briefing_text = "\n".join(briefing_parts)

            if briefing_parts:
                times = [n.display_time for n in new_items if n.display_time]
                NewsService.save_briefing(
                    content=briefing_text,
                    news_count=len(new_items),
                    period_start=min(times) if times else None,
                    period_end=max(times) if times else None,
                )

                NotificationService.send_slack(f"📰 *新闻简报* ({len(new_items)}条快讯)\n{briefing_text}")

        except Exception as e:
            logger.error(f'[新闻监控] AI简报生成失败: {e}')

        return []
