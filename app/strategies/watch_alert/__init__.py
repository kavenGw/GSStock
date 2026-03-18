"""盯盘告警策略 — 价格获取 + AI参数加载 + TD节流 + 7种检测"""
import logging
from datetime import datetime, time

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

TD_CALC_INTERVAL = 15 * 60
PARAMS_RETRY_INTERVAL = 30 * 60


class WatchAlertStrategy(Strategy):
    name = "watch_alert"
    description = "盯盘告警推送（每分钟检测）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _last_td_calc = None
    _td_cache = {}
    _alert_params_cache = {}
    _last_params_retry = None

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

        a_codes = [c for c in all_codes if MarketIdentifier.is_a_share(c)]
        other_codes = [c for c in all_codes if c not in a_codes]

        prices = {}
        if a_codes:
            prices.update(data_service.get_realtime_prices(a_codes, force_refresh=True))
        if other_codes:
            prices.update(data_service.get_realtime_prices(other_codes))

        watch_prices = {c: prices[c] for c in codes if c in prices}
        items = WatchList.query.filter(WatchList.stock_code.in_(codes)).all()
        name_map = {w.stock_code: w.stock_name for w in items}

        alert_params_map = self._load_alert_params(codes)
        td_results = self._calc_td_if_due(codes, data_service)
        trading_minutes = self._calc_trading_minutes(codes, items, TradingCalendarService)

        service = WatchAlertService()
        signals = service.check_alerts(
            watch_prices, name_map,
            alert_params_map=alert_params_map,
            td_results=td_results,
            trading_minutes=trading_minutes,
        )

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals

    def _load_alert_params(self, codes: list[str]) -> dict:
        today = datetime.now().strftime('%Y-%m-%d')
        cache_entry = self._alert_params_cache.get(today)
        if cache_entry and cache_entry.get('_queried_codes', set()) >= set(codes):
            result = cache_entry.get('params', {})
            missing = [c for c in codes if c not in result]
            if not missing:
                return result
            if not self._should_retry_params():
                return result
            # 缓存中有缺失且到了重试时间，fall through 重新加载

        result = self._fetch_alert_params(codes)

        missing = [c for c in codes if c not in result]
        if missing and self._should_retry_params():
            logger.info(f'[盯盘告警] {len(missing)}只缺少alert_params，触发7d分析重试: {missing}')
            self._last_params_retry = datetime.now()
            try:
                from app.services.watch_analysis_service import WatchAnalysisService
                WatchAnalysisService.analyze_stocks('7d')
                result = self._fetch_alert_params(codes)
                still_missing = [c for c in codes if c not in result]
                if still_missing:
                    logger.warning(f'[盯盘告警] 重试后仍有{len(still_missing)}只缺少alert_params: {still_missing}')
            except Exception as e:
                logger.error(f'[盯盘告警] 7d分析重试失败: {e}')

        self._alert_params_cache = {today: {'params': result, '_queried_codes': set(codes)}}
        return result

    def _should_retry_params(self) -> bool:
        if self._last_params_retry is None:
            return True
        return (datetime.now() - self._last_params_retry).total_seconds() >= PARAMS_RETRY_INTERVAL

    @staticmethod
    def _fetch_alert_params(codes: list[str]) -> dict:
        from app.services.watch_service import WatchService
        all_analyses = WatchService.get_all_today_analyses()
        result = {}
        for code in codes:
            analysis_7d = all_analyses.get(code, {}).get('7d', {})
            detail = analysis_7d.get('detail', {})
            alert_params = detail.get('alert_params', {})
            if alert_params:
                alert_params['support_levels'] = analysis_7d.get('support_levels', [])
                alert_params['resistance_levels'] = analysis_7d.get('resistance_levels', [])
                alert_params['ma_levels'] = detail.get('ma_levels', {})
                result[code] = alert_params
        return result

    def _calc_td_if_due(self, codes: list[str], data_service) -> dict:
        now = datetime.now()
        if self._last_td_calc and (now - self._last_td_calc).total_seconds() < TD_CALC_INTERVAL:
            return self._td_cache

        from app.services.td_sequential import TDSequentialService
        trend = data_service.get_trend_data(codes, days=60)
        td_results = {}
        for stock in trend.get('stocks', []):
            code = stock.get('stock_code')
            ohlc = stock.get('data', [])
            if code and ohlc:
                td_results[code] = TDSequentialService.calculate(ohlc)

        self._last_td_calc = now
        self._td_cache = td_results
        return td_results

    @staticmethod
    def _calc_trading_minutes(codes: list[str], items: list, calendar_service) -> dict:
        market_map = {w.stock_code: w.market for w in items}

        TOTAL_MINUTES = {
            'A': 240, 'US': 390, 'HK': 390,
            'KR': 390, 'TW': 270, 'JP': 300,
        }

        SESSIONS = {
            'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
            'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
        }

        result = {}
        for code in codes:
            market = market_map.get(code, 'A')
            total = TOTAL_MINUTES.get(market, 390)
            now_dt = calendar_service.get_market_now(market)
            now_t = now_dt.time()

            sessions = SESSIONS.get(market)
            if sessions:
                elapsed = 0
                for s_open, s_close in sessions:
                    if now_t >= s_close:
                        elapsed += (datetime.combine(now_dt.date(), s_close) - datetime.combine(now_dt.date(), s_open)).seconds // 60
                    elif now_t > s_open:
                        elapsed += (datetime.combine(now_dt.date(), now_t) - datetime.combine(now_dt.date(), s_open)).seconds // 60
            else:
                open_t, close_t = calendar_service.get_market_hours(market, now_dt.date())
                if open_t is None or close_t is None:
                    elapsed = 0
                elif now_t >= close_t:
                    elapsed = total
                elif now_t > open_t:
                    elapsed = (datetime.combine(now_dt.date(), now_t) - datetime.combine(now_dt.date(), open_t)).seconds // 60
                else:
                    elapsed = 0

            result[code] = {'elapsed': elapsed, 'total': total}
        return result
