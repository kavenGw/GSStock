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

        # 更新盯盘股票的信号缓存（A股）
        self._refresh_watch_signals(codes)

        from app.services.watch_analysis_service import WatchAnalysisService
        try:
            results = WatchAnalysisService.analyze_stocks('realtime', force=True)
            logger.info('[盯盘实时] 分析完成')

            from app.services.notification import NotificationService
            NotificationService.push_realtime_analysis(results)
        except Exception as e:
            logger.error(f'[盯盘实时] 分析失败: {e}')

        return []

    @staticmethod
    def _refresh_watch_signals(codes: list[str]):
        """更新盯盘 A 股的信号缓存"""
        from app.services.signal_cache import SignalCacheService
        from app.services.position import PositionService
        from app.models.stock import Stock
        from app.utils.market_identifier import MarketIdentifier

        try:
            a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
            if not a_codes:
                return

            stocks = Stock.query.filter(Stock.stock_code.in_(a_codes)).all()
            name_map = {s.stock_code: s.stock_name for s in stocks}

            trend_data = PositionService.get_trend_data(a_codes, days=365)
            if trend_data and trend_data.get('stocks'):
                SignalCacheService.update_signals_from_trend_data(trend_data, name_map)
                logger.info(f'[盯盘实时] 信号缓存更新: {len(a_codes)}只')
        except Exception as e:
            logger.error(f'[盯盘实时] 信号缓存更新失败: {e}')
