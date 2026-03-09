"""盯盘实时分析策略 — 开盘时段每15分钟自动分析"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchRealtimeStrategy(Strategy):
    name = "watch_realtime"
    description = "盯盘实时分析（开盘时段每15分钟）"
    schedule = "*/15 9-23 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.trading_calendar import TradingCalendarService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        from app.services.watch_analysis_service import WatchAnalysisService
        try:
            WatchAnalysisService.analyze_stocks('realtime', force=True)
            logger.info('[盯盘实时] 分析完成')
        except Exception as e:
            logger.error(f'[盯盘实时] 分析失败: {e}')

        return []
