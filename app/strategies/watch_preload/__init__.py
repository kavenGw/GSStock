"""盯盘数据预取策略 — A股每分钟，美股/港股每3分钟（差异化提频）"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

BACKOFF_CAP = 8
NON_A_REFRESH_EVERY = 3   # 美股/港股每 3 tick(≈3min)刷新


class WatchPreloadStrategy(Strategy):
    name = "watch_preload"
    description = "盯盘数据预取（A股1min/美港股3min，趋势分档）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _tick_count = 0
    _backoff = {}

    def _should_skip(self, market: str) -> bool:
        state = self._backoff.get(market)
        if state and state['remaining'] > 0:
            state['remaining'] -= 1
            return True
        return False

    def _record_result(self, market: str, ok: bool):
        if ok:
            if self._backoff.pop(market, None):
                logger.info(f'[盯盘预取] {market} 取价恢复，退避清零')
            return
        prev = self._backoff.get(market)
        skip = min(prev['skip'] * 2, BACKOFF_CAP) if prev else 1
        self._backoff[market] = {'skip': skip, 'remaining': skip}
        logger.warning(f'[盯盘预取] {market} 取价失败，退避 {skip} tick')

    @staticmethod
    def _prices_ok(prices: dict, codes: list[str]) -> bool:
        if not codes:
            return True
        valid = sum(1 for c in codes if (prices.get(c) or {}).get('current_price'))
        return valid >= len(codes) * 0.5

    @staticmethod
    def _index_codes_for_markets(open_markets: set) -> dict:
        from app.config.stock_codes import MARKET_INDICES
        out = {}
        for mkt, defs in MARKET_INDICES.items():
            if mkt in open_markets:
                out[mkt] = [i['code'] for i in defs]
        return out

    @staticmethod
    def _should_refresh_market(market: str, tick: int, non_a_every: int = NON_A_REFRESH_EVERY) -> bool:
        if market == 'A':
            return True
        return tick % non_a_every == 0

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

        # 每次按市场预取价格，失败市场指数退避（yfinance 限流不连累腾讯源）
        for market, m_codes in market_codes.items():
            if not self._should_refresh_market(market, self._tick_count):
                continue
            if self._should_skip(market):
                continue
            try:
                prices = unified_stock_data_service.get_realtime_prices(m_codes, force_refresh=True)
                ok = self._prices_ok(prices, m_codes)
                if ok:
                    logger.debug(f'[盯盘预取] {market} 价格预取完成: {len(m_codes)}只')
            except Exception as e:
                logger.error(f'[盯盘预取] {market} 价格预取失败: {e}')
                ok = False
            self._record_result(market, ok)

        # 每次预取A股分时数据（缓存TTL=1分钟，保证客户端随时可获取完整分时）
        a_codes = market_codes.get('A', [])
        if a_codes:
            try:
                unified_stock_data_service.get_intraday_data(a_codes)
                logger.debug(f'[盯盘预取] A股分时预取完成: {len(a_codes)}只')
            except Exception as e:
                logger.error(f'[盯盘预取] A股分时预取失败: {e}')

        # 指数条预热（价格 + 分时），独立于个股 backoff
        index_codes_by_market = self._index_codes_for_markets(open_markets)
        for mkt, idx_codes in index_codes_by_market.items():
            if not idx_codes:
                continue
            try:
                if mkt == 'A':
                    unified_stock_data_service.get_a_share_index_quotes(
                        idx_codes, force_refresh=True)
                else:
                    unified_stock_data_service.get_realtime_prices(
                        idx_codes, force_refresh=True)
                unified_stock_data_service.get_intraday_data(idx_codes)
                logger.debug(f'[盯盘预取] {mkt} 指数预热完成: {len(idx_codes)}只')
            except Exception as e:
                logger.error(f'[盯盘预取] {mkt} 指数预热失败: {e}')

        # 走势预取按市场分档：A股每 trend_interval tick，非A每 trend_interval*3 tick
        trend_interval = self._config.get('trend_interval', 15)
        a_codes_trend = market_codes.get('A', [])
        non_a_trend = [c for m, l in market_codes.items() if m != 'A' for c in l]
        if a_codes_trend and self._tick_count % trend_interval == 0:
            try:
                unified_stock_data_service.get_trend_data(a_codes_trend, days=7)
                unified_stock_data_service.get_trend_data(a_codes_trend, days=30)
                logger.info(f'[盯盘预取] A股走势预取完成: {len(a_codes_trend)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] A股走势预取失败: {e}')
        if non_a_trend and self._tick_count % (trend_interval * 3) == 0:
            try:
                unified_stock_data_service.get_trend_data(non_a_trend, days=7)
                unified_stock_data_service.get_trend_data(non_a_trend, days=30)
                logger.info(f'[盯盘预取] 非A走势预取完成: {len(non_a_trend)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] 非A走势预取失败: {e}')

        self._tick_count += 1
        return []
