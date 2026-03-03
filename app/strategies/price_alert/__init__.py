"""价格预警策略 — 基于 SignalDetector 的4种信号"""
import logging
from datetime import date
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class PriceAlertStrategy(Strategy):
    name = "price_alert"
    description = "价格预警（缩量突破/新高/顶部巨量/MA5交叉）"
    schedule = "*/5 9-15 * * 1-5"

    def scan(self) -> list[Signal]:
        from app.services.position import PositionService
        from app.services.signal_cache import SignalCacheService
        from app.services.trading_calendar import TradingCalendarService
        from app.models.stock import Stock
        from app.utils.market_identifier import MarketIdentifier

        signals = []
        try:
            latest_date = PositionService.get_latest_date()
            if not latest_date:
                return signals

            positions = PositionService.get_snapshot(latest_date)
            codes = [p.stock_code for p in positions]
            if not codes:
                return signals

            # 检查是否有任何持仓市场在交易中
            markets = set()
            for code in codes:
                m = MarketIdentifier.identify(code)
                if m:
                    markets.add(m)
            if not any(TradingCalendarService.is_market_open(m) for m in markets):
                return signals

            a_share_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
            if not a_share_codes:
                return signals

            name_map = {}
            stocks = Stock.query.filter(Stock.stock_code.in_(a_share_codes)).all()
            for s in stocks:
                name_map[s.stock_code] = s.stock_name

            # 只取当天信号，避免重复推送历史信号
            today = date.today()
            cached = SignalCacheService.get_cached_signals_with_names(
                a_share_codes, name_map, start_date=today, end_date=today
            )

            for sig_type in ['buy_signals', 'sell_signals']:
                for sig in cached.get(sig_type, []):
                    priority = "HIGH" if sig.get('type') == 'sell' else "MEDIUM"
                    signals.append(Signal(
                        strategy=self.name,
                        priority=priority,
                        title=f"{sig.get('stock_name', '')} - {sig.get('name', '')}",
                        detail=sig.get('description', ''),
                        data=sig,
                    ))
        except Exception as e:
            logger.error(f'[价格预警] 扫描失败: {e}')

        return signals
