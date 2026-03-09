"""每日简报策略 — 汇总市场数据生成日报"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class DailyBriefingStrategy(Strategy):
    name = "daily_briefing"
    description = "每日简报（市场概况+持仓+预警）"
    schedule = "30 8 * * 1-5"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService

        try:
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[每日简报] 推送成功')
            else:
                logger.warning('[每日简报] 推送失败或未配置')
        except Exception as e:
            logger.error(f'[每日简报] 推送失败: {e}')

        return []
