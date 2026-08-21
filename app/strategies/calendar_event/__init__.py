"""事件日历采集策略 — 每日 7:30 物化盯盘股与宏观事件"""
import logging

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class CalendarEventStrategy(Strategy):
    name = "calendar_event"
    description = "事件日历采集（财报/除权/宏观）"
    schedule = "30 7 * * *"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.calendar_event import CalendarEventService

        try:
            stats = CalendarEventService.refresh_all()
            if stats['errors']:
                logger.warning(f'[事件日历] 部分采集失败: {stats["errors"]}')
            if stats.get('incomplete'):
                logger.warning(
                    f'[事件日历] 采集不完整（本轮已跳过对应清理）: {stats["incomplete"]}')
        except Exception as e:
            logger.error(f'[事件日历] 刷新失败: {e}')

        return []
