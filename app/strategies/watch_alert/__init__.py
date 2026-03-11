"""盯盘推送告警策略 — 后端驱动价格获取 + 即时告警检测"""
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
        from app.config.stock_codes import BENCHMARK_CODES
        from app.utils.market_identifier import MarketIdentifier

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()

        bench_codes = [b['code'] for b in BENCHMARK_CODES]
        all_codes = list(set(codes + bench_codes))

        # A股批量获取快（tencent/sina 单次HTTP），强制刷新
        # 非A股（期货/美股）逐个调用yfinance慢，用正常缓存TTL
        a_codes = [c for c in all_codes if MarketIdentifier.is_a_share(c)]
        other_codes = [c for c in all_codes if c not in a_codes]

        prices = {}
        if a_codes:
            prices.update(data_service.get_realtime_prices(a_codes, force_refresh=True))
        if other_codes:
            prices.update(data_service.get_realtime_prices(other_codes))

        # 只对盯盘股票做告警检测
        watch_prices = {c: prices[c] for c in codes if c in prices}
        items = WatchList.query.filter(WatchList.stock_code.in_(codes)).all()
        name_map = {w.stock_code: w.stock_name for w in items}

        service = WatchAlertService()
        signals = service.check_alerts(watch_prices, name_map)

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals
