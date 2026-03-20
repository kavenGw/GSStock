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

        # 推送前先更新所有 A 股信号缓存（每天一次）
        self._refresh_signal_cache()

        try:
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[每日简报] 推送成功')
            else:
                logger.warning('[每日简报] 推送失败或未配置')
        except Exception as e:
            logger.error(f'[每日简报] 推送失败: {e}')

        return []

    @staticmethod
    def _refresh_signal_cache():
        """更新所有关注 A 股的信号缓存"""
        from app.services.notification import NotificationService
        from app.services.signal_cache import SignalCacheService
        from app.services.position import PositionService
        from app.utils.market_identifier import MarketIdentifier

        try:
            codes, name_map = NotificationService._get_all_watched_codes()
            a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
            if not a_codes:
                return

            from datetime import date
            trend_data = PositionService.get_trend_data(a_codes, date.today(), days=365)
            if trend_data and trend_data.get('stocks'):
                SignalCacheService.update_signals_from_trend_data(trend_data, name_map)
                logger.info(f'[每日简报] 信号缓存更新完成: {len(a_codes)}只A股')
        except Exception as e:
            logger.error(f'[每日简报] 信号缓存更新失败: {e}')
