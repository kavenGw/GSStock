"""华尔街见闻投行观点推送策略"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WallstreetNewsStrategy(Strategy):
    name = "wallstreet_news"
    description = "华尔街见闻投行观点日报"
    schedule = "0 20 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.wallstreet_news_service import (
            WALLSTREET_NEWS_ENABLED,
            WallstreetNewsService,
        )

        if not WALLSTREET_NEWS_ENABLED:
            return []

        try:
            results = WallstreetNewsService.run_daily()
            matched = results.get('matched', 0)
            logger.info(f'[华尔街见闻策略] 完成: {matched} 条匹配内容')
        except Exception as e:
            logger.error(f'[华尔街见闻策略] 执行失败: {e}')

        return []
