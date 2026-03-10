"""盯盘推送告警策略 — 每分钟检测价格信号"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchAlertStrategy(Strategy):
    name = "watch_alert"
    description = "盯盘告警推送（每分钟检测）"
    schedule = "interval_minutes:1"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.models.watch_list import WatchList
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService
        from app.services.watch_alert_service import WatchAlertService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()
        prices = data_service.get_realtime_prices(codes)

        items = WatchList.query.filter(WatchList.stock_code.in_(codes)).all()
        name_map = {w.stock_code: w.stock_name for w in items}

        service = WatchAlertService()
        signals = service.check_alerts(prices, name_map)

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals
