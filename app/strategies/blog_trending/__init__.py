"""博客监控 + GitHub Trending 独立推送策略"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class BlogTrendingStrategy(Strategy):
    name = "blog_trending"
    description = "博客监控 + GitHub Trending 独立推送"
    schedule = "0 5 * * *"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_AI_TOOL

        texts = []

        blog_texts = NotificationService.format_blog_updates()
        texts.extend(blog_texts)

        trending_texts = NotificationService.format_github_trending_updates()
        texts.extend(trending_texts)

        if texts:
            msg = '\n\n'.join(texts)
            if NotificationService.send_slack(msg, CHANNEL_AI_TOOL):
                logger.info(f'[博客/Trending] 推送成功: {len(texts)} 条')
            else:
                logger.warning('[博客/Trending] 推送失败')
        else:
            logger.info('[博客/Trending] 无新内容')

        return []
