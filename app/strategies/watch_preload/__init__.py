"""盯盘数据预取策略 — 每分钟预取价格，每15分钟预取走势"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchPreloadStrategy(Strategy):
    name = "watch_preload"
    description = "盯盘数据预取（每分钟价格，每15分钟走势）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _tick_count = 0

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.trading_calendar import TradingCalendarService
        from app.services.unified_stock_data import unified_stock_data_service
        from app.utils.market_identifier import MarketIdentifier

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        open_markets = {m for m in markets if TradingCalendarService.is_market_open(m)}
        if not open_markets:
            return []

        market_codes = {}
        for code in codes:
            market = MarketIdentifier.identify(code) or 'A'
            if market in open_markets:
                market_codes.setdefault(market, []).append(code)

        active_codes = [c for codes_list in market_codes.values() for c in codes_list]
        if not active_codes:
            return []

        # 每次预取价格
        try:
            unified_stock_data_service.get_realtime_prices(active_codes, force_refresh=True)
            logger.debug(f'[盯盘预取] 价格预取完成: {len(active_codes)}只')
        except Exception as e:
            logger.error(f'[盯盘预取] 价格预取失败: {e}')

        # 每 trend_interval 次预取走势
        trend_interval = self._config.get('trend_interval', 15)
        if self._tick_count % trend_interval == 0:
            try:
                unified_stock_data_service.get_trend_data(active_codes, days=7)
                unified_stock_data_service.get_trend_data(active_codes, days=30)
                logger.info(f'[盯盘预取] 走势预取完成: {len(active_codes)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] 走势预取失败: {e}')

        self._tick_count += 1
        return []
